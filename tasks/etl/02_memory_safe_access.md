# Memory-safe database access

- **Status:** in_progress
- **Blocked by:** —
- **Blocks:** every analysis step (EDA, assumptions, tests, effect sizes)
- **Owner:** worker
- **Output:** reusable query/streaming guidance + a verification check
- **Updated:** 2026-11-22

## Objective

Make SQL-first, wallet-level, streamed access the default for every analysis pass, so no
notebook or script materializes `accounts`, `transactions`, or `wallet_hops` wholesale on
an 8 GB machine. This task produces the reusable guidance and the check that proves a
read stayed small — not the analysis itself.

## Resources / context

- [`src/scripts/etl/README.md`](../../src/scripts/etl/README.md) — SQL-first, streaming,
  `COPY`-export, and DuckDB out-of-core patterns
- [`src/scripts/etl/transform/README.md`](../../src/scripts/etl/transform/README.md) — which
  rules belong in SQL (cleaning, cohort priority, eligibility, features)
- `AGENTS.md` — data access, memory, and export rules
- `src/scripts/etl/extract/main.py` — `get_local_engine`, `load_environment`
- `src/scripts/etl/tests/test_etl_args.py` — existing check style (plain asserts, no test runner)

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/scripts/etl/README.md` | tighten the access patterns only after they are verified |
| create | `src/scripts/etl/transform/access.py` | one documented entry point per access shape |
| create | `src/scripts/etl/tests/test_memory_safe_access.py` | verification check |
| create | `docs/context/memory_safe_access.md` | the rule, one page, linked from the code |

## Implementation points

- **One rule, one place.** Every read states its filter, projection, and grain; no
  `SELECT *`, no `pd.read_sql_table`, no `LIMIT` behind a reported count.
- **Grain:** return wallet-level aggregates or a bounded sample (50k–100k rows); raw
  event rows never reach pandas.
- **Streaming:** `engine.connect().execution_options(stream_results=True)` with
  `pd.read_sql_query(..., chunksize=50_000)`, one chunk or wallet group at a time, chunk
  freed after use.
- **Bulk export:** `COPY` to disk, then DuckDB to Parquet — not pandas.
- **Coexistence:** modest `work_mem`/`maintenance_work_mem`; DuckDB `memory_limit` and
  `temp_directory` set before a spill-prone query.
- **Verification check** asserts, on a real connection:
  1. every helper returns at most its declared row bound and grain;
  2. the chunked path yields the same totals as a single aggregate query;
  3. the n-flow of a filtered read reconciles with the unfiltered count;
  4. no helper selects `hex_address` unless the caller asks for it.
- Record the peak memory and row count beside the first real pass so the bound is
  evidence, not an assertion.

## Done when

- The guidance lives in one place and the code links to it.
- `python -m src.scripts.etl.tests.test_memory_safe_access` passes and prints the row
  counts it checked.
- A real analysis read is demonstrated within the declared bound, with the numbers shown.
