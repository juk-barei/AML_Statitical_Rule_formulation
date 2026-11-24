"""Orchestrate the available local profiling parts.

    python -m src.scripts.etl.profile.run_profile --parts local,quality,overlap,features

Feature/benchmark runs are heavy; use --limit-wallets or --benchmark-limit for a
bounded smoke run. Local-vs-online comparison is not implemented yet.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from src.scripts.config import PROFILING_OUTPUT_DIR
from src.scripts.etl.extract.main import get_local_engine, validate_schema_name
from src.scripts.etl.transform.profile import (
    benchmark_queries,
    profile_features,
    profile_local,
    profile_quality,
)
from src.scripts.etl.transform.profile.adapters import PostgresDataset
from src.scripts.etl.transform.profile.profile_overlap_local import profile_overlap
from src.scripts.etl.transform.profile.schema import utc_snapshot_id

AVAILABLE_PARTS = ("local", "quality", "overlap", "features", "benchmarks")


def _schemas(value: str) -> list[str]:
    return [validate_schema_name(item.strip()) for item in value.split(",") if item.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts", default="local,quality,overlap")
    parser.add_argument("--schemas", default="illicit,licit")
    parser.add_argument("--mode", choices=("quick", "full"), default="quick")
    parser.add_argument("--sample-percent", type=float, default=2.0)
    parser.add_argument("--output-dir", default=str(PROFILING_OUTPUT_DIR))
    parser.add_argument("--snapshot-id", default="")
    parser.add_argument("--limit-wallets", type=int, default=None)
    parser.add_argument("--benchmark-queries", default="all")
    parser.add_argument("--benchmark-limit", type=int, default=None)
    parser.add_argument("--benchmark-repeat", type=int, default=1)
    args = parser.parse_args(argv)

    requested = AVAILABLE_PARTS if args.parts == "all" else tuple(
        part.strip() for part in args.parts.split(",") if part.strip()
    )
    unknown = sorted(set(requested) - set(AVAILABLE_PARTS))
    if unknown:
        raise ValueError(f"unknown parts: {', '.join(unknown)}; available: {', '.join(AVAILABLE_PARTS)}")

    output_dir = Path(args.output_dir)
    snapshot_id = args.snapshot_id or utc_snapshot_id()
    schemas = _schemas(args.schemas)
    engine = get_local_engine()
    try:
        if "local" in requested:
            for schema in schemas:
                dataset = PostgresDataset(engine=engine, schema=schema, snapshot_id=snapshot_id)
                paths = profile_local.profile_schema(
                    dataset,
                    output_dir,
                    mode=args.mode,
                    sample_percent=args.sample_percent,
                    file_prefix=f"local_{schema}",
                )
                print(f"[local:{schema}] {', '.join(str(path) for path in paths.values())}")
        if "quality" in requested:
            rows = []
            for schema in schemas:
                dataset = PostgresDataset(engine=engine, schema=schema, snapshot_id=snapshot_id)
                rows.extend(profile_quality.collect_checks(dataset))
            path = profile_quality.write_checks(rows, output_dir)
            print(f"[quality] {path}")
        if "overlap" in requested:
            if "illicit" not in schemas or "licit" not in schemas:
                raise ValueError("overlap requires illicit and licit in --schemas")
            illicit = PostgresDataset(engine=engine, schema="illicit", snapshot_id=snapshot_id)
            licit = PostgresDataset(engine=engine, schema="licit", snapshot_id=snapshot_id)
            paths = profile_overlap(illicit, licit, output_dir)
            print(f"[overlap] {', '.join(str(path) for path in paths.values())}")
        if "features" in requested:
            datasets = [
                PostgresDataset(engine=engine, schema=schema, snapshot_id=snapshot_id)
                for schema in schemas
            ]
            paths = profile_features.profile_features(
                datasets,
                output_dir,
                limit_wallets=args.limit_wallets,
            )
            print(f"[features] {', '.join(str(path) for path in paths.values())}")
        if "benchmarks" in requested:
            benchmark_argv = [
                "--schema",
                ",".join(schemas),
                "--queries",
                args.benchmark_queries,
                "--output-dir",
                str(output_dir),
                "--snapshot-id",
                snapshot_id,
                "--repeat",
                str(args.benchmark_repeat),
            ]
            if args.benchmark_limit is not None:
                benchmark_argv.extend(["--limit", str(args.benchmark_limit)])
            benchmark_queries.main(benchmark_argv)
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
