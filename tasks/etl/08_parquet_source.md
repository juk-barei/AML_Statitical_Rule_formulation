# Parquet source adapter — `extract/main.py`

- **Status:** done
- **Blocked by:** —
- **Blocks:** offline teammate setup; full-pipeline reproduction from the public snapshot
- **Owner:** worker
- **Output:** `src/scripts/etl/extract/parquet_source.py`; `--source parquet` in `extract/main.py`
- **Updated:** 2026-11-24

## Objective

Load a frozen Parquet export snapshot into the local PostgreSQL mirror without
the online source database. The manifest is the authority for tables, columns,
row counts, and hashes.

## Resources / context

- `src/scripts/etl/README.md` § Extract → Parquet source
- `docs/dev/etl/extract/parquet-source.md` — mechanism and limits
- accepted concepts `01`, `02`, `05`, `07`, `09`, `10`
- `src/scripts/etl/load/load.py` — the manifest producer

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `src/scripts/etl/extract/parquet_source.py` | manifest validation, DuckDB → COPY, progress |
| update | `src/scripts/etl/extract/main.py` | `--source parquet`, `--parq-source-path`, dispatch |
| create | `src/scripts/etl/extract/tests/validate_parquet_source.py` | mapping, manifest, hash, partial checks |
| create | `docs/dev/etl/extract/parquet-source.md` | technical note |
| update | `src/scripts/etl/README.md` | commands and rules |

## Implementation points

- Absolute `--parq-source-path`; `manifest.json` required.
- SHA-256 and manifest column/row checks by default; `--parq-skip-hash` for speed.
- `amount_exact` → PostgreSQL `NUMERIC`; drop the `DOUBLE` helper.
- Streamed DuckDB `fetchmany` → psycopg `COPY FROM STDIN`; no pandas bulk path.
- Reuse `_etl_runs` / `_etl_progress`; `verify_ingestion` works after import.
- `--resume` skips completed tables; failed tables are truncated and retried.
- `--parq-allow-partial` and `--parq-allow-schema-mismatch` are explicit escape hatches.

## Done when

- `--source parquet --parq-source-path ... --dry-run` prints the snapshot plan with no writes.
- A real import writes the expected rows and `verify_ingestion` passes.
- `python -m src.scripts.etl.extract.tests.validate_parquet_source` passes.

## Verification

- `validate_parquet_source`, `validate_ingest_args`, and `load_export` pass.
- Full illicit snapshot dry-run prints 4,870,000 / 17,046 / 15,017,691 / 6,965,210.
- A 5-row `blacklisted_wallets` load into a throwaway schema reconciled
  manifest, streamed, and local counts, and `verify_ingestion` passed.

