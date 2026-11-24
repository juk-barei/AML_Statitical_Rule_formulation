"""Read-only profile of the local PostgreSQL mirror.

Quick mode samples large tables for null/share/distinct/time ranges; full mode
scans them. Row counts are always exact.

    python -m src.scripts.etl.profile.profile_local --schemas illicit,licit
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import MetaData, Table, func, inspect, select, tablesample

from src.scripts.config import PROFILING_OUTPUT_DIR
from src.scripts.etl.ingest import get_local_engine, validate_schema_name
from src.scripts.etl.profile.adapters import PostgresDataset, table_coverage
from src.scripts.etl.profile.schema import utc_snapshot_id

SAMPLE_THRESHOLD_ROWS = 100_000
KEY_COLUMNS = {
    "accounts": ("address",),
    "transactions": ("token_symbol", "from_address", "to_address"),
    "wallet_hops": ("wallet_address", "seed_address", "hop_level", "direction"),
    "blacklisted_wallets": ("wallet_address", "source_name", "label"),
    "seed_wallets": ("wallet_address", "source_name", "label"),
    "pipeline_crawl_state": ("address", "seed_address", "hop_level"),
}
TIME_COLUMNS = (
    "block_timestamp",
    "created_at",
    "created_date",
    "first_seen_timestamp",
    "last_seen_timestamp",
    "blacklisted_utc",
    "discovered_at",
    "updated_at",
)


def _source(table: Table, rows: int, mode: str, sample_percent: float):
    if mode == "full" or rows <= SAMPLE_THRESHOLD_ROWS:
        return table, "exact"
    return (
        tablesample(table, func.system(sample_percent)),
        f"sample_system_{sample_percent:g}pct",
    )


def _column_aggregates(connection, source, names: tuple[str, ...]) -> tuple[dict[str, int], dict[str, int]]:
    if not names:
        return {}, {}
    parts: list[Any] = []
    for name in names:
        parts.append(func.count(source.c[name]).label(f"nn__{name}"))
        parts.append(func.count(func.distinct(source.c[name])).label(f"nd__{name}"))
    row = connection.execute(select(*parts).select_from(source)).mappings().one()
    return (
        {name: int(row[f"nn__{name}"]) for name in names},
        {name: int(row[f"nd__{name}"]) for name in names},
    )


def _time_ranges(connection, source, names: tuple[str, ...]) -> dict[str, tuple[Any, Any]]:
    if not names:
        return {}
    parts: list[Any] = []
    for name in names:
        parts.append(func.min(source.c[name]).label(f"min__{name}"))
        parts.append(func.max(source.c[name]).label(f"max__{name}"))
    row = connection.execute(select(*parts).select_from(source)).mappings().one()
    return {name: (row[f"min__{name}"], row[f"max__{name}"]) for name in names}


def _profile_table(
    connection,
    *,
    schema: str,
    table_name: str,
    mode: str,
    sample_percent: float,
    snapshot_id: str,
    run_id: str | None,
    source_rows: int,
    table_is_partial: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    table = Table(table_name, MetaData(), schema=schema, autoload_with=connection)
    rows = int(connection.execute(select(func.count()).select_from(table)).scalar_one())
    source, method = _source(table, rows, mode, sample_percent)
    sample_rows = int(
        connection.execute(select(func.count()).select_from(source)).scalar_one()
    )
    names = tuple(column.name for column in table.columns)
    non_null, distinct = _column_aggregates(connection, source, names)
    times = tuple(name for name in TIME_COLUMNS if name in names)
    ranges = _time_ranges(connection, source, times)
    key_columns = [name for name in KEY_COLUMNS.get(table_name, ()) if name in names]

    null_cells = sum(sample_rows - non_null[name] for name in names)
    overview = {
        "schema": schema,
        "table": table_name,
        "rows": rows,
        "source_rows": source_rows,
        "run_id": run_id,
        "coverage_status": "partial" if table_is_partial else "complete",
        "columns": len(names),
        "sample_rows": sample_rows,
        "null_cells": null_cells,
        "null_share": null_cells / (sample_rows * len(names)) if sample_rows and names else 0.0,
        "time_min": min((value[0] for value in ranges.values() if value[0] is not None), default=None),
        "time_max": max((value[1] for value in ranges.values() if value[1] is not None), default=None),
        "key_columns": ", ".join(key_columns),
        "method": method,
        "snapshot_at": snapshot_id,
        "is_partial": table_is_partial,
    }
    column_rows = []
    for column in table.columns:
        nulls = sample_rows - non_null[column.name]
        column_rows.append(
            {
                "schema": schema,
                "table": table_name,
                "column": column.name,
                "data_type": str(column.type),
                "nullable": bool(column.nullable),
                "rows": rows,
                "sample_rows": sample_rows,
                "non_null": non_null[column.name],
                "nulls": nulls,
                "null_share": nulls / sample_rows if sample_rows else 0.0,
                "distinct": distinct[column.name],
                "min": ranges.get(column.name, (None, None))[0],
                "max": ranges.get(column.name, (None, None))[1],
                "method": method,
                "snapshot_at": snapshot_id,
                "is_partial": table_is_partial,
            }
        )
    return overview, column_rows


def _relations(engine, schema: str, snapshot_id: str) -> list[dict[str, Any]]:
    inspector = inspect(engine)
    rows: list[dict[str, Any]] = []
    for table_name in inspector.get_table_names(schema=schema):
        for fk in inspector.get_foreign_keys(table_name, schema=schema):
            rows.append(
                {
                    "schema": schema,
                    "table": table_name,
                    "column": ", ".join(fk.get("constrained_columns") or []),
                    "references": fk.get("referred_table"),
                    "referred_columns": ", ".join(fk.get("referred_columns") or []),
                    "snapshot_at": snapshot_id,
                }
            )
    return rows


def profile_schema(
    dataset: PostgresDataset,
    output_dir: Path,
    *,
    mode: str = "quick",
    sample_percent: float = 2.0,
    file_prefix: str = "local",
) -> dict[str, Path]:
    """Profile one schema and write overview/columns/relations CSV files."""
    if mode not in {"quick", "full"}:
        raise ValueError("mode must be quick or full")
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_id = dataset.snapshot_id
    overviews: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    table_names = [
        name for name in dataset.tables() if not name.startswith("_etl_")
    ]
    coverage = {
        name: table_coverage(dataset.engine, dataset.schema, name)
        for name in table_names
    }
    coverage_rows = [
        {
            "schema": item.schema,
            "table": item.table,
            "run_id": item.run_id,
            "source_rows": item.source_rows,
            "ingested_rows": item.ingested_rows,
            "local_rows": item.local_rows,
            "shard_count": item.shard_count,
            "completed_shards": item.completed_shards,
            "failed_shards": item.failed_shards,
            "coverage_status": item.status,
            "is_partial": item.is_partial,
            "snapshot_at": snapshot_id,
        }
        for item in coverage.values()
    ]
    with dataset.engine.connect() as connection:
        for table_name in table_names:
            print(f"[{dataset.schema}] profiling {table_name}", flush=True)
            item = coverage[table_name]
            overview, column_rows = _profile_table(
                connection,
                schema=dataset.schema,
                table_name=table_name,
                mode=mode,
                sample_percent=sample_percent,
                snapshot_id=snapshot_id,
                run_id=item.run_id,
                source_rows=item.source_rows,
                table_is_partial=item.is_partial,
            )
            overviews.append(overview)
            columns.extend(column_rows)
    relations = _relations(dataset.engine, dataset.schema, snapshot_id)
    paths = {
        "overview": output_dir / f"{file_prefix}_db_overview.csv",
        "columns": output_dir / f"{file_prefix}_columns.csv",
        "relations": output_dir / f"{file_prefix}_relations.csv",
        "coverage": output_dir / f"{file_prefix}_coverage.csv",
    }
    pd.DataFrame(overviews).to_csv(paths["overview"], index=False)
    pd.DataFrame(columns).to_csv(paths["columns"], index=False)
    relation_columns = [
        "schema",
        "table",
        "column",
        "references",
        "referred_columns",
        "snapshot_at",
    ]
    pd.DataFrame(relations, columns=relation_columns).to_csv(
        paths["relations"], index=False
    )
    pd.DataFrame(coverage_rows).to_csv(paths["coverage"], index=False)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schemas", default="illicit,licit")
    parser.add_argument("--output-dir", default=str(PROFILING_OUTPUT_DIR))
    parser.add_argument("--mode", choices=("quick", "full"), default="quick")
    parser.add_argument("--sample-percent", type=float, default=2.0)
    parser.add_argument("--snapshot-id", default="")
    args = parser.parse_args(argv)
    engine = get_local_engine()
    snapshot_id = args.snapshot_id or utc_snapshot_id()
    output_dir = Path(args.output_dir)
    try:
        for schema in [s.strip() for s in args.schemas.split(",") if s.strip()]:
            dataset = PostgresDataset(
                engine=engine,
                schema=validate_schema_name(schema),
                snapshot_id=snapshot_id,
            )
            paths = profile_schema(
                dataset,
                output_dir,
                mode=args.mode,
                sample_percent=args.sample_percent,
                file_prefix=f"local_{schema}",
            )
            print(f"[{schema}] wrote {', '.join(str(path) for path in paths.values())}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
