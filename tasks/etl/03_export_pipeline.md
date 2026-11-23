# Export pipeline — `load.py`

- **Status:** done
- **Blocked by:** [`01_export_contract.md`](01_export_contract.md); complete ingestion run
  (`python -m src.scripts.etl.ingest --status`)
- **Blocks:** [`04_web_serving.md`](04_web_serving.md); every hypothesis step after EDA
- **Owner:** worker
- **Output:** `src/scripts/etl/load.py`; `outputs/etl/export/phase1_raw_{illicit,licit}_<UTC>/`
- **Updated:** 2026-11-23

## Objective

Implement the designated export writer. It reads the mirror read-only, writes one frozen
snapshot under `outputs/etl/export/<snapshot>/`, and records the manifest the contract
requires. `src/scripts/etl/load.py` is currently a stub (`parse_args` only).

## Resources / context

- `docs/context/export_contract.md` — the contract this implements
- [`src/scripts/etl/README.md`](../../src/scripts/etl/README.md) — handoff layout, format
  decision, sampling rule, export checklist
- `src/scripts/etl/ingest.py` — engine/environment helpers and the CLI style to match
- [`src/scripts/etl/transform/README.md`](../../src/scripts/etl/transform/README.md) —
  cleaning, cohort priority, eligibility, features
- `AGENTS.md` — freeze-before-export, sampling, and data-hygiene rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/scripts/etl/load.py` | CLI + export implementation |
| create | `src/scripts/etl/tests/test_load_export.py` | contract checks |
| create | `outputs/etl/export/<snapshot>/` | the snapshot itself |

## Implementation points

- **CLI:** `--schema`, `--stage`, `--tables`, `--out-dir`, `--name`, `--format`, `--compression`,
  `--allow-partial`, `--allow-large-csv`, `--keep-hex`, `--force`, `--dry-run`;
  credentials load internally from `src/.env`, never printed.
- **Export path:** Postgres → `COPY` to disk → DuckDB to Parquet with
  `COMPRESSION zstd`; pandas is not in the bulk path.
- **Snapshot tree:** `manifest.json`, `DATA_DICTIONARY.md`, `nflow.csv`, `README.md`,
  and raw table files named `<snapshot>__<table>.parquet` (or `.csv[.gz]`). The default
  snapshot is `phase<N>_<stage>_<schema>_<UTC>`; `phase` comes from `pyproject.toml`
  `[tool.capstone].phase`.
- **Manifest:** snapshot id, phase, stage, schema, source, run id, per-file row count,
  columns, SHA-256, plus the sampling design when a sample is drawn.
- **Row counts:** exported counts must equal the SQL n-flow; a mismatch fails the run.
- **Sampling:** sample wallets, never transaction rows; census small/rare arms; keep all
  events for selected wallets; stratify suspicious by hop and licit by activity band.
- **Refuse unsafe output:** writes only inside the resolved `--out-dir`; no
  `hex_address`/`_etl_*`/`pipeline_crawl_state` unless `--keep-hex` or a task declares it;
  no credentials in any file.
- **Verify:** every Parquet file opens in DuckDB; a rerun into an existing snapshot
  refuses instead of overwriting a frozen handoff.

## Evidence

- `python -m src.scripts.etl.tests.test_load_export` passes.
- `phase1_raw_illicit_20261123T043155Z`: 4 files, 26,869,947 rows, 1.8 GB total, all hashes verified.
- `phase1_raw_licit_20261123T043744Z`: 5 files, 18,022,456 rows, 1.2 GB total, all hashes verified.
- Both manifests report `partial: false`, `phase: 1`, and `stage: raw`; `nflow.csv` and DuckDB counts match the manifest.

## Done when

- `--dry-run` prints the plan and exact per-table row counts without writing.
- Snapshots are written under `outputs/etl/export/<snapshot>/` with complete manifests.
- `python -m src.scripts.etl.tests.test_load_export` passes.
- The export checklist in `src/scripts/etl/README.md` is satisfied item by item.
