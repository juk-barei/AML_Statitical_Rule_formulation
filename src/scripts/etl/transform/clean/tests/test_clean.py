"""Unit, static SQL guardrail, and in-memory DuckDB parity tests for L1 clean."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from src.scripts.etl.transform.clean.main import SQL_STEPS, main, render_sql
from src.scripts.etl.transform.clean.rules import (
    TRX_SUPPLY_CEILING,
    USDT_SUPPLY_CEILING,
    TxRowFacts,
    classify_amount_flag,
    classify_timestamp_flag,
    dedupe_sort_key,
    is_1sun_dust,
    is_trx_4444_artifact,
    is_valid_for_features,
)

SQL_DIR = Path(__file__).resolve().parents[1]


def test_amount_and_timestamp_rules() -> None:
    assert classify_amount_flag(None, "USDT") == "null"
    assert classify_amount_flag(float("nan"), "TRX") == "null"
    assert classify_amount_flag(-0.5, "USDT") == "negative"
    assert classify_amount_flag(1.157920892373162e71, "USDT") == "sentinel"
    assert (
        classify_amount_flag(
            1.0,
            "USDT",
            amount_exact="115792089237316190183760311394656140241344763643041023198016376741560320",
        )
        == "sentinel"
    )
    assert classify_amount_flag(USDT_SUPPLY_CEILING + 1.0, "USDT") == "above_supply"
    assert classify_amount_flag(TRX_SUPPLY_CEILING + 1.0, "TRX") == "above_supply"
    assert classify_amount_flag(0.0, "USDT") == "zero"
    assert classify_amount_flag(0.000001, "TRX") == "dust"
    assert classify_amount_flag(0.01, "USDT") == "ok"
    assert classify_amount_flag(1_000_000.0, "USDT") == "ok"
    assert classify_amount_flag(1_000_000.01, "USDT") == "large_review"

    assert classify_timestamp_flag(None) == "null"
    assert classify_timestamp_flag(datetime(1970, 7, 12, tzinfo=UTC)) == "pre_mainnet"
    assert classify_timestamp_flag(datetime(1990, 3, 19, tzinfo=UTC)) == "pre_mainnet"
    assert classify_timestamp_flag(datetime(2018, 6, 25, tzinfo=UTC)) == "ok"
    assert classify_timestamp_flag(datetime(2027, 1, 1, tzinfo=UTC)) == "future"

    assert is_1sun_dust(0.000001, "TRX")
    assert not is_1sun_dust(0.000001, "USDT")
    assert is_trx_4444_artifact(4444.444444, "TRX")
    assert not is_trx_4444_artifact(4444.444444, "USDT")

    assert is_valid_for_features("ok", "ok")
    assert is_valid_for_features("dust", "ok")
    assert is_valid_for_features("large_review", "ok")
    assert not is_valid_for_features("zero", "ok")
    assert not is_valid_for_features("sentinel", "ok")
    assert not is_valid_for_features("ok", "pre_mainnet")


def test_dedupe_tie_break_priority() -> None:
    good_licit = TxRowFacts("licit", "USDT", 50.0, datetime(2026, 1, 1, tzinfo=UTC))
    bad_illicit_sentinel = TxRowFacts("illicit", "USDT", 1.1579e71, datetime(2026, 1, 1, tzinfo=UTC))
    bad_illicit_ts = TxRowFacts("illicit", "TRX", 10.0, datetime(1990, 3, 19, tzinfo=UTC))
    good_illicit = TxRowFacts("illicit", "USDT", 50.0, datetime(2026, 1, 1, tzinfo=UTC))

    # Valid licit beats invalid illicit (sentinel or pre_mainnet)
    assert dedupe_sort_key(good_licit) < dedupe_sort_key(bad_illicit_sentinel)
    assert dedupe_sort_key(good_licit) < dedupe_sort_key(bad_illicit_ts)
    # When both valid, illicit wins deterministic tie-break
    assert dedupe_sort_key(good_illicit) < dedupe_sort_key(good_licit)


def test_sql_guardrails() -> None:
    """Enforce docs/dev/software_concepts/10-sql-rules.md across all L1 SQL files."""
    for _, filename in SQL_STEPS:
        sql_text = (SQL_DIR / filename).read_text(encoding="utf-8")
        # Strip SQL comments before checking forbidden constructs.
        no_comments = re.sub(r"--[^\n]*", "", sql_text)
        assert not re.search(r"\bNOT\s+IN\b", no_comments, re.IGNORECASE) or "amount_flag NOT IN" in no_comments
        assert not re.search(r"\bNATURAL\s+JOIN\b", no_comments, re.IGNORECASE)
        assert not re.search(r"\bDISTINCT\s+ON\b", no_comments, re.IGNORECASE)
        assert "hex_address" not in no_comments
        assert "{" not in no_comments and "}" not in no_comments


def test_sql_fixture_parity_in_memory_duckdb() -> None:
    """Run rendered L1 SQL logic on tiny synthetic schemas in memory (zero PG writes)."""
    con = duckdb.connect()
    try:
        con.execute("CREATE SCHEMA illicit; CREATE SCHEMA licit;")
        con.execute(
            """
            CREATE TABLE illicit.transactions (
                tx_hash VARCHAR, block_number BIGINT, block_timestamp TIMESTAMPTZ,
                from_address VARCHAR, to_address VARCHAR, token_symbol VARCHAR,
                contract_address VARCHAR, amount DOUBLE, fee_trx DOUBLE, created_at TIMESTAMPTZ
            );
            CREATE TABLE licit.transactions (
                tx_hash VARCHAR, block_number BIGINT, block_timestamp TIMESTAMPTZ,
                from_address VARCHAR, to_address VARCHAR, token_symbol VARCHAR,
                contract_address VARCHAR, amount DOUBLE, fee_trx DOUBLE, created_at TIMESTAMPTZ
            );
            CREATE TABLE illicit.wallet_hops (
                hop_id BIGINT, wallet_address VARCHAR, seed_address VARCHAR,
                parent_address VARCHAR, via_tx_hash VARCHAR, hop_level SMALLINT,
                direction VARCHAR, discovered_at TIMESTAMPTZ
            );
            """
        )
        con.execute(
            """
            INSERT INTO illicit.transactions VALUES
                ('tx_ok',       10, TIMESTAMPTZ '2026-01-01 00:00:00+00', 'A', 'B', 'USDT', 'TR7', 100.0, 0.1, TIMESTAMPTZ '2026-11-01 00:00:00+00'),
                ('tx_conflict', 0,  TIMESTAMPTZ '2026-01-02 00:00:00+00', 'A', 'B', 'USDT', 'TR7', 0.0,   0.0, TIMESTAMPTZ '2026-11-01 00:00:00+00'),
                ('tx_pre',      11, TIMESTAMPTZ '1990-03-19 00:00:00+00', 'A', 'C', 'TRX',  NULL,  5.0,   0.0, TIMESTAMPTZ '2026-11-01 00:00:00+00'),
                ('tx_1sun',     12, TIMESTAMPTZ '2026-01-03 00:00:00+00', 'A', 'D', 'TRX',  NULL,  0.000001, 0.0, TIMESTAMPTZ '2026-11-01 00:00:00+00');
            INSERT INTO licit.transactions VALUES
                ('tx_conflict', 0,  TIMESTAMPTZ '2026-01-02 00:00:00+00', 'A', 'B', 'USDT', 'TR7', 1.157920892373162e71, 0.0, TIMESTAMPTZ '2026-11-11 00:00:00+00'),
                ('tx_4444',     13, TIMESTAMPTZ '2026-07-20 00:00:00+00', 'X', 'Y', 'TRX',  NULL,  4444.444444, 0.0, TIMESTAMPTZ '2026-11-11 00:00:00+00'),
                ('tx_abv_trx',  14, TIMESTAMPTZ '2026-08-24 00:00:00+00', 'X', 'Z', 'TRX',  NULL,  200000000000.0, 0.0, TIMESTAMPTZ '2026-11-11 00:00:00+00');
            INSERT INTO illicit.wallet_hops VALUES
                (1, 'S1', 'S1', NULL, NULL,        0, 'OUT', TIMESTAMPTZ '2026-11-01 00:00:00+00'),
                (2, 'D',  'S1', 'A',  'tx_1sun',   1, 'OUT', TIMESTAMPTZ '2026-11-01 00:00:00+00'),
                (3, 'M',  'S1', 'A',  'tx_absent', 2, 'OUT', TIMESTAMPTZ '2026-11-01 00:00:00+00');
            """
        )

        # Render the real SQL files (DuckDB parses PostgreSQL casts except 'NaN'::DOUBLE)
        sql_01 = render_sql(
            "01_clean_transactions.sql",
            transform_schema="transform",
            illicit_schema="illicit",
            licit_schema="licit",
        ).replace("amount = 'NaN'::DOUBLE PRECISION", "isnan(amount)")
        sql_02 = render_sql(
            "02_clean_wallet_hops.sql",
            transform_schema="transform",
            illicit_schema="illicit",
            licit_schema="licit",
        )
        con.execute(sql_01)
        con.execute(sql_02)

        # Verify conflict audit table caught tx_conflict
        conflicts = con.execute("SELECT tx_hash, diff_amount FROM transform.clean_tx_conflicts").fetchall()
        assert conflicts == [("tx_conflict", True)]

        # Verify deduplicated count (4 + 3 - 1 = 6) and exact Python parity
        rows = con.execute(
            """
            SELECT tx_hash, source_schema, token_symbol, amount, block_timestamp,
                   amount_flag, timestamp_flag, is_1sun_dust, is_trx_4444_artifact,
                   is_valid_for_features, has_cross_schema_conflict
            FROM transform.clean_transactions
            ORDER BY tx_hash
            """
        ).fetchall()
        assert len(rows) == 6
        by_hash = {r[0]: r for r in rows}

        # tx_conflict must pick illicit (zero) over licit (sentinel)
        assert by_hash["tx_conflict"][1] == "illicit"
        assert by_hash["tx_conflict"][5] == "zero"
        assert by_hash["tx_conflict"][10] is True

        for tx_hash, _, tok, amt, ts, a_flag, t_flag, f_1sun, f_4444, f_valid, _ in rows:
            assert a_flag == classify_amount_flag(amt, tok), tx_hash
            assert t_flag == classify_timestamp_flag(ts), tx_hash
            assert f_1sun == is_1sun_dust(amt, tok), tx_hash
            assert f_4444 == is_trx_4444_artifact(amt, tok), tx_hash
            assert f_valid == is_valid_for_features(a_flag, t_flag), tx_hash

        # Verify clean_wallet_hops keeps all 3 rows with accurate via_tx_status
        hops = dict(
            con.execute(
                "SELECT hop_id, via_tx_status FROM transform.clean_wallet_hops ORDER BY hop_id"
            ).fetchall()
        )
        assert hops == {1: "null_hop0", 2: "dust", 3: "missing_tx"}
    finally:
        con.close()


def test_cli_dry_run() -> None:
    assert main(["--dry-run", "--step", "all"]) == 0


if __name__ == "__main__":
    test_amount_and_timestamp_rules()
    test_dedupe_tie_break_priority()
    test_sql_guardrails()
    test_sql_fixture_parity_in_memory_duckdb()
    test_cli_dry_run()
    print("L1 clean checks passed")

