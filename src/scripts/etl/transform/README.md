# `etl/transform` — SQL and feature builders

SQL that turns the raw mirror into analysable tables: cleaning, cohort priority, eligibility, and the per-wallet features the hypotheses consume. One `.sql` file per rule set, with a short module wrapper only when a script needs to run it.

Profiling is the first step in this stage, not a separate ETL stage. `profile/` reads the source and mirror, writes `outputs/etl/transform/profile/`, and EDA plots those results. Transformation rules are then written from the profile's findings. See [`profile/README.md`](profile/README.md).

Outputs go to `outputs/etl/transform/`; tests for a transform live in `tests/` beside it.

Cohort definitions, hop nesting, and inference constraints are in [`AGENTS.md`](../../../../AGENTS.md). This folder implements them; it does not redefine them.

## What belongs here

| Concern | Rule to build |
| --- | --- |
| Cleaning | documented, versioned rules: null handling, type fixes, deduplication, zero-event rows — stated once, applied to every arm |
| Cohort priority | `illicit` (blacklist wins at every hop) > `suspicious` (hop 1–5, not blacklisted) > `licit` > `unlabeled` |
| Eligibility | a stated eligibility rule per response, so undefined responses are resolved by the rule, never dropped silently |
| H1 / H3 / H5 features | pass-through speed, spraying/funneling, seed proximity — wallet-level aggregates |
| H2 / H4 / H6 features | wallet-level response features for the shared cohort table |

Every transform reports the `group × filter` n-flow so the number of rows removed is visible at each step.

## Rules

- **SQL computes, pandas displays.** Aggregate, join, deduplicate, and window in SQL. Never load `accounts`, `transactions`, or `wallet_hops` wholesale into pandas; return wallet-level rows or a bounded sample.
- **One rule, one place.** A clean applied to one arm must be applied identically to the others; keep it in a CTE or view rather than copying conditions between queries.
- **No ad-hoc DDL or DML from notebooks.** Persistent tables are created through the ETL writer path — `extract/main.py` (mirror), `load/main.py` (exports), or a dedicated writer script under `src/scripts/etl/`. Intermediate results that do not need to persist stay as queries.
- **Freeze what you export.** A transform feeding a handoff snapshot is recorded in `outputs/etl/load/<snapshot>/manifest.json`, with snapshot time, row counts, exclusions, and hashes.

Memory and export patterns (streaming, `COPY`, DuckDB settings) are in [`../README.md`](../README.md).
