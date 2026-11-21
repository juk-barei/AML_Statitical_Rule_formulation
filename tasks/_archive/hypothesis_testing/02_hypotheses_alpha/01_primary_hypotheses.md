# Primary hypotheses

- **Status:** done
- **Blocked by:** Step 1 cohort + response
- **Blocks:** `02_secondary_hypotheses.md`, Step 3
- **Owner:** subagent
- **Output:** H0/Ha in `docs/context/`
- **Updated:** 2026-11-20

## Objective

Write H0/Ha for `log1p(tx_lifetime_days)`: all group means equal vs at least one differs. Name the three levels explicitly.

## Resources / context

- `docs/context/step_1_profiling_samples.md`
- `docs/flow.md` — test and weight plan
- NIST/SEMATECH

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/test_plan.md` | primary H0/Ha |

## Implementation points

- H0: all three group means equal for `log1p(tx_lifetime_days)`.
- Ha: at least one mean differs.
- Two-sided; alpha 0.05.

## Done when

- H0/Ha are unambiguous.
- Levels match the cohort contract.
- Alpha is stated.
