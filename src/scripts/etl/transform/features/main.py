"""L3 wallet feature builder runner — materializes transform.wallet_features for H1-H6.

Usage (inspect resolved SQL without touching PostgreSQL):
    python -m src.scripts.etl.transform.features.main --dry-run

Usage (execute step-by-step or end-to-end):
    python -m src.scripts.etl.transform.features.main --step 01_feat_scalar
    python -m src.scripts.etl.transform.features.main --step 02_feat_degrees_and_h4
    python -m src.scripts.etl.transform.features.main --step 03_feat_usdt_temporal
    python -m src.scripts.etl.transform.features.main --step 04_feat_h6_cv
    python -m src.scripts.etl.transform.features.main --step 05_wallet_features
    python -m src.scripts.etl.transform.features.main --step nflow
    python -m src.scripts.etl.transform.features.main --step all
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.scripts.config import ETL_OUTPUT_DIR
from src.scripts.etl.db import get_local_engine, validate_schema_name
from src.scripts.etl.transform.features.rules import COHORT_ORDER, FEATURE_NFLOW_SPECS

SQL_DIR = Path(__file__).resolve().parent
FEATURES_OUTPUT_DIR = ETL_OUTPUT_DIR / "transform" / "features"

SQL_STEPS: tuple[tuple[str, str], ...] = (
    ("01_feat_scalar", "01_feat_scalar.sql"),
    ("02_feat_degrees_and_h4", "02_feat_degrees_and_h4.sql"),
    ("03_feat_usdt_temporal", "03_feat_usdt_temporal.sql"),
    ("04_feat_h6_cv", "04_feat_h6_cv.sql"),
    ("05_wallet_features", "05_wallet_features.sql"),
)
VALID_STEPS: tuple[str, ...] = tuple(name for name, _ in SQL_STEPS) + ("nflow", "all")


def render_sql(filename: str, *, transform_schema: str) -> str:
    """Load one L3 SQL file and substitute the validated transform schema."""
    t_schema = validate_schema_name(transform_schema)
    template = (SQL_DIR / filename).read_text(encoding="utf-8")
    return template.format(transform_schema=t_schema)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--step",
        choices=VALID_STEPS,
        default="all",
        help="Run one L3 SQL step or all steps in sequence. Default: all.",
    )
    parser.add_argument("--schema", default="transform", help="Derived transform schema name.")
    parser.add_argument("--work-mem", default="128MB", help="Session work_mem for SQL steps.")
    parser.add_argument(
        "--maintenance-work-mem",
        default="512MB",
        help="Session maintenance_work_mem for PK creation.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(FEATURES_OUTPUT_DIR),
        help="Directory for L3 feature n-flow CSV.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved SQL steps without connecting to PostgreSQL.",
    )
    return parser.parse_args(argv)


def execute_sql_step(
    engine: Engine,
    sql_text: str,
    *,
    work_mem: str,
    maintenance_work_mem: str,
) -> None:
    """Execute one SQL step inside a transaction with conservative session memory."""
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL work_mem = :wm"), {"wm": work_mem})
        conn.execute(
            text("SET LOCAL maintenance_work_mem = :mwm"),
            {"mwm": maintenance_work_mem},
        )
        conn.exec_driver_sql(sql_text)


def write_feature_nflow(
    engine: Engine,
    *,
    transform_schema: str,
    output_dir: Path,
) -> Path:
    """Assert 1-to-1 row-count parity with cohort_wallet and emit wallet_class × filter n-flow."""
    t_schema = validate_schema_name(transform_schema)
    run_ts = datetime.now(UTC).isoformat(timespec="seconds")

    with engine.connect() as conn:
        n_cohort = int(conn.execute(text(f"SELECT COUNT(*) FROM {t_schema}.cohort_wallet")).scalar_one())
        n_feat = int(conn.execute(text(f"SELECT COUNT(*) FROM {t_schema}.wallet_features")).scalar_one())
        if n_feat != n_cohort:
            raise AssertionError(
                f"wallet_features row count ({n_feat}) != cohort_wallet ({n_cohort})"
            )

        count_exprs = ", ".join(f"COUNT({col}) AS nn_{col}" for col, _, _, _ in FEATURE_NFLOW_SPECS)
        rows = conn.execute(
            text(
                f"""
                SELECT wallet_class, COUNT(*) AS n_cohort, {count_exprs}
                FROM {t_schema}.wallet_features
                GROUP BY wallet_class
                """
            )
        ).mappings().all()

    by_class = {str(r["wallet_class"]): dict(r) for r in rows}
    nflow_records: list[dict[str, object]] = []
    for col, hyp, elig_filter, note in FEATURE_NFLOW_SPECS:
        for wc in COHORT_ORDER:
            rec = by_class.get(wc, {})
            n_in = int(rec.get("n_cohort", 0))
            n_out = int(rec.get(f"nn_{col}", 0))
            nflow_records.append(
                {
                    "wallet_class": wc,
                    "hypothesis": hyp,
                    "feature": col,
                    "filter": elig_filter,
                    "n_in": n_in,
                    "n_out": n_out,
                    "n_dropped": n_in - n_out,
                    "retained_share": (n_out / n_in) if n_in else 0.0,
                    "reason": note,
                    "generated_at": run_ts,
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    nflow_path = output_dir / "feature_nflow.csv"
    pd.DataFrame(nflow_records).to_csv(nflow_path, index=False)
    return nflow_path


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    steps_to_run = (
        [name for name, _ in SQL_STEPS] + ["nflow"]
        if args.step == "all"
        else [args.step]
    )
    sql_map = dict(SQL_STEPS)

    if args.dry_run:
        print(f"[features:dry-run] schema={args.schema} steps={steps_to_run}")
        for step in steps_to_run:
            if step in sql_map:
                rendered = render_sql(sql_map[step], transform_schema=args.schema)
                print(f"\n--- {step} ({sql_map[step]}) ---")
                print(rendered)
            else:
                print(f"\n--- {step} -> writes feature_nflow.csv in {args.output_dir} ---")
        return 0

    engine = get_local_engine()
    try:
        for step in steps_to_run:
            if step in sql_map:
                print(f"[features] running {step}...", flush=True)
                rendered = render_sql(sql_map[step], transform_schema=args.schema)
                execute_sql_step(
                    engine,
                    rendered,
                    work_mem=args.work_mem,
                    maintenance_work_mem=args.maintenance_work_mem,
                )
            elif step == "nflow":
                print("[features] verifying parity & writing feature_nflow.csv...", flush=True)
                nflow_path = write_feature_nflow(
                    engine,
                    transform_schema=args.schema,
                    output_dir=Path(args.output_dir),
                )
                print(f"[features:nflow] {nflow_path}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
