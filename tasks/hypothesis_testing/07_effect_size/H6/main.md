# H6 — Interval consistency

- **Status:** todo
- **Blocked by:** shared tasks in `../main.md`
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/reporting_template.md
- **Updated:** 2026-11-20

## Objective

Apply Step 7 (effect magnitude and confidence intervals) to H6: `log1p(cv_delta_t)` secondary. Rule: N ≥ 5 and CV < 0.15.

## Resources / context

- `docs/hypothesis.md` — H6 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/reporting_template.md` | H6 effect-size sentence |
| create | `outputs/effects/H6/` | effect sizes and CIs |

## Implementation points

- Effect size only if support exists.
- Otherwise report the support failure.
- Use seed-level CI.
