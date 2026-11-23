"""Export a frozen, manifest-backed snapshot from the local PostgreSQL mirror.

The mirror is read-only for this module. PostgreSQL streams one table at a time
via ``COPY ... TO STDOUT``; DuckDB converts the stream to Parquet or writes the
CSV directly. No table is loaded into pandas.

Run from the repo root:

    python -m src.scripts.etl.load --schema illicit --tables all \
        --out-dir outputs/etl/export/illicit_20261123 --name illicit_raw

    python -m src.scripts.etl.load --schema licit --tables transactions \
        --out-dir /shared/handoff/h1_h3 --name licit_transactions \
        --format csv --compression gzip --allow-large-csv

Use ``--dry-run`` first: it prints the plan and row counts without writing.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import shutil
import sys
import tomllib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from psycopg import sql
from sqlalchemy import Engine, MetaData, Table, case, func, inspect, select
from sqlalchemy.sql.sqltypes import DateTime, Numeric

from src.scripts.config import ROOT
from src.scripts.etl.ingest import (
    get_local_engine,
    load_environment,
    safe_error_message,
    validate_schema_name,
)

INTERNAL_TABLES = frozenset({"_etl_progress", "_etl_runs", "pipeline_crawl_state"})
PARQUET_COMPRESSIONS = frozenset({"zstd", "snappy", "gzip", "none"})
CSV_COMPRESSIONS = frozenset({"gzip", "none"})
LARGE_CSV_ROW_LIMIT = 1_000_000
NULL_MARKER = r"\N"
COLUMN_SEPARATOR = ", "


@dataclass(frozen=True)
class ColumnInfo:
    """One exported column and the type used when writing the export."""

    name: str
    source_name: str
    sql_type: str
    export_type: str
    nullable: bool
    derived_from: str | None = None


@dataclass(frozen=True)
class Coverage:
    """Latest ingestion bookkeeping for one table."""

    run_id: str
    run_status: str
    source_rows: int
    ingested_rows: int
    shard_count: int
    completed_shards: int
    failed_shards: int


@dataclass(frozen=True)
class TablePlan:
    """Everything needed to export one table."""

    table: str
    filename: str
    columns: tuple[ColumnInfo, ...]
    dropped_columns: tuple[str, ...]
    local_rows: int
    coverage: Coverage | None
    status: str
    coverage_percent: float


@dataclass(frozen=True)
class ExportPlan:
    """A validated export plan for one snapshot directory."""

    snapshot: str
    phase: int
    stage: str
    schema: str
    out_dir: Path
    file_format: str
    compression: str
    tables: tuple[TablePlan, ...]

    @property
    def partial(self) -> bool:
        return any(table.status != "complete" for table in self.tables)


def utc_stamp() -> str:
    """Return a filesystem-safe UTC timestamp."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def utc_iso() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def project_phase() -> int:
    """Read the project phase from ``[tool.capstone]`` in pyproject.toml."""
    path = ROOT / "pyproject.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError(f"Project metadata not found: {path}") from error
    phase = data.get("tool", {}).get("capstone", {}).get("phase")
    if isinstance(phase, bool) or not isinstance(phase, int) or phase < 1:
        raise RuntimeError(
            "pyproject.toml must define a positive integer [tool.capstone].phase."
        )
    return phase


def snapshot_name(phase: int, stage: str, schema: str, stamp: str | None = None) -> str:
    """Return ``phase<N>_<stage>_<schema>_<UTC>``."""
    return f"phase{phase}_{stage}_{schema}_{stamp or utc_stamp()}"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse export arguments."""
    parser = argparse.ArgumentParser(
        description="Export a frozen snapshot from the local PostgreSQL mirror.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--schema",
        required=True,
        help="Source schema in the local mirror, e.g. illicit or licit.",
    )
    parser.add_argument(
        "--stage",
        choices=("raw", "transformed"),
        default="raw",
        help="Data stage recorded in the snapshot name and manifest. Default: raw.",
    )
    parser.add_argument(
        "--tables",
        default="all",
        help="Comma-separated table names, or 'all' (default). Internal tables are excluded.",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help=(
            "Snapshot directory. Default: "
            "outputs/etl/export/phase<phase>_<stage>_<schema>_<UTC>.\n"
            "An external/mounted path is allowed; it is recorded in the manifest."
        ),
    )
    parser.add_argument(
        "--name",
        default="",
        help=(
            "Output basename. One table: exact file name (extension optional).\n"
            "Multiple tables: prefix, producing <name>__<table>.<ext>.\n"
            "Default: phase<phase>_<stage>_<schema>_<UTC>__<table>."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("parquet", "csv"),
        default="parquet",
        help="Export format. Default: parquet.",
    )
    parser.add_argument(
        "--compression",
        choices=("zstd", "snappy", "gzip", "none"),
        default=None,
        help=(
            "Compression. Parquet: zstd|snappy|gzip|none (default zstd).\n"
            "CSV: gzip|none (default gzip)."
        ),
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Export tables whose ingestion bookkeeping is incomplete; the manifest marks them partial.",
    )
    parser.add_argument(
        "--allow-large-csv",
        action="store_true",
        help=f"Permit CSV exports above {LARGE_CSV_ROW_LIMIT:,} rows.",
    )
    parser.add_argument(
        "--keep-hex",
        action="store_true",
        help="Keep hex_address. Default: drop it from every exported table.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing snapshot in --out-dir. Default: refuse.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan and row counts without writing files.",
    )
    return parser.parse_args(argv)


def resolve_compression(file_format: str, compression: str | None) -> str:
    """Return a valid compression for the selected format."""
    if compression is None:
        return "zstd" if file_format == "parquet" else "gzip"
    if file_format == "parquet" and compression not in PARQUET_COMPRESSIONS:
        raise ValueError(
            f"Unsupported Parquet compression: {compression!r}. "
            f"Use one of {sorted(PARQUET_COMPRESSIONS)}."
        )
    if file_format == "csv" and compression not in CSV_COMPRESSIONS:
        raise ValueError(
            f"Unsupported CSV compression: {compression!r}. "
            f"Use one of {sorted(CSV_COMPRESSIONS)}."
        )
    return compression


def parse_tables(spec: str) -> tuple[str, ...] | None:
    """Parse ``--tables``; return None for all tables."""
    names = [part.strip() for part in spec.split(",") if part.strip()]
    if not names:
        raise ValueError("--tables must name at least one table or be 'all'.")
    if "all" in names:
        if len(names) != 1:
            raise ValueError("'all' cannot be combined with explicit table names.")
        return None
    return tuple(dict.fromkeys(names))


def safe_basename(value: str) -> str:
    """Reject a basename that could escape the snapshot directory."""
    if not value or value in {".", ".."}:
        raise ValueError("--name must not be empty, '.', or '..'.")
    if "/" in value or "\\" in value or Path(value).name != value:
        raise ValueError("--name must be a basename, not a path.")
    return value


def output_extension(file_format: str, compression: str) -> str:
    """Return the file extension for a format/compression pair."""
    if file_format == "parquet":
        return ".parquet"
    return ".csv.gz" if compression == "gzip" else ".csv"


def output_filenames(
    schema: str,
    tables: Sequence[str],
    name: str,
    file_format: str,
    compression: str,
    *,
    default_prefix: str,
) -> dict[str, str]:
    """Return one basename per table, rejecting paths and wrong extensions."""
    extension = output_extension(file_format, compression)
    known = (".parquet", ".csv.gz", ".csv", ".gz")
    if name:
        name = safe_basename(name)
        if len(tables) > 1 and name.endswith(known):
            raise ValueError(
                "A multi-table --name must be a prefix without a file extension."
            )
        if len(tables) == 1 and name.endswith(
            tuple(item for item in known if item != extension)
        ):
            raise ValueError(
                f"--name extension does not match --format {file_format!r}."
            )
    result: dict[str, str] = {}
    for table in tables:
        if len(tables) == 1:
            base = name or f"{default_prefix}__{table}"
        else:
            base = f"{name or default_prefix}__{table}"
        if not base.endswith(extension):
            base += extension
        result[table] = base
    return result


def export_type(column_type: Any) -> str:
    """Map a SQLAlchemy/PostgreSQL type to an explicit DuckDB CSV type."""
    if isinstance(column_type, Numeric):
        precision = getattr(column_type, "precision", None)
        scale = getattr(column_type, "scale", None) or 0
        if precision:
            return f"DECIMAL({precision}, {scale})"
        # DuckDB cannot represent PostgreSQL's arbitrary-precision numeric.
        return "DOUBLE"
    if isinstance(column_type, DateTime):
        return "TIMESTAMPTZ" if column_type.timezone else "TIMESTAMP"
    name = str(column_type).upper()
    if name.startswith(("VARCHAR", "CHAR", "TEXT")):
        return "VARCHAR"
    if name.startswith("BIGINT"):
        return "BIGINT"
    if name.startswith("SMALLINT"):
        return "SMALLINT"
    if name.startswith("INTEGER"):
        return "INTEGER"
    if name.startswith("BOOLEAN"):
        return "BOOLEAN"
    if name.startswith("DOUBLE"):
        return "DOUBLE"
    if name.startswith("REAL"):
        return "REAL"
    if name.startswith("DATE"):
        return "DATE"
    if name.startswith("TIMESTAMP"):
        return "TIMESTAMP"
    return "VARCHAR"


def read_columns(
    engine: Engine,
    schema: str,
    table: str,
    *,
    keep_hex: bool,
) -> tuple[tuple[ColumnInfo, ...], tuple[str, ...]]:
    """Return exportable columns and the names dropped by the data-hygiene rule."""
    columns: list[ColumnInfo] = []
    dropped: list[str] = []
    for column in inspect(engine).get_columns(table, schema=schema):
        name = str(column["name"])
        if name == "hex_address" and not keep_hex:
            dropped.append(name)
            continue
        column_type = column["type"]
        sql_type = str(column_type)
        nullable = bool(column["nullable"])
        mapped_type = export_type(column_type)
        columns.append(
            ColumnInfo(
                name=name,
                source_name=name,
                sql_type=sql_type,
                export_type=mapped_type,
                nullable=nullable,
            )
        )
        if isinstance(column_type, Numeric) and not getattr(
            column_type, "precision", None
        ):
            columns.append(
                ColumnInfo(
                    name=f"{name}_exact",
                    source_name=name,
                    sql_type=sql_type,
                    export_type="VARCHAR",
                    nullable=nullable,
                    derived_from=name,
                )
            )
    if not columns:
        raise ValueError(f"{schema}.{table} has no exportable columns.")
    return tuple(columns), tuple(dropped)


def table_row_count(engine: Engine, schema: str, table: str) -> int:
    """Count a table exactly, in SQL."""
    source = Table(table, MetaData(), schema=schema, autoload_with=engine)
    with engine.connect() as connection:
        return int(
            connection.execute(select(func.count()).select_from(source)).scalar_one()
        )


def select_tables(engine: Engine, schema: str, spec: str) -> tuple[str, ...]:
    """Validate and expand the requested table list."""
    available = set(inspect(engine).get_table_names(schema=schema))
    requested = parse_tables(spec)
    if requested is None:
        selected = tuple(sorted(available - INTERNAL_TABLES))
    else:
        for table in requested:
            if table in INTERNAL_TABLES:
                raise ValueError(f"Internal table {table!r} is not exported.")
            if table not in available:
                raise ValueError(
                    f"Table {table!r} does not exist in schema {schema!r}."
                )
        selected = requested
    if not selected:
        raise ValueError(f"No exportable tables found in schema {schema!r}.")
    return selected


def load_coverage(
    engine: Engine,
    schema: str,
    tables: Sequence[str],
) -> dict[str, Coverage]:
    """Return the latest ingestion bookkeeping for each table.

    A table may not appear in the latest run; the newest run that includes it
    is the correct provenance. The run status is recorded but table
    completeness is decided from shard completion and row counts.
    """
    inspector = inspect(engine)
    if not (
        inspector.has_table("_etl_progress", schema=schema)
        and inspector.has_table("_etl_runs", schema=schema)
    ):
        return {}
    progress = Table("_etl_progress", MetaData(), schema=schema, autoload_with=engine)
    runs = Table("_etl_runs", MetaData(), schema=schema, autoload_with=engine)
    completed = func.sum(case((progress.c.status == "completed", 1), else_=0))
    failed = func.sum(case((progress.c.status == "failed", 1), else_=0))
    with engine.connect() as connection:
        rows = (
            connection.execute(
                select(
                    progress.c.table_name,
                    progress.c.run_id,
                    runs.c.status.label("run_status"),
                    func.sum(progress.c.source_rows).label("source_rows"),
                    func.sum(progress.c.ingested_rows).label("ingested_rows"),
                    func.count().label("shard_count"),
                    completed.label("completed_shards"),
                    failed.label("failed_shards"),
                    runs.c.started_at,
                )
                .select_from(progress.join(runs, progress.c.run_id == runs.c.run_id))
                .where(progress.c.table_name.in_(tables))
                .group_by(
                    progress.c.table_name,
                    progress.c.run_id,
                    runs.c.status,
                    runs.c.started_at,
                )
                .order_by(progress.c.table_name, runs.c.started_at.desc())
            )
            .mappings()
            .all()
        )
    result: dict[str, Coverage] = {}
    for row in rows:
        table = str(row["table_name"])
        if table in result:
            continue
        result[table] = Coverage(
            run_id=str(row["run_id"]),
            run_status=str(row["run_status"]),
            source_rows=int(row["source_rows"] or 0),
            ingested_rows=int(row["ingested_rows"] or 0),
            shard_count=int(row["shard_count"] or 0),
            completed_shards=int(row["completed_shards"] or 0),
            failed_shards=int(row["failed_shards"] or 0),
        )
    return result


def completeness(
    coverage: Coverage | None,
    local_rows: int,
) -> tuple[str, float]:
    """Return (status, coverage percent) for one table."""
    if coverage is None or coverage.shard_count == 0:
        return "unknown", 0.0
    percent = (
        100.0
        if coverage.source_rows <= 0
        else 100.0 * coverage.ingested_rows / coverage.source_rows
    )
    complete = (
        coverage.failed_shards == 0
        and coverage.completed_shards == coverage.shard_count
        and coverage.ingested_rows >= coverage.source_rows
        and local_rows == coverage.ingested_rows
    )
    return ("complete" if complete else "partial"), percent


def default_out_dir(phase: int, stage: str, schema: str, stamp: str) -> Path:
    """Return the default snapshot directory for a phase/stage/schema."""
    return (
        ROOT
        / "outputs"
        / "etl"
        / "export"
        / snapshot_name(phase, stage, schema, stamp)
    )


def build_plan(engine: Engine, args: argparse.Namespace) -> ExportPlan:
    """Validate the CLI request and build an immutable export plan."""
    schema = validate_schema_name(args.schema)
    if not inspect(engine).has_schema(schema):
        raise ValueError(f"Schema {schema!r} does not exist in the local mirror.")
    phase = project_phase()
    stage = str(args.stage)
    stamp = utc_stamp()
    snapshot = snapshot_name(phase, stage, schema, stamp)
    file_format = str(args.format)
    compression = resolve_compression(file_format, args.compression)
    tables = select_tables(engine, schema, args.tables)
    filenames = output_filenames(
        schema,
        tables,
        str(args.name or ""),
        file_format,
        compression,
        default_prefix=snapshot,
    )
    coverage_by_table = load_coverage(engine, schema, tables)
    plans: list[TablePlan] = []
    for table in tables:
        columns, dropped = read_columns(
            engine,
            schema,
            table,
            keep_hex=bool(args.keep_hex),
        )
        local_rows = table_row_count(engine, schema, table)
        coverage = coverage_by_table.get(table)
        status, percent = completeness(coverage, local_rows)
        plans.append(
            TablePlan(
                table=table,
                filename=filenames[table],
                columns=columns,
                dropped_columns=dropped,
                local_rows=local_rows,
                coverage=coverage,
                status=status,
                coverage_percent=percent,
            )
        )
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else default_out_dir(phase, stage, schema, stamp)
    )
    return ExportPlan(
        snapshot=snapshot,
        phase=phase,
        stage=stage,
        schema=schema,
        out_dir=out_dir.resolve(),
        file_format=file_format,
        compression=compression,
        tables=tuple(plans),
    )


def copy_table_to_csv(
    engine: Engine,
    schema: str,
    table: str,
    columns: Sequence[ColumnInfo],
    destination: Path,
    *,
    gzip_output: bool,
) -> None:
    """Stream one table from PostgreSQL to CSV without pandas."""
    selected = sql.SQL(COLUMN_SEPARATOR).join(
        (
            sql.Identifier(column.name)
            if column.name == column.source_name
            else sql.SQL("{source} AS {alias}").format(
                source=sql.Identifier(column.source_name),
                alias=sql.Identifier(column.name),
            )
        )
        for column in columns
    )
    statement = sql.SQL(
        "COPY (SELECT {columns} FROM {schema}.{table}) TO STDOUT "
        "WITH (FORMAT csv, HEADER true, NULL {null_marker})"
    ).format(
        columns=selected,
        schema=sql.Identifier(schema),
        table=sql.Identifier(table),
        null_marker=sql.Literal(NULL_MARKER),
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if gzip_output else open
    with engine.connect() as connection:
        raw_connection = connection.connection.driver_connection
        if raw_connection is None:
            raise RuntimeError("The local database connection is not available.")
        with (
            raw_connection.cursor() as cursor,
            cursor.copy(statement) as copy,
            opener(destination, "wb") as handle,
        ):
            for chunk in copy:
                handle.write(chunk)


def column_types(columns: Sequence[ColumnInfo]) -> dict[str, str]:
    """Return the DuckDB column map for an explicit CSV read."""
    return {column.name: column.export_type for column in columns}


def count_csv(path: Path, columns: Sequence[ColumnInfo], *, gzip_input: bool) -> int:
    """Count rows in a CSV export through DuckDB."""
    connection = duckdb.connect()
    try:
        if gzip_input:
            connection.execute("SET autoinstall_known_extensions = false")
            connection.execute("SET autoload_known_extensions = false")
        compression = "gzip" if gzip_input else "auto"
        row = connection.execute(
            "SELECT count(*) FROM read_csv(?, header = true, columns = ?, "
            "nullstr = ?, compression = ?)",
            [str(path), column_types(columns), NULL_MARKER, compression],
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        connection.close()


def write_parquet(
    csv_path: Path,
    destination: Path,
    columns: Sequence[ColumnInfo],
    compression: str,
    temp_directory: Path,
) -> int:
    """Convert a typed CSV file to Parquet with DuckDB and verify its row count."""
    connection = duckdb.connect()
    try:
        connection.execute("SET memory_limit = ?", ["1GB"])
        connection.execute("SET temp_directory = ?", [str(temp_directory)])
        connection.execute("SET threads = ?", [2])
        parquet_compression = (
            "UNCOMPRESSED" if compression == "none" else compression.upper()
        )
        connection.execute(
            "COPY (SELECT * FROM read_csv(?, header = true, columns = ?, "
            "nullstr = ?)) TO ? (FORMAT PARQUET, COMPRESSION ?)",
            [
                str(csv_path),
                column_types(columns),
                NULL_MARKER,
                str(destination),
                parquet_compression,
            ],
        )
        row = connection.execute(
            "SELECT count(*) FROM read_parquet(?)", [str(destination)]
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        connection.close()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_table(
    engine: Engine,
    plan: ExportPlan,
    table: TablePlan,
    temp_root: Path,
) -> dict[str, Any]:
    """Export one table to the snapshot directory and return its manifest record."""
    destination = plan.out_dir / table.filename
    work_dir = temp_root / table.table
    work_dir.mkdir(parents=True)
    output = work_dir / table.filename
    try:
        if plan.file_format == "parquet":
            csv_path = work_dir / f"{table.table}.csv"
            copy_table_to_csv(
                engine,
                plan.schema,
                table.table,
                table.columns,
                csv_path,
                gzip_output=False,
            )
            exported_rows = write_parquet(
                csv_path,
                output,
                table.columns,
                plan.compression,
                work_dir,
            )
        else:
            copy_table_to_csv(
                engine,
                plan.schema,
                table.table,
                table.columns,
                output,
                gzip_output=plan.compression == "gzip",
            )
            exported_rows = count_csv(
                output,
                table.columns,
                gzip_input=plan.compression == "gzip",
            )
        if exported_rows != table.local_rows:
            raise RuntimeError(
                f"{plan.schema}.{table.table}: exported {exported_rows:,} rows, "
                f"expected {table.local_rows:,}."
            )
        output.replace(destination)
        return {
            "file": table.filename,
            "rows": exported_rows,
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "columns": [column.name for column in table.columns],
            "dropped_columns": list(table.dropped_columns),
            "status": table.status,
            "coverage_percent": round(table.coverage_percent, 2),
            "run_id": table.coverage.run_id if table.coverage else None,
            "run_status": table.coverage.run_status if table.coverage else None,
            "source_rows": table.coverage.source_rows if table.coverage else None,
            "ingested_rows": table.coverage.ingested_rows if table.coverage else None,
            "local_rows": table.local_rows,
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def write_text_atomic(path: Path, text: str) -> None:
    """Write text through a temporary file and rename it into place."""
    temporary = path.with_name(path.name + ".part")
    # pi-lens-ignore: python-path-traversal -- path is inside the validated snapshot directory
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_nflow(
    path: Path, plan: ExportPlan, records: dict[str, dict[str, Any]]
) -> None:
    """Write the table n-flow as CSV."""
    fields = [
        "table",
        "status",
        "local_rows",
        "source_rows",
        "ingested_rows",
        "coverage_percent",
        "run_id",
        "run_status",
        "dropped_columns",
        "exported_rows",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for table in plan.tables:
            record = records[table.table]
            writer.writerow(
                {
                    "table": table.table,
                    "status": record["status"],
                    "local_rows": table.local_rows,
                    "source_rows": (
                        record["source_rows"]
                        if record["source_rows"] is not None
                        else ""
                    ),
                    "ingested_rows": (
                        record["ingested_rows"]
                        if record["ingested_rows"] is not None
                        else ""
                    ),
                    "coverage_percent": record["coverage_percent"],
                    "run_id": record["run_id"] or "",
                    "run_status": record["run_status"] or "",
                    "dropped_columns": ";".join(table.dropped_columns),
                    "exported_rows": record["rows"],
                }
            )


def write_data_dictionary(path: Path, plan: ExportPlan) -> None:
    """Write the exported column inventory."""
    lines = [
        "# Data dictionary",
        "",
        f"- Snapshot: `{plan.snapshot}`",
        f"- Phase: `{plan.phase}`",
        f"- Stage: `{plan.stage}`",
        f"- Schema: `{plan.schema}`",
        f"- Format: `{plan.file_format}` ({plan.compression})",
        "",
    ]
    for table in plan.tables:
        lines.extend(
            [
                f"## `{table.table}`",
                "",
                f"File: `{table.filename}`",
                "",
                "| Column | PostgreSQL type | Export type | Nullable |",
                "| --- | --- | --- | --- |",
            ]
        )
        for column in table.columns:
            lines.append(
                f"| `{column.name}` | `{column.sql_type}` | "
                f"`{column.export_type}` | {str(column.nullable).lower()} |"
            )
        if table.dropped_columns:
            lines.extend(
                [
                    "",
                    "Dropped by the export hygiene rule: "
                    + ", ".join(f"`{name}`" for name in table.dropped_columns)
                    + ".",
                ]
            )
        derived = [column for column in table.columns if column.derived_from]
        if derived:
            lines.extend(
                [
                    "",
                    "Derived columns: "
                    + ", ".join(
                        f"`{column.name}` (exact text of `{column.derived_from}`)"
                        for column in derived
                    )
                    + ". DuckDB has no arbitrary-precision decimal type.",
                ]
            )
        lines.append("")
    write_text_atomic(path, "\n".join(lines))


def read_snippet(plan: ExportPlan, table: TablePlan) -> str:
    """Return a consumer load snippet for the selected format."""
    relative = table.filename
    if plan.file_format == "parquet":
        return (
            f"DuckDB: FROM read_parquet('{relative}');\n"
            f"pandas: pd.read_parquet('{relative}')  # requires pyarrow or fastparquet"
        )
    return (
        f"DuckDB: FROM read_csv('{relative}', header = true, nullstr = '\\N');\n"
        f"pandas: pd.read_csv('{relative}', na_values = '\\\\N')"
    )


def write_readme(path: Path, plan: ExportPlan) -> None:
    """Write a short consumer README for the snapshot."""
    lines = [
        f"# Export snapshot: `{plan.snapshot}`",
        "",
        f"- Phase: `{plan.phase}`",
        f"- Stage: `{plan.stage}`",
        f"- Schema: `{plan.schema}`",
        f"- Created: `{utc_iso()}`",
        f"- Format: `{plan.file_format}`",
        f"- Compression: `{plan.compression}`",
        f"- Partial: `{str(plan.partial).lower()}`",
        "- Source: local PostgreSQL mirror; read-only export.",
        "",
        "## Files",
        "",
        "| Table | File | Rows | Status |",
        "| --- | --- | ---: | --- |",
    ]
    for table in plan.tables:
        lines.append(
            f"| `{table.table}` | `{table.filename}` | {table.local_rows:,} | {table.status} |"
        )
    lines.extend(
        [
            "",
            (
                "`manifest.json` records row counts, columns, and SHA-256 per file. "
                "`nflow.csv` records the row-count reconciliation. "
                "`DATA_DICTIONARY.md` records column types."
            ),
            "",
            "## Load",
            "",
        ]
    )
    for table in plan.tables:
        lines.extend(
            [
                f"### `{table.table}`",
                "",
                "```text",
                read_snippet(plan, table),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Sampling",
            "",
            "No sampling was applied. Counts are full-table exports from the mirror.",
            "",
        ]
    )
    write_text_atomic(path, "\n".join(lines))


def print_plan(plan: ExportPlan) -> None:
    """Print the export plan and per-table row counts."""
    print(
        f"snapshot={plan.snapshot} phase={plan.phase} stage={plan.stage} "
        f"schema={plan.schema} format={plan.file_format} "
        f"compression={plan.compression} out_dir={plan.out_dir}"
    )
    print(f"{'table':<24} {'rows':>14} {'status':>10} {'coverage':>10}  file")
    for table in plan.tables:
        print(
            f"{table.table:<24} {table.local_rows:>14,} {table.status:>10} "
            f"{table.coverage_percent:>9.1f}%  {table.filename}"
        )
    if plan.partial:
        print(
            "PARTIAL: at least one table is not complete; export requires --allow-partial."
        )


def clear_previous_snapshot(out_dir: Path) -> None:
    """Remove files listed by an older manifest before an explicit --force rewrite."""
    manifest_path = out_dir / "manifest.json"
    files = {
        out_dir / "manifest.json",
        out_dir / "nflow.csv",
        out_dir / "DATA_DICTIONARY.md",
        out_dir / "README.md",
    }
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
        for record in manifest.get("tables", {}).values():
            filename = record.get("file")
            if filename:
                files.add(out_dir / safe_basename(str(filename)))
    for path in files:
        path.unlink(missing_ok=True)


def run_export(args: argparse.Namespace) -> int:
    """Execute the export request."""
    load_environment()
    engine = get_local_engine()
    try:
        plan = build_plan(engine, args)
        print_plan(plan)
        if plan.partial and not args.allow_partial:
            raise RuntimeError(
                "Refusing to export incomplete tables. Finish ingestion or pass --allow-partial."
            )
        large_csv = [
            table.table
            for table in plan.tables
            if table.local_rows > LARGE_CSV_ROW_LIMIT
        ]
        if plan.file_format == "csv" and large_csv and not args.allow_large_csv:
            raise RuntimeError(
                "CSV export above the row limit for: "
                + ", ".join(large_csv)
                + ". Use Parquet or pass --allow-large-csv."
            )
        if args.dry_run:
            print("dry-run: no files written")
            return 0
        if plan.out_dir.exists() and not args.force:
            targets = [plan.out_dir / "manifest.json"] + [
                plan.out_dir / table.filename for table in plan.tables
            ]
            if any(path.exists() for path in targets):
                raise RuntimeError(
                    f"{plan.out_dir} already contains this snapshot. Pass --force to overwrite."
                )
        plan.out_dir.mkdir(parents=True, exist_ok=True)
        if args.force:
            clear_previous_snapshot(plan.out_dir)
        temp_root = plan.out_dir / f".tmp-{uuid.uuid4().hex}"
        temp_root.mkdir()
        records: dict[str, dict[str, Any]] = {}
        try:
            for table in plan.tables:
                record = export_table(engine, plan, table, temp_root)
                records[table.table] = record
                print(
                    f"wrote {table.filename}: {record['rows']:,} rows, "
                    f"{record['bytes']:,} bytes, sha256={record['sha256'][:12]}..."
                )
            write_nflow(plan.out_dir / "nflow.csv", plan, records)
            write_data_dictionary(plan.out_dir / "DATA_DICTIONARY.md", plan)
            write_readme(plan.out_dir / "README.md", plan)
            manifest = {
                "snapshot": plan.snapshot,
                "directory": plan.out_dir.name,
                "created_at": utc_iso(),
                "phase": plan.phase,
                "stage": plan.stage,
                "schema": plan.schema,
                "source": "local PostgreSQL mirror",
                "format": plan.file_format,
                "compression": plan.compression,
                "partial": plan.partial,
                "excluded_internal_tables": sorted(INTERNAL_TABLES),
                "tables": records,
            }
            write_text_atomic(
                plan.out_dir / "manifest.json",
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            )
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)
        print(f"snapshot written: {plan.out_dir}")
        return 0
    except Exception as error:  # noqa: BLE001 -- CLI boundary: one sanitized error, no traceback
        print(f"Export failed: {safe_error_message(error)}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    return run_export(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
