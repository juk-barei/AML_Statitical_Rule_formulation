# Task tracker

Live tracker for the 8-step ANOVA workflow.

- **Status vocabulary:** `todo` / `in_progress` / `blocked` / `done`.
- Phase-1 active hypotheses are **H2, H4, H6**; **H1, H3, H5 are deferred** and have no
  tracker — see [`DEFERRED.md`](DEFERRED.md).
- ETL and data-engineering tasks are shared by **every** hypothesis, including deferred
  ones — tracked in [`tasks/etl/README.md`](../etl/README.md), not here.
- Parametric and non-parametric branches are one file each, not folders — see
  [`test_paths.md`](test_paths.md).
- Each step directory has `main.md` (objective + shared task table) and shared task files.
  Do not create per-step `H2/H4/H6` folders; update the hypothesis tracker instead.
- `done` task files move to `tasks/_archive/`; the step `main.md` table keeps the link.

## Canonical output paths

Every artifact goes under the area that produced it. EDA writes below `outputs/eda/`;
hypothesis test and verdict work writes below `outputs/hypothesis_testing/`.

| Area | Path |
| --- | --- |
| ETL | `outputs/etl/{profile,tests,transform,export}`; snapshots in `outputs/etl/export/<snapshot>/` |
| EDA | `outputs/eda/{univariate,bivariate,multivariate,profile,additional}` |
| Hypothesis testing | `outputs/hypothesis_testing/shared/` (step-level), `outputs/hypothesis_testing/{h2,h4,h6}/` (per hypothesis), verdict at `outputs/hypothesis_testing/{h2,h4,h6}/verdict.md` |
| Statistical learning | `outputs/statistical_learning/` |

Other area trackers: [`tasks/etl/`](../etl/README.md), [`tasks/eda/`](../eda/README.md),
[`tasks/statistical_learning/`](../statistical_learning/README.md).

## Task file shape

Every task and `main.md` records:

- **Resources / context** — docs, code, data, and references used.
- **Files** — `create`, `update`, `delete`, or `rename`, with exact paths.
- **Implementation points** — the main points only.
- **Done when** — the check that closes the task.

## Steps

1. `01_response_factor_groups`
2. `02_hypotheses_alpha`
3. `03_explore`
4. `04_assumptions`
5. `05_omnibus_test`
6. `06_posthoc`
7. `07_effect_size`
8. `08_conclusion`
