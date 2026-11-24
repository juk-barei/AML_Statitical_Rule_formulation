# ruff: noqa: S608, RUF100
"""Load one frozen Parquet snapshot into the local PostgreSQL mirror.

This module is the Parquet source adapter for :mod:`src.scripts.etl.ingest`.
It hides four decisions behind a small interface:

1. Which tables a snapshot declares, and whether its manifest is trustworthy.
2. How a Parquet column becomes a PostgreSQL column, including the
   ``amount_exact`` reconstruction rule from ``load.py``.
3. How rows move from DuckDB to PostgreSQL without pandas or a whole-table
   materialisation.
4. How the existing ``_etl_runs`` / ``_etl_progress`` bookkeeping records the
   import, so ``verify_ingestion`` and the notebooks keep working.

The caller supplies an absolute snapshot directory. The manifest is required:
it carries the row counts, columns, and SHA-256 values this module verifies.

Run from the repo root::

    python -m src.scripts.etl.ingest \\
        --source parquet \\
        --source-path /absolute/path/to/phase1_raw_illicit_20261123T043155Z \\
        --schema illicit --dry-run

The local PostgreSQL credentials come from ``src/.env`` exactly as they do for
the online source. No connection string is printed.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from src.scripts.etl.ingest import (
    NULL_SENTINEL,
    ShardTask,
    build_ingestion_report,
    create_database_engine,
    create_post_ingest_indexes,
    create_progress_tables,
    drop_post_ingest_indexes,
    ensure_schema,
    finish_run,
    get_local_db_link,
    load_environment,
    parse_row_limits,
    qualified_name,
    quote_identifier,
    safe_error_message,
    seed_progress,
    validate_schema_name,
    write_progress,
    write_report,
)

INTERNAL_TABLES = frozenset({"_etl_progress", "_etl_runs", "pipeline_crawl_state"})
DUCKDB_MEMORY_LIMIT = "1GB"
DUCKDB_THREADS = 2
COPY_BATCH_SIZE = 50_000
FLOAT_TYPES = frozenset({"DOUBLE", "FLOAT", "REAL"})


@dataclass(frozen=True)
class ParquetColumn:
    """One column as DuckDB and the manifest describe it."""

    name: str
    duckdb_type: str


@dataclass(frozen=True)
class ParquetTable:
    """One table selected from a snapshot, ready to copy."""

    name: str
    path: Path
    manifest_rows: int
    planned_rows: int
    columns: tuple[ParquetColumn, ...]
    target_columns: tuple[tuple[str, str], ...]
    select_expressions: tuple[str, ...]
    sha256: str | None
    status: str


@dataclass(frozen=True)
class ParquetSnapshot:
    """A validated snapshot directory and its selected tables."""

    root: Path
    snapshot: str
    schema: str
    partial: bool
    created_at: str | None
    tables: tuple[ParquetTable, ...]


def sha256_file(path: Path) -> str:
    """Return the SHA-256 of one file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for block in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def describe_parquet(path: Path) -> tuple[ParquetColumn, ...]:
    """Return the DuckDB schema of one Parquet file."""
    with duckdb.connect() as connection:
        rows = connection.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]
        ).fetchall()
    return tuple(ParquetColumn(str(row[0]), str(row[1])) for row in rows)


def postgres_type(duckdb_type: str) -> str:
    """Map a DuckDB column type to a PostgreSQL column type.

    Only types that appear in the frozen snapshots are accepted. An unknown
    type fails loudly instead of silently becoming TEXT.
    """
    normalized = duckdb_type.strip().upper()
    if normalized.startswith("DECIMAL"):
        return normalized.replace("DECIMAL", "NUMERIC", 1)
    mappings = {
        "VARCHAR": "TEXT",
        "TEXT": "TEXT",
        "BIGINT": "BIGINT",
        "INTEGER": "INTEGER",
        "SMALLINT": "SMALLINT",
        "DOUBLE": "DOUBLE PRECISION",
        "FLOAT": "REAL",
        "REAL": "REAL",
        "BOOLEAN": "BOOLEAN",
        "DATE": "DATE",
        "TIME": "TIME",
        "TIMESTAMP": "TIMESTAMP",
        "TIMESTAMP WITH TIME ZONE": "TIMESTAMPTZ",
        "TIMESTAMPTZ": "TIMESTAMPTZ",
        "BLOB": "BYTEA",
    }
    if normalized in mappings:
        return mappings[normalized]
    raise ValueError(f"Unsupported Parquet type: {duckdb_type!r}.")


def build_target_columns(
    columns: Sequence[ParquetColumn],
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """Return target columns and DuckDB select expressions.

    ``load.py`` writes uncapped PostgreSQL numerics as a ``DOUBLE`` plus a
    ``<name>_exact`` VARCHAR. The mirror column is NUMERIC, so the exact text is
    selected back into the original name and the helper column is omitted.
    """
    types_by_name = {column.name: column.duckdb_type for column in columns}
    exact_bases = {
        column.name[: -len("_exact")]
        for column in columns
        if column.name.endswith("_exact")
        and column.name[: -len("_exact")] in types_by_name
        and types_by_name[column.name[: -len("_exact")]].upper() in FLOAT_TYPES
        and column.duckdb_type.upper() == "VARCHAR"
    }

    target_columns: list[tuple[str, str]] = []
    select_expressions: list[str] = []
    for column in columns:
        if column.name in exact_bases:
            continue
        if column.name.endswith("_exact") and column.name[: -len("_exact")] in exact_bases:
            base_name = column.name[: -len("_exact")]
            target_columns.append((base_name, "NUMERIC"))
            select_expressions.append(
                f"{quote_identifier(column.name)} AS {quote_identifier(base_name)}"
            )
            continue
        target_columns.append((column.name, postgres_type(column.duckdb_type)))
        select_expressions.append(quote_identifier(column.name))
    return tuple(target_columns), tuple(select_expressions)


def parse_table_spec(spec: str) -> tuple[str, ...] | None:
    """Return ``None`` for all tables, otherwise the requested names."""
    if spec.strip().lower() == "all":
        return None
    tables = tuple(name.strip() for name in spec.split(",") if name.strip())
    if not tables:
        raise ValueError("--tables must name at least one table or be 'all'.")
    return tables


def load_parquet_snapshot(
    source_path: str | Path,
    *,
    target_schema: str,
    tables_spec: str = "all",
    row_limits: dict[str, int] | None = None,
    verify_hashes: bool = True,
    allow_partial: bool = False,
    allow_schema_mismatch: bool = False,
) -> ParquetSnapshot:
    """Validate a frozen snapshot and return its selected tables.

    ``source_path`` must be absolute. This is deliberate: a relative path
    silently changes meaning when the working directory changes.
    """
    path = Path(source_path).expanduser()
    if not path.is_absolute():
        raise ValueError("--source-path must be an absolute path.")
    root = path.resolve()
    if not root.is_dir():
        raise ValueError(f"Parquet snapshot directory does not exist: {root}")

    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"manifest.json is missing from {root}.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if str(manifest.get("format", "")).lower() != "parquet":
        raise ValueError("The snapshot manifest is not a Parquet export.")
    manifest_schema = str(manifest.get("schema", ""))
    if manifest_schema != target_schema and not allow_schema_mismatch:
        raise ValueError(
            f"Snapshot schema {manifest_schema!r} does not match --schema "
            f"{target_schema!r}. Pass --allow-schema-mismatch only for a test load."
        )

    manifest_is_partial = bool(manifest.get("partial"))
    if manifest_is_partial and not allow_partial:
        raise ValueError(
            "The snapshot manifest is marked partial. Finish ingestion or pass "
            "--allow-partial explicitly."
        )

    records = manifest.get("tables")
    if not isinstance(records, dict) or not records:
        raise ValueError("The manifest has no tables.")

    requested = parse_table_spec(tables_spec)
    available = tuple(
        sorted(name for name in records if name not in INTERNAL_TABLES)
    )
    if requested is None:
        selected = available
    else:
        missing = [name for name in requested if name not in available]
        if missing:
            raise ValueError(
                f"Unknown snapshot table(s): {missing}. Available: {list(available)}"
            )
        selected = requested

    row_limits = row_limits or {}
    tables: list[ParquetTable] = []
    for table_name in selected:
        record = records[table_name]
        if not isinstance(record, dict):
            raise TypeError(f"Invalid manifest entry for {table_name!r}.")
        status = str(record.get("status", "unknown"))
        if status != "complete" and not allow_partial:
            raise ValueError(
                f"{table_name!r} is {status!r} in the manifest. Pass "
                "--allow-partial to load it anyway."
            )

        file_name = str(record.get("file", ""))
        if not file_name or Path(file_name).name != file_name:
            raise ValueError(f"Invalid file name for {table_name!r}: {file_name!r}")
        table_path = (root / file_name).resolve()
        if root not in table_path.parents:
            raise ValueError(f"File escapes the snapshot directory: {file_name!r}")
        if not table_path.is_file():
            raise ValueError(f"Missing Parquet file: {table_path}")

        manifest_rows = int(record.get("rows", 0))
        table_limit = row_limits.get(table_name, row_limits.get("all"))
        planned_rows = (
            min(manifest_rows, table_limit)
            if table_limit is not None
            else manifest_rows
        )
        if planned_rows < 0:
            raise ValueError(f"Row limit for {table_name!r} must be >= 0.")

        expected_sha256 = record.get("sha256")
        if verify_hashes:
            if not expected_sha256:
                raise ValueError(f"{table_name!r} has no SHA-256 in the manifest.")
            actual_sha256 = sha256_file(table_path)
            if actual_sha256 != expected_sha256:
                raise ValueError(
                    f"SHA-256 mismatch for {table_name!r}: "
                    f"manifest={expected_sha256}, file={actual_sha256}"
                )

        columns = describe_parquet(table_path)
        manifest_columns = tuple(str(name) for name in record.get("columns", []))
        actual_columns = tuple(column.name for column in columns)
        if manifest_columns != actual_columns:
            raise ValueError(
                f"Column mismatch for {table_name!r}: "
                f"manifest={manifest_columns}, file={actual_columns}"
            )

        target_columns, select_expressions = build_target_columns(columns)
        tables.append(
            ParquetTable(
                name=table_name,
                path=table_path,
                manifest_rows=manifest_rows,
                planned_rows=planned_rows,
                columns=columns,
                target_columns=target_columns,
                select_expressions=select_expressions,
                sha256=str(expected_sha256) if expected_sha256 else None,
                status=status,
            )
        )

    return ParquetSnapshot(
        root=root,
        snapshot=str(manifest.get("snapshot") or root.name),
        schema=manifest_schema,
        partial=manifest_is_partial,
        created_at=(
            str(manifest["created_at"]) if manifest.get("created_at") else None
        ),
        tables=tuple(tables),
    )


def create_target_table(
    local_engine: Engine,
    table: ParquetTable,
) -> None:
    """Create or reset one target table with the mapped column types."""
    inspector = inspect(local_engine)
    schema = str(local_engine.get_execution_options()["capstone_schema"])
    table_exists = inspector.has_table(table.name, schema=schema)
    target_names = [name for name, _type in table.target_columns]

    if table_exists:
        existing_names = [
            column["name"]
            for column in inspector.get_columns(table.name, schema=schema)
        ]
        if existing_names == target_names:
            with local_engine.begin() as connection:
                # pi-lens-ignore: python-sql-injection -- identifiers are quoted
                connection.execute(
                    text(f"TRUNCATE TABLE {qualified_name(local_engine, table.name)}")
                )
            return
        with local_engine.begin() as connection:
            # pi-lens-ignore: python-sql-injection -- identifiers are quoted
            connection.execute(
                text(
                    f"DROP TABLE IF EXISTS "
                    f"{qualified_name(local_engine, table.name)} CASCADE"
                )
            )

    definitions = ", ".join(
        f"{quote_identifier(name)} {column_type}"
        for name, column_type in table.target_columns
    )
    with local_engine.begin() as connection:
        # pi-lens-ignore: python-sql-injection -- identifiers are quoted
        connection.execute(
            text(
                f"CREATE TABLE {qualified_name(local_engine, table.name)} "
                f"({definitions})"
            )
        )


def copy_value(value: Any) -> Any:
    """Return the CSV field PostgreSQL COPY expects for one value."""
    if value is None:
        return NULL_SENTINEL
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, bytes):
        return value.hex()
    return value


def copy_parquet_table(
    local_engine: Engine,
    table: ParquetTable,
    *,
    batch_size: int = COPY_BATCH_SIZE,
) -> int:
    """Stream one Parquet table into PostgreSQL through ``COPY FROM STDIN``."""
    select_list = ", ".join(table.select_expressions)
    query = (  # pi-lens-ignore: python-sql-injection -- identifiers are quoted; path is bound
        f"SELECT {select_list} FROM read_parquet(?)"
    )
    if table.planned_rows < table.manifest_rows:
        query += f" LIMIT {int(table.planned_rows)}"

    target_names = ", ".join(
        quote_identifier(name) for name, _type in table.target_columns
    )
    copy_sql = (
        f"COPY {qualified_name(local_engine, table.name)} ({target_names}) "
        f"FROM STDIN WITH (FORMAT CSV, NULL '{NULL_SENTINEL}')"
    )

    loaded_rows = 0
    raw_connection = local_engine.raw_connection()
    postgres_cursor = raw_connection.cursor()
    try:
        with (
            tempfile.TemporaryDirectory(prefix="parquet_ingest_") as temp_dir,
            duckdb.connect() as duckdb_connection,
        ):
            duckdb_connection.execute(
                f"SET memory_limit = '{DUCKDB_MEMORY_LIMIT}'"
            )
            duckdb_connection.execute(f"SET threads = {DUCKDB_THREADS}")
            duckdb_connection.execute("SET temp_directory = ?", [temp_dir])
            # pi-lens-ignore: python-sql-injection -- select list is quoted; path is bound
            cursor = duckdb_connection.execute(query, [str(table.path)])
            with postgres_cursor.copy(copy_sql) as copy:
                while True:
                    rows = cursor.fetchmany(batch_size)
                    if not rows:
                        break
                    buffer = io.StringIO()
                    writer = csv.writer(buffer, lineterminator="\n")
                    for row in rows:
                        writer.writerow([copy_value(value) for value in row])
                    copy.write(buffer.getvalue())
                    loaded_rows += len(rows)
        raw_connection.commit()
    except Exception:
        raw_connection.rollback()
        raise
    finally:
        postgres_cursor.close()
        raw_connection.close()

    if loaded_rows != table.planned_rows:
        raise RuntimeError(
            f"{table.name!r} loaded {loaded_rows:,} rows, "
            f"expected {table.planned_rows:,}."
        )
    return loaded_rows


def latest_parquet_run_id(local_engine: Engine, snapshot_name: str) -> str | None:
    """Return the newest unfinished Parquet run for this snapshot."""
    base_run_id = f"parquet_{snapshot_name}"
    query = text(
        f"SELECT run_id FROM {qualified_name(local_engine, '_etl_runs')} "  # pi-lens-ignore: python-sql-injection -- identifiers are quoted
        "WHERE status <> 'completed' AND starts_with(run_id, :base_run_id) "
        "ORDER BY started_at DESC LIMIT 1"
    )
    with local_engine.connect() as connection:
        # pi-lens-ignore: python-sql-injection -- identifiers are quoted; value is bound
        return connection.execute(
            query, {"base_run_id": base_run_id}
        ).scalar_one_or_none()


def completed_tables(local_engine: Engine, run_id: str) -> set[str]:
    """Return tables already completed in one run."""
    query = text(
        f"SELECT table_name FROM {qualified_name(local_engine, '_etl_progress')} "  # pi-lens-ignore: python-sql-injection -- identifiers are quoted
        "WHERE run_id = :run_id AND status = 'completed'"
    )
    with local_engine.connect() as connection:
        return {
            str(row[0])
            for row in connection.execute(  # pi-lens-ignore: python-sql-injection -- identifiers are quoted; value is bound
                query, {"run_id": run_id}
            ).all()
        }


def truncate_table(local_engine: Engine, table_name: str) -> None:
    """Remove a failed table's rows so the next run starts clean."""
    with local_engine.begin() as connection:
        # pi-lens-ignore: python-sql-injection -- identifiers are quoted
        connection.execute(
            text(f"TRUNCATE TABLE {qualified_name(local_engine, table_name)}")
        )


def print_plan(snapshot: ParquetSnapshot) -> None:
    """Print the snapshot plan without touching PostgreSQL."""
    print(f"Source: {snapshot.root}")
    print(f"Snapshot: {snapshot.snapshot} | schema: {snapshot.schema}")
    print(f"Created: {snapshot.created_at or 'unknown'} | partial: {snapshot.partial}")
    print(
        f"{'table':<24} {'rows':>12} {'planned':>12} "
        f"{'columns':>8} file"
    )
    for table in snapshot.tables:
        print(
            f"{table.name:<24} {table.manifest_rows:>12,} "
            f"{table.planned_rows:>12,} {len(table.columns):>8} "
            f"{table.path.name}"
        )
    print("Dry run only; no local tables were changed.")


def run_parquet_ingest(args: Any) -> int:
    """Import an absolute Parquet snapshot into the local mirror."""
    load_environment()
    target_schema = validate_schema_name(args.schema)
    if not args.source_path:
        raise ValueError("--source-path is required when --source parquet is used.")

    row_limits = parse_row_limits(args.row_limits)
    snapshot = load_parquet_snapshot(
        args.source_path,
        target_schema=target_schema,
        tables_spec=args.tables,
        row_limits=row_limits,
        verify_hashes=not args.skip_hash,
        allow_partial=args.allow_partial,
        allow_schema_mismatch=args.allow_schema_mismatch,
    )

    if args.dry_run:
        print_plan(snapshot)
        return 0

    local_engine = create_database_engine(
        get_local_db_link(), is_source=False, schema=target_schema
    )
    try:
        ensure_schema(local_engine, target_schema)
        create_progress_tables(local_engine)

        existing_run_id = (
            latest_parquet_run_id(local_engine, snapshot.snapshot)
            if args.resume
            else None
        )
        resume = existing_run_id is not None
        run_id = existing_run_id or (
            f"parquet_{snapshot.snapshot}_"
            f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        )

        print(f"Run id: {run_id}")
        print(
            f"Source: parquet | snapshot: {snapshot.snapshot} | "
            f"target schema: {target_schema}"
        )
        print(
            f"Tables: {', '.join(table.name for table in snapshot.tables)} | "
            f"batch size: {max(1, args.batch_size):,}"
        )
        if resume:
            print("Resuming the latest unfinished Parquet run.")

        tasks = tuple(
            ShardTask(
                run_id=run_id,
                table_name=table.name,
                target_name=table.name,
                shard_index=0,
                shard_count=1,
                where_sql="",
                where_params={},
                source_rows=table.planned_rows,
                columns=tuple(name for name, _type in table.target_columns),
                order_columns=(),
                batch_size=max(1, args.batch_size),
                keyset=False,
            )
            for table in snapshot.tables
        )
        seed_progress(
            local_engine,
            run_id,
            tasks,
            workers=1,
            batch_size=max(1, args.batch_size),
            shards_per_table=1,
            tables=[table.name for table in snapshot.tables],
            total_source_rows=sum(task.source_rows for task in tasks),
        )

        finished = completed_tables(local_engine, run_id) if resume else set()
        tables_to_load = [
            table for table in snapshot.tables if table.name not in finished
        ]
        if not args.skip_indexes:
            drop_post_ingest_indexes(
                local_engine, [table.name for table in tables_to_load]
            )

        failures = 0
        for table in snapshot.tables:
            if table.name in finished:
                print(f"{table.name}: completed, skipping")
                continue

            task = next(task for task in tasks if task.table_name == table.name)
            started_at = datetime.now(UTC)
            start_time = time.perf_counter()
            try:
                create_target_table(local_engine, table)
                write_progress(
                    local_engine,
                    task,
                    ingested_rows=0,
                    status="running",
                    started_at=started_at,
                    start_time=start_time,
                )
                loaded_rows = copy_parquet_table(
                    local_engine, table, batch_size=max(1, args.batch_size)
                )
                write_progress(
                    local_engine,
                    task,
                    ingested_rows=loaded_rows,
                    status="completed",
                    started_at=started_at,
                    start_time=start_time,
                )
                print(
                    f"{table.name}: {loaded_rows:,} rows in "
                    f"{time.perf_counter() - start_time:.1f}s"
                )
            except Exception as error:  # noqa: BLE001 - one table must not stop the rest
                failures += 1
                message = safe_error_message(error)
                try:
                    truncate_table(local_engine, table.name)
                except Exception as cleanup_error:  # noqa: BLE001 - table may not exist yet
                    print(
                        f"Could not clear {table.name}: "
                        f"{safe_error_message(cleanup_error)}"
                    )
                write_progress(
                    local_engine,
                    task,
                    ingested_rows=0,
                    status="failed",
                    started_at=started_at,
                    start_time=start_time,
                    error_message=message,
                )
                print(f"FAILED {table.name}: {message}")

        report = build_ingestion_report(
            local_engine,
            run_id,
            tasks,
            tables=[table.name for table in snapshot.tables],
        )
        report_path = write_report(
            report, run_id, label=f"parquet_{target_schema}"
        )
        failed = report["status"].isin(["failed", "partial", "pending"])
        run_status = "failed" if failed.any() else "completed"
        finish_run(
            local_engine,
            run_id,
            status=run_status,
            total_ingested_rows=int(report["ingested_rows"].sum()),
            error_message=(
                "Some tables failed or were incomplete." if failed.any() else None
            ),
        )
        if run_status == "completed" and not args.skip_indexes:
            create_post_ingest_indexes(
                local_engine, [table.name for table in snapshot.tables]
            )

        print("\nFinal Parquet ingestion report")
        print(report.to_string(index=False))
        print(f"\nReport written to: {report_path}")
        return 0 if run_status == "completed" and failures == 0 else 1
    finally:
        local_engine.dispose()
