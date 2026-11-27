# Transformation Phase Recommendations & Issue-by-Issue Remediation
<!-- Created: 2026-11-27 | Last updated: 2026-11-27 | Edit count: 1 -->

## User Prompt

> I have updated the code to be ready for transformation, and you recommend what you will do for that phase. For partial data or data that has issues based on each issue what will you do. Reference to the outputs/ files related.

---

## Response / Recommendations

### Baseline Snapshot & Scope

All recommendations below are grounded in the frozen Phase 1 raw snapshots (`partial: false`) and full-frame `raw/` profile outputs:

- **Raw Parquet snapshots:** `phase1_raw_illicit_20261123T043155Z` (`outputs/etl/load/phase1_raw_illicit_20261123T043155Z/manifest.json`: `4,870,000` accounts, `17,046` blacklisted, `15,017,691` tx, `6,965,210` hops) + `phase1_raw_licit_20261123T043744Z` (`outputs/etl/load/phase1_raw_licit_20261123T043744Z/manifest.json`: `6,614,681` accounts, `0` blacklisted, `721` seeds, `11,326,298` tx, `80,756` hops).
- **Reconciled full wallet universe:** **`9,876,867`** wallets = `9,849,850` deduplicated accounts union + `27,017` hop-only wallets (`outputs/etl/transform/profile/raw/local_sampling_frame.csv:2-13`).
- **Transform architecture:** Materialize **L1 (`clean/`) → L2 (`cohort/`) → L3 (`features/`)** for **all `H1`–`H6`** inside a dedicated PostgreSQL `transform` schema (leaving L0 `illicit.*`/`licit.*` strictly read-only and unindexed), export via `load/main.py --stage transformed`, and audit against `outputs/etl/transform/profile/raw/` using `profile_stage.py --stage transformed`.

---

### Issue-by-Issue Remediation Plan (Partial Data & Quality Anomalies)

#### 1. Partial, Stale, or Asymmetric Data

| Issue | Evidence in `outputs/` | Recommended Transform Action |
| --- | --- | --- |
| **Stale/partial `illicit.pipeline_crawl_state`** (`3,891,887` source vs `3,891,889` local; `is_partial=True`) | `outputs/etl/transform/profile/raw/local_illicit_coverage.csv:4`, `local_illicit_db_overview.csv:4` | **Exclude completely** from L1–L3 and exports (already excluded in raw manifests). Internal crawler state only; never join on it. |
| **96%–100% NULL account timestamps** (`first_seen_timestamp`: 96.12% NULL in illicit, **100%** NULL in licit; `last_seen_timestamp` / `created_date`: 96.1%–98.9% NULL) | `outputs/etl/transform/profile/raw/local_illicit_columns.csv:3-5`, `local_licit_columns.csv:3-5` | **Do not use or impute** account timestamps for H2 or any temporal feature. Compute `tx_lifetime_days` strictly from clean transaction spans (`MAX(block_timestamp) - MIN(block_timestamp)` with `>= 2` valid non-zero events) in L3. |
| **47.52% NULL blacklist timestamps** (`8,100 / 17,046` missing `blacklisted_timestamp`, `blacklisted_utc`, `transaction_id`; `100%` NULL in `licit.seed_wallets`) | `outputs/etl/transform/profile/raw/local_illicit_columns.csv:8-10`, `local_licit_columns.csv:8-10` | Determine `illicit` membership solely from `wallet_address` (`label = 1`, 0% NULL). **Never filter on `blacklisted_utc IS NOT NULL`** (would silently drop 47.5% of illicit ground truth). Keep `blacklisted_utc` nullable + `has_blacklist_timestamp` flag in L2. |
| **Asymmetric `fee_trx` capture** (licit is **100% `0.0`** across `11,326,298` rows; illicit has 216 distinct values, max `2.267`) | `outputs/etl/transform/profile/raw/local_sampling_frame.csv:22-24,33-35`, `local_licit_columns.csv:23` | Preserve `fee_trx` in L1 `clean_transactions` for teammate H1/H3 handoff compatibility, **but ban `fee_trx` from L3 features / hypothesis tests / ML** (non-zero `fee_trx` leaks schema origin). Document explicitly in `DATA_DICTIONARY.md`. |
| **Hop-only wallets absent from `accounts`** (`27,017` hop 1–5 wallets; `0` transactions, `0` blacklisted) & **missing hop `via_tx_hash`** (`108,124` rows, 1.55%; plus `495` NULL `via_tx_hash` / `479` NULL `parent_address` at hop-0) | `outputs/etl/transform/profile/raw/local_pretransform_cleaning.csv:40,85-87`, `local_sampling_frame.csv:2-4`, `local_illicit_columns.csv:28-29` | Include all `27,017` hop-only wallets in L2 `cohort_wallet` as `suspicious` with `in_accounts_table = FALSE` (resolving the `692,784` vs `719,801` `unlabeled` discrepancy between `local_nflow.csv:7` and `local_sampling_frame.csv:8`). Keep them in L3 with `total_tx_count = 0` and `NULL` tx features. For H5 `wallet_hops`, keep rows and tag `via_tx_status` (`ok`/`dust`/`zero`/`missing_tx`/`null_hop0`) instead of dropping. |
| **Sampling-frame & activity asymmetry** (`licit` p10 ts `2023-04-28`, 80.1% TRX, median `total_tx_count = 1`, 86.3% have 0 USDT vs `illicit` p10 `2025-10-18`, median `100` tx, 90.5% USDT) | `outputs/etl/transform/profile/raw/local_sampling_frame.csv:14-35`, `local_wallet_distributions.csv:2-5,10-13` | **Do not prune inactive wallets in ETL.** Store provenance flags (`in_illicit_accounts`, `in_licit_accounts`, `is_licit_seed`) in L2 and activity counts + explicit boolean eligibility columns (`elig_h1`..`elig_h6`) in L3 so downstream sampling can stratify by activity band and report exact `wallet_class × filter` n-flow. |

#### 2. L1 Transaction Cleaning Issues (`src/scripts/etl/transform/clean/`)

All L1 rules are **non-destructive** (row flags added, applied identically to both arms) and reconciled via an L1 n-flow CSV in `outputs/etl/transform/clean/`:

| Issue | Evidence in `outputs/` | Recommended L1 Action |
| --- | --- | --- |
| **Cross-schema `tx_hash` overlap & field conflicts** (`154,288` shared hashes; conflicts on `2,867` amount, `313` ts, `85` to, `53` from, `0` token) | `outputs/etl/transform/profile/raw/local_pretransform_cleaning.csv:2-10` | Deduplicate `26,343,989 → 26,189,701` via deterministic `ROW_NUMBER() OVER (PARTITION BY tx_hash ORDER BY valid_amount, valid_ts, src_rank)` (illicit `src_rank=1` wins ties because licit has `fee_trx=0` and TRX corruption). Flag `has_cross_schema_conflict` and emit a conflict audit summary under `outputs/etl/transform/clean/`. |
| **Physically impossible amounts** (`sentinel` >= `1e70` / `2^256/1e6`: `6,277` illicit + `4,336` licit USDT = `10,613`; `above_supply`: `340` illicit USDT + `1,632` licit USDT + `8,852` licit TRX = `10,824`) | `outputs/etl/transform/profile/raw/local_pretransform_cleaning.csv:14,18,20,24,28,37` | Flag `amount_flag IN ('sentinel', 'above_supply')` (checking exact `NUMERIC` / `amount_exact` strings for `2^256/1e6` and `2^255/1e6`, plus ceilings `94,248,192,941.363764` USDT and `100B` TRX). Keep flagged in L1; **exclude from all L3 features** (`is_feature_eligible = FALSE`). |
| **Zero-amount transfers** (`42,891` illicit USDT + `13,936` licit USDT = `56,827`; `0` negative; `10,146` hop rows on zero tx) | `outputs/etl/transform/profile/raw/local_quality.csv:7,22`, `local_pretransform_cleaning.csv:19,29,41` | Flag `amount_flag = 'zero'`. Exclude from volume, lifetime, degree, burst, and inter-arrival CV, **but retain as a dedicated L3 feature `zero_tx_count`** (15.9% of illicit wallets vs 0.19% of licit have >=1 zero-USDT tx in `local_wallet_distributions.csv:6-9`). |
| **Pre-mainnet timestamps** (`5,861` illicit TRX in 1989–1990 + `12,254` licit TRX in 1970/1989/1990 = `18,115` rows before `2018-06-25T00:00:00Z`) | `outputs/etl/transform/profile/raw/local_quality.csv:11,26`, `local_pretransform_cleaning.csv:46,62-65,82-84` | Flag `timestamp_flag = 'pre_mainnet'` (`< 2018-06-25Z`, plus `'future'` guard). Keep flagged in L1; **exclude from all L3 features** (a single 1990 row corrupts H2 `tx_lifetime_days` by ~36 years and destroys H1/H6 timing). |
| **TRX micro-dust (`< 0.01`)** (`9,120,455` illicit TRX = 89.0%, incl. `3,314,141` exact 1-SUN; `5,612,141` licit TRX = 61.9%, incl. `2,248,914` exact 1-SUN; **`78.11%` of hop edges** use dust) & USDT dust (`38,666` rows) | `outputs/etl/transform/profile/raw/local_pretransform_cleaning.csv:11,15,21,25,30-35,38` | Flag `amount_flag = 'dust'` + `is_1sun_dust`. **Keep in baseline L3** (dropping TRX dust removes 78.1% of graph edges and most TRX funding), **and add no-dust sensitivity columns** (`trx_tx_count_nodust`, `tx_lifetime_days_nodust` or sensitivity audit) so H2/H4/H6 can verify robustness to 1-SUN spam. |
| **Licit-only `4444.444444` TRX repeated artifact** (`1,017,778` licit TRX rows = **11.22% of licit TRX**, `0` in illicit; visibly pins licit `trx_volume` p90 & p95 at `4444.444444`) | `outputs/etl/transform/profile/raw/local_pretransform_cleaning.csv:32,36`, `local_wallet_distributions.csv:44` | **Inspect origin before finalizing exclusion** (single spammer/contract vs crawler artifact), add symmetric boolean flag `is_trx_4444_artifact` in L1, and decide whether to exclude it from `trx_volume` / `trx_tx_count` (or report both). |
| **`large_review` transfers** (`1e6 < amount <= supply`: `44,539` raw rows across TRX+USDT) | `outputs/etl/transform/profile/raw/local_pretransform_cleaning.csv:12,16,22,26` | Flag `amount_flag = 'large_review'`; **retain in baseline L3** (real exchange/laundering transfers), matching `docs/context/friend_cleaning_samples.md`. Drop `hex_address` from all L1–L3 tables. |

#### 3. L2 Cohort & Graph Structure Issues (`src/scripts/etl/transform/cohort/`)

| Issue | Evidence in `outputs/` | Recommended L2 Action |
| --- | --- | --- |
| **Cross-cohort contamination** (`3,387` blacklisted in `licit.accounts`; `1,430,799` suspicious in `licit.accounts` → `1,434,186` removed from licit; `8,306` blacklisted inside hop 1–5; **`6 / 721` licit seeds are blacklisted**) | `outputs/etl/transform/profile/raw/local_group_overlap.csv:2-4`, `local_nflow.csv:4-6` | Enforce strict priority using `NOT EXISTS` (never `NOT IN` per `10-sql-rules.md`): **`illicit` (`17,046`) > `suspicious` (`3,959,525`) > `licit` (`5,180,495`) > `unlabeled` (`719,801`)**. Flag `is_contaminated_licit_seed` (and optionally `from_contaminated_licit_seed` via `licit.wallet_hops`) for sensitivity checks. |
| **Multi-hop & multi-seed multiplicity / extreme seed cluster skew** (`1,211,441` multi-hop wallets; `1,249,966` multi-seed wallets; `16,371` illicit seeds with cluster sizes `1` to **`1,906,809`**, median `72`) | `outputs/etl/transform/profile/raw/local_hop_seed.csv:2-6`, `local_sampling_frame.csv:36-63` | Pre-aggregate `illicit.wallet_hops` before joining (zero fan-out). Emit 1 row/wallet with `min_hop_level` (**nested inside `suspicious` only; `NULL` for all other classes**), `max_hop_level`, `seed_count`, `hop_row_count`, and deterministic `primary_seed_address` (at `min_hop_level`, tie-broken by earliest `discovered_at`, then `seed_address`) for cluster-aware inference. |

#### 4. L3 Feature Eligibility, Sparsity & Skewness Issues (`src/scripts/etl/transform/features/`)

| Issue | Evidence in `outputs/` | Recommended L3 Action |
| --- | --- | --- |
| **Low eligibility & activity-floor reversal** (licit eligible share: H1 `0.91%`, H2 `>=5 USDT` `0.73%`, H4 `2.62%`, H6 `2.40%` all / `1.07%` OUT; H2 pass rates jump dramatically without `>=5` gate; rare passes: H4 `52` illicit, H6 `24` all / `31` OUT illicit) | `outputs/etl/transform/profile/raw/local_feature_nflow.csv:46-117`, `local_wallet_distributions.csv:54-117` | Keep all `9,876,867` wallets with `NULL` for ineligible features (never fill `0` or drop rows). Compute **all `H1`–`H6` features** plus both audited sensitivity variants (`h2_pass_ge5` & `h2_pass_any_usdt`; `cv_delta_t_all`/`h6_pass_all` & `cv_delta_t_out`/`h6_pass_out`) and emit `outputs/etl/transform/features/feature_nflow.csv`. |
| **Extreme right-skew & heavy tails** (skewness `59`–`906` on counts/degrees/volumes; `log1p` brings `tx_lifetime_days` skew from `2.25–5.50` to `-0.72..+0.25`) | `outputs/etl/transform/profile/raw/local_wallet_distributions.csv:2-117` | Include **stateless `log1p_*` transforms only** in L3 (`log1p_tx_lifetime_days`, `log1p_cv_delta_t_all`, `log1p_cv_delta_t_out`, `log1p_usdt_volume`, `log1p_trx_volume`, `log1p_total_tx_count`, `log1p_min_passthrough_sec_usdt`). Keep **all stateful scaling** (`RobustScaler`, `StandardScaler`, Winsorization) strictly out of ETL (`statistical_learning/` train folds only). |
| **Unindexed PostgreSQL spill risk** (`cohort_priority_join` took `29.1s` and spilled `104,349` temp blocks on unindexed L0) | `outputs/etl/transform/profile/raw/query_benchmarks.csv:7` | Run with modest session limits (`work_mem = '128MB'`, `maintenance_work_mem = '512MB'`). Create join-key indexes on materialized `transform.*` tables **after** bulk `CREATE TABLE AS` (never on L0), and export L2/L3 Parquet sorted by `wallet_class` for free row-group pruning. |

---

### Recommended Phase Plan (Per `AGENTS.md` & `docs/dev/github_convention.md`)

1. **Phase 1 — L1 Cleaning (`clean/`)**
   - **Branch / Commit:** `layhok/etl-clean` → `[FEAT-clean]: implement L1 transaction dedupe, amount/timestamp flags, and n-flow`
   - **Scope / Paths:** `src/scripts/etl/transform/clean/` (SQL + runner + pure-rule & fixture tests in `clean/tests/`), `outputs/etl/transform/clean/` (cleaning n-flow & conflict summary), `docs/dev/etl/transform/clean/` note, `tasks/etl/`.
   - **Verification:** Pure-rule unit tests (`classify_amount_flag`, `classify_timestamp_flag`), synthetic PostgreSQL fixture test (overlap conflict tie-break, `sentinel`, `above_supply`, `zero`, `pre_mainnet`, `4444.444444`, `dust`), and full-frame n-flow check matching `26,189,701` unique `tx_hash`.

2. **Phase 2 — L2 Cohort Builder (`cohort/`)**
   - **Branch / Commit:** `layhok/etl-cohort` → `[FEAT-cohort]: build materialized L2 cohort_wallet with priority, hop nesting, and seed multiplicity`
   - **Scope / Paths:** `src/scripts/etl/transform/cohort/` (SQL + runner + `cohort/tests/`), `outputs/etl/transform/cohort/` (`cohort_nflow.csv`), `docs/dev/etl/transform/cohort/` note, `tasks/etl/`.
   - **Verification:** Pure classification tests, nullable anti-join & hop fan-out fixture tests (`10-sql-rules.md` Rule 12), and exact partition assertion (`17,046 + 3,959,525 + 5,180,495 + 719,801 = 9,876,867`, `min_hop_level IS NULL` outside `suspicious`).

3. **Phase 3 — L3 Wallet Features (`features/`)**
   - **Branch / Commit:** `layhok/etl-features` → `[FEAT-features]: build L3 wallet_features for H1-H6 with eligibility gates and stateless log1p`
   - **Scope / Paths:** `src/scripts/etl/transform/features/` (SQL + runner + `features/tests/`), `outputs/etl/transform/features/` (`feature_nflow.csv`), `docs/dev/etl/transform/features/` note, `tasks/etl/`.
   - **Verification:** Pure formula + synthetic fixture tests (H1–H6 edge cases, zero-tx wallets, tie timestamps with explicit `ROWS` frames, zero-denominator guards), `COUNT(*) = 9,876,867` assertion, and full n-flow reconciliation against `raw/local_feature_nflow.csv`.

4. **Phase 4 — Transformed Export & Stage Audit (`load/` + `profile/`)**
   - **Branch / Commit:** `layhok/etl-load` (or split `load` / `profile` if code changes are needed) → `[FEAT-load]: export phase1_transformed snapshot and verify raw-vs-transformed profile`
   - **Scope / Paths:** Run `load/main.py --schema transform --stage transformed --tables all` → `outputs/etl/load/phase1_transformed_transform_<UTC>/`, then `profile_stage.py --stage transformed` → `outputs/etl/transform/profile/transformed/`, plus update stale counts in `docs/context/` (`cohort_contract.md`, `sampling_evaluation.md`, `glossary.md`).
   - **Verification:** Manifest SHA-256 & row-count match, DuckDB `transformed/` profile matches `raw/` reconciled metrics, and documented `DROP SCHEMA transform CASCADE;` cleanup procedure ready for project end.

---

### Decisions Needed Before Starting Phase 1

1. **Approve the 4-phase plan above** (starting on a new branch `layhok/etl-clean` for Phase 1)?
2. **How should we treat the `1,017,778` licit `4444.444444` TRX rows in L1?** Flag-and-inspect first (keep in baseline TRX volume + add sensitivity column), or flag-and-exclude from TRX volume immediately?
3. **Should we keep `dust` (`< 0.01`) inside baseline TRX features + add no-dust sensitivity columns** (recommended, since 78.1% of `wallet_hops` use dust), or exclude 1-SUN TRX from baseline H2/H4/H6?
4. **Confirm H2 burst token scope** (`docs/context/feature_audit.md`): keep USDT-only `burst_ratio_usdt` as primary (matching `raw/` profile) and optionally add `burst_ratio_all_tokens` alongside it?
