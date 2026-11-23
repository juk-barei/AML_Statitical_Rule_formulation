# Licit EDA notebook

- **Status:** todo
- **Blocked by:** —
- **Blocks:** Step 3
- **Owner:** worker
- **Output:** `src/notebooks/1.2_LICIT_EDA.ipynb`
- **Updated:** 2026-11-23

## Objective

Build the licit EDA using the same Lecture 02 structure and the same cohort contract as the illicit notebook.

## Resources / context

- `src/notebooks/1.1_ILLICIT_EDA.ipynb` — current EDA and executed outputs
- `docs/external_resources/Lecture_02_Exploratory Data Analysis_v1.pdf`
- `docs/context/cohort_contract.md`
- `docs/context/licit_ingestion.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/notebooks/1.2_LICIT_EDA.ipynb` | licit EDA |
| create | `outputs/eda/` | figures and tables |

## Implementation points

- Same Lecture 02 section order as `1.1`.
- Read-only against the mirror.
- Use separate output paths; never call unlabeled licit.

## Done when

- Notebook reads only the mirror.
- Same chart hierarchy as `1.1`.
- Outputs land in a separate directory.
