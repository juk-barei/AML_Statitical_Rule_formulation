# Games–Howell post-hoc

- **Status:** blocked
- **Blocked by:** Step 5 Welch
- **Blocks:** Step 7
- **Owner:** subagent
- **Output:** pairwise table
- **Updated:** 2026-11-20

## Objective

Run Games–Howell for unequal variances. Report each pair’s difference, CI, and adjusted p.

## Resources / context

- `outputs/tests/welch.csv`
- Games–Howell method reference
- statsmodels

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/tests/games_howell.csv` | pairwise differences and CIs |

## Implementation points

- Unequal-variance pairwise test.
- Report difference, CI, adjusted p.
- All pairs, not only significant ones.

## Done when

- All pairs are reported.
- CIs exclude zero or not.
- Family-wise control is stated.
