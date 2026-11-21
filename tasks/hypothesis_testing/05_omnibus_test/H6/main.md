# H6 — Interval consistency

- **Status:** todo
- **Blocked by:** shared tasks in `../main.md`
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/test_plan.md
- **Updated:** 2026-11-20

## Objective

Apply Step 5 (omnibus test and sensitivity) to H6: `log1p(cv_delta_t)` secondary. Rule: N ≥ 5 and CV < 0.15.

## Resources / context

- `docs/hypothesis.md` — H6 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/test_plan.md` | H6 omnibus record |
| create | `outputs/tests/H6/` | omnibus and sensitivity results |

## Implementation points

- Welch/KW as secondary.
- 0 illicit passes is a support failure, not a mean test.
- Report the inversion.
