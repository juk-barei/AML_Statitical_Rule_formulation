# `hypothesis_testing`

Code for the eight-step ANOVA workflow on the active hypotheses **H2, H4, H6** (H1, H3, H5 are deferred). The live plan, status, and task tables are in [`tasks/hypothesis_testing/`](../../../tasks/hypothesis_testing/README.md) — read the tracker first; this folder holds the code that runs the steps.

Eight steps: response/factor/groups → H0/Ha and α → explore → assumptions → omnibus test → post-hoc → effect size → conclusion. Assumptions decide the branch: parametric (ANOVA, Tukey HSD) or non-parametric (Kruskal–Wallis, Dunn). Report effect sizes and exact denominators beside every p-value.

Inference constraints — nesting, seed-cluster dependence, illicit vs licit contrast — are in [`AGENTS.md`](../../../AGENTS.md).

## Folders

| Folder | Contents | Output |
| --- | --- | --- |
| `shared/` | Helpers used by more than one hypothesis: loading the frozen cohort table, assumption checks, n-flow tables, effect-size and formatting helpers | `outputs/hypothesis_testing/shared/` |
| `h2/` | H2 response, factors, groups, tests | `outputs/hypothesis_testing/h2/` |
| `h4/` | H4 response, factors, groups, tests | `outputs/hypothesis_testing/h4/` |
| `h6/` | H6 response, factors, groups, tests | `outputs/hypothesis_testing/h6/` |

One hypothesis, one folder. Anything used by only one hypothesis stays in that folder.

## Inputs

- `outputs/etl/transform/` — cleaned, eligible, feature-level tables from the ETL path.
- `outputs/etl/export/<snapshot>/` — the frozen handoff snapshot (`cohort_wallet.parquet` and event exports) when a test must be reproducible against a fixed freeze.
- `outputs/eda/` — exploration outputs for step 3 (distributions, group shape, outliers) and the chart decisions they produced.
- `outputs/etl/profile/` — denominators and cohort counts.

State the snapshot and row counts beside every quantitative claim, and never mix CSV-export counts with mirror counts.

## Outputs

`outputs/hypothesis_testing/{shared,h2,h4,h6}/` — assumption-check tables, test result tables, post-hoc pairs, effect sizes, and the n-flow for each response. Name files after the hypothesis and response so a result can be traced back to the step that produced it.

Code reads the mirror through the SQL-first path only; no notebook-sourced writes and no full-table pandas loads. See `AGENTS.md` and [`../etl/README.md`](../etl/README.md).
