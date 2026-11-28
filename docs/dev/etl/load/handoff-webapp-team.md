# Transformed Data Handoff Guide — Web Application Team
<!-- Created: 2026-11-28 | Last updated: 2026-11-28 | Edit count: 1 -->

- **Scope:** How the web application team consumes the frozen Phase-1 transformed Parquet snapshot, builds and indexes the managed PostgreSQL `wallet_serving` table, and maps `S1`–`S6` AML rules to UI/API responses.
- **Frozen snapshot:** `phase1_transformed_transform_20261127T224625Z` (`outputs/etl/load/phase1_transformed_transform_20261127T224625Z/`, `4.19 GB` total across 5 Parquet zstd files).
- **Related:** [`duckdb-and-reproducible-exports.md`](duckdb-and-reproducible-exports.md), [`handoff-ds-hypothesis-team.md`](handoff-ds-hypothesis-team.md), [`docs/dev/hypothesis_testing/general/all_hypothesis.md`](../../hypothesis_testing/general/all_hypothesis.md), [`docs/dev/software_concepts/02-layers-and-boundaries.md`](../../software_concepts/02-layers-and-boundaries.md).

> [!NOTE]
> `manifest.json` records `"partial": true` and per-table `"status": "unknown"` solely because the derived PostgreSQL `transform` schema has no `_etl_progress` ingestion tracking table. All 5 exported Parquet tables are **100% row-complete** and SHA-256 verified against the materialized local database.

---

## 1. Architecture Scenario: Why You Serve `wallet_serving` (Not Raw Transactions or DuckDB)

Suppose a user pastes a TRON address (`T...`) into the web UI to check its AML risk score under rules `S1`–`S6`.

- **Wrong path 1 — querying DuckDB from the web API:** DuckDB is an embedded single-writer OLAP library, not a multi-client server. Under concurrent HTTP requests it offers no connection pooling, role isolation, or high-concurrency point-lookup SLAs.
- **Wrong path 2 — loading all `26,189,701` rows of `clean_transactions.parquet` into the web database:** A live lookup does not need to scan 26M historical transfers per request; doing so bloats managed PostgreSQL storage (`~10 GB` with indexes) and turns a `< 5 ms` primary-key lookup into a multi-second aggregation.
- **Correct path:** Use DuckDB offline in a one-shot build job to join `wallet_features.parquet` + `cohort_wallet.parquet` (plus calibrated rule scores once DS finalizes weights), bulk `COPY` the resulting `9,876,867`-row wallet table into managed PostgreSQL `wallet_serving`, create `PRIMARY KEY (address)` and web-owned secondary indexes **after** bulk load, and serve point lookups via a read-only API role.

---

## 2. Snapshot Files to Consume (and Which to Skip)

Verify SHA-256 hashes from `manifest.json` before loading anything.

| Parquet file (`phase1_transformed_transform_20261127T224625Z__*.parquet`) | Rows | Size | Web App Action |
| --- | ---: | ---: | --- |
| `wallet_features.parquet` | `9,876,867` | `632 MB` | **Required (Primary).** Wallet-grain behavioral metrics, eligibility flags, and draft rule flags for `S1`–`S6`. |
| `cohort_wallet.parquet` | `9,876,867` | `261 MB` | **Required (Metadata join).** Provides `blacklisted_utc` and `has_blacklist_timestamp` (1:1 join on `wallet_address`). |
| `clean_wallet_hops.parquet` | `6,965,210` | `642 MB` | **Optional.** Load only if the UI renders seed-to-wallet hop lineage (`seed_address -> parent_address -> wallet_address`, `via_tx_hash`, `via_tx_status`). |
| `clean_transactions.parquet` | `26,189,701` | `2.65 GB` | **Do NOT load into web DB.** Analytical L1 archive used offline by DS (and offline batch job for `S3` 1.5h windowing). |
| `clean_tx_conflicts.parquet` | `3,194` | `386 KB` | **Do NOT load into web DB.** ETL cross-schema audit log only. |

### Handling `*_exact` Columns in `wallet_features.parquet`

`wallet_features.parquet` contains `73` columns: `58` typed core columns plus `15` `*_exact` `VARCHAR` shadow columns (emitted automatically by `load/main.py` whenever PostgreSQL stores an unconstrained `NUMERIC` so decimal text is preserved). **Ignore all `*_exact` columns when building `wallet_serving`** and select the typed `DOUBLE` / `BIGINT` / `BOOLEAN` columns.

---

## 3. Recommended `wallet_serving` Table & Column Contract

Keep `wallet_serving` narrow so the entire table (`~1.2–1.6 GB`) and its primary key (`~550 MB`) stay warm in PostgreSQL `shared_buffers`.

```sql
CREATE TABLE IF NOT EXISTS wallet_serving (
    address                    VARCHAR(40)  NOT NULL,
    wallet_class               VARCHAR(16)  NOT NULL,  -- illicit | suspicious | licit | unlabeled
    min_hop_level              SMALLINT,               -- 1..5 for suspicious ONLY; NULL otherwise
    primary_seed_address       VARCHAR(40),            -- nearest/lexicographically first illicit seed
    seed_count                 INTEGER      NOT NULL,
    blacklisted_utc            TIMESTAMPTZ,            -- non-NULL for 8,946 / 17,046 illicit wallets

    -- Headline behavioral summary for UI display
    total_tx_count             BIGINT       NOT NULL,
    usdt_tx_count              BIGINT       NOT NULL,
    trx_tx_count_excl_4444     BIGINT       NOT NULL,  -- excludes licit-only 4444.444444 spam artifact
    usdt_volume                DOUBLE PRECISION,
    tx_lifetime_days           DOUBLE PRECISION,

    -- Rule metrics (S1..S6)
    min_passthrough_sec_usdt   DOUBLE PRECISION,       -- S1 raw metric
    in_out_vol_ratio_usdt      DOUBLE PRECISION,       -- S1 volume ratio
    burst_ratio_usdt           DOUBLE PRECISION,       -- S2 (>=5 USDT events)
    fan_out_in_ratio_usdt      DOUBLE PRECISION,       -- S3 lifetime proxy
    amount_cv_usdt             DOUBLE PRECISION,       -- S3 lifetime proxy
    jaccard_index              DOUBLE PRECISION,       -- S4 gas co-occurrence
    cv_delta_t_all             DOUBLE PRECISION,       -- S6 inter-arrival CV

    -- Draft rule flags & final score (updated once DS calibrates thresholds/weights)
    s1_pass                    BOOLEAN,                -- h1_pass_15m = 1 AND in_out_vol_ratio_usdt >= 0.95
    s2_pass                    BOOLEAN,                -- h2_pass_ge5 = 1
    s3_pass                    BOOLEAN,                -- NULL until DS computes 1.5h window S3 batch
    s4_pass                    BOOLEAN,                -- h4_pass = 1
    s5_score                   DOUBLE PRECISION,       -- 10 * 2^(1-min_hop_level) for 1..4, 0 else (10 if illicit)
    s6_pass                    BOOLEAN,                -- h6_pass_all = 1
    risk_score                 DOUBLE PRECISION,       -- R(A) = min(10, sum w_i * S_i); NULL until calibrated

    snapshot_id                VARCHAR(80)  NOT NULL,
    updated_at                 TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

### Column Rules the UI Must Respect

1. **Never display `unlabeled` as `licit` or "safe".** Label the four cohorts distinctly: `illicit` (`17,046`), `suspicious` (`3,959,525`), `licit` (`5,180,495`), and `unlabeled` (`719,801` — unverified/provisional).
2. **Respect `NULL` eligibility:** A `NULL` in `jaccard_index`, `burst_ratio_usdt`, or `cv_delta_t_all` means **insufficient activity / ineligible**, **not zero risk**. Render `"N/A (insufficient transactions)"` rather than `0.0`.
3. **Use `trx_tx_count_excl_4444` and `trx_volume_excl_4444` for TRX UI metrics:** `1,017,778` licit TRX rows are upstream vanity address-poisoning spam converted at a hardcoded `0.225` rate (`4444.444444 TRX`); `826,853` licit wallets have no other TRX activity.
4. **Never expose `fee_trx` or schema-origin flags (`in_illicit_accounts`, `in_licit_accounts`) as risk indicators.** Those are crawl provenance flags, not on-chain behavior.

---

## 4. Indexing Strategy (Managed PostgreSQL)

Follow the project indexing policy (`AGENTS.md` — Indexing by consumer role): **bulk load first, build indexes after.** Maintaining a B-tree during a 9.88M-row load causes heavy WAL amplification and random page splits; creating it afterward runs a single sequential sort.

```sql
-- 1. Bulk-load into an unindexed staging table (wallet_serving_next) via COPY
-- 2. Build the primary key for O(log N) point lookups (~1–3 ms per wallet)
ALTER TABLE wallet_serving_next
    ADD CONSTRAINT wallet_serving_next_pkey PRIMARY KEY (address);

-- 3. Secondary indexes owned by the web app team (create ONLY what your endpoints query)
--    a) Filter by cohort or top-risk leaderboard
CREATE INDEX idx_wallet_serving_class_risk
    ON wallet_serving_next (wallet_class, risk_score DESC NULLS LAST);

--    b) Partial index for illicit/hop drilldowns (tiny footprint: ~17K illicit or ~3.96M suspicious)
CREATE INDEX idx_wallet_serving_seed
    ON wallet_serving_next (primary_seed_address)
    WHERE primary_seed_address IS NOT NULL;

-- 4. Refresh planner statistics before swapping live table
ANALYZE wallet_serving_next;
```

- **Optional hop lineage table (`wallet_hop_serving` from `clean_wallet_hops.parquet`):** If the UI shows hop paths for a looked-up address, bulk `COPY` `wallet_address, seed_address, parent_address, via_tx_hash, hop_level, direction, via_tx_status` and create `CREATE INDEX idx_hop_wallet ON wallet_hop_serving (wallet_address, hop_level);` **after** `COPY`. Remember `78.1%` (`5,441,596 / 6,965,210`) of hop edges are `via_tx_status = 'dust'` (1-SUN TRX) — surface `via_tx_status` as a badge in the graph viewer so users know whether a link was a real transfer or a 1-SUN dust spray.
- **Do NOT index `risk_score` or `wallet_class` before DS populates calibrated scores** if you want faster initial loads; add `idx_wallet_serving_class_risk` when `risk_score` is non-NULL.

---

## 5. Readiness Audit Against `S1`–`S6` Rules (What Is Ready vs. What Is Pending)

| Rule | Current Readiness in Snapshot | Ready Columns in `wallet_features` / `cohort_wallet` | Remaining Work Before Production |
| --- | --- | --- | --- |
| **S1** (Pass-Through Speed) | **Ready (minor assembly)** | `min_passthrough_sec_usdt`, `in_out_vol_ratio_usdt`, `h1_pass_15m`, `elig_h1` | Combine `h1_pass_15m = 1 AND in_out_vol_ratio_usdt >= 0.95` for joint rule trigger; DS may add 3-min/15-min tiered scoring or mean holding time. |
| **S2** (Temporal Burstiness) | **Ready** | `tx_lifetime_days`, `burst_ratio_usdt`, `h2_pass_ge5`, `elig_h2_ge5` | Wait for DS hypothesis testing (`H2`) to confirm/re-calibrate `7d` and `0.75` cutoffs. |
| **S3** (Spraying & Funneling) | **Gap (windowed rule)** | Lifetime proxies only: `in_degree_usdt`, `out_degree_usdt`, `fan_out_in_ratio_usdt`, `amount_cv_usdt`, `elig_h3` | DS must run a batch pass over `clean_transactions.parquet` for the **1.5-hour rolling window** degree (`>=7` / `>7`) + windowed `CV < 0.05` and ship `h3_pass`. |
| **S4** (TRON Gas Co-Occurrence) | **Ready** | `jaccard_index`, `h4_pass`, `elig_h4` | Wait for DS (`H4`) to verify `>= 0.50` cutoff (note: only `52 / 13,417` eligible illicit wallets pass at `0.50`; threshold/direction may change). |
| **S5** (Seed Proximity) | **Ready (1-line formula)** | `wallet_class`, `min_hop_level`, `seed_count`, `primary_seed_address` | Compute `s5_score = 10 * 2^(1 - min_hop_level)` for `min_hop_level BETWEEN 1 AND 4` (`0` for `5` or `NULL`; override to `10` for `wallet_class = 'illicit'`). |
| **S6** (Inter-Arrival Consistency) | **Ready** | `cv_delta_t_all`, `cv_delta_t_out`, `h6_pass_all`, `h6_pass_out`, `elig_h6_all` | Wait for DS (`H6`) to confirm/re-calibrate `< 0.15` cutoff (and decide all-direction vs OUT-only / session-split). |
| **Combined `R(A)` Risk Score** | **Pending DS Calibration** | Individual feature inputs ready | DS / ML team delivers calibrated thresholds + rule weights `w1..w6` (`R(A) = min(10, sum w_i * S_i)`). |
| **Unseen Live Wallets** | **Out of snapshot scope** | Snapshot covers `9,876,867` wallets up to `2026-11-23` | Lookup misses (`404` in `wallet_serving`) need either an "Address not in static snapshot" state or an on-demand TronGrid fetcher running the exact `S1`–`S6` scoring logic. |

---

## 6. Main Operational Steps (Snapshot to Production API)

1. **Verify integrity:** Check `sha256sum` on all downloaded Parquet files against `manifest.json` before touching PostgreSQL.
2. **Build `wallet_serving.csv` or stream via DuckDB:** Run a local DuckDB query joining `wallet_features.parquet` and `cohort_wallet.parquet` on `wallet_address`, dropping all `*_exact` columns, computing `s1_pass` and `s5_score`, and tagging `snapshot_id = 'phase1_transformed_transform_20261127T224625Z'`.
   ```sql
   -- DuckDB one-shot assembly into COPY-ready CSV (streaming, < 2 GB RAM)
   COPY (
     SELECT
       f.wallet_address AS address,
       f.wallet_class,
       f.min_hop_level,
       f.primary_seed_address,
       f.seed_count,
       c.blacklisted_utc,
       f.total_tx_count,
       f.usdt_tx_count,
       f.trx_tx_count_excl_4444,
       f.usdt_volume,
       f.tx_lifetime_days,
       f.min_passthrough_sec_usdt,
       f.in_out_vol_ratio_usdt,
       f.burst_ratio_usdt,
       f.fan_out_in_ratio_usdt,
       f.amount_cv_usdt,
       f.jaccard_index,
       f.cv_delta_t_all,
       CASE WHEN f.elig_h1 THEN (f.h1_pass_15m = 1 AND f.in_out_vol_ratio_usdt >= 0.95) END AS s1_pass,
       CASE WHEN f.elig_h2_ge5 THEN (f.h2_pass_ge5 = 1) END AS s2_pass,
       CAST(NULL AS BOOLEAN) AS s3_pass,
       CASE WHEN f.elig_h4 THEN (f.h4_pass = 1) END AS s4_pass,
       CASE
         WHEN f.wallet_class = 'illicit' THEN 10.0
         WHEN f.min_hop_level BETWEEN 1 AND 4 THEN 10.0 * pow(2.0, 1 - f.min_hop_level)
         ELSE 0.0
       END AS s5_score,
       CASE WHEN f.elig_h6_all THEN (f.h6_pass_all = 1) END AS s6_pass,
       CAST(NULL AS DOUBLE) AS risk_score,
       'phase1_transformed_transform_20261127T224625Z' AS snapshot_id
     FROM read_parquet('phase1_transformed_transform_20261127T224625Z__wallet_features.parquet') f
     JOIN read_parquet('phase1_transformed_transform_20261127T224625Z__cohort_wallet.parquet') c
       USING (wallet_address)
   ) TO 'wallet_serving_load.csv' (HEADER, FORMAT CSV);
   ```
3. **Bulk load into staging table (`wallet_serving_next`):** Use PostgreSQL `\copy wallet_serving_next FROM 'wallet_serving_load.csv' WITH (FORMAT csv, HEADER true)` with zero indexes present.
4. **Create PK, secondary indexes, and `ANALYZE`:** Run the index block in §4, verify row count equals `9,876,867`, and test `EXPLAIN ANALYZE SELECT * FROM wallet_serving_next WHERE address = '<sample>';` (must show `Index Scan using wallet_serving_next_pkey`, `< 5 ms`).
5. **Atomic table swap & read-only role:** Swap `wallet_serving` ↔ `wallet_serving_next` inside a single `BEGIN; ... COMMIT;` transaction, grant `SELECT` only to the web API user, and log `snapshot_id` in your API health/metadata endpoint.
