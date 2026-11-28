# Transformed Export & Raw-vs-Transformed Audit
<!-- Created: 2026-11-27 | Last updated: 2026-11-28 | Edit count: 2 -->

- **Status:** in_progress (Parquet snapshot `phase1_transformed_transform_20261127T224625Z` exported & verified; run offline DuckDB stage profile + diff + EDA plots)
- **Blocked by:** `09_l1_clean.md` (done), `10_l2_cohort.md` (done), `11_l3_features.md` (done)
- **Blocks:** `04_web_serving.md` (web app); downstream `H2`/`H4`/`H6` & teammate `H1`/`H3`/`H5` analysis already unblocked on frozen Parquet
- **Owner:** user manual execution + agent proposal
- **Output:** `outputs/etl/load/phase1_transformed_transform_20261127T224625Z/` (done), `outputs/etl/transform/profile/transformed/` (pending CLI run), `raw_vs_transformed_diff.csv` (pending CLI run)
- **Updated:** 2026-11-28

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `src/scripts/etl/transform/profile/compare_stages.py` | Read-only raw-vs-transformed distribution diff tool |
| create | `src/scripts/etl/transform/profile/tests/test_compare_stages.py` | Synthetic match/drift + dry-run checks |
| create | `docs/dev/etl/transform/transform-execution-runbook.md` | Full step-by-step execution, export, audit & cleanup runbook |
| update | `tasks/etl/README.md` | Register L1–L3 and transformed audit tasks (`09`–`12`) |

## Done when

- `python -m src.scripts.etl.transform.profile.tests.test_compare_stages` passes (verified).
- User runs `load/main.py --schema transform --stage transformed`, `run_profile --parts stage --stage transformed`, and `compare_stages.py`.
- `raw_vs_transformed_diff.csv` reports zero unexplained drift and `docs/context/{cohort_contract,sampling_evaluation,glossary}.md` are synced.
