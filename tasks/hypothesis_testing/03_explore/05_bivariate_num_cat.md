# Numerical with categorical
<!-- Last updated: 2026-11-28 | Edit count: 2 -->

- **Status:** todo (unblocked — query frozen `phase1_transformed_transform_20261127T224625Z__wallet_features.parquet` via DuckDB)
- **Blocked by:** —
- **Blocks:** Step 4
- **Owner:** worker
- **Output:** group comparison plots
- **Updated:** 2026-11-28

## Objective

Side-by-side boxplots, overlaid densities, and mean ± SD strip plots comparing clean `illicit` vs. `licit` alongside nested `suspicious` (`min_hop_level` 1–5) and `unlabeled`.

## Resources / context

- `docs/external_resources/Lecture_02_Exploratory Data Analysis_v1.pdf`
- `src/notebooks/1.1_ILLICIT_EDA.ipynb` — current EDA and executed outputs
- `docs/context/step_1_profiling_samples.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/notebooks/1.1_ILLICIT_EDA.ipynb` | group comparison cells |
| create | `outputs/eda/bivariate/` | figures |

## Implementation points

- Side-by-side boxplots and overlaid densities.
- Mean ± SD strip plot.
- Show n per group; keep groups comparable.

## Done when

- Three-group panels are comparable.
- n per group is shown.
- Outliers are visible.
