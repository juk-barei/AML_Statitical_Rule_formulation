# Statistical learning — blocked

**Status:** blocked until hypothesis testing completes. No task table exists yet; it is
written when the gate opens, not before.

Unblock condition: `H2`, `H4`, `H6` have a confirmed effect, a known direction, and a
validated assumption set, and the results in `outputs/hypothesis_testing/{shared,h2,h4,h6}/`
are final. A model fitted on a hypothesis that is still moving is not worth the row.

- **Code:** [`src/scripts/statistical_learning/README.md`](../../src/scripts/statistical_learning/README.md)
  — inputs, rules, and expected outputs.
- **Data:** `outputs/etl/load/<snapshot>/cohort_wallet.parquet`; shared data work is
  tracked in [`tasks/etl/README.md`](../etl/README.md).
- **Upstream tracker:** [`tasks/hypothesis_testing/README.md`](../hypothesis_testing/README.md).
- **Outputs:** `outputs/statistical_learning/`.
