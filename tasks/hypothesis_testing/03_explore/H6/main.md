# H6 — Interval consistency

- **Status:** todo
- **Blocked by:** shared tasks in `../main.md`
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** src/notebooks/1.1_ILLICIT_EDA.ipynb
- **Updated:** 2026-11-20

## Objective

Apply Step 3 (distribution, centre, spread, and n-flow) to H6: `log1p(cv_delta_t)` secondary. Rule: N ≥ 5 and CV < 0.15.

## Resources / context

- `docs/hypothesis.md` — H6 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/notebooks/1.1_ILLICIT_EDA.ipynb` | H6 exploration cells |
| create | `outputs/EDA_ILLICIT/H6/` | figures and tables |

## Implementation points

- CV distribution by group and hop band.
- Show N ≥ 5 eligibility.
- Flag the inverted direction.
