"""Assert-based checks for the H2/H4/H6 feature helpers."""
from __future__ import annotations

from datetime import datetime, timedelta

from src.scripts.etl.profile.profile_features import (
    NFLOW_COLUMNS,
    PROFILE_COLUMNS,
    burst_eligible,
    burst_ratio,
    coefficient_of_variation,
    cv_eligible,
    jaccard_eligible,
    jaccard_index,
    lifetime_days,
    lifetime_eligible,
    nflow_rows,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_lifetime() -> None:
    start = datetime(2026, 1, 1)
    check(lifetime_days([start, start + timedelta(days=2)]) == 2.0, "2-day span")
    check(lifetime_days([start]) is None, "one event is undefined")


def test_burst_ratio() -> None:
    start = datetime(2026, 1, 1)
    events = [
        (start, 10.0),
        (start + timedelta(minutes=30), 20.0),
        (start + timedelta(hours=2), 5.0),
    ]
    value = burst_ratio(events)
    check(value is not None and abs(value - (30.0 / 35.0)) < 1e-12, "max 1h window")
    check(burst_ratio([(start, 0.0)]) is None, "zero total is undefined")


def test_jaccard() -> None:
    check(jaccard_index({"a", "b", "c"}, {"b", "c", "d"}) == 0.5, "2/4")
    check(jaccard_index({"a"}, {"b"}) == 0.0, "disjoint")
    check(jaccard_index(set(), {"b"}) is None, "empty set is undefined")


def test_cv() -> None:
    value = coefficient_of_variation([2.0, 4.0, 6.0])
    check(value is not None and abs(value - 0.5) < 1e-12, "sample CV")
    check(coefficient_of_variation([5.0]) is None, "one gap is undefined")
    check(coefficient_of_variation([0.0, 0.0]) is None, "zero mean is undefined")


def test_eligibility() -> None:
    check(lifetime_eligible(2), "lifetime 2")
    check(not lifetime_eligible(1), "lifetime 1")
    check(burst_eligible(5), "burst 5")
    check(not burst_eligible(4), "burst 4")
    check(jaccard_eligible(1, 1), "both sets")
    check(not jaccard_eligible(0, 1), "empty set")
    check(cv_eligible(5, 10.0), "cv eligible")
    check(not cv_eligible(5, 0.0), "zero mean")


def test_nflow_rows() -> None:
    stats = [
        {"group": "illicit", "feature": "tx_lifetime_days", "n": 10, "n_eligible": 7},
        {"group": "licit", "feature": "tx_lifetime_days", "n": 20, "n_eligible": 12},
    ]
    rows = nflow_rows(stats, "2026-11-23T00:00:00Z", False)
    check(len(rows) == 2, "one row per group x feature")
    check(all(set(row) == set(NFLOW_COLUMNS) for row in rows), "n-flow schema")
    check(rows[0]["n_dropped"] == 3, "first n-flow drop")


def test_output_schemas() -> None:
    check("assumption" in PROFILE_COLUMNS, "profile assumption column")
    check("reason" in NFLOW_COLUMNS, "n-flow reason column")


test_lifetime()
test_burst_ratio()
test_jaccard()
test_cv()
test_eligibility()
test_nflow_rows()
test_output_schemas()
print("profile feature checks passed")
