"""Batch ETL for the capstone database.

This module is intentionally the only place that writes data.  The notebooks
read the local PostgreSQL mirror through :func:`load_analysis_tables` while this
script is free to keep ingesting in the background.

Typical usage
-------------
    # Ingest every table from the cloud PostgreSQL database into the local one.
    python3 src/scripts/ETL.py --workers 5 --batch-size 50000

    # Watch the current run without touching the ingestion process.
    python3 src/scripts/ETL.py --status

    # Resume the latest failed/interrupted run.
    python3 src/scripts/ETL.py --resume

Environment
-----------
The script reads the same variables as the notebook:

``ONLINE_DATABASE_LINK``
``LOCAL_DB_NAME`` / ``LOCAL_DB_USER`` / ``LOCAL_DB_HOST`` / ``LOCAL_DB_PASS``

They are loaded from ``src/.env`` by default.  Nothing in this module prints a
connection string or a password.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence, cast
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine

# ---------------------------------------------------------------------------
# Time constants (kept explicit instead of using magic numbers)
# ---------------------------------------------------------------------------
SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
SECONDS_PER_HOUR = SECONDS_PER_MINUTE * MINUTES_PER_HOUR
HOURS_PER_DAY = 24
SECONDS_PER_DAY = SECONDS_PER_HOUR * HOURS_PER_DAY

PERCENT = 100
SOURCE_CONNECT_TIMEOUT_SECONDS = 20
LOCAL_CONNECT_TIMEOUT_SECONDS = 10

# ---------------------------------------------------------------------------
# ETL defaults
# ---------------------------------------------------------------------------
DEFAULT_WORKERS = 5
MAX_WORKERS = 5
DEFAULT_BATCH_SIZE = 50_000
DEFAULT_SHARDS_PER_TABLE = 5
MIN_ROWS_PER_SHARD = 50_000
PROGRESS_POLL_SECONDS = 5
PROGRESS_WRITE_SECONDS = 15
DEFAULT_DEBUG_MODE = 0

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / "src" / ".env"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "ETL"

# PostgreSQL COPY uses this marker for NULL values.  The Python string is
# "\\N" so the SQL literal is NULL '\N'.
NULL_SENTINEL = "\\N"

INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1

# The four analysis tables.  Any extra table in the cloud database is still
# discovered and ingested; these names only define the notebook's default read
# order and the known sharding/ordering strategy.
DEFAULT_TABLE_NAMES: tuple[str, ...] = (
    "accounts",
    "transactions",
    "blacklisted_wallets",
    "wallet_hops",
)


# ---------------------------------------------------------------------------
# Table planning
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TableSpec:
    """How one source table is split and ordered."""

    name: str
    shard_column: str | None
    shard_strategy: str  # "numeric" | "hash" | "none"
    order_columns: tuple[str, ...]
    analysis_role: str


KNOWN_TABLE_SPECS: dict[str, TableSpec] = {
    "accounts": TableSpec(
        name="accounts",
        shard_column="address",
        shard_strategy="hash",
        order_columns=("address",),
        analysis_role="wallet dimension (H2 lifetime coverage check)",
    ),
    "transactions": TableSpec(
        name="transactions",
        shard_column="block_number",
        shard_strategy="numeric",
        order_columns=("block_number", "tx_hash"),
        analysis_role="event fact table (H2, H4, H6)",
    ),
    "blacklisted_wallets": TableSpec(
        name="blacklisted_wallets",
        shard_column="wallet_address",
        shard_strategy="hash",
        order_columns=("wallet_address", "transaction_id"),
        analysis_role="illicit label source",
    ),
    "wallet_hops": TableSpec(
        name="wallet_hops",
        shard_column="hop_id",
        shard_strategy="numeric",
        order_columns=("hop_id",),
        analysis_role="seed traversal / illicit-adjacent cohort",
    ),
}


@dataclass(frozen=True)
class ShardTask:
    """A picklable unit of parallel work."""

    run_id: str
    table_name: str
    target_name: str
    shard_index: int
    shard_count: int
    where_sql: str
    where_params: dict[str, Any]
    source_rows: int
    columns: tuple[str, ...]
    order_columns: tuple[str, ...]
    batch_size: int


@dataclass(frozen=True)
class ShardResult:
    """What a worker reports back to the parent process."""

    table_name: str
    shard_index: int
    source_rows: int
    ingested_rows: int
    elapsed_seconds: float
    status: str
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def quote_identifier(name: str) -> str:
    """Quote a PostgreSQL identifier without trusting its spelling."""
    return '"' + name.replace('"', '""') + '"'


def safe_error_message(error: BaseException) -> str:
    """Return an error string with connection strings redacted."""
    message = f"{type(error).__name__}: {error}"
    message = re.sub(
        r"postgresql(?:\+\w+)?://[^\s]+",
        "postgresql://<redacted>",
        message,
    )
    message = re.sub(r"(password=)[^\s&]+", r"\1<redacted>", message)
    return message[:2000]


def as_int(value: Any) -> int:
    """Coerce a scalar report value (often a numpy/pandas scalar) to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def as_float(value: Any) -> float:
    """Coerce a scalar report value (often a numpy/pandas scalar) to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def as_timestamp(value: Any) -> pd.Timestamp | None:
    """Return a pandas timestamp, or None when the value is missing."""
    if value is None:
        return None
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        return None
    return timestamp


def load_environment() -> None:
    """Load ``src/.env`` if it exists; never print its contents."""
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=False)

# get_online_db_link
# Get illicit db
def get_illicit_online_db_link() -> str:
    link = os.getenv("ILLICIT_ONLINE_DATABASE_LINK")
    if not link:
        raise RuntimeError(
            "ILLICIT_ONLINE_DATABASE_LINK is not set. Add it to src/.env before running ETL."
        )
    return link
    
# Get licit db
def get_licit_online_db_link() -> str:
    link = os.getenv("LICIT_ONLINE_DATABASE_LINK")
    if not link:
        raise RuntimeError(
            "LICIT_ONLINE_DATABASE_LINK is not set. Add it to src/.env before running ETL."
        )
    return link


def get_local_db_link() -> str:
    name = os.getenv("LOCAL_DB_NAME")
    user = os.getenv("LOCAL_DB_USER")
    host = os.getenv("LOCAL_DB_HOST")
    password = os.getenv("LOCAL_DB_PASS")
    missing = [
        variable_name
        for variable_name, value in {
            "LOCAL_DB_NAME": name,
            "LOCAL_DB_USER": user,
            "LOCAL_DB_HOST": host,
            "LOCAL_DB_PASS": password,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Local database variables are incomplete: " + ", ".join(missing)
        )
    # The missing-variable check above guarantees these are strings, but mypy
    # cannot narrow os.getenv() return values through a list comprehension.
    assert name is not None and user is not None
    assert host is not None and password is not None
    return (
        f"postgresql+psycopg://{quote(user, safe='')}:{quote(password, safe='')}"
        f"@{host}/{name}"
    )


def force_psycopg_driver(link: str) -> str:
    """Use psycopg 3 when the environment gives a plain postgresql:// URL."""
    if link.startswith("postgresql://"):
        return "postgresql+psycopg://" + link[len("postgresql://") :]
    return link


def create_database_engine(
    link: str, *, is_source: bool, pool_size: int = 1
) -> Engine:
    connect_timeout = (
        SOURCE_CONNECT_TIMEOUT_SECONDS if is_source else LOCAL_CONNECT_TIMEOUT_SECONDS
    )
    return create_engine(
        force_psycopg_driver(link),
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=0,
        connect_args={"connect_timeout": connect_timeout},
    )


def read_table_rows(
    engine: Engine,
    table_name: str,
    where_sql: str = "",
    where_params: dict[str, Any] | None = None,
) -> int:
    query = text(
        f"SELECT COUNT(*) AS row_count FROM {quote_identifier(table_name)} {where_sql}"
    )
    with engine.connect() as connection:
        # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
        return as_int(connection.execute(query, where_params or {}).scalar_one())


def read_numeric_bounds(
    engine: Engine, table_name: str, column_name: str
) -> tuple[Any, Any]:
    query = text(
        f"SELECT MIN({quote_identifier(column_name)}) AS min_value, "
        f"MAX({quote_identifier(column_name)}) AS max_value "
        f"FROM {quote_identifier(table_name)}"
    )
    with engine.connect() as connection:
        # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
        row = connection.execute(query).one()
    return row.min_value, row.max_value


def discover_source_tables(engine: Engine, requested: str) -> list[str]:
    """Return the requested tables, or every table in the source schema."""
    available = sorted(
        table_name
        for table_name in inspect(engine).get_table_names()
        if not table_name.startswith("_etl_")
    )
    if requested.strip().lower() == "all":
        return available

    requested_tables = [name.strip() for name in requested.split(",") if name.strip()]
    missing = [name for name in requested_tables if name not in available]
    if missing:
        raise ValueError(
            f"Unknown source table(s): {missing}. Available: {available}"
        )
    return requested_tables


def get_table_spec(table_name: str) -> TableSpec:
    """Known tables get a bespoke plan; unknown tables get a safe default."""
    if table_name in KNOWN_TABLE_SPECS:
        return KNOWN_TABLE_SPECS[table_name]
    return TableSpec(
        name=table_name,
        shard_column=None,
        shard_strategy="none",
        order_columns=(),
        analysis_role="extra source table",
    )


def get_table_columns(engine: Engine, table_name: str) -> tuple[str, ...]:
    return tuple(
        column["name"] for column in inspect(engine).get_columns(table_name)
    )


def choose_order_columns(
    table_name: str,
    columns: tuple[str, ...],
    spec: TableSpec,
    engine: Engine,
) -> tuple[str, ...]:
    """Prefer the known order, then the primary key, then the first column."""
    known_order = tuple(column for column in spec.order_columns if column in columns)
    if known_order:
        return known_order

    try:
        raw_primary_key = inspect(engine).get_pk_constraint(table_name).get(
            "constrained_columns", []
        )
    except Exception:
        raw_primary_key = []
    primary_key = tuple(column for column in raw_primary_key if column in columns)
    if primary_key:
        return primary_key
    if columns:
        return (columns[0],)
    return ()


def choose_shard_column(
    table_name: str,
    columns: tuple[str, ...],
    spec: TableSpec,
    engine: Engine,
) -> tuple[str | None, str]:
    """Return ``(column, strategy)`` for splitting a table."""
    if spec.shard_column in columns:
        return spec.shard_column, spec.shard_strategy

    # Unknown tables: use a single-column primary key when possible.
    try:
        primary_key = inspect(engine).get_pk_constraint(table_name).get(
            "constrained_columns", []
        )
    except Exception:
        primary_key = []
    if len(primary_key) == 1 and primary_key[0] in columns:
        return primary_key[0], "hash"
    return None, "none"


def make_hash_where(column_name: str, shard_index: int) -> tuple[str, dict[str, Any]]:
    quoted_column = quote_identifier(column_name)
    where_sql = (
        f"WHERE MOD(ABS(hashtext(CAST({quoted_column} AS TEXT))::bigint), "
        f":shard_count) = :shard_index"
    )
    if shard_index == 0:
        where_sql = (
            f"WHERE ({where_sql[len('WHERE '):]} OR {quoted_column} IS NULL)"
        )
    return where_sql, {"shard_index": shard_index}


def plan_table_tasks(
    source_engine: Engine,
    local_table_name: str,
    run_id: str,
    batch_size: int,
    requested_shards: int,
) -> list[ShardTask]:
    """Count rows and split one table into up to ``requested_shards`` chunks."""
    columns = get_table_columns(source_engine, local_table_name)
    spec = get_table_spec(local_table_name)
    order_columns = choose_order_columns(
        local_table_name, columns, spec, source_engine
    )

    total_rows = read_table_rows(source_engine, local_table_name)
    useful_shards = max(1, total_rows // MIN_ROWS_PER_SHARD)
    actual_shards = min(requested_shards, useful_shards)
    if total_rows == 0:
        actual_shards = 1

    shard_column, strategy = choose_shard_column(
        local_table_name, columns, spec, source_engine
    )

    def make_task(
        shard_index: int,
        shard_count: int,
        where_sql: str,
        where_params: dict[str, Any],
        source_rows: int,
    ) -> ShardTask:
        return ShardTask(
            run_id=run_id,
            table_name=local_table_name,
            target_name=local_table_name,
            shard_index=shard_index,
            shard_count=shard_count,
            where_sql=where_sql,
            where_params=where_params,
            source_rows=source_rows,
            columns=columns,
            order_columns=order_columns,
            batch_size=batch_size,
        )

    if actual_shards <= 1 or shard_column is None or not order_columns:
        return [
            make_task(
                shard_index=0,
                shard_count=1,
                where_sql="",
                where_params={},
                source_rows=total_rows,
            )
        ]

    if strategy == "numeric":
        min_value, max_value = read_numeric_bounds(
            source_engine, local_table_name, shard_column
        )
        # Only integer-like columns are safe to split without precision loss.
        if isinstance(min_value, int) and isinstance(max_value, int):
            span = max_value - min_value + 1
            actual_shards = min(actual_shards, span) if span > 0 else 1
            tasks: list[ShardTask] = []
            for shard_index in range(actual_shards):
                shard_start = min_value + (span * shard_index // actual_shards)
                shard_end = (
                    min_value
                    + (span * (shard_index + 1) // actual_shards)
                    - 1
                )
                where_sql = (
                    f"WHERE {quote_identifier(shard_column)} >= :shard_start "
                    f"AND {quote_identifier(shard_column)} <= :shard_end"
                )
                if shard_index == 0:
                    where_sql = (
                        f"WHERE ({where_sql[len('WHERE '):]} "
                        f"OR {quote_identifier(shard_column)} IS NULL)"
                    )
                where_params = {
                    "shard_start": shard_start,
                    "shard_end": shard_end,
                }
                source_rows = read_table_rows(
                    source_engine, local_table_name, where_sql, where_params
                )
                if source_rows:
                    tasks.append(
                        make_task(
                            shard_index,
                            actual_shards,
                            where_sql,
                            where_params,
                            source_rows,
                        )
                    )
            return tasks or [make_task(0, 1, "WHERE FALSE", {}, 0)]

    # Hash sharding works for text and for non-integer identifiers.
    tasks = []
    for shard_index in range(actual_shards):
        where_sql, base_params = make_hash_where(shard_column, shard_index)
        where_params = {**base_params, "shard_count": actual_shards}
        source_rows = read_table_rows(
            source_engine, local_table_name, where_sql, where_params
        )
        if source_rows:
            tasks.append(
                make_task(
                    shard_index,
                    actual_shards,
                    where_sql,
                    where_params,
                    source_rows,
                )
            )
    return tasks or [make_task(0, 1, "WHERE FALSE", {}, 0)]


# ---------------------------------------------------------------------------
# Local schema and progress tables
# ---------------------------------------------------------------------------
def source_type_to_local_sql(column: Any, local_engine: Engine) -> str:
    """Compile a source column type for the local PostgreSQL dialect."""
    column_type = column.get("type")
    if column_type is None:
        return "TEXT"
    visit_name = getattr(column_type, "__visit_name__", "")
    if visit_name in {"enum", "null", "user_defined"}:
        return "TEXT"
    compile_type = getattr(column_type, "compile", None)
    if compile_type is None:
        return "TEXT"
    try:
        type_sql = str(compile_type(dialect=local_engine.dialect))
    except Exception:
        return "TEXT"
    if not type_sql or type_sql.upper().startswith("NULL"):
        return "TEXT"
    return type_sql


def create_target_tables(
    source_engine: Engine,
    local_engine: Engine,
    table_names: Sequence[str],
    *,
    resume: bool,
) -> None:
    """Create or refresh the local mirror tables before workers start."""
    source_inspector = inspect(source_engine)
    local_inspector = inspect(local_engine)

    for table_name in table_names:
        table_exists = local_inspector.has_table(table_name)
        if resume and table_exists:
            continue

        columns = source_inspector.get_columns(table_name)
        source_column_names = [column["name"] for column in columns]

        # If the local schema already matches, truncate instead of dropping the
        # table. Readers then see an empty table that fills up, not a missing
        # relation while CREATE TABLE is in flight.
        if table_exists:
            existing_column_names = [
                column["name"]
                for column in local_inspector.get_columns(table_name)
            ]
            if existing_column_names == source_column_names:
                with local_engine.begin() as connection:
                    # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
                    connection.execute(
                        text(f"TRUNCATE TABLE {quote_identifier(table_name)}")
                    )
                continue

        column_definitions = []
        for column in columns:
            type_sql = source_type_to_local_sql(column, local_engine)
            column_definitions.append(
                f"{quote_identifier(column['name'])} {type_sql}"
            )
        create_sql = (
            f"CREATE TABLE {quote_identifier(table_name)} "
            f"({', '.join(column_definitions)})"
        )
        with local_engine.begin() as connection:
            # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
            connection.execute(
                text(f"DROP TABLE IF EXISTS {quote_identifier(table_name)} CASCADE")
            )
            # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
            connection.execute(text(create_sql))


def create_progress_tables(local_engine: Engine) -> None:
    """Create the run/progress bookkeeping tables if they are missing."""
    with local_engine.begin() as connection:
        # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS _etl_runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TIMESTAMPTZ NOT NULL,
                    finished_at TIMESTAMPTZ,
                    status TEXT NOT NULL,
                    workers INTEGER NOT NULL,
                    batch_size INTEGER NOT NULL,
                    shards_per_table INTEGER NOT NULL,
                    tables TEXT NOT NULL,
                    total_source_rows BIGINT NOT NULL DEFAULT 0,
                    total_ingested_rows BIGINT NOT NULL DEFAULT 0,
                    error_message TEXT
                )
                """
            )
        )
        # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS _etl_progress (
                    run_id TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    shard_index INTEGER NOT NULL,
                    shard_count INTEGER NOT NULL,
                    source_rows BIGINT NOT NULL DEFAULT 0,
                    ingested_rows BIGINT NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    started_at TIMESTAMPTZ,
                    updated_at TIMESTAMPTZ,
                    elapsed_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
                    rows_per_second DOUBLE PRECISION NOT NULL DEFAULT 0,
                    error_message TEXT,
                    PRIMARY KEY (run_id, table_name, shard_index)
                )
                """
            )
        )


def latest_run_id(local_engine: Engine, *, unfinished_only: bool = False) -> str | None:
    status_filter = "WHERE status NOT IN ('completed')" if unfinished_only else ""
    query = text(
        f"SELECT run_id FROM _etl_runs {status_filter} "
        f"ORDER BY started_at DESC LIMIT 1"
    )
    with local_engine.connect() as connection:
        # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
        return connection.execute(query).scalar_one_or_none()


def seed_progress(
    local_engine: Engine,
    run_id: str,
    tasks: Sequence[ShardTask],
    *,
    workers: int,
    batch_size: int,
    shards_per_table: int,
    tables: Sequence[str],
    total_source_rows: int,
) -> None:
    started_at = datetime.now(timezone.utc)
    with local_engine.begin() as connection:
        # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
        connection.execute(
            text(
                """
                INSERT INTO _etl_runs (
                    run_id, started_at, status, workers, batch_size,
                    shards_per_table, tables, total_source_rows
                ) VALUES (
                    :run_id, :started_at, 'running', :workers, :batch_size,
                    :shards_per_table, :tables, :total_source_rows
                )
                ON CONFLICT (run_id) DO UPDATE SET
                    status = 'running',
                    workers = EXCLUDED.workers,
                    batch_size = EXCLUDED.batch_size,
                    shards_per_table = EXCLUDED.shards_per_table,
                    tables = EXCLUDED.tables,
                    total_source_rows = EXCLUDED.total_source_rows,
                    finished_at = NULL,
                    total_ingested_rows = 0,
                    error_message = NULL
                """
            ),
            {
                "run_id": run_id,
                "started_at": started_at,
                "workers": workers,
                "batch_size": batch_size,
                "shards_per_table": shards_per_table,
                "tables": ",".join(tables),
                "total_source_rows": total_source_rows,
            },
        )
        for task in tasks:
            # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
            connection.execute(
                text(
                    """
                    INSERT INTO _etl_progress (
                        run_id, table_name, shard_index, shard_count,
                        source_rows, ingested_rows, status
                    ) VALUES (
                        :run_id, :table_name, :shard_index, :shard_count,
                        :source_rows, 0, 'pending'
                    )
                    ON CONFLICT (run_id, table_name, shard_index) DO NOTHING
                    """
                ),
                {
                    "run_id": task.run_id,
                    "table_name": task.table_name,
                    "shard_index": task.shard_index,
                    "shard_count": task.shard_count,
                    "source_rows": task.source_rows,
                },
            )


def clear_task_rows(local_engine: Engine, task: ShardTask) -> None:
    """Delete a partial shard before resuming it, keeping completed shards."""
    if not inspect(local_engine).has_table(task.target_name):
        return
    delete_sql = f"DELETE FROM {quote_identifier(task.target_name)} {task.where_sql}"
    with local_engine.begin() as connection:
        # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
        connection.execute(text(delete_sql), task.where_params)


def reset_task_progress(local_engine: Engine, task: ShardTask) -> None:
    with local_engine.begin() as connection:
        # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
        connection.execute(
            text(
                """
                UPDATE _etl_progress SET
                    status = 'pending',
                    ingested_rows = 0,
                    started_at = NULL,
                    updated_at = NULL,
                    elapsed_seconds = 0,
                    rows_per_second = 0,
                    error_message = NULL
                WHERE run_id = :run_id
                  AND table_name = :table_name
                  AND shard_index = :shard_index
                """
            ),
            {
                "run_id": task.run_id,
                "table_name": task.table_name,
                "shard_index": task.shard_index,
            },
        )


def completed_shard_indices(
    local_engine: Engine, run_id: str, table_name: str
) -> set[int]:
    query = text(
        """
        SELECT shard_index FROM _etl_progress
        WHERE run_id = :run_id AND table_name = :table_name
          AND status = 'completed'
        """
    )
    with local_engine.connect() as connection:
        return {
            as_int(row.shard_index)
            # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
            for row in connection.execute(
                query, {"run_id": run_id, "table_name": table_name}
            )
        }


def write_progress(
    local_engine: Engine,
    task: ShardTask,
    *,
    ingested_rows: int,
    status: str,
    started_at: datetime | None,
    start_time: float | None,
    error_message: str | None = None,
) -> None:
    elapsed_seconds = (
        time.perf_counter() - start_time if start_time is not None else 0.0
    )
    rows_per_second = (
        ingested_rows / elapsed_seconds if elapsed_seconds > 0 else 0.0
    )
    now = datetime.now(timezone.utc)
    with local_engine.begin() as connection:
        # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
        connection.execute(
            text(
                """
                INSERT INTO _etl_progress (
                    run_id, table_name, shard_index, shard_count,
                    source_rows, ingested_rows, status, started_at,
                    updated_at, elapsed_seconds, rows_per_second, error_message
                ) VALUES (
                    :run_id, :table_name, :shard_index, :shard_count,
                    :source_rows, :ingested_rows, :status, :started_at,
                    :updated_at, :elapsed_seconds, :rows_per_second, :error_message
                )
                ON CONFLICT (run_id, table_name, shard_index) DO UPDATE SET
                    source_rows = EXCLUDED.source_rows,
                    shard_count = EXCLUDED.shard_count,
                    ingested_rows = EXCLUDED.ingested_rows,
                    status = EXCLUDED.status,
                    started_at = COALESCE(_etl_progress.started_at, EXCLUDED.started_at),
                    updated_at = EXCLUDED.updated_at,
                    elapsed_seconds = EXCLUDED.elapsed_seconds,
                    rows_per_second = EXCLUDED.rows_per_second,
                    error_message = EXCLUDED.error_message
                """
            ),
            {
                "run_id": task.run_id,
                "table_name": task.table_name,
                "shard_index": task.shard_index,
                "shard_count": task.shard_count,
                "source_rows": task.source_rows,
                "ingested_rows": ingested_rows,
                "status": status,
                "started_at": started_at,
                "updated_at": now,
                "elapsed_seconds": elapsed_seconds,
                "rows_per_second": rows_per_second,
                "error_message": error_message,
            },
        )


# ---------------------------------------------------------------------------
# Worker side
# ---------------------------------------------------------------------------
_SOURCE_ENGINE: Engine | None = None
_LOCAL_ENGINE: Engine | None = None


def worker_init(source_link: str, local_link: str) -> None:
    """Create one source connection pool and one local pool per process.

    The local pool needs two connections: one stays checked out for the whole
    shard as the COPY stream, and a second one is borrowed by ``write_progress``
    while that COPY connection is still held.  With ``pool_size=1`` the
    progress write would block until the pool times out.
    """
    global _SOURCE_ENGINE, _LOCAL_ENGINE
    _SOURCE_ENGINE = create_database_engine(source_link, is_source=True)
    _LOCAL_ENGINE = create_database_engine(
        local_link, is_source=False, pool_size=2
    )


def build_batch_query(task: ShardTask) -> str:
    select_columns = ", ".join(
        quote_identifier(column) for column in task.columns
    )
    order_columns = ", ".join(
        quote_identifier(column) for column in task.order_columns
    )
    where_sql = f"\n{task.where_sql}" if task.where_sql.strip() else ""
    return (
        f"SELECT {select_columns}\n"
        f"FROM {quote_identifier(task.table_name)}"
        f"{where_sql}\n"
        f"ORDER BY {order_columns}\n"
        f"LIMIT :batch_limit OFFSET :batch_offset"
    )


def normalize_integer_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Write whole-number float columns as integers.

    pandas turns a BIGINT column containing NULLs into float64, so ``COPY``
    receives values like ``1758539670.0`` and PostgreSQL rejects them for a
    BIGINT column.  Nullable ``Int64`` keeps the NULLs (written as
    ``NULL_SENTINEL``) and emits plain integer text.
    """
    for column_name in dataframe.columns:
        series = dataframe[column_name]
        if not pd.api.types.is_float_dtype(series.dtype):
            continue
        non_null = series.dropna()
        if non_null.empty:
            continue
        if not (non_null % 1 == 0).all():
            continue
        if not ((non_null >= INT64_MIN) & (non_null <= INT64_MAX)).all():
            continue
        dataframe[column_name] = series.astype("Int64")
    return dataframe


def copy_dataframe_to_postgres(
    dataframe: pd.DataFrame,
    target_name: str,
    columns: Sequence[str],
    raw_connection: Any,
) -> None:
    """Stream one batch through PostgreSQL COPY (fast path for psycopg)."""
    ordered_frame = normalize_integer_columns(
        dataframe.loc[:, list(columns)].copy()
    )
    buffer = io.StringIO()
    ordered_frame.to_csv(
        buffer,
        index=False,
        header=False,
        na_rep=NULL_SENTINEL,
    )
    buffer.seek(0)
    copy_sql = (
        f"COPY {quote_identifier(target_name)} "
        f"({', '.join(quote_identifier(column) for column in columns)}) "
        f"FROM STDIN WITH (FORMAT CSV, NULL '{NULL_SENTINEL}')"
    )
    with raw_connection.cursor() as cursor:
        if hasattr(cursor, "copy"):
            with cursor.copy(copy_sql) as copy:
                copy.write(buffer.getvalue())
        else:
            # psycopg2 fallback
            cursor.copy_expert(copy_sql, buffer)


def ingest_shard(task: ShardTask) -> ShardResult:
    """Read one shard from the cloud in batches and COPY it into the local DB."""
    if _SOURCE_ENGINE is None or _LOCAL_ENGINE is None:
        raise RuntimeError("Worker engines were not initialized.")

    started_at = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    write_progress(
        _LOCAL_ENGINE,
        task,
        ingested_rows=0,
        status="running",
        started_at=started_at,
        start_time=start_time,
    )

    ingested_rows = 0
    batch_offset = 0
    last_progress_time = start_time
    source_connection: Connection | None = None
    local_raw_connection: Any = None

    try:
        source_connection = _SOURCE_ENGINE.connect().execution_options(
            isolation_level="REPEATABLE READ"
        )
        local_raw_connection = _LOCAL_ENGINE.raw_connection()

        with source_connection.begin():
            while True:
                query = text(build_batch_query(task))
                dataframe = pd.read_sql_query(
                    query,
                    source_connection,
                    params={
                        **task.where_params,
                        "batch_limit": task.batch_size,
                        "batch_offset": batch_offset,
                    },
                )
                if dataframe.empty:
                    break

                copy_dataframe_to_postgres(
                    dataframe,
                    task.target_name,
                    task.columns,
                    local_raw_connection,
                )
                local_raw_connection.commit()

                ingested_rows += len(dataframe)
                batch_offset += len(dataframe)
                now = time.perf_counter()
                if now - last_progress_time >= PROGRESS_WRITE_SECONDS:
                    write_progress(
                        _LOCAL_ENGINE,
                        task,
                        ingested_rows=ingested_rows,
                        status="running",
                        started_at=started_at,
                        start_time=start_time,
                    )
                    last_progress_time = now

                if len(dataframe) < task.batch_size:
                    break

        elapsed_seconds = time.perf_counter() - start_time
        write_progress(
            _LOCAL_ENGINE,
            task,
            ingested_rows=ingested_rows,
            status="completed",
            started_at=started_at,
            start_time=start_time,
        )
        return ShardResult(
            table_name=task.table_name,
            shard_index=task.shard_index,
            source_rows=task.source_rows,
            ingested_rows=ingested_rows,
            elapsed_seconds=elapsed_seconds,
            status="completed",
        )

    except Exception as error:
        if local_raw_connection is not None:
            local_raw_connection.rollback()
        error_message = safe_error_message(error)
        write_progress(
            _LOCAL_ENGINE,
            task,
            ingested_rows=ingested_rows,
            status="failed",
            started_at=started_at,
            start_time=start_time,
            error_message=error_message,
        )
        return ShardResult(
            table_name=task.table_name,
            shard_index=task.shard_index,
            source_rows=task.source_rows,
            ingested_rows=ingested_rows,
            elapsed_seconds=time.perf_counter() - start_time,
            status="failed",
            error_message=error_message,
        )

    finally:
        if source_connection is not None:
            source_connection.close()
        if local_raw_connection is not None:
            local_raw_connection.close()


# ---------------------------------------------------------------------------
# Parent side: live progress, reports, and orchestration
# ---------------------------------------------------------------------------
def get_ingestion_status(
    run_id: str | None = None,
    *,
    engine: Engine | None = None,
) -> pd.DataFrame:
    """Return one row per table for a run (latest run by default)."""
    load_environment()
    own_engine = engine is None
    local_engine = engine or create_database_engine(
        get_local_db_link(), is_source=False
    )
    try:
        create_progress_tables(local_engine)
        if run_id is None:
            run_id = latest_run_id(local_engine)
        if run_id is None:
            return pd.DataFrame()

        query = text(
            """
            SELECT
                table_name,
                SUM(source_rows) AS source_rows,
                SUM(ingested_rows) AS ingested_rows,
                COUNT(*) AS shard_count,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed_shards,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed_shards,
                MIN(started_at) AS started_at,
                MAX(updated_at) AS updated_at,
                SUM(elapsed_seconds) AS worker_elapsed_seconds
            FROM _etl_progress
            WHERE run_id = :run_id
            GROUP BY table_name
            ORDER BY table_name
            """
        )
        status = pd.read_sql_query(
            query, local_engine, params={"run_id": run_id}
        )
        if status.empty:
            return status

        status["progress_percent"] = (
            status["ingested_rows"]
            .div(status["source_rows"].where(status["source_rows"] > 0))
            .mul(PERCENT)
            .fillna(PERCENT)
        )
        status["status"] = "running"
        status.loc[
            status["completed_shards"] == status["shard_count"], "status"
        ] = "completed"
        status.loc[status["failed_shards"] > 0, "status"] = "failed"
        status.insert(0, "run_id", run_id)
        return status
    finally:
        if own_engine:
            local_engine.dispose()


def print_ingestion_status(run_id: str | None = None) -> pd.DataFrame:
    """Print a compact live table and return the underlying dataframe."""
    status = get_ingestion_status(run_id)
    if status.empty:
        print("No ETL run found in the local database.")
        return status
    display_columns = [
        "table_name",
        "source_rows",
        "ingested_rows",
        "progress_percent",
        "status",
    ]
    display_status = status[display_columns].copy()
    display_status["progress_percent"] = display_status["progress_percent"].round(1)
    print(display_status.to_string(index=False))
    return status


def build_ingestion_report(
    local_engine: Engine,
    run_id: str,
    tasks: Sequence[ShardTask],
    *,
    tables: Sequence[str],
) -> pd.DataFrame:
    """Compare source row counts with the actual local row counts."""
    source_rows_by_table: dict[str, int] = {table: 0 for table in tables}
    for task in tasks:
        source_rows_by_table[task.table_name] += task.source_rows

    status = get_ingestion_status(run_id, engine=local_engine)
    status_by_table: dict[str, dict[str, Any]] = {}
    if not status.empty:
        status_by_table = {
            str(table_name): cast(dict[str, Any], row.to_dict())
            for table_name, row in status.set_index("table_name").iterrows()
        }

    report_rows = []
    for table_name in tables:
        source_rows = source_rows_by_table.get(table_name, 0)
        local_rows = read_table_rows(local_engine, table_name)
        progress_row = status_by_table.get(table_name)
        ingested_rows = (
            as_int(progress_row["ingested_rows"])
            if progress_row is not None
            else 0
        )
        failed_shards = (
            as_int(progress_row["failed_shards"])
            if progress_row is not None
            else 0
        )
        worker_elapsed_seconds = (
            as_float(progress_row["worker_elapsed_seconds"])
            if progress_row is not None
            else 0.0
        )
        wall_elapsed_seconds = worker_elapsed_seconds
        if progress_row is not None:
            started_at = as_timestamp(progress_row.get("started_at"))
            updated_at = as_timestamp(progress_row.get("updated_at"))
            if started_at is not None and updated_at is not None:
                wall_elapsed_seconds = (
                    updated_at - started_at
                ).total_seconds()

        coverage_percent = (
            PERCENT * local_rows / source_rows if source_rows else PERCENT
        )
        if failed_shards:
            status_label = "failed"
        elif source_rows == local_rows:
            status_label = "complete"
        elif local_rows > 0:
            status_label = "partial"
        else:
            status_label = "pending"

        report_rows.append(
            {
                "table_name": table_name,
                "source_rows": source_rows,
                "ingested_rows": ingested_rows,
                "local_rows": local_rows,
                "delta_rows": local_rows - source_rows,
                "coverage_percent": coverage_percent,
                "status": status_label,
                "failed_shards": failed_shards,
                "elapsed_seconds": wall_elapsed_seconds,
                "rows_per_second": (
                    ingested_rows / wall_elapsed_seconds
                    if wall_elapsed_seconds > 0
                    else 0.0
                ),
            }
        )
    return pd.DataFrame(report_rows)


def write_report(report: pd.DataFrame, run_id: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    latest_path = OUTPUT_DIR / "ingestion_report.csv"
    run_path = OUTPUT_DIR / f"ingestion_report_{run_id}.csv"
    report.to_csv(latest_path, index=False)
    report.to_csv(run_path, index=False)
    return latest_path


def finish_run(
    local_engine: Engine,
    run_id: str,
    *,
    status: str,
    total_ingested_rows: int,
    error_message: str | None = None,
) -> None:
    with local_engine.begin() as connection:
        # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
        connection.execute(
            text(
                """
                UPDATE _etl_runs SET
                    finished_at = :finished_at,
                    status = :status,
                    total_ingested_rows = :total_ingested_rows,
                    error_message = :error_message
                WHERE run_id = :run_id
                """
            ),
            {
                "finished_at": datetime.now(timezone.utc),
                "status": status,
                "total_ingested_rows": total_ingested_rows,
                "error_message": error_message,
                "run_id": run_id,
            },
        )


POST_INGEST_INDEXES: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "accounts": (("idx_accounts_address", ("address",)),),
    "transactions": (
        ("idx_transactions_tx_hash", ("tx_hash",)),
        ("idx_transactions_block_number", ("block_number",)),
        ("idx_transactions_block_timestamp", ("block_timestamp",)),
        ("idx_transactions_token_from", ("token_symbol", "from_address")),
        ("idx_transactions_token_to", ("token_symbol", "to_address")),
    ),
    "blacklisted_wallets": (
        ("idx_blacklisted_wallet_address", ("wallet_address",)),
    ),
    "wallet_hops": (
        ("idx_wallet_hops_wallet_address", ("wallet_address",)),
        ("idx_wallet_hops_seed_address", ("seed_address",)),
    ),
}


def drop_post_ingest_indexes(
    local_engine: Engine, table_names: Sequence[str]
) -> None:
    """Drop the known indexes before a bulk load; recreate them afterwards."""
    for table_name in table_names:
        for index_name, _columns in POST_INGEST_INDEXES.get(table_name, ()):
            with local_engine.begin() as connection:
                # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
                connection.execute(
                    text(
                        f"DROP INDEX IF EXISTS {quote_identifier(index_name)}"
                    )
                )


def create_post_ingest_indexes(
    local_engine: Engine, table_names: Sequence[str]
) -> None:
    """Add the indexes used by the notebook after all rows are present."""
    inspector = inspect(local_engine)
    for table_name in table_names:
        if not inspector.has_table(table_name):
            continue
        available_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        indexes = POST_INGEST_INDEXES.get(table_name, ())
        for index_name, columns in indexes:
            if not set(columns).issubset(available_columns):
                print(
                    f"Skipping index {index_name}: missing column(s) "
                    f"{sorted(set(columns) - available_columns)}"
                )
                continue
            index_sql = (
                f"CREATE INDEX IF NOT EXISTS {quote_identifier(index_name)} "
                f"ON {quote_identifier(table_name)} "
                f"({', '.join(quote_identifier(column) for column in columns)})"
            )
            try:
                with local_engine.begin() as connection:
                    # pi-lens-ignore: python-sql-injection -- identifiers are quoted; values use bind params
                    connection.execute(text(index_sql))
            except Exception as error:
                print(
                    f"Index {index_name} failed: {safe_error_message(error)}"
                )
        if indexes:
            print(f"Indexes ready for {table_name}.")


def wait_for_workers(
    futures: Sequence[Any],
    *,
    run_id: str,
    poll_engine: Engine,
    started_at: datetime,
) -> list[ShardResult]:
    pending = set(futures)
    results: list[ShardResult] = []

    while pending:
        done, pending = wait(
            pending,
            timeout=PROGRESS_POLL_SECONDS,
            return_when=FIRST_COMPLETED,
        )
        for future in done:
            try:
                result = future.result()
            except Exception as error:
                print(f"Worker crashed: {safe_error_message(error)}")
                continue
            results.append(result)
            if result.status == "failed":
                print(
                    f"FAILED {result.table_name}[{result.shard_index}]: "
                    f"{result.error_message}"
                )
            else:
                print(
                    f"Finished {result.table_name}[{result.shard_index}] "
                    f"{result.ingested_rows:,}/{result.source_rows:,} rows "
                    f"in {result.elapsed_seconds:.1f}s"
                )

        elapsed_seconds = (
            datetime.now(timezone.utc) - started_at
        ).total_seconds()
        print(f"\n[{elapsed_seconds:.0f}s] local mirror progress")
        print_ingestion_status(run_id)
        print("-" * 78)

    return results


def run_etl(args: argparse.Namespace) -> int:
    load_environment()
    source_link = get_illicit_online_db_link()
    local_link = get_local_db_link()
    workers = max(1, min(args.workers, MAX_WORKERS))
    if args.workers > MAX_WORKERS:
        print(f"Capping workers at MAX_WORKERS={MAX_WORKERS}.")
    batch_size = max(1, args.batch_size)
    shards_per_table = max(1, args.shards_per_table)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_engine = create_database_engine(source_link, is_source=True)
    local_engine = create_database_engine(local_link, is_source=False)

    try:
        table_names = discover_source_tables(source_engine, args.tables)
        if not table_names:
            print("No source tables found.")
            return 1

        if not args.dry_run:
            create_progress_tables(local_engine)

        existing_run_id = (
            latest_run_id(local_engine, unfinished_only=True)
            if (args.resume and not args.dry_run)
            else None
        )
        resume = existing_run_id is not None
        run_id = existing_run_id or datetime.now(timezone.utc).strftime(
            "etl_%Y%m%dT%H%M%S_%fZ"
        )
        if resume:
            print(f"Resuming run {run_id}")

        print(f"Run id: {run_id}")
        print(f"Source tables: {', '.join(table_names)}")
        print(f"Workers: {workers} | batch size: {batch_size:,}")

        all_tasks: list[ShardTask] = []
        for table_name in table_names:
            table_tasks = plan_table_tasks(
                source_engine,
                table_name,
                run_id,
                batch_size,
                shards_per_table,
            )
            all_tasks.extend(table_tasks)
            table_source_rows = sum(task.source_rows for task in table_tasks)
            print(
                f"  {table_name}: {table_source_rows:,} source rows "
                f"in {len(table_tasks)} shard(s)"
            )

        if args.debug:
            for task in all_tasks:
                print(
                    f"DEBUG {task.table_name}[{task.shard_index}/"
                    f"{task.shard_count}] rows={task.source_rows:,} "
                    f"where={task.where_sql or '(all rows)'}"
                )

        if args.dry_run:
            print("Dry run only; no analysis tables were changed.")
            return 0

        create_target_tables(
            source_engine,
            local_engine,
            table_names,
            resume=resume,
        )
        if not args.skip_indexes:
            drop_post_ingest_indexes(local_engine, table_names)
        seed_progress(
            local_engine,
            run_id,
            all_tasks,
            workers=workers,
            batch_size=batch_size,
            shards_per_table=shards_per_table,
            tables=table_names,
            total_source_rows=sum(task.source_rows for task in all_tasks),
        )

        tasks_to_run: list[ShardTask] = []
        for task in all_tasks:
            if resume:
                finished = completed_shard_indices(
                    local_engine, run_id, task.table_name
                )
                if task.shard_index in finished:
                    continue
                clear_task_rows(local_engine, task)
                reset_task_progress(local_engine, task)
            tasks_to_run.append(task)

        # Start the largest shards first so the five workers stay busy and the
        # biggest table does not wait behind small dimension tables.
        tasks_to_run.sort(key=lambda task: task.source_rows, reverse=True)

        if not tasks_to_run:
            print("Nothing to ingest; all shards are already completed.")
            report = build_ingestion_report(
                local_engine, run_id, all_tasks, tables=table_names
            )
            write_report(report, run_id)
            finish_run(
                local_engine,
                run_id,
                status="completed",
                total_ingested_rows=int(report["ingested_rows"].sum()),
            )
            if not args.skip_indexes:
                create_post_ingest_indexes(local_engine, table_names)
            print(report.to_string(index=False))
            return 0

        # Do not carry forked SQLAlchemy pools into the children.
        source_engine.dispose()
        local_engine.dispose()
        started_at = datetime.now(timezone.utc)

        executor = ProcessPoolExecutor(
            max_workers=workers,
            initializer=worker_init,
            initargs=(source_link, local_link),
        )
        poll_engine = create_database_engine(local_link, is_source=False)
        try:
            futures = [executor.submit(ingest_shard, task) for task in tasks_to_run]
            results = wait_for_workers(
                futures,
                run_id=run_id,
                poll_engine=poll_engine,
                started_at=started_at,
            )
        except KeyboardInterrupt:
            print("\nInterrupted. Completed shards are safe; rerun with --resume.")
            executor.shutdown(wait=False, cancel_futures=True)
            finish_run(
                poll_engine,
                run_id,
                status="interrupted",
                total_ingested_rows=0,
                error_message="Interrupted by user.",
            )
            return 130
        except Exception as error:
            message = safe_error_message(error)
            print(f"Ingestion loop failed: {message}")
            executor.shutdown(wait=False, cancel_futures=True)
            finish_run(
                poll_engine,
                run_id,
                status="failed",
                total_ingested_rows=0,
                error_message=message,
            )
            return 1
        finally:
            executor.shutdown(wait=True)
            poll_engine.dispose()

        report_engine = create_database_engine(local_link, is_source=False)
        try:
            report = build_ingestion_report(
                report_engine, run_id, all_tasks, tables=table_names
            )
            report_path = write_report(report, run_id)
            failed = report["status"].isin(["failed", "partial", "pending"])
            run_status = "failed" if failed.any() else "completed"
            finish_run(
                report_engine,
                run_id,
                status=run_status,
                total_ingested_rows=int(report["ingested_rows"].sum()),
                error_message=(
                    "Some shards failed or were incomplete."
                    if failed.any()
                    else None
                ),
            )

            if not args.skip_indexes and run_status == "completed":
                create_post_ingest_indexes(report_engine, table_names)

            print("\nFinal ingestion report")
            print(report.to_string(index=False))
            print(f"\nReport written to: {report_path}")
            return 0 if run_status == "completed" else 1
        finally:
            report_engine.dispose()

    finally:
        source_engine.dispose()
        local_engine.dispose()


# ---------------------------------------------------------------------------
# Notebook read API
# ---------------------------------------------------------------------------
def get_local_engine() -> Engine:
    """Create an engine for the local mirror (notebook-friendly)."""
    load_environment()
    return create_database_engine(get_local_db_link(), is_source=False)


def read_local_table(
    table_name: str,
    *,
    columns: Sequence[str] | None = None,
    limit: int | None = None,
    engine: Engine | None = None,
) -> pd.DataFrame:
    """Read one table from the local mirror."""
    load_environment()
    own_engine = engine is None
    local_engine = engine or get_local_engine()
    try:
        select_columns = (
            ", ".join(quote_identifier(column) for column in columns)
            if columns
            else "*"
        )
        query = (
            f"SELECT {select_columns} "
            f"FROM {quote_identifier(table_name)}"
        )
        if limit is not None:
            query += f" LIMIT {int(limit)}"
        return pd.read_sql_query(text(query), local_engine)
    finally:
        if own_engine:
            local_engine.dispose()


def read_local_tables(
    table_names: Sequence[str] | None = None,
    *,
    columns: Sequence[str] | None = None,
    limit: int | None = None,
    engine: Engine | None = None,
) -> dict[str, pd.DataFrame]:
    """Read several tables from the local mirror into a name -> dataframe dict."""
    names = tuple(table_names or DEFAULT_TABLE_NAMES)
    load_environment()
    own_engine = engine is None
    local_engine = engine or get_local_engine()
    try:
        return {
            table_name: read_local_table(
                table_name,
                columns=columns,
                limit=limit,
                engine=local_engine,
            )
            for table_name in names
        }
    finally:
        if own_engine:
            local_engine.dispose()


def load_analysis_tables(
    limit: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return accounts, transactions, blacklisted_wallets, wallet_hops in order.

    Pass ``limit`` to read a quick sample while ETL is still filling the mirror.
    """
    frames = read_local_tables(DEFAULT_TABLE_NAMES, limit=limit)
    return (
        frames["accounts"],
        frames["transactions"],
        frames["blacklisted_wallets"],
        frames["wallet_hops"],
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-ingest cloud PostgreSQL tables into the local mirror.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Parallel worker processes, capped at {MAX_WORKERS}. Default: {DEFAULT_WORKERS}",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Rows read/written per batch. Default: {DEFAULT_BATCH_SIZE:,}",
    )
    parser.add_argument(
        "--shards-per-table",
        type=int,
        default=DEFAULT_SHARDS_PER_TABLE,
        help=f"Maximum shards per table. Default: {DEFAULT_SHARDS_PER_TABLE}",
    )
    parser.add_argument(
        "--tables",
        type=str,
        default="all",
        help="Comma-separated table names, or 'all' (default).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume the latest unfinished run; completed shards are skipped.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count and plan shards without writing to the local database.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print the latest run progress and exit.",
    )
    parser.add_argument(
        "--skip-indexes",
        action="store_true",
        help="Skip post-ingestion index creation.",
    )
    parser.add_argument(
        "--debug",
        type=int,
        default=DEFAULT_DEBUG_MODE,
        help=f"Print extra planning information. Default: {DEFAULT_DEBUG_MODE}",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.status:
            load_environment()
            print_ingestion_status()
            return 0
        if args.workers < 1:
            raise ValueError("--workers must be at least 1.")
        if args.batch_size < 1:
            raise ValueError("--batch-size must be at least 1.")
        if args.shards_per_table < 1:
            raise ValueError("--shards-per-table must be at least 1.")
        return run_etl(args)
    except Exception as error:
        print(f"ETL failed: {safe_error_message(error)}")
        if args.debug:
            raise
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
