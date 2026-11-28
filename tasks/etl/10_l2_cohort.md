# L2 Cohort Builder (`cohort/`)
<!-- Created: 2026-11-27 | Last updated: 2026-11-28 | Edit count: 2 -->

- **Status:** done (merged in PR #41; materialized and exported in `phase1_transformed_transform_20261127T224625Z`)
- **Blocked by:** `06_feature_profile.md` (done)
- **Blocks:** `11_l3_features.md` (done), `12_transformed_export_audit.md` (in_progress)
- **Owner:** user manual execution + agent proposal
- **Output:** `transform.cohort_wallet` (`9,876,867` rows: `17,046` illicit + `3,959,525` suspicious + `5,180,495` licit + `719,801` unlabeled)
- **Updated:** 2026-11-28

## Resources / context

- `docs/context/transform_phase_recommendations.md`
- `docs/dev/software_concepts/01-complexity-and-modules.md` (accepted)
- `docs/dev/software_concepts/02-layers-and-boundaries.md` (accepted)
- `docs/dev/software_concepts/10-sql-rules.md` (accepted)

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `src/scripts/etl/transform/cohort/rules.py` | Pure cohort priority, nesting, and partition checks |
| create | `src/scripts/etl/transform/cohort/01_cohort_wallet.sql` | Full-universe L2 cohort builder SQL |
| create | `src/scripts/etl/transform/cohort/02_cohort_indexes.sql` | Post-materialization PK, CHECK constraints, and indexes |
| create | `src/scripts/etl/transform/cohort/main.py` | Step-by-step runner + partition assertions + n-flow CSVs |
| create | `src/scripts/etl/transform/cohort/README.md` | Module runbook |
| create | `src/scripts/etl/transform/cohort/tests/test_cohort.py` | Pure-rule, SQL guardrail, nullable anti-join & fan-out tests |
| create | `docs/dev/etl/transform/cohort/l2-cohort-priority-and-nesting.md` | Architecture & reconciliation note |

## Done when

- `python -m src.scripts.etl.transform.cohort.tests.test_cohort` passes (verified).
- User reviews & executes `01_cohort_wallet` → `02_cohort_indexes` → `nflow`.
- Exact partition reconciles: `17,046 + 3,959,525 + 5,180,495 + 719,801 = 9,876,867`, with `min_hop_level IS NULL` outside `suspicious`.
