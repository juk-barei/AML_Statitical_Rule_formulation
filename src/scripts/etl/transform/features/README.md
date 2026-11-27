# `etl/transform/features` — L3 Wallet-Grain H1–H6 Features (Proposal)
<!-- Created: 2026-11-27 | Last updated: 2026-11-27 | Edit count: 1 -->

Materializes `transform.wallet_features` (1 row per wallet = `transform.cohort_wallet`) covering **all hypotheses (`H1`–`H6`)** prior to transformed export. Narrowing to `H2`/`H4`/`H6` happens only downstream of the exported snapshot.

## Files

| File | Role |
| --- | --- |
| `rules.py` | Pure-Python H1–H6 reference formulas, thresholds, and n-flow specs. |
| `01_feat_scalar.sql` | Counts, volumes, `zero_tx_count`, H2 `tx_lifetime_days`, H3 `amount_cv_usdt`, plus `4444.444444` & no-dust sensitivity metrics. |
| `02_feat_degrees_and_h4.sql` | Single directed-edge dedupe powering H3 degrees and H4 Jaccard. |
| `03_feat_usdt_temporal.sql` | H1 USDT pass-through speed (`min_passthrough_sec_usdt`) and H2 1-hour burst (`burst_ratio_usdt`, `burst_ratio_usdt_any`). |
| `04_feat_h6_cv.sql` | H6 inter-arrival CV (`cv_delta_t_all` and directional `cv_delta_t_out`). |
| `05_wallet_features.sql` | Joins `cohort_wallet` + all staging tables → `transform.wallet_features` with stateless `log1p_*`, explicit `elig_*` gates, PK, and drops staging tables. |
| `main.py` | Thin CLI runner with `--dry-run`, `--step`, row-count parity assertion, and `outputs/etl/transform/features/feature_nflow.csv` writer. |
| `tests/test_features.py` | Pure formula tests, `10-sql-rules.md` checks, and full in-memory DuckDB parity fixture covering H1–H6 edge cases. |

## Step-by-Step Execution (Manual Review Mode)

```bash
# Preview all L3 SQL without touching PostgreSQL
python -m src.scripts.etl.transform.features.main --dry-run

# Execute one step at a time after L1 (clean/) and L2 (cohort/) finish
python -m src.scripts.etl.transform.features.main --step 01_feat_scalar
python -m src.scripts.etl.transform.features.main --step 02_feat_degrees_and_h4
python -m src.scripts.etl.transform.features.main --step 03_feat_usdt_temporal
python -m src.scripts.etl.transform.features.main --step 04_feat_h6_cv
python -m src.scripts.etl.transform.features.main --step 05_wallet_features
python -m src.scripts.etl.transform.features.main --step nflow
```

## Verification

```bash
# Pure-Python + in-memory DuckDB parity checks (never touches PostgreSQL)
python -m src.scripts.etl.transform.features.tests.test_features
```

Architecture, scaling boundary, and trade-offs: [`docs/dev/etl/transform/features/l3-wallet-features-and-eligibility.md`](../../../../../docs/dev/etl/transform/features/l3-wallet-features-and-eligibility.md).
