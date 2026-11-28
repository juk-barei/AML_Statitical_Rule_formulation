# Upstream Online DB Audit & Data Engineering Improvement Guide
<!-- Created: 2026-11-28 | Last updated: 2026-11-28 | Edit count: 1 -->

- **Audience:** Data Engineering (DE) team maintaining the online `illicit` and `licit` PostgreSQL crawlers and ingestion pipelines.
- **Evidence baseline:** Frozen Phase-1 raw snapshots `phase1_raw_illicit_20261123T043155Z` (`4,870,000` accounts, `17,046` blacklisted, `15,017,691` tx, `6,965,210` hops) and `phase1_raw_licit_20261123T043744Z` (`6,614,681` accounts, `721` seeds, `11,326,298` tx, `80,756` hops), audited via full-frame profiling (`outputs/etl/transform/profile/{raw,transformed}/`) and L1–L3 transformation (`phase1_transformed_transform_20261127T224625Z`).
- **Related:** [`process-model-and-connections.md`](process-model-and-connections.md), [`docs/dev/etl/transform/clean/l1-transaction-cleaning.md`](../transform/clean/l1-transaction-cleaning.md), [`docs/dev/etl/transform/cohort/l2-cohort-priority-and-nesting.md`](../transform/cohort/l2-cohort-priority-and-nesting.md), [`outputs/etl/transform/profile/transformed/raw_vs_transformed_stage_summary.csv`](../../../../outputs/etl/transform/profile/transformed/raw_vs_transformed_stage_summary.csv).

---

## Scenario: Why Fixing These Upstream Matters

During Phase-1 profiling and L1–L3 transformation, the analytics pipeline had to build defensive cleaning, deduplication, and anti-leakage filters around defects originating in the two online source databases. For example:

- A single `1990` timestamp bug in `transactions` inflates a wallet's `tx_lifetime_days` by ~36 years (`H2`).
- Ingesting `TRC-20 Approval` events (`2^256 / 1e6 ≈ 1.16e71`) into `transactions` blows up `SUM(amount)`, `mean`, and `stddev` by 60 orders of magnitude.
- Storing `fee_trx = 0.0` for 100% of `licit` rows while populating non-zero `fee_trx` in `illicit` (and injecting `1.02M` `4444.444444` TRX rows only into `licit`) leaks database origin directly into ML models.
- Following 1-SUN TRX spam dust (`0.000001 TRX`) during hop crawling causes `78.1%` of `wallet_hops` edges to be spam links and expands single seeds into clusters of up to `1.91M` wallets.

Fixing these issues directly in the online crawlers/schemas will shrink DB storage, cut crawl time, eliminate cross-schema conflicts, and improve Phase-2 data quality.

---

## 1. Priority 0 — Wrong / Corrupted Values Ingested (Fix Parsers & Ingestion)

| Issue | Affected Source Table / Column | Exact Scope (Phase-1 Raw) | Root Cause & Downstream Impact | Recommended DE Fix |
| --- | --- | --- | --- | --- |
| **`4444.444444` TRX conversion / spam artifact (`licit`-only)** | `licit.transactions.amount` (`token_symbol = 'TRX'`) | **`1,017,778`** rows (`11.22%` of licit TRX; **`0`** in illicit); `826,853` licit wallets have *no other* TRX activity; plus `7,314 / 8,852` above-supply licit TRX rows are multiples of `4444.4444` | Upstream licit ingestion/conversion quirk (hardcoded `0.225` factor / vanity spam). Pins licit TRX `p90`/`p95` at `4444.444444` and leaks schema origin in ML. | Fix raw SUN → TRX conversion (`raw_sun / 1e6`, no hardcoded multiplier) and verify against TronGrid raw payloads before inserting. |
| **TRC-20 `Approval` sentinels ingested as transfers** | `{illicit,licit}.transactions.amount` (`token_symbol = 'USDT'`) | **`10,613`** raw (`6,277` illicit + `4,336` licit; `10,268` deduped) with `amount >= 1e70` (`2^256 / 1e6`, `2^255 / 1e6`) | Smart-contract `Approval(owner, spender, MAX_UINT256)` logs ingested into the `transactions` transfer ledger. Destroys volume sums and variances. | Filter TRC-20 logs strictly to `event_name = 'Transfer'` (or topic `0xddf252ad...`); reject or separate `Approval` events. |
| **Physically impossible above-supply amounts** | `{illicit,licit}.transactions.amount` | **`10,824`** raw (`340` illicit USDT, `1,632` licit USDT, `8,852` licit TRX; `10,543` deduped) | Values exceed total circulating/genesis token supply (`> 94.25B` USDT or `> 100B` TRX) due to decimal scaling / parsing defects. | Enforce token decimal normalization (`1e6` for TRX and USDT) and add an ingestion validation/quarantine check (`amount <= supply_ceiling`). |
| **Pre-TRON-mainnet block timestamps** | `{illicit,licit}.transactions.block_timestamp` (`token_symbol = 'TRX'`) | **`18,115`** raw (`5,861` illicit in 1989–1990; `12,254` licit in 1970/1989/1990; `18,094` deduped; `0` USDT affected) | Epoch-unit bug (ms vs. seconds / integer overflow) producing timestamps prior to TRON mainnet launch (`2018-06-25T00:00:00Z`). Corrupts lifetime (`H2`) and inter-arrival (`H6`). | Validate `block_timestamp >= '2018-06-25T00:00:00Z' AND block_timestamp <= NOW() + INTERVAL '1 hour'` at ingestion; quarantine or re-fetch failing TRX blocks. |
| **Asymmetric `fee_trx` capture** | `{illicit,licit}.transactions.fee_trx` | `licit`: **`100%`** `0.0` across all `11,326,298` rows (`1` distinct value); `illicit`: `216` distinct values (max `2.267`, `2.76%` non-zero) | Licit crawler does not populate `fee_trx` while illicit crawler does. Any model using `fee_trx` trivially classifies by source DB instead of behavior. | Either parse actual transaction fee identically in both crawlers or drop `fee_trx` from both schemas. |
| **Cross-schema `tx_hash` field discordance** | `illicit.transactions` vs. `licit.transactions` | **`154,288`** shared `tx_hash` rows, of which **`3,194`** disagree (`2,867` `amount`, `313` `block_timestamp`, `85` `to_address`, `53` `from_address`, `0` `token_symbol`) | The illicit and licit crawlers parse the same on-chain transaction differently (primarily driven by the licit TRX conversion/timestamp bugs above). | Share one common transaction parser/normalizer library across both crawlers so identical `tx_hash` records are byte-for-byte identical. |
| **Zero-amount USDT transfers unflagged** | `{illicit,licit}.transactions.amount` (`token_symbol = 'USDT'`) | **`56,827`** raw (`42,891` illicit + `13,936` licit; `56,588` deduped; `0` negative) | Zero-value TRC-20 spoofing/probe transfers are mixed directly into `transactions`. Note: **do not silently delete** (`15.9%` of illicit vs `0.19%` of licit wallets have zero-USDT events — useful signal), but separate or flag explicitly. | Add an explicit `is_zero_amount BOOLEAN` (or `tx_type`) column so value-transfer queries don't accidentally include `0`-amount rows. |

---

## 2. Priority 1 — Rows & Columns No Longer Needed (Prune / Isolate Storage)

These columns and tables add gigabytes of storage and extraction overhead without providing analytical value:

| Target | Exact Scope | Why It Is Not Needed / Broken | Recommended DE Action |
| --- | --- | --- | --- |
| **`accounts.hex_address`** (both schemas) | `11,484,681` rows (`4.87M` illicit + `6.61M` licit) | Deterministic 1:1 hex encoding of Base58 `address`. Dropped automatically during every downstream export (`load/main.py` excludes `hex_address` by default). | **Drop column** (or compute on the fly if a crawler needs hex for TronGrid API calls). |
| **`illicit.pipeline_crawl_state`** | `3,891,887` rows (marked `partial` in mirror checks; never used in analysis) | Internal crawler checkpoint/resume table sitting in the same schema as analytical tables. | **Move to a separate internal/ops schema** (e.g., `ops.crawl_state`) so analytics/ETL schemas expose only data tables. |
| **`accounts.{first_seen_timestamp, last_seen_timestamp, created_date}`** | `illicit`: `96.12%` / `96.73%` / `96.12%` NULL; `licit`: **`100.00%`** / `98.89%` / `98.88%` NULL | Nearly empty across both databases; completely unusable for `tx_lifetime_days` (analytics had to recompute lifetime from `transactions`). | **Drop** unless the crawler backfills them reliably for `100%` of accounts from chain metadata. |
| **`licit.seed_wallets.{blacklisted_timestamp, blacklisted_utc, transaction_id}`** & **`licit.blacklisted_wallets`** | `100%` NULL across all `721` rows in `licit.seed_wallets`; `0` rows in `licit.blacklisted_wallets` | Schema copied from `illicit.blacklisted_wallets` with unused columns and an empty table. | **Drop unused blacklist columns** from `licit.seed_wallets` (keep `wallet_address, source_name, label, created_at`) and remove empty `licit.blacklisted_wallets`. |

---

## 3. Priority 2 — Crawl Noise, Referential Integrity & Label Contamination

| Issue | Exact Scope | Impact on Downstream Analytics | Recommended DE Fix |
| --- | --- | --- | --- |
| **1-SUN TRX dust driving hop expansion** | **`5,441,596 / 6,965,210` (`78.11%`)** of `illicit.wallet_hops` edges are `< 0.01 TRX` dust (`3,314,141` illicit + `2,248,914` licit TRX tx are exact `0.000001 TRX` = 1 SUN) | Address-poisoning / spam dust dominates the BFS graph, blowing single blacklisted seeds up to **`1,906,809`** hop wallets and wasting the vast majority of API/storage budget. | Do **not** expand BFS hops across 1-SUN dust (`amount <= 0.000001 TRX` or `< 0.01 TRX`), or add a `min_hop_edge_usd` / dust filter before enqueuing next-hop addresses. |
| **Orphaned hop references (`missing_tx` & hop-only wallets)** | **`106,637`** (`108,124` raw) `illicit.wallet_hops.via_tx_hash` values are missing from `transactions`; **`27,017`** hop 1–5 wallets are absent from `accounts` and have `0` transactions | Breaks foreign-key consistency between `wallet_hops`, `transactions`, and `accounts`; creates `27,017` wallets with zero behavioral data. | Insert the parent `accounts` row and the `via_tx_hash` `transactions` row atomically (or before) inserting into `wallet_hops`. |
| **Unlinked `illicit.accounts` rows (`unlabeled` residual)** | **`719,801`** rows in `illicit.accounts` (`7.29%` of total universe) are not in `blacklisted_wallets`, not in `wallet_hops` (`0..5`), and not in `licit.accounts` | Forces a 4th `unlabeled` cohort that cannot be used in clean supervised tests. | Track discovery provenance (`discovered_via` / `source_run`) or ensure every wallet inserted into `illicit.accounts` is linked to either a blacklist entry or a `wallet_hops` edge. |
| **Missing blacklist timestamps (`47.52%` NULL)** | **`8,100 / 17,046`** rows in `illicit.blacklisted_wallets` have NULL `blacklisted_timestamp`, `blacklisted_utc`, and `transaction_id` | Prevents temporal leakage checks (e.g., pre- vs. post-blacklist activity) on nearly half of the illicit arm. | Backfill `blacklisted_utc` / freeze tx hash from TronScan USDT `AddedBlackList` contract events whenever available. |
| **Contaminated `licit.seed_wallets` & cross-schema overlap** | **`6 / 721`** `licit.seed_wallets` are on the TronScan blacklist; **`3,387`** blacklisted + **`1,430,799`** suspicious wallets appear inside `licit.accounts` (`1,434,186` = `21.7%` of raw licit accounts had to be removed) | Wastes ~22% of licit crawl capacity re-crawling illicit/suspicious addresses and risks contaminating licit hops. | Filter seed candidates against `illicit.blacklisted_wallets` (and optionally hop-1 addresses) **before** starting the licit crawl. |

---

## 4. Priority 3 — Sampling-Frame Parity for Phase-2 Crawling

Profiling (`outputs/etl/transform/profile/raw/local_sampling_frame.csv` and `local_wallet_distributions.csv`) revealed a severe **activity-depth asymmetry** between the two source databases:

| Metric | `illicit` (`17,046` wallets) | `licit` (`5,180,495` clean wallets) | Consequence |
| --- | ---: | ---: | --- |
| Median `total_tx_count` | **`100`** | **`1`** | Most licit accounts are single-transaction stubs |
| Share with `>= 1` USDT transfer | **`90.5%`** | **`13.7%`** | `86.3%` of licit wallets have zero USDT activity |
| Eligible share for `H2` (`>= 5` USDT tx) | **`74.9%`** (`12,764`) | **`0.73%`** (`37,965`) | Huge sample drop when testing USDT rules |
| Eligible share for `H1` (USDT IN→OUT) | **`81.5%`** (`13,893`) | **`0.91%`** (`47,238`) | Same structural sparsity |
| Token mix (`USDT` / `TRX` rows) | `31.8%` / `68.2%` | `19.9%` / `80.1%` | Licit crawl heavily skewed toward TRX dust/stubs |

**Recommendation for Phase-2 licit crawling:** Instead of crawling millions of 1-transaction TRX-only leaf addresses, crawl **deeper transaction histories for active USDT-transacting licit wallets** (e.g., targeting wallets with `>= 5` clean USDT transfers across diverse counterparties — retail users, merchants, exchange deposit/withdrawal wallets, DeFi routers). Fewer wallets (`~200K–500K`) with full transaction depth will give much stronger statistical power for `H1`–`H6` and ML than `6.6M` 1-tx stubs.

---

## 5. Pre-Freeze Verification Queries for the DE Team

Before cutting the next online DB snapshot, run these checks against both `illicit` and `licit` schemas (target: `0` rows on all P0 checks):

```sql
-- 1. Zero TRC-20 Approval sentinels or above-supply amounts
SELECT token_symbol, COUNT(*) AS bad_amount_rows
FROM transactions
WHERE amount IS NULL
   OR amount < 0
   OR amount >= 1e70
   OR (token_symbol = 'USDT' AND amount > 94248192941.363764)
   OR (token_symbol = 'TRX'  AND amount > 100000000000)
GROUP BY token_symbol;

-- 2. Zero pre-mainnet or future timestamps
SELECT COUNT(*) AS bad_ts_rows
FROM transactions
WHERE block_timestamp < TIMESTAMPTZ '2018-06-25 00:00:00+00'
   OR block_timestamp > NOW() + INTERVAL '1 hour';

-- 3. Check for the 4444.444444 TRX conversion bug
SELECT COUNT(*) AS artifact_4444_rows
FROM transactions
WHERE token_symbol = 'TRX'
  AND ABS(amount - 4444.444444) < 1e-5;

-- 4. Check fee_trx population parity (should not be 100% zero in licit if populated in illicit)
SELECT COUNT(*) AS total_rows,
       COUNT(*) FILTER (WHERE fee_trx > 0) AS nonzero_fee_rows
FROM transactions;

-- 5. Check hop referential integrity (missing via_tx_hash and hop-only wallets)
SELECT COUNT(*) AS missing_via_tx
FROM wallet_hops h
WHERE h.hop_level >= 1
  AND NOT EXISTS (SELECT 1 FROM transactions t WHERE t.tx_hash = h.via_tx_hash);

-- 6. Check licit seed contamination against blacklist
SELECT COUNT(*) AS contaminated_licit_seeds
FROM licit.seed_wallets s
WHERE EXISTS (
    SELECT 1 FROM illicit.blacklisted_wallets b
    WHERE b.label = 1 AND b.wallet_address = s.wallet_address
);
```

---

## Evidence Index

All counts above are backed by reproducible CSVs and diagnostic plots in this repository:
- Cleaning & anomaly breakdown: [`outputs/etl/transform/profile/raw/local_pretransform_cleaning.csv`](../../../../outputs/etl/transform/profile/raw/local_pretransform_cleaning.csv) & [`outputs/etl/transform/profile/transformed/raw_vs_transformed_stage_summary.csv`](../../../../outputs/etl/transform/profile/transformed/raw_vs_transformed_stage_summary.csv)
- Column nullness & types: [`outputs/etl/transform/profile/raw/local_illicit_columns.csv`](../../../../outputs/etl/transform/profile/raw/local_illicit_columns.csv) & [`local_licit_columns.csv`](../../../../outputs/etl/transform/profile/raw/local_licit_columns.csv)
- Overlap, hop/seed fan-out & sampling frame: [`outputs/etl/transform/profile/raw/local_group_overlap.csv`](../../../../outputs/etl/transform/profile/raw/local_group_overlap.csv), [`local_hop_seed.csv`](../../../../outputs/etl/transform/profile/raw/local_hop_seed.csv), [`local_sampling_frame.csv`](../../../../outputs/etl/transform/profile/raw/local_sampling_frame.csv)
- Visual diagnostics: [`outputs/eda/profile/raw/02_column_missingness_dtypes.png`](../../../../outputs/eda/profile/raw/02_column_missingness_dtypes.png), [`03_quality_and_cleaning_anomalies.png`](../../../../outputs/eda/profile/raw/03_quality_and_cleaning_anomalies.png), [`04_tx_volume_by_year.png`](../../../../outputs/eda/profile/raw/04_tx_volume_by_year.png), [`06_cross_schema_overlap.png`](../../../../outputs/eda/profile/raw/06_cross_schema_overlap.png), [`07_hop_and_seed_structure.png`](../../../../outputs/eda/profile/raw/07_hop_and_seed_structure.png), and [`outputs/eda/profile/compare/12_raw_vs_transformed_shift.png`](../../../../outputs/eda/profile/compare/12_raw_vs_transformed_shift.png)
