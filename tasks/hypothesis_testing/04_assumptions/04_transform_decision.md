# Transform decision

- **Status:** blocked
- **Blocked by:** `02`, `03`
- **Blocks:** Step 5
- **Owner:** subagent
- **Output:** transform decision
- **Updated:** 2026-11-20

## Objective

Choose `log1p` for lifetime and CV, or a rank-based path. Record the decision before testing.

## Resources / context

- `outputs/diagnostics/normality.csv`
- `outputs/diagnostics/levene.csv`
- `docs/context/step_1_profiling_samples.md` — cohort/response decisions

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/assumptions.md` | transform decision |
| update | `docs/context/test_plan.md` | pre-specified scale |

## Implementation points

- Choose `log1p` or rank-based path.
- Document back-interpretation.
- Do not change after seeing test p-values.

## Done when

- Transform is stated.
- Back-interpretation is documented.
