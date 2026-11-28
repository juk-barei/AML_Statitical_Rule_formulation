"""Group B profile plots: cohort composition, n-flow, overlap, and hop/seed frame."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

from src.scripts.eda.profile.io import ProfileBundle
from src.scripts.eda.profile.style import (
    COHORT_COLORS,
    COHORT_ORDER,
    INK_PRIMARY,
    INK_SECONDARY,
    SCHEMA_COLORS,
    STATUS_COLORS,
    apply_theme,
    format_compact,
    save_figure_and_table,
    stamp_figure,
)


def plot_cohort_composition_nflow(
    bundle: ProfileBundle,
    *,
    out_path: Path | None = None,
    verbose: bool = True,
) -> tuple[Figure, np.ndarray, pd.DataFrame]:
    """Plot 05: Canonical 4-cohort counts/shares (left) and priority n-flow waterfall (right)."""
    apply_theme()
    has_sf = bundle.has("sampling_frame")
    has_cc = bundle.has("cohort_counts")
    has_nf = bundle.has("nflow")
    if not (has_sf or has_cc):
        raise ValueError("Missing both sampling_frame and cohort_counts in profile bundle.")

    if has_sf:
        sf = bundle.get("sampling_frame").copy()
        cu = sf[sf["section"] == "cohort_universe"].copy()
        cu["value"] = pd.to_numeric(cu["value"], errors="coerce").fillna(0)
        piv = cu.pivot_table(index="group", columns="metric", values="value", aggfunc="first").fillna(0)
        cohort_df = pd.DataFrame(
            {
                "wallet_class": [g for g in COHORT_ORDER if g in piv.index],
            }
        )
        cohort_df["wallets_total"] = cohort_df["wallet_class"].map(piv.get("wallets_total", 0))
        cohort_df["wallets_in_accounts"] = cohort_df["wallet_class"].map(piv.get("wallets_in_accounts", cohort_df["wallets_total"]))
        cohort_df["wallets_hop_only"] = cohort_df["wallet_class"].map(piv.get("wallets_hop_only", 0))
    else:
        cc = bundle.get("cohort_counts").copy()
        cc["count"] = pd.to_numeric(cc["count"], errors="coerce").fillna(0)
        cohort_df = cc.rename(columns={"group": "wallet_class", "count": "wallets_total"}).copy()
        cohort_df["wallets_in_accounts"] = cohort_df["wallets_total"]
        cohort_df["wallets_hop_only"] = 0.0
        cohort_df["wallet_class"] = pd.Categorical(cohort_df["wallet_class"], categories=list(COHORT_ORDER), ordered=True)
        cohort_df = cohort_df.sort_values("wallet_class").reset_index(drop=True)

    universe_total = float(cohort_df["wallets_total"].sum())
    cohort_df["share"] = cohort_df["wallets_total"] / max(universe_total, 1.0)

    n_panels = 2 if has_nf else 1
    fig, axes = plt.subplots(1, n_panels, figsize=(6.8 * n_panels, 5.8))
    axes_arr = np.atleast_1d(axes)

    ax0 = axes_arr[0]
    y = np.arange(len(cohort_df))
    colors = [COHORT_COLORS.get(str(g), STATUS_COLORS["neutral"]) for g in cohort_df["wallet_class"]]
    bars = ax0.barh(y, cohort_df["wallets_total"], color=colors, height=0.58, edgecolor="white")
    for bar, row in zip(bars, cohort_df.itertuples(index=False), strict=True):
        hop_note = f"  (+{format_compact(row.wallets_hop_only)} hop-only)" if row.wallets_hop_only > 0 else ""
        ax0.text(
            row.wallets_total * 1.15,
            bar.get_y() + bar.get_height() / 2.0,
            f"{int(row.wallets_total):,} ({row.share * 100:.2f}%){hop_note}",
            va="center",
            ha="left",
            fontsize=8.3,
            color=INK_PRIMARY,
            fontweight="bold" if row.wallet_class == "illicit" else "normal",
        )
    ax0.set_xscale("log")
    ax0.set_xlim(1_000, max(cohort_df["wallets_total"].max(), 10_000) * 160.0)
    ax0.set_yticks(y)
    ax0.set_yticklabels(cohort_df["wallet_class"], fontsize=9.5, fontweight="bold")
    ax0.invert_yaxis()
    ax0.set_xlabel("Distinct wallets (log10 scale)")
    ax0.set_title("A. Cohort Universe Composition (Priority Contract)", loc="left")
    ax0.grid(axis="y", visible=False)

    summary_parts = [cohort_df.assign(panel="cohort_universe")]

    if has_nf:
        ax1 = axes_arr[1]
        nf = bundle.get("nflow").copy()
        for col in ("n_in", "n_out", "n_dropped"):
            nf[col] = pd.to_numeric(nf[col], errors="coerce").fillna(0)
        y1 = np.arange(len(nf))
        ax1.barh(
            y1 - 0.18,
            nf["n_in"],
            height=0.34,
            color=STATUS_COLORS["neutral"],
            alpha=0.55,
            label="n_in (candidate pool)",
        )
        out_colors = [
            COHORT_COLORS.get(str(st), STATUS_COLORS["retained"]) for st in nf["stage"]
        ]
        bars_out = ax1.barh(
            y1 + 0.18,
            nf["n_out"],
            height=0.34,
            color=out_colors,
            alpha=0.95,
            label="n_out (retained after priority rule)",
        )
        for bar, row in zip(bars_out, nf.itertuples(index=False), strict=True):
            drop_txt = f"  (-{format_compact(row.n_dropped)})" if row.n_dropped > 0 else ""
            ax1.text(
                max(row.n_in, row.n_out) * 1.03,
                bar.get_y(),
                f"{format_compact(row.n_out)}{drop_txt}",
                va="center",
                ha="left",
                fontsize=8.0,
                color=INK_PRIMARY,
            )
        ax1.set_xlim(0, max(nf["n_in"].max(), nf["n_out"].max()) * 1.48)
        ax1.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1e6:.0f}M" if v >= 1e6 else format_compact(v)))
        ax1.set_yticks(y1)
        ax1.set_yticklabels(
            [f"{r.stage}\n({r.filter})" for r in nf.itertuples(index=False)],
            fontsize=7.9,
        )
        ax1.set_ylim(len(nf) + 0.55, -0.55)
        ax1.set_xlabel("Wallet count (linear scale)")
        ax1.set_title("B. Deduplication & Priority Assignment n-Flow", loc="left")
        ax1.grid(axis="y", visible=False)
        ax1.legend(loc="lower right", fontsize=8.0)
        summary_parts.append(nf.assign(panel="nflow"))

    snap, is_partial = bundle.snapshot_for("sampling_frame", "cohort_counts", "nflow")
    stamp_figure(
        fig,
        title="05. Authoritative Cohort Composition & Priority n-Flow",
        subtitle="Strict priority order: illicit (blacklist/hop-0) > suspicious (min hop 1–5) > licit > unlabeled (provisional).",
        stage=bundle.stage,
        snapshot_at=snap,
        denominator_text=f"Total wallet universe: {int(universe_total):,}",
        is_partial=is_partial,
        top=0.84,
        bottom=0.14,
    )
    fig.subplots_adjust(wspace=0.52)

    summary = pd.concat(summary_parts, ignore_index=True)
    if verbose:
        print(f"[05_cohort_composition_nflow] stage={bundle.stage} universe={int(universe_total):,}")
    save_figure_and_table(fig, summary, out_path)
    return fig, axes_arr, summary


def plot_cross_schema_overlap(
    bundle: ProfileBundle,
    *,
    out_path: Path | None = None,
    verbose: bool = True,
) -> tuple[Figure, np.ndarray, pd.DataFrame]:
    """Plot 06: Wallet cross-schema overlap (left) and shared tx-hash field discordance (right)."""
    apply_theme()
    has_ov = bundle.has("group_overlap")
    has_clean = bundle.has("pretransform_cleaning")
    if not (has_ov or has_clean):
        raise ValueError("Missing both group_overlap and pretransform_cleaning in profile bundle.")

    n_panels = int(has_ov) + int(has_clean)
    fig, axes = plt.subplots(1, n_panels, figsize=(7.0 * n_panels, 5.4))
    axes_arr = np.atleast_1d(axes)
    idx = 0
    summary_parts: list[pd.DataFrame] = []

    if has_ov:
        ax = axes_arr[idx]
        idx += 1
        ov = bundle.get("group_overlap").copy()
        for col in ("left_count", "right_count", "overlap", "left_share", "right_share"):
            ov[col] = pd.to_numeric(ov[col], errors="coerce").fillna(0.0)
        y = np.arange(len(ov))
        left_pct = ov["left_share"] * 100.0
        right_pct = ov["right_share"] * 100.0

        ax.barh(y - 0.17, left_pct, height=0.32, color=SCHEMA_COLORS["illicit"], alpha=0.92, label="% of left (illicit-side) group")
        ax.barh(y + 0.17, right_pct, height=0.32, color=SCHEMA_COLORS["licit"], alpha=0.92, label="% of right (licit-side) group")

        for yi, row in zip(y, ov.itertuples(index=False), strict=True):
            ax.text(
                row.left_share * 100.0 + 0.8,
                yi - 0.17,
                f"{row.left_share * 100:.2f}%  ({int(row.overlap):,} / {int(row.left_count):,})",
                va="center",
                ha="left",
                fontsize=7.9,
                color=INK_PRIMARY,
            )
            ax.text(
                row.right_share * 100.0 + 0.8,
                yi + 0.17,
                f"{row.right_share * 100:.2f}%  ({int(row.overlap):,} / {int(row.right_count):,})",
                va="center",
                ha="left",
                fontsize=7.9,
                color=INK_SECONDARY,
            )

        ax.set_xlim(0, max(left_pct.max(), right_pct.max(), 10.0) * 1.55)
        ax.set_yticks(y)
        ax.set_yticklabels(ov["comparison"], fontsize=8.6)
        ax.invert_yaxis()
        ax.set_xlabel("Overlap share (%)")
        ax.set_title("A. Wallet Overlap Across Illicit & Licit Schemas", loc="left")
        ax.grid(axis="y", visible=False)
        ax.legend(loc="lower right", fontsize=8.0)
        summary_parts.append(ov.assign(panel="wallet_overlap"))

    if has_clean:
        ax = axes_arr[idx]
        cdf = bundle.get("pretransform_cleaning").copy()
        ov_tx = cdf[cdf["section"] == "cross_schema_tx_overlap"].copy()
        ov_tx["count"] = pd.to_numeric(ov_tx["count"], errors="coerce").fillna(0)
        ov_tx["share"] = pd.to_numeric(ov_tx["share"], errors="coerce").fillna(0.0)
        diffs = ov_tx[ov_tx["category"].isin(["overlap_tx_hash", "diff_amount", "diff_ts", "diff_to", "diff_from", "diff_token"])].copy()
        diffs = diffs.sort_values("count", ascending=True)
        y = np.arange(len(diffs))
        colors = [
            SCHEMA_COLORS["both"] if cat == "overlap_tx_hash" else STATUS_COLORS["warn"]
            for cat in diffs["category"]
        ]
        vals = diffs["count"].clip(lower=0.5)
        bars = ax.barh(y, vals, color=colors, height=0.58, edgecolor="white")
        for bar, cnt, sh in zip(bars, diffs["count"], diffs["share"], strict=True):
            txt = f"{int(cnt):,} ({sh * 100:.2f}%)" if cnt > 0 else "0 (0.00%)"
            ax.text(
                max(cnt, 1.0) * 1.18,
                bar.get_y() + bar.get_height() / 2.0,
                txt,
                va="center",
                ha="left",
                fontsize=8.2,
                color=INK_PRIMARY,
            )
        ax.set_xscale("log")
        ax.set_xlim(0.4, max(diffs["count"].max(), 10.0) * 28.0)
        ax.set_yticks(y)
        ax.set_yticklabels(diffs["category"], fontsize=8.8)
        ax.set_xlabel("Transaction rows (log10 scale)")
        ax.set_title("B. Shared tx_hash Overlap & Field Discordance", loc="left")
        ax.grid(axis="y", visible=False)
        ax.legend(
            handles=[
                Patch(facecolor=SCHEMA_COLORS["both"], label="shared tx_hash count"),
                Patch(facecolor=STATUS_COLORS["warn"], label="field discordance within shared hashes"),
            ],
            loc="lower right",
            fontsize=8.0,
        )
        summary_parts.append(diffs.assign(panel="tx_overlap"))

    snap, is_partial = bundle.snapshot_for("group_overlap", "pretransform_cleaning")
    stamp_figure(
        fig,
        title="06. Cross-Schema Wallet & Transaction Overlap Audit",
        subtitle="Demonstrates why blacklist-wins priority and deterministic L1 tx_hash deduplication are mandatory.",
        stage=bundle.stage,
        snapshot_at=snap,
        denominator_text="Wallet overlap exact; tx discordance denominator = 154,288 shared hashes",
        is_partial=is_partial,
        top=0.86,
        bottom=0.14,
    )
    fig.subplots_adjust(wspace=0.42)

    summary = pd.concat(summary_parts, ignore_index=True)
    if verbose:
        print(f"[06_cross_schema_overlap] stage={bundle.stage} rows={len(summary)}")
    save_figure_and_table(fig, summary, out_path)
    return fig, axes_arr, summary


def plot_hop_and_seed_structure(
    bundle: ProfileBundle,
    *,
    out_path: Path | None = None,
    verbose: bool = True,
) -> tuple[Figure, np.ndarray, pd.DataFrame]:
    """Plot 07: Hop-depth distributions (left) and seed-cluster quantiles (right)."""
    apply_theme()
    sf = bundle.get("sampling_frame").copy()
    sf["value"] = pd.to_numeric(sf["value"], errors="coerce")
    sf["denominator"] = pd.to_numeric(sf["denominator"], errors="coerce")

    hop_rows = sf[sf["section"].isin(["suspicious_hop_band", "licit_hop_band"])].copy()
    seed_rows = sf[sf["section"] == "seed_cluster_size"].copy()
    if hop_rows.empty and seed_rows.empty:
        raise ValueError("Missing hop_band and seed_cluster_size sections in local_sampling_frame.csv.")

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.8))
    axes_arr = np.atleast_1d(axes)

    # Panel A: Hop-depth profile (share of each arm + exact count labels)
    ax0 = axes_arr[0]
    hops = [f"hop_{k}" for k in range(1, 6)]
    x = np.arange(len(hops))
    series_cfg = [
        cfg
        for cfg in (
            ("suspicious_hop_band", "suspicious (illicit crawl)", COHORT_COLORS["suspicious"]),
            ("licit_hop_band", "licit (licit crawl)", COHORT_COLORS["licit"]),
        )
        if cfg[0] in set(hop_rows["section"])
    ]
    bar_w = 0.36 if len(series_cfg) > 1 else 0.52
    for idx, (sec, label, color) in enumerate(series_cfg):
        sdf = hop_rows[hop_rows["section"] == sec].set_index("group")
        shares = []
        counts = []
        for h in hops:
            if h in sdf.index:
                val = float(sdf.loc[h, "value"])
                den = float(sdf.loc[h, "denominator"])
                counts.append(val)
                shares.append((val / den * 100.0) if den > 0 else 0.0)
            else:
                counts.append(0.0)
                shares.append(0.0)
        offset = (idx - (len(series_cfg) - 1) / 2.0) * bar_w
        bars = ax0.bar(x + offset, shares, width=bar_w * 0.92, color=color, alpha=0.92, label=label, edgecolor="white")
        for bar, cnt, sh in zip(bars, counts, shares, strict=True):
            if cnt > 0:
                ax0.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    sh + 1.2,
                    f"{sh:.1f}%\n({format_compact(cnt)})",
                    ha="center",
                    va="bottom",
                    fontsize=7.3,
                    color=INK_PRIMARY,
                )

    ax0.set_xticks(x)
    ax0.set_xticklabels([f"Hop {k}" for k in range(1, 6)], fontsize=9.0)
    ax0.set_ylim(0, max(78.0, ax0.get_ylim()[1] * 1.15))
    ax0.set_ylabel("Share of crawled hop wallets (%)")
    ax0.set_title("A. Hop-Depth Nesting: Suspicious vs Licit Crawl", loc="left")
    ax0.grid(axis="x", visible=False)
    ax0.legend(loc="upper left", fontsize=8.3)

    # Panel B: Seed-cluster size quantile comparison (log10 scale)
    ax1 = axes_arr[1]
    groups = [g for g in ("illicit_seeds", "licit_seeds") if g in set(seed_rows["group"])]
    y = np.arange(len(groups))
    for yi, grp in enumerate(groups):
        gdf = seed_rows[seed_rows["group"] == grp].set_index("metric")["value"]
        color = SCHEMA_COLORS["illicit"] if "illicit" in grp else SCHEMA_COLORS["licit"]
        p25 = float(gdf.get("p25", np.nan))
        p50 = float(gdf.get("p50", np.nan))
        p75 = float(gdf.get("p75", np.nan))
        p90 = float(gdf.get("p90", np.nan))
        p99 = float(gdf.get("p99", np.nan))
        vmin = max(float(gdf.get("min", 1.0)), 1.0)
        vmax = float(gdf.get("max", np.nan))
        mean_v = float(gdf.get("mean", np.nan))
        n_seeds = int(gdf.get("n_seeds", 0))

        ax1.hlines(yi, vmin, p99, color=color, linewidth=1.8, alpha=0.55)
        ax1.hlines(yi, p25, p75, color=color, linewidth=8.5, alpha=0.85, label=None)
        ax1.scatter([p50], [yi], color="white", edgecolors=color, s=75, linewidth=2.0, zorder=4)
        ax1.scatter([mean_v], [yi], color=INK_PRIMARY, marker="D", s=45, zorder=5)
        ax1.scatter([vmax], [yi], color=color, marker="|", s=140, linewidth=2.0, zorder=4)
        ax1.text(
            1.2,
            yi - 0.24,
            f"n={n_seeds:,} seeds | p50={format_compact(p50)} | p90={format_compact(p90)} | mean={format_compact(mean_v)} | max={format_compact(vmax)}",
            ha="left",
            va="bottom",
            fontsize=7.8,
            color=INK_PRIMARY,
        )

    seed_label_map = {
        "illicit_seeds": "Illicit seeds\n(suspicious clusters)",
        "licit_seeds": "Licit seeds\n(licit crawl clusters)",
    }
    ax1.set_xscale("log")
    ax1.set_xlim(0.7, max(seed_rows["value"].max(), 100.0) * 3.5)
    ax1.set_yticks(y)
    ax1.set_yticklabels([seed_label_map.get(g, g) for g in groups], fontsize=8.8)
    ax1.set_ylim(-0.65, len(groups) - 0.35)
    ax1.set_xlabel("Wallets per seed cluster (log10 scale; bar=IQR, circle=p50, diamond=mean)")
    ax1.set_title("B. Seed-Cluster Fan-Out & Graph Non-Independence", loc="left")
    ax1.grid(axis="y", visible=False)

    if bundle.has("hop_seed"):
        hs = bundle.get("hop_seed").set_index("metric")["value"]
        multi_hop = int(float(hs.get("multi_hop_wallets", 0)))
        multi_seed = int(float(hs.get("multi_seed_wallets", 0)))
        ax1.text(
            0.02,
            0.05,
            f"Multi-hop wallets: {multi_hop:,}  |  Multi-seed wallets: {multi_seed:,}\n"
            "Suspicious wallets share seeds & hops -> non-independent arm",
            transform=ax1.transAxes,
            fontsize=8.0,
            color=INK_PRIMARY,
            bbox={"boxstyle": "round,pad=0.35", "facecolor": "#FAF6F2", "edgecolor": STATUS_COLORS["warn"], "linewidth": 0.9},
        )

    snap, is_partial = bundle.snapshot_for("sampling_frame", "hop_seed")
    susp_den = int(hop_rows.loc[hop_rows["section"] == "suspicious_hop_band", "denominator"].dropna().iloc[0]) if not hop_rows[hop_rows["section"] == "suspicious_hop_band"].empty else 0
    licit_den = int(hop_rows.loc[hop_rows["section"] == "licit_hop_band", "denominator"].dropna().iloc[0]) if not hop_rows[hop_rows["section"] == "licit_hop_band"].empty else 0
    denom_parts = [f"Suspicious hop wallets: {susp_den:,}"]
    if licit_den > 0:
        denom_parts.append(f"Licit hop wallets: {licit_den:,}")
    stamp_figure(
        fig,
        title="07. Sampling-Frame Geometry: Hop Nesting & Seed-Cluster Dependence",
        subtitle="Hop depth is nested inside crawl arms; heavy seed-cluster fan-out invalidates naive i.i.d. assumptions for suspicious.",
        stage=bundle.stage,
        snapshot_at=snap,
        denominator_text=" | ".join(denom_parts),
        is_partial=is_partial,
        top=0.86,
        bottom=0.14,
    )
    fig.subplots_adjust(wspace=0.28)

    summary = pd.concat([hop_rows, seed_rows], ignore_index=True)
    if verbose:
        print(f"[07_hop_and_seed_structure] stage={bundle.stage} rows={len(summary)}")
    save_figure_and_table(fig, summary, out_path)
    return fig, axes_arr, summary
