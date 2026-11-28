# Cohort contract
<!-- Last updated: 2026-11-28 | Edit count: 2 -->

**Snapshot:** `phase1_transformed_transform_20261127T224625Z` (`outputs/etl/load/phase1_transformed_transform_20261127T224625Z/phase1_transformed_transform_20261127T224625Z__cohort_wallet.parquet`).
Unit: one wallet (`9,876,867` total = `9,849,850` unique union accounts + `27,017` hop-only wallets). Priority: **`illicit` > `suspicious` > `licit` > `unlabeled`**.

| Group | Rule | Frozen count | Share |
| --- | --- | ---: | ---: |
| `illicit` | TronScan blacklist, `label = 1`; blacklist wins at every hop | 17,046 | 0.17% |
| `suspicious` | `min(hop_level) ∈ 1..5` **and** not blacklisted (includes `27,017` hop-only wallets) | 3,959,525 | 40.09% |
| `licit` | Licit DB accounts (`6,614,681` raw) **minus** `illicit` (`3,387`) and `suspicious` (`1,430,799`) | 5,180,495 | 52.45% |
| `unlabeled` | Remaining universe (`illicit.accounts` not blacklisted, not in hops, not in licit) | 719,801 | 7.29% |

**Contamination & nesting rules (enforced in L2 `cohort_wallet`):**
- `8,306` blacklisted wallets appearing in hop 1–5 are promoted to `illicit`; `1,434,186` overlapping wallets are removed from `licit` (never relabeled `unlabeled`).
- `6 / 721` licit seeds are blacklisted (`is_contaminated_licit_seed` / `from_contaminated_licit_seed` flags retained for sensitivity audits).
- `min_hop_level` is nested strictly inside `suspicious` (`NULL` for all other classes). Wallet is the experimental unit; `primary_seed_address` (`16,371` illicit seeds) is the clustering unit. Never cross `wallet_class × hop`.
