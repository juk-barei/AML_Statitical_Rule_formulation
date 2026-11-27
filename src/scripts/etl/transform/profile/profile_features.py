"""Read-only local profile of H2/H4/H6 wallet-level features.

Profiles feature distributions and eligibility n-flow per wallet_class; it does
not write a feature table. All heavy work stays in PostgreSQL.

    python -m src.scripts.etl.transform.profile.profile_features --schemas illicit,licit
"""
from __future__ import annotations

import argparse
import math
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import (
    Float,
    Interval,
    String,
    Table,
    and_,
    bindparam,
    case,
    cast,
    column,
    false,
    func,
    literal,
    select,
    true,
    values,
)
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import FrameClause, FrameClauseType
from sqlalchemy.sql.selectable import Subquery

from src.scripts.config import PROFILING_OUTPUT_DIR
from src.scripts.etl.db import get_local_engine, validate_schema_name
from src.scripts.etl.transform.profile.adapters import PostgresDataset
from src.scripts.etl.transform.profile.schema import utc_snapshot_id

MIN_HOP = 1
MAX_HOP = 5
H2_MAX_LIFETIME_DAYS = 7.0
H2_MIN_BURST_RATIO = 0.75
H4_MIN_JACCARD = 0.50
H6_MAX_CV = 0.15
MIN_LIFETIME_EVENTS = 2
MIN_BURST_EVENTS = 5
MIN_CV_EVENTS = 5

FEATURES = (
    "tx_lifetime_days",
    "burst_ratio",
    "jaccard_index",
    "cv_delta_t",
    "event_count",
    "h2_pass",
    "h4_pass",
    "h6_pass",
)

METRICS = (
    "n",
    "n_eligible",
    "missing",
    "zero_share",
    "mean",
    "median",
    "p10",
    "p25",
    "p75",
    "p90",
    "p99",
    "stddev",
    "min",
    "max",
    "pass_count",
    "pass_share",
)

PROFILE_COLUMNS = (
    "schema",
    "wallet_class",
    "feature",
    "metric",
    "value",
    "denominator",
    "snapshot_at",
    "is_partial",
    "method",
    "assumption",
)

NFLOW_COLUMNS = (
    "wallet_class",
    "feature",
    "filter",
    "n_in",
    "n_out",
    "n_dropped",
    "reason",
    "snapshot_at",
    "is_partial",
)

FEATURE_ASSUMPTIONS = {
    "tx_lifetime_days": (
        "all tokens; transaction span, not account first-seen; "
        f">={MIN_LIFETIME_EVENTS} events"
    ),
    "burst_ratio": (
        "USDT-only; rule text says in+out volume, token scope unresolved; "
        f">={MIN_BURST_EVENTS} USDT events"
    ),
    "jaccard_index": (
        "distinct TRX funders vs USDT recipients; both sets non-empty"
    ),
    "cv_delta_t": (
        "pooled IN/OUT events, direction unresolved; "
        f">={MIN_CV_EVENTS} events and mean gap > 0"
    ),
    "event_count": (
        "de-duplicated wallet events; pooled IN/OUT, direction unresolved"
    ),
    "h2_pass": (
        f"tx_lifetime_days <= {H2_MAX_LIFETIME_DAYS:g} and "
        f"burst_ratio >= {H2_MIN_BURST_RATIO:g}; both feature eligibilities"
    ),
    "h4_pass": f"jaccard_index >= {H4_MIN_JACCARD:g}; both sets non-empty",
    "h6_pass": (
        f"cv_delta_t < {H6_MAX_CV:g}; >={MIN_CV_EVENTS} events and mean gap > 0"
    ),
}

FEATURE_ELIGIBILITY = {
    "tx_lifetime_days": (
        "event_count_gte_2",
        "lifetime undefined below 2 events",
    ),
    "burst_ratio": (
        "usdt_event_count_gte_5",
        "burst undefined below 5 USDT events",
    ),
    "jaccard_index": (
        "both_sets_non_empty",
        "Jaccard undefined when either side is empty",
    ),
    "cv_delta_t": (
        "event_count_gte_5_and_mean_gap_gt_0",
        "CV undefined below 5 events or with zero mean gap",
    ),
    "event_count": ("all_wallets", "event count defined for every wallet"),
    "h2_pass": (
        "event_count_gte_2_and_usdt_event_count_gte_5",
        "H2 needs lifetime and burst eligibility",
    ),
    "h4_pass": (
        "both_sets_non_empty",
        "H4 needs both counterparty sets",
    ),
    "h6_pass": (
        "event_count_gte_5_and_mean_gap_gt_0",
        "H6 needs the activity gate and a positive mean gap",
    ),
}

ONE_HOUR_FRAME = FrameClause(
    start=bindparam("one_hour", value=timedelta(hours=1), type_=Interval()),
    end=None,
    start_frame_type=FrameClauseType.PRECEDING,
    end_frame_type=FrameClauseType.CURRENT,
)


def lifetime_days(timestamps: Sequence[datetime]) -> float | None:
    """Observed transaction span in days; undefined below two events."""
    if len(timestamps) < MIN_LIFETIME_EVENTS:
        return None
    span = max(timestamps) - min(timestamps)
    return span.total_seconds() / 86_400.0


def burst_ratio(events: Sequence[tuple[datetime, float]]) -> float | None:
    """Max rolling 1-hour volume divided by total volume."""
    if not events:
        return None
    total = sum(amount for _, amount in events)
    if total <= 0:
        return None
    ordered = sorted(events, key=lambda item: item[0])
    start = 0
    window = 0.0
    best = 0.0
    for timestamp, amount in ordered:
        window += amount
        while timestamp - ordered[start][0] > timedelta(hours=1):
            window -= ordered[start][1]
            start += 1
        best = max(best, window)
    return best / total


def jaccard_index(
    trx_funders: Iterable[str], usdt_recipients: Iterable[str]
) -> float | None:
    """Jaccard of two non-empty counterparty sets."""
    funders = set(trx_funders)
    recipients = set(usdt_recipients)
    if not funders or not recipients:
        return None
    return len(funders & recipients) / len(funders | recipients)


def coefficient_of_variation(gaps: Sequence[float]) -> float | None:
    """Sample standard deviation divided by the mean of positive gaps."""
    if len(gaps) < 2:
        return None
    mean = sum(gaps) / len(gaps)
    if mean <= 0:
        return None
    variance = sum((gap - mean) ** 2 for gap in gaps) / (len(gaps) - 1)
    return math.sqrt(variance) / mean


def lifetime_eligible(event_count: int) -> bool:
    return event_count >= MIN_LIFETIME_EVENTS


def burst_eligible(usdt_event_count: int) -> bool:
    return usdt_event_count >= MIN_BURST_EVENTS


def jaccard_eligible(trx_funder_count: int, usdt_recipient_count: int) -> bool:
    return trx_funder_count > 0 and usdt_recipient_count > 0


def cv_eligible(event_count: int, mean_gap: float | None) -> bool:
    return (
        event_count >= MIN_CV_EVENTS
        and mean_gap is not None
        and mean_gap > 0
    )


def build_cohort(
    source: PostgresDataset,
    external: PostgresDataset | None,
    *,
    limit_wallets: int | None = None,
) -> Select:
    """One row per account address with the priority group and home schema."""
    accounts = source.table("accounts")
    source_query = (
        select(accounts.c.address.label("address"))
        .where(accounts.c.address.is_not(None))
    )
    if limit_wallets is not None:
        source_query = source_query.limit(limit_wallets)
    source_addresses = source_query.subquery("source_addresses")
    if external is not None:
        external_accounts = external.table("accounts")
        external_query = (
            select(external_accounts.c.address.label("address"))
            .where(external_accounts.c.address.is_not(None))
        )
        if limit_wallets is not None:
            external_query = external_query.limit(limit_wallets)
        external_addresses = external_query.subquery("external_addresses")
    else:
        external_addresses = (
            select(literal(None).label("address"))
            .where(false())
            .subquery()
        )
    universe = (
        select(source_addresses.c.address)
        .union(select(external_addresses.c.address))
        .subquery("universe")
    )

    if source.has_table("blacklisted_wallets"):
        blacklist = source.table("blacklisted_wallets")
        blacklisted = (
            select(blacklist.c.wallet_address.label("address"))
            .where(
                blacklist.c.label == 1,
                blacklist.c.wallet_address.is_not(None),
            )
            .distinct()
            .subquery("blacklisted")
        )
    else:
        blacklisted = select(literal(None).label("address")).where(false()).subquery()

    if source.has_table("wallet_hops"):
        hops = source.table("wallet_hops")
        hop_query = select(
            hops.c.wallet_address.label("address"),
            func.min(hops.c.hop_level).label("min_hop"),
        ).where(hops.c.hop_level.between(MIN_HOP, MAX_HOP))
        if limit_wallets is not None:
            hop_query = hop_query.where(
                hops.c.wallet_address.in_(select(universe.c.address))
            )
        hop_agg = hop_query.group_by(hops.c.wallet_address).subquery("hop_agg")
    else:
        hop_agg = select(literal(None).label("address")).where(false()).subquery()

    address = universe.c.address
    blacklisted_match = blacklisted.c.address.is_not(None)
    suspicious_match = hop_agg.c.min_hop.between(MIN_HOP, MAX_HOP)
    external_match = external_addresses.c.address.is_not(None)
    source_match = source_addresses.c.address.is_not(None)
    wallet_class = case(
        (blacklisted_match, literal("illicit")),
        (suspicious_match, literal("suspicious")),
        (external_match, literal("licit")),
        else_=literal("unlabeled"),
    )
    external_schema = external.schema if external is not None else source.schema
    home_schema = case(
        (blacklisted_match, literal(source.schema)),
        (suspicious_match, literal(source.schema)),
        (external_match, literal(external_schema)),
        (source_match, literal(source.schema)),
        else_=literal(external_schema),
    )
    return (
        select(
            address.label("address"),
            wallet_class.label("wallet_class"),
            home_schema.label("schema"),
        )
        .select_from(
            universe.outerjoin(
                blacklisted, blacklisted.c.address == address
            )
            .outerjoin(hop_agg, hop_agg.c.address == address)
            .outerjoin(
                external_addresses, external_addresses.c.address == address
            )
            .outerjoin(
                source_addresses, source_addresses.c.address == address
            )
        )
    )


def _wallet_events(transactions: Table, cohort: Select) -> Subquery:
    scope = cohort.subquery("cohort_scope")
    columns = (
        transactions.c.tx_hash,
        transactions.c.block_timestamp,
        transactions.c.block_number,
        transactions.c.token_symbol,
        transactions.c.amount,
    )
    outgoing = select(
        transactions.c.from_address.label("wallet_address"), *columns
    ).select_from(
        transactions.join(
            scope, scope.c.address == transactions.c.from_address
        )
    )
    incoming = select(
        transactions.c.to_address.label("wallet_address"), *columns
    ).select_from(
        transactions.join(scope, scope.c.address == transactions.c.to_address)
    )
    return outgoing.union(incoming).subquery("wallet_events")


def _event_aggregates(events: Subquery) -> Subquery:
    ordered = (
        select(
            events.c.wallet_address,
            events.c.block_timestamp,
            events.c.block_number,
            events.c.token_symbol,
            events.c.amount,
            (
                events.c.block_timestamp
                - func.lag(events.c.block_timestamp).over(
                    partition_by=events.c.wallet_address,
                    order_by=(events.c.block_timestamp, events.c.block_number),
                )
            ).label("gap"),
        )
        .subquery("ordered_events")
    )
    usdt_event = and_(
        ordered.c.token_symbol == literal("USDT"),
        ordered.c.amount.is_not(None),
    )
    gap_seconds = func.extract("epoch", ordered.c.gap)
    return (
        select(
            ordered.c.wallet_address,
            func.count().label("event_count"),
            func.min(ordered.c.block_timestamp).label("first_ts"),
            func.max(ordered.c.block_timestamp).label("last_ts"),
            func.count().filter(usdt_event).label("usdt_event_count"),
            func.sum(ordered.c.amount).filter(usdt_event).label(
                "total_volume_usdt"
            ),
            func.avg(gap_seconds).label("mean_gap_seconds"),
            func.stddev_samp(gap_seconds).label("stddev_gap_seconds"),
        )
        .group_by(ordered.c.wallet_address)
        .subquery("event_aggregates")
    )


def _max_hourly_volume(events: Subquery) -> Subquery:
    usdt = (
        select(
            events.c.wallet_address,
            events.c.block_timestamp,
            events.c.amount,
        )
        .where(
            events.c.token_symbol == literal("USDT"),
            events.c.amount.is_not(None),
            events.c.block_timestamp.is_not(None),
        )
        .subquery("usdt_events")
    )
    windowed = (
        select(
            usdt.c.wallet_address,
            func.sum(usdt.c.amount)
            .over(
                partition_by=usdt.c.wallet_address,
                order_by=usdt.c.block_timestamp,
                range_=ONE_HOUR_FRAME,
            )
            .label("window_volume"),
        )
        .subquery("usdt_windows")
    )
    return (
        select(
            windowed.c.wallet_address,
            func.max(windowed.c.window_volume).label("max_1h_volume_usdt"),
        )
        .group_by(windowed.c.wallet_address)
        .subquery("max_hourly_volume")
    )


def _jaccard_counts(transactions: Table, cohort: Select) -> Subquery:
    scope = cohort.subquery("cohort_scope")
    funders = (
        select(
            transactions.c.to_address.label("wallet_address"),
            transactions.c.from_address.label("counterparty"),
        )
        .select_from(
            transactions.join(
                scope, scope.c.address == transactions.c.to_address
            )
        )
        .where(
            transactions.c.token_symbol == literal("TRX"),
            transactions.c.to_address.is_not(None),
            transactions.c.from_address.is_not(None),
        )
        .group_by(transactions.c.to_address, transactions.c.from_address)
        .subquery("trx_funders")
    )
    recipients = (
        select(
            transactions.c.from_address.label("wallet_address"),
            transactions.c.to_address.label("counterparty"),
        )
        .select_from(
            transactions.join(
                scope, scope.c.address == transactions.c.from_address
            )
        )
        .where(
            transactions.c.token_symbol == literal("USDT"),
            transactions.c.to_address.is_not(None),
            transactions.c.from_address.is_not(None),
        )
        .group_by(transactions.c.from_address, transactions.c.to_address)
        .subquery("usdt_recipients")
    )
    funder_counts = (
        select(
            funders.c.wallet_address,
            func.count().label("trx_funder_count"),
        )
        .group_by(funders.c.wallet_address)
        .subquery("funder_counts")
    )
    recipient_counts = (
        select(
            recipients.c.wallet_address,
            func.count().label("usdt_recipient_count"),
        )
        .group_by(recipients.c.wallet_address)
        .subquery("recipient_counts")
    )
    intersection = (
        select(
            funders.c.wallet_address,
            func.count().label("intersection_count"),
        )
        .select_from(
            funders.join(
                recipients,
                and_(
                    funders.c.wallet_address == recipients.c.wallet_address,
                    funders.c.counterparty == recipients.c.counterparty,
                ),
            )
        )
        .group_by(funders.c.wallet_address)
        .subquery("intersection_counts")
    )
    wallets = (
        select(funder_counts.c.wallet_address)
        .union(select(recipient_counts.c.wallet_address))
        .subquery("jaccard_wallets")
    )
    return (
        select(
            wallets.c.wallet_address,
            func.coalesce(funder_counts.c.trx_funder_count, 0).label(
                "trx_funder_count"
            ),
            func.coalesce(recipient_counts.c.usdt_recipient_count, 0).label(
                "usdt_recipient_count"
            ),
            func.coalesce(intersection.c.intersection_count, 0).label(
                "intersection_count"
            ),
        )
        .select_from(
            wallets.outerjoin(
                funder_counts,
                funder_counts.c.wallet_address == wallets.c.wallet_address,
            )
            .outerjoin(
                recipient_counts,
                recipient_counts.c.wallet_address == wallets.c.wallet_address,
            )
            .outerjoin(
                intersection,
                intersection.c.wallet_address == wallets.c.wallet_address,
            )
        )
        .subquery("jaccard_counts")
    )


def build_wallet_features(cohort: Select, transactions: Table) -> Select:
    """One row per cohort wallet with the H2/H4/H6 feature columns."""
    scope = cohort.subquery("cohort_scope")
    events = _wallet_events(transactions, cohort)
    event_agg = _event_aggregates(events)
    hourly = _max_hourly_volume(events)
    jaccard = _jaccard_counts(transactions, cohort)

    lifetime = (
        func.extract(
            "epoch", event_agg.c.last_ts - event_agg.c.first_ts
        )
        / 86_400.0
    )
    union_count = (
        jaccard.c.trx_funder_count + jaccard.c.usdt_recipient_count
        - jaccard.c.intersection_count
    )
    return (
        select(
            scope.c.address.label("wallet_address"),
            scope.c.wallet_class,
            scope.c.schema,
            func.coalesce(event_agg.c.event_count, 0).label("event_count"),
            lifetime.label("tx_lifetime_days"),
            func.coalesce(event_agg.c.usdt_event_count, 0).label(
                "usdt_event_count"
            ),
            event_agg.c.total_volume_usdt,
            hourly.c.max_1h_volume_usdt,
            case(
                (
                    event_agg.c.total_volume_usdt > 0,
                    hourly.c.max_1h_volume_usdt
                    / event_agg.c.total_volume_usdt,
                ),
                else_=None,
            ).label("burst_ratio"),
            func.coalesce(jaccard.c.trx_funder_count, 0).label(
                "trx_funder_count"
            ),
            func.coalesce(jaccard.c.usdt_recipient_count, 0).label(
                "usdt_recipient_count"
            ),
            case(
                (union_count > 0, jaccard.c.intersection_count / union_count),
                else_=None,
            ).label("jaccard_index"),
            event_agg.c.mean_gap_seconds,
            case(
                (
                    event_agg.c.mean_gap_seconds > 0,
                    event_agg.c.stddev_gap_seconds
                    / event_agg.c.mean_gap_seconds,
                ),
                else_=None,
            ).label("cv_delta_t"),
        )
        .select_from(
            scope.outerjoin(
                event_agg, event_agg.c.wallet_address == scope.c.address
            )
            .outerjoin(
                hourly, hourly.c.wallet_address == scope.c.address
            )
            .outerjoin(
                jaccard, jaccard.c.wallet_address == scope.c.address
            )
        )
    )


def _binary_value(eligible, predicate):
    return case(
        (eligible, case((predicate, 1.0), else_=0.0)),
        else_=None,
    )


def _feature_values():
    """One row per feature name; join by a true condition, not a lateral unnest."""
    return (
        values(column("feature", String), name="feature_values")
        .data([(name,) for name in FEATURES])
        .alias("feature_values")
    )


def _feature_expr(feature_values, mapping, default):
    return case(
        *[
            (feature_values.c.feature == name, expression)
            for name, expression in mapping.items()
        ],
        else_=default,
    )


def feature_stats(connection, wallet_features: Select) -> list[dict[str, Any]]:
    """Compute the long-metric inputs per schema x wallet_class x feature."""
    wallet_features_subquery = wallet_features.subquery("wallet_features")
    feature_values = _feature_values()
    event_count = wallet_features_subquery.c.event_count
    usdt_count = wallet_features_subquery.c.usdt_event_count
    lifetime = wallet_features_subquery.c.tx_lifetime_days
    burst = wallet_features_subquery.c.burst_ratio
    jaccard = wallet_features_subquery.c.jaccard_index
    cv = wallet_features_subquery.c.cv_delta_t
    mean_gap = wallet_features_subquery.c.mean_gap_seconds

    lifetime_eligible = event_count >= MIN_LIFETIME_EVENTS
    burst_eligible = usdt_count >= MIN_BURST_EVENTS
    jaccard_eligible = and_(
        wallet_features_subquery.c.trx_funder_count > 0,
        wallet_features_subquery.c.usdt_recipient_count > 0,
    )
    cv_eligible = and_(
        event_count >= MIN_CV_EVENTS,
        func.coalesce(mean_gap > 0, false()),
    )
    h2_eligible = and_(lifetime_eligible, burst_eligible)

    lifetime_pass = func.coalesce(lifetime <= H2_MAX_LIFETIME_DAYS, false())
    burst_pass = func.coalesce(burst >= H2_MIN_BURST_RATIO, false())
    jaccard_pass = func.coalesce(jaccard >= H4_MIN_JACCARD, false())
    cv_pass = func.coalesce(cv < H6_MAX_CV, false())
    event_pass = event_count >= MIN_BURST_EVENTS
    h2_pass = and_(lifetime_pass, burst_pass)
    h4_pass = jaccard_pass
    h6_pass = cv_pass

    specs = {
        "tx_lifetime_days": (
            cast(lifetime, Float),
            lifetime_eligible,
            lifetime_pass,
        ),
        "burst_ratio": (cast(burst, Float), burst_eligible, burst_pass),
        "jaccard_index": (
            cast(jaccard, Float),
            jaccard_eligible,
            jaccard_pass,
        ),
        "cv_delta_t": (cast(cv, Float), cv_eligible, cv_pass),
        "event_count": (cast(event_count, Float), true(), event_pass),
        "h2_pass": (
            cast(_binary_value(h2_eligible, h2_pass), Float),
            h2_eligible,
            h2_pass,
        ),
        "h4_pass": (
            cast(_binary_value(jaccard_eligible, h4_pass), Float),
            jaccard_eligible,
            h4_pass,
        ),
        "h6_pass": (
            cast(_binary_value(cv_eligible, h6_pass), Float),
            cv_eligible,
            h6_pass,
        ),
    }
    value = _feature_expr(
        feature_values, {name: item[0] for name, item in specs.items()}, None
    )
    eligible = _feature_expr(
        feature_values, {name: item[1] for name, item in specs.items()}, false()
    )
    is_pass = _feature_expr(
        feature_values, {name: item[2] for name, item in specs.items()}, false()
    )
    eligible_value = case((eligible, value), else_=None)
    query = (
        select(
            wallet_features_subquery.c.schema,
            wallet_features_subquery.c.wallet_class,
            feature_values.c.feature,
            func.count().label("n"),
            func.count().filter(eligible).label("n_eligible"),
            func.count()
            .filter(and_(eligible, value == 0))
            .label("zero_count"),
            func.count().filter(and_(eligible, is_pass)).label("pass_count"),
            func.avg(eligible_value).label("mean"),
            func.percentile_cont(0.5)
            .within_group(eligible_value)
            .label("median"),
            func.percentile_cont(0.1).within_group(eligible_value).label("p10"),
            func.percentile_cont(0.25).within_group(eligible_value).label("p25"),
            func.percentile_cont(0.75).within_group(eligible_value).label("p75"),
            func.percentile_cont(0.9).within_group(eligible_value).label("p90"),
            func.percentile_cont(0.99).within_group(eligible_value).label("p99"),
            func.stddev_samp(eligible_value).label("stddev"),
            func.min(eligible_value).label("min_value"),
            func.max(eligible_value).label("max_value"),
        )
        .select_from(wallet_features_subquery.join(feature_values, true()))
        .group_by(
            wallet_features_subquery.c.schema,
            wallet_features_subquery.c.wallet_class,
            feature_values.c.feature,
        )
        .order_by(
            wallet_features_subquery.c.schema,
            wallet_features_subquery.c.wallet_class,
            feature_values.c.feature,
        )
    )
    # pi-lens-ignore: python-sql-injection -- SQLAlchemy Core; no string interpolation
    return [dict(row) for row in connection.execute(query).mappings()]


def _number(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, float):
        return value
    return float(value)


def _metric_values(row: dict[str, Any]) -> dict[str, tuple[Any, int]]:
    n = int(row["n"] or 0)
    eligible = int(row["n_eligible"] or 0)
    zero_count = int(row["zero_count"] or 0)
    pass_count = int(row["pass_count"] or 0)
    return {
        "n": (n, n),
        "n_eligible": (eligible, n),
        "missing": (n - eligible, n),
        "zero_share": (zero_count / eligible if eligible else None, eligible),
        "mean": (_number(row["mean"]), eligible),
        "median": (_number(row["median"]), eligible),
        "p10": (_number(row["p10"]), eligible),
        "p25": (_number(row["p25"]), eligible),
        "p75": (_number(row["p75"]), eligible),
        "p90": (_number(row["p90"]), eligible),
        "p99": (_number(row["p99"]), eligible),
        "stddev": (_number(row["stddev"]), eligible),
        "min": (_number(row["min_value"]), eligible),
        "max": (_number(row["max_value"]), eligible),
        "pass_count": (pass_count, eligible),
        "pass_share": (
            pass_count / eligible if eligible else None,
            eligible,
        ),
    }


def profile_rows(
    stats: Sequence[dict[str, Any]],
    snapshot_id: str,
    is_partial: bool,
    method: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stat in stats:
        feature = stat["feature"]
        for metric, (value, denominator) in _metric_values(stat).items():
            rows.append(
                {
                    "schema": stat["schema"],
                    "wallet_class": stat["wallet_class"],
                    "feature": feature,
                    "metric": metric,
                    "value": value,
                    "denominator": denominator,
                    "snapshot_at": snapshot_id,
                    "is_partial": is_partial,
                    "method": method,
                    "assumption": FEATURE_ASSUMPTIONS[feature],
                }
            )
    return rows


def nflow_rows(
    stats: Sequence[dict[str, Any]],
    snapshot_id: str,
    is_partial: bool,
) -> list[dict[str, Any]]:
    totals: dict[tuple[str, str], list[int]] = {}
    for stat in stats:
        key = (stat["wallet_class"], stat["feature"])
        current = totals.setdefault(key, [0, 0])
        current[0] += int(stat["n"] or 0)
        current[1] += int(stat["n_eligible"] or 0)
    rows: list[dict[str, Any]] = []
    for (wallet_class, feature), (n_in, n_out) in sorted(totals.items()):
        filter_name, reason = FEATURE_ELIGIBILITY[feature]
        rows.append(
            {
                "wallet_class": wallet_class,
                "feature": feature,
                "filter": filter_name,
                "n_in": n_in,
                "n_out": n_out,
                "n_dropped": n_in - n_out,
                "reason": reason,
                "snapshot_at": snapshot_id,
                "is_partial": is_partial,
            }
        )
    return rows


def _cohort_counts(connection, cohort: Select) -> dict[str, int]:
    scope = cohort.subquery("cohort_counts")
    query = select(scope.c.wallet_class, func.count()).group_by(
        scope.c.wallet_class
    )
    # pi-lens-ignore: python-sql-injection -- SQLAlchemy Core; no string interpolation
    rows = connection.execute(query).all()
    return {str(wallet_class): int(count) for wallet_class, count in rows}


def _assert_reconciled(
    observed: dict[str, int], output_dir: Path, limit_wallets: int | None
) -> None:
    if limit_wallets is not None:
        return
    path = output_dir / "local_cohort_counts.csv"
    expected: dict[str, int] | None = None
    if path.exists():
        frame = pd.read_csv(path)
        expected = {
            str(wallet_class): int(count)
            for wallet_class, count in zip(
                frame["wallet_class"], frame["count"], strict=True
            )
        }
    if expected is not None:
        for wallet_class, count in expected.items():
            if observed.get(wallet_class, 0) != count:
                raise ValueError(
                    f"cohort wallet_class {wallet_class} does not reconcile: "
                    f"profile={observed.get(wallet_class, 0)} expected={count}"
                )
        return
    total = sum(observed.values())
    labelled = sum(
        observed.get(wallet_class, 0)
        for wallet_class in ("illicit", "suspicious", "licit", "unlabeled")
    )
    if labelled != total:
        raise ValueError(
            "cohort wallet_classes do not partition the universe: "
            f"{labelled} != {total}"
        )


def _resolve_datasets(
    datasets: Sequence[PostgresDataset],
) -> tuple[PostgresDataset, PostgresDataset | None]:
    if not datasets:
        raise ValueError("at least one schema is required")
    source = next(
        (
            dataset
            for dataset in datasets
            if dataset.has_table("wallet_hops")
            or dataset.has_table("blacklisted_wallets")
        ),
        datasets[0],
    )
    external = next(
        (dataset for dataset in datasets if dataset is not source), None
    )
    return source, external


def profile_features(
    datasets: Sequence[PostgresDataset],
    output_dir: Path,
    *,
    limit_wallets: int | None = None,
    dry_run: bool = False,
) -> dict[str, Path]:
    """Profile wallet features and write the two CSVs."""
    if not datasets:
        raise ValueError("at least one schema is required")
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_id = datasets[0].snapshot_id
    is_partial = any(dataset.is_partial for dataset in datasets)
    method = "exact" if limit_wallets is None else f"limit_wallets_{limit_wallets}"
    source, external = _resolve_datasets(datasets)
    engine = datasets[0].engine
    paths = {
        "feature_profile": output_dir / "local_feature_profile.csv",
        "feature_nflow": output_dir / "local_feature_nflow.csv",
    }
    if dry_run:
        print(
            f"dry run: schemas={[dataset.schema for dataset in datasets]} "
            f"limit_wallets={limit_wallets} outputs={list(paths.values())}"
        )
        return paths

    transactions_by_schema = {
        dataset.schema: dataset.table("transactions") for dataset in datasets
    }
    cohort_query = build_cohort(
        source, external, limit_wallets=limit_wallets
    )
    cohort_scope = cohort_query.subquery("cohort")
    limited = select(
        cohort_scope.c.address,
        cohort_scope.c.wallet_class,
        cohort_scope.c.schema,
    ).subquery("cohort_limited")

    stats: list[dict[str, Any]] = []
    with engine.connect() as connection:
        observed = _cohort_counts(connection, cohort_query)
        _assert_reconciled(observed, output_dir, limit_wallets)
        for dataset in datasets:
            scoped = select(
                limited.c.address,
                limited.c.wallet_class,
                limited.c.schema,
            ).where(limited.c.schema == dataset.schema)
            wallet_features = build_wallet_features(
                scoped, transactions_by_schema[dataset.schema]
            )
            stats.extend(feature_stats(connection, wallet_features))

    rows = profile_rows(stats, snapshot_id, is_partial, method)
    nflow = nflow_rows(stats, snapshot_id, is_partial)
    pd.DataFrame(rows, columns=PROFILE_COLUMNS).to_csv(
        paths["feature_profile"], index=False
    )
    pd.DataFrame(nflow, columns=NFLOW_COLUMNS).to_csv(
        paths["feature_nflow"], index=False
    )
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schemas", default="illicit,licit")
    parser.add_argument("--output-dir", default=str(PROFILING_OUTPUT_DIR))
    parser.add_argument("--snapshot-id", default="")
    parser.add_argument("--limit-wallets", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    engine = get_local_engine()
    snapshot_id = args.snapshot_id or utc_snapshot_id()
    try:
        datasets = [
            PostgresDataset(
                engine=engine,
                schema=validate_schema_name(schema.strip()),
                snapshot_id=snapshot_id,
            )
            for schema in args.schemas.split(",")
            if schema.strip()
        ]
        paths = profile_features(
            datasets,
            Path(args.output_dir),
            limit_wallets=args.limit_wallets,
            dry_run=args.dry_run,
        )
        if not args.dry_run:
            print(f"wrote {', '.join(str(path) for path in paths.values())}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
