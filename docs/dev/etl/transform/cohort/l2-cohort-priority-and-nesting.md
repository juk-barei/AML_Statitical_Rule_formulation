# L2 Cohort Priority, Nesting, and Seed Multiplicity (`etl/transform/cohort`)
<!-- Created: 2026-11-27 | Last updated: 2026-11-28 | Edit count: 2 -->

- **Code:** `src/scripts/etl/transform/cohort/{rules.py,01_cohort_wallet.sql,02_cohort_indexes.sql,main.py}`
- **Tests:** `src/scripts/etl/transform/cohort/tests/test_cohort.py`
- **Evidence:** `outputs/etl/transform/profile/raw/{local_group_overlap,local_hop_seed,local_sampling_frame}.csv`

## Mechanism

`01_cohort_wallet.sql` materializes `transform.cohort_wallet` at strict **1-row-per-wallet** grain over the reconciled full universe (`9,876,867` wallets = `9,849,850` deduplicated accounts union + `27,017` hop-only wallets):

1. **Pre-aggregation before join (zero fan-out):** `illicit.wallet_hops` (`6,965,210` rows) has `1,211,441` multi-hop and `1,249,966` multi-seed wallets. Aggregating `MIN(hop_level)`, `MAX(hop_level)`, `COUNT(DISTINCT seed_address)`, and `COUNT(*)` in `hop_agg` before joining to `universe` guarantees exact wallet-level counts without fan-out.
2. **Deterministic `primary_seed_address`:** For cluster-aware inference (`16,371` illicit seeds with cluster sizes up to `1,906,809`), `ROW_NUMBER() OVER (PARTITION BY wallet_address ORDER BY hop_level ASC, discovered_at ASC NULLS LAST, seed_address ASC) = 1` assigns one reproducible clustering seed per hop wallet.
3. **Strict priority (`illicit > suspicious > licit > unlabeled`):** Resolves the `1,434,186` overlapping `licit.accounts` wallets (`3,387` blacklisted + `1,430,799` suspicious) and `8,306` blacklisted hop 1–5 wallets using NULL-safe joins and `EXISTS` (never `NOT IN`).
   - **`hop_level = 0` defensive guard (`hop0` CTE):** `hop_level = 0` records the crawl seed itself (`wallet_address = seed_address`, `parent_address IS NULL`, `via_tx_hash IS NULL`). In frozen `phase1_raw_illicit_20261123T043155Z`, all `478 / 478` hop-0 wallets are already in `illicit.blacklisted_wallets` (`0` outside the blacklist). Keeping `OR h0.wallet_address IS NOT NULL` in `01_cohort_wallet.sql:126` adds zero extra rows today and prevents a hop-0 seed from ever falling into `suspicious` or `unlabeled` if a future crawl inserts a seed row before syncing `blacklisted_wallets`.
4. **Hop nesting constraint:** `min_hop_level` is set to `NULL` for every non-`suspicious` wallet and enforced via `chk_cohort_hop_nesting` in `02_cohort_indexes.sql` so downstream notebooks cannot accidentally fit a crossed `wallet_class × hop` ANOVA.
5. **Contaminated licit-seed provenance:** Flags the `6 / 721` blacklisted `licit.seed_wallets` (`is_contaminated_licit_seed`) and wallets reached from them in `licit.wallet_hops` (`from_contaminated_licit_seed`) for sensitivity analysis without silently dropping them.
6. **Reconciling `local_nflow.csv` vs. `local_sampling_frame.csv`:** Earlier accounts-only counts subtracted `3,959,525` suspicious wallets (which included `27,017` hop-only wallets) from `9,849,850` accounts, under-reporting `unlabeled` as `692,784`. Taking the explicit union universe yields the exact reconciled partition: `17,046` illicit + `3,959,525` suspicious (`3,932,508` in accounts + `27,017` hop-only) + `5,180,495` licit + `719,801` unlabeled = `9,876,867`.

## Limits & Operations

- **Row ordering:** `ORDER BY wallet_class, wallet_address` prepares `transform.cohort_wallet` so `load/main.py` Parquet export gets free row-group pruning by `wallet_class`.
- **Blacklist timestamps:** `47.52%` (`8,100 / 17,046`) of `illicit.blacklisted_wallets` have NULL `blacklisted_utc`. Membership never filters on `blacklisted_utc`; `has_blacklist_timestamp` records provenance explicitly.
- **Indexing:** `02_cohort_indexes.sql` creates `PRIMARY KEY (wallet_address)`, `CHECK` constraints, and secondary indexes strictly **after** `CREATE TABLE AS`.

## Verification

```bash
python -m src.scripts.etl.transform.cohort.tests.test_cohort
python -m src.scripts.etl.transform.cohort.main --dry-run
```
