# Step 3 — Explore: boxplots and means

- **Status:** in_progress
- **Blocked by:** [Step 1](../01_response_factor_groups/main.md), [Step 2](../02_hypotheses_alpha/main.md)
- **Blocks:** [Step 4](../04_assumptions/main.md)
- **Updated:** 2026-11-22

## Objective

Explore each response by group and restructure the EDA notebook to follow Lecture 02. Report centre, spread, shape, outliers, and n-flow before testing.

## Resources / context

- `docs/external_resources/Lecture_02_Exploratory Data Analysis_v1.pdf`
- `src/notebooks/1.1_ILLICIT_EDA.ipynb` — current EDA and executed outputs
- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `docs/hypothesis.md` — H2/H4/H6 definitions and thresholds

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/notebooks/1.1_ILLICIT_EDA.ipynb` | restructured EDA |
| create | `outputs/EDA_ILLICIT/` | figures and tables |

## Implementation points

- Follow Lecture 02 section order.
- Keep the three-group four-view panels.
- Report n and shape before inference.

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
| `01_eda_restructure_lecture02.md` | todo | Step 1 cohort | updated notebook plan |
| `02_univariate_numerical.md` | blocked | `01_eda_restructure_lecture02.md` | hist/KDE/box/time plots |
| `03_univariate_categorical.md` | blocked | `01_eda_restructure_lecture02.md` | frequency/bar plots |
| `04_bivariate_num_num.md` | blocked | `01_eda_restructure_lecture02.md` | scatter/r/heatmap |
| `05_bivariate_num_cat.md` | blocked | Step 1 cohort | group box/KDE/mean±SD |
| `06_bivariate_cat_cat.md` | blocked | `01_eda_restructure_lecture02.md` | crosstab/chi-square |
| `07_multivariate_preview.md` | todo | `05_bivariate_num_cat.md` | preview note |
| `08_nflow_tables.md` | todo | Step 1 cohort | group × filter table |
