# Step 2 — H0, Ha, alpha

- **Status:** in_progress
- **Blocked by:** licit cleaning (H0_L)
- **Blocks:** [Step 3](../03_explore/main.md)
- **Updated:** 2026-11-20

## Objective

Write the null and alternative hypotheses, the alpha level, and the multiplicity policy for each response before looking at test results.

## Resources / context

- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `docs/hypothesis.md` — H2/H4/H6 definitions and thresholds
- `docs/flow.md` — test and weight plan
- NIST/SEMATECH one-way ANOVA

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `docs/context/test_plan.md` | H0/Ha, alpha, and test path |
| update | `tasks/02_hypotheses_alpha/main.md` | step status |

## Implementation points

- Write hypotheses before looking at results.
- Fix alpha and multiplicity.
- Name the licit/unlabeled substitution.

## Hypothesis folders

| Hypothesis | Folder | Status | Focus |
| --- | --- | --- | --- |
| H1 | `H1/main.md` | blocked | deferred; not in phase-1 scope |
| H2 | `H2/main.md` | in_progress | lifetime + burst |
| H3 | `H3/main.md` | blocked | deferred; not in phase-1 scope |
| H4 | `H4/main.md` | blocked | Jaccard + coverage |
| H5 | `H5/main.md` | blocked | deferred; not in phase-1 scope |
| H6 | `H6/main.md` | in_progress | CV + direction |

## Shared tasks

| File | Status | Blocked by | Output |
| --- | --- | --- | --- |
| `01_primary_hypotheses.md` | done | Step 1 cohort + response | H0/Ha text |
| `02_secondary_hypotheses.md` | done | `01_primary_hypotheses.md` | H0/Ha text |
| `03_alpha_multiplicity.md` | done | — | alpha/Holm policy |
| `04_licit_substitution_policy.md` | done | — | naming rule |
| `05_licit_hypotheses.md` | blocked | licit cleaning | H0_L/Ha_L |
