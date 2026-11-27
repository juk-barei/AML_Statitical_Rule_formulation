"""Group D profile plot: raw vs transformed before/after stage shift comparison."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from src.scripts.eda.profile.io import ProfileBundle, validate_compare_compatibility
from src.scripts.eda.profile.style import (
    COHORT_COLORS,
    COHORT_ORDER,
    DELTA_CMAP,
    INK_PRIMARY,
    INK_SECONDARY,
    STATUS_COLORS,
    apply_theme,
    format_compact,
    save_figure_and_table,
    stamp_figure,
)


def plot_raw_vs_transformed_shift(
    raw_bundle: ProfileBundle,
    transformed_bundle: ProfileBundle,
    *,
    allow_cross_snapshot: bool = False,
    out_path: Path | None = None,
    verbose: bool = True,
) -> tuple[Figure, np.ndarray, pd.DataFrame]:
    """Plot 12: Before/after raw vs transformed delta across eligibility, medians, and anomalies."""
    apply_theme()
    raw_snap, tr_snap = validate_compare_compatibility(
        raw_bundle,
        transformed_bundle,
        allow_cross_snapshot=allow_cross_snapshot,
    )

    if not (raw_bundle.has("wallet_distributions") and transformed_bundle.has("wallet_distributions")):
        raise ValueError("Both raw and transformed bundles require wallet_distributions for comparison.")

    r_dist = raw_bundle.get("wallet_distributions").copy()
    t_dist = transformed_bundle.get("wallet_distributions").copy()
    for col in ("n_cohort", "n_eligible", "eligible_share", "p50", "p99", "skewness"):
        r_dist[col] = pd.to_numeric(r_dist[col], errors="coerce")
        t_dist[col] = pd.to_numeric(t_dist[col], errors="coerce")

    merged = r_dist.merge(
        t_dist,
        on=["wallet_class", "feature"],
        how="inner",
        suffixes=("_raw", "_tr"),
    )
    if merged.empty:
        raise ValueError("No overlapping (wallet_class, feature) rows between raw and transformed profiles.")

    merged["elig_pp_delta"] = (merged["eligible_share_tr"] - merged["eligible_share_raw"]) * 100.0
    merged["p50_pct_delta"] = np.where(
        merged["p50_raw"].abs() > 1e-12,
        (merged["p50_tr"] - merged["p50_raw"]) / merged["p50_raw"].abs() * 100.0,
        0.0,
    )
    merged["skew_delta"] = merged["skewness_tr"] - merged["skewness_raw"]

    cohorts = [c for c in COHORT_ORDER if c in set(merged["wallet_class"])]
    features = sorted(merged["feature"].astype(str).unique().tolist())

    fig, axes = plt.subplots(1, 3, figsize=(15.6, max(6.4, len(features) * 0.28 + 2.0)))
    axes_arr = np.atleast_1d(axes)

    # Panel A: Eligibility share delta heatmap (percentage points)
    ax0 = axes_arr[0]
    mat = (
        merged.pivot_table(index="feature", columns="wallet_class", values="elig_pp_delta", aggfunc="first")
        .reindex(index=features, columns=cohorts)
        .fillna(0.0)
    )
    vmax = max(float(np.abs(mat.to_numpy()).max()), 1.0)
    im = ax0.imshow(mat.to_numpy(), cmap=DELTA_CMAP, vmin=-vmax, vmax=vmax, aspect="auto")
    for i, feat in enumerate(features):
        for j, coh in enumerate(cohorts):
            val = float(mat.loc[feat, coh])
            ax0.text(j, i, f"{val:+.1f}pp", ha="center", va="center", fontsize=7.0, color=INK_PRIMARY)
    ax0.set_xticks(np.arange(len(cohorts)))
    ax0.set_xticklabels(cohorts, rotation=25, ha="right", fontsize=8.5)
    ax0.set_yticks(np.arange(len(features)))
    ax0.set_yticklabels(features, fontsize=7.8)
    ax0.set_title("A. Eligibility Shift (pp)", loc="left")
    ax0.grid(False)
    fig.colorbar(im, ax=ax0, fraction=0.045, pad=0.02)

    # Panel B: Median (p50) relative % shift by cohort for top shifted features
    ax1 = axes_arr[1]
    top_feats = (
        merged.assign(abs_p50=merged["p50_pct_delta"].abs())
        .groupby("feature")["abs_p50"]
        .max()
        .sort_values(ascending=False)
        .head(12)
        .index.tolist()
    )
    sub_b = merged[merged["feature"].isin(top_feats)]
    y_map = {f: i for i, f in enumerate(top_feats)}
    offsets = np.linspace(-0.22, 0.22, max(len(cohorts), 1))
    ax1.axvline(0.0, color=INK_SECONDARY, linewidth=1.0, linestyle="--")
    for coh, off in zip(cohorts, offsets, strict=True):
        csub = sub_b[sub_b["wallet_class"] == coh]
        ax1.scatter(
            csub["p50_pct_delta"],
            [y_map[f] + off for f in csub["feature"]],
            color=COHORT_COLORS.get(coh, STATUS_COLORS["neutral"]),
            s=42,
            label=coh,
            alpha=0.9,
            edgecolors="white",
            linewidths=0.4,
        )
    ax1.set_yticks(np.arange(len(top_feats)))
    ax1.set_yticklabels(top_feats, fontsize=8.2)
    ax1.invert_yaxis()
    ax1.set_xlabel("Median (p50) relative change (%)")
    ax1.set_title("B. Top Median Shifts (Raw → Transformed)", loc="left")
    ax1.legend(loc="lower right", fontsize=8.0)

    # Panel C: Cleaning anomaly count before vs after (if available in both) or cohort retention
    ax2 = axes_arr[2]
    if raw_bundle.has("pretransform_cleaning") and transformed_bundle.has("pretransform_cleaning"):
        rc = raw_bundle.get("pretransform_cleaning").copy()
        tc = transformed_bundle.get("pretransform_cleaning").copy()
        rc["count"] = pd.to_numeric(rc["count"], errors="coerce").fillna(0)
        tc["count"] = pd.to_numeric(tc["count"], errors="coerce").fillna(0)
        cm = rc[rc["section"].isin(["amount_flag", "timestamp_flag"]) & (rc["category"] != "ok")].merge(
            tc[tc["section"].isin(["amount_flag", "timestamp_flag"]) & (tc["category"] != "ok")],
            on=["section", "schema", "token_symbol", "category"],
            how="outer",
            suffixes=("_raw", "_tr"),
        ).fillna(0)
        cm["label"] = cm["schema"].astype(str) + " " + cm["token_symbol"].astype(str) + " | " + cm["category"].astype(str)
        cm = cm.sort_values("count_raw", ascending=True).tail(10)
        y2 = np.arange(len(cm))
        ax2.barh(y2 - 0.17, cm["count_raw"].clip(lower=0.5), height=0.32, color=STATUS_COLORS["error"], alpha=0.82, label="raw")
        ax2.barh(y2 + 0.17, cm["count_tr"].clip(lower=0.5), height=0.32, color=STATUS_COLORS["retained"], alpha=0.92, label="transformed")
        ax2.set_xscale("log")
        ax2.set_yticks(y2)
        ax2.set_yticklabels(cm["label"], fontsize=7.8)
        ax2.set_xlabel("Flagged rows (log10 scale)")
        ax2.set_title("C. Cleaning Flag Reduction", loc="left")
        ax2.legend(loc="lower right", fontsize=8.0)
    else:
        coh_tot = (
            merged.drop_duplicates("wallet_class")[["wallet_class", "n_cohort_raw", "n_cohort_tr"]]
            .set_index("wallet_class")
            .reindex(cohorts)
        )
        y2 = np.arange(len(coh_tot))
        ax2.barh(y2 - 0.17, coh_tot["n_cohort_raw"], height=0.32, color=STATUS_COLORS["neutral"], alpha=0.65, label="raw")
        ax2.barh(y2 + 0.17, coh_tot["n_cohort_tr"], height=0.32, color=STATUS_COLORS["retained"], alpha=0.92, label="transformed")
        for yi, row in zip(y2, coh_tot.itertuples(), strict=True):
            delta = int(row.n_cohort_tr - row.n_cohort_raw)
            ax2.text(max(row.n_cohort_raw, row.n_cohort_tr) * 1.05, yi, f"Δ={delta:+,}", va="center", fontsize=8.0)
        ax2.set_xscale("log")
        ax2.set_yticks(y2)
        ax2.set_yticklabels(coh_tot.index, fontsize=8.8)
        ax2.invert_yaxis()
        ax2.set_xlabel("Cohort wallets (log10 scale)")
        ax2.set_title("C. Cohort Size Reconciliation", loc="left")
        ax2.legend(loc="lower right", fontsize=8.0)

    is_partial = raw_bundle.metadata.is_partial or transformed_bundle.metadata.is_partial
    stamp_figure(
        fig,
        title="12. Stage Comparison: Raw vs. Transformed Profile Shift",
        subtitle="Audit of eligibility retention, median shifts, and anomaly removal across the same snapshot family.",
        stage="compare (raw → transformed)",
        snapshot_at=f"raw={raw_snap} | tr={tr_snap}",
        denominator_text=f"Matched (cohort × feature) cells: {len(merged)}",
        is_partial=is_partial,
        top=0.90,
        bottom=0.09,
    )
    fig.subplots_adjust(wspace=0.45)

    summary = merged[
        [
            "wallet_class",
            "feature",
            "n_cohort_raw",
            "n_cohort_tr",
            "n_eligible_raw",
            "n_eligible_tr",
            "elig_pp_delta",
            "p50_raw",
            "p50_tr",
            "p50_pct_delta",
            "skew_delta",
        ]
    ].sort_values(["feature", "wallet_class"])
    if verbose:
        max_pp = float(summary["elig_pp_delta"].abs().max())
        print(f"[12_raw_vs_transformed_shift] cells={len(summary)} max_abs_elig_pp_delta={max_pp:.2f}")
    save_figure_and_table(fig, summary, out_path)
    return fig, axes_arr, summary
