# Transformation Execution, Export & Audit Runbook (Proposal)
<!-- Created: 2026-11-27 | Last updated: 2026-11-27 | Edit count: 2 -->

Step-by-step runbook for manually reviewing, executing, exporting, and auditing the L1–L3 transformation pipeline without touching L0 raw tables (`illicit.*`, `licit.*`). All `.sql` files are directly executable in `psql` / DBeaver (no template placeholders).

## 1. Branch Review & Merge Order

Each phase sits on its own narrow branch for review before merging into `main`:

1. `layhok/general-docs` — decision & forensic validation docs (`docs/context/{transform_phase_recommendations,ingestion_anomaly_validation}.md`)
2. `layhok/etl-load` — `default_out_dir()` fix pointing to `outputs/etl/load/` (`src/scripts/etl/load/`)
3. `layhok/etl-clean` — L1 cleaning (`src/scripts/etl/transform/clean/`)
4. `layhok/etl-cohort` — L2 cohort priority (`src/scripts/etl/transform/cohort/`)
5. `layhok/etl-features` — L3 H1–H6 features (`src/scripts/etl/transform/features/`)
6. `layhok/etl-transform-audit` — verification/cleanup SQL, stage comparator, and execution runbook (`90_verify_transform_counts.sql`, `99_drop_transform_schema.sql`, `compare_stages.py`, `tasks/etl/`)

## 2. Offline Verification (Zero PostgreSQL Writes)

```bash
python -m src.scripts.etl.transform.clean.tests.test_clean
python -m src.scripts.etl.transform.cohort.tests.test_cohort
python -m src.scripts.etl.transform.features.tests.test_features
python -m src.scripts.etl.transform.profile.tests.test_compare_stages
```

## 3. Step-by-Step Local DB Execution (Manual Fact-Check Mode)

Preview every SQL statement first with `--dry-run`, or copy-paste each `.sql` file directly into `psql`:

```bash
# --- Phase 1: L1 Clean ---
python -m src.scripts.etl.transform.clean.main --dry-run
python -m src.scripts.etl.transform.clean.main --step 01_clean_transactions
python -m src.scripts.etl.transform.clean.main --step 02_clean_wallet_hops
python -m src.scripts.etl.transform.clean.main --step 03_clean_indexes
python -m src.scripts.etl.transform.clean.main --step nflow

# --- Phase 2: L2 Cohort ---
python -m src.scripts.etl.transform.cohort.main --dry-run
python -m src.scripts.etl.transform.cohort.main --step 01_cohort_wallet
python -m src.scripts.etl.transform.cohort.main --step 02_cohort_indexes
python -m src.scripts.etl.transform.cohort.main --step nflow

# --- Phase 3: L3 Features (all H1-H6) ---
python -m src.scripts.etl.transform.features.main --dry-run
python -m src.scripts.etl.transform.features.main --step 01_feat_scalar
python -m src.scripts.etl.transform.features.main --step 02_feat_degrees_and_h4
python -m src.scripts.etl.transform.features.main --step 03_feat_usdt_temporal
python -m src.scripts.etl.transform.features.main --step 04_feat_h6_cv
python -m src.scripts.etl.transform.features.main --step 05_wallet_features
python -m src.scripts.etl.transform.features.main --step nflow
```

Expected reconciliation checkpoints:
- L1 `clean_transactions`: `26,189,701` unique `tx_hash` (`26,343,989 - 154,288` overlap).
- L2 `cohort_wallet`: `9,876,867` total (`17,046` illicit + `3,959,525` suspicious + `5,180,495` licit + `719,801` unlabeled); `0` rows violating `min_hop_level` nesting.
- L3 `wallet_features`: exact `9,876,867` rows (1-to-1 with `cohort_wallet`).

## 4. Verification SQL, Frozen Transformed Export & Stage Audit

Run read-only checkpoint queries in `psql` / DBeaver:
- `src/scripts/etl/transform/90_verify_transform_counts.sql`

Then freeze and audit the transformed snapshot (`--allow-partial` is required because `transform` has no `_etl_progress` bookkeeping table):

```bash
# Dry-run export first (defaults to outputs/etl/load/phase1_transformed_transform_<UTC>)
python -m src.scripts.etl.load.main \
  --schema transform --stage transformed \
  --tables clean_transactions,clean_wallet_hops,cohort_wallet,wallet_features \
  --allow-partial --dry-run

# Export frozen transformed Parquet + manifest + SHA-256
python -m src.scripts.etl.load.main \
  --schema transform --stage transformed \
  --tables clean_transactions,clean_wallet_hops,cohort_wallet,wallet_features \
  --allow-partial

# Profile frozen transformed snapshot -> outputs/etl/transform/profile/transformed/
python -m src.scripts.etl.transform.profile.run_profile --parts stage --stage transformed

# Compare raw vs transformed distributions -> raw_vs_transformed_diff.csv
python -m src.scripts.etl.transform.profile.compare_stages
```

## 5. End-of-Project Cleanup & Documentation Freshness

- After the frozen transformed Parquet snapshot is verified and archived, run `src/scripts/etl/transform/99_drop_transform_schema.sql` (`DROP SCHEMA IF EXISTS transform CASCADE;`) to reclaim local PostgreSQL disk space cleanly without touching L0 (`illicit.*`, `licit.*`).
- Refresh stale pre-ingestion counts in `docs/context/cohort_contract.md`, `docs/context/sampling_evaluation.md`, and `docs/context/glossary.md` once the transformed snapshot is frozen.
