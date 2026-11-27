"""Assert-based tests for raw-vs-transformed stage comparison."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from src.scripts.etl.transform.profile.compare_stages import (
    compare_distribution_frames,
    main,
)


def test_compare_match_and_drift() -> None:
    raw = pd.DataFrame(
        [
            {"wallet_class": "illicit", "feature": "tx_lifetime_days", "n_cohort": 17046, "n_eligible": 16041, "mean": 239.14, "p50": 114.65, "pass_count": None},
            {"wallet_class": "licit", "feature": "h2_pass_ge5", "n_cohort": 5180495, "n_eligible": 37965, "mean": 0.08, "p50": 0.0, "pass_count": 3028},
        ]
    )
    transformed = pd.DataFrame(
        [
            {"wallet_class": "illicit", "feature": "tx_lifetime_days", "n_cohort": 17046, "n_eligible": 16041, "mean": 239.14, "p50": 114.65, "pass_count": None},
            {"wallet_class": "licit", "feature": "h2_pass_ge5", "n_cohort": 5180495, "n_eligible": 37960, "mean": 0.08, "p50": 0.0, "pass_count": 3020},
        ]
    )
    diff = compare_distribution_frames(raw, transformed)
    by_key = {(r["wallet_class"], r["feature"]): r for r in diff.to_dict(orient="records")}
    assert by_key[("illicit", "tx_lifetime_days")]["status"] == "match"
    assert by_key[("licit", "h2_pass_ge5")]["status"] == "drift"
    assert by_key[("licit", "h2_pass_ge5")]["n_eligible_delta"] == -5.0
    assert by_key[("licit", "h2_pass_ge5")]["pass_count_delta"] == -8.0


def test_cli_dry_run_and_write() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        raw_dir, tr_dir = root / "raw", root / "transformed"
        raw_dir.mkdir()
        tr_dir.mkdir()
        df = pd.DataFrame(
            [{"wallet_class": "illicit", "feature": "total_tx_count", "n_cohort": 10, "n_eligible": 10, "mean": 5.0, "p50": 4.0, "pass_count": None}]
        )
        df.to_csv(raw_dir / "local_wallet_distributions.csv", index=False)
        df.to_csv(tr_dir / "local_wallet_distributions.csv", index=False)

        assert main(["--raw-dir", str(raw_dir), "--transformed-dir", str(tr_dir), "--dry-run"]) == 0
        assert not (tr_dir / "raw_vs_transformed_diff.csv").exists()

        assert main(["--raw-dir", str(raw_dir), "--transformed-dir", str(tr_dir)]) == 0
        out = pd.read_csv(tr_dir / "raw_vs_transformed_diff.csv")
        assert len(out) == 1 and out.loc[0, "status"] == "match"


if __name__ == "__main__":
    test_compare_match_and_drift()
    test_cli_dry_run_and_write()
    print("stage comparison checks passed")
