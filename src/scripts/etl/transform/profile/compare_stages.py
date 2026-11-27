"""Compare raw vs. transformed stage profiling CSVs for post-transform audit.

Read-only over ``outputs/etl/transform/profile/{raw,transformed}/``. Writes a
compact diff table ``raw_vs_transformed_diff.csv`` inside the transformed
profile directory (unless ``--dry-run`` is passed).

    python -m src.scripts.etl.transform.profile.compare_stages --dry-run
    python -m src.scripts.etl.transform.profile.compare_stages
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from src.scripts.config import PROFILING_OUTPUT_DIR

NUMERIC_COMPARE_COLS: tuple[str, ...] = (
    "n_cohort",
    "n_eligible",
    "mean",
    "p50",
    "pass_count",
)


def compare_distribution_frames(
    raw_df: pd.DataFrame,
    transformed_df: pd.DataFrame,
    *,
    rel_tol: float = 1e-6,
    abs_tol: float = 1e-6,
) -> pd.DataFrame:
    """Join raw and transformed distribution profiles on (wallet_class, feature)."""
    keys = ["wallet_class", "feature"]
    keep_cols = keys + [c for c in NUMERIC_COMPARE_COLS if c in raw_df.columns and c in transformed_df.columns]
    merged = raw_df[keep_cols].merge(
        transformed_df[keep_cols],
        on=keys,
        how="inner",
        suffixes=("_raw", "_transformed"),
    )
    records: list[dict[str, object]] = []
    for row in merged.to_dict(orient="records"):
        out: dict[str, object] = {
            "wallet_class": row["wallet_class"],
            "feature": row["feature"],
        }
        any_drift = False
        for col in NUMERIC_COMPARE_COLS:
            r_col, t_col = f"{col}_raw", f"{col}_transformed"
            if r_col not in row or t_col not in row:
                continue
            rv, tv = row[r_col], row[t_col]
            r_na, t_na = pd.isna(rv), pd.isna(tv)
            out[r_col] = None if r_na else float(rv)
            out[t_col] = None if t_na else float(tv)
            if r_na and t_na:
                out[f"{col}_delta"] = 0.0
                continue
            if r_na != t_na:
                out[f"{col}_delta"] = None
                any_drift = True
                continue
            delta = float(tv) - float(rv)
            out[f"{col}_delta"] = delta
            tol = max(abs_tol, rel_tol * max(abs(float(rv)), abs(float(tv))))
            if abs(delta) > tol:
                any_drift = True
        out["status"] = "drift" if any_drift else "match"
        records.append(out)
    return pd.DataFrame(records)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        default=str(PROFILING_OUTPUT_DIR / "raw"),
        help="Directory holding raw stage CSVs.",
    )
    parser.add_argument(
        "--transformed-dir",
        default=str(PROFILING_OUTPUT_DIR / "transformed"),
        help="Directory holding transformed stage CSVs.",
    )
    parser.add_argument("--rel-tol", type=float, default=1e-6)
    parser.add_argument("--abs-tol", type=float, default=1e-6)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate paths and print summary without writing CSV output.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    raw_dist = Path(args.raw_dir) / "local_wallet_distributions.csv"
    tr_dist = Path(args.transformed_dir) / "local_wallet_distributions.csv"
    out_path = Path(args.transformed_dir) / "raw_vs_transformed_diff.csv"

    if args.dry_run:
        print(f"[compare:dry-run] raw={raw_dist} (exists={raw_dist.exists()})")
        print(f"[compare:dry-run] transformed={tr_dist} (exists={tr_dist.exists()})")
        print(f"[compare:dry-run] output={out_path}")
        return 0

    if not raw_dist.exists():
        raise FileNotFoundError(f"missing raw profile CSV: {raw_dist}")
    if not tr_dist.exists():
        raise FileNotFoundError(
            f"missing transformed profile CSV: {tr_dist} — run profile_stage --stage transformed first."
        )

    diff_df = compare_distribution_frames(
        pd.read_csv(raw_dist),
        pd.read_csv(tr_dist),
        rel_tol=args.rel_tol,
        abs_tol=args.abs_tol,
    )
    diff_df.to_csv(out_path, index=False)
    n_drift = int((diff_df["status"] == "drift").sum()) if not diff_df.empty else 0
    print(f"[compare] wrote {out_path} ({len(diff_df)} rows, drift={n_drift})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
