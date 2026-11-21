# Licit substitution policy

- **Status:** done
- **Blocked by:** —
- **Blocks:** Step 8
- **Owner:** subagent
- **Output:** naming rule
- **Updated:** 2026-11-20

## Objective

State how results are labelled while licit is pending: use `unlabeled` as the third level, never call it licit, and name the substitution in every conclusion.

## Resources / context

- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `docs/context/current_progress_and_gaps.md`
- `AGENTS.md` — data authority, cohort priority, task rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/test_plan.md` | naming rule |
| update | `docs/context/step_1_profiling_samples.md` | licit-pending wording |

## Implementation points

- Use `unlabeled` while licit is pending.
- Never call the complement licit.
- Name the substitution in every conclusion.

## Done when

- Rule is written.
- Report template reflects it.
