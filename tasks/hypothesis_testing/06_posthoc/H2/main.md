# H2 — Temporal burstiness

- **Status:** todo
- **Blocked by:** shared tasks in `../main.md`
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/test_plan.md
- **Updated:** 2026-11-20

## Objective

Apply Step 6 (pairwise comparisons and family-wise error) to H2: `log1p(tx_lifetime_days)` primary; `burst_ratio` descriptive. Rule: lifetime ≤ 7 days and burst ratio ≥ 0.75.

## Resources / context

- `docs/hypothesis.md` — H2 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/test_plan.md` | H2 post-hoc record |
| create | `outputs/tests/H2/posthoc.csv` | pairwise comparisons |

## Implementation points

- Games–Howell or Dunn by test path.
- Report pairwise CIs and adjusted p.
- All pairs, not only significant ones.
