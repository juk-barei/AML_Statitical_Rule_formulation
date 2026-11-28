# Step 2 — H0, Ha, alpha
<!-- Last updated: 2026-11-28 | Edit count: 2 -->

- **Status:** in_progress (unblocked on clean licit frame `phase1_transformed_transform_20261127T224625Z`)
- **Blocked by:** —
- **Blocks:** [Step 3](../03_explore/main.md)
- **Updated:** 2026-11-28

## Objective

Write the null and alternative hypotheses, the alpha level, and the multiplicity policy for each response before looking at test results.

## Resources / context

- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `docs/dev/hypothesis_testing/general/all_hypothesis.md` — H1–H6 definitions and thresholds
- `docs/dev/hypothesis_testing/overall_flow.md` — test and weight plan
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

## Hypothesis trackers

| Hypothesis | Tracker | Status | Focus |
| --- | --- | --- | --- |
| H2 | [`H2.md`](../H2.md) | in_progress | lifetime + burst |
| H4 | [`H4.md`](../H4.md) | blocked | Jaccard + coverage |
| H6 | [`H6.md`](../H6.md) | in_progress | CV + direction |

`H1`, `H3`, `H5` are deferred and have no tracker; see [`../DEFERRED.md`](../DEFERRED.md).

## Shared tasks

Done tasks are archived under `tasks/_archive/`; their links point there.

| File | Status | Blocked by | Output |
| --- | --- | --- | --- |
| [`01_primary_hypotheses.md`](../../_archive/hypothesis_testing/02_hypotheses_alpha/01_primary_hypotheses.md) | done | Step 1 cohort + response | H0/Ha text |
| [`02_secondary_hypotheses.md`](../../_archive/hypothesis_testing/02_hypotheses_alpha/02_secondary_hypotheses.md) | done | `01_primary_hypotheses.md` | H0/Ha text |
| [`03_alpha_multiplicity.md`](../../_archive/hypothesis_testing/02_hypotheses_alpha/03_alpha_multiplicity.md) | done | — | alpha/Holm policy |
| [`04_licit_substitution_policy.md`](../../_archive/hypothesis_testing/02_hypotheses_alpha/04_licit_substitution_policy.md) | done | — | naming rule |
| `05_licit_hypotheses.md` | todo | — | `H0_L`/`Ha_L` sign-off in `docs/context/test_plan.md` |
