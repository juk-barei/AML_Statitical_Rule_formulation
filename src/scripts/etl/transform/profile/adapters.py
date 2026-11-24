"""Read-only dataset adapters for the profile suite."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, MetaData, Table, case, func, inspect, select

from src.scripts.etl.transform.profile.schema import TableCoverage, utc_snapshot_id


def latest_run_status(engine: Engine, schema: str) -> dict | None:
    """Return the latest ETL run row for a schema, if the bookkeeping exists."""
    inspector = inspect(engine)
    if not inspector.has_table("_etl_runs", schema=schema):
        return None
    runs = Table("_etl_runs", MetaData(), schema=schema, autoload_with=engine)
    with engine.connect() as connection:
        row = connection.execute(
            select(runs.c.run_id, runs.c.started_at, runs.c.status)
            .order_by(runs.c.started_at.desc())
            .limit(1)
        ).mappings().first()
    return dict(row) if row else None


def schema_is_partial(engine: Engine, schema: str) -> bool:
    """True when the latest run is unfinished or has failed shards."""
    inspector = inspect(engine)
    if not inspector.has_table("_etl_progress", schema=schema):
        return False
    progress = Table("_etl_progress", MetaData(), schema=schema, autoload_with=engine)
    run = latest_run_status(engine, schema)
    if run is None:
        return False
    with engine.connect() as connection:
        row = connection.execute(
            select(
                func.count().label("shards"),
                func.sum(
                    case((progress.c.status == "completed", 1), else_=0)
                ).label("completed"),
            ).where(progress.c.run_id == run["run_id"])
        ).mappings().one()
    shards = int(row["shards"] or 0)
    completed = int(row["completed"] or 0)
    return shards == 0 or completed != shards or run["status"] != "completed"


def table_coverage(engine: Engine, schema: str, table_name: str) -> TableCoverage:
    """Return the latest run provenance and local count for one table."""
    inspector = inspect(engine)
    target_exists = inspector.has_table(table_name, schema=schema)
    target = (
        Table(table_name, MetaData(), schema=schema, autoload_with=engine)
        if target_exists
        else None
    )
    if not (
        inspector.has_table("_etl_progress", schema=schema)
        and inspector.has_table("_etl_runs", schema=schema)
    ):
        local_rows = _local_count(engine, target)
        return TableCoverage(
            schema=schema,
            table=table_name,
            run_id=None,
            source_rows=0,
            ingested_rows=0,
            local_rows=local_rows,
            shard_count=0,
            completed_shards=0,
            failed_shards=0,
            status="untracked",
            is_partial=True,
        )

    progress = Table("_etl_progress", MetaData(), schema=schema, autoload_with=engine)
    runs = Table("_etl_runs", MetaData(), schema=schema, autoload_with=engine)
    with engine.connect() as connection:
        run = connection.execute(
            select(
                progress.c.run_id,
                func.max(runs.c.started_at).label("last_started"),
            )
            .select_from(
                progress.join(runs, progress.c.run_id == runs.c.run_id)
            )
            .where(progress.c.table_name == table_name)
            .group_by(progress.c.run_id)
            .order_by(func.max(runs.c.started_at).desc())
            .limit(1)
        ).mappings().first()
        if run is None:
            local_rows = _local_count_connection(connection, target)
            return TableCoverage(
                schema=schema,
                table=table_name,
                run_id=None,
                source_rows=0,
                ingested_rows=0,
                local_rows=local_rows,
                shard_count=0,
                completed_shards=0,
                failed_shards=0,
                status="untracked",
                is_partial=True,
            )

        row = connection.execute(
            select(
                func.sum(progress.c.source_rows).label("source_rows"),
                func.sum(progress.c.ingested_rows).label("ingested_rows"),
                func.count().label("shard_count"),
                func.sum(
                    case((progress.c.status == "completed", 1), else_=0)
                ).label("completed_shards"),
                func.sum(
                    case((progress.c.status == "failed", 1), else_=0)
                ).label("failed_shards"),
            ).where(
                progress.c.run_id == run["run_id"],
                progress.c.table_name == table_name,
            )
        ).mappings().one()
        local_rows = _local_count_connection(connection, target)

    source_rows = int(row["source_rows"] or 0)
    ingested_rows = int(row["ingested_rows"] or 0)
    shard_count = int(row["shard_count"] or 0)
    completed_shards = int(row["completed_shards"] or 0)
    failed_shards = int(row["failed_shards"] or 0)
    if failed_shards:
        status = "failed"
    elif completed_shards != shard_count:
        status = "incomplete"
    elif local_rows is None:
        status = "missing"
    elif local_rows != source_rows:
        status = "stale"
    else:
        status = "complete"
    return TableCoverage(
        schema=schema,
        table=table_name,
        run_id=str(run["run_id"]),
        source_rows=source_rows,
        ingested_rows=ingested_rows,
        local_rows=local_rows,
        shard_count=shard_count,
        completed_shards=completed_shards,
        failed_shards=failed_shards,
        status=status,
        is_partial=status != "complete",
    )


def _local_count(engine: Engine, table: Table | None) -> int | None:
    if table is None:
        return None
    with engine.connect() as connection:
        return _local_count_connection(connection, table)


def _local_count_connection(connection, table: Table | None) -> int | None:
    if table is None:
        return None
    return int(connection.execute(select(func.count()).select_from(table)).scalar_one())


def schema_coverage(
    engine: Engine,
    schema: str,
    tables: list[str] | None = None,
) -> list[TableCoverage]:
    """Per-table coverage for non-internal tables."""
    names = tables or [
        name
        for name in inspect(engine).get_table_names(schema=schema)
        if not name.startswith("_etl_")
    ]
    return [table_coverage(engine, schema, name) for name in names]


@dataclass
class PostgresDataset:
    """A read-only PostgreSQL schema with a fixed snapshot id."""

    engine: Engine
    schema: str
    snapshot_id: str = ""
    name: str = "local"
    is_partial: bool = False

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            object.__setattr__(self, "snapshot_id", utc_snapshot_id())
        if not inspect(self.engine).has_schema(self.schema):
            raise ValueError(f"schema not found: {self.schema}")
        self.is_partial = schema_is_partial(self.engine, self.schema)

    def tables(self) -> list[str]:
        return sorted(inspect(self.engine).get_table_names(schema=self.schema))

    def table(self, name: str) -> Table:
        return Table(name, MetaData(), schema=self.schema, autoload_with=self.engine)

    def has_table(self, name: str) -> bool:
        return inspect(self.engine).has_table(name, schema=self.schema)
