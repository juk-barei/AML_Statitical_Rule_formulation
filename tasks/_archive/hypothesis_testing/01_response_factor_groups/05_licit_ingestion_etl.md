# Licit ingestion and ETL path

- **Status:** done
- **Blocked by:** —
- **Blocks:** `11_licit_eda_notebook.md`
- **Owner:** worker
- **Output:** licit tables in the mirror
- **Updated:** 2026-11-23

## Objective

Add a licit source path to ETL without colliding with illicit tables. `src/scripts/etl/ingest.py` exposes `--source illicit|licit`; the open work is completing the licit transaction shards and documenting the table names. Local PostgreSQL is up. The default `public` schema is not writable by the ETL role, so pass `--schema licit`.

## Resources / context

- `src/scripts/etl/ingest.py` — ingestion, loader, and source-link behavior
- `src/.env.example` — database variable names; never read `.env`
- `src/notebooks/1.2_LICIT_EDA.ipynb`
- `docs/context/cohort_contract.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/scripts/etl/ingest.py` | licit source selection and target names |
| create | `src/scripts/etl/ingest_licit.py` | resume + status + coverage wrapper |
| create | `src/scripts/etl/verify_ingestion.py` | read-only coverage check |
| create | `docs/context/licit_ingestion.md` | commands, table names, caveats |
| update | `docs/flow.md` | licit data boundary |

## Implementation points

- Namespace licit tables; do not overwrite illicit tables.
- Keep resume/idempotency; never print credentials.
- Confirm `--source licit` end to end before `11_licit_eda_notebook.md` starts.

## Result

Licit ingestion completed on `etl_20261122T034716_677817Z`:

- `accounts`: 6,614,681 / 6,614,681 (100%)
- `transactions`: 11,326,298 / 11,326,298 (100%)
- 5/5 shards complete

`verify_ingestion --schema licit` exits 0. No more ingestion will run; the local
mirror is the frozen analysis source.

## Done when

- `--source illicit|licit` or equivalent.
- Licit tables are separate/namespaced.
- Licit transactions reach 100% coverage.
- Rerun and resume are safe.
