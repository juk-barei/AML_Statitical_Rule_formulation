# EDA — exploratory data analysis

Code for data-science exploration and presentation plots. Follows the Lecture 02 structure in `docs/external_resources/Lecture_02_Exploratory Data Analysis_v1.pdf`, which covers steps 1–3 of the 8-step workflow in `tasks/hypothesis_testing/`.

Data rules (mirror is read-only, SQL-first access, sampling, n-flow) are in [`AGENTS.md`](../../../AGENTS.md). This README only covers how the EDA code is organised.

## Module rule

Write each plot or table as a **reusable module function**, not inline notebook code, so the same function serves every hypothesis and arm:

- one function per plot, explicit `ax`/`fig` return;
- accept a small dataframe or a SQL query, never a full table;
- print the numbers the plot supports;
- notebooks in `src/notebooks/` import these modules.

Functions must not load `accounts`, `transactions`, or `wallet_hops` wholesale into pandas. Aggregate or sample in SQL first; return wallet-level aggregates or a bounded sample.

## Order

| Step | Section | Output folder |
| --- | --- | --- |
| 1 | Data types and chart map | `outputs/eda/profile/` |
| 2 | Univariate numerical | `outputs/eda/univariate/` |
| 3 | Univariate categorical | `outputs/eda/univariate/` |
| 4 | Numerical–numerical | `outputs/eda/bivariate/` |
| 5 | Numerical–categorical (includes the three-group comparison) | `outputs/eda/bivariate/` |
| 6 | Categorical–categorical | `outputs/eda/bivariate/` |
| 7 | Multivariate | `outputs/eda/multivariate/` |

Analytics that do not fit these sections go to `outputs/eda/additional/`.

## Input

Primary input is the data-engineering profile in `outputs/etl/transform/profile/` (`db_overview.csv`, `columns.csv`, `relations.csv`, `cohort_counts.csv`, `group_overlap.csv`, `local_cohort_check.csv`). Plot and describe those files directly; only query the mirror when a section needs a distribution the profile does not carry.

## Output

`outputs/eda/{univariate,bivariate,multivariate,profile,additional}/`. Put each figure and its supporting table side by side, and state the snapshot, the arm, and the denominator that produced it.
