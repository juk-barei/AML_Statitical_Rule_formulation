"""Assert-based checks for the export CLI, naming, typing, and completeness."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.sql.sqltypes import BigInteger, Boolean, DateTime, Numeric, String

from src.scripts.etl.load import (
    Coverage,
    clear_previous_snapshot,
    completeness,
    export_type,
    output_filenames,
    parse_args,
    parse_tables,
    project_phase,
    resolve_compression,
    safe_basename,
    snapshot_name,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def rejects(callable_object, message: str) -> None:
    try:
        callable_object()
    except (ValueError, SystemExit):
        return
    raise AssertionError(message)


def test_cli_defaults() -> None:
    args = parse_args(["--schema", "illicit"])
    check(args.schema == "illicit", "schema is required and stored")
    check(args.tables == "all", "tables default")
    check(args.format == "parquet", "format default")
    check(args.stage == "raw", "stage default")
    check(args.compression is None, "compression resolves later")
    check(args.allow_partial is False, "partial is opt-in")
    check(args.allow_large_csv is False, "large CSV is opt-in")
    with contextlib.redirect_stderr(io.StringIO()):
        rejects(lambda: parse_args([]), "schema must be required")


def test_compression_resolution() -> None:
    check(resolve_compression("parquet", None) == "zstd", "parquet default")
    check(resolve_compression("csv", None) == "gzip", "csv default")
    check(resolve_compression("csv", "none") == "none", "csv none")
    check(resolve_compression("parquet", "snappy") == "snappy", "parquet snappy")
    rejects(lambda: resolve_compression("csv", "zstd"), "csv cannot use zstd")
    rejects(lambda: resolve_compression("parquet", "brotli"), "unknown parquet codec")


def test_table_selection_spec() -> None:
    check(parse_tables("all") is None, "all expands later")
    check(
        parse_tables("accounts, transactions,accounts") == ("accounts", "transactions"),
        "tables are trimmed, split, and deduplicated",
    )
    rejects(lambda: parse_tables(""), "empty table list")
    rejects(lambda: parse_tables("all,accounts"), "all cannot be mixed")


def test_names_are_basenames() -> None:
    check(safe_basename("illicit_raw") == "illicit_raw", "plain name")
    rejects(lambda: safe_basename("../escape"), "path traversal")
    rejects(lambda: safe_basename("sub/name"), "subdirectory")
    rejects(lambda: safe_basename("sub\\name"), "windows separator")
    rejects(lambda: safe_basename(".."), "parent directory")


def test_snapshot_naming() -> None:
    check(project_phase() == 1, "phase comes from pyproject.toml")
    check(
        snapshot_name(1, "raw", "illicit", "20261123T000000Z")
        == "phase1_raw_illicit_20261123T000000Z",
        "phase/stage/schema/time snapshot name",
    )
    check(
        snapshot_name(2, "transformed", "licit", "20261124T000000Z")
        == "phase2_transformed_licit_20261124T000000Z",
        "transformed snapshot name",
    )


def test_output_filenames() -> None:
    prefix = "phase1_raw_illicit_20261123T000000Z"
    check(
        output_filenames(
            "illicit", ("accounts",), "", "parquet", "zstd", default_prefix=prefix
        )
        == {"accounts": f"{prefix}__accounts.parquet"},
        "single table default name",
    )
    check(
        output_filenames(
            "illicit",
            ("accounts",),
            "wallets.parquet",
            "parquet",
            "zstd",
            default_prefix=prefix,
        )
        == {"accounts": "wallets.parquet"},
        "single table exact name",
    )
    check(
        output_filenames(
            "illicit",
            ("accounts", "transactions"),
            "raw",
            "parquet",
            "zstd",
            default_prefix=prefix,
        )
        == {
            "accounts": "raw__accounts.parquet",
            "transactions": "raw__transactions.parquet",
        },
        "multi-table prefix",
    )
    check(
        output_filenames(
            "illicit",
            ("transactions",),
            "",
            "csv",
            "gzip",
            default_prefix=prefix,
        )
        == {"transactions": f"{prefix}__transactions.csv.gz"},
        "gzip csv extension",
    )
    rejects(
        lambda: output_filenames(
            "illicit",
            ("accounts",),
            "x.csv",
            "parquet",
            "zstd",
            default_prefix=prefix,
        ),
        "mismatched single-table extension",
    )
    rejects(
        lambda: output_filenames(
            "illicit",
            ("accounts", "transactions"),
            "x.parquet",
            "parquet",
            "zstd",
            default_prefix=prefix,
        ),
        "multi-table name must be a prefix",
    )


def test_export_types() -> None:
    check(export_type(Numeric(18, 6)) == "DECIMAL(18, 6)", "constrained numeric")
    check(export_type(Numeric()) == "DOUBLE", "unconstrained numeric is double")
    check(export_type(DateTime(timezone=True)) == "TIMESTAMPTZ", "timestamptz")
    check(export_type(DateTime(timezone=False)) == "TIMESTAMP", "timestamp")
    check(export_type(String(40)) == "VARCHAR", "varchar")
    check(export_type(BigInteger()) == "BIGINT", "bigint")
    check(export_type(Boolean()) == "BOOLEAN", "boolean")


def test_completeness() -> None:
    complete = Coverage(
        run_id="r1",
        run_status="completed",
        source_rows=100,
        ingested_rows=100,
        shard_count=2,
        completed_shards=2,
        failed_shards=0,
    )
    status, percent = completeness(complete, 100)
    check(status == "complete" and percent == 100.0, "complete table")

    failed = Coverage(
        run_id="r2",
        run_status="failed",
        source_rows=100,
        ingested_rows=100,
        shard_count=2,
        completed_shards=2,
        failed_shards=1,
    )
    check(completeness(failed, 100)[0] == "partial", "failed shard")

    missing_rows = Coverage(
        run_id="r3",
        run_status="completed",
        source_rows=100,
        ingested_rows=100,
        shard_count=2,
        completed_shards=2,
        failed_shards=0,
    )
    check(completeness(missing_rows, 90)[0] == "partial", "local row mismatch")

    empty = Coverage(
        run_id="r4",
        run_status="completed",
        source_rows=0,
        ingested_rows=0,
        shard_count=1,
        completed_shards=1,
        failed_shards=0,
    )
    check(completeness(empty, 0) == ("complete", 100.0), "empty table is complete")

    check(completeness(None, 10) == ("unknown", 0.0), "no bookkeeping is unknown")


def test_force_cleanup_is_bounded() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "manifest.json").write_text(
            json.dumps({"tables": {"accounts": {"file": "accounts.parquet"}}}),
            encoding="utf-8",
        )
        (root / "accounts.parquet").write_text("old", encoding="utf-8")
        (root / "keep.txt").write_text("keep", encoding="utf-8")
        clear_previous_snapshot(root)
        check(not (root / "accounts.parquet").exists(), "manifest file removed")
        check(not (root / "manifest.json").exists(), "old manifest removed")
        check((root / "keep.txt").exists(), "unrelated file survives")


def main() -> None:
    test_cli_defaults()
    test_compression_resolution()
    test_table_selection_spec()
    test_names_are_basenames()
    test_snapshot_naming()
    test_output_filenames()
    test_export_types()
    test_completeness()
    test_force_cleanup_is_bounded()
    print("Load export checks passed")


if __name__ == "__main__":
    main()
