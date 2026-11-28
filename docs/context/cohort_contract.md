# Cohort contract
<!-- Last updated: 2026-11-28 | Edit count: 3 -->

**Snapshot:** `phase1_transformed_transform_20261127T224625Z` (`outputs/etl/load/phase1_transformed_transform_20261127T224625Z/phase1_transformed_transform_20261127T224625Z__cohort_wallet.parquet`).
Unit: one wallet (`9,876,867` total = `9,849,850` unique union accounts + `27,017` hop-only wallets). Priority: **`illicit` > `suspicious` > `licit` > `unlabeled`**.

| Group | Rule | Frozen count | Share |
| --- | --- | ---: | ---: |
| `illicit` | TronScan blacklist (`label = 1`) **or** `hop_level = 0` seed rows; blacklist wins at every hop | 17,046 | 0.17% |
| `suspicious` | `min(hop_level) ∈ 1..5` **and** not blacklisted (includes `27,017` hop-only wallets) | 3,959,525 | 40.09% |
| `licit` | Licit DB accounts (`6,614,681` raw) **minus** `illicit` (`3,387`) and `suspicious` (`1,430,799`) | 5,180,495 | 52.45% |
| `unlabeled` | Remaining universe (`illicit.accounts` not blacklisted, not in hops, not in licit) | 719,801 | 7.29% |

**Contamination & nesting rules (enforced in L2 `cohort_wallet`):**
- **Why `hop_level = 0` belongs to `illicit`:** `hop_level = 0` represents the crawl seed itself (0 hops from the seed, where `wallet_address = seed_address` and `parent_address` / `via_tx_hash` are `NULL`). In `phase1_raw_illicit_20261123T043155Z`, all `478 / 478` hop-0 wallets are already in `illicit.blacklisted_wallets` (`0` outside the blacklist); the `hop0` clause in `01_cohort_wallet.sql` adds zero extra wallets and acts as a defensive guard if a future crawl inserts a seed row before syncing `blacklisted_wallets`.
- `8,306` blacklisted wallets appearing in hop 1–5 are promoted to `illicit`; `1,434,186` overlapping wallets are removed from `licit` (never relabeled `unlabeled`).
- `6 / 721` licit seeds are blacklisted (`is_contaminated_licit_seed` / `from_contaminated_licit_seed` flags retained for sensitivity audits).
- `min_hop_level` is nested strictly inside `suspicious` (`NULL` for all other classes). Wallet is the experimental unit; `primary_seed_address` (`16,371` illicit seeds) is the clustering unit. Never cross `wallet_class × hop`.
