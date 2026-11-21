# Categorical with categorical

- **Status:** blocked
- **Blocked by:** `01_eda_restructure_lecture02.md`
- **Blocks:** Step 8
- **Owner:** worker
- **Output:** crosstabs and bars
- **Updated:** 2026-11-20

## Objective

Crosstab, grouped/stacked bars, heatmap of counts, and chi-square where the cells are adequate.

## Resources / context

- `docs/external_resources/Lecture_02_Exploratory Data Analysis_v1.pdf`
- `src/notebooks/1.1_ILLICIT_EDA.ipynb` — current EDA and executed outputs
- `docs/context/cohort_contract.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/notebooks/1.1_ILLICIT_EDA.ipynb` | crosstab/bar cells |
| create | `outputs/EDA_ILLICIT/bivariate_cat_cat/` | figures |

## Implementation points

- Crosstab, grouped/stacked bars, heatmap.
- Chi-square only when cells are adequate.
- Flag sparse cells.

## Done when

- Row/column percentages are clear.
- Sparse cells are flagged.
