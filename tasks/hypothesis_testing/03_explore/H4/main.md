# H4 — TRX gas co-occurrence

- **Status:** blocked
- **Blocked by:** data support
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** src/notebooks/1.1_ILLICIT_EDA.ipynb
- **Updated:** 2026-11-20

## Objective

Apply Step 3 (distribution, centre, spread, and n-flow) to H4: `jaccard_index` descriptive. Rule: Jaccard ≥ 0.50, only when both sets are non-empty.

## Resources / context

- `docs/hypothesis.md` — H4 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/notebooks/1.1_ILLICIT_EDA.ipynb` | H4 exploration cells |
| create | `outputs/EDA_ILLICIT/H4/` | figures and tables |

## Implementation points

- Jaccard distribution and zero mass.
- Use both-set denominator.
- Do not infer from the pooled rate.
