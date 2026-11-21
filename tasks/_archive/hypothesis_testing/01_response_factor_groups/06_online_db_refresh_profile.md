# Online DB refresh and fixed sample

- **Status:** done
- **Blocked by:** —
- **Blocks:** `07_incremental_ingestion_check.md`, `08_sampling_evaluation.md`
- **Owner:** subagent
- **Output:** `docs/context/statistical_info.md` update
- **Updated:** 2026-11-20

## Objective

Both online DBs have newer data. Profile the online overview and recommend a fixed sample size for this phase while ingestion continues.

## Resources / context

- `src/.env.example` — database variable names; never read `.env`
- `src/scripts/ETL.py` — ingestion, loader, and source-link behavior
- `scripts/profile_databases.py`
- `docs/context/statistical_info.md` — proposed groups and profiling

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `scripts/profile_databases.py` | online source mode |
| update | `docs/context/statistical_info.md` | online counts and fixed sample advice |

## Implementation points

- Profile both online DBs without ingesting.
- Report freshness and local mirror staleness.
- Recommend a fixed sample size with a reason.

## Done when

- Online counts and coverage are reported.
- A fixed sample size is recommended with a reason.
- Local mirror staleness is stated.
