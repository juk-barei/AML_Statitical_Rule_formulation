# H4 — TRX gas co-occurrence

- **Status:** blocked
- **Blocked by:** data support
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/final_report.md
- **Updated:** 2026-11-20

## Objective

Apply Step 8 (rule-level verdict and limitations) to H4: `jaccard_index` descriptive. Rule: Jaccard ≥ 0.50, only when both sets are non-empty.

## Resources / context

- `docs/hypothesis.md` — H4 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/final_report.md` | H4 verdict |
| create | `outputs/report/H4_verdict.md` | rule verdict and limits |

## Implementation points

- Verdict: not supported as written.
- 13 illicit passes; rule is inverted.
- Recommend redesign, not deletion.
