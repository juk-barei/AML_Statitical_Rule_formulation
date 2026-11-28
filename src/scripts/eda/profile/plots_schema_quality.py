"""Group A profile plots: schema overview, missingness, quality, and temporal volume."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from src.scripts.eda.profile.io import ProfileBundle
from src.scripts.eda.profile.style import (
    INK_PRIMARY,
    INK_SECONDARY,
    RISK_CMAP,
    SCHEMA_COLORS,
    STATUS_COLORS,
    TOKEN_COLORS,
    apply_theme,
    format_compact,
    save_figure_and_table,
    stamp_figure,
)


def plot_table_overview_coverage(
    bundle: ProfileBundle,
    *,
    out_path: Path | None = None,
    verbose: bool = True,
) -> tuple[Figure, Axes, pd.DataFrame]:
    """Plot 01: Log-scale row counts across illicit and licit tables with coverage badges."""
    apply_theme()
    frames = [
        bundle.get(k)
        for k in ("illicit_db_overview", "licit_db_overview")
        if bundle.has(k)
    ]
    if not frames:
        raise ValueError("Missing db_overview tables in profile bundle.")

    df = pd.concat(frames, ignore_index=True)
    if bundle.has("illicit_coverage") or bundle.has("licit_coverage"):
        cov_frames = [
            bundle.get(k)
            for k in ("illicit_coverage", "licit_coverage")
            if bundle.has(k)
        ]
        cov = pd.concat(cov_frames, ignore_index=True)[
            ["schema", "table", "coverage_status", "completed_shards", "shard_count", "failed_shards"]
        ].drop_duplicates(["schema", "table"])
        df = df.drop(columns=["coverage_status"], errors="ignore").merge(
            cov, on=["schema", "table"], how="left"
        )

    df["rows"] = pd.to_numeric(df["rows"], errors="coerce").fillna(0)
    df["coverage_status"] = df.get("coverage_status", pd.Series(["unknown"] * len(df))).fillna("unknown")
    df["is_partial_bool"] = df.get("is_partial", False).astype(str).str.lower().eq("true")

    table_order = (
        df.groupby("table")["rows"].max().sort_values(ascending=True).index.tolist()
    )
    schemas = [s for s in ("illicit", "licit") if s in set(df["schema"])]
    if not schemas:
        schemas = sorted(df["schema"].astype(str).unique().tolist())

    fig, ax = plt.subplots(figsize=(11.2, 5.8))
    y_pos = np.arange(len(table_order))
    bar_h = 0.36 if len(schemas) > 1 else 0.52

    for idx, schema in enumerate(schemas):
        sub = df[df["schema"] == schema].set_index("table")
        offset = (idx - (len(schemas) - 1) / 2.0) * bar_h
        color = SCHEMA_COLORS.get(schema, STATUS_COLORS["neutral"])
        vals: list[float | None] = []
        for tbl in table_order:
            vals.append(float(sub.loc[tbl, "rows"]) if tbl in sub.index else None)
        plot_vals = [np.nan if v is None else (v if v > 0 else 0.5) for v in vals]
        bars = ax.barh(
            y_pos + offset,
            plot_vals,
            height=bar_h * 0.9,
            color=color,
            alpha=0.9,
            label=f"{schema} schema",
            edgecolor="white",
            linewidth=0.6,
        )
        for bar, tbl, raw_v in zip(bars, table_order, vals, strict=True):
            if raw_v is None or tbl not in sub.index:
                continue
            status = str(sub.loc[tbl, "coverage_status"])
            is_part = bool(sub.loc[tbl, "is_partial_bool"])
            badge = f" [{status}]" if (is_part or status != "complete") else ""
            txt_color = STATUS_COLORS["warn"] if (is_part or status != "complete") else INK_PRIMARY
            label_str = "0 rows" if raw_v == 0 else f"{format_compact(raw_v)}{badge}"
            ax.text(
                max(raw_v, 1.0) * 1.15,
                bar.get_y() + bar.get_height() / 2.0,
                label_str,
                va="center",
                ha="left",
                fontsize=8.3,
                color=txt_color,
                fontweight="bold" if badge else "normal",
            )

    ax.set_xscale("log")
    ax.set_xlim(0.4, max(df["rows"].max(), 10.0) * 12.0)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(table_order, fontsize=9.5, fontweight="normal")
    ax.set_xlabel("Row count (log10 scale)")
    ax.grid(axis="x", which="major", alpha=0.8)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", title="Database schema", frameon=True)

    snap, is_partial = bundle.snapshot_for("illicit_db_overview", "licit_db_overview")
    total_rows = int(df["rows"].sum())
    stamp_figure(
        fig,
        title="01. Mirror Table Volume & Ingestion Coverage",
        subtitle="Exact row counts per table across illicit and licit schemas; non-complete statuses flagged in amber.",
        stage=bundle.stage,
        snapshot_at=snap,
        denominator_text=f"Total rows across profiled tables: {total_rows:,}",
        is_partial=is_partial,
        top=0.86,
        bottom=0.14,
    )

    summary = df[
        [c for c in ("schema", "table", "rows", "source_rows", "coverage_status", "is_partial", "snapshot_at") if c in df.columns]
    ].sort_values(["schema", "rows"], ascending=[True, False])
    if verbose:
        print(f"[01_table_overview_coverage] stage={bundle.stage} tables={len(summary)} total_rows={total_rows:,}")
    save_figure_and_table(fig, summary, out_path)
    return fig, ax, summary


def plot_column_missingness_dtypes(
    bundle: ProfileBundle,
    *,
    out_path: Path | None = None,
    verbose: bool = True,
) -> tuple[Figure, np.ndarray, pd.DataFrame]:
    """Plot 02: Per-column missingness share annotated with SQL data types."""
    apply_theme()
    frames = [
        bundle.get(k)
        for k in ("illicit_columns", "licit_columns", "transform_columns")
        if bundle.has(k)
    ]
    if not frames:
        raise ValueError("Missing *_columns tables in profile bundle.")

    df = pd.concat(frames, ignore_index=True)
    df["null_share"] = pd.to_numeric(df["null_share"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    df["distinct_approx"] = pd.to_numeric(df.get("distinct_approx", np.nan), errors="coerce")
    df["short_type"] = (
        df["data_type"]
        .astype(str)
        .str.replace("TIMESTAMP WITH TIME ZONE", "TIMESTAMPTZ", regex=False)
        .str.replace("CHARACTER VARYING", "VARCHAR", regex=False)
    )
    df["col_label"] = df["table"].astype(str) + "." + df["column"].astype(str)

    # For transformed Parquet profiles, omit *_exact string shadow mirrors from the plot
    # (kept in full summary CSV) and split L1-L2 tables vs L3 wallet_features for readability.
    raw_schemas = [s for s in ("illicit", "licit") if s in set(df["schema"])]
    if raw_schemas:
        panels = [(f"{s} schema", df[df["schema"] == s], SCHEMA_COLORS.get(s, INK_PRIMARY)) for s in raw_schemas]
    else:
        plot_df = df[~df["column"].astype(str).str.endswith("_exact")].copy()
        if plot_df.empty:
            plot_df = df.copy()
        l12 = plot_df[plot_df["table"].astype(str) != "wallet_features"]
        l3 = plot_df[plot_df["table"].astype(str) == "wallet_features"]
        panels = []
        if not l12.empty:
            panels.append(("transform L1–L2 (clean & cohort)", l12, STATUS_COLORS["retained"]))
        if not l3.empty:
            panels.append(("transform L3 (wallet_features)", l3, STATUS_COLORS["neutral"]))
        if not panels:
            for s in sorted(plot_df["schema"].astype(str).unique().tolist()):
                panels.append((f"{s} schema", plot_df[plot_df["schema"] == s], INK_PRIMARY))

    max_rows = max(len(sub_df) for _, sub_df, _ in panels)
    fig_h = max(6.8, max_rows * 0.24 + 2.0)
    fig, axes = plt.subplots(1, len(panels), figsize=(7.6 * len(panels), fig_h), sharex=True)
    axes_arr = np.atleast_1d(axes)

    for ax, (panel_title, panel_df, title_color) in zip(axes_arr, panels, strict=True):
        sub = (
            panel_df
            .sort_values(["null_share", "table", "column"], ascending=[True, False, False])
            .reset_index(drop=True)
        )
        y = np.arange(len(sub))
        pct = sub["null_share"] * 100.0
        colors = [
            RISK_CMAP(min(1.0, 0.15 + 0.85 * float(v))) if float(v) > 0 else STATUS_COLORS["ok"]
            for v in sub["null_share"]
        ]
        ax.hlines(y, 0, pct, color=colors, linewidth=2.2, alpha=0.85)
        ax.scatter(pct, y, color=colors, s=36, zorder=3, edgecolors="white", linewidths=0.5)
        for yi, p_val, dtype in zip(y, pct, sub["short_type"], strict=True):
            txt = f"{p_val:.1f}%  ({dtype})" if p_val > 0 else f"0.0%  ({dtype})"
            ax.text(
                min(p_val + 1.8, 102.0),
                yi,
                txt,
                va="center",
                ha="left",
                fontsize=7.6,
                color=INK_PRIMARY if p_val > 5.0 else INK_SECONDARY,
                fontweight="bold" if p_val >= 50.0 else "normal",
            )
        ax.set_yticks(y)
        ax.set_yticklabels(sub["col_label"], fontsize=8.0)
        ax.set_xlim(-2, 148)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
        ax.set_xlabel("Null percentage (%)")
        ax.set_title(
            f"{panel_title} ({len(sub)} columns)",
            color=title_color,
            loc="left",
        )
        ax.grid(axis="x", alpha=0.7)
        ax.grid(axis="y", visible=False)

    snap, is_partial = bundle.snapshot_for("illicit_columns", "licit_columns", "transform_columns")
    n_with_nulls = int((df["null_share"] > 0).sum())
    stamp_figure(
        fig,
        title="02. Column Missingness & SQL Data Types",
        subtitle="Null share per column (0% shown in green-teal; elevated nullness scales along warm sand-to-crimson).",
        stage=bundle.stage,
        snapshot_at=snap,
        denominator_text=f"Profiled columns: {len(df)} ({n_with_nulls} with >0% nulls)",
        is_partial=is_partial,
        top=0.90,
        bottom=0.07,
    )
    fig.subplots_adjust(wspace=0.52)

    summary = df[
        [c for c in ("schema", "table", "column", "data_type", "rows", "nulls", "null_share", "distinct_approx", "snapshot_at") if c in df.columns]
    ].sort_values(["schema", "null_share"], ascending=[True, False])
    if verbose:
        print(f"[02_column_missingness_dtypes] stage={bundle.stage} cols={len(summary)} nonzero_null_cols={n_with_nulls}")
    save_figure_and_table(fig, summary, out_path)
    return fig, axes_arr, summary


def plot_quality_and_cleaning_anomalies(
    bundle: ProfileBundle,
    *,
    out_path: Path | None = None,
    verbose: bool = True,
) -> tuple[Figure, np.ndarray, pd.DataFrame]:
    """Plot 03: Mirror quality rule failures (left) and L1 cleaning anomalies (right)."""
    apply_theme()
    has_q = bundle.has("quality")
    has_c = bundle.has("pretransform_cleaning")
    if not (has_q or has_c):
        raise ValueError("Neither quality nor pretransform_cleaning is available in profile bundle.")

    n_panels = int(has_q) + int(has_c)
    fig, axes = plt.subplots(1, n_panels, figsize=(7.2 * n_panels, 6.8))
    axes_arr = np.atleast_1d(axes)
    panel_idx = 0
    summary_parts: list[pd.DataFrame] = []

    if has_q:
        ax = axes_arr[panel_idx]
        panel_idx += 1
        qdf = bundle.get("quality").copy()
        qdf["failed_rows"] = pd.to_numeric(qdf["failed_rows"], errors="coerce").fillna(0)
        qdf["failed_share"] = pd.to_numeric(qdf["failed_share"], errors="coerce").fillna(0.0)
        qdf["label"] = qdf["schema"].astype(str) + "." + qdf["table"].astype(str) + ": " + qdf["check"].astype(str)
        nonzero = qdf[qdf["failed_rows"] > 0].sort_values("failed_rows", ascending=True)
        zero_count = int((qdf["failed_rows"] == 0).sum())
        plot_q = nonzero if not nonzero.empty else qdf.head(8)

        y = np.arange(len(plot_q))
        colors = [
            STATUS_COLORS.get(str(sev).lower(), STATUS_COLORS["neutral"])
            for sev in plot_q["severity"]
        ]
        vals = plot_q["failed_rows"].clip(lower=0.5)
        bars = ax.barh(y, vals, color=colors, height=0.58, edgecolor="white")
        for bar, raw_v, share in zip(bars, plot_q["failed_rows"], plot_q["failed_share"], strict=True):
            txt = f"{format_compact(raw_v)} ({share * 100:.3f}%)" if raw_v > 0 else "0 failures"
            ax.text(
                max(raw_v, 1.0) * 1.18,
                bar.get_y() + bar.get_height() / 2.0,
                txt,
                va="center",
                ha="left",
                fontsize=8.3,
                color=INK_PRIMARY,
            )
        ax.set_xscale("log")
        ax.set_xlim(0.4, max(plot_q["failed_rows"].max(), 10.0) * 20.0)
        ax.set_yticks(y)
        ax.set_yticklabels(plot_q["label"], fontsize=8.4)
        ax.set_xlabel("Failed rows (log10 scale)")
        ax.set_title(
            f"A. Mirror Quality Checks ({len(nonzero)} nonzero / {zero_count} passed with 0)",
            loc="left",
        )
        ax.grid(axis="y", visible=False)
        ax.legend(
            handles=[
                Patch(facecolor=STATUS_COLORS["error"], label="error severity"),
                Patch(facecolor=STATUS_COLORS["warn"], label="warn severity"),
            ],
            loc="lower right",
        )
        summary_parts.append(
            qdf[["schema", "table", "check", "failed_rows", "denominator", "failed_share", "severity"]]
            .assign(source_table="local_quality")
            .rename(columns={"check": "category", "failed_rows": "count", "failed_share": "share"})
        )

    if has_c:
        ax = axes_arr[panel_idx]
        cdf = bundle.get("pretransform_cleaning").copy()
        cdf["count"] = pd.to_numeric(cdf["count"], errors="coerce").fillna(0)
        cdf["share"] = pd.to_numeric(cdf["share"], errors="coerce").fillna(0.0)
        anom = cdf[
            cdf["section"].isin(["amount_flag", "timestamp_flag", "trx_anomaly_detail", "cross_schema_tx_overlap"])
            & ~cdf["category"].isin(["ok", "raw_union_rows", "deduped_tx_rows", "diff_amount_exact"])
            & (cdf["count"] > 0)
        ].copy()
        anom["label"] = (
            anom["schema"].astype(str)
            + " "
            + anom["token_symbol"].astype(str)
            + " | "
            + anom["category"].astype(str)
        )
        anom = anom.sort_values("count", ascending=True).tail(16)
        y = np.arange(len(anom))
        colors = [
            SCHEMA_COLORS.get(str(s), STATUS_COLORS["neutral"])
            for s in anom["schema"]
        ]
        bars = ax.barh(y, anom["count"], color=colors, height=0.62, edgecolor="white")
        for bar, cnt, sh in zip(bars, anom["count"], anom["share"], strict=True):
            ax.text(
                cnt * 1.18,
                bar.get_y() + bar.get_height() / 2.0,
                f"{format_compact(cnt)} ({sh * 100:.2f}%)",
                va="center",
                ha="left",
                fontsize=8.0,
                color=INK_PRIMARY,
            )
        ax.set_xscale("log")
        ax.set_xlim(1, max(anom["count"].max(), 10.0) * 60.0)
        ax.set_ylim(-2.8, len(anom) - 0.3)
        ax.set_yticks(y)
        ax.set_yticklabels(anom["label"], fontsize=8.1)
        ax.set_xlabel("Flagged transaction rows (log10 scale)")
        ax.set_title("B. L1 Pre-Transform Cleaning Flags (non-ok rows)", loc="left")
        ax.grid(axis="y", visible=False)
        ax.legend(
            handles=[
                Patch(facecolor=SCHEMA_COLORS["illicit"], label="illicit schema"),
                Patch(facecolor=SCHEMA_COLORS["licit"], label="licit schema"),
                Patch(facecolor=SCHEMA_COLORS["both"], label="cross-schema (both)"),
            ],
            loc="lower right",
        )
        summary_parts.append(
            anom[["section", "schema", "token_symbol", "category", "count", "denominator", "share"]]
            .assign(source_table="local_pretransform_cleaning")
        )

    snap, is_partial = bundle.snapshot_for("pretransform_cleaning", "quality")
    denom_text = f"Quality checks: {len(bundle.get('quality')) if has_q else 0}"
    if has_c:
        cdf_all = bundle.get("pretransform_cleaning")
        ov = cdf_all[cdf_all["section"] == "cross_schema_tx_overlap"].set_index("category")["count"]
        raw_u = int(pd.to_numeric(ov.get("raw_union_rows", 0), errors="coerce") or 0)
        ded_u = int(pd.to_numeric(ov.get("deduped_tx_rows", 0), errors="coerce") or 0)
        if raw_u > 0:
            denom_text = f"Tx union: {raw_u:,} raw / {ded_u:,} deduped rows"
    stamp_figure(
        fig,
        title="03. Data Quality Rule Checks & L1 Cleaning Anomalies",
        subtitle="Non-zero quality violations and transaction anomaly flags driving non-destructive L1 cleaning rules.",
        stage=bundle.stage,
        snapshot_at=snap,
        denominator_text=denom_text,
        is_partial=is_partial,
        top=0.87,
        bottom=0.11,
    )
    fig.subplots_adjust(wspace=0.58)

    summary = pd.concat(summary_parts, ignore_index=True)
    if verbose:
        print(f"[03_quality_and_cleaning_anomalies] stage={bundle.stage} summary_rows={len(summary)}")
    save_figure_and_table(fig, summary, out_path)
    return fig, axes_arr, summary


def plot_tx_volume_by_year(
    bundle: ProfileBundle,
    *,
    out_path: Path | None = None,
    verbose: bool = True,
) -> tuple[Figure, np.ndarray, pd.DataFrame]:
    """Plot 04: Annual transaction counts by schema and token, separating pre-mainnet artifacts."""
    apply_theme()
    cdf = bundle.get("pretransform_cleaning").copy()
    sub = cdf[cdf["section"] == "tx_by_year"].copy()
    if sub.empty:
        raise ValueError("No tx_by_year section found in local_pretransform_cleaning.csv.")

    sub["count"] = pd.to_numeric(sub["count"], errors="coerce").fillna(0)
    sub["share"] = pd.to_numeric(sub["share"], errors="coerce").fillna(0.0)
    sub["is_pre_mainnet"] = sub["category"].astype(str).str.startswith("pre_mainnet")

    pre_cats = sorted(sub.loc[sub["is_pre_mainnet"], "category"].astype(str).unique().tolist())
    year_cats = sorted(sub.loc[~sub["is_pre_mainnet"], "category"].astype(str).unique().tolist())
    ordered_cats = pre_cats + year_cats

    schemas = [s for s in ("illicit", "licit") if s in set(sub["schema"])]
    fig, axes = plt.subplots(1, len(schemas), figsize=(6.8 * len(schemas), 5.6), sharey=True)
    axes_arr = np.atleast_1d(axes)

    x = np.arange(len(ordered_cats))
    tokens = [t for t in ("TRX", "USDT") if t in set(sub["token_symbol"])]
    bar_w = 0.38 if len(tokens) > 1 else 0.55

    for ax, schema in zip(axes_arr, schemas, strict=True):
        sdf = sub[sub["schema"] == schema]
        for idx, tok in enumerate(tokens):
            tdf = sdf[sdf["token_symbol"] == tok].set_index("category")
            vals = [float(tdf.loc[c, "count"]) if c in tdf.index else 0.0 for c in ordered_cats]
            offset = (idx - (len(tokens) - 1) / 2.0) * bar_w
            bars = ax.bar(
                x + offset,
                [v if v > 0 else np.nan for v in vals],
                width=bar_w * 0.92,
                color=TOKEN_COLORS.get(tok, STATUS_COLORS["neutral"]),
                alpha=0.92,
                label=tok,
                edgecolor="white",
                linewidth=0.5,
            )
            for bar, v in zip(bars, vals, strict=True):
                if v > 0:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2.0,
                        v * 1.18,
                        format_compact(v),
                        ha="center",
                        va="bottom",
                        fontsize=7.0,
                        rotation=90,
                        color=INK_SECONDARY,
                    )

        if pre_cats and year_cats:
            boundary = len(pre_cats) - 0.5
            ax.axvline(boundary, color=STATUS_COLORS["warn"], linestyle="--", linewidth=1.2)
            ax.axvspan(-0.6, boundary, color=STATUS_COLORS["warn"], alpha=0.07, zorder=0)
            ax.text(
                boundary - 0.08,
                0.96,
                "pre-mainnet\nartifacts",
                transform=ax.get_xaxis_transform(),
                ha="right",
                va="top",
                fontsize=7.8,
                color=STATUS_COLORS["warn"],
                fontweight="bold",
            )

        ax.set_yscale("log")
        ax.set_ylim(0.5, max(sub["count"].max(), 10.0) * 18.0)
        ax.set_xticks(x)
        short_labels = [c.replace("pre_mainnet_", "<") for c in ordered_cats]
        ax.set_xticklabels(short_labels, rotation=40, ha="right", fontsize=8.3)
        ax.set_title(
            f"{schema} schema (n = {int(sdf['count'].sum()):,})",
            color=SCHEMA_COLORS.get(schema, INK_PRIMARY),
            loc="left",
        )
        ax.grid(axis="x", visible=False)
        ax.legend(title="Token", loc="upper center", bbox_to_anchor=(0.45, 0.99), ncol=2)

    axes_arr[0].set_ylabel("Transaction rows (log10 scale)")
    snap, is_partial = bundle.snapshot_for("pretransform_cleaning")
    stamp_figure(
        fig,
        title="04. Annual Transaction Volume & Pre-Mainnet Artifacts",
        subtitle="TRX vs USDT row volume by block year; shaded region flags pre-TRON-mainnet (1970/1989/1990) timestamps.",
        stage=bundle.stage,
        snapshot_at=snap,
        denominator_text=f"Total rows plotted: {int(sub['count'].sum()):,}",
        is_partial=is_partial,
        top=0.86,
        bottom=0.18,
    )
    fig.subplots_adjust(wspace=0.12)

    summary = sub[["schema", "token_symbol", "category", "count", "denominator", "share", "snapshot_at"]].sort_values(
        ["schema", "category", "token_symbol"]
    )
    if verbose:
        pre_total = int(sub.loc[sub["is_pre_mainnet"], "count"].sum())
        print(f"[04_tx_volume_by_year] stage={bundle.stage} total_tx={int(sub['count'].sum()):,} pre_mainnet={pre_total:,}")
    save_figure_and_table(fig, summary, out_path)
    return fig, axes_arr, summary
