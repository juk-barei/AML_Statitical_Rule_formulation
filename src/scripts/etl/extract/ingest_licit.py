"""Resume licit ingestion, print status, and verify coverage.

This is a thin wrapper around the existing ingest CLI. It always uses
``--source licit --schema licit`` so the ETL role never targets ``public``.

Run from the repo root:

    python -m src.scripts.etl.ingest_licit

If the source connection times out again, retry with fewer workers or a
smaller batch:

    python -m src.scripts.etl.ingest_licit --workers 3 --batch-size 25000
"""
from __future__ import annotations

import argparse
import subprocess
import sys

from src.scripts.config import ROOT
from src.scripts.etl.verify_ingestion import verify_schema

SOURCE = "licit"
SCHEMA = "licit"


def _run(command: list[str]) -> int:
    print(f"+ {' '.join(command)}", flush=True)
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--shards-per-table", type=int)
    parser.add_argument("--tables")
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Skip the resume run and only print progress.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Return 0 even when ingestion is incomplete.",
    )
    args = parser.parse_args(argv)

    base = [
        sys.executable,
        "-m",
        "src.scripts.etl.ingest",
        "--source",
        SOURCE,
        "--schema",
        SCHEMA,
    ]

    if not args.status_only:
        resume = [*base, "--resume"]
        if args.workers is not None:
            resume.extend(["--workers", str(args.workers)])
        if args.batch_size is not None:
            resume.extend(["--batch-size", str(args.batch_size)])
        if args.shards_per_table is not None:
            resume.extend(["--shards-per-table", str(args.shards_per_table)])
        if args.tables:
            resume.extend(["--tables", args.tables])
        code = _run(resume)
        if code != 0:
            print(
                f"Ingestion exited with code {code}; checking coverage anyway.",
                file=sys.stderr,
            )

    _run([*base, "--status"])
    return verify_schema(
        SCHEMA,
        require_complete=not args.allow_incomplete,
    )


if __name__ == "__main__":
    raise SystemExit(main())
