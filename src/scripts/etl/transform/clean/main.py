"""L1 cleaning runner — executes direct SQL steps in order and writes L1 n-flow CSVs.

Usage (inspect plan without touching PostgreSQL):
    python -m src.scripts.etl.transform.clean.main --dry-run

Usage (execute step-by-step or end-to-end):
    python -m src.scripts.etl.transform.clean.main --step 01_clean_transactions
    python -m src.scripts.etl.transform.clean.main --step 02_clean_wallet_hops
    python -m src.scripts.etl.transform.clean.main --step 03_clean_indexes
    python -m src.scripts.etl.transform.clean.main --step nflow
    python -m src.scripts.etl.transform.clean.main --step all
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

SQL_DIR = Path(__file__).resolve().parent
CLEAN_OUTPUT_DIR = ETL_OUTPUT_DIR / "transform" / "clean"

SQL_STEPS: tuple[tuple[str, str], ...] = (
    ("01_clean_transactions", "01_clean_transactions.sql"),
    ("02_clean_wallet_hops", "02_clean_wallet_hops.sql"),
    ("03_clean_indexes", "03_clean_indexes.sql"),
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
        help="Run one step or all L1 steps in sequence. Default: all.",
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
        default=str(CLEAN_OUTPUT_DIR),
        help="Directory for L1 n-flow and conflict audit CSVs.",
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


def write_clean_nflow(
    engine: Engine,
    *,
    transform_schema: str,
    illicit_schema: str,
    licit_schema: str,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Query L1 row counts and emit reconciled n-flow and conflict summary CSVs."""
    t_schema = validate_schema_name(transform_schema)
    i_schema = validate_schema_name(illicit_schema)
    l_schema = validate_schema_name(licit_schema)
    run_ts = datetime.now(UTC).isoformat(timespec="seconds")

    with engine.connect() as conn:
        n_illicit = int(conn.execute(text(f"SELECT COUNT(*) FROM {i_schema}.transactions")).scalar_one())
        n_licit = int(conn.execute(text(f"SELECT COUNT(*) FROM {l_schema}.transactions")).scalar_one())
        raw_union = n_illicit + n_licit
        summary = conn.execute(
            text(
                f"""
                SELECT
                    COUNT(*) AS deduped_rows,
                    COUNT(*) FILTER (WHERE in_both_schemas) AS overlap_tx_hash,
                    COUNT(*) FILTER (WHERE has_cross_schema_conflict) AS conflict_tx_hash,
                    COUNT(*) FILTER (WHERE timestamp_flag <> 'ok') AS bad_ts_rows,
                    COUNT(*) FILTER (WHERE amount_flag IN ('null', 'negative', 'sentinel', 'above_supply')) AS invalid_amt_rows,
                    COUNT(*) FILTER (WHERE amount_flag = 'zero') AS zero_amt_rows,
                    COUNT(*) FILTER (WHERE amount_flag = 'dust') AS dust_rows,
                    COUNT(*) FILTER (WHERE is_1sun_dust) AS one_sun_rows,
                    COUNT(*) FILTER (WHERE is_trx_4444_artifact) AS trx_4444_rows,
                    COUNT(*) FILTER (WHERE is_valid_for_features) AS valid_for_features,
                    COUNT(*) FILTER (WHERE is_valid_for_features AND NOT is_trx_4444_artifact) AS valid_excl_4444
                FROM {t_schema}.clean_transactions
                """
            )
        ).mappings().one()
        flag_rows = conn.execute(
            text(
                f"""
                SELECT
                    source_schema,
                    token_symbol,
                    amount_flag,
                    timestamp_flag,
                    is_trx_4444_artifact,
                    COUNT(*) AS rows
                FROM {t_schema}.clean_transactions
                GROUP BY source_schema, token_symbol, amount_flag, timestamp_flag, is_trx_4444_artifact
                ORDER BY source_schema, token_symbol, amount_flag, timestamp_flag
                """
            )
        ).mappings().all()

    deduped = int(summary["deduped_rows"])
    valid_feat = int(summary["valid_for_features"])
    valid_no4444 = int(summary["valid_excl_4444"])

    nflow_records = [
        {
            "stage": "L1_clean",
            "filter": "raw_union_to_deduped_tx_hash",
            "n_in": raw_union,
            "n_out": deduped,
            "n_dropped": raw_union - deduped,
            "reason": f"cross-schema tx_hash dedupe (illicit={n_illicit}, licit={n_licit})",
            "generated_at": run_ts,
        },
        {
            "stage": "L1_clean",
            "filter": "flag_valid_for_features_baseline",
            "n_in": deduped,
            "n_out": valid_feat,
            "n_dropped": deduped - valid_feat,
            "reason": "non-destructive gate: ts_flag='ok' and amount_flag not in (null,negative,sentinel,above_supply,zero)",
            "generated_at": run_ts,
        },
        {
            "stage": "L1_clean",
            "filter": "sensitivity_exclude_trx_4444_artifact",
            "n_in": valid_feat,
            "n_out": valid_no4444,
            "n_dropped": valid_feat - valid_no4444,
            "reason": "sensitivity gate excluding upstream 0.225-rate 4444.444444 TRX rows",
            "generated_at": run_ts,
        },
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    nflow_path = output_dir / "clean_nflow.csv"
    flags_path = output_dir / "clean_flag_breakdown.csv"
    pd.DataFrame(nflow_records).to_csv(nflow_path, index=False)
    pd.DataFrame([dict(r) for r in flag_rows]).to_csv(flags_path, index=False)
    return nflow_path, flags_path


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
            f"[clean:dry-run] schema={args.schema} illicit={args.illicit_schema} "
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
                print(f"\n--- {step} -> writes clean_nflow.csv & clean_flag_breakdown.csv in {args.output_dir} ---")
        return 0

    engine = get_local_engine()
    try:
        for step in steps_to_run:
            if step in sql_map:
                print(f"[clean] running {step}...", flush=True)
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
                print("[clean] computing L1 n-flow CSVs...", flush=True)
                nflow_path, flags_path = write_clean_nflow(
                    engine,
                    transform_schema=args.schema,
                    illicit_schema=args.illicit_schema,
                    licit_schema=args.licit_schema,
                    output_dir=Path(args.output_dir),
                )
                print(f"[clean:nflow] {nflow_path}")
                print(f"[clean:flags] {flags_path}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
