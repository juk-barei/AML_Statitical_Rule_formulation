# H2 — Temporal burstiness

- **Status:** todo
- **Blocked by:** shared tasks in `../main.md`
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** src/notebooks/1.1_ILLICIT_EDA.ipynb
- **Updated:** 2026-11-20

## Objective

Apply Step 3 (distribution, centre, spread, and n-flow) to H2: `log1p(tx_lifetime_days)` primary; `burst_ratio` descriptive. Rule: lifetime ≤ 7 days and burst ratio ≥ 0.75.

## Resources / context

- `docs/hypothesis.md` — H2 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/notebooks/1.1_ILLICIT_EDA.ipynb` | H2 exploration cells |
| create | `outputs/EDA_ILLICIT/H2/` | figures and tables |

## Implementation points

- Lifetime and burst distributions by group.
- Show mean/median and 7-day/75% lines.
- Report n and zeros.
