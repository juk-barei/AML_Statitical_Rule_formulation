# H4 — TRX gas co-occurrence

- **Status:** blocked
- **Blocked by:** data support
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/assumptions.md
- **Updated:** 2026-11-20

## Objective

Apply Step 4 (independence, normality, variance, and transform) to H4: `jaccard_index` descriptive. Rule: Jaccard ≥ 0.50, only when both sets are non-empty.

## Resources / context

- `docs/hypothesis.md` — H4 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/assumptions.md` | H4 diagnostics |
| create | `outputs/diagnostics/H4/` | Q–Q, Levene, transform checks |

## Implementation points

- Do not run a mean test while zeros dominate.
- Report support instead.
- Revisit only after redesign.
