# H6 — Interval consistency

- **Status:** in_progress
- **Blocked by:** shared tasks in `../main.md`
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/final_report.md
- **Updated:** 2026-11-20

## Objective

Apply Step 8 (rule-level verdict and limitations) to H6: `log1p(cv_delta_t)` secondary. Rule: N ≥ 5 and CV < 0.15.

## Resources / context

- `docs/hypothesis.md` — H6 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/final_report.md` | H6 verdict |
| create | `outputs/report/H6_verdict.md` | rule verdict and limits |

## Implementation points

- Verdict: not supported as written.
- CV is highest in illicit, not lowest.
- Report the opposite direction.
