"""Unit and synthetic-fixture tests for src.scripts.eda.profile."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from src.scripts.eda.profile.io import (
    load_profile_bundle,
    resolve_eda_profile_output_dir,
    validate_compare_compatibility,
)
from src.scripts.eda.profile.main import run_stage_plots
from src.scripts.eda.profile.plots_compare import plot_raw_vs_transformed_shift
from src.scripts.eda.profile.style import COHORT_COLORS, COHORT_ORDER, format_compact


def _write_synthetic_stage(
    stage_dir: Path,
    *,
    snapshot_at: str,
    include_mirror_tables: bool = True,
    scale_factor: float = 1.0,
) -> None:
    stage_dir.mkdir(parents=True, exist_ok=True)
    if include_mirror_tables:
        pd.DataFrame(
            [
                {
                    "schema": "illicit",
                    "table": "accounts",
                    "rows": 1000,
                    "source_rows": 1000,
                    "coverage_status": "complete",
                    "snapshot_at": snapshot_at,
                    "is_partial": False,
                },
                {
                    "schema": "illicit",
                    "table": "transactions",
                    "rows": 5000,
                    "source_rows": 5000,
                    "coverage_status": "complete",
                    "snapshot_at": snapshot_at,
                    "is_partial": False,
                },
            ]
        ).to_csv(stage_dir / "local_illicit_db_overview.csv", index=False)
        pd.DataFrame(
            [
                {
                    "schema": "licit",
                    "table": "accounts",
                    "rows": 2000,
                    "source_rows": 2000,
                    "coverage_status": "complete",
                    "snapshot_at": snapshot_at,
                    "is_partial": False,
                },
            ]
        ).to_csv(stage_dir / "local_licit_db_overview.csv", index=False)
        pd.DataFrame(
            [
                {
                    "schema": "illicit",
                    "table": "transactions",
                    "check": "non_positive_amount",
                    "failed_rows": int(50 * scale_factor),
                    "denominator": 5000,
                    "failed_share": 0.01 * scale_factor,
                    "severity": "error",
                    "status": "checked",
                    "snapshot_at": snapshot_at,
                    "is_partial": False,
                },
                {
                    "schema": "illicit",
                    "table": "accounts",
                    "check": "duplicate_accounts",
                    "failed_rows": 0,
                    "denominator": 1000,
                    "failed_share": 0.0,
                    "severity": "error",
                    "status": "checked",
                    "snapshot_at": snapshot_at,
                    "is_partial": False,
                },
            ]
        ).to_csv(stage_dir / "local_quality.csv", index=False)
        pd.DataFrame(
            [
                {
                    "comparison": "illicit blacklist vs licit accounts",
                    "left_count": 100,
                    "right_count": 2000,
                    "overlap": 20,
                    "left_share": 0.2,
                    "right_share": 0.01,
                    "method": "exact",
                    "snapshot_at": snapshot_at,
                    "is_partial": False,
                }
            ]
        ).to_csv(stage_dir / "local_group_overlap.csv", index=False)
        pd.DataFrame(
            [
                {
                    "stage": "account_union",
                    "filter": "cross_schema_dedupe",
                    "n_in": 3000,
                    "n_out": 2800,
                    "n_dropped": 200,
                    "reason": "overlap",
                    "snapshot_at": snapshot_at,
                    "is_partial": False,
                },
                {
                    "stage": "illicit",
                    "filter": "blacklist_label_1",
                    "n_in": 100,
                    "n_out": 100,
                    "n_dropped": 0,
                    "reason": "priority",
                    "snapshot_at": snapshot_at,
                    "is_partial": False,
                },
            ]
        ).to_csv(stage_dir / "local_nflow.csv", index=False)
        pd.DataFrame(
            [
                {"metric": "multi_hop_wallets", "value": 120, "snapshot_at": snapshot_at, "is_partial": False},
                {"metric": "multi_seed_wallets", "value": 95, "snapshot_at": snapshot_at, "is_partial": False},
            ]
        ).to_csv(stage_dir / "local_hop_seed.csv", index=False)

    pd.DataFrame(
        [
            {
                "schema": "illicit",
                "table": "accounts",
                "column": "address",
                "data_type": "VARCHAR",
                "rows": 1000,
                "nulls": 0,
                "null_share": 0.0,
                "distinct_approx": 1000,
                "snapshot_at": snapshot_at,
                "is_partial": False,
            },
            {
                "schema": "illicit",
                "table": "accounts",
                "column": "first_seen_timestamp",
                "data_type": "TIMESTAMP WITH TIME ZONE",
                "rows": 1000,
                "nulls": 800,
                "null_share": 0.8,
                "distinct_approx": 180,
                "snapshot_at": snapshot_at,
                "is_partial": False,
            },
        ]
    ).to_csv(stage_dir / "local_illicit_columns.csv", index=False)

    pd.DataFrame(
        [
            {"section": "cross_schema_tx_overlap", "schema": "both", "token_symbol": "ALL", "category": "raw_union_rows", "count": 5000, "denominator": 5000, "share": 1.0, "snapshot_at": snapshot_at, "is_partial": False},
            {"section": "cross_schema_tx_overlap", "schema": "both", "token_symbol": "ALL", "category": "overlap_tx_hash", "count": 100, "denominator": 5000, "share": 0.02, "snapshot_at": snapshot_at, "is_partial": False},
            {"section": "cross_schema_tx_overlap", "schema": "both", "token_symbol": "ALL", "category": "deduped_tx_rows", "count": 4900, "denominator": 5000, "share": 0.98, "snapshot_at": snapshot_at, "is_partial": False},
            {"section": "cross_schema_tx_overlap", "schema": "both", "token_symbol": "ALL", "category": "diff_amount", "count": 10, "denominator": 100, "share": 0.1, "snapshot_at": snapshot_at, "is_partial": False},
            {"section": "amount_flag", "schema": "illicit", "token_symbol": "USDT", "category": "zero", "count": int(50 * scale_factor), "denominator": 5000, "share": 0.01 * scale_factor, "snapshot_at": snapshot_at, "is_partial": False},
            {"section": "timestamp_flag", "schema": "illicit", "token_symbol": "ALL", "category": "pre_mainnet", "count": int(20 * scale_factor), "denominator": 5000, "share": 0.004 * scale_factor, "snapshot_at": snapshot_at, "is_partial": False},
            {"section": "tx_by_year", "schema": "illicit", "token_symbol": "TRX", "category": "pre_mainnet_1990", "count": 20, "denominator": 5000, "share": 0.004, "snapshot_at": snapshot_at, "is_partial": False},
            {"section": "tx_by_year", "schema": "illicit", "token_symbol": "TRX", "category": "2025", "count": 1200, "denominator": 5000, "share": 0.24, "snapshot_at": snapshot_at, "is_partial": False},
            {"section": "tx_by_year", "schema": "illicit", "token_symbol": "USDT", "category": "2026", "count": 3780, "denominator": 5000, "share": 0.756, "snapshot_at": snapshot_at, "is_partial": False},
            {"section": "tx_by_year", "schema": "licit", "token_symbol": "USDT", "category": "2026", "count": 2500, "denominator": 2500, "share": 1.0, "snapshot_at": snapshot_at, "is_partial": False},
        ]
    ).to_csv(stage_dir / "local_pretransform_cleaning.csv", index=False)

    sf_rows = [
        {"section": "cohort_universe", "group": "illicit", "metric": "wallets_total", "value": 100, "denominator": None, "snapshot_at": snapshot_at, "is_partial": False},
        {"section": "cohort_universe", "group": "illicit", "metric": "wallets_in_accounts", "value": 100, "denominator": 100, "snapshot_at": snapshot_at, "is_partial": False},
        {"section": "cohort_universe", "group": "illicit", "metric": "wallets_hop_only", "value": 0, "denominator": 100, "snapshot_at": snapshot_at, "is_partial": False},
        {"section": "cohort_universe", "group": "suspicious", "metric": "wallets_total", "value": 900, "denominator": None, "snapshot_at": snapshot_at, "is_partial": False},
        {"section": "cohort_universe", "group": "suspicious", "metric": "wallets_in_accounts", "value": 850, "denominator": 900, "snapshot_at": snapshot_at, "is_partial": False},
        {"section": "cohort_universe", "group": "suspicious", "metric": "wallets_hop_only", "value": 50, "denominator": 900, "snapshot_at": snapshot_at, "is_partial": False},
        {"section": "cohort_universe", "group": "licit", "metric": "wallets_total", "value": 1500, "denominator": None, "snapshot_at": snapshot_at, "is_partial": False},
        {"section": "cohort_universe", "group": "unlabeled", "metric": "wallets_total", "value": 300, "denominator": None, "snapshot_at": snapshot_at, "is_partial": False},
    ]
    for hop in range(1, 6):
        sf_rows.append({"section": "suspicious_hop_band", "group": f"hop_{hop}", "metric": "wallets", "value": 180, "denominator": 900, "snapshot_at": snapshot_at, "is_partial": False})
        sf_rows.append({"section": "licit_hop_band", "group": f"hop_{hop}", "metric": "wallets", "value": 20 * hop, "denominator": 300, "snapshot_at": snapshot_at, "is_partial": False})
    for grp, mult in (("illicit_seeds", 10), ("licit_seeds", 3)):
        for m, v in (("n_seeds", 50), ("min", 1), ("p25", 2 * mult), ("p50", 5 * mult), ("p75", 12 * mult), ("p90", 25 * mult), ("p99", 80 * mult), ("max", 120 * mult), ("mean", 14 * mult)):
            sf_rows.append({"section": "seed_cluster_size", "group": grp, "metric": m, "value": v, "denominator": 50, "snapshot_at": snapshot_at, "is_partial": False})
    pd.DataFrame(sf_rows).to_csv(stage_dir / "local_sampling_frame.csv", index=False)

    dist_rows = []
    for hyp, feat in (("shared", "total_tx_count"), ("H2", "tx_lifetime_days"), ("H4", "jaccard_index"), ("H6", "cv_delta_t_all")):
        for idx, coh in enumerate(COHORT_ORDER):
            base = (idx + 1) * 10.0 * scale_factor
            dist_rows.append(
                {
                    "wallet_class": coh,
                    "hypothesis": hyp,
                    "feature": feat,
                    "n_cohort": 100 * (idx + 1),
                    "n_eligible": int(80 * (idx + 1)),
                    "eligible_share": min(1.0, 0.8 * scale_factor),
                    "missing": 20 * (idx + 1),
                    "zero_share": 0.1 * idx,
                    "mean": base * 1.4,
                    "stddev": base * 0.9,
                    "skewness": 3.5 + idx,
                    "min": 0.0,
                    "p10": base * 0.2,
                    "p25": base * 0.5,
                    "p50": base,
                    "p75": base * 1.8,
                    "p90": base * 3.2,
                    "p99": base * 12.0,
                    "p99_p50_ratio": 12.0,
                    "recommended_scale": "log1p",
                    "snapshot_at": snapshot_at,
                    "is_partial": False,
                }
            )
    pd.DataFrame(dist_rows).to_csv(stage_dir / "local_wallet_distributions.csv", index=False)

    hist_rows = []
    for feat, scale in (("total_tx_count", "count_buckets"), ("jaccard_index", "raw_0_1")):
        for coh in COHORT_ORDER:
            for bi in range(4):
                hist_rows.append(
                    {
                        "wallet_class": coh,
                        "feature": feat,
                        "scale": scale,
                        "bin_index": bi,
                        "bin_low": bi * 0.25,
                        "bin_high": (bi + 1) * 0.25,
                        "count": 25 * (bi + 1),
                        "share": 0.1 * (bi + 1),
                        "denominator": 250,
                        "snapshot_at": snapshot_at,
                        "is_partial": False,
                    }
                )
    pd.DataFrame(hist_rows).to_csv(stage_dir / "local_wallet_histograms.csv", index=False)


class TestEdaProfile(unittest.TestCase):
    def test_palette_and_compact_formatting(self) -> None:
        self.assertEqual(set(COHORT_COLORS.keys()), set(COHORT_ORDER))
        self.assertEqual(format_compact(1_500_000), "1.50M")
        self.assertEqual(format_compact(25_400), "25.4K")
        self.assertEqual(format_compact(42), "42")

    def test_output_dir_resolution_no_double_nesting(self) -> None:
        base = Path("/tmp/eda_out")
        self.assertEqual(resolve_eda_profile_output_dir("raw", base), base / "raw")
        self.assertEqual(resolve_eda_profile_output_dir("raw", base / "raw"), base / "raw")
        with self.assertRaises(ValueError):
            resolve_eda_profile_output_dir("invalid", base)

    def test_raw_and_transformed_pipeline_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prof = root / "profile"
            out = root / "eda_out"
            _write_synthetic_stage(
                prof / "raw",
                snapshot_at="phase1_raw_illicit_20261123T043155Z+phase1_raw_licit_20261123T043744Z",
                include_mirror_tables=True,
                scale_factor=1.0,
            )
            # Transformed stage omits mirror-only db_overview/quality/nflow to test graceful skipping
            _write_synthetic_stage(
                prof / "transformed",
                snapshot_at="phase1_transformed_unified_20261127T120000Z",
                include_mirror_tables=False,
                scale_factor=0.85,
            )

            raw_manifest = run_stage_plots("raw", profile_base_dir=prof, output_base_dir=out, verbose=False)
            self.assertEqual(len(raw_manifest["generated"]), 11)
            self.assertEqual(len(raw_manifest["skipped"]), 0)
            for item in raw_manifest["generated"]:
                self.assertTrue((out / "raw" / item["figure"]).exists())
                self.assertTrue((out / "raw" / item["table"]).exists())

            tr_manifest = run_stage_plots("transformed", profile_base_dir=prof, output_base_dir=out, verbose=False)
            self.assertGreaterEqual(len(tr_manifest["generated"]), 8)
            self.assertTrue((out / "transformed" / "manifest.json").exists())
            parsed = json.loads((out / "transformed" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(parsed["stage"], "transformed")

            cmp_manifest = run_stage_plots("compare", profile_base_dir=prof, output_base_dir=out, verbose=False)
            self.assertEqual(len(cmp_manifest["generated"]), 1)
            self.assertTrue((out / "compare" / "12_raw_vs_transformed_shift.png").exists())
            self.assertTrue((out / "compare" / "12_raw_vs_transformed_shift.csv").exists())

    def test_compare_refuses_mixed_snapshot_phases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prof = Path(tmp) / "profile"
            _write_synthetic_stage(prof / "raw", snapshot_at="phase1_raw_illicit_20261123T043155Z")
            _write_synthetic_stage(prof / "transformed", snapshot_at="phase2_transformed_unified_20261201T000000Z")
            raw_b = load_profile_bundle("raw", profile_base_dir=prof)
            tr_b = load_profile_bundle("transformed", profile_base_dir=prof)

            with self.assertRaises(ValueError):
                validate_compare_compatibility(raw_b, tr_b)
            with self.assertRaises(ValueError):
                plot_raw_vs_transformed_shift(raw_b, tr_b, verbose=False)

            fig, _, summary = plot_raw_vs_transformed_shift(
                raw_b, tr_b, allow_cross_snapshot=True, verbose=False
            )
            self.assertIsInstance(fig, Figure)
            self.assertFalse(summary.empty)
            plt.close(fig)

    def test_compare_accepts_same_phase_with_mirror_timestamp_and_transform_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prof = Path(tmp) / "profile"
            out = Path(tmp) / "eda_out"
            _write_synthetic_stage(
                prof / "raw",
                snapshot_at="phase1_raw_illicit_20261123T043155Z+phase1_raw_licit_20261123T043744Z",
                include_mirror_tables=True,
            )
            # Overwrite raw pretransform_cleaning with mirror timestamp (simulates real raw/ dir)
            pt = pd.read_csv(prof / "raw" / "local_pretransform_cleaning.csv")
            pt["snapshot_at"] = "2026-11-23T03:10:00Z"
            pt.to_csv(prof / "raw" / "local_pretransform_cleaning.csv", index=False)

            # Build transformed stage with local_transform_columns.csv (no illicit/licit columns)
            tr_dir = prof / "transformed"
            _write_synthetic_stage(
                tr_dir,
                snapshot_at="phase1_transformed_transform_20261127T224625Z",
                include_mirror_tables=False,
            )
            (tr_dir / "local_illicit_columns.csv").unlink()
            pd.DataFrame(
                [
                    {
                        "schema": "transform",
                        "table": "cohort_wallet",
                        "column": "wallet_address",
                        "data_type": "VARCHAR",
                        "rows": 1000,
                        "nulls": 0,
                        "null_share": 0.0,
                        "distinct_approx": 1000,
                        "snapshot_at": "phase1_transformed_transform_20261127T224625Z",
                        "is_partial": False,
                    },
                    {
                        "schema": "transform",
                        "table": "wallet_features",
                        "column": "min_passthrough_sec_usdt",
                        "data_type": "DOUBLE",
                        "rows": 1000,
                        "nulls": 900,
                        "null_share": 0.9,
                        "distinct_approx": 90,
                        "snapshot_at": "phase1_transformed_transform_20261127T224625Z",
                        "is_partial": False,
                    },
                ]
            ).to_csv(tr_dir / "local_transform_columns.csv", index=False)

            tr_manifest = run_stage_plots("transformed", profile_base_dir=prof, output_base_dir=out, verbose=False)
            figs = {item["figure"] for item in tr_manifest["generated"]}
            self.assertIn("02_column_missingness_dtypes.png", figs)

            cmp_manifest = run_stage_plots("compare", profile_base_dir=prof, output_base_dir=out, verbose=False)
            self.assertEqual(len(cmp_manifest["generated"]), 1)
            self.assertTrue((out / "compare" / "12_raw_vs_transformed_shift.png").exists())


if __name__ == "__main__":
    unittest.main()
