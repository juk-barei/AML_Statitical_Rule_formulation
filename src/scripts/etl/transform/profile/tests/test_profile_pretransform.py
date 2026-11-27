"""Assert-based checks for pre-transform profiling rules and DuckDB SQL logic."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import tempfile

import duckdb

from src.scripts.etl.transform.profile.profile_pretransform import (
    TRX_SUPPLY_CEILING,
    USDT_SUPPLY_CEILING,
    classify_amount_flag,
    classify_timestamp_flag,
    recommend_scale,
    _amount_flag_sql,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


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
    from src.scripts.etl.transform.profile.profile_pretransform import _refresh_exact_columns

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


test_amount_flag_priority()
test_timestamp_flag()
test_recommend_scale()
test_sql_amount_flag_matches_python()
test_duckdb_fixture_null_free()
print("profile pretransform checks passed")
