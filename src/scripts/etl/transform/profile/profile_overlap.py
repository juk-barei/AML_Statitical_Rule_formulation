"""Cross-database wallet overlap for the illicit and licit cohorts."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import MetaData, Table, distinct, func, select, tablesample

from src.scripts.config import PROFILING_OUTPUT_DIR
from src.scripts.etl.db import (
    create_database_engine,
    get_illicit_online_db_link,
    get_licit_online_db_link,
    load_environment,
    validate_schema_name,
)

OUTPUT_DIR = PROFILING_OUTPUT_DIR
def table_obj(engine, schema: str, name: str) -> Table:
    return Table(name, MetaData(), schema=schema, autoload_with=engine)

def fetch_set(engine, schema: str, table: str, column: str) -> set[str]:
    obj = table_obj(engine, schema, table)
    col = obj.c[column]
    values: set[str] = set()
    with engine.connect().execution_options(stream_results=True) as connection:
        for chunk in pd.read_sql_query(
            select(col).where(col.is_not(None)), connection, chunksize=500_000
        ):
            values.update(chunk[column].astype(str).tolist())
    return values


def count_total(engine, schema: str, table: str, column: str) -> int:
    obj = table_obj(engine, schema, table)
    with engine.connect() as connection:
        return int(connection.execute(select(func.count()).select_from(obj)).scalar_one())


def count_distinct(
    engine,
    schema: str,
    table: str,
    column: str,
    *,
    hop_level_min: int | None = None,
    hop_level: int | None = None,
) -> int:
    obj = table_obj(engine, schema, table)
    query = select(func.count(distinct(obj.c[column])))
    if hop_level_min is not None:
        query = query.where(obj.c.hop_level >= hop_level_min)
    if hop_level is not None:
        query = query.where(obj.c.hop_level == hop_level)
    with engine.connect() as connection:
        # pi-lens-ignore: python-sql-injection -- SQLAlchemy Core; values are bound
        return int(connection.execute(query).scalar_one())


def count_in_values(engine, schema: str, table: str, column: str, values: list[str]) -> int:
    if not values:
        return 0
    obj = table_obj(engine, schema, table)
    query = select(func.count()).select_from(obj).where(obj.c[column].in_(values))
    with engine.connect() as connection:
        # pi-lens-ignore: python-sql-injection -- SQLAlchemy Core; values are bound
        return int(connection.execute(query).scalar_one())


def sample_values(
    engine,
    schema: str,
    table: str,
    column: str,
    *,
    limit: int,
    hop_level_min: int | None = None,
    hop_level_max: int | None = None,
) -> list[str]:
    obj = table_obj(engine, schema, table)
    sample = tablesample(obj, func.system(1))
    query = (
        select(sample.c[column])
        .select_from(sample)
        .where(sample.c[column].is_not(None))
        .distinct()
        .limit(limit)
    )
    if hop_level_min is not None:
        query = query.where(sample.c.hop_level >= hop_level_min)
    if hop_level_max is not None:
        query = query.where(sample.c.hop_level <= hop_level_max)
    with engine.connect() as connection:
        # pi-lens-ignore: python-sql-injection -- SQLAlchemy Core; values are bound
        return [str(value) for value in connection.execute(query).scalars().all()]


def row(label: str, left: int, right: int, overlap: int, method: str) -> dict:
    return {
        "comparison": label,
        "left_count": left,
        "right_count": right,
        "overlap": overlap,
        "left_share": overlap / left if left else 0.0,
        "right_share": overlap / right if right else 0.0,
        "method": method,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", default="public")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--suspicious-sample", type=int, default=5000)
    args = parser.parse_args()
    load_environment()
    schema = validate_schema_name(args.schema)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_at = datetime.now(UTC).isoformat()

    illicit = create_database_engine(get_illicit_online_db_link(), is_source=True, pool_size=4)
    licit = create_database_engine(get_licit_online_db_link(), is_source=True, pool_size=4)
    try:
        print("[illicit] loading blacklist", flush=True)
        blacklist = fetch_set(illicit, schema, "blacklisted_wallets", "wallet_address")
        print(f"[illicit] blacklist unique: {len(blacklist):,}", flush=True)

        print("[illicit] counting hop cohorts", flush=True)
        hop0 = count_distinct(illicit, schema, "wallet_hops", "wallet_address", hop_level=0)
        hop_ge1 = count_distinct(illicit, schema, "wallet_hops", "wallet_address", hop_level_min=1)
        hop_table = table_obj(illicit, schema, "wallet_hops")
        blacklist_table = table_obj(illicit, schema, "blacklisted_wallets")
        joined = hop_table.join(
            blacklist_table,
            hop_table.c.wallet_address == blacklist_table.c.wallet_address,
        )
        with illicit.connect() as connection:
            blacklist_hop_ge1 = int(
                connection.execute(
                    select(func.count(distinct(hop_table.c.wallet_address)))
                    .select_from(joined)
                    .where(hop_table.c.hop_level >= 1)
                ).scalar_one()
            )
        suspicious_total = hop_ge1 - blacklist_hop_ge1

        print("[illicit] sampling suspicious hop wallets", flush=True)
        suspicious_sample = [
            value
            for value in sample_values(
                illicit,
                schema,
                "wallet_hops",
                "wallet_address",
                limit=args.suspicious_sample * 2,
                hop_level_min=1,
                hop_level_max=5,
            )
            if value not in blacklist
        ][: args.suspicious_sample]
        print(f"[illicit] suspicious sample: {len(suspicious_sample):,}", flush=True)

        print("[licit] loading seed_wallets and blacklist", flush=True)
        licit_seed = fetch_set(licit, schema, "seed_wallets", "wallet_address")
        licit_blacklist = fetch_set(licit, schema, "blacklisted_wallets", "wallet_address")
        licit_accounts = count_total(licit, schema, "accounts", "address")

        print("[licit] counting blacklist matches", flush=True)
        in_blacklist = count_in_values(
            licit, schema, "accounts", "address", sorted(blacklist)
        )
        print("[licit] counting suspicious-sample matches", flush=True)
        in_suspicious_sample = count_in_values(
            licit, schema, "accounts", "address", suspicious_sample
        )

        rows = [
            row("illicit blacklist vs licit accounts", len(blacklist), licit_accounts, in_blacklist, "exact"),
            row(
                "illicit suspicious sample vs licit accounts",
                len(suspicious_sample),
                licit_accounts,
                in_suspicious_sample,
                f"sample of {len(suspicious_sample)} suspicious hop 1-5 wallets",
            ),
            row(
                "illicit blacklist vs licit seed_wallets",
                len(blacklist),
                len(licit_seed),
                len(blacklist & licit_seed),
                "exact",
            ),
            row(
                "illicit blacklist vs licit blacklist",
                len(blacklist),
                len(licit_blacklist),
                len(blacklist & licit_blacklist),
                "exact",
            ),
        ]
        overlap_frame = pd.DataFrame(rows)
        overlap_frame["snapshot_at"] = snapshot_at
        overlap_frame.to_csv(output_dir / "group_overlap.csv", index=False)
        counts = [
            {"source": "illicit", "group": "blacklist", "count": len(blacklist)},
            {"source": "illicit", "group": "hop0", "count": hop0},
            {"source": "illicit", "group": "hop_ge1", "count": hop_ge1},
            {"source": "illicit", "group": "blacklist_hop_ge1", "count": blacklist_hop_ge1},
            {"source": "illicit", "group": "suspicious", "count": suspicious_total},
            {"source": "licit", "group": "accounts", "count": licit_accounts},
            {"source": "licit", "group": "seed_wallets", "count": len(licit_seed)},
            {"source": "licit", "group": "blacklist", "count": len(licit_blacklist)},
        ]
        count_frame = pd.DataFrame(counts)
        count_frame["snapshot_at"] = snapshot_at
        count_frame.to_csv(output_dir / "cohort_counts.csv", index=False)
        print(f"Wrote {output_dir}/group_overlap.csv", flush=True)
        print(pd.DataFrame(rows).to_string(index=False), flush=True)
    finally:
        illicit.dispose()
        licit.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
