# Performance and observability

- **Status:** Accepted 
- **Parent:** [`README.md`](README.md)
- **Use when:** adding a query, a read helper, a transform, or a run report.

## Scenario

A profiling script calls `read_local_tables()` to “just look” at `transactions`. Even on our 16–23 GB team machines (and originally an 8 GB target), materializing millions of rows of addresses and hashes in pandas causes 5×–10× memory expansion and hangs before the first chart. The query would have been cheap as `GROUP BY wallet_address`; the hang is self-inflicted.

A second failure: a run takes 5 hours and fails on 3 shards. Without a coverage table and manifest, nobody can tell which rows are present or whether a percentage used a partial denominator.

## Code

```python
def iter_wallet_chunks(engine: Engine, query: TextClause, chunk_size: int = 50_000):
    with engine.connect().execution_options(stream_results=True) as connection:
        for chunk in pd.read_sql_query(query, connection, chunksize=chunk_size):
            yield chunk
```

```python
# Bound is part of the interface.
def read_wallet_sample(engine: Engine, limit: int = 50_000) -> pd.DataFrame:
    if not 1 <= limit <= 100_000:
        raise ValueError("sample must be 1..100_000 wallets")
    ...
```

## Rules

1. **SQL computes; pandas displays.** Aggregate, filter, join, and window in SQL.
2. **Every read helper declares a row bound or grain.** No `SELECT *`; no full-table pandas.
3. **Stream row-level work** with `stream_results=True` and `chunksize`.
4. **Bulk movement uses `COPY`**, not pandas.
5. **Measure first.** Add `EXPLAIN (ANALYZE, BUFFERS)`, wall time, rows scanned/returned, rows/sec, and index use.
6. **Do not add workers or caching before measuring.** Source timeouts are a sign that more parallelism can hurt.
7. **Record `run_id`, `snapshot_id`, `schema`, `is_partial` in every output.**
8. **Three observability artefacts are enough:** run report, stage manifest, n-flow table.
9. **Do not build a monitoring stack** for a batch research pipeline.
10. **Quarantine known-broken state.** If it cannot be fixed now, label it (`is_partial`, red shard, blocked export) so nobody can quote it as clean.
11. **A prototype is not a tracer bullet.** A spike answers one question, is time-boxed, lives outside `src/`, and is deleted. If it survives, it is a tracer bullet and needs tests.

## Debate

- Is 50k the right default sample bound, or should it be 10k for 8 GB?
-> Keep 50k as the default wallet sample bound (~20 MB in pandas, safe on 16–23 GB team machines and matches `AGENTS.md` `50k–100k` while capturing enough rare `illicit` wallets).
- Should every read helper return a generator instead of a DataFrame?
-> Split by grain: return a generator (`iter_*_chunks`) for row-level/unbounded streaming, and return a `DataFrame` directly (`read_*`) for bounded wallet-level or aggregated reads where whole-column operations (quantiles, imputation, ANOVA, plots) are needed.
- Do we need a Parquet adapter now, or only PostgreSQL/CSV until DuckDB is installed?
-> DuckDB (`>=2.0.1`) and Parquet adapters are already implemented in `extract/parquet_source.py`, `load/main.py`, and full-frame stage profiling (`profile_stage.py --stage raw|transformed` over frozen Parquet snapshots); local mirror checks (`local`, `quality`, `overlap`, `benchmarks`) stay PostgreSQL-only per `02`.
- Which query should be the first benchmark: hop aggregation, cohort join, or feature aggregation?
-> Cohort join first (already identified as the current bottleneck in `profile/README.md`). Benchmark priority does not change coding style; its `EXPLAIN ANALYZE` results guide indexing and L1/L2 materialization.

## Additional to discuss
- Should we modify the database modeling to follow snowflake or star schema to improve the performance?
-> No Star/Snowflake remodeling needed. Keep L0 as a verbatim, unindexed mirror; create `wallet_address` indexes on materialized L1/L2 tables **after** bulk materialization only when PostgreSQL transform joins need them; keep L3 as a flat wallet-grain table exported to Parquet for H1–H6 analytical scans (no B-tree index needed, since `COPY` export and columnar Parquet scans are sequential); and build `address PRIMARY KEY` on `wallet_serving` after bulk load in managed PostgreSQL for concurrent web-app point lookups (with extra API-filter indexes owned by the web app team).

