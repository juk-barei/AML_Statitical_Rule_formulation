# Local feature profile — C

- **Status:** done
- **Blocked by:** —
- **Blocks:** L1–L3 transform builders (`clean/`, `cohort/`, `features/`), H1–H6 profiling comparison
- **Owner:** worker subagent + lead review
- **Output:** `outputs/etl/transform/profile/local_wallet_distributions.csv`, `local_wallet_histograms.csv`, `local_feature_nflow.csv`
- **Updated:** 2026-11-27

## Objective

Profile **all H1–H6** wallet-level features from the frozen raw Parquet snapshots
without writing to the mirror. Record eligibility, zero mass, quantiles, skewness,
pass counts, scale recommendations, and definition assumptions.

## Current result

- Unblocked via `src/scripts/etl/transform/profile/profile_pretransform.py` (DuckDB over frozen `phase1_raw_{illicit,licit}_*` Parquet snapshots, 6 GB memory bound).
- Reconciled full wallet universe: `9,876,867` = `9,849,850` accounts union + `27,017` hop-only wallets (`0` transactions, `0` blacklisted).
- Generated full-frame `local_wallet_distributions.csv` (116 feature×cohort rows across H1–H6), `local_wallet_histograms.csv` (360 bin rows for offline EDA plots), and `local_feature_nflow.csv` (116 reconciled n-flow rows).
- Unit tests (`test_profile_core`, `test_profile_features`, `test_profile_pretransform`) pass.

## Done when

- Full-frame feature profile completes within the memory/time budget. (done)
- Group counts reconcile with the cohort universe including hop-only accounting. (done)
- Long-format profile, histogram, and n-flow outputs are snapshot-tagged. (done)
