# ETL — extract, transform, load

The data pipeline lives in `src/scripts/etl/`. It has exactly three stages — `extract/`, `transform/`, `load/` — matching the name. Profiling is not a fourth stage; it is a read-only first step inside `transform/`. Every file is written under the matching `outputs/etl/` stage folder.

Data authority, cohort rules, and inference rules are in [`AGENTS.md`](../../../AGENTS.md); this README covers how the pipeline runs and how to export safely.

| Stage | Code | Output |
| --- | --- | --- |
| Extract | `extract/main.py` — online PostgreSQL or a frozen Parquet snapshot → local PostgreSQL mirror. **Only writer of the mirror.** `extract/parquet_source.py` is the Parquet adapter behind `--source parquet`; `extract/ingest_licit.py` resumes and verifies the licit load. | Mirror database; `outputs/etl/extract/` reports |
| Transform | `transform/` — SQL for cleaning, cohort priority, eligibility, and features. `transform/profile/` is the read-only first step. See [`transform/README.md`](transform/README.md). | `outputs/etl/transform/` |
| Load | `load/main.py` — frozen snapshot exporter: schema/table selection, Parquet or CSV, manifest, hashes. | `outputs/etl/load/<snapshot>/` |

**Tests live with their stage.** `extract/tests/`, `transform/profile/tests/`, and `load/tests/` hold the assert-based checks for that stage. There is no top-level `etl/tests/`, and no test writes into `outputs/etl/tests/`.

> Stage migration note: The ETL stages are organized into `extract/`, `transform/`, and `load/`. The export stage entry point is `load/main.py` (accessible via `python -m src.scripts.etl.load.main` or `uv run load`). Helper modules keep their own names.

Notebooks are **read-only** against the mirror: no `INSERT`, `UPDATE`, `DELETE`, or DDL. A cleaned or aggregated table that must persist is written by `extract/main.py`, `load/main.py`, or a dedicated writer script under `src/scripts/etl/` — never created by hand in a notebook.

## Extract

The CLI has three groups: general options, online-PostgreSQL options (`--pos*`),
and Parquet options (`--parq*`). `--source` is only `online_db` or `parquet`.

```bash
# General
python -m src.scripts.etl.extract.main --status --schema illicit
python -m src.scripts.etl.extract.main --source online_db --pos-db-type illicit --schema illicit --dry-run

# Online PostgreSQL
python -m src.scripts.etl.extract.main --source online_db --pos-db-type illicit --schema illicit
python -m src.scripts.etl.extract.main --source online_db --pos-db-type licit --schema licit
```

### Parquet source

A frozen export snapshot can rebuild the mirror without the online database:

```bash
# Validate the manifest, hashes, columns, and rows. No writes.
python -m src.scripts.etl.extract.main \
  --source parquet \
  --parq-source-path /absolute/path/to/phase1_raw_illicit_20261123T043155Z \
  --schema illicit --dry-run

# Load every table into the local mirror.
python -m src.scripts.etl.extract.main \
  --source parquet \
  --parq-source-path /absolute/path/to/phase1_raw_illicit_20261123T043155Z \
  --schema illicit
```

Rules:

- `--parq-source-path` must be **absolute** and must contain `manifest.json`.
- The manifest schema must match `--schema`. `--parq-allow-schema-mismatch` is
  for a test load only; it records the mismatch in the report.
- SHA-256 and row counts are verified by default. `--parq-skip-hash` skips only
  the file hash, not the manifest row/column checks.
- `--parq-allow-partial` is required for a snapshot or table marked `partial`.
- The Parquet adapter is single-process. `--pos-workers` and
  `--pos-shards-per-table` do not apply; `--batch-size` is the COPY batch size.
- `--resume` skips completed tables and reloads incomplete tables from scratch.
- `amount` is rebuilt as PostgreSQL `NUMERIC` from the exported `amount_exact`
  text; `amount_exact` is not recreated in the mirror.
- `hex_address`, `_etl_*`, and `pipeline_crawl_state` are not in a raw export and
  are not reconstructed. The adapter writes synthetic `_etl_runs` /
  `_etl_progress` provenance from the manifest.

The mechanism and limits are in
[`docs/dev/etl/extract/parquet-source.md`](../../../docs/dev/etl/extract/parquet-source.md).

### Licit recovery

Run these in order from the repo root:

```bash
python -m src.scripts.etl.extract.ingest_licit
python -m src.scripts.etl.extract.verify_ingestion --schema licit
```

`ingest_licit` resumes the latest licit run, then prints status and coverage.
`verify_ingestion` is read-only and exits non-zero until every table is 100%.
It is a command-line check, not a test fixture, and lives at `extract/verify_ingestion.py`.
Always pass `--schema licit`; `--status` without it targets `public` and fails
with `permission denied for schema public`.

Requires the variables in `src/.env.example`. Never read or print `src/.env`.

Before any export, confirm per-table coverage. `load/main.py` reads the newest run that includes each table; a table is complete only when all shards completed and local rows equal ingested rows. Local and online counts drift; never quote a moving partial as a frozen `N`.

## Transform

Transform in SQL, not in pandas. SQL lives in `transform/` and covers cleaning, cohort priority, eligibility, and per-wallet features (CTEs, window functions, `GROUP BY wallet_address`). Keep L0 mirror schemas (`illicit.*`, `licit.*`) strictly read-only; L1/L2 derived layers may be materialized as views/tables in a dedicated transform schema (with documented `DROP SCHEMA` cleanup at project end). Apply each clean rule identically to every arm and record the `wallet_class × filter` n-flow — see [`transform/README.md`](transform/README.md).

Profiling is the first transform step: `transform/profile/` reads the source and mirror, writes CSVs to `outputs/etl/transform/profile/`, and EDA plots those results. Profiling never writes to the mirror and is not a separate ETL stage.

Keep results wallet-level or bounded; never return raw event rows to pandas.

## Load (export)

An export is a **frozen snapshot**, not a live database dump. Record:

- snapshot time, source, and schema;
- per-table row counts;
- exclusions and filters;
- export format and compression;
- SHA-256 of each file.

### Export commands

Run `--dry-run` first. It prints per-table coverage and row counts without writing.

```bash
# Full raw illicit snapshot, default phase/stage path
python -m src.scripts.etl.load.main --schema illicit --tables all --dry-run

# Full licit snapshot, explicit transformed stage
python -m src.scripts.etl.load.main --schema licit --tables all --stage transformed

# H1/H3 transactions only, gzip CSV (explicit large-CSV opt-in)
python -m src.scripts.etl.load.main \
  --schema illicit --tables transactions \
  --out-dir /shared/handoff/h1_h3 --name illicit_transactions \
  --format csv --compression gzip --allow-large-csv

# H5 graph handoff
python -m src.scripts.etl.load.main \
  --schema illicit --tables wallet_hops,blacklisted_wallets \
  --out-dir /shared/handoff/h5 --name illicit_h5
```

The default snapshot id is `phase<N>_<stage>_<schema>_<UTC>`, where `N` comes from `[tool.capstone].phase` in `pyproject.toml` and `stage` is `raw` (default) or `transformed`. The default directory is `outputs/etl/load/<snapshot>/`; default table files are `<snapshot>__<table>.<ext>`.

`--out-dir` overrides the directory; `--name` is one exact basename for a single table or a prefix for several (`<name>__<table>.<ext>`). Existing snapshots are refused unless `--force` is passed. `--allow-partial` is required when any selected table's latest bookkeeping is incomplete.

Default export is Parquet + zstd. CSV defaults to gzip and refuses more than 1,000,000 rows unless `--allow-large-csv`. `hex_address` is dropped unless `--keep-hex` is passed. PostgreSQL `numeric` without precision is exported as `DOUBLE` plus `<column>_exact` VARCHAR, because DuckDB has no arbitrary-precision decimal type.

### Handoff layout

One directory per snapshot: `outputs/etl/load/phase<N>_<stage>_<schema>_<UTC>/`.

```text
outputs/etl/load/<snapshot>/
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

Raw exports use `<snapshot>__<table>.<ext>`; transformed handoffs may use the fixed names above. Drop `hex_address`, `_etl_*`, and `pipeline_crawl_state` unless a task needs them. Keep `tx_hash`, `block_timestamp`, `from_address`, `to_address`, `token_symbol`, `amount`, and `fee_trx` for H1/H3.

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

## Tests

Each stage owns its checks under `<stage>/tests/`. Run them from the repo root:

```bash
python -m src.scripts.etl.extract.tests.validate_ingest_args
python -m src.scripts.etl.extract.tests.verify_ingestion --schema illicit  # read-only coverage check
python -m src.scripts.etl.load.tests.load_export
python -m src.scripts.etl.load.tests.parquet_source

pytest src/scripts/etl/transform/profile/tests
```

`verify_ingestion` needs a loaded mirror; it is a CLI check, not a fixture. The profile tests are pytest-style. A stage change ships with the test that proves it, in that stage's `tests/` folder — never a shared top-level test directory.

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

from src.scripts.etl.extract.main import get_local_engine, load_environment

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
TO 'outputs/etl/load/<snapshot>/transactions_illicit.parquet'
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

- [ ] `extract.main --status` shows the source run complete.
- [ ] Snapshot time and per-table row counts recorded.
- [ ] SQL n-flow matches exported row counts.
- [ ] No `hex_address`, `_etl_*`, or credentials in the export.
- [ ] Files are written under `outputs/etl/load/<snapshot>/`.
- [ ] Parquet opens in DuckDB.
- [ ] `manifest.json` has `phase`, `stage`, `schema`, row counts, and SHA-256 hashes.
- [ ] `nflow.csv` exported counts equal local counts and the manifest.
- [ ] `amount_exact` is present whenever an unconstrained `numeric` column was exported.
- [ ] Sampling design is documented, if a sample was drawn.
- [ ] Demo data is labelled and excluded from inference.
