# Layers and boundaries

- **Status:** accepted 
- **Parent:** [`README.md`](README.md)
- **Use when:** deciding what a module may read, write, or import.

## Scenario

A hypothesis runner needs `tx_lifetime_days` and `cv_delta_t`. It must not join `transactions` itself; otherwise the feature definition lives in two places and the test path depends on raw data.

## Layers

| Layer | Contents | Writer | Reader |
| --- | --- | --- | --- |
| L0 raw | `illicit.*`, `licit.*` mirror | `extract/main.py` only | L1 only |
| L1 clean | typed, deduped, null-policy applied | transform SQL | L2 only |
| L2 cohort | one row per wallet: group, hop, seed, flags | cohort builder | L3, analysis |
| L3 features | one row per wallet: all H1–H6 columns (scope narrows to H2/H4/H6 only after transformed export) | feature builder | analysis |
| L4 analysis | profile and test outputs | profiling/tests | humans |
| L5 export | frozen snapshot + manifest | `load/main.py` | downstream |

One writer per layer. Dependencies point one way. Analysis never reaches back into L0.

## Code

```python
# Pure core: no SQLAlchemy, no env, no file writes.
def classify_wallet(facts: WalletFacts) -> str: ...

# Imperative shell: owns the database layer, never writes export files directly.
def build_cohort(engine: Engine) -> CohortReport:
    rows = fetch_wallet_facts(engine)
    cohort = [WalletGroup(f.wallet_address, classify_wallet(f)) for f in rows]
    write_cohort_table(engine, cohort)
    return CohortReport(rows_in=len(rows), rows_out=len(cohort))
```

A ports-and-adapters seam is justified only for the formats we actually swap: PostgreSQL now, Parquet/CSV later. It is not a reason to add a repository class per table.

## Rules

1. L4 reads L2 + L3 + the manifest; never raw events.
2. Pure decisions live in a core that can be tested without a database.
3. The shell owns SQL, files, env, and CLI.
4. Do not cross `wallet_class × hop`; hop is nested in `suspicious`.
5. Every layer transition writes an n-flow row.

## Debate

- Is L1 clean a real layer, or can it be a SQL view inside L2?
-> Use a materialized view or table in a dedicated transform/clean schema (keeping `illicit.*` and `licit.*` strictly raw L0), and document which derived schemas/tables to export and drop (`DROP SCHEMA ... CASCADE`) from local storage when the project finishes.
- Should `build_cohort` write Parquet, or return rows for `load/main.py` to write?
-> `load/main.py` is the sole writer of Parquet files and any future export formats. `build_cohort` only computes/materializes the cohort inside PostgreSQL and never writes export files directly.
- Does the profile comparison need a Parquet adapter now, or only PostgreSQL/CSV?
-> Split by profiling workload: mirror schema, quality, overlap, and `EXPLAIN (ANALYZE, BUFFERS)` benchmarks stay PostgreSQL-only via `PostgresDataset`, while full-frame stage profiling (`profile_stage.py --stage raw|transformed`) runs DuckDB directly over frozen Parquet snapshots under `outputs/etl/load/` and writes stage-scoped CSVs to `outputs/etl/transform/profile/{raw,transformed}/` (avoiding unindexed L0 full-frame joins and `TABLESAMPLE` drift; see `docs/dev/etl/transform/profile/duckdb-stage-profiling.md`). L1–L3 materialization still runs in PostgreSQL and `load/main.py` remains the sole Parquet exporter.
