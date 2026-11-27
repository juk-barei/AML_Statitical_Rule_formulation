# DuckDB full-frame stage profiling (`profile_stage.py`)
<!-- Last updated: 2026-11-27 | Edit count: 1 -->

- **Code:** `src/scripts/etl/transform/profile/profile_stage.py`, `src/scripts/etl/transform/profile/run_profile.py`, `src/scripts/etl/transform/profile/schema.py`
- **Contract:** `src/scripts/etl/transform/profile/README.md`, `src/scripts/etl/transform/README.md`

## The decision

Profiling inside `src/scripts/etl/transform/profile/` is split by workload:

- **PostgreSQL parts** (`local`, `quality`, `overlap`, `features` smoke mode, `benchmarks`) query the local mirror directly via `PostgresDataset` (`run_profile.py:75-133`).
- **Full-frame stage profiling** (`--parts stage`, implemented in `profile_stage.py`) runs **DuckDB** directly over frozen Parquet snapshots under `outputs/etl/load/phase*_{raw,transformed}_*` and writes compact CSVs into `outputs/etl/transform/profile/{raw,transformed}/`.

This does not turn DuckDB into the transform or serving database. L1–L3 materialization still belongs in PostgreSQL, and Parquet remains the canonical handoff. DuckDB is used here solely as an embedded, read-only analytical engine over frozen Parquet snapshots.

## Scenario: why PostgreSQL stalled on full-frame profiling

Profiling must be strictly read-only against the L0 mirror (`illicit.*`, `licit.*`): it cannot create indexes, primary keys, or derived tables in PostgreSQL. In the local mirror, the raw tables are unindexed row-store heaps (`illicit.accounts` 378 MB, `illicit.transactions` 3.45 GB, `licit.accounts` 507 MB — all with `0` index bytes in `outputs/etl/transform/profile/raw/query_benchmarks.csv:2-11`).

On that unindexed heap:

- A single `cohort_priority_join` took **29.1 s** and spilled **104,349 temp blocks** to disk (`query_benchmarks.csv:7`).
- Full-frame `profile_features.py` (which joins all accounts, hops, blacklists, and ~26.5M transactions across both schemas without materialized intermediates) was blocked by runtime/spill limits and restricted to `--limit-wallets` smoke runs.
- `profile_local.py` avoided full row scans in quick mode via `TABLESAMPLE SYSTEM(2%)` for tables above 100k rows (`profile_local.py:22-49`), which cannot provide exact full-frame column null counts.

In contrast, DuckDB reads compressed columnar Parquet files and allows **ephemeral, session-local `TEMP TABLE`s** without touching PostgreSQL:

```python
con = duckdb.connect()
con.execute(f"SET memory_limit = '{memory_limit}'")     # default: 6GB
con.execute("SET threads = 4")
con.execute(f"SET temp_directory = '{temp_dir.as_posix()}'")
con.execute("SET preserve_insertion_order = false")
```

(`profile_stage.py:172-179`). When the process exits, `con.close()` and `shutil.rmtree(temp_dir, ignore_errors=True)` leave zero persisted DB state (`profile_stage.py:1435-1437`, `1525-1527`).

## Mechanism

1. **Frozen manifest discovery.** `run_stage_profile()` resolves the latest snapshot directory for `--stage raw` (paired `illicit` + `licit` manifests) or `--stage transformed` (single transformed manifest) under `outputs/etl/load/` (`profile_stage.py:1252-1257`, `1462-1467`). Every output row carries `snapshot_at` and `is_partial` copied from `manifest.json`.
2. **Stage-routed outputs.** `stage_output_dir(output_dir, stage)` (`schema.py`) routes all profiling CSVs into `outputs/etl/transform/profile/raw/` or `outputs/etl/transform/profile/transformed/` so before/after runs never overwrite each other.
3. **Exact full-frame column refresh.** `_refresh_exact_columns()` scans each Parquet view once with `COUNT(col)`, `APPROX_COUNT_DISTINCT(col)`, and `MIN/MAX` on timestamp columns (`profile_stage.py:206-258`), eliminating `TABLESAMPLE` artifacts.
4. **Decomposed session-local intermediates (`--stage raw`).** `_materialize_cohort_and_clean_tx()` builds temp tables `cohort_wallet` (full `9,876,867` universe including `27,017` hop-only wallets) and `clean_tx` (`profile_stage.py:485-580`). `_materialize_wallet_features()` splits scalar counts/volumes (`feat_scalar`), distinct counterparty edges (`distinct_edges`, `feat_degrees`), Jaccard (`feat_h4_jaccard`), temporal burst (`feat_usdt_temporal`), and interval CV (`feat_h6_cv`) into sequential temp tables and drops intermediates immediately after joining into `wallet_profile` (`profile_stage.py:706-1015`). This prevents DuckDB from holding multiple ~50M-row `COUNT(DISTINCT)` hash tables concurrently under the 6 GB memory cap.
5. **Symmetric transformed mode (`--stage transformed`).** `_run_transformed_stage_profile()` maps `t_wallet_features` directly to `wallet_profile` and emits the exact same CSV schemas (`local_wallet_distributions.csv`, `local_feature_nflow.csv`, `local_wallet_histograms.csv`) for only the `FEATURE_SPECS` columns present (`profile_stage.py:1277-1434`).

## Limits

- **Requires an exported Parquet snapshot.** `profile_stage.py` cannot inspect live, unexported changes in PostgreSQL; run `load/main.py` first to freeze a snapshot.
- **Spill space required.** With `--memory-limit 6GB`, DuckDB spills hash/sort intermediates to `/tmp/duckdb_stage_profile` (deleted in `finally`). Low `/tmp` disk space will abort the run.
- **Numeric precision in raw mode.** Unconstrained PostgreSQL `numeric` columns arrive in Parquet as `DOUBLE` plus `<col>_exact` VARCHAR (see `docs/dev/etl/load/duckdb-and-reproducible-exports.md`). `classify_amount_flag()` checks both the `DOUBLE` ceiling and exact string sentinels (`profile_stage.py:59-90`).
- **Not a replacement for PostgreSQL query benchmarks.** DuckDB timings do not predict PostgreSQL transform join plans; use `benchmark_queries.py` (`EXPLAIN (ANALYZE, BUFFERS)`) when tuning PostgreSQL L1–L3 SQL and indexes.

## Verification

```bash
# Unit and synthetic DuckDB fixture tests
python -m src.scripts.etl.transform.profile.tests.test_profile_stage

# Full-frame raw stage profile -> outputs/etl/transform/profile/raw/
python -m src.scripts.etl.transform.profile.run_profile --parts stage --stage raw

# Post-transform stage profile -> outputs/etl/transform/profile/transformed/
python -m src.scripts.etl.transform.profile.run_profile --parts stage --stage transformed
```
