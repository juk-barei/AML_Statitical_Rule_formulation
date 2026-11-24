"""Fast checks for the Parquet source adapter."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import duckdb

from src.scripts.etl.extract.parquet_source import (
    ParquetColumn,
    build_target_columns,
    load_parquet_snapshot,
    parse_table_spec,
    postgres_type,
    sha256_file,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def rejects(callable_check, message: str) -> None:
    try:
        callable_check()
    except (ValueError, TypeError):
        return
    raise AssertionError(message)


def write_fixture(root: Path, *, status: str = "complete") -> Path:
    parquet_path = root / "fixture__wallet_hops.parquet"
    with duckdb.connect() as connection:
        connection.execute(
            f"""
            COPY (
                SELECT
                    'wallet-1' AS wallet_address,
                    1.5::DOUBLE AS amount,
                    '1.50' AS amount_exact,
                    0.1::DECIMAL(18, 6) AS fee_trx,
                    1::SMALLINT AS hop_level,
                    TIMESTAMPTZ '2026-01-01 00:00:00+00' AS discovered_at
            ) TO '{parquet_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )
    manifest = {
        "format": "parquet",
        "schema": "illicit",
        "snapshot": "fixture_20260101T000000Z",
        "created_at": "2026-01-01T00:00:00+00:00",
        "partial": False,
        "tables": {
            "wallet_hops": {
                "file": parquet_path.name,
                "rows": 1,
                "columns": [
                    "wallet_address",
                    "amount",
                    "amount_exact",
                    "fee_trx",
                    "hop_level",
                    "discovered_at",
                ],
                "sha256": sha256_file(parquet_path),
                "status": status,
            }
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return parquet_path


def main() -> int:
    check(postgres_type("VARCHAR") == "TEXT", "varchar mapping")
    check(postgres_type("DOUBLE") == "DOUBLE PRECISION", "double mapping")
    check(postgres_type("DECIMAL(18,6)") == "NUMERIC(18,6)", "decimal mapping")
    check(
        postgres_type("TIMESTAMP WITH TIME ZONE") == "TIMESTAMPTZ",
        "timestamp mapping",
    )
    rejects(lambda: postgres_type("STRUCT"), "unknown type must fail")

    target_columns, select_expressions = build_target_columns(
        (
            ParquetColumn("wallet_address", "VARCHAR"),
            ParquetColumn("amount", "DOUBLE"),
            ParquetColumn("amount_exact", "VARCHAR"),
            ParquetColumn("fee_trx", "DECIMAL(18,6)"),
        )
    )
    check(
        target_columns
        == (
            ("wallet_address", "TEXT"),
            ("amount", "NUMERIC"),
            ("fee_trx", "NUMERIC(18,6)"),
        ),
        "amount_exact must become the numeric amount column",
    )
    check(
        select_expressions
        == ('"wallet_address"', '"amount_exact" AS "amount"', '"fee_trx"'),
        "exact select expressions",
    )
    check(parse_table_spec("all") is None, "all tables")
    check(
        parse_table_spec("accounts,transactions") == ("accounts", "transactions"),
        "comma table list",
    )
    rejects(lambda: parse_table_spec(" , "), "empty table list must fail")

    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        write_fixture(root)
        snapshot = load_parquet_snapshot(
            root,
            target_schema="illicit",
            verify_hashes=True,
        )
        check(snapshot.schema == "illicit", "snapshot schema")
        check(snapshot.partial is False, "snapshot partial flag")
        check(len(snapshot.tables) == 1, "one selected table")
        table = snapshot.tables[0]
        check(table.name == "wallet_hops", "table name")
        check(table.planned_rows == 1, "planned row count")
        check(
            ("amount", "NUMERIC") in table.target_columns,
            "target amount type",
        )

        limited = load_parquet_snapshot(
            root,
            target_schema="illicit",
            row_limits={"all": 0},
            verify_hashes=False,
        )
        check(limited.tables[0].planned_rows == 0, "row limit")

        rejects(
            lambda: load_parquet_snapshot(
                Path("outputs/etl/export"),
                target_schema="illicit",
            ),
            "relative path must fail",
        )
        rejects(
            lambda: load_parquet_snapshot(
                root,
                target_schema="licit",
            ),
            "schema mismatch must fail",
        )
        allowed = load_parquet_snapshot(
            root,
            target_schema="licit",
            allow_schema_mismatch=True,
            verify_hashes=False,
        )
        check(allowed.schema == "illicit", "explicit mismatch keeps provenance")

        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["tables"]["wallet_hops"]["sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        rejects(
            lambda: load_parquet_snapshot(
                root,
                target_schema="illicit",
                verify_hashes=True,
            ),
            "hash mismatch must fail",
        )

        manifest["tables"]["wallet_hops"]["status"] = "partial"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        rejects(
            lambda: load_parquet_snapshot(
                root,
                target_schema="illicit",
                verify_hashes=False,
            ),
            "partial table must fail without --allow-partial",
        )
        allowed_partial = load_parquet_snapshot(
            root,
            target_schema="illicit",
            verify_hashes=False,
            allow_partial=True,
        )
        check(
            allowed_partial.tables[0].status == "partial",
            "explicit partial load keeps provenance",
        )

        manifest_path.unlink()
        rejects(
            lambda: load_parquet_snapshot(root, target_schema="illicit"),
            "missing manifest must fail",
        )

    print("Parquet source checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
