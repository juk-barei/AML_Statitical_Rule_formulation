# Deferred hypotheses and the shared data gate
<!-- Last updated: 2026-11-28 | Edit count: 2 -->

- **Status:** H1, H3, H5 deferred; shared data gate **open** via frozen snapshot `phase1_transformed_transform_20261127T224625Z`
- **Updated:** 2026-11-28

## Phase split

| Phase | Owner | Hypotheses | Scope |
| --- | --- | --- | --- |
| 1 (now, this repo) | current team | `H2`, `H4`, `H6` | data cleaning, cohort, tests, verdicts |
| 2 (after handoff) | teammates | `H1`, `H3`, `H5` | rules `S1`, `S3`, `S5`; web application |

| Deferred | Rule | Why it is not in phase 1 |
| --- | --- | --- |
| `H1` | `S1` pass-through speed | needs paired in/out amounts and timestamps from the cleaned event table; 15-min threshold is uncalibrated |
| `H3` | `S3` spraying / funneling | needs in-degree, out-degree, and amount CV over fixed windows from the cleaned event table |
| `H5` | `S5` seed proximity | decay score is deterministic from hop distance; the open question is threshold calibration, which needs the cleaned licit arm |

Deferred means **not scheduled**, never **disproven**. Rules stay canonical in
`docs/dev/hypothesis_testing/general/all_hypothesis.md`. No `H1`/`H3`/`H5` tracker and no
per-step folders exist.

## Exception: shared data work

ETL and data-engineering tasks are **not hypothesis-specific**. Everything from
ingestion through the frozen cleaned/transformed dataset gates every hypothesis,
including deferred `H1`/`H3`/`H5` and the web-application team. Update these once;
all hypotheses inherit the result.

Pipeline-level tasks — export contract, memory-safe access, export pipeline, web
serving — live in [`tasks/etl/README.md`](../etl/README.md). The table below is only
the hypothesis-time shared tasks that consume that gate.

| Task | Status | Produces |
| --- | --- | --- |
| [`01_response_factor_groups/04_cohort_contract_v2.md`](../_archive/hypothesis_testing/01_response_factor_groups/04_cohort_contract_v2.md) | done (archived) | `phase1_transformed_transform_20261127T224625Z__cohort_wallet.parquet` (`9,876,867` wallets) |
| [`01_response_factor_groups/05_licit_ingestion_etl.md`](../_archive/hypothesis_testing/01_response_factor_groups/05_licit_ingestion_etl.md) | done (archived; licit 100%) | namespaced licit tables in the mirror |
| `01_response_factor_groups/11_licit_eda_notebook.md` | todo | `1.2_LICIT_EDA.ipynb` licit profile (DuckDB over frozen Parquet) |
| `02_hypotheses_alpha/05_licit_hypotheses.md` | todo (unblocked) | `H0_L` / `Ha_L` sign-off in `docs/context/test_plan.md` |
| `04_assumptions/04_transform_decision.md` | todo | pre-specified `log1p` or rank/permutation path |
| `03_explore/08_nflow_tables.md` | todo (unblocked) | n-flow by group × filter (`wallet_features.parquet`) |

**Gate closes when** the cohort table, licit tables, transform rule, and n-flow
table are frozen. Everything downstream is per-hypothesis.

## Handoff contract

Phase-2 owners receive, not re-derive:

- cohort table path and the group priority rules (`AGENTS.md`, `docs/context/cohort_contract.md`)
- namespaced licit table names and coverage/overlap
- the pre-specified transform per response
- n-flow tables and the feature audit for `S1`/`S3`/`S5` variables

They must not read the raw mirror; the web application consumes the risk-score
weights from `08_conclusion/04_next_phase_handoff.md`, not the raw data.

## Rules

- A shared task can be `done` while `H1`/`H3`/`H5` stay deferred.
- Shared tasks carry no hypothesis owner; status is set once.
- Never mark a shared task `done` because one hypothesis finished with it.
- Do not mix `datasets/*.csv` export counts with mirror counts in the handoff.
