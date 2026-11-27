"""L2 cohort builder runner — materializes transform.cohort_wallet and verifies partition invariants.

Usage (inspect resolved SQL without touching PostgreSQL):
    python -m src.scripts.etl.transform.cohort.main --dry-run

Usage (execute step-by-step or end-to-end):
    python -m src.scripts.etl.transform.cohort.main --step 01_cohort_wallet
    python -m src.scripts.etl.transform.cohort.main --step 02_cohort_indexes
    python -m src.scripts.etl.transform.cohort.main --step nflow
    python -m src.scripts.etl.transform.cohort.main --step all
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
from src.scripts.etl.transform.cohort.rules import COHORT_ORDER, assert_cohort_partition

SQL_DIR = Path(__file__).resolve().parent
COHORT_OUTPUT_DIR = ETL_OUTPUT_DIR / "transform" / "cohort"

SQL_STEPS: tuple[tuple[str, str], ...] = (
    ("01_cohort_wallet", "01_cohort_wallet.sql"),
    ("02_cohort_indexes", "02_cohort_indexes.sql"),
)
VALID_STEPS: tuple[str, ...] = tuple(name for name, _ in SQL_STEPS) + ("nflow", "all")


def render_sql(
    filename: str,
    *,
    transform_schema: str,
    illicit_schema: str,
    licit_schema: str,
) -> str:
    """Load one SQL file and substitute validated schema identifiers."""
    t_schema = validate_schema_name(transform_schema)
    i_schema = validate_schema_name(illicit_schema)
    l_schema = validate_schema_name(licit_schema)
    template = (SQL_DIR / filename).read_text(encoding="utf-8")
    return template.format(
        transform_schema=t_schema,
        illicit_schema=i_schema,
        licit_schema=l_schema,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--step",
        choices=VALID_STEPS,
        default="all",
        help="Run one step or all L2 steps in sequence. Default: all.",
    )
    parser.add_argument("--schema", default="transform", help="Derived transform schema name.")
    parser.add_argument("--illicit-schema", default="illicit", help="Read-only L0 illicit schema.")
    parser.add_argument("--licit-schema", default="licit", help="Read-only L0 licit schema.")
    parser.add_argument("--work-mem", default="128MB", help="Session work_mem for SQL steps.")
    parser.add_argument(
        "--maintenance-work-mem",
        default="512MB",
        help="Session maintenance_work_mem for post-load index builds.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(COHORT_OUTPUT_DIR),
        help="Directory for L2 cohort count and n-flow CSVs.",
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


def write_cohort_nflow(
    engine: Engine,
    *,
    transform_schema: str,
    illicit_schema: str,
    licit_schema: str,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Assert L2 partition & nesting invariants and emit cohort CSVs."""
    t_schema = validate_schema_name(transform_schema)
    i_schema = validate_schema_name(illicit_schema)
    l_schema = validate_schema_name(licit_schema)
    run_ts = datetime.now(UTC).isoformat(timespec="seconds")

    with engine.connect() as conn:
        counts_rows = conn.execute(
            text(
                f"""
                SELECT
                    wallet_class,
                    COUNT(*) AS wallets_total,
                    COUNT(*) FILTER (WHERE in_accounts_table) AS wallets_in_accounts,
                    COUNT(*) FILTER (WHERE NOT in_accounts_table) AS wallets_hop_only,
                    COUNT(*) FILTER (WHERE is_contaminated_licit_seed) AS contaminated_licit_seeds,
                    COUNT(*) FILTER (WHERE from_contaminated_licit_seed) AS from_contaminated_licit_seed
                FROM {t_schema}.cohort_wallet
                GROUP BY wallet_class
                """
            )
        ).mappings().all()
        bad_nesting = int(
            conn.execute(
                text(
                    f"""
                    SELECT COUNT(*) FROM {t_schema}.cohort_wallet
                    WHERE (wallet_class = 'suspicious' AND (min_hop_level IS NULL OR min_hop_level NOT BETWEEN 1 AND 5))
                       OR (wallet_class <> 'suspicious' AND min_hop_level IS NOT NULL)
                    """
                )
            ).scalar_one()
        )
        raw_illicit_acc = int(conn.execute(text(f"SELECT COUNT(*) FROM {i_schema}.accounts")).scalar_one())
        raw_licit_acc = int(conn.execute(text(f"SELECT COUNT(*) FROM {l_schema}.accounts")).scalar_one())
        raw_hop_ge1 = int(
            conn.execute(
                text(
                    f"SELECT COUNT(DISTINCT wallet_address) FROM {i_schema}.wallet_hops "
                    f"WHERE hop_level BETWEEN 1 AND 5"
                )
            ).scalar_one()
        )

    if bad_nesting != 0:
        raise AssertionError(f"cohort nesting invariant violated on {bad_nesting} rows")

    by_class = {str(r["wallet_class"]): dict(r) for r in counts_rows}
    class_totals = {wc: int(by_class.get(wc, {}).get("wallets_total", 0)) for wc in COHORT_ORDER}
    universe_total = sum(class_totals.values())
    assert_cohort_partition(universe_total, class_totals)

    in_accounts_total = sum(int(by_class.get(wc, {}).get("wallets_in_accounts", 0)) for wc in COHORT_ORDER)
    hop_only_total = sum(int(by_class.get(wc, {}).get("wallets_hop_only", 0)) for wc in COHORT_ORDER)

    count_records = [
        {
            "wallet_class": wc,
            "wallets_total": class_totals[wc],
            "share": (class_totals[wc] / universe_total) if universe_total else 0.0,
            "wallets_in_accounts": int(by_class.get(wc, {}).get("wallets_in_accounts", 0)),
            "wallets_hop_only": int(by_class.get(wc, {}).get("wallets_hop_only", 0)),
            "contaminated_licit_seeds": int(by_class.get(wc, {}).get("contaminated_licit_seeds", 0)),
            "from_contaminated_licit_seed": int(by_class.get(wc, {}).get("from_contaminated_licit_seed", 0)),
            "generated_at": run_ts,
        }
        for wc in COHORT_ORDER
    ]
    nflow_records = [
        {
            "stage": "L2_cohort",
            "filter": "accounts_cross_schema_dedupe",
            "n_in": raw_illicit_acc + raw_licit_acc,
            "n_out": in_accounts_total,
            "n_dropped": (raw_illicit_acc + raw_licit_acc) - in_accounts_total,
            "reason": "address present in both illicit.accounts and licit.accounts",
            "generated_at": run_ts,
        },
        {
            "stage": "L2_cohort",
            "filter": "universe_with_hop_only_wallets",
            "n_in": in_accounts_total,
            "n_out": universe_total,
            "n_dropped": -hop_only_total,
            "reason": "negative n_dropped = hop-only wallets added to reconcile full universe",
            "generated_at": run_ts,
        },
        {
            "stage": "L2_cohort",
            "filter": "illicit_priority",
            "n_in": universe_total,
            "n_out": class_totals["illicit"],
            "n_dropped": universe_total - class_totals["illicit"],
            "reason": "blacklisted (label=1) or hop_level=0; wins at every hop",
            "generated_at": run_ts,
        },
        {
            "stage": "L2_cohort",
            "filter": "suspicious_hop_1_5_minus_blacklist",
            "n_in": raw_hop_ge1,
            "n_out": class_totals["suspicious"],
            "n_dropped": raw_hop_ge1 - class_totals["suspicious"],
            "reason": "blacklist wins over hop 1..5",
            "generated_at": run_ts,
        },
        {
            "stage": "L2_cohort",
            "filter": "licit_minus_illicit_minus_suspicious",
            "n_in": raw_licit_acc,
            "n_out": class_totals["licit"],
            "n_dropped": raw_licit_acc - class_totals["licit"],
            "reason": "illicit and suspicious overlap removed from licit.accounts",
            "generated_at": run_ts,
        },
        {
            "stage": "L2_cohort",
            "filter": "unlabeled_remainder",
            "n_in": universe_total,
            "n_out": class_totals["unlabeled"],
            "n_dropped": universe_total - class_totals["unlabeled"],
            "reason": "universe minus illicit, suspicious, and licit",
            "generated_at": run_ts,
        },
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    counts_path = output_dir / "cohort_counts.csv"
    nflow_path = output_dir / "cohort_nflow.csv"
    pd.DataFrame(count_records).to_csv(counts_path, index=False)
    pd.DataFrame(nflow_records).to_csv(nflow_path, index=False)
    return counts_path, nflow_path


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    steps_to_run = (
        [name for name, _ in SQL_STEPS] + ["nflow"]
        if args.step == "all"
        else [args.step]
    )
    sql_map = dict(SQL_STEPS)

    if args.dry_run:
        print(
            f"[cohort:dry-run] schema={args.schema} illicit={args.illicit_schema} "
            f"licit={args.licit_schema} steps={steps_to_run}"
        )
        for step in steps_to_run:
            if step in sql_map:
                rendered = render_sql(
                    sql_map[step],
                    transform_schema=args.schema,
                    illicit_schema=args.illicit_schema,
                    licit_schema=args.licit_schema,
                )
                print(f"\n--- {step} ({sql_map[step]}) ---")
                print(rendered)
            else:
                print(
                    f"\n--- {step} -> writes cohort_counts.csv & cohort_nflow.csv in {args.output_dir} ---"
                )
        return 0

    engine = get_local_engine()
    try:
        for step in steps_to_run:
            if step in sql_map:
                print(f"[cohort] running {step}...", flush=True)
                rendered = render_sql(
                    sql_map[step],
                    transform_schema=args.schema,
                    illicit_schema=args.illicit_schema,
                    licit_schema=args.licit_schema,
                )
                execute_sql_step(
                    engine,
                    rendered,
                    work_mem=args.work_mem,
                    maintenance_work_mem=args.maintenance_work_mem,
                )
            elif step == "nflow":
                print("[cohort] verifying partition & writing CSVs...", flush=True)
                counts_path, nflow_path = write_cohort_nflow(
                    engine,
                    transform_schema=args.schema,
                    illicit_schema=args.illicit_schema,
                    licit_schema=args.licit_schema,
                    output_dir=Path(args.output_dir),
                )
                print(f"[cohort:counts] {counts_path}")
                print(f"[cohort:nflow] {nflow_path}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
