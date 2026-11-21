# H6 — Interval consistency

- **Status:** in_progress
- **Blocked by:** shared tasks in `../main.md`
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/hypotheses/H6.md
- **Updated:** 2026-11-20

## Objective

Apply Step 1 (response, eligibility, feature formula, and support) to H6: `log1p(cv_delta_t)` secondary. Rule: N ≥ 5 and CV < 0.15.

## Resources / context

- `docs/hypothesis.md` — H6 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/hypotheses/H6.md` | response, eligibility, and support note |
| create | `outputs/profiling/H6_support.csv` | eligibility/support counts |

## Implementation points

- CV is secondary; 0 illicit passes.
- Check the opposite-direction signal.
- Gate on N ≥ 5 events.
