# H2 — Temporal burstiness

- **Status:** in_progress
- **Blocked by:** shared tasks in `../main.md`
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/final_report.md
- **Updated:** 2026-11-20

## Objective

Apply Step 8 (rule-level verdict and limitations) to H2: `log1p(tx_lifetime_days)` primary; `burst_ratio` descriptive. Rule: lifetime ≤ 7 days and burst ratio ≥ 0.75.

## Resources / context

- `docs/hypothesis.md` — H2 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/final_report.md` | H2 verdict |
| create | `outputs/report/H2_verdict.md` | rule verdict and limits |

## Implementation points

- Verdict: supported / not / inconclusive.
- Separate mean difference from threshold support.
- Name the licit substitution.
