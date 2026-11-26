# Export contract — frozen snapshot

- **Status:** done
- **Blocked by:** —
- **Blocks:** `03_export_pipeline.md`
- **Owner:** worker
- **Output:** `docs/context/export_contract.md` (implemented by `src/scripts/etl/load/main.py`)
- **Updated:** 2026-11-23

## Objective

Freeze what a handoff snapshot must contain **before** any exporter is written:
manifest fields, per-table row counts, exclusions, format and compression, snapshot
directory, and the credential ban. This task produces the contract document and the
checklist only — the exporter is `03_export_pipeline.md`.

## Resources / context

- [`src/scripts/etl/README.md`](../../src/scripts/etl/README.md) — handoff layout,
  format decision, sampling rule, export checklist
- `AGENTS.md` — freeze-before-export, sampling, and data-hygiene rules
- `docs/context/sampling_evaluation.md` — why the frame must be frozen before pooling
- `docs/context/etl_incremental_safety.md` — what a rerun replaces vs resumes
- `outputs/etl/load/` — snapshot root, one directory per snapshot

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `docs/context/export_contract.md` | manifest schema, snapshot fields, exclusions, format |
| update | `tasks/etl/README.md` | status and output once the contract is frozen |

## Implementation points

- **Snapshot identity:** `phase<N>_<stage>_<schema>_<UTC>`; phase from
  `[tool.capstone].phase`; stage `raw|transformed`; snapshot time (UTC), source database,
  schema, ETL run id, and mirror row counts per table.
- **Manifest:** `manifest.json` per snapshot with per-file row count, columns, and
  SHA-256; one manifest entry per exported file, no file outside the manifest.
- **Row counts and n-flow:** exported counts must reconcile with the SQL n-flow; a
  mismatch blocks the snapshot, it is not explained away.
- **Exclusions:** every filter, eligibility rule, and dropped column (`hex_address`,
  `_etl_*`, `pipeline_crawl_state`) stated once with its row cost.
- **Format:** Parquet + zstd is the canonical analysis handoff; CSV only for small
  manifests and data dictionaries; DuckDB reads the Parquet.
- **Layout:** everything under `outputs/etl/load/<snapshot>/`; no ad-hoc top-level
  output folder.
- **Credentials:** no connection string, password, or `src/.env` value in any exported
  file, manifest, log line, or task record.
- **Sampling:** if a sample is drawn, the seed, strata, cluster, weights, and design
  effect are recorded in the manifest; a demo sample is labelled and excluded from
  inference.

## Done when

- `docs/context/export_contract.md` states every field above and is under 200 words plus
  tables.
- The checklist is copy-paste runnable and each item names the file it checks.
- `03_export_pipeline.md` can be implemented from the contract without a new decision.
