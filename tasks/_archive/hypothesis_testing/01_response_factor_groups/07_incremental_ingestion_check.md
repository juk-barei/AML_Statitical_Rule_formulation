# Incremental ingestion safety

- **Status:** done
- **Blocked by:** `06_online_db_refresh_profile.md`
- **Blocks:** `05_licit_ingestion_etl.md`
- **Owner:** worker
- **Output:** ETL safety note
- **Updated:** 2026-11-20

## Objective

Check whether ingesting more illicit data into the existing mirror causes duplicates, overwrites, or progress conflicts under the current ETL shard logic.

## Resources / context

- `src/scripts/ETL.py` — ingestion, loader, and source-link behavior
- `_etl_progress` and `_etl_runs` tables
- `docs/context/licit_ingestion.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `docs/context/etl_incremental_safety.md` | duplicate/overwrite analysis |
| update | `src/scripts/ETL.py` | only if a destructive path is found |

## Implementation points

- Trace shard keys, primary keys, and resume behavior.
- Flag duplicate/overwrite risks.
- Document a safe rerun command.

## Done when

- Duplicate/overwrite behavior is traced.
- A safe rerun command is documented.
- Any destructive path is flagged.
