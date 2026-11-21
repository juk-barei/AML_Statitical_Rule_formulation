# H2 — Temporal burstiness

- **Status:** todo
- **Blocked by:** shared tasks in `../main.md`
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/reporting_template.md
- **Updated:** 2026-11-20

## Objective

Apply Step 7 (effect magnitude and confidence intervals) to H2: `log1p(tx_lifetime_days)` primary; `burst_ratio` descriptive. Rule: lifetime ≤ 7 days and burst ratio ≥ 0.75.

## Resources / context

- `docs/hypothesis.md` — H2 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/reporting_template.md` | H2 effect-size sentence |
| create | `outputs/effects/H2/` | effect sizes and CIs |

## Implementation points

- Eta/omega squared, Cliff’s delta, bootstrap CI.
- Bootstrap over seeds.
- Interpret magnitude in context.
