# Cliff’s delta

- **Status:** blocked
- **Blocked by:** Step 6
- **Blocks:** Step 8
- **Owner:** subagent
- **Output:** pairwise effects
- **Updated:** 2026-11-20

## Objective

Compute Cliff’s delta for each pair; use it as the distribution-free effect size.

## Resources / context

- `outputs/hypothesis_testing/shared/posthoc.csv`
- Cliff’s delta reference

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/hypothesis_testing/shared/cliffs_delta.csv` | pairwise delta |

## Implementation points

- Distribution-free effect size.
- Report direction and magnitude.
- Handle ties explicitly.

## Done when

- Direction and magnitude are reported.
- Ties are handled.
