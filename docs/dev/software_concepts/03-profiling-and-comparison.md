# Profiling and comparison

- **Status:** Accepted 
- **Parent:** [`README.md`](README.md)
- **Use when:** adding a profile, a transform, or a before/after check.

## Scenario

Suppose an ingestion arm is incomplete (for example, when licit transactions were historically at 54.6% before ingestion finished). A profile that prints a single count without `is_partial` invites someone to quote it as a frozen `N`. A before/after comparison that joins raw and cleaned tables without a snapshot id mixes two different states.

## Stages

```text
raw → cleaned → eligible → feature-level → cohort/analysis
```

Compare each stage on:

1. row flow and retention per group/filter;
2. group movement (raw label vs final group crosstab);
3. missingness, zero mass, duplicates, orphans;
4. distribution shift (quantiles, mean/SD, skew) in original and transformed units;
5. hypothesis support (eligibility n, pass counts,need normalization, aggregation, standardization,  denominators);
6. compute cost (runtime, rows scanned, bytes, plan change).

The comparison is descriptive. It is not a p-value and must not choose a hypothesis after results.

## Code

```python
@dataclass(frozen=True)
class ProfileRecord:
    dataset: str
    stage: str
    table: str
    column: str | None
    metric: str
    value: float | int | None
    denominator: int | None
    group: str | None
    snapshot_id: str
    is_partial: bool
```

```python
def compare_records(before: list[ProfileRecord], after: list[ProfileRecord]) -> list[ComparisonRecord]:
    if {r.snapshot_id for r in before + after} != {before[0].snapshot_id}:
        raise ValueError("refusing to compare mixed snapshots")
    ...
```

## Rules

1. Every profile row carries `snapshot_id`, `schema`, and `is_partial`.
2. The comparison refuses mixed snapshots.
3. Row-count reconciliation and n-flow are mandatory, not optional charts.
4. The output is long-format, one row per metric, so CSV/Parquet/PostgreSQL can share it.
5. Profiling never writes to the mirror.
6. **Good-enough applies to tooling and exploratory scope, never to denominators, eligibility, cohort priority, or the frozen snapshot.** A partial arm is quarantined, not called complete.

## Debate

- Is `is_partial` enough, or does every row need the failed-shard count?
-> Keep `ProfileRecord` lean with `is_partial: bool` as the safety flag; `failed_shards` and shard-level details stay normalized once per table in `TableCoverage` / manifest (matching `src/scripts/etl/transform/profile/schema.py`).
- Should the comparison live in `etl/transform/profile/` or directly in `transform/`?
-> Keep comparison under `etl/transform/profile/compare/` following the Hedgehog flow (mirrored across `outputs/etl/transform/profile/`, `tasks/etl/transform/profile/`, and `docs/dev/etl/transform/profile/` only when 2+ related files justify a subdirectory).
- Do we compare raw-to-final only, or every adjacent stage?
-> Targeted adjacent-stage comparison: compare every adjacent stage for n-flow, row retention, and group movement, and run full column/distribution shifts only at stages that actually transform those columns (e.g., `raw → cleaned`, `eligible → feature-level`).
