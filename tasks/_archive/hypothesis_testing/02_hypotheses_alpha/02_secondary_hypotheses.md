# Secondary hypotheses

- **Status:** done
- **Blocked by:** `01_primary_hypotheses.md`
- **Blocks:** Step 3
- **Owner:** subagent
- **Output:** H0/H1 in `docs/context/`
- **Updated:** 2026-11-20

## Objective

Write H0/H1 for `log1p(cv_delta_t)` and state that H4/H2 descriptive features are not primary tests.

## Resources / context

- `docs/context/step_1_profiling_samples.md`
- `docs/hypothesis.md` — H2/H4/H6 definitions and thresholds
- `docs/flow.md` — test and weight plan

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/test_plan.md` | secondary H0/H1 |

## Implementation points

- H0/H1 for `log1p(cv_delta_t)`.
- Mark H4/H2 descriptive features as non-primary.
- Do not add hypotheses after results.

## Done when

- Secondary status is explicit.
- No hypothesis is added after seeing results.
