# Transformed Export & Raw-vs-Transformed Audit — Proposal
<!-- Created: 2026-11-27 | Last updated: 2026-11-27 | Edit count: 1 -->

- **Status:** todo (comparator + runbook proposed; awaits manual L1–L3 execution)
- **Blocked by:** `09_l1_clean.md`, `10_l2_cohort.md`, `11_l3_features.md`
- **Blocks:** `04_web_serving.md`, downstream `H2`/`H4`/`H6` hypothesis testing, teammate `H1`/`H3`/`H5` handoff
- **Owner:** user manual execution + agent proposal
- **Output:** `outputs/etl/load/phase1_transformed_transform_<UTC>/`, `outputs/etl/transform/profile/transformed/`, `raw_vs_transformed_diff.csv`
- **Updated:** 2026-11-27

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
