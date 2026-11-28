# n-flow tables
<!-- Last updated: 2026-11-28 | Edit count: 2 -->

- **Status:** todo (unblocked — reconcile directly from frozen `phase1_transformed_transform_20261127T224625Z__wallet_features.parquet` via DuckDB)
- **Blocked by:** —
- **Blocks:** Steps 4–8
- **Owner:** subagent
- **Output:** n-flow table
- **Updated:** 2026-11-28

## Objective

For each response, report the number of wallets by group before and after each eligibility filter.

## Resources / context

- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `docs/context/cohort_contract.md`
- `src/notebooks/1.1_ILLICIT_EDA.ipynb` — current EDA and executed outputs

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/etl/transform/nflow.csv` | group × filter counts |
| update | `src/notebooks/1.1_ILLICIT_EDA.ipynb` | n-flow table display |

## Implementation points

- One row per response and filter.
- Counted in the transform SQL that owns the cleaning rule, not by a notebook-side recount.
- Report group denominators.
- Explain every drop.

## Done when

- Every denominator is explicit.
- Differences are explained.
