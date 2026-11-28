"""Assert-based checks for stage profiling rules, stage routing, and DuckDB SQL logic."""
from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from src.scripts.etl.transform.profile.profile_stage import (
    TRX_SUPPLY_CEILING,
    USDT_SUPPLY_CEILING,
    _amount_flag_sql,
    _refresh_exact_columns,
    _resolve_transformed_partial,
    classify_amount_flag,
    classify_timestamp_flag,
    recommend_scale,
    run_stage_profile,
)
from src.scripts.etl.transform.profile.schema import stage_output_dir


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_stage_output_dir() -> None:
    base = Path("/tmp/profile")
    check(stage_output_dir(base, "raw") == Path("/tmp/profile/raw"), "append raw")
    check(stage_output_dir(base, "transformed") == Path("/tmp/profile/transformed"), "append transformed")
    check(stage_output_dir(base / "raw", "raw") == Path("/tmp/profile/raw"), "no double raw/raw")
    check(
        stage_output_dir(base / "transformed", "transformed") == Path("/tmp/profile/transformed"),
        "no double transformed/transformed",
    )
    try:
        stage_output_dir(base, "invalid")
    except ValueError:
        return
    raise AssertionError("invalid stage must raise ValueError")


def test_amount_flag_priority() -> None:
    check(classify_amount_flag(None, "USDT") == "null", "null amount")
    check(classify_amount_flag(float("nan"), "USDT") == "null", "nan amount")
    check(classify_amount_flag(-1.0, "USDT") == "negative", "negative amount")
    check(classify_amount_flag(1.157920892373162e71, "USDT") == "sentinel", "uint256 sentinel")
    check(classify_amount_flag(5.78960446186581e70, "USDT") == "sentinel", "uint255 sentinel")
    check(classify_amount_flag(USDT_SUPPLY_CEILING + 1.0, "USDT") == "above_supply", "above USDT supply")
    check(classify_amount_flag(TRX_SUPPLY_CEILING + 1.0, "TRX") == "above_supply", "above TRX supply")
    check(classify_amount_flag(0.0, "USDT") == "zero", "zero amount")
    check(classify_amount_flag(0.000001, "TRX") == "dust", "1-SUN TRX dust")
    check(classify_amount_flag(0.009999, "USDT") == "dust", "sub-cent USDT dust")
    check(classify_amount_flag(0.01, "USDT") == "ok", "exact 0.01 is ok")
    check(classify_amount_flag(1_000_000.0, "USDT") == "ok", "exact 1e6 is ok")
    check(classify_amount_flag(1_000_000.01, "USDT") == "large_review", "above 1e6 is large_review")
    check(classify_amount_flag(USDT_SUPPLY_CEILING, "USDT") == "large_review", "at supply is large_review")


def test_timestamp_flag() -> None:
    check(classify_timestamp_flag(None) == "null", "null ts")
    check(classify_timestamp_flag(datetime(1990, 3, 19, tzinfo=UTC)) == "pre_mainnet", "1990 pre_mainnet")
    check(classify_timestamp_flag(datetime(2018, 6, 24, 23, 59, tzinfo=UTC)) == "pre_mainnet", "day before launch")
    check(classify_timestamp_flag(datetime(2018, 6, 25, 0, 0, tzinfo=UTC)) == "ok", "launch day ok")
    check(classify_timestamp_flag(datetime(2027, 1, 1, tzinfo=UTC)) == "future", "future ts")


def test_recommend_scale() -> None:
    check(
        recommend_scale(min_value=0.0, max_value=1.0, skewness=2.5, p50=0.0, p99=0.8, zero_share=0.8)
        == "bounded_0_1_zero_inflated",
        "zero-inflated bounded",
    )
    check(
        recommend_scale(min_value=0.0, max_value=1.0, skewness=-0.5, p50=0.9, p99=1.0, zero_share=0.01)
        == "bounded_0_1",
        "bounded 0..1",
    )
    check(
        recommend_scale(min_value=0.0, max_value=1e7, skewness=12.0, p50=10.0, p99=5000.0, zero_share=0.1)
        == "log1p_in_L3_plus_train_only_robust_scaler",
        "heavy-tailed non-negative",
    )
    check(
        recommend_scale(min_value=1.0, max_value=5.0, skewness=0.1, p50=3.0, p99=5.0, zero_share=0.0, is_discrete=True)
        == "discrete_or_ordinal",
        "discrete",
    )


def test_sql_amount_flag_matches_python() -> None:
    con = duckdb.connect()
    try:
        sql = f"""
        SELECT token_symbol, amount, {_amount_flag_sql('amount', 'token_symbol')} AS flag
        FROM (VALUES
            ('USDT', NULL::DOUBLE),
            ('USDT', -5.0),
            ('USDT', 1.157920892373162e71),
            ('USDT', 1e12),
            ('TRX', 2e11),
            ('USDT', 0.0),
            ('TRX', 0.000001),
            ('USDT', 500.0),
            ('USDT', 2000000.0)
        ) AS t(token_symbol, amount)
        """
        for token, amt, sql_flag in con.execute(sql).fetchall():
            py_flag = classify_amount_flag(amt, token)
            check(sql_flag == py_flag, f"SQL/Python mismatch for ({token}, {amt}): {sql_flag} != {py_flag}")
    finally:
        con.close()


def test_duckdb_fixture_null_free() -> None:
    """Verify exact Parquet column profiling never produces negative nulls."""
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        con = duckdb.connect()
        try:
            con.execute(
                """
                CREATE VIEW v_acc AS
                SELECT * FROM (VALUES ('T1', TIMESTAMP '2024-01-01 00:00:00+00'), ('T2', NULL)) AS t(address, created_at)
                """
            )
            csv_path = _refresh_exact_columns(
                con, "illicit", {"accounts": "v_acc"}, "snap1", False, out_dir
            )
            rows = list(con.execute(f'SELECT "column", nulls, sample_rows FROM read_csv_auto(\'{csv_path}\')').fetchall())
            check(all(n >= 0 for _, n, _ in rows), "nulls must never be negative")
            by_col = {c: (n, s) for c, n, s in rows}
            check(by_col["address"] == (0, 2), "address nulls=0, sample_rows=2")
            check(by_col["created_at"] == (1, 2), "created_at nulls=1, sample_rows=2")
        finally:
            con.close()


def test_resolve_transformed_partial() -> None:
    check(
        _resolve_transformed_partial(
            {"partial": True, "tables": {"wallet_features": {"status": "unknown"}}}
        )
        is False,
        "unknown-only transformed tables are not partial",
    )
    check(
        _resolve_transformed_partial(
            {"partial": True, "tables": {"wallet_features": {"status": "partial"}}}
        )
        is True,
        "explicit partial table remains partial",
    )
    check(
        _resolve_transformed_partial(
            {"partial": False, "tables": {"wallet_features": {"status": "complete"}}}
        )
        is False,
        "complete transformed table is not partial",
    )


def test_transformed_stage_fixture() -> None:
    """Verify --stage transformed writes matching CSV schemas into output_dir/transformed/."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        load_dir = root / "load"
        snap_dir = load_dir / "phase1_transformed_transform_20261127T000000Z"
        snap_dir.mkdir(parents=True)
        out_dir = root / "profile_out"

        wf_path = snap_dir / "wallet_features.parquet"
        tx_path = snap_dir / "clean_transactions.parquet"
        cw_path = snap_dir / "cohort_wallet.parquet"
        hops_path = snap_dir / "clean_wallet_hops.parquet"
        con = duckdb.connect()
        try:
            con.execute(
                f"""
                COPY (
                    SELECT * FROM (VALUES
                        ('T1', 'illicit', 10.0, LN(11.0), 0.8, LN(101.0), TRUE, 5::BIGINT),
                        ('T2', 'suspicious', 2.0, LN(3.0), 0.9, LN(51.0), FALSE, 0::BIGINT),
                        ('T3', 'licit', 20.0, LN(21.0), 0.2, LN(21.0), TRUE, 2::BIGINT),
                        ('T4', 'licit', NULL::DOUBLE, NULL::DOUBLE, NULL::DOUBLE, NULL::DOUBLE, TRUE, 0::BIGINT)
                    ) AS t(wallet_address, wallet_class, tx_lifetime_days, log1p_tx_lifetime_days, burst_ratio_usdt, log1p_usdt_volume, in_accounts_table, total_tx_count)
                ) TO '{wf_path}' (FORMAT PARQUET)
                """
            )
            con.execute(
                f"""
                COPY (
                    SELECT * FROM (VALUES
                        ('tx1', TIMESTAMPTZ '2026-01-01 00:00:00+00', 'USDT', 100.0, 0.0, 'illicit', FALSE, FALSE, 'ok', 'ok', FALSE, FALSE, TRUE),
                        ('tx2', TIMESTAMPTZ '1990-01-01 00:00:00+00', 'TRX', 0.000001, 0.0, 'licit', TRUE, FALSE, 'dust', 'pre_mainnet', TRUE, FALSE, FALSE),
                        ('tx3', TIMESTAMPTZ '2026-02-01 00:00:00+00', 'TRX', 0.000001, 0.0, 'licit', FALSE, FALSE, 'dust', 'ok', TRUE, FALSE, TRUE)
                    ) AS t(tx_hash, block_timestamp, token_symbol, amount, fee_trx, source_schema, in_both_schemas, has_cross_schema_conflict, amount_flag, timestamp_flag, is_1sun_dust, is_trx_4444_artifact, is_valid_for_features)
                ) TO '{tx_path}' (FORMAT PARQUET)
                """
            )
            con.execute(
                f"""
                COPY (
                    SELECT * FROM (VALUES
                        ('T1', 'illicit', NULL::SMALLINT, NULL::SMALLINT, TRUE, TRUE, TRUE, TRUE),
                        ('T2', 'suspicious', 1::SMALLINT, 1::SMALLINT, FALSE, FALSE, TRUE, FALSE),
                        ('T3', 'licit', NULL::SMALLINT, NULL::SMALLINT, TRUE, FALSE, TRUE, FALSE),
                        ('T4', 'licit', NULL::SMALLINT, NULL::SMALLINT, TRUE, FALSE, TRUE, FALSE)
                    ) AS t(wallet_address, wallet_class, min_hop_level, max_hop_level, in_accounts_table, in_illicit_accounts, in_licit_accounts, is_licit_seed)
                ) TO '{cw_path}' (FORMAT PARQUET)
                """
            )
            con.execute(
                f"""
                COPY (
                    SELECT * FROM (VALUES
                        ('T2', 'T1', 1::SMALLINT, 'ok')
                    ) AS t(wallet_address, seed_address, hop_level, via_tx_status)
                ) TO '{hops_path}' (FORMAT PARQUET)
                """
            )
        finally:
            con.close()

        manifest = {
            "snapshot": "phase1_transformed_transform_20261127T000000Z",
            "stage": "transformed",
            "schema": "transform",
            "partial": True,
            "tables": {
                "wallet_features": {"file": "wallet_features.parquet", "status": "unknown"},
                "clean_transactions": {"file": "clean_transactions.parquet", "status": "unknown"},
                "cohort_wallet": {"file": "cohort_wallet.parquet", "status": "unknown"},
                "clean_wallet_hops": {"file": "clean_wallet_hops.parquet", "status": "unknown"},
            },
        }
        (snap_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        written = run_stage_profile(
            load_dir=load_dir,
            output_dir=out_dir,
            stage="transformed",
            temp_dir=root / "duck_tmp",
        )
        for key in ("columns", "db_overview", "cleaning", "cohort_counts", "nflow", "group_overlap", "sampling_frame", "hop_seed", "distributions", "feature_nflow"):
            check(key in written and written[key].exists(), f"missing transformed output: {key}")
        check(written["distributions"].parent == out_dir / "transformed", "writes inside transformed/")
        dist = pd.read_csv(written["distributions"])
        nflow = pd.read_csv(written["feature_nflow"])
        cleaning = pd.read_csv(written["cleaning"])
        check(
            set(dist["feature"]) == {"total_tx_count", "tx_lifetime_days", "log1p_tx_lifetime_days", "burst_ratio_usdt", "log1p_usdt_volume"},
            "present core + transformed extra features",
        )
        check(not bool(dist["is_partial"].any()), "unknown-only transformed snapshot must not mark is_partial=True")
        check((nflow["n_in"] - nflow["n_out"] == nflow["n_dropped"]).all(), "nflow arithmetic")
        ts_flags = cleaning[cleaning["section"] == "timestamp_flag"]
        check(set(ts_flags["category"]) == {"ok"}, "pre_mainnet excluded from post-L1 valid-for-features timestamp flags")


test_stage_output_dir()
test_amount_flag_priority()
test_timestamp_flag()
test_recommend_scale()
test_sql_amount_flag_matches_python()
test_duckdb_fixture_null_free()
test_resolve_transformed_partial()
test_transformed_stage_fixture()
print("profile stage checks passed")
