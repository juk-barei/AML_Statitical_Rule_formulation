# EDA — tracker pointer

EDA is the exploration half of the hypothesis-testing workflow, so its tasks live with the
workflow, not beside it.

- **Tasks:** [`tasks/hypothesis_testing/03_explore/`](../hypothesis_testing/03_explore/main.md)
  (and `04_assumptions/` for the shape checks that follow). The 8-step task list stays in
  [`tasks/hypothesis_testing/README.md`](../hypothesis_testing/README.md); do not duplicate it
  here.
- **Code:** [`src/scripts/eda/README.md`](../../src/scripts/eda/README.md) — module rule,
  Lecture 02 order, and the output folder per section.
- **Outputs:** `outputs/eda/{univariate,bivariate,multivariate,profile,additional}`.
- **Input:** the data-engineering profile in `outputs/etl/transform/profile/`; shared data work is
  tracked in [`tasks/etl/README.md`](../etl/README.md).
