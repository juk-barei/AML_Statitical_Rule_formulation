# Test decision rule

- **Status:** todo
- **Blocked by:** —
- **Blocks:** Step 5
- **Owner:** subagent
- **Output:** decision rule
- **Updated:** 2026-11-20

## Objective

Pre-specify: Welch primary, KW sensitivity, seed-cluster permutation for dependence, classic ANOVA only as reference.

## Resources / context

- `AGENTS.md` — data authority, cohort priority, task rules
- `docs/context/assumptions.md`
- `docs/context/test_plan.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/test_plan.md` | decision rule |

## Implementation points

- Welch primary.
- KW sensitivity.
- Seed-cluster permutation if dependence is material.
- No switching after p-values.

## Done when

- Rule is written before results.
- No post-hoc test switching.
