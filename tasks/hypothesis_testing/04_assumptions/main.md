# Step 4 — Assumptions

- **Status:** todo
- **Blocked by:** [Step 3](../03_explore/main.md)
- **Blocks:** [Step 5](../05_omnibus_test/main.md)
- **Updated:** 2026-11-22

## Objective

Check independence, residual normality, equal variance, and missingness. Decide the transform and the test path before running the omnibus test.

**Test path:** this step opens the parametric/non-parametric branch; the fork is `04_transform_decision.md`. Branch map: [`../test_paths.md`](../test_paths.md).

## Resources / context

- `docs/hypothesis_testing_flow.md` — assumption flow
- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- NIST/SEMATECH ANOVA assumptions
- SciPy diagnostics docs

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `docs/context/assumptions.md` | diagnostics and decisions |
| update | `docs/context/test_plan.md` | test path |

## Implementation points

- Check independence first.
- Then normality and equal variance.
- Record transform before testing.

## Hypothesis trackers

| Hypothesis | Tracker | Status | Focus |
| --- | --- | --- | --- |
| H2 | [`H2.md`](../H2.md) | todo | lifetime + burst |
| H4 | [`H4.md`](../H4.md) | blocked | Jaccard + coverage |
| H6 | [`H6.md`](../H6.md) | todo | CV + direction |

`H1`, `H3`, `H5` are deferred and have no tracker; see [`../DEFERRED.md`](../DEFERRED.md).

## Shared tasks

| File | Status | Blocked by | Output |
| --- | --- | --- | --- |
| `01_independence_seed_cluster.md` | blocked | Step 1 cohort | dependence verdict |
| `02_normality_qq_shapiro.md` | blocked | Step 1 response | Q–Q/Shapiro results |
| `03_equal_variance_levene.md` | blocked | Step 1 response | Levene results |
| `04_transform_decision.md` | blocked | `02`, `03` | log1p decision |
| `05_missingness_eligibility.md` | todo | Step 3 n-flow | missingness note |

Branch map: [`../test_paths.md`](../test_paths.md).
