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

Status vocabulary: `todo` / `in_progress` / `blocked` / `done`. `done` files are
archived per [`AGENTS.md`](../../AGENTS.md); do not delete them.

## Task file shape

Every task records **resources / context**, **files** (`create` / `update` / `delete` /
`rename`, exact paths), **implementation points**, and **done when**.

## Gate

The data gate closes when the export contract is frozen, memory-safe access is verified,
one snapshot is exported under `outputs/etl/load/<snapshot>/`, and the wallet-level
serving table is loaded. Before that, every hypothesis step downstream of the data
stays blocked on the task it needs.
