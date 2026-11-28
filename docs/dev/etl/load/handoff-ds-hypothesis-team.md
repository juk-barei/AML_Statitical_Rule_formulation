# Transformed Data Handoff Guide — Hypothesis Testing & Data Science Team
<!-- Created: 2026-11-28 | Last updated: 2026-11-28 | Edit count: 1 -->

- **Scope:** Tables, columns, compute/indexing rules, `H1`–`H6` readiness, statistical inference constraints, and ML anti-leakage guardrails for working with the frozen Phase-1 transformed Parquet snapshot.
- **Frozen snapshot:** `phase1_transformed_transform_20261127T224625Z` (`outputs/etl/load/phase1_transformed_transform_20261127T224625Z/`, `4.19 GB` total across 5 Parquet zstd files).
- **Related:** [`handoff-webapp-team.md`](handoff-webapp-team.md), [`duckdb-and-reproducible-exports.md`](duckdb-and-reproducible-exports.md), [`docs/dev/hypothesis_testing/general/all_hypothesis.md`](../../hypothesis_testing/general/all_hypothesis.md), [`docs/context/glossary.md`](../../../context/glossary.md), [`docs/dev/software_concepts/10-sql-rules.md`](../../software_concepts/10-sql-rules.md).

> [!NOTE]
> `manifest.json` sets `"partial": true` and `"status": "unknown"` only because the derived PostgreSQL `transform` schema has no `_etl_progress` table. All 5 exported tables are **100% row-complete** and reconciled (`0` row diff between `cohort_wallet` and `wallet_features`, `110/116` exact raw-vs-transformed parity, `6/116` expected H1 deterministic tie-break improvement).

---

## 1. Snapshot Table Inventory & Grain

Verify SHA-256 checksums in `manifest.json` before running any notebook or script. Never mix counts from this snapshot with legacy `datasets/*.csv` or un-deduped L0 tables.

| Layer | Parquet file (`phase1_transformed_transform_20261127T224625Z__*.parquet`) | Grain | Rows | Size | Columns | Primary Purpose |
| --- | --- | --- | ---: | ---: | ---: | --- |
| **L1** | `clean_transactions.parquet` | 1 row per deduped `tx_hash` | `26,189,701` | `2.65 GB` | `19` | Full clean+flagged TRX/USDT ledger (`is_valid_for_features = TRUE` selects `26,094,208` baseline rows). Required for custom windowed features (`H1` mean lag, `H3` 1.5h window, `H6` session split). |
| **L1** | `clean_tx_conflicts.parquet` | 1 row per conflicting `tx_hash` | `3,194` | `386 KB` | `18` | Audit table of cross-schema field mismatches (`illicit` vs `licit`); `illicit` values win in `clean_transactions`. |
| **L1** | `clean_wallet_hops.parquet` | 1 row per `hop_id` | `6,965,210` | `642 MB` | `12` | Illicit seed crawl graph annotated with `via_tx_status` (`5,441,596` `dust`, `1,397,695` `ok`, `106,637` `missing_tx`, `10,146` `zero`, `5,569` `large_review`, `2,861` `sentinel`, `495` `null_hop0`, `211` `above_supply`). |
| **L2** | `cohort_wallet.parquet` | 1 row per `wallet_address` | `9,876,867` | `261 MB` | `15` | Authoritative 4-arm partition (`illicit=17,046`, `suspicious=3,959,525`, `licit=5,180,495`, `unlabeled=719,801`), seed cluster ID (`primary_seed_address`), contamination audit flags, and `blacklisted_utc`. |
| **L3** | `wallet_features.parquet` | 1 row per `wallet_address` | `9,876,867` | `632 MB` | `73` (`58` core + `15` `*_exact`) | Flat analysis & ML mart covering `H1`–`H6`, shared volume/count/degree metrics, stateless `log1p_*` responses, sensitivity variants (`_excl_4444`, `_nodust`), and explicit `elig_*` booleans. |

### `*_exact` Shadow Columns

`load/main.py` emits a `VARCHAR` `<col>_exact` companion whenever PostgreSQL stores an unconstrained `NUMERIC` (`15` columns in `wallet_features`, `1` in `clean_transactions`, `2` in `clean_tx_conflicts`). Use the typed `DOUBLE` columns for statistical tests and ML; ignore `*_exact` unless auditing arbitrary-precision rounding.

---

## 2. Compute & Indexing Policy (DuckDB/Parquet vs. PostgreSQL)

**Scenario:** A teammate loads `clean_transactions.parquet` (`26.2M` rows) into pandas with `pd.read_parquet(...)`, blowing out 32 GB RAM; another loads all 5 Parquet files into a local PostgreSQL DB and creates B-tree indexes before bulk insert, waiting 40 minutes unnecessarily.

Follow the role-based indexing and memory contract (`AGENTS.md`):

1. **Default path — DuckDB (or Polars) directly over Parquet (NO DB indexes needed):**
   - Parquet is columnar with per-row-group min/max zone maps. Project only the columns you need (`SELECT wallet_class, jaccard_index ...`) so DuckDB skips > 90% of bytes on disk.
   - Both `cohort_wallet.parquet` and `wallet_features.parquet` were exported **sorted by `(wallet_class, wallet_address)`**, so `WHERE wallet_class IN ('illicit', 'licit')` prunes entire `suspicious` and `unlabeled` row groups for free without any B-tree index.
   - Always bound DuckDB memory and enable disk spill when joining `clean_transactions.parquet` (`26.2M` rows):
     ```python
     import duckdb
     con = duckdb.connect()
     con.execute("SET memory_limit = '8GB'")
     con.execute("SET temp_directory = '/tmp/duckdb_spill'")
     con.execute("SET threads = 4")
     ```
2. **Optional path — Personal PostgreSQL analytical workspace:**
   - Only load into PostgreSQL if you are authoring multi-pass SQL views. Bulk `COPY` first into an unindexed schema, then create join indexes **after** bulk load:
     - `wallet_features` / `cohort_wallet`: `PRIMARY KEY (wallet_address)`
     - `clean_transactions`: `CREATE INDEX ON clean_transactions (from_address);` and `(to_address)` **only** if writing wallet-level SQL joins.
   - **Never** index, `INSERT`, `UPDATE`, `DELETE`, or run DDL on the L0 raw mirror (`illicit.*`, `licit.*`).
3. **Never pull full L1 or full 9.88M-row tables wholesale into pandas:** Aggregate, filter by `elig_*`, or perform wallet-level stratified sampling inside DuckDB SQL first, returning `<= 100k` rows (or exact census of `illicit` `17,046` + stratified sample of `licit`) into pandas/scipy/sklearn.

---

## 3. Column Map & Readiness Matrix for `H1`–`H6` and Statistical Learning

Phase-1 active hypothesis-testing scope in this repo is **`H2`, `H4`, `H6`** (teammates own **`H1`, `H3`, `H5`**). All `H1`–`H6` base data is included in this export.

| Workstream | Readiness | Primary Columns in `wallet_features.parquet` | Eligible `n` (`illicit` / `licit` / `suspicious` / `unlabeled`) | Remaining Work / Nuances |
| --- | --- | --- | --- | --- |
| **H1 (`S1` Pass-Through Speed)** | **Ready (nuance)** | `min_passthrough_sec_usdt`, `log1p_min_passthrough_sec_usdt`, `in_out_vol_ratio_usdt`, `h1_pass_15m`, `elig_h1` | `13,893` / `47,238` / `191,862` / `6,891` | `h1_pass_15m` checks `min_passthrough_sec_usdt <= 900` only. For full `S1` rule testing, apply joint gate `h1_pass_15m = 1 AND in_out_vol_ratio_usdt >= 0.95`. If testing **mean** holding time or a **3-min** tier, compute from `clean_transactions.parquet` (`WHERE is_valid_for_features AND token_symbol = 'USDT'`). |
| **H2 (`S2` Temporal Burstiness)** | **Ready** | `tx_lifetime_days`, `log1p_tx_lifetime_days`, `burst_ratio_usdt`, `burst_ratio_usdt_any`, `h2_pass_ge5`, `h2_pass_any_usdt`, `elig_h2_ge5`, `elig_h2_any` | `elig_h2_ge5`: `12,764` / `37,965` / `235,556` / `11,545`<br>`tx_lifetime_days`: `16,041` / `871,241` / `2,515,876` / `122,212` | `burst_ratio_usdt` is USDT-only (`>= 5` USDT events); `h2_pass_any_usdt` provides activity-floor sensitivity without the `>= 5` floor. All-token burst can be derived from `clean_transactions.parquet` if needed. |
| **H3 (`S3` Spraying & Funneling)** | **Partial (windowed gap)** | `in_degree_all`, `out_degree_all`, `in_degree_usdt`, `out_degree_usdt`, `fan_out_in_ratio_usdt`, `amount_cv_usdt`, `elig_h3` | `amount_cv_usdt` (`elig_h3`): `12,764` / `37,965` / `235,556` / `11,545`<br>`fan_out_in_ratio_usdt`: `15,426` / `708,582` / `1,064,765` / `231,534` | **Gap:** Lifetime degree & lifetime `amount_cv_usdt` are pre-computed, but `S3` specifies degree `>= 7` / `> 7` **within a 1.5-hour rolling window** with windowed `CV < 0.05`. Compute this directly in DuckDB over `clean_transactions.parquet` (`WHERE is_valid_for_features`) joined to `cohort_wallet.parquet`. |
| **H4 (`S4` TRON Gas Co-Occurrence)** | **Ready** | `jaccard_index`, `h4_pass`, `elig_h4` | `13,417` / `135,588` / `386,981` / `3,016` | Note baseline pass count at `0.50` is very low in illicit (`52 / 13,417 = 0.39%`) vs licit (`9,096 / 135,588 = 6.71%`). Run no-dust TRX sensitivity from `clean_transactions.parquet` (`AND NOT is_1sun_dust`) to test whether 1-SUN dust inflates or dilutes funder overlap. |
| **H5 (`S5` Seed Proximity)** | **Ready** | `min_hop_level`, `max_hop_level`, `seed_count`, `hop_row_count`, `primary_seed_address` + `clean_wallet_hops.parquet` | `min_hop_level`: `0` / `0` / `3,959,525` / `0` (strictly nested in `suspicious`) | Decay formula `10 * 2^(1-d)` (`1 <= d <= 4`) is 1 line over `min_hop_level`. Use `clean_wallet_hops.parquet` (`via_tx_status`, `via_tx_is_1sun_dust`) for mandatory dust-free (`1,397,695` `ok` edges) and `missing_tx` (`106,637` edges) sensitivity checks. |
| **H6 (`S6` Inter-Arrival Consistency)** | **Ready (nuance)** | `cv_delta_t_all`, `log1p_cv_delta_t_all`, `cv_delta_t_out`, `log1p_cv_delta_t_out`, `h6_pass_all`, `h6_pass_out`, `elig_h6_all`, `elig_h6_out` | `elig_h6_all`: `15,218` / `124,258` / `891,564` / `18,073`<br>`elig_h6_out`: `12,244` / `55,334` / `433,972` / `9,657` | Computed over full wallet history (no operational session split). Baseline `h6_pass_all` (`CV < 0.15`) is rare across all cohorts (`24` illicit, `611` licit); session-segmented CV can be computed from `clean_transactions.parquet` if needed. |
| **Statistical Learning (`STL`)** | **Ready** | All behavioral metrics + `log1p_*` + `elig_*` + `primary_seed_address` | `9,876,867` total (`17,046` illicit vs `5,180,495` licit clean binary contrast) | Fit all stateful preprocessing (`RobustScaler`, `StandardScaler`, imputation, Winsorization, class weighting) **strictly on train folds**. Enforce anti-leakage column drops in §4. |

---

## 4. Mandatory Statistical & Machine Learning Guardrails

### A. Inference & Experimental Design Rules
1. **Clean independent contrast:** Primary two-group hypothesis tests and binary classifiers compare **`illicit` (`17,046`) vs `licit` (`5,180,495`)**. Never pool `unlabeled` (`719,801`) into `licit`.
2. **`suspicious` is NOT an independent sample:** All `3,959,525` `suspicious` wallets were graph-crawled from blacklisted seeds. Non-parametric tests (Mann–Whitney, Kruskal–Wallis, Dunn) relax normality/homoscedasticity — **they do not fix dependence**. When analyzing `suspicious`, use seed-cluster bootstrap/permutation or mixed-effects models clustered by `primary_seed_address`, or report it strictly as a descriptive/nested arm.
3. **Hop nesting:** `min_hop_level` is defined **only** inside `suspicious` (`NULL` for `illicit`, `licit`, `unlabeled`). Never fit a crossed `wallet_class × hop` two-way ANOVA.
4. **Always report exact n-flow denominators and effect sizes:** Eligibility varies sharply across cohorts (e.g., `elig_h2_ge5` retains `74.9%` of `illicit` vs `0.73%` of `licit` because most licit accounts have `< 5` USDT events). Never silently impute `NULL` eligibility as `0` and never report p-values without effect size (rank-biserial `r`, Cliff's `delta`, Cohen's `d`, or Hodges–Lehmann shift) and exact `n_eligible`.
5. **Follow the 8-step workflow (`H2`, `H4`, `H6`):** response/factor/groups → `H0`/`Ha`/`α` → explore → assumptions → test → post-hoc → effect size → conclusion.

### B. Required Data-Quality Sensitivity Checks
- **`4444.444444` TRX vanity-spam artifact (`licit`-only):** `1,017,778` licit TRX rows (`0` illicit) come from an upstream crawler `0.225` conversion quirk (`826,853` licit wallets have no other TRX activity). Always use `trx_tx_count_excl_4444` and `trx_volume_excl_4444` in primary models (or report baseline vs `excl_4444` sensitivity) — raw `trx_volume` leaks schema origin!
- **1-SUN TRX dust (`<= 1e-6 TRX`):** `14,636,054` deduped TRX rows and `78.1%` of `clean_wallet_hops` edges are 1-SUN dust. Pair baseline runs with `trx_tx_count_nodust` / `WHERE NOT is_1sun_dust` sensitivity.
- **`fee_trx` is banned from modeling:** `100%` `0.0` in `licit` vs `216` distinct values in `illicit`. It is omitted from `wallet_features` intentionally; do not re-join it from `clean_transactions.parquet`.

### C. ML Feature Anti-Leakage Checklist (Drop Before Fitting!)
When training supervised models predicting `wallet_class` (`illicit` vs `licit`, or multiclass), **MUST exclude** these provenance/target-adjacent columns from `X`:

| Column(s) to Exclude from `X` | Why Including It Causes Leakage |
| --- | --- |
| `in_accounts_table`, `in_illicit_accounts`, `in_licit_accounts`, `is_licit_seed` | Directly encodes which crawler database discovered the wallet (near-100% trivial shortcut). |
| `is_contaminated_licit_seed`, `from_contaminated_licit_seed`, `has_blacklist_timestamp`, `blacklisted_utc` | Derived from the blacklist label itself. |
| `min_hop_level`, `max_hop_level`, `seed_count`, `hop_row_count`, `primary_seed_address` | Graph-crawl metadata only populated for `illicit` / `suspicious` (target leakage in behavioral models; keep `primary_seed_address` ONLY as the `groups=` vector for `GroupKFold` / `StratifiedGroupKFold`). |
| `trx_tx_count`, `trx_volume` (prefer `*_excl_4444`) | Unfiltered TRX includes the `1,017,778` `licit`-only `4444.444444` artifact. |
| `*_exact` (`15` VARCHAR columns) | String shadow duplicates of `DOUBLE` features. |

### D. Stateless vs. Stateful Scaling Split
- **Done in ETL (`wallet_features.parquet`):** Stateless monotonic transforms only (`log1p_tx_lifetime_days`, `log1p_cv_delta_t_all`, `log1p_cv_delta_t_out`, `log1p_usdt_volume`, `log1p_trx_volume`, `log1p_total_tx_count`, `log1p_min_passthrough_sec_usdt`).
- **Done in `src/scripts/statistical_learning/` (Train Folds Only):** `RobustScaler`, `StandardScaler`, median/indicator imputation, quantile Winsorization, SMOTE/class weights, and threshold/weight optimization (`w1..w6`).

---

## 5. Main Workflow Steps & Starter Queries

1. **Inspect snapshot provenance & verify counts:**
   ```python
   import json, duckdb
   manifest = json.loads(open("outputs/etl/load/phase1_transformed_transform_20261127T224625Z/manifest.json").read())
   print(manifest["snapshot"], {k: v["rows"] for k, v in manifest["tables"].items()})
   ```
2. **Pull an eligible hypothesis slice directly from `wallet_features.parquet` (example: `H2` `illicit` vs `licit`):**
   ```python
   con = duckdb.connect()
   con.execute("SET memory_limit = '8GB'; SET temp_directory = '/tmp/duckdb_spill';")
   df_h2 = con.execute("""
       SELECT
           wallet_address,
           wallet_class,
           tx_lifetime_days,
           log1p_tx_lifetime_days,
           burst_ratio_usdt,
           h2_pass_ge5
       FROM read_parquet('outputs/etl/load/phase1_transformed_transform_20261127T224625Z/*__wallet_features.parquet')
       WHERE wallet_class IN ('illicit', 'licit')
         AND elig_h2_ge5 = TRUE
   """).df()
   # Returns 50,729 rows (12,764 illicit + 37,965 licit) in < 1s
   ```
3. **Compute custom windowed features (`H3` 1.5-hour window, `H1` mean lag, `H6` session split) from `clean_transactions.parquet`:**
   ```sql
   -- Always gate on is_valid_for_features = TRUE (and add NOT is_1sun_dust / NOT is_trx_4444_artifact for sensitivity)
   SELECT
       t.from_address AS wallet_address,
       t.block_timestamp,
       t.to_address,
       t.amount
   FROM read_parquet('outputs/etl/load/phase1_transformed_transform_20261127T224625Z/*__clean_transactions.parquet') t
   WHERE t.is_valid_for_features = TRUE
     AND t.token_symbol = 'USDT';
   ```
4. **Run the 8-step hypothesis test and record outputs:** Write reproducible scripts under `src/scripts/hypothesis_testing/{shared,h2,h4,h6}/`, save tables/plots under `outputs/hypothesis_testing/{shared,h2,h4,h6}/`, and update `tasks/hypothesis_testing/{H2,H4,H6}.md`.
5. **Calibrate rule thresholds & weights (`S1`–`S6` → `R(A)`) for Web App handoff:** Export calibrated cutoffs, `h3_pass` (1.5h window), rule weights `w1..w6`, and out-of-fold evaluation metrics (PR-AUC, precision@K, F1 by cohort) under `outputs/statistical_learning/` so the Web App team can populate `wallet_serving.risk_score`.
