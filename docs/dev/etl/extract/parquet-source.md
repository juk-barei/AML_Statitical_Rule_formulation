# Parquet source adapter for `extract/main.py`

- **Date:** 2026-11-24
- **Edits:** 3
- **Code:** `src/scripts/etl/extract/parquet_source.py`, `src/scripts/etl/extract/main.py`
- **Contract:** `src/scripts/etl/README.md` § Extract → Parquet source

## The decision

The online PostgreSQL path and the Parquet path share a destination and a
bookkeeping contract, but they do not share a reader. The online path pages a
remote server through `pandas` and a sharded worker pool. The Parquet path has
no server, no shards, and no reason to use pandas; rows already sit in a local
columnar file.

`extract/parquet_source.py` is therefore a deep module behind one call:

```python
run_parquet_ingest(args) -> int
```

The caller states intent — absolute snapshot, target schema, table list — and
does not construct DuckDB SQL, map types, or write progress rows.

## Mechanism

1. **Manifest is the authority.** `manifest.json` must exist and declare
   `format: parquet`, a schema, a snapshot id, and one record per table. Each
   record supplies the relative file name, row count, column order, SHA-256, and
   status.
2. **Absolute path only.** `--parq-source-path` is rejected if relative. A relative
   path changes meaning when the working directory changes, which breaks a
   reproducible handoff.
3. **Three gates before writing.**
   - file SHA-256 equals the manifest value (default; `--parq-skip-hash` skips only
     this hash);
   - DuckDB `DESCRIBE` columns equal the manifest column list and order;
   - manifest row count and table status are recorded.
4. **Type mapping is explicit.** DuckDB types are mapped to a small allow-list.
   An unknown type fails instead of silently becoming `TEXT`.
5. **`amount_exact` reconstruction.** `load.py` exports an uncapped PostgreSQL
   `numeric` as `DOUBLE` plus `<name>_exact` VARCHAR because DuckDB DECIMAL is
   capped at 38 digits. The loader drops the `DOUBLE`, recreates the original
   column as `NUMERIC`, and selects the exact text into it.
6. **Streamed COPY.** DuckDB `fetchmany(batch_size)` → CSV buffer → psycopg
   `COPY FROM STDIN`. No pandas DataFrame, no whole-table `fetchall`, no
   server-side file path. DuckDB is capped at `memory_limit=1GB`, two threads,
   and a temporary directory for spill.
7. **Existing progress contract.** The adapter creates `ShardTask` records with
   one shard per table and calls the same `seed_progress`, `write_progress`,
   `build_ingestion_report`, and `finish_run` used by the online path. Thus
   `verify_ingestion`, `--status`, and the notebooks see one contract.
8. **Failure is quarantined.** A failed table is truncated, marked `failed`, and
   the run continues. `--resume` skips completed tables and reloads failed or
   partial tables from scratch.

## Why not reuse the online worker pool

The online worker's unit is a shard defined by a source query. A Parquet file
is already a closed, local unit. Running it through a process pool would copy
the worker engine initialization, the keyset logic, and the remote timeout
policy without using any of them. The Parquet adapter is single-process and
table-at-a-time on purpose.

## Limits

- One table at a time. A 15M-row table is bounded by DuckDB scan plus local
  PostgreSQL WAL/fsync, not by network.
- `COPY` uses `\N` as the NULL marker, inherited from the online path. A literal
  string `\N` would be read as NULL; the source snapshot does not contain one.
- The adapter cannot reconstruct `hex_address`, `_etl_*`, or
  `pipeline_crawl_state`; a raw export intentionally excludes them.
- `--parq-allow-schema-mismatch` is a test escape hatch. It keeps the manifest
  schema in the report, but it lets a licit snapshot land in another schema.
  Never use it for a handoff.
- Parquet tables are truncated and reloaded; there is no row-level upsert.

## Verification

```bash
# No writes, but hashes/columns/rows are checked.
python -m src.scripts.etl.extract.main \
  --source parquet \
  --parq-source-path /absolute/path/to/phase1_raw_illicit_20261123T043155Z \
  --schema illicit --dry-run

# Unit checks.
python -m src.scripts.etl.extract.tests.validate_parquet_source
python -m src.scripts.etl.extract.tests.validate_ingest_args

# After a real load.
python -m src.scripts.etl.extract.verify_ingestion --schema illicit
```

A successful load reconciles three numbers per table: manifest rows, rows
streamed by DuckDB, and PostgreSQL `COUNT(*)` in the report. A mismatch fails
the table, not the whole run.
