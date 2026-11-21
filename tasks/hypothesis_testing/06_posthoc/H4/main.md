# H4 — TRX gas co-occurrence

- **Status:** blocked
- **Blocked by:** data support
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/test_plan.md
- **Updated:** 2026-11-20

## Objective

Apply Step 6 (pairwise comparisons and family-wise error) to H4: `jaccard_index` descriptive. Rule: Jaccard ≥ 0.50, only when both sets are non-empty.

## Resources / context

- `docs/hypothesis.md` — H4 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/test_plan.md` | H4 post-hoc record |
| create | `outputs/tests/H4/posthoc.csv` | pairwise comparisons |

## Implementation points

- No post-hoc while support fails.
- Report pass-rate difference with CI.
- Keep it descriptive.
