# `statistical_learning`

**Blocked.** Nothing here runs until `hypothesis_testing` is complete and its results are accurate: only a hypothesis with a confirmed effect, a known direction, and a validated assumption set is worth modelling. Do not start a model on a hypothesis that is still moving.

## Inputs (when unblocked)

- `outputs/etl/export/<snapshot>/cohort_wallet.parquet` — frozen wallet-level cohort table: group, hop, seed, features.
- `outputs/hypothesis_testing/{shared,h2,h4,h6}/` — the confirmed results, effect sizes, and n-flow that define the response and the features.
- `outputs/eda/` — group shape and candidate features from exploration.

Models read the frozen snapshot, never the live mirror, so a result can be reproduced against a fixed row set.

## Expected outputs

`outputs/statistical_learning/` — per-hypothesis model outputs: design matrix definition, fitted model summary, cross-validation or holdout metrics, feature importance or coefficients, and the figures that support the conclusion. One subfolder per modelled hypothesis, named after the hypothesis.

## Rules

- No raw mirror reads. Read frozen Parquet from `outputs/etl/export/<snapshot>/` or DuckDB queries over it.
- `suspicious` is graph-derived from blacklisted seeds: use cluster-aware splits (group by `seed_address`) so the same seed never spans train and test.
- Keep licit, illicit, suspicious, and unlabeled arms separate; do not pool arms whose sampling frame differs.
- State the snapshot, row counts, and split design beside every metric.

Data and inference rules: [`AGENTS.md`](../../../AGENTS.md).
