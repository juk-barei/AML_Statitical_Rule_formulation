# Numerical with categorical

- **Status:** blocked
- **Blocked by:** Step 1 cohort
- **Blocks:** Step 4
- **Owner:** worker
- **Output:** group comparison plots
- **Updated:** 2026-11-20

## Objective

Side-by-side boxplots, overlaid densities, and mean ± SD strip plots for illicit / suspicious / licit (or unlabeled).

## Resources / context

- `docs/external_resources/Lecture_02_Exploratory Data Analysis_v1.pdf`
- `src/notebooks/1.1_ILLICIT_EDA.ipynb` — current EDA and executed outputs
- `docs/context/step_1_profiling_samples.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/notebooks/1.1_ILLICIT_EDA.ipynb` | group comparison cells |
| create | `outputs/EDA_ILLICIT/bivariate_num_cat/` | figures |

## Implementation points

- Side-by-side boxplots and overlaid densities.
- Mean ± SD strip plot.
- Show n per group; keep groups comparable.

## Done when

- Three-group panels are comparable.
- n per group is shown.
- Outliers are visible.
