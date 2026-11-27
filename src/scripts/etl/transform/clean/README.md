# `etl/transform/clean` — L1 Transaction & Hop Cleaning (Proposal)
<!-- Created: 2026-11-27 | Last updated: 2026-11-27 | Edit count: 1 -->

Materializes L1 cleaned tables inside a dedicated PostgreSQL `transform` schema while leaving L0 (`illicit.*`, `licit.*`) strictly read-only.

## Files

| File | Role |
| --- | --- |
| `rules.py` | Database-free Python domain rules (`classify_amount_flag`, `classify_timestamp_flag`, `is_1sun_dust`, `is_trx_4444_artifact`, `dedupe_sort_key`). |
| `01_clean_transactions.sql` | Cross-schema union, deterministic `ROW_NUMBER()` `tx_hash` dedupe, conflict audit table (`transform.clean_tx_conflicts`), and non-destructive flags (`transform.clean_transactions`). |
| `02_clean_wallet_hops.sql` | Non-destructive `transform.clean_wallet_hops` tagging `via_tx_status` (`null_hop0`, `missing_tx`, or transaction `amount_flag`) for H5 sensitivity. |
| `03_clean_indexes.sql` | Post-materialization `PRIMARY KEY` and partial join indexes on `transform.*` only. |
| `main.py` | Thin CLI runner with `--dry-run`, `--step`, and n-flow CSV writer (`outputs/etl/transform/clean/`). |
| `tests/test_clean.py` | Pure-rule unit tests, `10-sql-rules.md` static checks, and in-memory DuckDB SQL parity fixtures. |

## Step-by-Step Execution (Manual Review Mode)

Inspect the exact SQL before executing anything:

```bash
python -m src.scripts.etl.transform.clean.main --dry-run
```

Run one step at a time and inspect counts between steps:

```bash
python -m src.scripts.etl.transform.clean.main --step 01_clean_transactions
python -m src.scripts.etl.transform.clean.main --step 02_clean_wallet_hops
python -m src.scripts.etl.transform.clean.main --step 03_clean_indexes
python -m src.scripts.etl.transform.clean.main --step nflow
```

## Verification & Cleanup

```bash
# Pure-Python + in-memory DuckDB parity tests (never touches PostgreSQL)
python -m src.scripts.etl.transform.clean.tests.test_clean

# Cleanup at project end (leaves illicit.* and licit.* untouched)
# DROP SCHEMA transform CASCADE;
```

Architecture, failure modes, and trade-offs: [`docs/dev/etl/transform/clean/l1-transaction-cleaning.md`](../../../../../docs/dev/etl/transform/clean/l1-transaction-cleaning.md).
