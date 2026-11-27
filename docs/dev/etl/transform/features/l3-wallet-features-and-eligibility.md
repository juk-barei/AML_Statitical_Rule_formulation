# L3 Wallet-Grain H1–H6 Features & Eligibility (`etl/transform/features`)
<!-- Created: 2026-11-27 | Last updated: 2026-11-27 | Edit count: 1 -->

- **Code:** `src/scripts/etl/transform/features/{rules.py,01_feat_scalar.sql,02_feat_degrees_and_h4.sql,03_feat_usdt_temporal.sql,04_feat_h6_cv.sql,05_wallet_features.sql,main.py}`
- **Tests:** `src/scripts/etl/transform/features/tests/test_features.py`
- **Evidence:** `outputs/etl/transform/profile/raw/{local_wallet_distributions,local_feature_nflow}.csv`

## Mechanism

L3 reads **only L1 (`transform.clean_transactions`) and L2 (`transform.cohort_wallet`)** — never L0 raw schemas (`02-layers-and-boundaries.md`) — and decomposes feature computation into 5 sequential SQL steps so an 8 GB host never builds multiple 50M-row `COUNT(DISTINCT)` hash tables concurrently:

1. **`01_feat_scalar.sql`**: scalar counts, volumes, `zero_tx_count`, H2 `tx_lifetime_days`, H3 `amount_cv_usdt`, plus sensitivity metrics (`trx_tx_count_excl_4444`, `trx_volume_excl_4444`, `trx_tx_count_nodust`). `fee_trx` is excluded by design because `licit.transactions.fee_trx` is 100% zero (schema-origin leakage).
2. **`02_feat_degrees_and_h4.sql`**: deduplicates directed edges once into `_stg_distinct_edges`, computes H3 counterparty degrees and H4 `jaccard_index`, then immediately drops `_stg_distinct_edges`.
3. **`03_feat_usdt_temporal.sql`**: computes H1 `min_passthrough_sec_usdt` using an explicit `ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING` frame (deterministic `IN` before `OUT` tie-break) and H2 `burst_ratio_usdt` / `burst_ratio_usdt_any` using a 1-hour `RANGE` calendar window.
4. **`04_feat_h6_cv.sql`**: pre-filters via `EXISTS` to wallets with `total_tx_count >= 5`, skipping ~8.5M inactive wallets before computing `cv_delta_t_all` and directional `cv_delta_t_out`.
5. **`05_wallet_features.sql`**: left-joins all 4 staging tables onto `transform.cohort_wallet` (preserving all `9,876,867` wallets including the `27,017` hop-only wallets), adds stateless `log1p_*` transforms and explicit `elig_*` gates, orders by `(wallet_class, wallet_address)` for Parquet row-group pruning, adds `PRIMARY KEY (wallet_address)`, and drops all `_stg_*` tables.

## Boundary Decisions

- **Full `H1`–`H6` scope before export:** Teammates own `H1`/`H3`/`H5` and the web app; narrowing to `H2`/`H4`/`H6` happens only **after** `transform.wallet_features` is exported via `load/main.py --stage transformed`.
- **Stateless vs. stateful scaling:** Only stateless `log1p_*` columns live in L3 (`log1p_tx_lifetime_days` reduces skewness from `2.25–5.50` to `-0.72..+0.25`). Stateful scalers (`RobustScaler`, `StandardScaler`, Winsorization) belong strictly in `src/scripts/statistical_learning/` fit on training folds only.
- **No silent drops:** Ineligible wallets stay in `transform.wallet_features` with `NULL` feature values and `elig_* = FALSE`, accounted for in `outputs/etl/transform/features/feature_nflow.csv`.

## Verification

```bash
python -m src.scripts.etl.transform.features.tests.test_features
python -m src.scripts.etl.transform.features.main --dry-run
```
