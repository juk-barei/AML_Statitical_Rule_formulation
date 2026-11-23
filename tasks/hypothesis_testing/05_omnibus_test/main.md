# Step 5 — F-test, Welch, or Kruskal–Wallis

- **Status:** todo
- **Blocked by:** [Step 4](../04_assumptions/main.md)
- **Blocks:** [Step 6](../06_posthoc/main.md), [Step 7](../07_effect_size/main.md)
- **Updated:** 2026-11-22

## Objective

Run the pre-specified omnibus test for the primary response, plus sensitivity tests. Do not choose the test after seeing p-values.

**Test path:** Welch and Kruskal–Wallis live side by side; `05_test_path_gate.md` declares which is primary. Branch map: [`../test_paths.md`](../test_paths.md).

## Resources / context

- `docs/context/test_plan.md`
- `docs/context/assumptions.md`
- SciPy `f_oneway`/`kruskal` docs
- statsmodels `anova_lm`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/hypothesis_testing/shared/omnibus.csv` | omnibus results |
| update | `docs/context/test_plan.md` | declared test path |
| update | `docs/context/test_plan.md` | executed test record |

## Implementation points

- Welch primary; KW sensitivity.
- Seed-cluster permutation for dependence.
- Classic ANOVA reference only.

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
| `01_welch_anova.md` | blocked | Step 4 | Welch result |
| `02_kruskal_wallis.md` | blocked | Step 4 | KW result |
| `03_cluster_permutation.md` | blocked | Step 4 independence verdict | permutation result |
| `04_test_decision_rule.md` | todo | — | decision rule |
| `05_test_path_gate.md` | todo | `04_transform_decision.md` | declared path per response |
