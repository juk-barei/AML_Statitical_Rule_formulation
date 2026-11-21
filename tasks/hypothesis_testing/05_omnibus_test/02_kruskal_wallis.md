# Kruskal–Wallis sensitivity

- **Status:** blocked
- **Blocked by:** Step 4
- **Blocks:** Step 6
- **Owner:** subagent
- **Output:** KW result
- **Updated:** 2026-11-20

## Objective

Run Kruskal–Wallis on the untransformed or ranked response as a sensitivity analysis. State that it still assumes independence.

## Resources / context

- `docs/non-parametric_introduction.md`
- SciPy `kruskal`
- `docs/context/test_plan.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/tests/kruskal.csv` | H, df, p |
| update | `docs/context/test_plan.md` | sensitivity result |

## Implementation points

- Run on untransformed or ranked response.
- Report H, df, p.
- State independence caveat.

## Done when

- H, df, p reported.
- Independence caveat stated.
