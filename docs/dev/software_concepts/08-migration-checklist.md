# Migration checklist

- **Status:** accepted 
- **Parent:** [`README.md`](README.md)
- **Use when:** starting the next implementation slice.

## Order

These are tracer bullets: each step is a thin end-to-end slice with an observable “Done when”, not a horizontal layer.

1. **Extract `db.py`.** Move environment loading, link getters, engine creation, `validate_schema_name`, `safe_error_message`, `quote_identifier`, and `qualified_name` out of `extract/main.py`.
   - Done when: `transform/profile/*` and `load/main.py` import `db.py`, not `extract/main.py`; `extract/main.py` still works as a facade.
2. **Add `profile/schema.py`.** *(Done)* Define `DatasetRef`, `ProfileRecord`, `StageManifest`, `ComparisonRecord`.
   - Done when: a raw-vs-raw profile produces the same shape with delta 0.
3. **Add `profile_local.py`, `profile_quality.py`, `profile_overlap_local.py`.** *(Done)* Read-only, snapshot-tagged.
   - Done when: outputs record `is_partial` provenance and local cohort counts.
4. **Add the Postgres adapter and `compare/` (`compare.py`).** *(Adapter done; `compare/` pending)* No Parquet profiling adapter yet.
   - Done when: the comparison refuses mixed snapshots and writes long-format rows.
5. **Add stage manifests** to cohort and feature writers.
   - Done when: each manifest records input/output rows, filters, SQL hash, snapshot, `is_partial`.
6. **Build cohort + features.** Licit ingestion is 100% complete; materialize L1/L2 in a dedicated transform schema and keep L3 flat at wallet grain.
   - Done when: priority tests and feature fixture tests pass.
7. **Add the test suite** from `06-testing.md` (`pytest` in `pyproject.toml`).
   - Done when: priority, formulas, n-flow, and stratified golden sample checks are green; the small/medium suite runs on every commit or pre-commit hook.
8. **Add hypothesis helpers and runners.** Only after the cohort/feature contracts are stable.
   - Done when: H2/H4/H6 dry-runs read only cohort/features and write result tables.
9. **Freeze/export.** *(Built for L0 raw in `load/main.py`; ready for L2/L3 once Step 6 completes.)*
   - Done when: manifest, hashes, row counts, and n-flow reconcile.

## Do not start with

- A framework (Airflow/Dagster/Prefect).
- A full hexagonal/onion layout.
- A repository class per table.
- A generic plugin system.
- A shared H2/H4/H6 base runner.

## Debate

- Is step 1 enough to remove the profile→ingest coupling, or do we need `access.py` too?
-> `db.py` alone is enough right now: every current import from `extract/main.py` across `profile/` and `load/main.py` is purely engine/env/schema plumbing. Defer `access.py` until notebooks or hypothesis runners need shared bounded L2/L3 read helpers.
- Should step 3 run before `compare.py`, or can they be built together?
-> Before, in order to separate concerns and verify real `ProfileRecord` outputs first (already proven in the codebase).
- Is the cohort builder or the profile suite the real first slice?
-> The profile suite was the first slice (already built and surfaced the cohort/transaction join bottleneck); the cohort builder (L1/L2) is now the next real slice.
- Which step is allowed to change a published output column name?
-> Internal renames happen before Step 9 freeze (e.g., during Step 6 L1/L2/L3 build). After Step 9 publication, no step may rename a published snapshot column in place — bump `feature_version`, publish a new snapshot, and record the rename in the manifest/changelog.
