# H4 — TRX gas co-occurrence

- **Status:** blocked
- **Blocked by:** data support
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/reporting_template.md
- **Updated:** 2026-11-20

## Objective

Apply Step 7 (effect magnitude and confidence intervals) to H4: `jaccard_index` descriptive. Rule: Jaccard ≥ 0.50, only when both sets are non-empty.

## Resources / context

- `docs/hypothesis.md` — H4 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/reporting_template.md` | H4 effect-size sentence |
| create | `outputs/effects/H4/` | effect sizes and CIs |

## Implementation points

- Report support proportions, not effect size.
- If redesigned, use Cliff’s delta.
- Do not overclaim.
