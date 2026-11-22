# ETL — extract, transform, load

The data pipeline lives in `src/scripts/etl/`. It writes every file under `outputs/etl/`.

Data authority, cohort rules, and inference rules are in [`AGENTS.md`](../../../AGENTS.md); this README covers how the pipeline runs and how to export safely.

| Module | Role | Output |
| --- | --- | --- |
| `ingest.py` | Extract online PostgreSQL → local PostgreSQL mirror. **Only writer of the mirror.** | Mirror database |
| `profile/` | Read-only schema, row, and overlap profiling. See [`profile/README.md`](profile/README.md). | `outputs/etl/profile/` |
| `transform/` | Reusable SQL for cleaning, cohort priority, eligibility, and features. See [`transform/README.md`](transform/README.md). | `outputs/etl/transform/` |
| `load.py` | Designated writer for shared exports. Currently a stub; implement exports here, not in notebooks. | `outputs/etl/export/<snapshot>/` |
| `tests/` | Assert-based checks: `python -m src.scripts.etl.tests.test_etl_args`. | `outputs/etl/tests/` |

Notebooks are **read-only** against the mirror: no `INSERT`, `UPDATE`, `DELETE`, or DDL. A cleaned or aggregated table that must persist is written by `ingest.py`, `load.py`, or a dedicated writer script under `src/scripts/etl/` — never created by hand in a notebook.

## Extract

```bash
python -m src.scripts.etl.ingest --status
python -m src.scripts.etl.ingest --dry-run
python -m src.scripts.etl.ingest --source illicit --schema illicit
python -m src.scripts.etl.ingest --source licit --schema licit
```

Requires the variables in `src/.env.example`. Never read or print `src/.env`.

Before any export, confirm the latest run is complete. Local and online counts drift; never quote a moving partial as a frozen `N`.

## Transform

Transform in SQL, not in pandas. SQL lives in `transform/` and covers cleaning, cohort priority, eligibility, and per-wallet features (CTEs, window functions, `GROUP BY wallet_address`). The rule for each clean is documented once in SQL and applied identically to every arm, with the `group × filter` n-flow recorded — see [`transform/README.md`](transform/README.md).

Keep results wallet-level or bounded; never return raw event rows to pandas.

## Load (export)

An export is a **frozen snapshot**, not a live database dump. Record:

- snapshot time, source, and schema;
- per-table row counts;
- exclusions and filters;
- export format and compression;
- SHA-256 of each file.

### Handoff layout

One directory per snapshot: `outputs/etl/export/<snapshot>/`.

```text
outputs/etl/export/<snapshot>/
  manifest.json
  DATA_DICTIONARY.md
  nflow.csv
  cohort_wallet.parquet          # one row per wallet: group, hop, seed, features
  wallet_hops.parquet            # full graph-distance table for H5
  blacklisted_wallets.parquet
  licit_seed_wallets.parquet
  transactions_illicit.parquet   # event history for H1/H3
  transactions_licit.parquet
  demo/                          # optional clearly-labelled sample
```

Drop `hex_address`, `_etl_*`, and `pipeline_crawl_state` unless a task needs them. Keep `tx_hash`, `block_timestamp`, `from_address`, `to_address`, `token_symbol`, `amount`, and `fee_trx` for H1/H3.

### Format decision

| Format | Use it for | Do not use it for |
| --- | --- | --- |
| **Parquet + zstd** | Canonical analysis handoff; columnar scans, typed timestamps/decimals, DuckDB/Polars/pandas | Point lookups by address; in-place updates |
| **CSV** | Small manifests, data dictionaries, n-flow tables | 15M+ transaction rows; type-sensitive numeric data |
| **Managed PostgreSQL** | Wallet-level serving table behind an API; concurrent lookups | Shipping raw event tables or credentials to friends |
| **DuckDB file** | Single-file local analysis or demo | Multi-user web app; source of truth |
| **SQLite** | Small embedded demo lookup table | Large analytical scans |

Parquet is usually the smallest practical analytical format because repeated addresses use dictionary encoding, timestamps use delta encoding, and zstd compresses the result. Gzipped CSV can be close in size but loses types, column pruning, and predicate pushdown.

### Consumer needs

| Consumer | Needs | Export |
| --- | --- | --- |
| `H1` pass-through speed | paired in/out amount and timestamp per wallet | `transactions_*` + `cohort_wallet` |
| `H3` spraying/funneling | in/out degree and amount CV over 1.5h windows | `transactions_*` + `cohort_wallet` |
| `H5` seed proximity | hop distance and seed assignment | `wallet_hops` + `blacklisted_wallets` |
| `H2`/`H4`/`H6` | wallet-level response features | `cohort_wallet` |
| Web app | address → group/score lookup | `wallet_serving` in managed PostgreSQL |

### Sampling rule

Sample **wallets**, never transaction rows, and keep all events for every selected wallet. Census small/rare arms; stratify suspicious by hop and cluster by `seed_address`; stratify licit by activity band. Record seed, strata, cluster, weights, and design effect. A demo sample is labelled as demo and never used for inference. The design evidence is in `outputs/nested-sampling-aml-wallets.md`.

### Web serving

Load only a wallet-level table into managed PostgreSQL:

```text
wallet_serving(address PK, group, risk_score, rule_flags, min_hop, seed, updated_at)
```

Expose it through an API with a read-only role. Do not expose the raw event table or database credentials. If the app must score arbitrary addresses outside the snapshot, that needs a live feature job, not a static export.

## Memory-constrained database access (8 GB target)

The failure mode is not the database; it is materializing millions of address strings in pandas. The illicit transaction table is ~15.2M rows and the licit table is ~11.3M at the 2026-11-22 online profile. Two ~40-character addresses per row plus `tx_hash` can exceed 8 GB before any merge.

### Rules

1. **Do not use `load_analysis_tables()` for real analysis.** It reads all four tables. Use it only with a small `limit` as a smoke test.
2. **Project and filter in SQL.** Select only needed columns; return wallet-level aggregates, not event rows.
3. **Stream row-level work.** Use a server-side cursor and process one chunk at a time.
4. **Process one group or wallet chunk at a time.** Illicit, suspicious, licit, and unlabeled are separate passes.
5. **Export with `COPY`, not pandas.** Bulk data goes Postgres → disk; DuckDB converts to Parquet.
6. **Use DuckDB for out-of-core Parquet analysis.** Set `memory_limit` and `temp_directory` so it spills to disk.
7. **Keep Postgres modest on the same machine.** Do not let Python and Postgres both assume they own 8 GB.

### SQL-first pattern

```python
from sqlalchemy import text

from src.scripts.etl.ingest import get_local_engine, load_environment

load_environment()
engine = get_local_engine()

sql = text("""
WITH eligible AS (
    SELECT ...
    FROM illicit.transactions
    WHERE block_timestamp >= :start
),
features AS (
    SELECT
        from_address AS wallet_address,
        count(*) AS n_events,
        avg(amount) AS avg_amount
    FROM eligible
    GROUP BY from_address
)
SELECT *
FROM features
""")

with engine.connect() as conn:
    wallet_features = pd.read_sql_query(
        sql, conn, params={"start": "2026-01-01"}
    )
```

### Streaming pattern

```python
with engine.connect().execution_options(stream_results=True) as conn:
    for chunk in pd.read_sql_query(
        sql, conn, params={"start": "2026-01-01"}, chunksize=50_000
    ):
        process(chunk)
        del chunk
```

A huge `ORDER BY` or window function still consumes Postgres memory. For global windows, aggregate in SQL or process one wallet group at a time.

### Export-without-pandas pattern

Export the `LOCAL_DB_*` variables from `src/.env.example` into your shell without printing them, then:

```bash
psql -h "$LOCAL_DB_HOST" -U "$LOCAL_DB_USER" -d "$LOCAL_DB_NAME" -c "\copy (
  SELECT from_address, to_address, block_timestamp, amount, token_symbol
  FROM illicit.transactions
) TO '/tmp/transactions_illicit.csv' CSV HEADER"
```

```sql
COPY (SELECT * FROM read_csv_auto('/tmp/transactions_illicit.csv'))
TO 'outputs/etl/export/<snapshot>/transactions_illicit.parquet'
(FORMAT parquet, COMPRESSION zstd);
```

### DuckDB out-of-core settings

```sql
SET memory_limit = '4GB';
SET temp_directory = '/tmp/duckdb_spill';
SET preserve_insertion_order = false;
```

DuckDB is for querying Parquet and prototypes. It is not the mirror and not the multi-user web database.

### Avoid

- `SELECT *` from `transactions`, `wallet_hops`, or `accounts`
- `pd.read_sql_table(...)` without filters
- merging two multi-million-row DataFrames in pandas
- `df.apply(...)` or `astype(str)` over all transactions
- keeping old DataFrames in notebook globals
- setting `work_mem` to several GB globally
- using `LIMIT` for a reported count

### Postgres coexistence

```sql
SET work_mem = '128MB';              -- per operation
SET maintenance_work_mem = '512MB';  -- index/build work
```

Keep `shared_buffers` modest on an 8 GB laptop. A small swap file is a safety net, not a substitute for SQL-first access.

## Export checklist

- [ ] `ingest --status` shows the source run complete.
- [ ] Snapshot time and per-table row counts recorded.
- [ ] SQL n-flow matches exported row counts.
- [ ] No `hex_address`, `_etl_*`, or credentials in the export.
- [ ] Files are written under `outputs/etl/export/<snapshot>/`.
- [ ] Parquet opens in DuckDB.
- [ ] `manifest.json` has row counts and SHA-256 hashes.
- [ ] Sampling design is documented, if a sample was drawn.
- [ ] Demo data is labelled and excluded from inference.
