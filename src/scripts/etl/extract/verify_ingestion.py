"""Verify local mirror coverage for one ingestion schema.

Read-only: this script never writes to the mirror. It compares the latest
``_etl_progress`` rows with the actual local table counts.

Run from the repo root:

    python -m src.scripts.etl.extract.verify_ingestion --schema licit
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from sqlalchemy import MetaData, Table, case, func, inspect, select
from sqlalchemy.exc import NoSuchTableError, ProgrammingError

from src.scripts.etl.extract.main import get_local_engine, validate_schema_name


@dataclass(frozen=True)
class TableCoverage:
    table_name: str
    source_rows: int
    ingested_rows: int
    local_rows: int | None
    shard_count: int
    completed_shards: int
    failed_shards: int
    status: str

    @property
    def coverage_percent(self) -> float:
        if self.source_rows <= 0:
            return 100.0
        return 100.0 * self.ingested_rows / self.source_rows


def _table(bind, schema: str, name: str) -> Table:
    return Table(name, MetaData(), schema=schema, autoload_with=bind)


def _latest_run(engine, schema: str) -> dict | None:
    with engine.connect() as connection:
        try:
            runs = _table(connection, schema, "_etl_runs")
        except (NoSuchTableError, ProgrammingError):
            return None
        row = connection.execute(
            select(runs.c.run_id, runs.c.started_at, runs.c.status, runs.c.tables)
            .order_by(runs.c.started_at.desc())
            .limit(1)
        ).mappings().first()
    return dict(row) if row else None


def _table_counts(
    engine,
    connection,
    schema: str,
    run_id: str,
) -> list[TableCoverage]:
    try:
        progress = _table(connection, schema, "_etl_progress")
    except (NoSuchTableError, ProgrammingError):
        return []

    completed = func.sum(
        case((progress.c.status == "completed", 1), else_=0)
    ).label("completed_shards")
    failed = func.sum(
        case((progress.c.status == "failed", 1), else_=0)
    ).label("failed_shards")
    rows = connection.execute(
        select(
            progress.c.table_name,
            func.sum(progress.c.source_rows).label("source_rows"),
            func.sum(progress.c.ingested_rows).label("ingested_rows"),
            func.count().label("shard_count"),
            completed,
            failed,
        )
        .where(progress.c.run_id == run_id)
        .group_by(progress.c.table_name)
        .order_by(progress.c.table_name)
    ).mappings().all()

    inspector = inspect(connection)
    results: list[TableCoverage] = []
    for row in rows:
        table_name = str(row["table_name"])
        local_rows: int | None = None
        if inspector.has_table(table_name, schema=schema):
            local_table = _table(connection, schema, table_name)
            local_rows = int(
                connection.execute(
                    select(func.count()).select_from(local_table)
                ).scalar_one()
            )

        shard_count = int(row["shard_count"])
        completed_count = int(row["completed_shards"] or 0)
        failed_count = int(row["failed_shards"] or 0)
        if failed_count:
            status = "failed"
        elif completed_count == shard_count:
            status = "complete"
        else:
            status = "incomplete"

        results.append(
            TableCoverage(
                table_name=table_name,
                source_rows=int(row["source_rows"] or 0),
                ingested_rows=int(row["ingested_rows"] or 0),
                local_rows=local_rows,
                shard_count=shard_count,
                completed_shards=completed_count,
                failed_shards=failed_count,
                status=status,
            )
        )
    return results


def verify_schema(
    schema: str,
    *,
    require_complete: bool = True,
    verbose: bool = True,
) -> int:
    """Print coverage and return 0 only when every table is complete."""
    schema = validate_schema_name(schema)
    engine = get_local_engine()
    try:
        run = _latest_run(engine, schema)
        if run is None:
            print(f"No ingestion run found in schema {schema!r}.", file=sys.stderr)
            return 1
        with engine.connect() as connection:
            rows = _table_counts(engine, connection, schema, str(run["run_id"]))

        if verbose:
            print(
                f"schema={schema} run={run['run_id']} "
                f"status={run['status']} started={run['started_at']}"
            )
            print(
                f"{'table':<22} {'source':>12} {'ingested':>12} "
                f"{'local':>12} {'coverage':>9} {'shards':>10} status"
            )
            for row in rows:
                local = "missing" if row.local_rows is None else f"{row.local_rows:,}"
                shards = f"{row.completed_shards}/{row.shard_count}"
                print(
                    f"{row.table_name:<22} {row.source_rows:>12,} "
                    f"{row.ingested_rows:>12,} {local:>12} "
                    f"{row.coverage_percent:>8.1f}% {shards:>10} {row.status}"
                )

        complete = bool(rows) and all(row.status == "complete" for row in rows)
        if require_complete and not complete:
            print(
                "Incomplete ingestion. Resume with "
                "`python -m src.scripts.etl.extract.main --source online_db "
                "--pos-db-type licit --schema licit --resume`.",
                file=sys.stderr,
            )
            return 1
        return 0
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", default="licit")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Return 0 even when a table is incomplete (status check only).",
    )
    args = parser.parse_args(argv)
    return verify_schema(
        args.schema,
        require_complete=not args.allow_incomplete,
    )


if __name__ == "__main__":
    raise SystemExit(main())
