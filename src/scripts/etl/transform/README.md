# `etl/transform` — SQL and feature builders
<!-- Last updated: 2026-11-27 | Edit count: 2 -->

SQL that turns the raw mirror into analysable tables: cleaning, cohort priority, eligibility, and per-wallet features for **all hypotheses (`H1`–`H6`)**. Scope narrows to `H2` / `H4` / `H6` only **after** the transformed database is exported to teammates (for `H1` / `H3` / `H5` and the web application). One `.sql` file per rule set, with a short module wrapper only when a script needs to run it.

Profiling is the first step in this stage, not a separate ETL stage. `profile/` reads the source, mirror, and frozen raw Parquet snapshots, writes `outputs/etl/transform/profile/`, and EDA plots those results. Transformation rules are then written from the profile's findings. See [`profile/README.md`](profile/README.md).

Outputs mirror the sections under `outputs/etl/transform/{profile,clean,cohort,features}/`; tests for each section live in `<section>/tests/`.

Cohort definitions, hop nesting, and inference constraints are in [`AGENTS.md`](../../../../AGENTS.md). This folder implements them; it does not redefine them.

## Sections (Hedgehog layout, L1–L3)

| Folder | Layer | Owns |
| --- | --- | --- |
| `profile/` | Read-only (L0–L3) | Schema, quality, anomaly, overlap, benchmarks, and stage-to-stage comparisons (`raw → clean → cohort → features`). |
| `clean/` | **L1** | Cross-schema union, `tx_hash` deduplication, type unification, dropping `hex_address`, and non-destructive row flags (`amount_flag`, `timestamp_flag`) applied identically to every arm. |
| `cohort/` | **L2** | Materialized 1-row-per-wallet `cohort_wallet` with priority `illicit` (blacklist wins at every hop) > `suspicious` (hop 1–5, not blacklisted) > `licit` > `unlabeled`, nested `min_hop_level`, and seed multiplicity. |
| `features/` | **L3** | Wallet-grain SQL aggregations, **all `H1`–`H6` feature formulas**, stated eligibility gates (never silently dropping undefined rows), and stateless monotonic transforms (`log1p`). |

**Scaling boundary:** Stateless transforms (`log1p`, ratios) belong in `features/` (L3). Stateful scaling (Z-score standardization, min-max normalization, `RobustScaler`, percentile Winsorization) **must not** live here — fit it exclusively on training splits inside `src/scripts/statistical_learning/` to prevent train/test leakage.

Every transform reports the `wallet_class × filter` n-flow so the number of rows removed is visible at each step.

## Rules

- **SQL computes, pandas displays.** Aggregate, join, deduplicate, and window in SQL. Never load `accounts`, `transactions`, or `wallet_hops` wholesale into pandas; return wallet-level rows or a bounded sample.
- **One rule, one place.** A clean applied to one arm must be applied identically to the others; keep it in transform SQL (as a CTE/view, or materialized view/table in a dedicated transform schema with documented `DROP SCHEMA` cleanup at project end) rather than copying conditions between queries.
- **No ad-hoc DDL or DML from notebooks.** L0 mirror schemas (`illicit.*`, `licit.*`) are strictly read-only outside `extract/main.py`. Persistent derived tables live in a dedicated transform schema written only by ETL transform scripts — never created by hand in a notebook.
- **Freeze what you export.** A transform feeding a handoff snapshot is recorded in `outputs/etl/load/<snapshot>/manifest.json`, with snapshot time, row counts, exclusions, and hashes.

Memory and export patterns (streaming, `COPY`, DuckDB settings) are in [`../README.md`](../README.md).
