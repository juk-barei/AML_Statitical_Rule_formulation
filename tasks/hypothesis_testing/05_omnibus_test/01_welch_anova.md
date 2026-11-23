# Welch ANOVA

- **Status:** blocked
- **Blocked by:** Step 4
- **Blocks:** Step 6
- **Owner:** subagent
- **Output:** Welch result
- **Updated:** 2026-11-20

## Objective

Run Welch ANOVA on `log1p(tx_lifetime_days)` across the three groups; report F, df, p, and n per group.

## Resources / context

- `docs/context/test_plan.md`
- SciPy `f_oneway(equal_var=False)`
- statsmodels

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/hypothesis_testing/shared/welch.csv` | F, df, p, n |
| update | `src/notebooks/1.1_ILLICIT_EDA.ipynb` | result display |

## Implementation points

- Response = `log1p(tx_lifetime_days)`.
- Report F, both df, exact p, n per group.
- Name the third level actually used.

## Done when

- Both df are reported.
- Exact p is reported.
- Group substitution is named.
