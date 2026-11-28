# ETL — shared data gate

ETL and data-engineering tasks are **shared by every hypothesis**: `H2`, `H4`, `H6`,
the deferred `H1`/`H3`/`H5`, and the web application. No task here has a hypothesis
owner — ingestion, cleaning, cohort, and the frozen export gate every arm at once, so
a change here is inherited everywhere and must be recorded once.

Hypothesis-specific work stays in [`tasks/hypothesis_testing/`](../hypothesis_testing/README.md).

- **[`src/scripts/etl/README.md`](../../src/scripts/etl/README.md)** — pipeline rules:
  extract, transform, load/export contract, memory-safe access, checklist.
- **[`AGENTS.md`](../../AGENTS.md)** — data authority, cohort priority, export and
  sampling rules. This tracker implements them; it does not redefine them.
- **Outputs:** `outputs/etl/{extract,transform,load}`; handoff snapshots in
  `outputs/etl/load/<snapshot>/`.

## Tasks

| File | Status | Blocked by | Blocks | Produces |
| --- | --- | --- | --- | --- |
| [`01_export_contract.md`](01_export_contract.md) | done | — | `03_export_pipeline.md` | frozen snapshot contract + checklist |
| [`02_memory_safe_access.md`](02_memory_safe_access.md) | in_progress | — | every analysis step | reusable SQL/streaming guidance + verification check |
| [`03_export_pipeline.md`](03_export_pipeline.md) | done | `01_export_contract.md`; complete ingestion | `04_web_serving.md`; every hypothesis | `src/scripts/etl/load/main.py`; illicit/licit snapshots |
| [`04_web_serving.md`](04_web_serving.md) | todo | `03_export_pipeline.md` | web application | wallet-level serving table |
| [`05_local_profiling.md`](05_local_profiling.md) | done | — | cohort builder, licit EDA | local profile/quality/overlap/pretransform CSVs + contracts |
| [`06_feature_profile.md`](06_feature_profile.md) | done | — | L1–L3 transform builders | full-frame H1–H6 distributions, histograms, and reconciled n-flow CSVs |
| [`07_query_benchmarks.md`](07_query_benchmarks.md) | done | — | export/cohort design | benchmark CSV + query plans |
| [`08_parquet_source.md`](08_parquet_source.md) | done | — | offline setup | Parquet → PostgreSQL loader |
| [`09_l1_clean.md`](09_l1_clean.md) | done | `06_feature_profile.md` | `11_l3_features.md`; `12_transformed_export_audit.md` | L1 `clean_transactions` (`26,189,701`), `clean_tx_conflicts` (`3,194`), `clean_wallet_hops` (`6,965,210`) |
| [`10_l2_cohort.md`](10_l2_cohort.md) | done | `06_feature_profile.md` | `11_l3_features.md`; `12_transformed_export_audit.md` | L2 `cohort_wallet` (`9,876,867` wallets: `17,046` / `3,959,525` / `5,180,495` / `719,801`) |
| [`11_l3_features.md`](11_l3_features.md) | done | `09_l1_clean.md`; `10_l2_cohort.md` | `12_transformed_export_audit.md` | L3 `wallet_features` (`9,876,867` rows, `73` cols covering `H1`–`H6`) |
| [`12_transformed_export_audit.md`](12_transformed_export_audit.md) | in_progress | `09_l1_clean.md`; `10_l2_cohort.md`; `11_l3_features.md` | `04_web_serving.md`; H2/H4/H6 & teammate handoff | frozen transformed Parquet `phase1_transformed_transform_20261127T224625Z` exported; run offline `profile_stage --stage transformed` + `compare_stages` |

Status vocabulary: `todo` / `in_progress` / `blocked` / `done`. `done` files are
archived per [`AGENTS.md`](../../AGENTS.md); do not delete them.

## Task file shape

Every task records **resources / context**, **files** (`create` / `update` / `delete` /
`rename`, exact paths), **implementation points**, and **done when**.

## Gate

The analytical data gate is **open** via frozen transformed Parquet snapshot `outputs/etl/load/phase1_transformed_transform_20261127T224625Z/` (`4.19 GB`, 5 zstd Parquet files queried directly via DuckDB without local PostgreSQL). Remaining ETL items: offline transformed stage profile/diff (`12_transformed_export_audit.md`) and managed PostgreSQL web-serving load (`04_web_serving.md`).
