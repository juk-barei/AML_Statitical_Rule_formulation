# L1 Transaction & Hop Cleaning (`etl/transform/clean`)
<!-- Created: 2026-11-27 | Last updated: 2026-11-27 | Edit count: 1 -->

- **Code:** `src/scripts/etl/transform/clean/{rules.py,01_clean_transactions.sql,02_clean_wallet_hops.sql,03_clean_indexes.sql,main.py}`
- **Tests:** `src/scripts/etl/transform/clean/tests/test_clean.py`
- **Evidence:** `docs/context/transform_phase_recommendations.md`, `docs/context/ingestion_anomaly_validation.md`

## Mechanism

L1 reads L0 mirror tables (`illicit.transactions`, `licit.transactions`, `illicit.wallet_hops`) strictly read-only and materializes three derived tables in PostgreSQL schema `transform`:

1. **`transform.clean_tx_conflicts`**: inner join on `tx_hash` using `IS DISTINCT FROM` across `token_symbol`, `amount`, `block_timestamp`, `from_address`, and `to_address`. Captures the ~3,200 field-conflicting shared hashes (primarily `2,367` 4-vs-6 decimal USDT rounding differences and `401` `0.0`-vs-`uint256.max` TRC-20 `Approval` rows) for auditability.
2. **`transform.clean_transactions`**: `UNION ALL` of both schemas with symmetric non-destructive flags (`amount_flag`, `timestamp_flag`, `is_1sun_dust`, `is_trx_4444_artifact`, `is_valid_for_features`) deduplicated to 1 row per `tx_hash` via `ROW_NUMBER()` (preferring valid `amount_flag`, valid `timestamp_flag`, then `illicit` because `licit` has `fee_trx = 0` everywhere and `1,017,778` `4444.444444` TRX artifacts).
3. **`transform.clean_wallet_hops`**: left-joins `illicit.wallet_hops` onto `transform.clean_transactions` without dropping rows, tagging `via_tx_status` (`null_hop0`, `missing_tx`, or the edge transaction's `amount_flag`) so H5 can test hop-graph sensitivity to dust (`78.11%` of hop edges) and missing tx hashes (`108,124` rows).

## Why non-destructive flags + dedicated `transform` schema

- **Scenario:** Deleting `zero` or `dust` rows physically during cleaning would break two downstream analyses at once: `zero_tx_count` is an informative address-poisoning signal (15.9% of illicit wallets vs 0.19% of licit), and `78.11%` of `wallet_hops` edges traverse `< 0.01 TRX` dust. Flagging rows in `transform.clean_transactions` makes every downstream filter explicit, countable, and reversible while leaving L0 untouched.
- **Confirmed upstream `4444.444444` TRX artifact:** Direct online-DB validation proved `1,017,778` licit TRX rows (`11.22%`) and `7,314 / 8,852` `>100B` TRX rows are exact multiples of `1 / 0.000225` with 49.2% matching address suffixes. `is_trx_4444_artifact` flags it identically across both schemas so L3 can report both baseline and artifact-excluded TRX metrics.

## Limits & Operations

- **Memory:** `01_clean_transactions.sql` partitions `26.34M` rows by `tx_hash` for `ROW_NUMBER()`. Run with conservative `SET LOCAL work_mem = '128MB'` and allow temporary disk spill.
- **Indexing:** `03_clean_indexes.sql` runs only **after** `CREATE TABLE AS` and builds partial indexes (`WHERE is_valid_for_features`) on `from_address` and `to_address`.
- **Precision:** `amount` is cast to `DOUBLE PRECISION` alongside `amount_exact` (`TEXT`), matching `load/main.py` Parquet semantics while preserving string sentinel checks.
- **Cleanup:** `DROP SCHEMA transform CASCADE;` removes all derived tables at project end without touching `illicit.*` or `licit.*`.

## Verification

```bash
# 1. Pure-Python + in-memory DuckDB parity checks (zero PostgreSQL writes)
python -m src.scripts.etl.transform.clean.tests.test_clean

# 2. Preview resolved SQL without executing
python -m src.scripts.etl.transform.clean.main --dry-run

# 3. Execute step-by-step when approved
python -m src.scripts.etl.transform.clean.main --step 01_clean_transactions
python -m src.scripts.etl.transform.clean.main --step 02_clean_wallet_hops
python -m src.scripts.etl.transform.clean.main --step 03_clean_indexes
python -m src.scripts.etl.transform.clean.main --step nflow
```
