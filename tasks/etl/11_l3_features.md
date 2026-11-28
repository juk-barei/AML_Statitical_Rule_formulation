# L3 Wallet Features Builder (`features/`)
<!-- Created: 2026-11-27 | Last updated: 2026-11-28 | Edit count: 2 -->

- **Status:** done (merged in PR #42; materialized and exported in `phase1_transformed_transform_20261127T224625Z`)
- **Blocked by:** `09_l1_clean.md` (done), `10_l2_cohort.md` (done)
- **Blocks:** `12_transformed_export_audit.md` (in_progress)
- **Owner:** user manual execution + agent proposal
- **Output:** `transform.wallet_features` (`9,876,867` rows, `73` columns covering `H1`–`H6`)
- **Updated:** 2026-11-28

## Resources / context

- `docs/context/transform_phase_recommendations.md`
- `docs/context/feature_audit.md`
- `docs/dev/software_concepts/02-layers-and-boundaries.md` (accepted)
- `docs/dev/software_concepts/10-sql-rules.md` (accepted)

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `src/scripts/etl/transform/features/rules.py` | Pure H1–H6 formulas, thresholds, and n-flow specs |
| create | `src/scripts/etl/transform/features/01_feat_scalar.sql` | Scalar counts, volumes, lifetime, amount CV, and 4444/dust sensitivity |
| create | `src/scripts/etl/transform/features/02_feat_degrees_and_h4.sql` | Single edge dedupe → H3 degrees + H4 Jaccard |
| create | `src/scripts/etl/transform/features/03_feat_usdt_temporal.sql` | H1 pass-through speed + H2 1h USDT burst ratio |
| create | `src/scripts/etl/transform/features/04_feat_h6_cv.sql` | H6 inter-arrival CV (`all` and `OUT`-only) |
| create | `src/scripts/etl/transform/features/05_wallet_features.sql` | Final L3 assembly + `log1p_*` + `elig_*` + staging cleanup |
| create | `src/scripts/etl/transform/features/main.py` | Step-by-step runner + parity check + `feature_nflow.csv` writer |
| create | `src/scripts/etl/transform/features/README.md` | Module runbook |
| create | `src/scripts/etl/transform/features/tests/test_features.py` | Pure formula, SQL guardrail, and DuckDB parity checks |
| create | `docs/dev/etl/transform/features/l3-wallet-features-and-eligibility.md` | Architecture & scaling-boundary note |

## Done when

- `python -m src.scripts.etl.transform.features.tests.test_features` passes (verified).
- User reviews & executes `01_feat_scalar` → `05_wallet_features` → `nflow`.
- `COUNT(*) == 9,876,867` (1-to-1 with `transform.cohort_wallet`) and `feature_nflow.csv` reconciles with `raw/local_feature_nflow.csv`.
