# Query benchmarks — D

- **Status:** done
- **Blocked by:** —
- **Blocks:** export size/time decisions, cohort/feature query design
- **Owner:** worker subagent + lead review
- **Output:** `outputs/etl/profile/query_benchmarks.csv`, `query_plans/`
- **Updated:** 2026-11-23

## Objective

Measure representative local queries with `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`:
counts, blacklist anti-join, hop aggregation, token aggregation, cohort join,
and H2/H4/H6 aggregates. Record timing, rows, blocks, and table/index sizes.

## Resources / context

- `src/scripts/etl/profile/profile_local.py`, `metrics.py`
- accepted concepts `02`, `05`, `07`, `10`
- `docs/dev/software_concepts/07-performance-and-observability.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `src/scripts/etl/profile/benchmark_queries.py` | benchmark runner |
| create | `src/scripts/etl/profile/tests/test_benchmark.py` | tests |
| create | `outputs/etl/profile/query_benchmarks.csv` | results |
| create | `outputs/etl/profile/query_plans/*.json` | plans |

## Implementation points

- Query registry with counts, anti-join, hop aggregation, token aggregation, cohort, H2/H4/H6.
- Parse JSON plans; record planning/execution ms, rows, blocks, temp blocks.
- Record table/index bytes.
- `--limit` bounded mode; no result materialization.
- No DDL, no mirror writes, no `ingest.py` edits.

## Result

- `benchmark_queries.py` and `test_benchmark.py` exist; ruff/pyright and unit checks pass.
- Bounded all-query run completed for illicit and licit.
- `query_benchmarks.csv` and `query_plans/` written.
- Full unbounded `--queries all` was not run; bounded results are labelled in the CSV.
EOF
