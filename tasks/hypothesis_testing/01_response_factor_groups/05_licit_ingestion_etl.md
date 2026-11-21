# Licit ingestion and ETL path

- **Status:** blocked
- **Blocked by:** local PostgreSQL down
- **Blocks:** `11_licit_eda_notebook.md`
- **Owner:** worker
- **Output:** licit tables in the mirror
- **Updated:** 2026-11-20

## Objective

Add a licit source path to ETL without colliding with illicit tables. The current code defines `get_licit_online_db_link()` but `run_etl()` calls only the illicit link.

## Resources / context

- `src/scripts/ETL.py` — ingestion, loader, and source-link behavior
- `src/.env.example` — database variable names; never read `.env`
- `src/notebooks/1.2_LICIT_EDA.ipynb`
- `docs/context/cohort_contract.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/scripts/ETL.py` | licit source selection and target names |
| create | `docs/context/licit_ingestion.md` | commands, table names, caveats |
| update | `docs/flow.md` | licit data boundary |

## Implementation points

- Add `--source illicit|licit` or equivalent.
- Namespace licit tables; do not overwrite illicit tables.
- Keep resume/idempotency; never print credentials.

## Done when

- `--source illicit|licit` or equivalent.
- Licit tables are separate/namespaced.
- Rerun and resume are safe.
