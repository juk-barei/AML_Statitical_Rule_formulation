# n-flow tables

- **Status:** todo
- **Blocked by:** Step 1 cohort
- **Blocks:** Steps 4–8
- **Owner:** subagent
- **Output:** n-flow table
- **Updated:** 2026-11-20

## Objective

For each response, report the number of wallets by group before and after each eligibility filter.

## Resources / context

- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `docs/context/cohort_contract.md`
- `src/notebooks/1.1_ILLICIT_EDA.ipynb` — current EDA and executed outputs

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/analysis/nflow.csv` | group × filter counts |
| update | `src/notebooks/1.1_ILLICIT_EDA.ipynb` | n-flow table display |

## Implementation points

- One row per response and filter.
- Report group denominators.
- Explain every drop.

## Done when

- Every denominator is explicit.
- Differences are explained.
