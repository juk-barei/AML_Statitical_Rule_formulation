"""Assert-based checks for the profile contracts and n-flow arithmetic."""
from src.scripts.etl.transform.profile.profile_overlap_local import build_nflow
from src.scripts.etl.transform.profile.schema import (
    ComparisonRecord,
    ProfileRecord,
    StageManifest,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_comparison_delta() -> None:
    before = ProfileRecord(
        dataset="local",
        stage="raw",
        table="accounts",
        column="address",
        metric="null_share",
        wallet_class="illicit",
        value=0.1,
        denominator=100,
        snapshot_id="2026-11-22T00:00:00Z",
    )
    after = ProfileRecord(
        dataset="local",
        stage="clean",
        table="accounts",
        column="address",
        metric="null_share",
        wallet_class="illicit",
        value=0.0,
        denominator=100,
        snapshot_id="2026-11-22T00:00:00Z",
    )
    comparison = ComparisonRecord.from_records(before, after)
    check(comparison.stage_before == "raw", "stage_before")
    check(comparison.stage_after == "clean", "stage_after")
    check(comparison.delta == -0.1, "delta must be after - before")
    check(comparison.delta_pct == -100.0, "delta percent")
    check(comparison.n_before == 100, "n_before")
    check(comparison.n_after == 100, "n_after")
    check(comparison.as_dict()["wallet_class"] == "illicit", "wallet_class in dict")


def test_comparison_rejects_snapshot() -> None:
    before = ProfileRecord(
        dataset="local",
        stage="raw",
        table="accounts",
        metric="rows",
        value=1,
        denominator=1,
        snapshot_id="2026-11-22T00:00:00Z",
    )
    after = ProfileRecord(
        dataset="local",
        stage="raw",
        table="accounts",
        metric="rows",
        value=1,
        denominator=1,
        snapshot_id="2026-11-23T00:00:00Z",
    )
    try:
        ComparisonRecord.from_records(before, after)
    except ValueError:
        return
    raise AssertionError("mixed snapshots must raise")


def test_stage_manifest_dropped() -> None:
    manifest = StageManifest(
        stage="cohort",
        input_table="universe",
        output_table="cohort_wallet",
        rows_in=10,
        rows_out=7,
        snapshot_id="2026-11-22T00:00:00Z",
    )
    check(manifest.rows_dropped == 3, "rows_dropped")


def test_nflow_arithmetic() -> None:
    counts = {
        "illicit_accounts": 10,
        "licit_accounts": 9,
        "universe": 15,
        "account_union": 15,
        "blacklist": 2,
        "hop_ge1": 7,
        "suspicious": 5,
        "licit_clean": 6,
        "unlabeled": 2,
        "blacklist_licit_overlap": 1,
        "suspicious_licit_overlap": 2,
    }
    rows = build_nflow(counts, "2026-11-22T00:00:00Z", False)
    by_stage = {row["stage"]: row for row in rows}
    check(by_stage["account_union"]["n_in"] == 19, "account union n_in")
    check(by_stage["account_union"]["n_out"] == 15, "account union n_out")
    check(by_stage["account_union"]["n_dropped"] == 4, "account union drop")
    check(by_stage["universe"]["n_out"] == 15, "universe n_out")
    check(by_stage["universe"]["n_dropped"] == 0, "universe drop")
    check(by_stage["suspicious"]["n_dropped"] == 2, "suspicious drop")
    check(by_stage["licit"]["n_dropped"] == 3, "licit drop")
    check(
        counts["blacklist"] + counts["suspicious"] + counts["licit_clean"] + counts["unlabeled"]
        == counts["universe"],
        "groups must partition universe",
    )


test_comparison_delta()
test_comparison_rejects_snapshot()
test_stage_manifest_dropped()
test_nflow_arithmetic()
print("profile core checks passed")
