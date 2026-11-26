# Export contract — frozen snapshot

- **Status:** implemented by `src/scripts/etl/load/main.py`
- **Updated:** 2026-11-26

A snapshot is one directory under `outputs/etl/load/<snapshot>/` (an explicit external path is allowed). It contains data files plus `manifest.json`, `nflow.csv`, `DATA_DICTIONARY.md`, and `README.md`.

## Required fields

| Field | Rule |
| --- | --- |
| Snapshot identity | `phase<N>_<stage>_<schema>_<UTC>`; directory name; UTC `created_at`; source `local PostgreSQL mirror` |
| Project phase | positive integer from `[tool.capstone].phase` in `pyproject.toml` |
| Stage | `raw` or `transformed`; recorded in the snapshot name and manifest |
| Per table | file, rows, bytes, SHA-256, columns, status, coverage %, latest run id and run status |
| Row counts | exact local `count(*)`; exported count must equal it; `nflow.csv` records source/ingested/local/exported |
| Exclusions | internal tables (`_etl_*`, `pipeline_crawl_state`); `hex_address` unless `--keep-hex` |
| Partial data | `partial: true`; requires `--allow-partial`; status per table |
| Format | Parquet + zstd default; CSV + gzip optional; CSV above 1,000,000 rows requires `--allow-large-csv` |
| Numeric | constrained `numeric` → `DECIMAL(p,s)`; unconstrained `numeric` → `DOUBLE` plus `<column>_exact` VARCHAR |
| Credentials | none in any file, manifest, log, or task record |
| Overwrite | refuse an existing snapshot unless `--force` |

The manifest is written last. A snapshot without a manifest is not a handoff. `phase` and `stage` are required fields, not optional metadata.
