# Step 5 — F-test, Welch, or Kruskal–Wallis

- **Status:** todo
- **Blocked by:** [Step 4](../04_assumptions/main.md)
- **Blocks:** [Step 6](../06_posthoc/main.md), [Step 7](../07_effect_size/main.md)
- **Updated:** 2026-11-20

## Objective

Run the pre-specified omnibus test for the primary response, plus sensitivity tests. Do not choose the test after seeing p-values.

## Resources / context

- `docs/context/test_plan.md`
- `docs/context/assumptions.md`
- SciPy `f_oneway`/`kruskal` docs
- statsmodels `anova_lm`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/tests/omnibus.csv` | omnibus results |
| update | `docs/context/test_plan.md` | executed test record |

## Implementation points

- Welch primary; KW sensitivity.
- Seed-cluster permutation for dependence.
- Classic ANOVA reference only.

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
| `01_welch_anova.md` | blocked | Step 4 | Welch result |
| `02_kruskal_wallis.md` | blocked | Step 4 | KW result |
| `03_cluster_permutation.md` | blocked | Step 4 independence verdict | permutation result |
| `04_test_decision_rule.md` | todo | — | decision rule |
