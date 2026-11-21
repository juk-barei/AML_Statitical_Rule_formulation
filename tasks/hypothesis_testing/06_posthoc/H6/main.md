# H6 — Interval consistency

- **Status:** todo
- **Blocked by:** shared tasks in `../main.md`
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/test_plan.md
- **Updated:** 2026-11-20

## Objective

Apply Step 6 (pairwise comparisons and family-wise error) to H6: `log1p(cv_delta_t)` secondary. Rule: N ≥ 5 and CV < 0.15.

## Resources / context

- `docs/hypothesis.md` — H6 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/test_plan.md` | H6 post-hoc record |
| create | `outputs/tests/H6/posthoc.csv` | pairwise comparisons |

## Implementation points

- Post-hoc only if the omnibus supports a difference.
- Otherwise stop and report no support.
- Name the direction.
