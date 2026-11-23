# Dunn post-hoc

- **Status:** blocked
- **Blocked by:** Step 5 KW
- **Blocks:** Step 7
- **Owner:** subagent
- **Output:** pairwise table
- **Updated:** 2026-11-20

## Objective

Run Dunn’s test after Kruskal–Wallis with Holm adjustment.

## Resources / context

- `outputs/hypothesis_testing/shared/kruskal.csv`
- Dunn method reference
- `docs/non-parametric_introduction.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/hypothesis_testing/shared/dunn.csv` | pairwise rank results |

## Implementation points

- Run after a significant KW.
- Holm adjustment.
- Report adjusted p and direction.

## Done when

- Adjusted p reported.
- Rank interpretation is clear.
