"""Unit, static SQL guardrail, and in-memory DuckDB parity tests for L3 features."""
from __future__ import annotations

import math
import re
from pathlib import Path

import duckdb

from src.scripts.etl.transform.features.main import SQL_STEPS, main, render_sql
from src.scripts.etl.transform.features.rules import (
    compute_burst_ratio_1h,
    compute_cv,
    compute_fan_out_in_ratio,
    compute_interarrival_cv,
    compute_jaccard,
    compute_log1p,
    compute_min_passthrough_sec,
    compute_tx_lifetime_days,
)

SQL_DIR = Path(__file__).resolve().parents[1]


def test_pure_feature_formulas() -> None:
    assert compute_tx_lifetime_days([100.0]) is None
    assert math.isclose(compute_tx_lifetime_days([0.0, 86400.0 * 3.0]) or 0.0, 3.0)
    assert compute_fan_out_in_ratio(0, 0) is None
    assert math.isclose(compute_fan_out_in_ratio(1, 3) or 0.0, 2.0)
    assert compute_jaccard(set(), {"A"}) is None
    assert compute_jaccard({"A", "B"}, {"B", "C"}) == 1.0 / 3.0
    assert compute_cv([10.0, 10.0, 10.0, 10.0]) is None  # <5 events
    assert compute_cv([0.0, 0.0, 0.0, 0.0, 0.0]) is None  # zero mean guard
    assert compute_cv([10.0, 10.0, 10.0, 10.0, 10.0]) == 0.0
    assert compute_interarrival_cv([0.0, 10.0, 20.0, 30.0, 40.0]) == 0.0
    assert compute_interarrival_cv([10.0, 10.0, 10.0, 10.0, 10.0]) is None  # zero mean gap
    assert compute_min_passthrough_sec([(100.0, "OUT"), (200.0, "IN"), (250.0, "OUT")]) == 50.0
    # Same-timestamp tie orders IN before OUT -> lag 0
    assert compute_min_passthrough_sec([(200.0, "OUT"), (200.0, "IN")]) == 0.0
    assert math.isclose(
        compute_burst_ratio_1h(
            [(0.0, 10.0), (100.0, 10.0), (200.0, 10.0), (300.0, 10.0), (10000.0, 10.0)]
        )
        or 0.0,
        0.8,
    )
    assert math.isclose(compute_log1p(3.0) or 0.0, math.log1p(3.0))


def test_sql_guardrails() -> None:
    """Enforce docs/dev/software_concepts/10-sql-rules.md across all L3 SQL files."""
    for _, filename in SQL_STEPS:
        sql_text = (SQL_DIR / filename).read_text(encoding="utf-8")
        no_comments = re.sub(r"--[^\n]*", "", sql_text)
        assert not re.search(r"\bNOT\s+IN\b", no_comments, re.IGNORECASE)
        assert not re.search(r"\bNATURAL\s+JOIN\b", no_comments, re.IGNORECASE)
        assert not re.search(r"\bDISTINCT\s+ON\b", no_comments, re.IGNORECASE)
        assert "hex_address" not in no_comments
        assert "fee_trx" not in no_comments
        assert "illicit." not in no_comments and "licit." not in no_comments


def test_sql_fixture_parity_in_memory_duckdb() -> None:
    """Run all 5 L3 SQL steps on tiny synthetic L1+L2 tables in memory (zero PG writes)."""
    con = duckdb.connect()
    try:
        con.execute("CREATE SCHEMA transform;")
        con.execute(
            """
            CREATE TABLE transform.cohort_wallet (
                wallet_address VARCHAR,
                wallet_class VARCHAR,
                min_hop_level SMALLINT,
                max_hop_level SMALLINT,
                seed_count INTEGER,
                hop_row_count INTEGER,
                primary_seed_address VARCHAR,
                in_accounts_table BOOLEAN,
                in_illicit_accounts BOOLEAN,
                in_licit_accounts BOOLEAN,
                is_licit_seed BOOLEAN,
                is_contaminated_licit_seed BOOLEAN,
                from_contaminated_licit_seed BOOLEAN
            );
            CREATE TABLE transform.clean_transactions (
                tx_hash VARCHAR,
                block_timestamp TIMESTAMPTZ,
                from_address VARCHAR,
                to_address VARCHAR,
                token_symbol VARCHAR,
                amount DOUBLE,
                amount_flag VARCHAR,
                timestamp_flag VARCHAR,
                is_1sun_dust BOOLEAN,
                is_trx_4444_artifact BOOLEAN,
                is_valid_for_features BOOLEAN
            );
            """
        )
        con.execute(
            """
            INSERT INTO transform.cohort_wallet VALUES
                ('W_ACTIVE', 'illicit',    NULL, NULL, 0, 0, NULL,  TRUE,  TRUE,  FALSE, FALSE, FALSE, FALSE),
                ('W_TIE_TS', 'suspicious', 2,    2,    1, 1, 'S1',  TRUE,  TRUE,  FALSE, FALSE, FALSE, FALSE),
                ('W_4444',   'licit',      NULL, NULL, 0, 0, NULL,  TRUE,  FALSE, TRUE,  FALSE, FALSE, FALSE),
                ('W_EMPTY',  'suspicious', 1,    1,    1, 1, 'S1',  FALSE, FALSE, FALSE, FALSE, FALSE, FALSE);

            INSERT INTO transform.clean_transactions VALUES
                -- W_ACTIVE: 1 TRX funding from F1, 5 USDT transfers (including 1 IN then OUT 60s later to F1) + 1 zero-USDT tx
                ('t1', TIMESTAMPTZ '2026-01-01 00:00:00+00', 'F1',       'W_ACTIVE', 'TRX',  10.0,  'ok',   'ok', FALSE, FALSE, TRUE),
                ('t2', TIMESTAMPTZ '2026-01-01 00:10:00+00', 'P1',       'W_ACTIVE', 'USDT', 100.0, 'ok',   'ok', FALSE, FALSE, TRUE),
                ('t3', TIMESTAMPTZ '2026-01-01 00:11:00+00', 'W_ACTIVE', 'F1',       'USDT', 100.0, 'ok',   'ok', FALSE, FALSE, TRUE),
                ('t4', TIMESTAMPTZ '2026-01-01 00:20:00+00', 'W_ACTIVE', 'R2',       'USDT', 100.0, 'ok',   'ok', FALSE, FALSE, TRUE),
                ('t5', TIMESTAMPTZ '2026-01-01 00:30:00+00', 'W_ACTIVE', 'R3',       'USDT', 100.0, 'ok',   'ok', FALSE, FALSE, TRUE),
                ('t6', TIMESTAMPTZ '2026-01-02 00:00:00+00', 'W_ACTIVE', 'R4',       'USDT', 100.0, 'ok',   'ok', FALSE, FALSE, TRUE),
                ('t7', TIMESTAMPTZ '2026-01-02 01:00:00+00', 'W_ACTIVE', 'R4',       'USDT', 0.0,   'zero', 'ok', FALSE, FALSE, FALSE),
                -- W_TIE_TS: 5 identical-timestamp events -> mean gap = 0 -> cv_delta_t_all MUST be NULL (no div-by-zero!)
                ('u1', TIMESTAMPTZ '2026-01-05 00:00:00+00', 'P2',       'W_TIE_TS', 'USDT', 50.0,  'ok',   'ok', FALSE, FALSE, TRUE),
                ('u2', TIMESTAMPTZ '2026-01-05 00:00:00+00', 'W_TIE_TS', 'R5',       'USDT', 50.0,  'ok',   'ok', FALSE, FALSE, TRUE),
                ('u3', TIMESTAMPTZ '2026-01-05 00:00:00+00', 'W_TIE_TS', 'R6',       'USDT', 50.0,  'ok',   'ok', FALSE, FALSE, TRUE),
                ('u4', TIMESTAMPTZ '2026-01-05 00:00:00+00', 'W_TIE_TS', 'R7',       'USDT', 50.0,  'ok',   'ok', FALSE, FALSE, TRUE),
                ('u5', TIMESTAMPTZ '2026-01-05 00:00:00+00', 'W_TIE_TS', 'R8',       'USDT', 50.0,  'ok',   'ok', FALSE, FALSE, TRUE),
                -- W_4444: 1 artifact TRX row + 1 normal TRX dust row -> verify sensitivity columns
                ('v1', TIMESTAMPTZ '2026-07-20 00:00:00+00', 'S_SPAM',   'W_4444',   'TRX',  4444.444444, 'ok',   'ok', FALSE, TRUE,  TRUE),
                ('v2', TIMESTAMPTZ '2026-07-21 00:00:00+00', 'S_DUST',   'W_4444',   'TRX',  0.000001,    'dust', 'ok', TRUE,  FALSE, TRUE);
            """
        )

        for _, filename in SQL_STEPS:
            sql_text = render_sql(filename, transform_schema="transform")
            # DuckDB does not support ALTER TABLE ... ADD CONSTRAINT PRIMARY KEY on populated tables
            sql_text = re.sub(
                r"ALTER TABLE\s+\S+\s+ADD CONSTRAINT\s+\S+\s+PRIMARY KEY\s*\([^)]+\);",
                "",
                sql_text,
                flags=re.IGNORECASE,
            )
            con.execute(sql_text)

        rows = con.execute(
            """
            SELECT wallet_address, total_tx_count, zero_tx_count, trx_tx_count_excl_4444,
                   trx_tx_count_nodust, trx_volume_excl_4444, tx_lifetime_days,
                   burst_ratio_usdt, h2_pass_ge5, min_passthrough_sec_usdt, h1_pass_15m,
                   jaccard_index, h4_pass, cv_delta_t_all, log1p_tx_lifetime_days,
                   elig_h1, elig_h2_ge5, elig_h4, elig_h6_all
            FROM transform.wallet_features
            ORDER BY wallet_address
            """
        ).fetchall()

        assert len(rows) == 4  # Exact 1-to-1 parity with cohort_wallet (never drops W_EMPTY!)
        by_w = {r[0]: r for r in rows}

        # W_ACTIVE assertions
        wa = by_w["W_ACTIVE"]
        assert wa[1] == 6  # 6 non-zero events
        assert wa[2] == 1  # 1 zero-USDT event preserved in zero_tx_count
        assert math.isclose(wa[6], 1.0)  # exactly 1 day span
        assert math.isclose(wa[7], 0.8)  # 400/500 USDT within 1h window
        assert wa[8] == 1.0  # lifetime <= 7d AND burst >= 0.75
        assert math.isclose(wa[9], 60.0)  # t2 IN 00:10 -> t3 OUT 00:11 = 60s
        assert wa[10] == 1.0  # <= 900s
        assert math.isclose(wa[11], 0.25)  # TRX funders={F1}, USDT recip={F1,R2,R3,R4} -> 1/4
        assert wa[12] == 0.0  # 0.25 < 0.50
        assert wa[13] is not None and wa[13] > 0.0
        assert math.isclose(wa[14], math.log1p(1.0))
        assert (wa[15], wa[16], wa[17], wa[18]) == (True, True, True, True)

        # W_TIE_TS assertions: tied timestamps -> lag 0, zero-mean-gap guard returns NULL CV
        wt = by_w["W_TIE_TS"]
        assert wt[9] == 0.0
        assert wt[13] is None
        assert wt[18] is False

        # W_4444 assertions: sensitivity columns isolate 4444.444444 and dust cleanly
        w4 = by_w["W_4444"]
        assert w4[1] == 2
        assert w4[3] == 1  # trx_tx_count_excl_4444
        assert w4[4] == 1  # trx_tx_count_nodust
        assert math.isclose(w4[5], 0.000001)  # trx_volume_excl_4444

        # W_EMPTY (hop-only wallet): retained with 0 tx counts and NULL features
        we = by_w["W_EMPTY"]
        assert we[1] == 0
        assert we[6] is None
        assert (we[15], we[16], we[17], we[18]) == (False, False, False, False)
    finally:
        con.close()


def test_cli_dry_run() -> None:
    assert main(["--dry-run", "--step", "all"]) == 0


if __name__ == "__main__":
    test_pure_feature_formulas()
    test_sql_guardrails()
    test_sql_fixture_parity_in_memory_duckdb()
    test_cli_dry_run()
    print("L3 features checks passed")
