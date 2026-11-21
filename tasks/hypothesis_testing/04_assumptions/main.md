# Step 4 — Assumptions

- **Status:** todo
- **Blocked by:** [Step 3](../03_explore/main.md)
- **Blocks:** [Step 5](../05_omnibus_test/main.md)
- **Updated:** 2026-11-20

## Objective

Check independence, residual normality, equal variance, and missingness. Decide the transform and the test path before running the omnibus test.

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

## Hypothesis folders

| Hypothesis | Folder | Status | Focus |
| --- | --- | --- | --- |
| H1 | `H1/main.md` | blocked | deferred; not in phase-1 scope |
| H2 | `H2/main.md` | todo | lifetime + burst |
| H3 | `H3/main.md` | blocked | deferred; not in phase-1 scope |
| H4 | `H4/main.md` | blocked | Jaccard + coverage |
| H5 | `H5/main.md` | blocked | deferred; not in phase-1 scope |
| H6 | `H6/main.md` | todo | CV + direction |

## Shared tasks

| File | Status | Blocked by | Output |
| --- | --- | --- | --- |
| `01_independence_seed_cluster.md` | blocked | Step 1 cohort | dependence verdict |
| `02_normality_qq_shapiro.md` | blocked | Step 1 response | Q–Q/Shapiro results |
| `03_equal_variance_levene.md` | blocked | Step 1 response | Levene results |
| `04_transform_decision.md` | blocked | `02`, `03` | log1p decision |
| `05_missingness_eligibility.md` | todo | Step 3 n-flow | missingness note |
