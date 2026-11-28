# Sampling evaluation
<!-- Last updated: 2026-11-28 | Edit count: 2 -->

**Historical online drift resolved:** Live cloud DB drift has been frozen into Phase-1 raw snapshots (`phase1_raw_illicit_20261123T043155Z` + `phase1_raw_licit_20261123T043744Z`) and reconciled into the frozen transformed Parquet snapshot `phase1_transformed_transform_20261127T224625Z` (`9,876,867` unique wallets).

**Licit cleaning & frame asymmetry (reconciled counts):**
- Raw `licit.accounts` (`6,614,681`) overlapped `3,387` blacklisted wallets and `1,430,799` suspicious wallets (`1,434,186` removed by priority in L2 `cohort_wallet`, leaving `5,180,495` clean `licit` wallets). `6 / 721` licit seeds were blacklisted (`is_contaminated_licit_seed` flagged for sensitivity).
- Even after cleaning, the sampling frames differ sharply in activity and era: `licit` p10 timestamp `2023-04-28`, `80.1%` TRX, median `1` tx, `86.3%` zero-USDT vs. `illicit` p10 `2025-10-18`, `90.5%` USDT, median `100` tx.

**Implication:** Do not prune inactive wallets in ETL; report exact `wallet_class × filter` n-flow and stratify downstream comparisons by activity band. For Phase-1 testing, census all eligible `illicit` wallets (`12,764`–`16,041`), use census or `50,000`–`100,000` stratified samples for `licit` (and seed-cluster samples on `primary_seed_address` for `suspicious`), and keep `unlabeled` (`719,801`) separate from `licit`.
