"""Shared visual palette, typography, and figure stamping for EDA profile plots.

Color palette and encoding rationale live in
docs/dev/eda/profile/color-theory-and-visual-encoding.md.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import matplotlib
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

matplotlib.use("Agg", force=False)

# Palette anchors: see docs/dev/eda/profile/color-theory-and-visual-encoding.md
COHORT_ORDER: tuple[str, ...] = ("illicit", "suspicious", "licit", "unlabeled")

COHORT_COLORS: Mapping[str, str] = {
    "illicit": "#C83E2B",
    "suspicious": "#D9822B",
    "licit": "#1F6F8B",
    "unlabeled": "#7A8694",
}

COHORT_LINESTYLES: Mapping[str, str] = {
    "illicit": "-",
    "suspicious": "--",
    "licit": "-.",
    "unlabeled": ":",
}

COHORT_MARKERS: Mapping[str, str] = {
    "illicit": "o",
    "suspicious": "s",
    "licit": "D",
    "unlabeled": "^",
}

SCHEMA_COLORS: Mapping[str, str] = {
    "illicit": "#C83E2B",
    "licit": "#1F6F8B",
    "both": "#5B4B8A",
}

TOKEN_COLORS: Mapping[str, str] = {
    "TRX": "#5B4B8A",
    "USDT": "#2A9D8F",
    "ALL": "#52606D",
}

STATUS_COLORS: Mapping[str, str] = {
    "error": "#C83E2B",
    "warn": "#D9822B",
    "ok": "#2E7D6F",
    "complete": "#2E7D6F",
    "partial": "#D9822B",
    "stale": "#D9822B",
    "neutral": "#64748B",
    "dropped": "#9B2226",
    "retained": "#1F6F8B",
}

INK_PRIMARY = "#1F2933"
INK_SECONDARY = "#52606D"
GRID_COLOR = "#E5E9EF"
SPINE_COLOR = "#CBD2D9"
BG_COLOR = "#FFFFFF"
PANEL_BG = "#FAFBFC"

ELIGIBILITY_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "eda_eligibility",
    ["#F4F7FA", "#A9D0DE", "#4E95AE", "#164E63"],
)

RISK_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "eda_risk",
    ["#FAF6F2", "#E9B98A", "#D97B48", "#9B2226"],
)

DELTA_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "eda_delta",
    ["#1F6F8B", "#94BFC9", "#F1F5F9", "#E5987E", "#C83E2B"],
)


def apply_theme() -> None:
    """Apply consistent matplotlib rcParams for profile figures."""
    plt.rcParams.update(
        {
            "figure.facecolor": BG_COLOR,
            "axes.facecolor": BG_COLOR,
            "axes.edgecolor": SPINE_COLOR,
            "axes.linewidth": 0.9,
            "axes.labelcolor": INK_PRIMARY,
            "axes.titlecolor": INK_PRIMARY,
            "axes.titlesize": 11.5,
            "axes.titleweight": "bold",
            "axes.labelsize": 9.5,
            "axes.grid": True,
            "grid.color": GRID_COLOR,
            "grid.linewidth": 0.7,
            "grid.linestyle": "-",
            "axes.axisbelow": True,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": INK_SECONDARY,
            "ytick.color": INK_SECONDARY,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.frameon": True,
            "legend.facecolor": BG_COLOR,
            "legend.edgecolor": GRID_COLOR,
            "legend.fontsize": 8.5,
            "text.color": INK_PRIMARY,
            "font.family": "DejaVu Sans",
            "savefig.facecolor": BG_COLOR,
            "savefig.dpi": 180,
        }
    )


def format_compact(value: float | int) -> str:
    """Format large counts compactly for direct data labels."""
    if pd.isna(value):
        return "NA"
    abs_v = abs(float(value))
    if abs_v >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if abs_v >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs_v >= 10_000:
        return f"{value / 1_000:.1f}K"
    if abs_v >= 1_000:
        return f"{int(round(value)):,}"
    if float(value).is_integer():
        return f"{int(value)}"
    return f"{value:.2f}"


def stamp_figure(
    fig: Figure,
    *,
    title: str,
    subtitle: str,
    stage: str,
    snapshot_at: str,
    denominator_text: str,
    is_partial: bool,
    top: float | None = None,
    bottom: float | None = None,
) -> None:
    """Stamp title, subtitle, and provenance footer with height-aware spacing."""
    fig_h = max(float(fig.get_figheight()), 4.0)
    title_y = 1.0 - 0.14 / fig_h
    subtitle_y = 1.0 - 0.46 / fig_h
    footer_y = 0.12 / fig_h
    resolved_top = min(top, 1.0 - 1.02 / fig_h) if top is not None else (1.0 - 1.02 / fig_h)
    resolved_bottom = max(bottom, 0.72 / fig_h) if bottom is not None else (0.72 / fig_h)

    fig.suptitle(
        title,
        x=0.04,
        y=title_y,
        ha="left",
        va="top",
        fontsize=13.5,
        fontweight="bold",
        color=INK_PRIMARY,
    )
    fig.text(
        0.04,
        subtitle_y,
        subtitle,
        ha="left",
        va="top",
        fontsize=9.3,
        color=INK_SECONDARY,
    )
    partial_badge = "PARTIAL SNAPSHOT" if is_partial else "is_partial=False"
    footer = (
        f"Stage: {stage}  |  Snapshot: {snapshot_at}  |  "
        f"{denominator_text}  |  {partial_badge}"
    )
    fig.text(
        0.04,
        footer_y,
        footer,
        ha="left",
        va="bottom",
        fontsize=8.0,
        color=STATUS_COLORS["warn"] if is_partial else INK_SECONDARY,
        fontweight="bold" if is_partial else "normal",
    )
    fig.subplots_adjust(top=resolved_top, bottom=resolved_bottom)


def save_figure_and_table(
    fig: Figure,
    summary_df: pd.DataFrame,
    out_path: Path | None,
    *,
    dpi: int = 180,
) -> tuple[Path | None, Path | None]:
    """Save figure PNG and companion supporting CSV beside each other."""
    if out_path is None:
        return None, None
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    csv_path = out_path.with_suffix(".csv")
    summary_df.to_csv(csv_path, index=False)
    return out_path, csv_path
