# Sync step-1 documents

- **Status:** done
- **Blocked by:** —
- **Blocks:** Step 2
- **Owner:** subagent
- **Output:** corrected `docs/context/`
- **Updated:** 2026-11-20

## Objective

Apply the accepted corrections: licit is pending, unlabeled is not licit, all-hop blacklist priority, non-parametric tests do not fix dependence.

## Resources / context

- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `docs/context/current_progress_and_gaps.md`
- `docs/context/01_concepts_and_answer_structure.md`
- `AGENTS.md` — data authority, cohort priority, task rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/step_1_profiling_samples.md` | licit-pending and priority corrections |
| update | `docs/context/current_progress_and_gaps.md` | step statuses |
| update | `docs/context/01_concepts_and_answer_structure.md` | concept mapping |

## Implementation points

- Say licit is pending, not absent.
- Say every hop 1–5 blacklist record is illicit.
- Keep summary docs under 200 words.

## Done when

- No stale "licit absent" claim.
- Priority rule says every hop 1–5.
- Dependence caveat is explicit.
