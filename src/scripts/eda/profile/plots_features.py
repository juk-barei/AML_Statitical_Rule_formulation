"""Group C profile plots: full-frame H1–H6 feature eligibility, tails, quantiles, histograms."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from src.scripts.eda.profile.io import ProfileBundle
from src.scripts.eda.profile.style import (
    COHORT_COLORS,
    COHORT_LINESTYLES,
    COHORT_MARKERS,
    COHORT_ORDER,
    ELIGIBILITY_CMAP,
    INK_PRIMARY,
    INK_SECONDARY,
    STATUS_COLORS,
    apply_theme,
    format_compact,
    save_figure_and_table,
    stamp_figure,
)

HYPOTHESIS_ORDER: tuple[str, ...] = ("shared", "H1", "H2", "H3", "H4", "H5", "H6")

KEY_QUANTILE_FEATURES: tuple[str, ...] = (
    "total_tx_count",
    "usdt_volume",
    "min_passthrough_sec_usdt",
    "tx_lifetime_days",
    "burst_ratio_usdt",
    "out_degree_usdt",
    "fan_out_in_ratio_usdt",
    "jaccard_index",
    "cv_delta_t_all",
    "cv_delta_t_out",
)


def _ordered_features(df: pd.DataFrame) -> list[str]:
    hyp_rank = {h: i for i, h in enumerate(HYPOTHESIS_ORDER)}
    meta = df[["hypothesis", "feature"]].drop_duplicates().copy()
    meta["h_rank"] = meta["hypothesis"].map(lambda h: hyp_rank.get(str(h), 99))
    meta = meta.sort_values(["h_rank", "feature"])
    return meta["feature"].tolist()


def plot_feature_eligibility_nflow(
    bundle: ProfileBundle,
    *,
    out_path: Path | None = None,
    verbose: bool = True,
) -> tuple[Figure, Axes, pd.DataFrame]:
    """Plot 08: Heatmap of feature eligibility share (0–100%) annotated with exact n_eligible."""
    apply_theme()
    df = bundle.get("wallet_distributions").copy()
    df["eligible_share"] = pd.to_numeric(df["eligible_share"], errors="coerce").fillna(0.0)
    df["n_eligible"] = pd.to_numeric(df["n_eligible"], errors="coerce").fillna(0)

    features = _ordered_features(df)
    cohorts = [c for c in COHORT_ORDER if c in set(df["wallet_class"])]
    hyp_map = df.drop_duplicates("feature").set_index("feature")["hypothesis"].to_dict()

    share_mat = (
        df.pivot_table(index="feature", columns="wallet_class", values="eligible_share", aggfunc="first")
        .reindex(index=features, columns=cohorts)
        .fillna(0.0)
    )
    n_mat = (
        df.pivot_table(index="feature", columns="wallet_class", values="n_eligible", aggfunc="first")
        .reindex(index=features, columns=cohorts)
        .fillna(0.0)
    )

    fig_h = max(7.6, len(features) * 0.34 + 2.2)
    fig, ax = plt.subplots(figsize=(10.4, fig_h))
    im = ax.imshow(share_mat.to_numpy() * 100.0, cmap=ELIGIBILITY_CMAP, vmin=0.0, vmax=100.0, aspect="auto")

    for i, feat in enumerate(features):
        for j, coh in enumerate(cohorts):
            sh = float(share_mat.loc[feat, coh]) * 100.0
            ne = float(n_mat.loc[feat, coh])
            txt_color = "white" if sh >= 58.0 else INK_PRIMARY
            ax.text(
                j,
                i,
                f"{sh:.1f}%\n({format_compact(ne)})",
                ha="center",
                va="center",
                fontsize=7.3,
                color=txt_color,
                fontweight="bold" if sh < 50.0 else "normal",
            )

    # Group separator lines between hypotheses
    prev_h = None
    for i, feat in enumerate(features):
        cur_h = hyp_map.get(feat, "")
        if prev_h is not None and cur_h != prev_h:
            ax.axhline(i - 0.5, color="white", linewidth=2.0)
        prev_h = cur_h

    ax.set_xticks(np.arange(len(cohorts)))
    ax.set_xticklabels(cohorts, fontsize=9.8, fontweight="bold")
    ax.set_yticks(np.arange(len(features)))
    ax.set_yticklabels([f"[{hyp_map.get(f, '')}] {f}" for f in features], fontsize=8.3)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Eligible share of cohort (%)", fontsize=9.0)

    snap, is_partial = bundle.snapshot_for("wallet_distributions")
    stamp_figure(
        fig,
        title="08. Full-Frame H1–H6 Feature Eligibility Matrix",
        subtitle="Percentage and exact wallet denominator eligible per feature × cohort; low cells highlight structural eligibility filters.",
        stage=bundle.stage,
        snapshot_at=snap,
        denominator_text=f"Features: {len(features)} across {len(cohorts)} cohorts",
        is_partial=is_partial,
        top=0.92,
        bottom=0.05,
    )

    summary = df[
        ["hypothesis", "feature", "wallet_class", "n_cohort", "n_eligible", "eligible_share", "missing", "snapshot_at"]
    ].sort_values(["hypothesis", "feature", "wallet_class"])
    if verbose:
        low_cells = int((df["eligible_share"] < 0.5).sum())
        print(f"[08_feature_eligibility_nflow] stage={bundle.stage} features={len(features)} cells_under_50pct={low_cells}")
    save_figure_and_table(fig, summary, out_path)
    return fig, ax, summary


def plot_feature_skew_zero_tail(
    bundle: ProfileBundle,
    *,
    out_path: Path | None = None,
    verbose: bool = True,
) -> tuple[Figure, np.ndarray, pd.DataFrame]:
    """Plot 09: Three-column diagnostic of zero-mass, tail ratio (p99/p50), and skewness."""
    apply_theme()
    df = bundle.get("wallet_distributions").copy()
    # Exclude binary pass indicators (pass_0_1) so continuous/count features stay readable.
    cont = df[~df["feature"].astype(str).str.contains("_pass")].copy()
    if cont.empty:
        cont = df.copy()
    for col in ("zero_share", "p99_p50_ratio", "skewness"):
        cont[col] = pd.to_numeric(cont[col], errors="coerce")

    features = _ordered_features(cont)
    cohorts = [c for c in COHORT_ORDER if c in set(cont["wallet_class"])]
    hyp_map = cont.drop_duplicates("feature").set_index("feature")["hypothesis"].to_dict()

    fig_h = max(7.4, len(features) * 0.34 + 2.0)
    fig, axes = plt.subplots(1, 3, figsize=(15.0, fig_h), sharey=True)
    axes_arr = np.atleast_1d(axes)
    y_map = {f: i for i, f in enumerate(features)}

    offsets = np.linspace(-0.22, 0.22, max(len(cohorts), 1))
    for coh, off in zip(cohorts, offsets, strict=True):
        sub = cont[cont["wallet_class"] == coh]
        color = COHORT_COLORS.get(coh, STATUS_COLORS["neutral"])
        marker = COHORT_MARKERS.get(coh, "o")
        ys = [y_map[f] + off for f in sub["feature"] if f in y_map]
        sub = sub[sub["feature"].isin(y_map)]

        # Panel 0: zero share (%)
        axes_arr[0].scatter(
            sub["zero_share"] * 100.0,
            ys,
            color=color,
            marker=marker,
            s=40,
            alpha=0.9,
            label=coh,
            edgecolors="white",
            linewidths=0.4,
        )
        # Panel 1: p99/p50 ratio (log10)
        ratio_vals = sub["p99_p50_ratio"].where(sub["p99_p50_ratio"] > 0)
        axes_arr[1].scatter(
            ratio_vals,
            ys,
            color=color,
            marker=marker,
            s=40,
            alpha=0.9,
            edgecolors="white",
            linewidths=0.4,
        )
        # Panel 2: |skewness| (symlog for negative/extreme skew)
        axes_arr[2].scatter(
            sub["skewness"],
            ys,
            color=color,
            marker=marker,
            s=40,
            alpha=0.9,
            edgecolors="white",
            linewidths=0.4,
        )

    axes_arr[0].set_xlim(-3, 105)
    axes_arr[0].set_xlabel("Zero-value share (%)")
    axes_arr[0].set_title("A. Zero Mass", loc="left")

    axes_arr[1].set_xscale("log")
    axes_arr[1].axvline(10.0, color=STATUS_COLORS["warn"], linestyle="--", linewidth=1.0, alpha=0.8)
    axes_arr[1].set_xlabel("p99 / p50 tail ratio (log10 scale; dashed=10x)")
    axes_arr[1].set_title("B. Heavy-Tail Ratio (p99 / p50)", loc="left")

    axes_arr[2].set_xscale("symlog", linthresh=2.0)
    axes_arr[2].axvline(2.0, color=STATUS_COLORS["warn"], linestyle="--", linewidth=1.0, alpha=0.8)
    axes_arr[2].axvline(-2.0, color=STATUS_COLORS["warn"], linestyle="--", linewidth=1.0, alpha=0.8)
    axes_arr[2].set_xlabel("Skewness (symlog; dashed = ±2 threshold)")
    axes_arr[2].set_title("C. Distributional Skewness", loc="left")

    axes_arr[0].set_yticks(np.arange(len(features)))
    axes_arr[0].set_yticklabels([f"[{hyp_map.get(f, '')}] {f}" for f in features], fontsize=8.3)
    axes_arr[0].invert_yaxis()
    axes_arr[0].legend(loc="lower right", title="Cohort", frameon=True, fontsize=8.2)

    for ax in axes_arr:
        ax.grid(axis="x", alpha=0.7)
        ax.grid(axis="y", alpha=0.35, linestyle=":")

    snap, is_partial = bundle.snapshot_for("wallet_distributions")
    stamp_figure(
        fig,
        title="09. Heavy-Tail, Zero-Inflation & Skewness Diagnostics (H1–H6)",
        subtitle="Justifies stateless log1p in L3 and non-parametric / robust rank inference over raw Gaussian ANOVA.",
        stage=bundle.stage,
        snapshot_at=snap,
        denominator_text=f"Continuous/count features: {len(features)}",
        is_partial=is_partial,
        top=0.91,
        bottom=0.07,
    )
    fig.subplots_adjust(wspace=0.12)

    summary = cont[
        ["hypothesis", "feature", "wallet_class", "n_eligible", "zero_share", "p50", "p99", "p99_p50_ratio", "skewness", "recommended_scale"]
    ].sort_values(["hypothesis", "feature", "wallet_class"])
    if verbose:
        extreme = int((cont["skewness"].abs() > 2.0).sum())
        print(f"[09_feature_skew_zero_tail] stage={bundle.stage} features={len(features)} cells_abs_skew_gt_2={extreme}")
    save_figure_and_table(fig, summary, out_path)
    return fig, axes_arr, summary


def plot_feature_quantile_ranges(
    bundle: ProfileBundle,
    *,
    features: tuple[str, ...] | None = None,
    out_path: Path | None = None,
    verbose: bool = True,
) -> tuple[Figure, np.ndarray, pd.DataFrame]:
    """Plot 10: Quantile-interval panels (p10–p90 whisker, IQR bar, p50 dot, mean diamond)."""
    apply_theme()
    df = bundle.get("wallet_distributions").copy()
    avail = set(df["feature"].astype(str).unique())
    selected = [f for f in (features or KEY_QUANTILE_FEATURES) if f in avail]
    if not selected:
        selected = _ordered_features(df)[:8]

    cohorts = [c for c in COHORT_ORDER if c in set(df["wallet_class"])]
    ncols = 2
    nrows = int(np.ceil(len(selected) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(13.6, 2.75 * nrows))
    axes_arr = np.atleast_1d(axes).ravel()

    q_cols = ("p10", "p25", "p50", "p75", "p90", "mean")
    for col in q_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for ax, feat in zip(axes_arr, selected, strict=False):
        sub = df[df["feature"] == feat].set_index("wallet_class")
        hyp = str(sub["hypothesis"].iloc[0]) if not sub.empty else ""
        max_val = float(sub[["p90", "mean"]].max().max()) if not sub.empty else 1.0
        min_pos = float(sub[["p10", "p25", "p50", "p75", "p90"]].replace(0, np.nan).min().min())
        use_log = bool(np.isfinite(max_val) and np.isfinite(min_pos) and max_val > 25.0 and (max_val / max(min_pos, 1e-6)) > 20.0)

        for yi, coh in enumerate(cohorts):
            if coh not in sub.index:
                continue
            row = sub.loc[coh]
            color = COHORT_COLORS.get(coh, STATUS_COLORS["neutral"])
            p10, p25, p50, p75, p90, mean_v = (
                float(row["p10"]),
                float(row["p25"]),
                float(row["p50"]),
                float(row["p75"]),
                float(row["p90"]),
                float(row["mean"]),
            )
            if use_log:
                eps = 1e-3 if min_pos < 1.0 else 0.1
                p10, p25, p50, p75, p90, mean_v = [max(v, eps) for v in (p10, p25, p50, p75, p90, mean_v)]

            ax.hlines(yi, p10, p90, color=color, linewidth=1.8, alpha=0.55)
            ax.hlines(yi, p25, p75, color=color, linewidth=7.5, alpha=0.88)
            ax.scatter([p50], [yi], color="white", edgecolors=color, s=55, linewidth=1.8, zorder=4)
            ax.scatter([mean_v], [yi], color=INK_PRIMARY, marker="D", s=30, zorder=5)

        if use_log:
            ax.set_xscale("log")
        ax.set_yticks(np.arange(len(cohorts)))
        ax.set_yticklabels(cohorts, fontsize=8.4)
        ax.invert_yaxis()
        ax.set_title(f"[{hyp}] {feat}" + (" (log10)" if use_log else ""), loc="left", fontsize=10.0)
        ax.grid(axis="x", alpha=0.7)
        ax.grid(axis="y", visible=False)

    for extra_ax in axes_arr[len(selected) :]:
        extra_ax.set_visible(False)

    snap, is_partial = bundle.snapshot_for("wallet_distributions")
    stamp_figure(
        fig,
        title="10. Full-Frame Feature Quantile Ranges by Cohort",
        subtitle="Whisker = p10–p90, thick bar = IQR (p25–p75), white circle = median (p50), dark diamond = mean.",
        stage=bundle.stage,
        snapshot_at=snap,
        denominator_text=f"Selected features: {len(selected)} (computed over full SQL/DuckDB frame)",
        is_partial=is_partial,
        top=0.92,
        bottom=0.05,
    )
    fig.subplots_adjust(hspace=0.45, wspace=0.22)

    summary = df[df["feature"].isin(selected)][
        ["hypothesis", "feature", "wallet_class", "n_eligible", "p10", "p25", "p50", "p75", "p90", "p99", "mean", "stddev"]
    ].sort_values(["feature", "wallet_class"])
    if verbose:
        print(f"[10_feature_quantile_ranges] stage={bundle.stage} panels={len(selected)}")
    save_figure_and_table(fig, summary, out_path)
    return fig, axes_arr, summary


def _format_bucket_label(low: float, high: float, scale: str) -> str:
    if scale == "seconds_buckets":
        def _sec(v: float) -> str:
            if v >= 1e11:
                return "∞"
            if v >= 2_592_000:
                return f"{int(round(v / 2_592_000))}mo"
            if v >= 604_800:
                return f"{int(round(v / 604_800))}w"
            if v >= 86_400:
                return f"{int(round(v / 86_400))}d"
            if v >= 3_600:
                return f"{int(round(v / 3_600))}h"
            if v >= 60:
                return f"{int(round(v / 60))}m"
            return f"{int(v)}s"
        return f"≥{_sec(low)}" if high >= 1e11 else f"{_sec(low)}–{_sec(high)}"
    if scale == "usd_log10_buckets":
        return f"≥${format_compact(low)}" if high >= 1e11 else f"${format_compact(low)}–{format_compact(high)}"
    if high >= 1e8:
        return f"≥{format_compact(low)}"
    if low == 0 and high <= 1e-6:
        return "=0"
    if 0 < low <= 1e-6:
        return f">0–{high:g}"
    clean_high = 1.0 if abs(high - 1.0001) < 1e-5 else high
    return f"{low:g}–{clean_high:g}"


def plot_feature_histograms_grid(
    bundle: ProfileBundle,
    *,
    out_path: Path | None = None,
    verbose: bool = True,
) -> tuple[Figure, np.ndarray, pd.DataFrame]:
    """Plot 11: Overlaid full-frame pre-binned share histograms across all 4 cohorts."""
    apply_theme()
    df = bundle.get("wallet_histograms").copy()
    for col in ("bin_index", "bin_low", "bin_high", "count", "share", "denominator"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    features = sorted(df["feature"].astype(str).unique().tolist())
    cohorts = [c for c in COHORT_ORDER if c in set(df["wallet_class"])]

    ncols = 2
    nrows = int(np.ceil(len(features) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(14.2, 3.3 * nrows))
    axes_arr = np.atleast_1d(axes).ravel()

    for ax, feat in zip(axes_arr, features, strict=False):
        fdf = df[df["feature"] == feat].sort_values("bin_index")
        scale = str(fdf["scale"].iloc[0])
        ref_bins = (
            fdf[["bin_index", "bin_low", "bin_high"]]
            .drop_duplicates("bin_index")
            .sort_values("bin_index")
        )
        bin_indices = ref_bins["bin_index"].to_numpy()

        for coh in cohorts:
            cdf = fdf[fdf["wallet_class"] == coh].set_index("bin_index")
            y_vals = [float(cdf.loc[b, "share"]) * 100.0 if b in cdf.index else 0.0 for b in bin_indices]
            color = COHORT_COLORS.get(coh, STATUS_COLORS["neutral"])
            ls = COHORT_LINESTYLES.get(coh, "-")
            mk = COHORT_MARKERS.get(coh, "o")
            ax.plot(
                bin_indices,
                y_vals,
                color=color,
                linestyle=ls,
                marker=mk,
                markersize=3.8,
                linewidth=1.9,
                label=coh,
                alpha=0.92,
            )
            if coh == "illicit":
                ax.fill_between(bin_indices, 0, y_vals, color=color, alpha=0.08)

        labels = [
            _format_bucket_label(float(r.bin_low), float(r.bin_high), scale)
            for r in ref_bins.itertuples(index=False)
        ]
        step = 2 if len(labels) > 11 else 1
        ax.set_xticks(bin_indices[::step])
        ax.set_xticklabels(labels[::step], rotation=35, ha="right", fontsize=7.5)
        ax.set_ylabel("Cohort share (%)")
        ax.set_title(f"{feat}  [{scale}]", loc="left", fontsize=10.0)
        ax.grid(axis="x", alpha=0.45)

    axes_arr[0].legend(loc="upper right", title="Cohort", fontsize=8.0, ncol=2)
    for extra_ax in axes_arr[len(features) :]:
        extra_ax.set_visible(False)

    snap, is_partial = bundle.snapshot_for("wallet_histograms")
    stamp_figure(
        fig,
        title="11. Full-Frame Pre-Binned Feature Distributions Across Cohorts",
        subtitle="Overlaid cohort shares with redundant hue + linestyle + marker encoding (computed from 100% of eligible wallets).",
        stage=bundle.stage,
        snapshot_at=snap,
        denominator_text=f"Pre-binned features: {len(features)} | Total histogram rows: {len(df)}",
        is_partial=is_partial,
        top=0.90,
        bottom=0.09,
    )
    fig.subplots_adjust(hspace=0.55, wspace=0.18)

    summary = df[
        ["feature", "scale", "wallet_class", "bin_index", "bin_low", "bin_high", "count", "share", "denominator"]
    ].sort_values(["feature", "wallet_class", "bin_index"])
    if verbose:
        print(f"[11_feature_histograms_grid] stage={bundle.stage} features={len(features)} bins={len(df)}")
    save_figure_and_table(fig, summary, out_path)
    return fig, axes_arr, summary
