# H6 — Interval consistency

- **Status:** todo
- **Blocked by:** shared tasks in `../main.md`
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/assumptions.md
- **Updated:** 2026-11-20

## Objective

Apply Step 4 (independence, normality, variance, and transform) to H6: `log1p(cv_delta_t)` secondary. Rule: N ≥ 5 and CV < 0.15.

## Resources / context

- `docs/hypothesis.md` — H6 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/assumptions.md` | H6 diagnostics |
| create | `outputs/diagnostics/H6/` | Q–Q, Levene, transform checks |

## Implementation points

- Q–Q and Levene on log CV.
- Expect heteroscedasticity.
- Use seed-cluster inference.
