# EDA restructure to Lecture 02

- **Status:** todo
- **Blocked by:** Step 1 cohort
- **Blocks:** `02`–`06`
- **Owner:** worker
- **Output:** notebook structure
- **Updated:** 2026-11-20

## Objective

Reorganize `1.1_ILLICIT_EDA.ipynb` into Lecture 02 sections: data types/chart map → univariate numerical → univariate categorical → num–num → num–cat → cat–cat → multivariate.

## Resources / context

- `docs/external_resources/Lecture_02_Exploratory Data Analysis_v1.pdf`
- `src/notebooks/1.1_ILLICIT_EDA.ipynb` — current EDA and executed outputs
- `AGENTS.md` — data authority, cohort priority, task rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/notebooks/1.1_ILLICIT_EDA.ipynb` | section order and navigation |
| create | `docs/context/eda_structure.md` | section map |

## Implementation points

- Data types/chart map first.
- Then univariate → bivariate → multivariate.
- Preserve hypothesis labels and outputs.

## Done when

- Section order matches the lecture.
- Four-view group panels remain.
- Existing hypothesis labels are preserved.
