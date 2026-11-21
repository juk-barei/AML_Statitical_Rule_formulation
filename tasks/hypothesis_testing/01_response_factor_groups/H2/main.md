# H2 — Temporal burstiness

- **Status:** in_progress
- **Blocked by:** shared tasks in `../main.md`
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/hypotheses/H2.md
- **Updated:** 2026-11-20

## Objective

Apply Step 1 (response, eligibility, feature formula, and support) to H2: `log1p(tx_lifetime_days)` primary; `burst_ratio` descriptive. Rule: lifetime ≤ 7 days and burst ratio ≥ 0.75.

## Resources / context

- `docs/hypothesis.md` — H2 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/hypotheses/H2.md` | response, eligibility, and support note |
| create | `outputs/profiling/H2_support.csv` | eligibility/support counts |

## Implementation points

- Response = `log1p(tx_lifetime_days)`; burst is descriptive.
- Gate on ≥2 events; report n-flow.
- Check whether the 7-day premise is inverted.
