"""Local cohort, overlap, and n-flow profile.

Read-only against the mirror. Group priority is illicit > suspicious > licit >
unlabeled. Uses ``NOT EXISTS`` for nullable anti-joins and aggregates hops
before joining, per the accepted SQL rules.

    python -m src.scripts.etl.profile.profile_overlap_local
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import distinct, exists, func, select
from sqlalchemy.sql import Select

from src.scripts.config import PROFILING_OUTPUT_DIR
from src.scripts.etl.ingest import get_local_engine, validate_schema_name
from src.scripts.etl.profile.adapters import PostgresDataset
from src.scripts.etl.profile.schema import utc_snapshot_id

MIN_HOP = 1
MAX_HOP = 5


def _scalar(connection, query) -> int:
    # pi-lens-ignore: python-sql-injection -- SQLAlchemy Core; no string interpolation
    return int(connection.execute(query).scalar_one())


def _count_subquery(connection, subquery) -> int:
    from_clause = subquery.subquery() if isinstance(subquery, Select) else subquery
    return _scalar(connection, select(func.count()).select_from(from_clause))


def _build_counts(illicit: PostgresDataset, licit: PostgresDataset) -> dict[str, int]:
    i_accounts = illicit.table("accounts")
    l_accounts = licit.table("accounts")
    blacklist = illicit.table("blacklisted_wallets")
    hops = illicit.table("wallet_hops")
    seed_wallets = licit.table("seed_wallets") if licit.has_table("seed_wallets") else None

    blacklisted = (
        select(blacklist.c.wallet_address)
        .where(blacklist.c.label == 1)
        .distinct()
        .subquery("blacklisted")
    )
    hop_agg = (
        select(
            hops.c.wallet_address,
            func.min(hops.c.hop_level).label("min_hop"),
        )
        .where(hops.c.hop_level.between(MIN_HOP, MAX_HOP))
        .group_by(hops.c.wallet_address)
        .subquery("hop_agg")
    )
    account_universe = (
        select(i_accounts.c.address)
        .union(select(l_accounts.c.address))
        .subquery("account_universe")
    )
    universe = account_universe
    blacklist_exists = exists(
        select(1).select_from(blacklisted).where(
            blacklisted.c.wallet_address == hop_agg.c.wallet_address
        )
    )
    licit_exists = exists(
        select(1).select_from(l_accounts).where(
            l_accounts.c.address == hop_agg.c.wallet_address
        )
    )
    blacklist_licit_exists = exists(
        select(1).select_from(l_accounts).where(
            l_accounts.c.address == blacklisted.c.wallet_address
        )
    )

    with illicit.engine.connect() as connection:
        blacklist_count = _count_subquery(connection, blacklisted)
        hop0 = _scalar(
            connection,
            select(func.count(distinct(hops.c.wallet_address))).where(
                hops.c.hop_level == 0
            ),
        )
        hop_ge1 = _scalar(
            connection,
            select(func.count(distinct(hops.c.wallet_address))).where(
                hops.c.hop_level >= MIN_HOP
            ),
        )
        suspicious = _count_subquery(
            connection,
            select(hop_agg.c.wallet_address).where(~blacklist_exists),
        )
        universe_count = _count_subquery(connection, universe)
        account_union_count = _count_subquery(connection, account_universe)
        illicit_accounts = _scalar(
            connection, select(func.count(distinct(i_accounts.c.address)))
        )
        multi_hop = _count_subquery(
            connection,
            select(hops.c.wallet_address)
            .group_by(hops.c.wallet_address)
            .having(func.count(distinct(hops.c.hop_level)) > 1),
        )
        multi_seed = _count_subquery(
            connection,
            select(hops.c.wallet_address)
            .group_by(hops.c.wallet_address)
            .having(func.count(distinct(hops.c.seed_address)) > 1),
        )
        distinct_seeds = _scalar(
            connection, select(func.count(distinct(hops.c.seed_address)))
        )
        blacklist_licit_overlap = _count_subquery(
            connection,
            select(blacklisted.c.wallet_address).where(blacklist_licit_exists),
        )
        suspicious_licit_overlap = _count_subquery(
            connection,
            select(hop_agg.c.wallet_address).where(
                ~blacklist_exists, licit_exists
            ),
        )
        licit_accounts = _scalar(
            connection, select(func.count(distinct(l_accounts.c.address)))
        )
        licit_clean = licit_accounts - blacklist_licit_overlap - suspicious_licit_overlap
        unlabeled = universe_count - blacklist_count - suspicious - licit_clean

        seed_wallets_count = 0
        blacklist_seed_overlap = 0
        if seed_wallets is not None:
            seed_wallets_count = _scalar(
                connection,
                select(func.count(distinct(seed_wallets.c.wallet_address))),
            )
            seed_overlap_exists = exists(
                select(1).select_from(blacklisted).where(
                    blacklisted.c.wallet_address == seed_wallets.c.wallet_address
                )
            )
            blacklist_seed_overlap = _count_subquery(
                connection,
                select(seed_wallets.c.wallet_address).where(seed_overlap_exists),
            )

    labelled = blacklist_count + suspicious + licit_clean + unlabeled
    if labelled != universe_count:
        raise ValueError(
            "cohort groups do not partition the universe: "
            f"{labelled} != {universe_count}"
        )

    return {
        "illicit_accounts": illicit_accounts,
        "licit_accounts": licit_accounts,
        "universe": universe_count,
        "account_union": account_union_count,
        "blacklist": blacklist_count,
        "hop0": hop0,
        "hop_ge1": hop_ge1,
        "suspicious": suspicious,
        "licit_clean": licit_clean,
        "unlabeled": unlabeled,
        "blacklist_licit_overlap": blacklist_licit_overlap,
        "suspicious_licit_overlap": suspicious_licit_overlap,
        "multi_hop_wallets": multi_hop,
        "multi_seed_wallets": multi_seed,
        "distinct_seeds": distinct_seeds,
        "seed_wallets_count": seed_wallets_count,
        "blacklist_seed_overlap": blacklist_seed_overlap,
    }


def build_nflow(counts: dict[str, int], snapshot_id: str, is_partial: bool) -> list[dict[str, Any]]:
    """Build the group x filter n-flow rows from exact counts."""
    return [
        {
            "stage": "account_union",
            "filter": "cross_schema_dedupe",
            "n_in": counts["illicit_accounts"] + counts["licit_accounts"],
            "n_out": counts["account_union"],
            "n_dropped": counts["illicit_accounts"] + counts["licit_accounts"] - counts["account_union"],
            "reason": "address present in both schemas",
            "snapshot_at": snapshot_id,
            "is_partial": is_partial,
        },
        {
            "stage": "universe",
            "filter": "accounts_plus_blacklist_plus_hop",
            "n_in": counts["universe"],
            "n_out": counts["universe"],
            "n_dropped": 0,
            "reason": "frozen account universe; hop-only wallets are excluded from feature profiles",
            "snapshot_at": snapshot_id,
            "is_partial": is_partial,
        },
        {
            "stage": "illicit",
            "filter": "blacklist_label_1",
            "n_in": counts["blacklist"],
            "n_out": counts["blacklist"],
            "n_dropped": 0,
            "reason": "priority group",
            "snapshot_at": snapshot_id,
            "is_partial": is_partial,
        },
        {
            "stage": "suspicious",
            "filter": "min_hop_1_5_and_not_blacklisted",
            "n_in": counts["hop_ge1"],
            "n_out": counts["suspicious"],
            "n_dropped": counts["hop_ge1"] - counts["suspicious"],
            "reason": "blacklist wins at every hop",
            "snapshot_at": snapshot_id,
            "is_partial": is_partial,
        },
        {
            "stage": "licit",
            "filter": "external_minus_illicit_minus_suspicious",
            "n_in": counts["licit_accounts"],
            "n_out": counts["licit_clean"],
            "n_dropped": counts["blacklist_licit_overlap"] + counts["suspicious_licit_overlap"],
            "reason": "illicit/suspicious overlap",
            "snapshot_at": snapshot_id,
            "is_partial": is_partial,
        },
        {
            "stage": "unlabeled",
            "filter": "universe_minus_labelled",
            "n_in": counts["universe"],
            "n_out": counts["unlabeled"],
            "n_dropped": counts["universe"] - counts["unlabeled"],
            "reason": "assigned to illicit/suspicious/licit",
            "snapshot_at": snapshot_id,
            "is_partial": is_partial,
        },
    ]


def profile_overlap(
    illicit: PostgresDataset,
    licit: PostgresDataset,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_id = illicit.snapshot_id
    is_partial = illicit.is_partial or licit.is_partial
    counts = _build_counts(illicit, licit)
    total = counts["universe"]

    group_rows = [
        {"group": "illicit", "count": counts["blacklist"]},
        {"group": "suspicious", "count": counts["suspicious"]},
        {"group": "licit", "count": counts["licit_clean"]},
        {"group": "unlabeled", "count": counts["unlabeled"]},
    ]
    for row in group_rows:
        row["share"] = row["count"] / total if total else 0.0
        row["snapshot_at"] = snapshot_id
        row["is_partial"] = is_partial

    overlap_rows = [
        {
            "comparison": "illicit blacklist vs licit accounts",
            "left_count": counts["blacklist"],
            "right_count": counts["licit_accounts"],
            "overlap": counts["blacklist_licit_overlap"],
        },
        {
            "comparison": "suspicious vs licit accounts",
            "left_count": counts["suspicious"],
            "right_count": counts["licit_accounts"],
            "overlap": counts["suspicious_licit_overlap"],
        },
        {
            "comparison": "illicit blacklist vs licit seed wallets",
            "left_count": counts["blacklist"],
            "right_count": counts["seed_wallets_count"],
            "overlap": counts["blacklist_seed_overlap"],
        },
    ]
    for row in overlap_rows:
        row["left_share"] = row["overlap"] / row["left_count"] if row["left_count"] else 0.0
        row["right_share"] = row["overlap"] / row["right_count"] if row["right_count"] else 0.0
        row["method"] = "exact"
        row["snapshot_at"] = snapshot_id
        row["is_partial"] = is_partial

    hop_rows = [
        {"metric": "hop0_wallets", "value": counts["hop0"]},
        {"metric": "hop_ge1_wallets", "value": counts["hop_ge1"]},
        {"metric": "multi_hop_wallets", "value": counts["multi_hop_wallets"]},
        {"metric": "multi_seed_wallets", "value": counts["multi_seed_wallets"]},
        {"metric": "distinct_seeds", "value": counts["distinct_seeds"]},
    ]
    for row in hop_rows:
        row["snapshot_at"] = snapshot_id
        row["is_partial"] = is_partial

    paths = {
        "cohort_counts": output_dir / "local_cohort_counts.csv",
        "group_overlap": output_dir / "local_group_overlap.csv",
        "nflow": output_dir / "local_nflow.csv",
        "hop_seed": output_dir / "local_hop_seed.csv",
    }
    pd.DataFrame(group_rows).to_csv(paths["cohort_counts"], index=False)
    pd.DataFrame(overlap_rows).to_csv(paths["group_overlap"], index=False)
    pd.DataFrame(build_nflow(counts, snapshot_id, is_partial)).to_csv(paths["nflow"], index=False)
    pd.DataFrame(hop_rows).to_csv(paths["hop_seed"], index=False)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--illicit-schema", default="illicit")
    parser.add_argument("--licit-schema", default="licit")
    parser.add_argument("--output-dir", default=str(PROFILING_OUTPUT_DIR))
    parser.add_argument("--snapshot-id", default="")
    args = parser.parse_args(argv)
    engine = get_local_engine()
    snapshot_id = args.snapshot_id or utc_snapshot_id()
    try:
        illicit = PostgresDataset(
            engine=engine,
            schema=validate_schema_name(args.illicit_schema),
            snapshot_id=snapshot_id,
        )
        licit = PostgresDataset(
            engine=engine,
            schema=validate_schema_name(args.licit_schema),
            snapshot_id=snapshot_id,
        )
        paths = profile_overlap(illicit, licit, Path(args.output_dir))
        print(f"wrote {', '.join(str(path) for path in paths.values())}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
