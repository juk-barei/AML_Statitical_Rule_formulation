# Eta-squared and omega-squared

- **Status:** blocked
- **Blocked by:** Step 5
- **Blocks:** Step 8
- **Owner:** subagent
- **Output:** effect-size table
- **Updated:** 2026-11-20

## Objective

Compute eta-squared and omega-squared for the omnibus model, with interpretation bands.

## Resources / context

- `outputs/tests/welch.csv`
- statsmodels ANOVA
- NIST/SEMATECH

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/effects/eta_omega.csv` | eta/omega values |

## Implementation points

- Compute from the omnibus sums of squares.
- Report formula and denominator.
- Interpret with bands, not labels alone.

## Done when

- Formula and denominator are stated.
- Value is interpreted.
- Small/medium/large labels are not overclaimed.
