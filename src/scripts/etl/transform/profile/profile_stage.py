"""Full-frame stage profile (raw or transformed) over frozen Parquet snapshots via DuckDB.

Read-only against frozen Parquet handoff snapshots under
``outputs/etl/load/phase*_{raw,transformed}_*``. Produces compact,
self-contained CSV outputs under ``outputs/etl/transform/profile/<stage>/``
covering L1 cleaning anomalies, L2 sampling-frame compatibility, L3 wallet-level
H1-H6 feature distributions, histograms, and reconciled n-flow tables so
downstream EDA and raw-vs-transformed comparisons can run offline without a
live PostgreSQL instance.

    python -m src.scripts.etl.transform.profile.profile_stage --stage raw
    python -m src.scripts.etl.transform.profile.profile_stage --stage transformed
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.scripts.config import ETL_OUTPUT_DIR, PROFILING_OUTPUT_DIR
from src.scripts.etl.transform.profile.schema import VALID_STAGES, stage_output_dir

# Physical upper ceilings for L1 amount validation (documented snapshot constants).
USDT_SUPPLY_CEILING = 94_248_192_941.363764  # Tronscan TRON USDT total supply (2026-11-10)
TRX_SUPPLY_CEILING = 100_000_000_000.0  # TRON TRX genesis/historical ceiling (> current ~86-95B)
UINT256_SENTINEL_FLOOR = 1e70  # catches 2^256/1e6 (~1.1579e71) and 2^255/1e6 (~5.7896e70)
DUST_UPPER_BOUND = 0.01
LARGE_REVIEW_LOWER_BOUND = 1_000_000.0

# TRON mainnet launch timestamp (2018-06-25T00:00:00Z) and snapshot upper bound.
TRON_MAINNET_START = datetime(2018, 6, 25, tzinfo=UTC)
DEFAULT_FUTURE_CUTOFF = datetime(2026, 11, 27, tzinfo=UTC)

H1_MAX_PASSTHROUGH_SEC = 900.0  # 15 minutes
H2_MAX_LIFETIME_DAYS = 7.0
H2_MIN_BURST_RATIO = 0.75
H4_MIN_JACCARD = 0.50
H6_MAX_CV = 0.15

COHORT_ORDER = ("illicit", "suspicious", "licit", "unlabeled")


def supply_ceiling_for(token_symbol: str) -> float:
    """Return physical supply ceiling for a token symbol."""
    if token_symbol == "USDT":
        return USDT_SUPPLY_CEILING
    if token_symbol == "TRX":
        return TRX_SUPPLY_CEILING
    raise ValueError(f"unsupported token_symbol: {token_symbol!r}")


def classify_amount_flag(
    amount: float | None,
    token_symbol: str,
    *,
    amount_exact: str | None = None,
) -> str:
    """Pure L1 amount-flag rule matching priority:
    null -> negative -> sentinel -> above_supply -> zero -> dust -> large_review -> ok.
    """
    if amount is None or (isinstance(amount, float) and math.isnan(amount)):
        return "null"
    if amount < 0:
        return "negative"
    if amount >= UINT256_SENTINEL_FLOOR or (
        amount_exact is not None
        and amount_exact.split(".", 1)[0].lstrip("-")
        in {
            "115792089237316200000000000000000000000000000000000000000000000000000000",
            "115792089237316195423570985008687907853269984665640564039457584007913129",
            "57896044618658100000000000000000000000000000000000000000000000000000000",
        }
    ):
        return "sentinel"
    if amount > supply_ceiling_for(token_symbol):
        return "above_supply"
    if amount == 0:
        return "zero"
    if amount < DUST_UPPER_BOUND:
        return "dust"
    if amount > LARGE_REVIEW_LOWER_BOUND:
        return "large_review"
    return "ok"


def classify_timestamp_flag(
    timestamp: datetime | None,
    *,
    future_cutoff: datetime = DEFAULT_FUTURE_CUTOFF,
) -> str:
    """Pure L1 timestamp-flag rule using TRON mainnet launch as lower bound."""
    if timestamp is None:
        return "null"
    ts = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)
    if ts < TRON_MAINNET_START:
        return "pre_mainnet"
    if ts > future_cutoff:
        return "future"
    return "ok"


def recommend_scale(
    *,
    min_value: float | None,
    max_value: float | None,
    skewness: float | None,
    p50: float | None,
    p99: float | None,
    zero_share: float | None,
    is_discrete: bool = False,
) -> str:
    """Classify recommended transform/scaling strategy from distribution shape.

    Note: stateless transforms (log1p) belong in L3 features; stateful scaling
    (RobustScaler / StandardScaler / Winsorization) belongs in ML train splits only.
    """
    if is_discrete:
        return "discrete_or_ordinal"
    if min_value is None or max_value is None:
        return "insufficient_data"
    if min_value >= 0.0 and max_value <= 1.0:
        if zero_share is not None and zero_share >= 0.5:
            return "bounded_0_1_zero_inflated"
        return "bounded_0_1"
    ratio = (p99 / p50) if (p50 is not None and p50 > 0 and p99 is not None) else None
    heavy_tail = (
        (skewness is not None and abs(skewness) >= 2.0)
        or (ratio is not None and ratio >= 20.0)
    )
    if min_value >= 0.0 and heavy_tail:
        return "log1p_in_L3_plus_train_only_robust_scaler"
    if heavy_tail:
        return "yeo_johnson_or_train_only_robust_scaler"
    return "raw_or_train_only_standard_scaler"


def _latest_snapshot_dir(load_dir: Path, schema: str, stage: str = "raw") -> Path:
    candidates = sorted(
        path for path in load_dir.glob(f"phase*_{stage}_{schema}_*") if path.is_dir()
    )
    if not candidates:
        raise FileNotFoundError(f"no {stage} snapshot found for {schema} in {load_dir}")
    return candidates[-1]


def _latest_transformed_snapshot_dir(load_dir: Path) -> Path:
    candidates = sorted(
        path for path in load_dir.glob("phase*_transformed_*") if path.is_dir()
    )
    if not candidates:
        raise FileNotFoundError(f"no transformed snapshot found in {load_dir}")
    return candidates[-1]


def _load_manifest(snapshot_dir: Path) -> dict[str, Any]:
    manifest_path = snapshot_dir / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _table_parquet(snapshot_dir: Path, manifest: dict[str, Any], table: str) -> str:
    file_name = manifest["tables"][table]["file"]
    return str((snapshot_dir / file_name).resolve())


def _connect_duckdb(memory_limit: str, temp_dir: Path) -> duckdb.DuckDBPyConnection:
    temp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET memory_limit = '{memory_limit}'")
    con.execute("SET threads = 4")
    con.execute(f"SET temp_directory = '{temp_dir.as_posix()}'")
    con.execute("SET preserve_insertion_order = false")
    return con


def _create_source_views(
    con: duckdb.DuckDBPyConnection,
    illicit_dir: Path,
    illicit_manifest: dict[str, Any],
    licit_dir: Path,
    licit_manifest: dict[str, Any],
) -> None:
    tables = {
        "i_accounts": _table_parquet(illicit_dir, illicit_manifest, "accounts"),
        "i_blacklist": _table_parquet(illicit_dir, illicit_manifest, "blacklisted_wallets"),
        "i_tx": _table_parquet(illicit_dir, illicit_manifest, "transactions"),
        "i_hops": _table_parquet(illicit_dir, illicit_manifest, "wallet_hops"),
        "l_accounts": _table_parquet(licit_dir, licit_manifest, "accounts"),
        "l_seeds": _table_parquet(licit_dir, licit_manifest, "seed_wallets"),
        "l_tx": _table_parquet(licit_dir, licit_manifest, "transactions"),
        "l_hops": _table_parquet(licit_dir, licit_manifest, "wallet_hops"),
    }
    for view_name, path in tables.items():
        escaped = path.replace("'", "''")
        con.execute(
            f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM read_parquet('{escaped}')"
        )


def _refresh_exact_columns(
    con: duckdb.DuckDBPyConnection,
    schema: str,
    table_views: dict[str, str],
    snapshot_id: str,
    is_partial: bool,
    output_dir: Path,
) -> Path:
    """Recompute exact non-null/null counts from frozen Parquet (no TABLESAMPLE bug)."""
    rows_out: list[dict[str, Any]] = []
    for table_name, view_name in table_views.items():
        desc = con.execute(f"DESCRIBE SELECT * FROM {view_name}").fetchall()
        total_rows = int(con.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()[0])
        agg_parts = []
        time_cols: list[str] = []
        for col_name, col_type, *_ in desc:
            quoted = f'"{col_name}"'
            agg_parts.append(f"COUNT({quoted}) AS nn_{col_name}")
            agg_parts.append(f"APPROX_COUNT_DISTINCT({quoted}) AS nd_{col_name}")
            if "TIMESTAMP" in col_type.upper():
                time_cols.append(col_name)
                agg_parts.append(f"MIN({quoted}) AS min_{col_name}")
                agg_parts.append(f"MAX({quoted}) AS max_{col_name}")
        result = con.execute(f"SELECT {', '.join(agg_parts)} FROM {view_name}").fetchone()
        col_map: dict[str, Any] = {}
        idx = 0
        for col_name, col_type, *_ in desc:
            col_map[f"nn_{col_name}"] = result[idx]
            col_map[f"nd_{col_name}"] = result[idx + 1]
            idx += 2
            if col_name in time_cols:
                col_map[f"min_{col_name}"] = result[idx]
                col_map[f"max_{col_name}"] = result[idx + 1]
                idx += 2
        for col_name, col_type, *_ in desc:
            non_null = int(col_map[f"nn_{col_name}"])
            nulls = total_rows - non_null
            rows_out.append(
                {
                    "schema": schema,
                    "table": table_name,
                    "column": col_name,
                    "data_type": col_type,
                    "nullable": nulls > 0,
                    "rows": total_rows,
                    "sample_rows": total_rows,
                    "non_null": non_null,
                    "nulls": nulls,
                    "null_share": (nulls / total_rows) if total_rows else 0.0,
                    "distinct_approx": int(col_map[f"nd_{col_name}"]),
                    "min": col_map.get(f"min_{col_name}"),
                    "max": col_map.get(f"max_{col_name}"),
                    "method": "exact_parquet",
                    "snapshot_at": snapshot_id,
                    "is_partial": is_partial,
                }
            )
    path = output_dir / f"local_{schema}_columns.csv"
    pd.DataFrame(rows_out).to_csv(path, index=False)
    return path


def _amount_flag_sql(amount_col: str = "amount", token_col: str = "token_symbol") -> str:
    return f"""
    CASE
        WHEN {amount_col} IS NULL OR isnan({amount_col}) THEN 'null'
        WHEN {amount_col} < 0 THEN 'negative'
        WHEN {amount_col} >= {UINT256_SENTINEL_FLOOR} THEN 'sentinel'
        WHEN ({token_col} = 'USDT' AND {amount_col} > {USDT_SUPPLY_CEILING})
          OR ({token_col} = 'TRX' AND {amount_col} > {TRX_SUPPLY_CEILING}) THEN 'above_supply'
        WHEN {amount_col} = 0 THEN 'zero'
        WHEN {amount_col} < {DUST_UPPER_BOUND} THEN 'dust'
        WHEN {amount_col} > {LARGE_REVIEW_LOWER_BOUND} THEN 'large_review'
        ELSE 'ok'
    END
    """


def _timestamp_flag_sql(ts_col: str = "block_timestamp") -> str:
    return f"""
    CASE
        WHEN {ts_col} IS NULL THEN 'null'
        WHEN {ts_col} < TIMESTAMPTZ '2018-06-25 00:00:00+00' THEN 'pre_mainnet'
        WHEN {ts_col} > TIMESTAMPTZ '2026-11-27 00:00:00+00' THEN 'future'
        ELSE 'ok'
    END
    """


def _build_cleaning_profile(
    con: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    is_partial: bool,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(
        section: str,
        schema: str,
        token: str,
        category: str,
        count: int,
        denominator: int,
        note: str = "",
    ) -> None:
        rows.append(
            {
                "section": section,
                "schema": schema,
                "token_symbol": token,
                "category": category,
                "count": int(count),
                "denominator": int(denominator),
                "share": (count / denominator) if denominator else 0.0,
                "note": note,
                "snapshot_at": snapshot_id,
                "is_partial": is_partial,
            }
        )

    # 1. Cross-schema tx_hash overlap and field conflict audit
    ov = con.execute(
        """
        WITH i_cnt AS (SELECT COUNT(*) AS n FROM i_tx),
             l_cnt AS (SELECT COUNT(*) AS n FROM l_tx),
             m AS (
                 SELECT COUNT(*) AS matched,
                        COUNT(*) FILTER (WHERE i.token_symbol IS DISTINCT FROM l.token_symbol) AS diff_token,
                        COUNT(*) FILTER (WHERE i.amount IS DISTINCT FROM l.amount) AS diff_amount,
                        COUNT(*) FILTER (WHERE i.amount_exact IS DISTINCT FROM l.amount_exact) AS diff_amount_exact,
                        COUNT(*) FILTER (WHERE i.from_address IS DISTINCT FROM l.from_address) AS diff_from,
                        COUNT(*) FILTER (WHERE i.to_address IS DISTINCT FROM l.to_address) AS diff_to,
                        COUNT(*) FILTER (WHERE i.block_timestamp IS DISTINCT FROM l.block_timestamp) AS diff_ts
                 FROM i_tx i
                 INNER JOIN l_tx l USING (tx_hash)
             )
        SELECT i_cnt.n, l_cnt.n, m.*
        FROM i_cnt, l_cnt, m
        """
    ).fetchone()
    total_raw_tx = int(ov[0]) + int(ov[1])
    matched = int(ov[2])
    add("cross_schema_tx_overlap", "both", "ALL", "raw_union_rows", total_raw_tx, total_raw_tx, "illicit + licit raw tx rows")
    add("cross_schema_tx_overlap", "both", "ALL", "overlap_tx_hash", matched, total_raw_tx, "tx_hash present in both schemas")
    add("cross_schema_tx_overlap", "both", "ALL", "deduped_tx_rows", total_raw_tx - matched, total_raw_tx, "unique tx_hash across schemas")
    for idx, name in enumerate(
        ("diff_token", "diff_amount", "diff_amount_exact", "diff_from", "diff_to", "diff_ts"),
        start=3,
    ):
        add("cross_schema_tx_overlap", "both", "ALL", name, int(ov[idx]), matched, "field differs on shared tx_hash")

    # 2. Per-schema, per-token amount flags (USDT + TRX)
    flag_expr = _amount_flag_sql("amount", "token_symbol")
    for schema, view in (("illicit", "i_tx"), ("licit", "l_tx")):
        df_flags = con.execute(
            f"""
            WITH tagged AS (
                SELECT token_symbol, {flag_expr} AS flag
                FROM {view}
            ),
            totals AS (
                SELECT token_symbol, COUNT(*) AS denom FROM tagged GROUP BY token_symbol
            )
            SELECT t.token_symbol, t.flag, COUNT(*) AS n, tot.denom
            FROM tagged t
            JOIN totals tot USING (token_symbol)
            GROUP BY t.token_symbol, t.flag, tot.denom
            ORDER BY t.token_symbol, t.flag
            """
        ).fetchall()
        for token, flag, cnt, denom in df_flags:
            add("amount_flag", schema, str(token), str(flag), int(cnt), int(denom))

    # 3. TRX micro-dust & exact 1-SUN + corrupt 4444.444444 check
    for schema, view in (("illicit", "i_tx"), ("licit", "l_tx")):
        trx_det = con.execute(
            f"""
            SELECT COUNT(*) AS n_trx,
                   COUNT(*) FILTER (WHERE amount = 0.000001) AS eq_1sun,
                   COUNT(*) FILTER (WHERE amount > 0.000001 AND amount < 0.01) AS gt_1sun_lt_001,
                   COUNT(*) FILTER (WHERE ABS(amount - 4444.444444) < 1e-5) AS eq_4444_444444,
                   COUNT(*) FILTER (WHERE amount > {TRX_SUPPLY_CEILING}) AS above_trx_supply
            FROM {view}
            WHERE token_symbol = 'TRX'
            """
        ).fetchone()
        n_trx = int(trx_det[0])
        add("trx_anomaly_detail", schema, "TRX", "exact_1_sun_0.000001", int(trx_det[1]), n_trx, "likely 1-SUN spam/memo dust")
        add("trx_anomaly_detail", schema, "TRX", "micro_dust_gt_1sun_lt_0.01", int(trx_det[2]), n_trx, "sub-cent TRX transfers")
        add("trx_anomaly_detail", schema, "TRX", "repeated_4444.444444_artifact", int(trx_det[3]), n_trx, "repeated numeric artifact in TRX")
        add("trx_anomaly_detail", schema, "TRX", "above_100b_trx_supply", int(trx_det[4]), n_trx, "physically impossible TRX amount")

    # 4. Hop-edge dependency on flagged transactions (via_tx_hash)
    ts_expr = _timestamp_flag_sql("block_timestamp")
    hop_dep = con.execute(
        f"""
        WITH tx_flags AS (
            SELECT tx_hash, {flag_expr} AS amount_flag, {ts_expr} AS ts_flag
            FROM i_tx
        ),
        tot AS (SELECT COUNT(*) AS n FROM i_hops)
        SELECT COALESCE(tx.amount_flag, 'tx_not_in_illicit_tx') AS flag,
               COUNT(*) AS n,
               tot.n AS denom
        FROM i_hops h
        LEFT JOIN tx_flags tx ON h.via_tx_hash = tx.tx_hash
        CROSS JOIN tot
        GROUP BY 1, tot.n
        ORDER BY n DESC
        """
    ).fetchall()
    for flag, cnt, denom in hop_dep:
        add("hop_edge_tx_flag", "illicit", "ALL", str(flag), int(cnt), int(denom), "illicit.wallet_hops via_tx_hash status")

    # 5. Timestamp flags & yearly distribution (pre-mainnet vs 2018-2026)
    for schema, view in (("illicit", "i_tx"), ("licit", "l_tx")):
        tot = int(con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0])
        ts_rows = con.execute(
            f"""
            SELECT {ts_expr} AS flag, COUNT(*) AS n
            FROM {view}
            GROUP BY 1 ORDER BY 1
            """
        ).fetchall()
        for flag, cnt in ts_rows:
            add("timestamp_flag", schema, "ALL", str(flag), int(cnt), tot)

        yr_rows = con.execute(
            f"""
            SELECT CASE
                       WHEN block_timestamp < TIMESTAMPTZ '2018-06-25 00:00:00+00'
                       THEN 'pre_mainnet_' || CAST(EXTRACT(YEAR FROM block_timestamp) AS VARCHAR)
                       ELSE CAST(EXTRACT(YEAR FROM block_timestamp) AS VARCHAR)
                   END AS yr,
                   token_symbol,
                   COUNT(*) AS n
            FROM {view}
            GROUP BY 1, 2
            ORDER BY 1, 2
            """
        ).fetchall()
        for yr, tok, cnt in yr_rows:
            add("tx_by_year", schema, str(tok), str(yr), int(cnt), tot)

    # 6. Reconcile the hop-only wallets (in illicit.wallet_hops but not in accounts union)
    hop_only = con.execute(
        """
        WITH acc_u AS (
            SELECT address FROM i_accounts
            UNION
            SELECT address FROM l_accounts
        ),
        hop_w AS (
            SELECT DISTINCT wallet_address FROM i_hops WHERE hop_level BETWEEN 1 AND 5
        ),
        hop_only_w AS (
            SELECT h.wallet_address
            FROM hop_w h
            WHERE NOT EXISTS (SELECT 1 FROM acc_u a WHERE a.address = h.wallet_address)
        ),
        tx_w AS (
            SELECT from_address AS addr FROM i_tx
            UNION SELECT to_address AS addr FROM i_tx
            UNION SELECT from_address AS addr FROM l_tx
            UNION SELECT to_address AS addr FROM l_tx
        )
        SELECT (SELECT COUNT(*) FROM hop_w) AS total_hop_ge1,
               (SELECT COUNT(*) FROM hop_only_w) AS hop_only_not_in_accounts,
               (SELECT COUNT(*) FROM hop_only_w h WHERE EXISTS (SELECT 1 FROM tx_w t WHERE t.addr = h.wallet_address)) AS hop_only_in_tx,
               (SELECT COUNT(*) FROM hop_only_w h WHERE EXISTS (SELECT 1 FROM i_blacklist b WHERE b.label = 1 AND b.wallet_address = h.wallet_address)) AS hop_only_blacklisted
        """
    ).fetchone()
    add("hop_only_reconciliation", "both", "ALL", "hop_only_not_in_accounts", int(hop_only[1]), int(hop_only[0]), "in illicit.wallet_hops (1..5) but absent from accounts union")
    add("hop_only_reconciliation", "both", "ALL", "hop_only_present_in_transactions", int(hop_only[2]), int(hop_only[1]), "hop-only wallets with >=1 tx")
    add("hop_only_reconciliation", "both", "ALL", "hop_only_blacklisted", int(hop_only[3]), int(hop_only[1]), "hop-only wallets in blacklist")

    return pd.DataFrame(rows)


def _materialize_cohort_and_clean_tx(con: duckdb.DuckDBPyConnection) -> None:
    """Create session-local temp tables in DuckDB (never modifies any persisted DB)."""
    # L2 cohort table over full universe (accounts union + blacklist + hop 1..5 wallets so counts reconcile 100%).
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE cohort_wallet AS
        WITH universe AS (
            SELECT address AS wallet_address FROM i_accounts
            UNION
            SELECT address AS wallet_address FROM l_accounts
            UNION
            SELECT wallet_address FROM i_blacklist WHERE label = 1
            UNION
            SELECT wallet_address FROM i_hops WHERE hop_level BETWEEN 1 AND 5
        ),
        bl AS (
            SELECT DISTINCT wallet_address FROM i_blacklist WHERE label = 1
        ),
        hop_agg AS (
            SELECT wallet_address,
                   MIN(hop_level) AS min_hop_level,
                   COUNT(DISTINCT seed_address) AS seed_count,
                   COUNT(*) AS hop_row_count
            FROM i_hops
            WHERE hop_level BETWEEN 1 AND 5
            GROUP BY wallet_address
        ),
        in_acc AS (
            SELECT address AS wallet_address FROM i_accounts
            UNION
            SELECT address AS wallet_address FROM l_accounts
        ),
        in_licit AS (
            SELECT DISTINCT address AS wallet_address FROM l_accounts
        )
        SELECT u.wallet_address,
               CASE
                   WHEN bl.wallet_address IS NOT NULL THEN 'illicit'
                   WHEN h.wallet_address IS NOT NULL THEN 'suspicious'
                   WHEN l.wallet_address IS NOT NULL THEN 'licit'
                   ELSE 'unlabeled'
               END AS wallet_class,
               CASE WHEN bl.wallet_address IS NULL THEN h.min_hop_level ELSE NULL END AS min_hop_level,
               COALESCE(h.seed_count, 0) AS seed_count,
               COALESCE(h.hop_row_count, 0) AS hop_row_count,
               (acc.wallet_address IS NOT NULL) AS in_accounts_table
        FROM universe u
        LEFT JOIN bl ON bl.wallet_address = u.wallet_address
        LEFT JOIN hop_agg h ON h.wallet_address = u.wallet_address
        LEFT JOIN in_licit l ON l.wallet_address = u.wallet_address
        LEFT JOIN in_acc acc ON acc.wallet_address = u.wallet_address
        """
    )

    flag_expr = _amount_flag_sql("amount", "token_symbol")
    ts_expr = _timestamp_flag_sql("block_timestamp")
    # L1 deduplicated clean transactions (compact columns only; drops tx_hash/fee_trx after dedupe).
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE clean_tx AS
        WITH raw_u AS (
            SELECT tx_hash, block_timestamp, from_address, to_address,
                   token_symbol, amount, 1 AS src_rank,
                   {flag_expr} AS amount_flag,
                   {ts_expr} AS ts_flag
            FROM i_tx
            UNION ALL
            SELECT tx_hash, block_timestamp, from_address, to_address,
                   token_symbol, amount, 2 AS src_rank,
                   {flag_expr} AS amount_flag,
                   {ts_expr} AS ts_flag
            FROM l_tx
        ),
        ranked AS (
            SELECT block_timestamp, from_address, to_address,
                   (token_symbol = 'USDT') AS is_usdt,
                   amount,
                   (amount_flag = 'zero') AS is_zero,
                   amount_flag,
                   ts_flag,
                   ROW_NUMBER() OVER (
                       PARTITION BY tx_hash
                       ORDER BY
                           CASE WHEN amount_flag IN ('sentinel', 'above_supply', 'negative', 'null') THEN 1 ELSE 0 END ASC,
                           CASE WHEN ts_flag != 'ok' THEN 1 ELSE 0 END ASC,
                           src_rank ASC
                   ) AS rn
            FROM raw_u
        )
        SELECT block_timestamp, from_address, to_address, is_usdt, amount, is_zero
        FROM ranked
        WHERE rn = 1
          AND ts_flag = 'ok'
          AND amount_flag NOT IN ('sentinel', 'above_supply', 'negative', 'null')
        """
    )


def _build_sampling_frame_profile(
    con: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    is_partial: bool,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(section: str, group: str, metric: str, value: Any, denominator: int | None = None, note: str = "") -> None:
        rows.append(
            {
                "section": section,
                "group": group,
                "metric": metric,
                "value": value,
                "denominator": denominator,
                "note": note,
                "snapshot_at": snapshot_id,
                "is_partial": is_partial,
            }
        )

    # 1. Reconciled full-universe cohort counts (including vs excluding hop-only)
    for wc, n_all, n_acc, n_hop_only in con.execute(
        """
        SELECT wallet_class,
               COUNT(*) AS n_all,
               COUNT(*) FILTER (WHERE in_accounts_table) AS n_in_accounts,
               COUNT(*) FILTER (WHERE NOT in_accounts_table) AS n_hop_only
        FROM cohort_wallet
        GROUP BY wallet_class
        """
    ).fetchall():
        add("cohort_universe", str(wc), "wallets_total", int(n_all), None, "accounts + blacklist + hop(1..5) universe")
        add("cohort_universe", str(wc), "wallets_in_accounts", int(n_acc), int(n_all))
        add("cohort_universe", str(wc), "wallets_hop_only", int(n_hop_only), int(n_all))

    # 2. Schema-level time range, token mix, and fee_trx compatibility (illicit vs licit)
    for schema, view in (("illicit", "i_tx"), ("licit", "l_tx")):
        stats = con.execute(
            f"""
            SELECT COUNT(*) AS n,
                   COUNT(*) FILTER (WHERE token_symbol = 'USDT') AS n_usdt,
                   COUNT(*) FILTER (WHERE token_symbol = 'TRX') AS n_trx,
                   MIN(block_timestamp) FILTER (WHERE block_timestamp >= TIMESTAMPTZ '2018-06-25 00:00:00+00') AS min_ts,
                   MAX(block_timestamp) FILTER (WHERE block_timestamp <= TIMESTAMPTZ '2026-11-27 00:00:00+00') AS max_ts,
                   quantile_cont(EPOCH(block_timestamp), 0.10) FILTER (WHERE block_timestamp >= TIMESTAMPTZ '2018-06-25 00:00:00+00') AS p10_epoch,
                   quantile_cont(EPOCH(block_timestamp), 0.50) FILTER (WHERE block_timestamp >= TIMESTAMPTZ '2018-06-25 00:00:00+00') AS p50_epoch,
                   quantile_cont(EPOCH(block_timestamp), 0.90) FILTER (WHERE block_timestamp >= TIMESTAMPTZ '2018-06-25 00:00:00+00') AS p90_epoch,
                   COUNT(DISTINCT fee_trx) AS fee_distinct,
                   AVG(CASE WHEN fee_trx = 0 THEN 1.0 ELSE 0.0 END) AS fee_zero_share,
                   MAX(fee_trx) AS fee_max
            FROM {view}
            """
        ).fetchone()
        n = int(stats[0])
        add("schema_frame", schema, "tx_rows", n, n)
        add("schema_frame", schema, "usdt_share", int(stats[1]) / n if n else 0.0, n)
        add("schema_frame", schema, "trx_share", int(stats[2]) / n if n else 0.0, n)
        add("schema_frame", schema, "valid_ts_min", str(stats[3]), n)
        add("schema_frame", schema, "valid_ts_max", str(stats[4]), n)
        add("schema_frame", schema, "valid_ts_p10", str(datetime.fromtimestamp(float(stats[5]), UTC)), n)
        add("schema_frame", schema, "valid_ts_p50", str(datetime.fromtimestamp(float(stats[6]), UTC)), n)
        add("schema_frame", schema, "valid_ts_p90", str(datetime.fromtimestamp(float(stats[7]), UTC)), n)
        add("schema_frame", schema, "fee_trx_distinct", int(stats[8]), n)
        add("schema_frame", schema, "fee_trx_zero_share", float(stats[9]), n)
        add("schema_frame", schema, "fee_trx_max", float(stats[10]), n)

    # 3. Hop-band sizes inside suspicious (nested factor) and licit hops
    sus_total = int(con.execute("SELECT COUNT(*) FROM cohort_wallet WHERE wallet_class = 'suspicious'").fetchone()[0])
    for hop, cnt in con.execute(
        """
        SELECT min_hop_level, COUNT(*)
        FROM cohort_wallet
        WHERE wallet_class = 'suspicious'
        GROUP BY min_hop_level
        ORDER BY min_hop_level
        """
    ).fetchall():
        add("suspicious_hop_band", f"hop_{int(hop)}", "wallets", int(cnt), sus_total, "nested inside suspicious")

    licit_hop_total = int(con.execute("SELECT COUNT(DISTINCT wallet_address) FROM l_hops").fetchone()[0])
    for hop, cnt in con.execute(
        """
        SELECT min_hop, COUNT(*)
        FROM (SELECT wallet_address, MIN(hop_level) AS min_hop FROM l_hops GROUP BY wallet_address)
        GROUP BY min_hop ORDER BY min_hop
        """
    ).fetchall():
        add("licit_hop_band", f"hop_{int(hop)}", "wallets", int(cnt), licit_hop_total, "from licit.wallet_hops")

    # 4. Seed-cluster size distribution (illicit vs licit seeds)
    for label, view in (("illicit_seeds", "i_hops"), ("licit_seeds", "l_hops")):
        sq = con.execute(
            f"""
            WITH sc AS (
                SELECT seed_address, COUNT(DISTINCT wallet_address) AS cluster_size
                FROM {view}
                WHERE hop_level >= 1
                GROUP BY seed_address
            )
            SELECT COUNT(*) AS n_seeds,
                   MIN(cluster_size),
                   quantile_cont(cluster_size, 0.25),
                   quantile_cont(cluster_size, 0.50),
                   quantile_cont(cluster_size, 0.75),
                   quantile_cont(cluster_size, 0.90),
                   quantile_cont(cluster_size, 0.99),
                   MAX(cluster_size),
                   AVG(cluster_size)
            FROM sc
            """
        ).fetchone()
        n_seeds = int(sq[0])
        for name, val in zip(
            ("n_seeds", "min", "p25", "p50", "p75", "p90", "p99", "max", "mean"),
            sq,
            strict=True,
        ):
            add("seed_cluster_size", label, name, float(val) if val is not None else None, n_seeds)

    return pd.DataFrame(rows)


def _materialize_wallet_features(con: duckdb.DuckDBPyConnection) -> None:
    """Compute full-frame wallet-level H1-H6 feature profile table in DuckDB.

    Decomposes distinct-edge degrees from scalar aggregates so DuckDB never builds
    multiple 50M-row COUNT(DISTINCT) hash tables concurrently.
    """
    # Lightweight VIEW over compact clean_tx (never materialized).
    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW wallet_events AS
        SELECT from_address AS wallet_address,
               'OUT' AS direction,
               block_timestamp,
               is_usdt,
               amount,
               is_zero
        FROM clean_tx
        UNION ALL
        SELECT to_address AS wallet_address,
               'IN' AS direction,
               block_timestamp,
               is_usdt,
               amount,
               is_zero
        FROM clean_tx
        """
    )

    # 1. Scalar wallet counts, volumes, H2 lifetime, H3 amount CV (zero COUNT(DISTINCT))
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE feat_scalar AS
        SELECT wallet_address,
               COUNT(*) FILTER (WHERE NOT is_zero) AS total_tx_count,
               COUNT(*) FILTER (WHERE is_zero) AS zero_tx_count,
               COUNT(*) FILTER (WHERE is_usdt AND NOT is_zero) AS usdt_tx_count,
               COUNT(*) FILTER (WHERE NOT is_usdt AND NOT is_zero) AS trx_tx_count,
               SUM(amount) FILTER (WHERE is_usdt AND NOT is_zero) AS usdt_volume,
               SUM(amount) FILTER (WHERE is_usdt AND direction = 'IN' AND NOT is_zero) AS usdt_in_volume,
               SUM(amount) FILTER (WHERE is_usdt AND direction = 'OUT' AND NOT is_zero) AS usdt_out_volume,
               SUM(amount) FILTER (WHERE NOT is_usdt AND NOT is_zero) AS trx_volume,
               CASE
                   WHEN COUNT(*) FILTER (WHERE NOT is_zero) >= 2
                   THEN EPOCH(MAX(block_timestamp) FILTER (WHERE NOT is_zero)
                              - MIN(block_timestamp) FILTER (WHERE NOT is_zero)) / 86400.0
                   ELSE NULL
               END AS tx_lifetime_days,
               CASE
                   WHEN COUNT(*) FILTER (WHERE is_usdt AND NOT is_zero) >= 5
                        AND AVG(amount) FILTER (WHERE is_usdt AND NOT is_zero) > 0
                   THEN STDDEV_SAMP(amount) FILTER (WHERE is_usdt AND NOT is_zero)
                        / AVG(amount) FILTER (WHERE is_usdt AND NOT is_zero)
                   ELSE NULL
               END AS amount_cv_usdt
        FROM wallet_events
        GROUP BY wallet_address
        """
    )

    # 2. Single directed edge deduplication -> powers H3 degrees + H4 Jaccard cleanly
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE distinct_edges AS
        SELECT from_address,
               to_address,
               BOOL_OR(is_usdt) AS has_usdt,
               BOOL_OR(NOT is_usdt) AS has_trx
        FROM clean_tx
        WHERE NOT is_zero
        GROUP BY from_address, to_address
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE feat_degrees AS
        WITH out_d AS (
            SELECT from_address AS wallet_address,
                   COUNT(*) AS out_degree_all,
                   COUNT(*) FILTER (WHERE has_usdt) AS out_degree_usdt
            FROM distinct_edges
            GROUP BY from_address
        ),
        in_d AS (
            SELECT to_address AS wallet_address,
                   COUNT(*) AS in_degree_all,
                   COUNT(*) FILTER (WHERE has_usdt) AS in_degree_usdt,
                   COUNT(*) FILTER (WHERE has_trx) AS trx_funder_count
            FROM distinct_edges
            GROUP BY to_address
        )
        SELECT COALESCE(o.wallet_address, i.wallet_address) AS wallet_address,
               COALESCE(i.in_degree_all, 0) AS in_degree_all,
               COALESCE(o.out_degree_all, 0) AS out_degree_all,
               COALESCE(i.in_degree_usdt, 0) AS in_degree_usdt,
               COALESCE(o.out_degree_usdt, 0) AS out_degree_usdt,
               COALESCE(i.trx_funder_count, 0) AS trx_funder_count
        FROM out_d o
        FULL OUTER JOIN in_d i USING (wallet_address)
        """
    )

    # 3. H4 Jaccard index directly from distinct_edges (only both-set wallets)
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE feat_h4_jaccard AS
        WITH eligible_w AS (
            SELECT wallet_address, trx_funder_count, out_degree_usdt AS usdt_recipient_count
            FROM feat_degrees
            WHERE trx_funder_count > 0 AND out_degree_usdt > 0
        ),
        trx_f AS (
            SELECT e.to_address AS wallet_address, e.from_address AS counterparty
            FROM distinct_edges e
            SEMI JOIN eligible_w w ON w.wallet_address = e.to_address
            WHERE e.has_trx
        ),
        usdt_r AS (
            SELECT e.from_address AS wallet_address, e.to_address AS counterparty
            FROM distinct_edges e
            SEMI JOIN eligible_w w ON w.wallet_address = e.from_address
            WHERE e.has_usdt
        ),
        inter AS (
            SELECT t.wallet_address, COUNT(*) AS inter_cnt
            FROM trx_f t
            INNER JOIN usdt_r u
              ON t.wallet_address = u.wallet_address AND t.counterparty = u.counterparty
            GROUP BY t.wallet_address
        )
        SELECT w.wallet_address,
               COALESCE(i.inter_cnt, 0)::DOUBLE
               / NULLIF((w.trx_funder_count + w.usdt_recipient_count - COALESCE(i.inter_cnt, 0))::DOUBLE, 0.0)
               AS jaccard_index
        FROM eligible_w w
        LEFT JOIN inter i USING (wallet_address)
        """
    )
    con.execute("DROP TABLE IF EXISTS distinct_edges")

    # 4. H1 pass-through speed (USDT IN -> next OUT lag) + H2 USDT 1-hour burst ratio
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE feat_usdt_temporal AS
        WITH usdt_win AS (
            SELECT wallet_address,
                   direction,
                   block_timestamp,
                   amount,
                   MAX(CASE WHEN direction = 'IN' THEN block_timestamp END) OVER (
                       PARTITION BY wallet_address
                       ORDER BY block_timestamp
                       ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                   ) AS prev_in_ts,
                   SUM(amount) OVER (
                       PARTITION BY wallet_address
                       ORDER BY block_timestamp
                       RANGE BETWEEN INTERVAL '1 hour' PRECEDING AND CURRENT ROW
                   ) AS win_1h_vol
            FROM wallet_events
            WHERE is_usdt AND NOT is_zero
        )
        SELECT wallet_address,
               COUNT(*) AS usdt_n,
               SUM(amount) AS total_usdt_vol,
               CASE WHEN SUM(amount) > 0 THEN MAX(win_1h_vol) / SUM(amount) ELSE NULL END AS burst_ratio_usdt_any,
               CASE WHEN COUNT(*) >= 5 AND SUM(amount) > 0 THEN MAX(win_1h_vol) / SUM(amount) ELSE NULL END AS burst_ratio_usdt,
               MIN(CASE
                       WHEN direction = 'OUT' AND prev_in_ts IS NOT NULL AND block_timestamp >= prev_in_ts
                       THEN EPOCH(block_timestamp - prev_in_ts)
                       ELSE NULL
                   END) AS min_passthrough_sec_usdt
        FROM usdt_win
        GROUP BY wallet_address
        """
    )

    # 5. H6 inter-arrival CV (all non-zero events AND OUT-only directional sensitivity)
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE feat_h6_cv AS
        WITH elig_all AS (
            SELECT wallet_address FROM feat_scalar WHERE total_tx_count >= 5
        ),
        all_gaps AS (
            SELECT e.wallet_address,
                   EPOCH(e.block_timestamp - LAG(e.block_timestamp) OVER (
                       PARTITION BY e.wallet_address ORDER BY e.block_timestamp
                   )) AS gap_sec
            FROM wallet_events e
            SEMI JOIN elig_all a USING (wallet_address)
            WHERE NOT e.is_zero
        ),
        all_agg AS (
            SELECT wallet_address,
                   CASE
                       WHEN COUNT(*) >= 5 AND AVG(gap_sec) > 0
                       THEN STDDEV_SAMP(gap_sec) / AVG(gap_sec)
                       ELSE NULL
                   END AS cv_delta_t_all
            FROM all_gaps
            GROUP BY wallet_address
        ),
        out_gaps AS (
            SELECT e.wallet_address,
                   EPOCH(e.block_timestamp - LAG(e.block_timestamp) OVER (
                       PARTITION BY e.wallet_address ORDER BY e.block_timestamp
                   )) AS gap_sec
            FROM wallet_events e
            SEMI JOIN elig_all a USING (wallet_address)
            WHERE NOT e.is_zero AND e.direction = 'OUT'
        ),
        out_agg AS (
            SELECT wallet_address,
                   CASE
                       WHEN COUNT(*) >= 5 AND AVG(gap_sec) > 0
                       THEN STDDEV_SAMP(gap_sec) / AVG(gap_sec)
                       ELSE NULL
                   END AS cv_delta_t_out
            FROM out_gaps
            GROUP BY wallet_address
        )
        SELECT COALESCE(a.wallet_address, o.wallet_address) AS wallet_address,
               a.cv_delta_t_all,
               o.cv_delta_t_out
        FROM all_agg a
        FULL OUTER JOIN out_agg o USING (wallet_address)
        """
    )

    con.execute("DROP VIEW IF EXISTS wallet_events")
    con.execute("DROP TABLE IF EXISTS clean_tx")

    # Combine into unified flat wallet-grain L3 profile table
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE wallet_profile AS
        SELECT c.wallet_address,
               c.wallet_class,
               c.min_hop_level::DOUBLE AS min_hop_level,
               c.seed_count::DOUBLE AS seed_count,
               COALESCE(b.total_tx_count, 0)::DOUBLE AS total_tx_count,
               COALESCE(b.zero_tx_count, 0)::DOUBLE AS zero_tx_count,
               COALESCE(b.usdt_tx_count, 0)::DOUBLE AS usdt_tx_count,
               COALESCE(b.trx_tx_count, 0)::DOUBLE AS trx_tx_count,
               COALESCE(d.in_degree_all, 0)::DOUBLE AS in_degree_all,
               COALESCE(d.out_degree_all, 0)::DOUBLE AS out_degree_all,
               COALESCE(d.in_degree_usdt, 0)::DOUBLE AS in_degree_usdt,
               COALESCE(d.out_degree_usdt, 0)::DOUBLE AS out_degree_usdt,
               CASE
                   WHEN COALESCE(d.in_degree_usdt, 0) + COALESCE(d.out_degree_usdt, 0) > 0
                   THEN (COALESCE(d.out_degree_usdt, 0) + 1.0) / (COALESCE(d.in_degree_usdt, 0) + 1.0)
                   ELSE NULL
               END AS fan_out_in_ratio_usdt,
               b.usdt_volume,
               b.trx_volume,
               CASE
                   WHEN b.usdt_in_volume > 0 AND b.usdt_out_volume > 0
                   THEN b.usdt_out_volume / b.usdt_in_volume
                   ELSE NULL
               END AS in_out_vol_ratio_usdt,
               u.min_passthrough_sec_usdt,
               CASE
                   WHEN u.min_passthrough_sec_usdt IS NOT NULL
                   THEN CASE WHEN u.min_passthrough_sec_usdt <= {H1_MAX_PASSTHROUGH_SEC} THEN 1.0 ELSE 0.0 END
                   ELSE NULL
               END AS h1_pass_15m,
               b.tx_lifetime_days,
               CASE WHEN b.tx_lifetime_days IS NOT NULL THEN LN(1.0 + b.tx_lifetime_days) ELSE NULL END AS log1p_tx_lifetime_days,
               u.burst_ratio_usdt,
               CASE
                   WHEN b.tx_lifetime_days IS NOT NULL AND u.burst_ratio_usdt IS NOT NULL
                   THEN CASE WHEN b.tx_lifetime_days <= {H2_MAX_LIFETIME_DAYS} AND u.burst_ratio_usdt >= {H2_MIN_BURST_RATIO} THEN 1.0 ELSE 0.0 END
                   ELSE NULL
               END AS h2_pass_ge5,
               CASE
                   WHEN u.burst_ratio_usdt_any IS NOT NULL
                   THEN CASE WHEN COALESCE(b.tx_lifetime_days, 0.0) <= {H2_MAX_LIFETIME_DAYS} AND u.burst_ratio_usdt_any >= {H2_MIN_BURST_RATIO} THEN 1.0 ELSE 0.0 END
                   ELSE NULL
               END AS h2_pass_any_usdt,
               b.amount_cv_usdt,
               j.jaccard_index,
               CASE
                   WHEN j.jaccard_index IS NOT NULL
                   THEN CASE WHEN j.jaccard_index >= {H4_MIN_JACCARD} THEN 1.0 ELSE 0.0 END
                   ELSE NULL
               END AS h4_pass,
               h6.cv_delta_t_all,
               CASE WHEN h6.cv_delta_t_all IS NOT NULL THEN LN(1.0 + h6.cv_delta_t_all) ELSE NULL END AS log1p_cv_delta_t_all,
               h6.cv_delta_t_out,
               CASE
                   WHEN h6.cv_delta_t_all IS NOT NULL
                   THEN CASE WHEN h6.cv_delta_t_all < {H6_MAX_CV} THEN 1.0 ELSE 0.0 END
                   ELSE NULL
               END AS h6_pass_all,
               CASE
                   WHEN h6.cv_delta_t_out IS NOT NULL
                   THEN CASE WHEN h6.cv_delta_t_out < {H6_MAX_CV} THEN 1.0 ELSE 0.0 END
                   ELSE NULL
               END AS h6_pass_out
        FROM cohort_wallet c
        LEFT JOIN feat_scalar b USING (wallet_address)
        LEFT JOIN feat_degrees d USING (wallet_address)
        LEFT JOIN feat_usdt_temporal u USING (wallet_address)
        LEFT JOIN feat_h4_jaccard j USING (wallet_address)
        LEFT JOIN feat_h6_cv h6 USING (wallet_address)
        """
    )
    con.execute("DROP TABLE IF EXISTS feat_scalar")
    con.execute("DROP TABLE IF EXISTS feat_degrees")
    con.execute("DROP TABLE IF EXISTS feat_usdt_temporal")
    con.execute("DROP TABLE IF EXISTS feat_h4_jaccard")
    con.execute("DROP TABLE IF EXISTS feat_h6_cv")


FEATURE_SPECS: tuple[tuple[str, str, bool, str, str], ...] = (
    # (column_name, hypothesis, is_discrete_or_indicator, eligibility_filter, assumption)
    ("total_tx_count", "shared", False, "all wallets (non-zero clean events)", "deduped clean tx; excludes sentinel/above_supply/pre_mainnet/zero"),
    ("zero_tx_count", "shared", False, "all wallets (zero-amount clean events)", "flagged zero-value transfers per wallet"),
    ("usdt_tx_count", "shared", False, "all wallets (non-zero USDT)", "deduped clean USDT events"),
    ("trx_tx_count", "shared", False, "all wallets (non-zero TRX)", "deduped clean TRX events (includes 1-SUN dust)"),
    ("in_degree_all", "H3", False, "all wallets", "distinct inbound counterparties across TRX+USDT"),
    ("out_degree_all", "H3", False, "all wallets", "distinct outbound counterparties across TRX+USDT"),
    ("in_degree_usdt", "H3", False, "all wallets", "distinct inbound USDT counterparties"),
    ("out_degree_usdt", "H3", False, "all wallets", "distinct outbound USDT counterparties"),
    ("fan_out_in_ratio_usdt", "H3", False, ">=1 USDT event", "(out_degree_usdt + 1) / (in_degree_usdt + 1)"),
    ("usdt_volume", "shared", False, ">=1 non-zero USDT event", "total clean USDT in+out volume"),
    ("trx_volume", "shared", False, ">=1 non-zero TRX event", "total clean TRX in+out volume (<=100B cap)"),
    ("in_out_vol_ratio_usdt", "H1", False, "both USDT in>0 and out>0", "usdt_out_volume / usdt_in_volume"),
    ("min_passthrough_sec_usdt", "H1", False, "paired USDT IN -> subsequent OUT", "min seconds from prior USDT IN to next USDT OUT"),
    ("h1_pass_15m", "H1", True, "paired USDT IN -> subsequent OUT", "min_passthrough_sec_usdt <= 900s (15 min)"),
    ("tx_lifetime_days", "H2", False, ">=2 non-zero events (all tokens)", "transaction span, not accounts.first_seen"),
    ("log1p_tx_lifetime_days", "H2", False, ">=2 non-zero events (all tokens)", "stateless log1p(tx_lifetime_days) primary ANOVA response"),
    ("burst_ratio_usdt", "H2", False, ">=5 non-zero USDT events", "max 1h USDT vol / total USDT vol (USDT-only)"),
    ("h2_pass_ge5", "H2", True, ">=2 events and >=5 USDT events", "lifetime <= 7d AND burst_ratio_usdt >= 0.75"),
    ("h2_pass_any_usdt", "H2", True, ">=1 non-zero USDT event", "activity-floor sensitivity check (no >=5 USDT gate)"),
    ("amount_cv_usdt", "H3", False, ">=5 non-zero USDT events", "stddev/mean of clean USDT amounts"),
    ("jaccard_index", "H4", False, "both TRX funders>0 and USDT recipients>0", "Jaccard(TRX funders, USDT recipients)"),
    ("h4_pass", "H4", True, "both TRX funders>0 and USDT recipients>0", "jaccard_index >= 0.50"),
    ("min_hop_level", "H5", True, "suspicious wallets (hop 1..5)", "nested inside suspicious; NULL for other cohorts"),
    ("seed_count", "H5", True, "all wallets", "distinct illicit seed_address count in wallet_hops"),
    ("cv_delta_t_all", "H6", False, ">=5 non-zero events and mean gap > 0", "all-direction inter-arrival CV (no session split)"),
    ("log1p_cv_delta_t_all", "H6", False, ">=5 non-zero events and mean gap > 0", "stateless log1p(cv_delta_t_all) secondary ANOVA response"),
    ("cv_delta_t_out", "H6", False, ">=5 non-zero OUT events and mean gap > 0", "OUT-only directional sensitivity for H6"),
    ("h6_pass_all", "H6", True, ">=5 non-zero events and mean gap > 0", "cv_delta_t_all < 0.15"),
    ("h6_pass_out", "H6", True, ">=5 non-zero OUT events and mean gap > 0", "cv_delta_t_out < 0.15 (OUT-only sensitivity)"),
)

TRANSFORMED_EXTRA_FEATURE_SPECS: tuple[tuple[str, str, bool, str, str], ...] = (
    ("trx_tx_count_excl_4444", "shared", False, "all wallets (non-zero TRX excl 4444.444444)", "sensitivity count excluding repeated 4444.444444 TRX artifact"),
    ("trx_tx_count_nodust", "shared", False, "all wallets (non-zero TRX excl 1-SUN dust)", "sensitivity count excluding 1-SUN TRX dust"),
    ("trx_volume_excl_4444", "shared", False, ">=1 non-zero TRX event excl 4444.444444", "clean TRX volume excluding repeated 4444.444444 artifact"),
    ("burst_ratio_usdt_any", "H2", False, ">=1 non-zero USDT event", "max 1h USDT vol / total USDT vol without >=5 USDT gate"),
    ("log1p_cv_delta_t_out", "H6", False, ">=5 non-zero OUT events and mean gap > 0", "stateless log1p(cv_delta_t_out) OUT-only H6 sensitivity"),
    ("log1p_usdt_volume", "shared", False, ">=1 non-zero USDT event", "stateless log1p(usdt_volume)"),
    ("log1p_trx_volume", "shared", False, ">=1 non-zero TRX event", "stateless log1p(trx_volume)"),
    ("log1p_total_tx_count", "shared", False, "all wallets (non-zero clean events)", "stateless log1p(total_tx_count)"),
    ("log1p_min_passthrough_sec_usdt", "H1", False, "paired USDT IN -> subsequent OUT", "stateless log1p(min_passthrough_sec_usdt)"),
)

HISTOGRAM_SPECS: tuple[tuple[str, str, list[float]], ...] = (
    # (feature_col, transform_label, bin_edges)
    ("log1p_tx_lifetime_days", "log1p_days", [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 8.0, 10.0]),
    ("burst_ratio_usdt", "raw_0_1", [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 0.95, 1.0001]),
    ("jaccard_index", "raw_0_1", [0.0, 1e-9, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]),
    ("log1p_cv_delta_t_all", "log1p_cv", [0.0, 0.14, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0, 6.0]),
    ("min_passthrough_sec_usdt", "seconds_buckets", [0.0, 60.0, 300.0, 900.0, 3600.0, 21600.0, 86400.0, 604800.0, 2592000.0, 1e12]),
    ("usdt_volume", "usd_log10_buckets", [0.0, 1.0, 10.0, 100.0, 1000.0, 1e4, 1e5, 1e6, 1e7, 1e8, 1e12]),
    ("total_tx_count", "count_buckets", [0.0, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0, 500.0, 1000.0, 1e9]),
    ("out_degree_usdt", "degree_buckets", [0.0, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0, 500.0, 1e9]),
)


def _summarize_wallet_distributions(
    con: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    is_partial: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cohort_totals = {
        str(wc): int(cnt)
        for wc, cnt in con.execute(
            "SELECT wallet_class, COUNT(*) FROM wallet_profile GROUP BY wallet_class"
        ).fetchall()
    }

    dist_rows: list[dict[str, Any]] = []
    nflow_rows: list[dict[str, Any]] = []

    for col, hyp, is_disc, elig_filter, assumption in FEATURE_SPECS:
        query = f"""
            SELECT wallet_class,
                   COUNT({col}) AS n_eligible,
                   COUNT(*) - COUNT({col}) AS missing,
                   AVG(CASE WHEN {col} = 0 THEN 1.0 ELSE 0.0 END) FILTER (WHERE {col} IS NOT NULL) AS zero_share,
                   AVG({col}) AS mean_v,
                   STDDEV_SAMP({col}) AS std_v,
                   SKEWNESS({col}) AS skew_v,
                   MIN({col}) AS min_v,
                   quantile_cont({col}, 0.01) AS p01,
                   quantile_cont({col}, 0.10) AS p10,
                   quantile_cont({col}, 0.25) AS p25,
                   quantile_cont({col}, 0.50) AS p50,
                   quantile_cont({col}, 0.75) AS p75,
                   quantile_cont({col}, 0.90) AS p90,
                   quantile_cont({col}, 0.95) AS p95,
                   quantile_cont({col}, 0.99) AS p99,
                   quantile_cont({col}, 0.999) AS p999,
                   MAX({col}) AS max_v,
                   SUM(CASE WHEN {col} = 1.0 THEN 1 ELSE 0 END) FILTER (WHERE {col} IS NOT NULL) AS pass_count
            FROM wallet_profile
            GROUP BY wallet_class
        """
        by_class = {str(r[0]): r for r in con.execute(query).fetchall()}
        for wc in COHORT_ORDER:
            n_cohort = cohort_totals.get(wc, 0)
            r = by_class.get(wc)
            n_elig = int(r[1]) if r else 0
            missing = int(r[2]) if r else n_cohort
            zero_share = float(r[3]) if r and r[3] is not None else None
            mean_v = float(r[4]) if r and r[4] is not None else None
            std_v = float(r[5]) if r and r[5] is not None else None
            skew_v = float(r[6]) if r and r[6] is not None and not math.isnan(float(r[6])) else None
            min_v = float(r[7]) if r and r[7] is not None else None
            qs = [float(r[i]) if r and r[i] is not None else None for i in range(8, 17)]
            max_v = float(r[17]) if r and r[17] is not None else None
            p50 = qs[3]
            p99 = qs[7]
            p99_p50 = (p99 / p50) if (p50 is not None and p50 > 0 and p99 is not None) else None
            pass_count = int(r[18]) if (is_disc and col.startswith(("h1_", "h2_", "h4_", "h6_")) and r and r[18] is not None) else None
            pass_share = (pass_count / n_elig) if (pass_count is not None and n_elig > 0) else None
            scale_rec = recommend_scale(
                min_value=min_v,
                max_value=max_v,
                skewness=skew_v,
                p50=p50,
                p99=p99,
                zero_share=zero_share,
                is_discrete=is_disc,
            )
            dist_rows.append(
                {
                    "wallet_class": wc,
                    "hypothesis": hyp,
                    "feature": col,
                    "n_cohort": n_cohort,
                    "n_eligible": n_elig,
                    "eligible_share": (n_elig / n_cohort) if n_cohort else 0.0,
                    "missing": missing,
                    "zero_share": zero_share,
                    "mean": mean_v,
                    "stddev": std_v,
                    "skewness": skew_v,
                    "min": min_v,
                    "p01": qs[0],
                    "p10": qs[1],
                    "p25": qs[2],
                    "p50": p50,
                    "p75": qs[4],
                    "p90": qs[5],
                    "p95": qs[6],
                    "p99": p99,
                    "p999": qs[8],
                    "max": max_v,
                    "p99_p50_ratio": p99_p50,
                    "pass_count": pass_count,
                    "pass_share": pass_share,
                    "recommended_scale": scale_rec,
                    "assumption": assumption,
                    "snapshot_at": snapshot_id,
                    "is_partial": is_partial,
                }
            )
            nflow_rows.append(
                {
                    "wallet_class": wc,
                    "hypothesis": hyp,
                    "feature": col,
                    "filter": elig_filter,
                    "n_in": n_cohort,
                    "n_out": n_elig,
                    "n_dropped": n_cohort - n_elig,
                    "retained_share": (n_elig / n_cohort) if n_cohort else 0.0,
                    "reason": assumption,
                    "snapshot_at": snapshot_id,
                    "is_partial": is_partial,
                }
            )

    # Compact histogram bins for offline plotting (box/density/bar plots without DB)
    hist_rows: list[dict[str, Any]] = []
    for col, scale_label, edges in HISTOGRAM_SPECS:
        case_clauses = []
        for idx in range(len(edges) - 1):
            lo, hi = edges[idx], edges[idx + 1]
            case_clauses.append(f"WHEN {col} >= {lo} AND {col} < {hi} THEN {idx}")
        case_sql = f"CASE {' '.join(case_clauses)} ELSE {len(edges) - 1} END"
        bins = con.execute(
            f"""
            SELECT wallet_class, {case_sql} AS bin_idx, COUNT(*) AS n
            FROM wallet_profile
            WHERE {col} IS NOT NULL
            GROUP BY 1, 2
            ORDER BY 1, 2
            """
        ).fetchall()
        bin_map = {(str(wc), int(bidx)): int(cnt) for wc, bidx, cnt in bins}
        elig_by_wc = {
            str(wc): sum(cnt for (w, _), cnt in bin_map.items() if w == wc)
            for wc in COHORT_ORDER
        }
        for wc in COHORT_ORDER:
            denom = elig_by_wc[wc]
            for idx in range(len(edges) - 1):
                cnt = bin_map.get((wc, idx), 0)
                hist_rows.append(
                    {
                        "wallet_class": wc,
                        "feature": col,
                        "scale": scale_label,
                        "bin_index": idx,
                        "bin_low": edges[idx],
                        "bin_high": edges[idx + 1],
                        "count": cnt,
                        "share": (cnt / denom) if denom else 0.0,
                        "denominator": denom,
                        "snapshot_at": snapshot_id,
                        "is_partial": is_partial,
                    }
                )
            overflow = bin_map.get((wc, len(edges) - 1), 0)
            if overflow > 0:
                hist_rows.append(
                    {
                        "wallet_class": wc,
                        "feature": col,
                        "scale": scale_label,
                        "bin_index": len(edges) - 1,
                        "bin_low": edges[-1],
                        "bin_high": None,
                        "count": overflow,
                        "share": (overflow / denom) if denom else 0.0,
                        "denominator": denom,
                        "snapshot_at": snapshot_id,
                        "is_partial": is_partial,
                    }
                )

    return pd.DataFrame(dist_rows), pd.DataFrame(nflow_rows), pd.DataFrame(hist_rows)


def _resolve_transformed_partial(manifest: dict[str, Any]) -> bool:
    """Resolve partial status for a transformed snapshot manifest.

    Transformed schemas materialize locally via SQL and have no sharded
    ingestion bookkeeping (_etl_runs/_etl_progress). Older exports therefore
    recorded table status='unknown' and manifest['partial']=True even when all
    tables were fully materialized. Treat as partial only if a table explicitly
    reports status='partial' (or the manifest lists no tables).
    """
    tables_meta = manifest.get("tables", {})
    if not tables_meta:
        return bool(manifest.get("partial", False))
    statuses = {str(meta.get("status", "unknown")).lower() for meta in tables_meta.values()}
    if "partial" in statuses:
        return True
    if statuses <= {"complete", "unknown"}:
        return False
    return bool(manifest.get("partial", False))


def _build_transformed_db_overview(
    con: duckdb.DuckDBPyConnection,
    schema_name: str,
    table_views: dict[str, str],
    snapshot_id: str,
    is_partial: bool,
    *,
    columns_csv_path: Path | None = None,
) -> pd.DataFrame:
    """Build exact table-level overview CSV for transformed Parquet snapshots."""
    coverage_status = "partial" if is_partial else "complete"
    rows_out: list[dict[str, Any]] = []
    if columns_csv_path is not None and columns_csv_path.exists():
        cols_df = pd.read_csv(columns_csv_path)
        for table_name in table_views:
            sub = cols_df[cols_df["table"] == table_name]
            if sub.empty:
                continue
            total_rows = int(sub["rows"].iloc[0])
            n_cols = int(len(sub))
            null_cells = int(pd.to_numeric(sub["nulls"], errors="coerce").fillna(0).sum())
            denom = total_rows * n_cols
            mins = [str(v) for v in sub["min"].dropna().tolist() if str(v)]
            maxs = [str(v) for v in sub["max"].dropna().tolist() if str(v)]
            rows_out.append(
                {
                    "schema": schema_name,
                    "table": table_name,
                    "rows": total_rows,
                    "source_rows": total_rows,
                    "run_id": "",
                    "coverage_status": coverage_status,
                    "columns": n_cols,
                    "sample_rows": total_rows,
                    "null_cells": null_cells,
                    "null_share": (null_cells / denom) if denom else 0.0,
                    "time_min": min(mins) if mins else "",
                    "time_max": max(maxs) if maxs else "",
                    "key_columns": "",
                    "method": "exact_parquet",
                    "snapshot_at": snapshot_id,
                    "is_partial": is_partial,
                }
            )
        return pd.DataFrame(rows_out)

    for table_name, view_name in table_views.items():
        desc = con.execute(f"DESCRIBE SELECT * FROM {view_name}").fetchall()
        total_rows = int(con.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()[0])
        rows_out.append(
            {
                "schema": schema_name,
                "table": table_name,
                "rows": total_rows,
                "source_rows": total_rows,
                "run_id": "",
                "coverage_status": coverage_status,
                "columns": len(desc),
                "sample_rows": total_rows,
                "null_cells": 0,
                "null_share": 0.0,
                "time_min": "",
                "time_max": "",
                "key_columns": "",
                "method": "exact_parquet",
                "snapshot_at": snapshot_id,
                "is_partial": is_partial,
            }
        )
    return pd.DataFrame(rows_out)


def _build_transformed_cleaning_profile(
    con: duckdb.DuckDBPyConnection,
    table_views: dict[str, str],
    snapshot_id: str,
    is_partial: bool,
) -> pd.DataFrame:
    """Build post-L1 cleaning profile matching raw/local_pretransform_cleaning.csv schema."""
    rows: list[dict[str, Any]] = []

    def add(
        section: str,
        schema: str,
        token: str,
        category: str,
        count: int,
        denominator: int,
        note: str = "",
    ) -> None:
        rows.append(
            {
                "section": section,
                "schema": schema,
                "token_symbol": token,
                "category": category,
                "count": int(count),
                "denominator": int(denominator),
                "share": (count / denominator) if denominator else 0.0,
                "note": note,
                "snapshot_at": snapshot_id,
                "is_partial": is_partial,
            }
        )

    if "clean_transactions" in table_views:
        tx_view = table_views["clean_transactions"]
        deduped, overlap = con.execute(
            f"""
            SELECT COUNT(*) AS deduped_rows,
                   COUNT(*) FILTER (WHERE in_both_schemas) AS overlap_rows
            FROM {tx_view}
            """
        ).fetchone()
        deduped_i, overlap_i = int(deduped), int(overlap)
        raw_union = deduped_i + overlap_i
        add("cross_schema_tx_overlap", "both", "ALL", "raw_union_rows", raw_union, raw_union, "deduped + overlap rows reconstructed from clean_transactions")
        add("cross_schema_tx_overlap", "both", "ALL", "overlap_tx_hash", overlap_i, raw_union, "tx_hash present in both schemas (resolved deterministically)")
        add("cross_schema_tx_overlap", "both", "ALL", "deduped_tx_rows", deduped_i, raw_union, "unique tx_hash in transform.clean_transactions")

        if "clean_tx_conflicts" in table_views:
            conf_view = table_views["clean_tx_conflicts"]
            cstats = con.execute(
                f"""
                SELECT COUNT(*) FILTER (WHERE diff_token) AS diff_token,
                       COUNT(*) FILTER (WHERE diff_amount) AS diff_amount,
                       COUNT(*) FILTER (WHERE illicit_amount_exact IS DISTINCT FROM licit_amount_exact) AS diff_amount_exact,
                       COUNT(*) FILTER (WHERE diff_from) AS diff_from,
                       COUNT(*) FILTER (WHERE diff_to) AS diff_to,
                       COUNT(*) FILTER (WHERE diff_ts) AS diff_ts
                FROM {conf_view}
                """
            ).fetchone()
            for name, val in zip(
                ("diff_token", "diff_amount", "diff_amount_exact", "diff_from", "diff_to", "diff_ts"),
                cstats,
                strict=True,
            ):
                add("cross_schema_tx_overlap", "both", "ALL", name, int(val), overlap_i, "resolved conflict logged in transform.clean_tx_conflicts")

        # Post-L1 valid-for-features amount flags (invalid sentinel/above_supply/zero/pre_mainnet excluded)
        flag_rows = con.execute(
            f"""
            WITH valid_tx AS (
                SELECT source_schema, token_symbol, amount_flag
                FROM {tx_view}
                WHERE is_valid_for_features
            ),
            totals AS (
                SELECT source_schema, token_symbol, COUNT(*) AS denom
                FROM valid_tx
                GROUP BY source_schema, token_symbol
            )
            SELECT v.source_schema, v.token_symbol, v.amount_flag, COUNT(*) AS n, t.denom
            FROM valid_tx v
            JOIN totals t USING (source_schema, token_symbol)
            GROUP BY v.source_schema, v.token_symbol, v.amount_flag, t.denom
            ORDER BY v.source_schema, v.token_symbol, v.amount_flag
            """
        ).fetchall()
        for src_schema, token, flag, cnt, denom in flag_rows:
            add("amount_flag", str(src_schema), str(token), str(flag), int(cnt), int(denom), "post-L1 valid-for-features rows")

        # TRX anomaly details on post-L1 valid-for-features TRX rows
        trx_rows = con.execute(
            f"""
            SELECT source_schema,
                   COUNT(*) AS n_trx,
                   COUNT(*) FILTER (WHERE is_1sun_dust) AS eq_1sun,
                   COUNT(*) FILTER (WHERE NOT is_1sun_dust AND amount < {DUST_UPPER_BOUND}) AS gt_1sun_lt_001,
                   COUNT(*) FILTER (WHERE is_trx_4444_artifact) AS eq_4444_444444,
                   COUNT(*) FILTER (WHERE amount > {TRX_SUPPLY_CEILING}) AS above_trx_supply
            FROM {tx_view}
            WHERE is_valid_for_features AND token_symbol = 'TRX'
            GROUP BY source_schema
            ORDER BY source_schema
            """
        ).fetchall()
        for src_schema, n_trx, eq_1sun, gt_1sun, eq_4444, above_sup in trx_rows:
            n_trx_i = int(n_trx)
            add("trx_anomaly_detail", str(src_schema), "TRX", "exact_1_sun_0.000001", int(eq_1sun), n_trx_i, "flagged 1-SUN dust retained for sensitivity checks")
            add("trx_anomaly_detail", str(src_schema), "TRX", "micro_dust_gt_1sun_lt_0.01", int(gt_1sun), n_trx_i, "sub-cent TRX transfers")
            add("trx_anomaly_detail", str(src_schema), "TRX", "repeated_4444.444444_artifact", int(eq_4444), n_trx_i, "flagged 4444.444444 artifact retained for sensitivity checks")
            add("trx_anomaly_detail", str(src_schema), "TRX", "above_100b_trx_supply", int(above_sup), n_trx_i, "physically impossible TRX amount (0 after L1 filter)")

        # Post-L1 valid-for-features timestamp flags & annual volume
        ts_totals = {
            str(s): int(n)
            for s, n in con.execute(
                f"SELECT source_schema, COUNT(*) FROM {tx_view} WHERE is_valid_for_features GROUP BY source_schema"
            ).fetchall()
        }
        ts_rows = con.execute(
            f"""
            SELECT source_schema, timestamp_flag, COUNT(*) AS n
            FROM {tx_view}
            WHERE is_valid_for_features
            GROUP BY source_schema, timestamp_flag
            ORDER BY source_schema, timestamp_flag
            """
        ).fetchall()
        for src_schema, flag, cnt in ts_rows:
            add("timestamp_flag", str(src_schema), "ALL", str(flag), int(cnt), ts_totals.get(str(src_schema), int(cnt)), "post-L1 valid-for-features rows")

        yr_rows = con.execute(
            f"""
            SELECT source_schema,
                   token_symbol,
                   CASE
                       WHEN block_timestamp < TIMESTAMPTZ '2018-06-25 00:00:00+00'
                       THEN 'pre_mainnet_' || CAST(EXTRACT(YEAR FROM block_timestamp) AS VARCHAR)
                       ELSE CAST(EXTRACT(YEAR FROM block_timestamp) AS VARCHAR)
                   END AS yr,
                   COUNT(*) AS n
            FROM {tx_view}
            WHERE is_valid_for_features
            GROUP BY 1, 2, 3
            ORDER BY 1, 3, 2
            """
        ).fetchall()
        for src_schema, tok, yr, cnt in yr_rows:
            add("tx_by_year", str(src_schema), str(tok), str(yr), int(cnt), ts_totals.get(str(src_schema), int(cnt)), "post-L1 valid-for-features rows")

    if "clean_wallet_hops" in table_views:
        hops_view = table_views["clean_wallet_hops"]
        tot_hops = int(con.execute(f"SELECT COUNT(*) FROM {hops_view}").fetchone()[0])
        for status, cnt in con.execute(
            f"SELECT via_tx_status, COUNT(*) AS n FROM {hops_view} GROUP BY 1 ORDER BY n DESC"
        ).fetchall():
            add("hop_edge_tx_flag", "illicit", "ALL", str(status), int(cnt), tot_hops, "transform.clean_wallet_hops via_tx_status")

    if "cohort_wallet" in table_views:
        cw_view = table_views["cohort_wallet"]
        hop_ge1 = int(
            con.execute(f"SELECT COUNT(*) FROM {cw_view} WHERE max_hop_level >= 1").fetchone()[0]
        )
        hop_only_cnt = int(
            con.execute(f"SELECT COUNT(*) FROM {cw_view} WHERE NOT in_accounts_table").fetchone()[0]
        )
        hop_only_bl = int(
            con.execute(
                f"SELECT COUNT(*) FROM {cw_view} WHERE NOT in_accounts_table AND wallet_class = 'illicit'"
            ).fetchone()[0]
        )
        hop_only_tx = 0
        if "wallet_features" in table_views:
            wf_view = table_views["wallet_features"]
            wf_cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {wf_view}").fetchall()}
            if {"in_accounts_table", "total_tx_count"} <= wf_cols:
                hop_only_tx = int(
                    con.execute(
                        f"SELECT COUNT(*) FROM {wf_view} WHERE NOT in_accounts_table AND total_tx_count > 0"
                    ).fetchone()[0]
                )
        add("hop_only_reconciliation", "both", "ALL", "hop_only_not_in_accounts", hop_only_cnt, hop_ge1, "in clean_wallet_hops (1..5) but absent from accounts union")
        add("hop_only_reconciliation", "both", "ALL", "hop_only_present_in_transactions", hop_only_tx, hop_only_cnt, "hop-only wallets with >=1 valid tx")
        add("hop_only_reconciliation", "both", "ALL", "hop_only_blacklisted", hop_only_bl, hop_only_cnt, "hop-only wallets in blacklist")

    return pd.DataFrame(rows)


def _build_transformed_cohort_profiles(
    con: duckdb.DuckDBPyConnection,
    table_views: dict[str, str],
    snapshot_id: str,
    is_partial: bool,
) -> dict[str, pd.DataFrame]:
    """Build cohort counts, n-flow, overlap, hop/seed, and sampling-frame CSVs from transform tables."""
    outputs: dict[str, pd.DataFrame] = {}

    if "cohort_wallet" in table_views:
        cw_view = table_views["cohort_wallet"]
        cw_cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {cw_view}").fetchall()}

        # 1. local_cohort_counts.csv
        counts_raw = {
            str(wc): int(n)
            for wc, n in con.execute(
                f"SELECT wallet_class, COUNT(*) FROM {cw_view} GROUP BY wallet_class"
            ).fetchall()
        }
        universe_total = sum(counts_raw.values())
        outputs["cohort_counts"] = pd.DataFrame(
            [
                {
                    "group": wc,
                    "count": counts_raw.get(wc, 0),
                    "share": (counts_raw.get(wc, 0) / universe_total) if universe_total else 0.0,
                    "snapshot_at": snapshot_id,
                    "is_partial": is_partial,
                }
                for wc in COHORT_ORDER
            ]
        )

        # 2. local_nflow.csv
        if {"in_accounts_table", "in_illicit_accounts", "in_licit_accounts", "max_hop_level"} <= cw_cols:
            nf_stats = con.execute(
                f"""
                SELECT COUNT(*) AS universe_n,
                       COUNT(*) FILTER (WHERE in_accounts_table) AS acc_union_n,
                       COUNT(*) FILTER (WHERE in_illicit_accounts) AS ill_acc_n,
                       COUNT(*) FILTER (WHERE in_licit_accounts) AS lic_acc_n,
                       COUNT(*) FILTER (WHERE wallet_class = 'illicit') AS illicit_n,
                       COUNT(*) FILTER (WHERE max_hop_level >= 1) AS hop_ge1_n,
                       COUNT(*) FILTER (WHERE wallet_class = 'suspicious') AS susp_n,
                       COUNT(*) FILTER (WHERE wallet_class = 'licit') AS licit_n,
                       COUNT(*) FILTER (WHERE wallet_class = 'unlabeled') AS unlabeled_n
                FROM {cw_view}
                """
            ).fetchone()
            (
                univ_n,
                acc_u,
                ill_acc,
                lic_acc,
                ill_n,
                hop_ge1,
                susp_n,
                lic_n,
                unlab_n,
            ) = (int(v) for v in nf_stats)
            raw_acc_sum = ill_acc + lic_acc
            outputs["nflow"] = pd.DataFrame(
                [
                    {
                        "stage": "account_union",
                        "filter": "cross_schema_dedupe",
                        "n_in": raw_acc_sum,
                        "n_out": acc_u,
                        "n_dropped": raw_acc_sum - acc_u,
                        "reason": "address present in both schemas",
                        "snapshot_at": snapshot_id,
                        "is_partial": is_partial,
                    },
                    {
                        "stage": "universe",
                        "filter": "accounts_plus_blacklist_plus_hop",
                        "n_in": univ_n,
                        "n_out": univ_n,
                        "n_dropped": 0,
                        "reason": "full L2 cohort_wallet universe (accounts + blacklist + hop 1..5)",
                        "snapshot_at": snapshot_id,
                        "is_partial": is_partial,
                    },
                    {
                        "stage": "illicit",
                        "filter": "blacklist_label_1",
                        "n_in": ill_n,
                        "n_out": ill_n,
                        "n_dropped": 0,
                        "reason": "priority group",
                        "snapshot_at": snapshot_id,
                        "is_partial": is_partial,
                    },
                    {
                        "stage": "suspicious",
                        "filter": "min_hop_1_5_and_not_blacklisted",
                        "n_in": hop_ge1,
                        "n_out": susp_n,
                        "n_dropped": hop_ge1 - susp_n,
                        "reason": "blacklist wins at every hop",
                        "snapshot_at": snapshot_id,
                        "is_partial": is_partial,
                    },
                    {
                        "stage": "licit",
                        "filter": "external_minus_illicit_minus_suspicious",
                        "n_in": lic_acc,
                        "n_out": lic_n,
                        "n_dropped": lic_acc - lic_n,
                        "reason": "illicit/suspicious overlap",
                        "snapshot_at": snapshot_id,
                        "is_partial": is_partial,
                    },
                    {
                        "stage": "unlabeled",
                        "filter": "remaining_illicit_accounts",
                        "n_in": unlab_n,
                        "n_out": unlab_n,
                        "n_dropped": 0,
                        "reason": "provisional residual arm",
                        "snapshot_at": snapshot_id,
                        "is_partial": is_partial,
                    },
                ]
            )

        # 3. local_group_overlap.csv
        if {"in_licit_accounts", "is_licit_seed"} <= cw_cols:
            ov_stats = con.execute(
                f"""
                SELECT COUNT(*) FILTER (WHERE wallet_class = 'illicit') AS ill_n,
                       COUNT(*) FILTER (WHERE wallet_class = 'suspicious') AS susp_n,
                       COUNT(*) FILTER (WHERE in_licit_accounts) AS lic_acc_n,
                       COUNT(*) FILTER (WHERE is_licit_seed) AS lic_seed_n,
                       COUNT(*) FILTER (WHERE wallet_class = 'illicit' AND in_licit_accounts) AS ill_x_lic_acc,
                       COUNT(*) FILTER (WHERE wallet_class = 'suspicious' AND in_licit_accounts) AS susp_x_lic_acc,
                       COUNT(*) FILTER (WHERE wallet_class = 'illicit' AND is_licit_seed) AS ill_x_lic_seed
                FROM {cw_view}
                """
            ).fetchone()
            ill_n, susp_n, lic_acc, lic_seed, ov_il, ov_sl, ov_is = (int(v) for v in ov_stats)
            ov_rows = []
            for label, lc, rc, ov in (
                ("illicit blacklist vs licit accounts", ill_n, lic_acc, ov_il),
                ("suspicious vs licit accounts", susp_n, lic_acc, ov_sl),
                ("illicit blacklist vs licit seed wallets", ill_n, lic_seed, ov_is),
            ):
                ov_rows.append(
                    {
                        "comparison": label,
                        "left_count": lc,
                        "right_count": rc,
                        "overlap": ov,
                        "left_share": (ov / lc) if lc else 0.0,
                        "right_share": (ov / rc) if rc else 0.0,
                        "method": "exact_parquet",
                        "snapshot_at": snapshot_id,
                        "is_partial": is_partial,
                    }
                )
            outputs["group_overlap"] = pd.DataFrame(ov_rows)

        # 4. local_sampling_frame.csv
        sf_rows: list[dict[str, Any]] = []

        def add_sf(section: str, group: str, metric: str, value: Any, denominator: int | None = None, note: str = "") -> None:
            sf_rows.append(
                {
                    "section": section,
                    "group": group,
                    "metric": metric,
                    "value": value,
                    "denominator": denominator,
                    "note": note,
                    "snapshot_at": snapshot_id,
                    "is_partial": is_partial,
                }
            )

        if "in_accounts_table" in cw_cols:
            for wc, n_all, n_acc, n_hop_only in con.execute(
                f"""
                SELECT wallet_class,
                       COUNT(*) AS n_all,
                       COUNT(*) FILTER (WHERE in_accounts_table) AS n_in_accounts,
                       COUNT(*) FILTER (WHERE NOT in_accounts_table) AS n_hop_only
                FROM {cw_view}
                GROUP BY wallet_class
                """
            ).fetchall():
                add_sf("cohort_universe", str(wc), "wallets_total", int(n_all), None, "transform.cohort_wallet universe")
                add_sf("cohort_universe", str(wc), "wallets_in_accounts", int(n_acc), int(n_all))
                add_sf("cohort_universe", str(wc), "wallets_hop_only", int(n_hop_only), int(n_all))

        if "clean_transactions" in table_views:
            tx_view = table_views["clean_transactions"]
            for src_schema in ("illicit", "licit"):
                stats = con.execute(
                    f"""
                    SELECT COUNT(*) AS n,
                           COUNT(*) FILTER (WHERE token_symbol = 'USDT') AS n_usdt,
                           COUNT(*) FILTER (WHERE token_symbol = 'TRX') AS n_trx,
                           MIN(block_timestamp) AS min_ts,
                           MAX(block_timestamp) AS max_ts,
                           quantile_cont(EPOCH(block_timestamp), 0.10) AS p10_epoch,
                           quantile_cont(EPOCH(block_timestamp), 0.50) AS p50_epoch,
                           quantile_cont(EPOCH(block_timestamp), 0.90) AS p90_epoch,
                           COUNT(DISTINCT fee_trx) AS fee_distinct,
                           AVG(CASE WHEN fee_trx = 0 THEN 1.0 ELSE 0.0 END) AS fee_zero_share,
                           MAX(fee_trx) AS fee_max
                    FROM {tx_view}
                    WHERE is_valid_for_features AND source_schema = '{src_schema}'
                    """
                ).fetchone()
                n = int(stats[0])
                if n == 0:
                    continue
                add_sf("schema_frame", src_schema, "tx_rows", n, n, "post-L1 valid-for-features rows")
                add_sf("schema_frame", src_schema, "usdt_share", int(stats[1]) / n, n)
                add_sf("schema_frame", src_schema, "trx_share", int(stats[2]) / n, n)
                add_sf("schema_frame", src_schema, "valid_ts_min", str(stats[3]), n)
                add_sf("schema_frame", src_schema, "valid_ts_max", str(stats[4]), n)
                add_sf("schema_frame", src_schema, "valid_ts_p10", str(datetime.fromtimestamp(float(stats[5]), UTC)), n)
                add_sf("schema_frame", src_schema, "valid_ts_p50", str(datetime.fromtimestamp(float(stats[6]), UTC)), n)
                add_sf("schema_frame", src_schema, "valid_ts_p90", str(datetime.fromtimestamp(float(stats[7]), UTC)), n)
                add_sf("schema_frame", src_schema, "fee_trx_distinct", int(stats[8]), n)
                add_sf("schema_frame", src_schema, "fee_trx_zero_share", float(stats[9]), n)
                add_sf("schema_frame", src_schema, "fee_trx_max", float(stats[10]), n)

        sus_total = counts_raw.get("suspicious", 0)
        if sus_total > 0 and "min_hop_level" in cw_cols:
            for hop, cnt in con.execute(
                f"""
                SELECT min_hop_level, COUNT(*)
                FROM {cw_view}
                WHERE wallet_class = 'suspicious' AND min_hop_level IS NOT NULL
                GROUP BY min_hop_level
                ORDER BY min_hop_level
                """
            ).fetchall():
                add_sf("suspicious_hop_band", f"hop_{int(hop)}", "wallets", int(cnt), sus_total, "nested inside suspicious")

        if "clean_wallet_hops" in table_views:
            hops_view = table_views["clean_wallet_hops"]
            sq = con.execute(
                f"""
                WITH sc AS (
                    SELECT seed_address, COUNT(DISTINCT wallet_address) AS cluster_size
                    FROM {hops_view}
                    WHERE hop_level >= 1
                    GROUP BY seed_address
                )
                SELECT COUNT(*) AS n_seeds,
                       MIN(cluster_size),
                       quantile_cont(cluster_size, 0.25),
                       quantile_cont(cluster_size, 0.50),
                       quantile_cont(cluster_size, 0.75),
                       quantile_cont(cluster_size, 0.90),
                       quantile_cont(cluster_size, 0.99),
                       MAX(cluster_size),
                       AVG(cluster_size)
                FROM sc
                """
            ).fetchone()
            n_seeds = int(sq[0])
            if n_seeds > 0:
                for name, val in zip(
                    ("n_seeds", "min", "p25", "p50", "p75", "p90", "p99", "max", "mean"),
                    sq,
                    strict=True,
                ):
                    add_sf("seed_cluster_size", "illicit_seeds", name, float(val) if val is not None else None, n_seeds)

        if sf_rows:
            outputs["sampling_frame"] = pd.DataFrame(sf_rows)

    if "clean_wallet_hops" in table_views:
        hops_view = table_views["clean_wallet_hops"]
        hs = con.execute(
            f"""
            WITH per_w AS (
                SELECT wallet_address,
                       COUNT(DISTINCT hop_level) FILTER (WHERE hop_level >= 1) AS n_hops,
                       COUNT(DISTINCT seed_address) FILTER (WHERE hop_level >= 1) AS n_seeds
                FROM {hops_view}
                GROUP BY wallet_address
            )
            SELECT (SELECT COUNT(DISTINCT wallet_address) FROM {hops_view} WHERE hop_level = 0) AS hop0_wallets,
                   (SELECT COUNT(DISTINCT wallet_address) FROM {hops_view} WHERE hop_level >= 1) AS hop_ge1_wallets,
                   (SELECT COUNT(*) FROM per_w WHERE n_hops > 1) AS multi_hop_wallets,
                   (SELECT COUNT(*) FROM per_w WHERE n_seeds > 1) AS multi_seed_wallets,
                   (SELECT COUNT(DISTINCT seed_address) FROM {hops_view}) AS distinct_seeds
            """
        ).fetchone()
        outputs["hop_seed"] = pd.DataFrame(
            [
                {"metric": name, "value": int(val), "snapshot_at": snapshot_id, "is_partial": is_partial}
                for name, val in zip(
                    ("hop0_wallets", "hop_ge1_wallets", "multi_hop_wallets", "multi_seed_wallets", "distinct_seeds"),
                    hs,
                    strict=True,
                )
            ]
        )

    return outputs


def _run_transformed_stage_profile(
    *,
    load_dir: Path,
    stage_dir: Path,
    memory_limit: str,
    temp_dir: Path,
    refresh_columns: bool,
) -> dict[str, Path]:
    """Profile a frozen transformed snapshot using the same CSV schemas as raw."""
    snap_dir = _latest_transformed_snapshot_dir(load_dir)
    manifest = _load_manifest(snap_dir)
    snapshot_id = str(manifest["snapshot"])
    schema_name = str(manifest.get("schema", "transformed"))
    is_partial = _resolve_transformed_partial(manifest)
    tables_meta: dict[str, Any] = manifest.get("tables", {})

    con = _connect_duckdb(memory_limit, temp_dir)
    written: dict[str, Path] = {}
    try:
        table_views: dict[str, str] = {}
        for table_name in tables_meta:
            view_name = f"t_{table_name}"
            parquet_path = _table_parquet(snap_dir, manifest, table_name).replace("'", "''")
            con.execute(
                f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM read_parquet('{parquet_path}')"
            )
            table_views[table_name] = view_name

        if refresh_columns and table_views:
            print(f"[stage:transformed] refreshing exact column null profiles ({schema_name})...", flush=True)
            written["columns"] = _refresh_exact_columns(
                con, schema_name, table_views, snapshot_id, is_partial, stage_dir
            )

        if table_views:
            print(f"[stage:transformed] writing table overview ({schema_name})...", flush=True)
            overview_df = _build_transformed_db_overview(
                con,
                schema_name,
                table_views,
                snapshot_id,
                is_partial,
                columns_csv_path=written.get("columns"),
            )
            if not overview_df.empty:
                written["db_overview"] = stage_dir / f"local_{schema_name}_db_overview.csv"
                overview_df.to_csv(written["db_overview"], index=False)

        if any(k in table_views for k in ("clean_transactions", "clean_wallet_hops", "cohort_wallet")):
            print("[stage:transformed] profiling post-L1 cleaning & anomaly rules...", flush=True)
            cleaning_df = _build_transformed_cleaning_profile(con, table_views, snapshot_id, is_partial)
            if not cleaning_df.empty:
                written["cleaning"] = stage_dir / "local_pretransform_cleaning.csv"
                cleaning_df.to_csv(written["cleaning"], index=False)

        if any(k in table_views for k in ("cohort_wallet", "clean_wallet_hops")):
            print("[stage:transformed] profiling L2 cohort, overlap, hop/seed, and sampling frame...", flush=True)
            cohort_frames = _build_transformed_cohort_profiles(con, table_views, snapshot_id, is_partial)
            file_map = {
                "cohort_counts": "local_cohort_counts.csv",
                "nflow": "local_nflow.csv",
                "group_overlap": "local_group_overlap.csv",
                "sampling_frame": "local_sampling_frame.csv",
                "hop_seed": "local_hop_seed.csv",
            }
            for key, df_part in cohort_frames.items():
                if not df_part.empty:
                    out_csv = stage_dir / file_map[key]
                    df_part.to_csv(out_csv, index=False)
                    written[key] = out_csv

        if "wallet_features" in table_views:
            # Summarize FEATURE_SPECS + transformed-only extra columns present in wallet_features.
            available_cols = {
                row[0]
                for row in con.execute("DESCRIBE SELECT * FROM t_wallet_features").fetchall()
            }
            if "wallet_class" in available_cols:
                con.execute("CREATE OR REPLACE TEMP VIEW wallet_profile AS SELECT * FROM t_wallet_features")
                cohort_totals = {
                    str(wc): int(cnt)
                    for wc, cnt in con.execute(
                        "SELECT wallet_class, COUNT(*) FROM wallet_profile GROUP BY wallet_class"
                    ).fetchall()
                }
                all_specs = FEATURE_SPECS + TRANSFORMED_EXTRA_FEATURE_SPECS
                present_specs = tuple(spec for spec in all_specs if spec[0] in available_cols)
                dist_rows: list[dict[str, Any]] = []
                nflow_rows: list[dict[str, Any]] = []
                for col, hyp, is_disc, elig_filter, assumption in present_specs:
                    query = f"""
                        SELECT wallet_class,
                               COUNT({col}) AS n_eligible,
                               COUNT(*) - COUNT({col}) AS missing,
                               AVG(CASE WHEN {col} = 0 THEN 1.0 ELSE 0.0 END) FILTER (WHERE {col} IS NOT NULL) AS zero_share,
                               AVG({col}) AS mean_v,
                               STDDEV_SAMP({col}) AS std_v,
                               SKEWNESS({col}) AS skew_v,
                               MIN({col}) AS min_v,
                               quantile_cont({col}, 0.01) AS p01,
                               quantile_cont({col}, 0.10) AS p10,
                               quantile_cont({col}, 0.25) AS p25,
                               quantile_cont({col}, 0.50) AS p50,
                               quantile_cont({col}, 0.75) AS p75,
                               quantile_cont({col}, 0.90) AS p90,
                               quantile_cont({col}, 0.95) AS p95,
                               quantile_cont({col}, 0.99) AS p99,
                               quantile_cont({col}, 0.999) AS p999,
                               MAX({col}) AS max_v,
                               SUM(CASE WHEN {col} = 1.0 THEN 1 ELSE 0 END) FILTER (WHERE {col} IS NOT NULL) AS pass_count
                        FROM wallet_profile
                        GROUP BY wallet_class
                    """
                    by_class = {str(r[0]): r for r in con.execute(query).fetchall()}
                    for wc in COHORT_ORDER:
                        n_cohort = cohort_totals.get(wc, 0)
                        r = by_class.get(wc)
                        n_elig = int(r[1]) if r else 0
                        missing = int(r[2]) if r else n_cohort
                        zero_share = float(r[3]) if r and r[3] is not None else None
                        mean_v = float(r[4]) if r and r[4] is not None else None
                        std_v = float(r[5]) if r and r[5] is not None else None
                        skew_v = float(r[6]) if r and r[6] is not None and not math.isnan(float(r[6])) else None
                        min_v = float(r[7]) if r and r[7] is not None else None
                        qs = [float(r[i]) if r and r[i] is not None else None for i in range(8, 17)]
                        max_v = float(r[17]) if r and r[17] is not None else None
                        p50, p99 = qs[3], qs[7]
                        p99_p50 = (p99 / p50) if (p50 is not None and p50 > 0 and p99 is not None) else None
                        pass_count = int(r[18]) if (is_disc and col.startswith(("h1_", "h2_", "h4_", "h6_")) and r and r[18] is not None) else None
                        pass_share = (pass_count / n_elig) if (pass_count is not None and n_elig > 0) else None
                        dist_rows.append(
                            {
                                "wallet_class": wc,
                                "hypothesis": hyp,
                                "feature": col,
                                "n_cohort": n_cohort,
                                "n_eligible": n_elig,
                                "eligible_share": (n_elig / n_cohort) if n_cohort else 0.0,
                                "missing": missing,
                                "zero_share": zero_share,
                                "mean": mean_v,
                                "stddev": std_v,
                                "skewness": skew_v,
                                "min": min_v,
                                "p01": qs[0],
                                "p10": qs[1],
                                "p25": qs[2],
                                "p50": p50,
                                "p75": qs[4],
                                "p90": qs[5],
                                "p95": qs[6],
                                "p99": p99,
                                "p999": qs[8],
                                "max": max_v,
                                "p99_p50_ratio": p99_p50,
                                "pass_count": pass_count,
                                "pass_share": pass_share,
                                "recommended_scale": recommend_scale(
                                    min_value=min_v,
                                    max_value=max_v,
                                    skewness=skew_v,
                                    p50=p50,
                                    p99=p99,
                                    zero_share=zero_share,
                                    is_discrete=is_disc,
                                ),
                                "assumption": assumption,
                                "snapshot_at": snapshot_id,
                                "is_partial": is_partial,
                            }
                        )
                        nflow_rows.append(
                            {
                                "wallet_class": wc,
                                "hypothesis": hyp,
                                "feature": col,
                                "filter": elig_filter,
                                "n_in": n_cohort,
                                "n_out": n_elig,
                                "n_dropped": n_cohort - n_elig,
                                "retained_share": (n_elig / n_cohort) if n_cohort else 0.0,
                                "reason": assumption,
                                "snapshot_at": snapshot_id,
                                "is_partial": is_partial,
                            }
                        )
                written["distributions"] = stage_dir / "local_wallet_distributions.csv"
                written["feature_nflow"] = stage_dir / "local_feature_nflow.csv"
                pd.DataFrame(dist_rows).to_csv(written["distributions"], index=False)
                pd.DataFrame(nflow_rows).to_csv(written["feature_nflow"], index=False)

                hist_rows: list[dict[str, Any]] = []
                for col, scale_label, edges in HISTOGRAM_SPECS:
                    if col not in available_cols:
                        continue
                    case_clauses = [
                        f"WHEN {col} >= {edges[i]} AND {col} < {edges[i + 1]} THEN {i}"
                        for i in range(len(edges) - 1)
                    ]
                    case_sql = f"CASE {' '.join(case_clauses)} ELSE {len(edges) - 1} END"
                    bins = con.execute(
                        f"SELECT wallet_class, {case_sql} AS bin_idx, COUNT(*) AS n "
                        f"FROM wallet_profile WHERE {col} IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 2"
                    ).fetchall()
                    bin_map = {(str(wc), int(bidx)): int(cnt) for wc, bidx, cnt in bins}
                    elig_by_wc = {
                        str(wc): sum(cnt for (w, _), cnt in bin_map.items() if w == wc)
                        for wc in COHORT_ORDER
                    }
                    for wc in COHORT_ORDER:
                        denom = elig_by_wc[wc]
                        for idx in range(len(edges) - 1):
                            cnt = bin_map.get((wc, idx), 0)
                            hist_rows.append(
                                {
                                    "wallet_class": wc,
                                    "feature": col,
                                    "scale": scale_label,
                                    "bin_index": idx,
                                    "bin_low": edges[idx],
                                    "bin_high": edges[idx + 1],
                                    "count": cnt,
                                    "share": (cnt / denom) if denom else 0.0,
                                    "denominator": denom,
                                    "snapshot_at": snapshot_id,
                                    "is_partial": is_partial,
                                }
                            )
                written["histograms"] = stage_dir / "local_wallet_histograms.csv"
                pd.DataFrame(hist_rows).to_csv(written["histograms"], index=False)
    finally:
        con.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
    return written


def run_stage_profile(
    *,
    load_dir: Path,
    output_dir: Path,
    stage: str = "raw",
    memory_limit: str = "6GB",
    temp_dir: Path = Path("/tmp/duckdb_stage_profile"),
    refresh_columns: bool = True,
) -> dict[str, Path]:
    """Run full-frame DuckDB profiling for either ``raw`` or ``transformed`` snapshots."""
    stage_dir = stage_output_dir(output_dir, stage)
    stage_dir.mkdir(parents=True, exist_ok=True)
    if stage == "transformed":
        return _run_transformed_stage_profile(
            load_dir=load_dir,
            stage_dir=stage_dir,
            memory_limit=memory_limit,
            temp_dir=temp_dir,
            refresh_columns=refresh_columns,
        )

    illicit_dir = _latest_snapshot_dir(load_dir, "illicit", stage="raw")
    licit_dir = _latest_snapshot_dir(load_dir, "licit", stage="raw")
    illicit_manifest = _load_manifest(illicit_dir)
    licit_manifest = _load_manifest(licit_dir)
    snapshot_id = f"{illicit_manifest['snapshot']}+{licit_manifest['snapshot']}"
    is_partial = bool(illicit_manifest.get("partial") or licit_manifest.get("partial"))

    con = _connect_duckdb(memory_limit, temp_dir)
    written: dict[str, Path] = {}
    try:
        _create_source_views(con, illicit_dir, illicit_manifest, licit_dir, licit_manifest)

        if refresh_columns:
            print("[stage:raw] refreshing exact column null profiles...", flush=True)
            written["illicit_columns"] = _refresh_exact_columns(
                con,
                "illicit",
                {
                    "accounts": "i_accounts",
                    "blacklisted_wallets": "i_blacklist",
                    "transactions": "i_tx",
                    "wallet_hops": "i_hops",
                },
                snapshot_id,
                is_partial,
                stage_dir,
            )
            written["licit_columns"] = _refresh_exact_columns(
                con,
                "licit",
                {
                    "accounts": "l_accounts",
                    "seed_wallets": "l_seeds",
                    "transactions": "l_tx",
                    "wallet_hops": "l_hops",
                },
                snapshot_id,
                is_partial,
                stage_dir,
            )

        print("[stage:raw] profiling L1 cleaning & anomaly rules...", flush=True)
        cleaning_df = _build_cleaning_profile(con, snapshot_id, is_partial)
        written["cleaning"] = stage_dir / "local_pretransform_cleaning.csv"
        cleaning_df.to_csv(written["cleaning"], index=False)

        print("[stage:raw] materializing session-local L1/L2 views in DuckDB...", flush=True)
        _materialize_cohort_and_clean_tx(con)

        print("[stage:raw] profiling L2 sampling frame & multiplicity...", flush=True)
        frame_df = _build_sampling_frame_profile(con, snapshot_id, is_partial)
        written["sampling_frame"] = stage_dir / "local_sampling_frame.csv"
        frame_df.to_csv(written["sampling_frame"], index=False)

        print("[stage:raw] computing full-frame L3 H1-H6 wallet distributions...", flush=True)
        _materialize_wallet_features(con)
        dist_df, nflow_df, hist_df = _summarize_wallet_distributions(con, snapshot_id, is_partial)
        written["distributions"] = stage_dir / "local_wallet_distributions.csv"
        written["feature_nflow"] = stage_dir / "local_feature_nflow.csv"
        written["histograms"] = stage_dir / "local_wallet_histograms.csv"
        dist_df.to_csv(written["distributions"], index=False)
        nflow_df.to_csv(written["feature_nflow"], index=False)
        hist_df.to_csv(written["histograms"], index=False)
    finally:
        con.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=VALID_STAGES, default="raw")
    parser.add_argument("--load-dir", default=str(ETL_OUTPUT_DIR / "load"))
    parser.add_argument("--output-dir", default=str(PROFILING_OUTPUT_DIR))
    parser.add_argument("--memory-limit", default="6GB")
    parser.add_argument("--skip-columns-refresh", action="store_true")
    args = parser.parse_args(argv)
    paths = run_stage_profile(
        load_dir=Path(args.load_dir),
        output_dir=Path(args.output_dir),
        stage=args.stage,
        memory_limit=args.memory_limit,
        refresh_columns=not args.skip_columns_refresh,
    )
    for name, path in paths.items():
        print(f"[stage:{args.stage}:{name}] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
