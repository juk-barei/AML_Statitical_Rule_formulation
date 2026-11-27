"""CLI entry point for stage-aware EDA profile visualizations.

Generates paired PNG figures, supporting CSV tables, and a provenance manifest
under ``outputs/eda/profile/{raw,transformed,compare}/`` from compact ETL
profile CSVs in ``outputs/etl/transform/profile/{raw,transformed}/``.

Examples:
    python -m src.scripts.eda.profile.main --stage raw
    python -m src.scripts.eda.profile.main --stage transformed --groups schema,features
    python -m src.scripts.eda.profile.main --stage compare
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from src.scripts.eda.profile.io import (
    VALID_EDA_STAGES,
    ProfileBundle,
    load_profile_bundle,
    resolve_eda_profile_output_dir,
)
from src.scripts.eda.profile.plots_cohort_frame import (
    plot_cohort_composition_nflow,
    plot_cross_schema_overlap,
    plot_hop_and_seed_structure,
)
from src.scripts.eda.profile.plots_compare import plot_raw_vs_transformed_shift
from src.scripts.eda.profile.plots_features import (
    plot_feature_eligibility_nflow,
    plot_feature_histograms_grid,
    plot_feature_quantile_ranges,
    plot_feature_skew_zero_tail,
)
from src.scripts.eda.profile.plots_schema_quality import (
    plot_column_missingness_dtypes,
    plot_quality_and_cleaning_anomalies,
    plot_table_overview_coverage,
    plot_tx_volume_by_year,
)

PlotSpec = tuple[str, str, tuple[str, ...], Callable[..., Any]]

STAGE_PLOT_SPECS: tuple[PlotSpec, ...] = (
    ("schema", "01_table_overview_coverage.png", ("illicit_db_overview",), plot_table_overview_coverage),
    ("schema", "02_column_missingness_dtypes.png", ("illicit_columns",), plot_column_missingness_dtypes),
    ("schema", "03_quality_and_cleaning_anomalies.png", ("pretransform_cleaning",), plot_quality_and_cleaning_anomalies),
    ("schema", "04_tx_volume_by_year.png", ("pretransform_cleaning",), plot_tx_volume_by_year),
    ("cohort", "05_cohort_composition_nflow.png", ("sampling_frame",), plot_cohort_composition_nflow),
    ("cohort", "06_cross_schema_overlap.png", ("group_overlap",), plot_cross_schema_overlap),
    ("cohort", "07_hop_and_seed_structure.png", ("sampling_frame",), plot_hop_and_seed_structure),
    ("features", "08_feature_eligibility_nflow.png", ("wallet_distributions",), plot_feature_eligibility_nflow),
    ("features", "09_feature_skew_zero_tail.png", ("wallet_distributions",), plot_feature_skew_zero_tail),
    ("features", "10_feature_quantile_ranges.png", ("wallet_distributions",), plot_feature_quantile_ranges),
    ("features", "11_feature_histograms_grid.png", ("wallet_histograms",), plot_feature_histograms_grid),
)

VALID_GROUPS: tuple[str, ...] = ("all", "schema", "cohort", "features")


def _can_run_plot(bundle: ProfileBundle, filename: str, required_hint: tuple[str, ...]) -> bool:
    if filename == "01_table_overview_coverage.png":
        return bundle.has("illicit_db_overview") or bundle.has("licit_db_overview")
    if filename == "02_column_missingness_dtypes.png":
        return bundle.has("illicit_columns") or bundle.has("licit_columns")
    if filename == "03_quality_and_cleaning_anomalies.png":
        return bundle.has("quality") or bundle.has("pretransform_cleaning")
    if filename == "05_cohort_composition_nflow.png":
        return bundle.has("sampling_frame") or bundle.has("cohort_counts")
    if filename == "06_cross_schema_overlap.png":
        return bundle.has("group_overlap") or bundle.has("pretransform_cleaning")
    return bundle.has(*required_hint)


def run_stage_plots(
    stage: str,
    *,
    groups: Sequence[str] = ("all",),
    profile_base_dir: Path | None = None,
    output_base_dir: Path | None = None,
    allow_cross_snapshot: bool = False,
    verbose: bool = True,
) -> dict[str, Any]:
    """Run requested plot groups for 'raw', 'transformed', or 'compare' stage."""
    if stage not in VALID_EDA_STAGES:
        raise ValueError(f"stage must be one of {VALID_EDA_STAGES}, got {stage!r}")

    out_dir = resolve_eda_profile_output_dir(stage, base_dir=output_base_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    generated: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    if stage == "compare":
        raw_bundle = load_profile_bundle("raw", profile_base_dir=profile_base_dir)
        tr_bundle = load_profile_bundle("transformed", profile_base_dir=profile_base_dir)
        out_path = out_dir / "12_raw_vs_transformed_shift.png"
        fig, _, summary = plot_raw_vs_transformed_shift(
            raw_bundle,
            tr_bundle,
            allow_cross_snapshot=allow_cross_snapshot,
            out_path=out_path,
            verbose=verbose,
        )
        plt.close(fig)
        generated.append(
            {
                "group": "compare",
                "figure": out_path.name,
                "table": out_path.with_suffix(".csv").name,
                "summary_rows": int(len(summary)),
            }
        )
        manifest = {
            "stage": "compare",
            "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "raw_source_dir": str(raw_bundle.source_dir),
            "transformed_source_dir": str(tr_bundle.source_dir),
            "raw_snapshot_at": raw_bundle.metadata.snapshot_at,
            "transformed_snapshot_at": tr_bundle.metadata.snapshot_at,
            "is_partial": raw_bundle.metadata.is_partial or tr_bundle.metadata.is_partial,
            "generated": generated,
            "skipped": skipped,
        }
    else:
        bundle = load_profile_bundle(stage, profile_base_dir=profile_base_dir)
        active_groups = {"schema", "cohort", "features"} if "all" in groups else set(groups)
        for group, filename, req_hint, fn in STAGE_PLOT_SPECS:
            if group not in active_groups:
                continue
            if not _can_run_plot(bundle, filename, req_hint):
                skipped.append({"group": group, "figure": filename, "reason": f"missing inputs ({', '.join(req_hint)})"})
                if verbose:
                    print(f"[eda.profile:{stage}] skipped {filename} (missing required CSVs)")
                continue
            out_path = out_dir / filename
            fig, _, summary = fn(bundle, out_path=out_path, verbose=verbose)
            plt.close(fig)
            generated.append(
                {
                    "group": group,
                    "figure": out_path.name,
                    "table": out_path.with_suffix(".csv").name,
                    "summary_rows": int(len(summary)),
                }
            )
        meta = bundle.metadata
        manifest = {
            "stage": stage,
            "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_dir": str(meta.source_dir),
            "snapshot_at": meta.snapshot_at,
            "is_partial": meta.is_partial,
            "loaded_tables": list(meta.loaded_tables),
            "missing_tables": list(meta.missing_tables),
            "generated": generated,
            "skipped": skipped,
        }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if verbose:
        print(
            f"[eda.profile:{stage}] generated={len(generated)} skipped={len(skipped)} "
            f"manifest={manifest_path}"
        )
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=VALID_EDA_STAGES,
        default="raw",
        help="Profile stage to plot: raw, transformed, or compare.",
    )
    parser.add_argument(
        "--groups",
        default="all",
        help="Comma-separated plot groups for raw/transformed: all, schema, cohort, features.",
    )
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=None,
        help="Override base directory for ETL profile CSVs (default: outputs/etl/transform/profile).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override base directory for EDA profile outputs (default: outputs/eda/profile).",
    )
    parser.add_argument(
        "--allow-cross-snapshot",
        action="store_true",
        help="Allow compare mode across differing snapshot phases (not recommended for audits).",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout summary lines.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    groups = [g.strip().lower() for g in args.groups.split(",") if g.strip()]
    unknown = [g for g in groups if g not in VALID_GROUPS]
    if unknown:
        raise ValueError(f"Unknown --groups values: {unknown}. Choose from {VALID_GROUPS}.")
    run_stage_plots(
        args.stage,
        groups=groups,
        profile_base_dir=args.profile_dir,
        output_base_dir=args.output_dir,
        allow_cross_snapshot=args.allow_cross_snapshot,
        verbose=not args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
