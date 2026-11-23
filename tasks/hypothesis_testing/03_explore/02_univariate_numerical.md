# Univariate numerical

- **Status:** blocked
- **Blocked by:** `01_eda_restructure_lecture02.md`
- **Blocks:** `05_bivariate_num_cat.md`
- **Owner:** worker
- **Output:** plots in notebook
- **Updated:** 2026-11-20

## Objective

Histogram, density, box plot, and time-series for each response, with mean/median and threshold lines.

## Resources / context

- `docs/external_resources/Lecture_02_Exploratory Data Analysis_v1.pdf`
- `src/notebooks/1.1_ILLICIT_EDA.ipynb` — current EDA and executed outputs
- `docs/context/step_1_profiling_samples.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/notebooks/1.1_ILLICIT_EDA.ipynb` | hist/KDE/box/time cells |
| create | `outputs/eda/univariate/` | figures |

## Implementation points

- Histogram, density, box, time series.
- Show mean/median and thresholds.
- State log scale and zeros.

## Done when

- Each plot has labels and n.
- Zeros and clipping are stated.
