"""Read-only profile of the illicit and licit online PostgreSQL databases."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import MetaData, Table, distinct, func, select

from src.scripts.config import PROFILING_OUTPUT_DIR
from src.scripts.etl.extract.main import (
    create_database_engine,
    get_illicit_online_db_link,
    get_licit_online_db_link,
    load_environment,
    validate_schema_name,
)

OUTPUT_DIR = PROFILING_OUTPUT_DIR
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


def profile_table(engine, schema: str, table: str) -> tuple[dict, list[dict]]:
    table_obj = Table(table, MetaData(), schema=schema, autoload_with=engine)
    names = [column.name for column in table_obj.columns]
    keys = [name for name in KEY_COLUMNS.get(table, ()) if name in names]
    times = [name for name in TIME_COLUMNS if name in names]

    select_parts = [func.count().label("rows")]
    for name in names:
        select_parts.append(
            func.count(table_obj.c[name]).label(f"nn__{name}")
        )
    for name in times:
        select_parts.append(func.min(table_obj.c[name]).label(f"min__{name}"))
        select_parts.append(func.max(table_obj.c[name]).label(f"max__{name}"))
    for name in keys:
        select_parts.append(
            func.count(distinct(table_obj.c[name])).label(f"nd__{name}")
        )

    with engine.connect() as connection:
        row = connection.execute(
            select(*select_parts).select_from(table_obj)
        ).mappings().one()

    rows = int(row["rows"])
    column_rows = []
    null_cells = 0
    for column in table_obj.columns:
        name = column.name
        non_null = int(row[f"nn__{name}"])
        nulls = rows - non_null
        null_cells += nulls
        column_rows.append(
            {
                "table": table,
                "column": name,
                "data_type": str(column.type),
                "nullable": bool(column.nullable),
                "rows": rows,
                "non_null": non_null,
                "nulls": nulls,
                "null_share": nulls / rows if rows else 0.0,
                "distinct": int(row[f"nd__{name}"]) if f"nd__{name}" in row else None,
            }
        )
    overview = {
        "table": table,
        "rows": rows,
        "columns": len(names),
        "null_cells": null_cells,
        "null_share": null_cells / (rows * len(names)) if rows and names else 0.0,
        "time_min": min((row[f"min__{name}"] for name in times if row[f"min__{name}"] is not None), default=None),
        "time_max": max((row[f"max__{name}"] for name in times if row[f"max__{name}"] is not None), default=None),
        "key_columns": ", ".join(keys),
    }
    return overview, column_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", default="illicit,licit")
    parser.add_argument("--schema", default="public")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()
    load_environment()
    schema = validate_schema_name(args.schema)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    links = {"illicit": get_illicit_online_db_link(), "licit": get_licit_online_db_link()}
    overviews, columns, relations = [], [], []
    snapshot_at = datetime.now(UTC).isoformat()
    engines = {}
    for source in [s.strip() for s in args.sources.split(",") if s.strip()]:
        if source not in links:
            raise ValueError(f"Unknown source: {source}")
        print(f"[{source}] connecting", flush=True)
        engine = create_database_engine(links[source], is_source=True, pool_size=4)
        engines[source] = engine
        inspector = __import__("sqlalchemy").inspect(engine)
        tables = inspector.get_table_names(schema=schema)
        print(f"[{source}] tables: {tables}", flush=True)
        for table in tables:
            print(f"[{source}] profiling {table}", flush=True)
            overview, column_rows = profile_table(engine, schema, table)
            overview["source"] = source
            overview["schema"] = schema
            overview["snapshot_at"] = snapshot_at
            overviews.append(overview)
            for item in column_rows:
                item["source"] = source
                item["schema"] = schema
                columns.append(item)
            for fk in inspector.get_foreign_keys(table, schema=schema):
                relations.append(
                    {
                        "source": source,
                        "schema": schema,
                        "table": table,
                        "column": ", ".join(fk.get("constrained_columns") or []),
                        "references": f"{fk.get('referred_schema') or schema}.{fk.get('referred_table')}",
                        "referred_columns": ", ".join(fk.get("referred_columns") or []),
                    }
                )

    pd.DataFrame(overviews).to_csv(output_dir / "db_overview.csv", index=False)
    pd.DataFrame(columns).to_csv(output_dir / "columns.csv", index=False)
    pd.DataFrame(relations).to_csv(output_dir / "relations.csv", index=False)
    print(f"Wrote {output_dir}/db_overview.csv, columns.csv, relations.csv", flush=True)

    for engine in engines.values():
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
