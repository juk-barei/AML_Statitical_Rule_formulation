# H2 — Temporal burstiness

- **Status:** todo
- **Blocked by:** shared tasks in `../main.md`
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/assumptions.md
- **Updated:** 2026-11-20

## Objective

Apply Step 4 (independence, normality, variance, and transform) to H2: `log1p(tx_lifetime_days)` primary; `burst_ratio` descriptive. Rule: lifetime ≤ 7 days and burst ratio ≥ 0.75.

## Resources / context

- `docs/hypothesis.md` — H2 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/assumptions.md` | H2 diagnostics |
| create | `outputs/diagnostics/H2/` | Q–Q, Levene, transform checks |

## Implementation points

- Q–Q and Levene on log lifetime.
- Check seed clustering; do not use i.i.d. SE.
- Record log1p before testing.
