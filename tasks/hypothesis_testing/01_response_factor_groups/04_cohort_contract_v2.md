# Cohort contract v2

- **Status:** in_progress
- **Blocked by:** `02_group_validation.md`
- **Blocks:** `05_licit_ingestion_etl.md`, Steps 2–8
- **Owner:** subagent
- **Output:** authoritative cohort table
- **Updated:** 2026-11-20

## Objective

Define `illicit = blacklist ∪ hop-0`, `suspicious = min(hop) 1–5 minus blacklist`, `licit = external DB`, `unlabeled = rest`. Any blacklist record at hop 1–5 is illicit.

## Resources / context

- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `docs/context/statistical_info.md`
- `src/notebooks/1.1_ILLICIT_EDA.ipynb` — current EDA and executed outputs
- `AGENTS.md` — data authority, cohort priority, task rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `docs/context/cohort_contract.md` | authoritative group rules |
| create | `outputs/etl/transform/cohort_wallet.parquet` | one row per wallet |
| update | `docs/context/step_1_profiling_samples.md` | link the contract |

## Implementation points

- `illicit = blacklist ∪ hop-0`; `suspicious = min(hop) 1–5 minus blacklist`.
- Any blacklist record at hop 1–5 is illicit.
- `cohort_wallet.parquet` is written by the ETL transform path, never by a notebook.
- Publish n-flow by group and eligibility.

## Done when

- One row per wallet.
- Priority and overlap rules are explicit.
- n-flow table by group.
