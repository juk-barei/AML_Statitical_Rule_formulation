# Pairwise effects and CIs

- **Status:** blocked
- **Blocked by:** Step 5
- **Blocks:** Step 7
- **Owner:** subagent
- **Output:** effect + CI table
- **Updated:** 2026-11-20

## Objective

Compute Cliff’s delta or rank-biserial correlation and bootstrap CIs for each pair.

## Resources / context

- `outputs/hypothesis_testing/shared/posthoc.csv`
- Cliff’s delta reference
- bootstrap docs

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/hypothesis_testing/shared/pairwise_effects.csv` | effect sizes and CIs |

## Implementation points

- Cliff’s delta or rank-biserial.
- Bootstrap CIs over seeds.
- Report direction and magnitude.

## Done when

- Effect direction is stated.
- CI is reported.
- Seed clustering is respected.
