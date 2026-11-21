# Step 1 — Response, factor, groups

- **Status:** in_progress
- **Blocked by:** —
- **Blocks:** [Step 2](../02_hypotheses_alpha/main.md)
- **Updated:** 2026-11-20

## Objective

Fix the experimental unit, response, factor, levels, group rules, and nesting before any test. Validate whether the three-group design is supported by the illicit and licit data.

## Resources / context

- `AGENTS.md` — data authority, cohort priority, task rules
- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `docs/context/statistical_info.md` — proposed groups and profiling
- `docs/hypothesis.md` — H2/H4/H6 definitions and thresholds
- `src/scripts/ETL.py` — ingestion, loader, and source-link behavior

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/step_1_profiling_samples.md` | step-1 design and evidence |
| update | `tasks/01_response_factor_groups/main.md` | step status and task table |

## Implementation points

- Freeze unit, response, factor, levels, and nesting.
- Do not call uncleaned licit a control.
- Keep every step-1 subtask linked in the table.

## Hypothesis folders

| Hypothesis | Folder | Status | Focus |
| --- | --- | --- | --- |
| H1 | `H1/main.md` | blocked | deferred; not in phase-1 scope |
| H2 | `H2/main.md` | in_progress | lifetime + burst |
| H3 | `H3/main.md` | blocked | deferred; not in phase-1 scope |
| H4 | `H4/main.md` | blocked | Jaccard + coverage |
| H5 | `H5/main.md` | blocked | deferred; not in phase-1 scope |
| H6 | `H6/main.md` | in_progress | CV + direction |

## Shared tasks

| File | Status | Blocked by | Output |
| --- | --- | --- | --- |
| `01_profile_illicit_licit.md` | done | — | `docs/context/statistical_info.md` |
| `02_group_validation.md` | done | `01_profile_illicit_licit.md` | group verdict |
| `03_reproducible_evidence.md` | done | `01_profile_illicit_licit.md` | `scripts/` + cited lines |
| `04_cohort_contract_v2.md` | in_progress | `02_group_validation.md` | cohort table |
| `05_licit_ingestion_etl.md` | blocked | local PostgreSQL down | licit tables |
| `06_online_db_refresh_profile.md` | done | — | fixed sample recommendation |
| `07_incremental_ingestion_check.md` | done | `06_online_db_refresh_profile.md` | ETL safety note |
| `08_sampling_evaluation.md` | done | `06_online_db_refresh_profile.md` | sampling note |
| `09_feature_definition_audit.md` | done | — | feature fix list |
| `10_step1_docs_sync.md` | done | — | corrected docs |
| `11_licit_eda_notebook.md` | blocked | `05_licit_ingestion_etl.md` | `1.2_LICIT_EDA.ipynb` |
| `12_agents_contract.md` | done | — | `AGENTS.md`, README, rename |
