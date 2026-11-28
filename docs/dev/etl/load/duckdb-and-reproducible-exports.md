# DuckDB and reproducible export environments
<!-- Last updated: 2026-11-28 | Edit count: 3 -->

- **Scope:** why `src/scripts/etl/load/main.py` uses DuckDB, how the engine is distributed, and when a container image is warranted.
- **Applies to:** ETL export (`load/main.py`), Parquet handoff, public raw-data releases, paper reproduction.
- **Related:** [`src/scripts/etl/README.md`](../../../../src/scripts/etl/README.md), [`etl/extract/process-model-and-connections.md`](../extract/process-model-and-connections.md).

## 1. What DuckDB is

DuckDB is an **embedded analytical relational database**. It is a full SQL engine linked into the calling process, not a client-server service.

Operational consequences:

- `import duckdb` loads a native library. There is no daemon, listening socket, port, authentication layer, or background service.
- `duckdb.connect()` creates an in-memory database by default. `duckdb.connect("file.duckdb")` creates a file-backed database. Neither is required for Parquet export.
- Execution is columnar and vectorized, with zone maps, predicate pushdown, and parallel operators. It is designed for scans, joins, aggregation, and file conversion.
- It supports ACID transactions and MVCC inside a process, but it is **not** a multi-client database server. Treat it as single-writer; do not use it as the web application's serving database.
- It reads CSV, Parquet, JSON, and Arrow directly. Parquet and CSV support are built in; optional extensions add other sources, including a PostgreSQL scanner.
- Queries can spill to disk. `memory_limit` and `temp_directory` bound memory and choose the spill location.

PostgreSQL and DuckDB solve different problems:

| Property | PostgreSQL | DuckDB |
| --- | --- | --- |
| Process model | Separate server process; TCP protocol | In-process library |
| Primary workload | OLTP, concurrent clients, serving | OLAP, batch scans, file conversion |
| Concurrency | Many clients, roles, MVCC | Single writer per database; not a server |
| Persistence | Server-managed database | `*.duckdb` file or in-memory |
| Containerization | Natural, because it is a service | Unnecessary, because it is embedded |

## 2. Distribution: package, module, and CLI

DuckDB ships the same engine through several distribution surfaces:

| Surface | Install | Role in this project |
| --- | --- | --- |
| Python package `duckdb` | `uv add duckdb` | **Required.** `load/main.py` imports it to convert and verify Parquet. |
| CLI `duckdb-cli` | `uvx duckdb-cli` | Optional inspection only. Runs in an isolated `uvx` environment. |
| System/binary CLI | OS package or release binary | Not used; adds an unmanaged version to the host. |

The Python wheel contains platform-specific native code, so `uv` resolves the correct wheel for the interpreter and OS. As of 2026-11-23, `duckdb==2.0.1` resolves for the project's Python 3.14 environment, and `uvx duckdb-cli` reports the same engine version.

`uvx duckdb-cli` is **not importable** by project code. It is a separate environment and must not be invoked by `load/main.py`; doing so would make the pipeline depend on a mutable user cache and a second process.

Version discipline:

- Pin the Python package in `pyproject.toml`/`uv.lock`; the engine version is part of the export environment.
- A CLI version mismatch is usually harmless for reading Parquet, but it is a second engine and should not be used for pipeline verification.
- DuckDB's CSV sniffer can infer different types across versions. `load/main.py` must pass explicit column types from `information_schema`, not rely on inference.

## 3. Role in the export path

The export path is deliberately:

```text
PostgreSQL
  -> COPY (SELECT ...) TO STDOUT          # server-side stream, explicit columns
  -> temporary CSV on disk                # no pandas materialization
  -> DuckDB typed read                    # explicit schema
  -> Parquet + zstd                       # portable handoff
  -> DuckDB row-count verification
  -> SHA-256 + manifest entry
```

Why this shape:

- **Memory:** a 14M-row transaction table cannot be materialized in pandas on the 8 GB target. PostgreSQL streams; DuckDB converts out of core.
- **Types:** CSV is an interchange buffer, not the deliverable. DuckDB restores `bigint`, constrained `numeric`, `timestamptz`, and text columns according to the source schema before writing Parquet. PostgreSQL `numeric` without precision exceeds DuckDB's `DECIMAL(38)` limit, so it is exported as `DOUBLE` plus `<column>_exact` VARCHAR to preserve the source text.
- **Portability:** Parquet is the contract. Consumers can read it with DuckDB, pandas/pyarrow, Polars, R, Spark, or a warehouse. DuckDB is replaceable; the file is not.
- **Separation of concerns:** PostgreSQL remains the mirror and computes SQL. DuckDB is a conversion/verification engine, not a second source of truth.
- **Security and reproducibility:** the Postgres `COPY` path avoids putting a connection string into a DuckDB `ATTACH` statement, avoids requiring the PostgreSQL extension in the image, and keeps one credential path through `psycopg`.

DuckDB's PostgreSQL scanner is a valid alternative for some workloads, but it changes the trust boundary: credentials and connection metadata enter DuckDB, and the extension must be available offline. It is not the default here.

Format policy:

- `parquet` + `zstd` is the canonical export.
- `csv` is allowed for small tables, manifests, and data dictionaries. CSV above 1,000,000 rows requires an explicit override and is not the recommended public release.
- No `.duckdb` file is produced by the export. A DuckDB file is a query workspace, not a handoff artifact.
- For spill-prone conversions set `memory_limit`, `temp_directory`, and a bounded `threads` value. Temp files live under the snapshot directory and are removed after verification.

## 4. Reproducibility: the environment, not the engine

A DuckDB-only image is not a reproducible pipeline. It contains the conversion engine but omits:

- the Python interpreter version;
- `psycopg`, SQLAlchemy, and the rest of the dependency graph;
- the project source and entry points;
- the pinned `uv.lock`;
- OS libraries and locale/timezone data.

Reproducibility therefore pins the **whole runtime**:

```dockerfile
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
RUN uv sync --frozen --no-dev

ENTRYPOINT ["python", "-m", "src.scripts.etl.load.main"]
```

Build-context rules:

- Never copy `src/.env`, credentials, `outputs/`, `datasets/`, or `.git/` into the image. Use `.dockerignore`.
- Confirm `.dockerignore` excludes at least `src/.env`, `outputs/`, `datasets/`, `.git/`, and `__pycache__/`.
- Mount the snapshot destination as a volume. Never bake export data into the image.
- Pass credentials at run time, not build time.

Example run:

```bash
docker build -t etl-repro:0.1 .
docker run --rm \
  --env-file src/.env \
  -v "$PWD/outputs:/app/outputs" \
  etl-repro:0.1 \
  --schema illicit --tables all \
  --out-dir /app/outputs/export/illicit_20261123 \
  --name illicit_raw
```

Operational caveats:

- Docker's `--env-file` is not dotenv syntax: no `export`, and quoting/escaping rules differ. Validate the file before relying on it.
- Inside a container, `localhost` is the container. For a PostgreSQL server on the host, use the host gateway (`host.docker.internal` with `--add-host=host.docker.internal:host-gateway` on Linux) or a Compose service name.
- If PostgreSQL is also containerized, keep the mirror in a named volume and make the ETL service depend on a database healthcheck.
- DuckDB needs no service, port, or healthcheck. That is the reason not to containerize it separately.
- On macOS/Windows, bind-mount I/O is slower than a native filesystem. Measure before blaming DuckDB for throughput.

Evidence for a paper release:

- image digest (not only the tag);
- `uv.lock` commit;
- snapshot time and manifest;
- per-file SHA-256;
- source run ids and row counts.

The image is the executable environment; the manifest and hashes are the data evidence. Neither replaces the other.

## 5. Decisions and limits

| Decision | Rationale |
| --- | --- |
| Install `duckdb` as a project dependency | `load/main.py` needs the Python API; `uv.lock` pins it. |
| Use `uvx duckdb-cli` only for inspection | Keeps the CLI out of the pipeline and avoids a mutable cache dependency. |
| Do not run DuckDB as a server or container | Embedded engine; no network surface or service to operate. |
| Containerize the whole ETL environment only when reproducing/publishing | Pins Python, `uv`, lock, code, and OS together. |
| Keep Parquet as the canonical artifact | Portable and typed; DuckDB remains replaceable. |

Limits to record in the export contract:

- DuckDB does not replace PostgreSQL for web serving or concurrent writes.
- CSV export loses type fidelity and is not the public-analysis default.
- Unconstrained PostgreSQL `numeric` cannot be represented exactly as a DuckDB decimal; `DOUBLE` is the analysis column and `<column>_exact` keeps the source text.
- Explicit column typing is mandatory; never trust CSV inference for a frozen snapshot.
- Offline images must disable extension auto-install/auto-load or preinstall every required extension.
- A DuckDB version is part of the environment manifest when the engine participates in conversion or verification.
- Completeness bookkeeping (`_etl_runs` / `_etl_progress`) exists only on extracted `raw` mirror schemas (`illicit`, `licit`); locally materialized `--stage transformed` exports have no shard bookkeeping and resolve to `status="complete"` (`partial=false`) unless explicit shard failures are recorded.
