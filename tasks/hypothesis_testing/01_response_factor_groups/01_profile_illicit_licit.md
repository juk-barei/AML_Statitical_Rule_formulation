# Profile illicit and licit databases

- **Status:** done
- **Blocked by:** —
- **Blocks:** `02_group_validation.md`, `03_reproducible_evidence.md`
- **Owner:** subagent
- **Output:** `docs/context/statistical_info.md`; profiling script in `scripts/`
- **Updated:** 2026-11-20

## Objective

Use `src/.env.example` to profile both online DBs: shape, relations, columns, dtypes, coverage, overlap. Do not read or print `.env`. Decide whether the licit data supports a third group.

## Resources / context

- `src/.env.example` — database variable names; never read `.env`
- `src/scripts/ETL.py` — ingestion, loader, and source-link behavior
- `docs/context/statistical_info.md` — proposed groups and profiling
- `AGENTS.md` — data authority, cohort priority, task rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `scripts/profile_databases.py` | read-only profiling logic |
| update | `docs/context/statistical_info.md` | profile findings and 3-group verdict |
| create | `outputs/profiling/db_overview.csv` | table/column counts and coverage |

## Implementation points

- Connect from `src/.env.example`; never print URLs or `.env`.
- Profile shape, relations, columns, dtypes, nulls, time range, and overlap.
- Print every number the report uses; no hard-coded counts.

## Done when

- Script is reproducible and prints the numbers it supports.
- Numbers cite script path + line.
- `statistical_info.md` is concise and states whether 3 groups fit.
