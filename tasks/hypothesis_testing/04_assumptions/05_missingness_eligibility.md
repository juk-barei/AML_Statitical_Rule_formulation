# Missingness and eligibility

- **Status:** todo
- **Blocked by:** Step 3 n-flow
- **Blocks:** Step 8
- **Owner:** subagent
- **Output:** missingness note
- **Updated:** 2026-11-20

## Objective

Quantify missing responses and eligibility filters by group. State whether missingness is informative.

## Resources / context

- `outputs/etl/transform/nflow.csv`
- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `src/notebooks/1.1_ILLICIT_EDA.ipynb` — current EDA and executed outputs

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/etl/transform/missingness.csv` | missingness by group/filter |
| update | `docs/context/assumptions.md` | missingness note |

## Implementation points

- Quantify missing responses by group.
- Computed in SQL over the frozen cohort and written by the ETL transform path, not by a notebook edit.
- State whether missingness is informative.
- Feed selection risk into Step 8.

## Done when

- Missingness table is complete.
- Selection risk is stated.
