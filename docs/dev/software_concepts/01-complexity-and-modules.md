# Complexity and modules

- **Status:** Accept 
- **Parent:** [`README.md`](README.md)
- **Use when:** deciding whether to split a module or add a new one.

## Scenario

`src/scripts/etl/extract/main.py` is 2,167 lines (though extraction has begun with `parquet_source.py` at 705 lines) and owns environment loading, engine creation, shard planning, COPY, progress, reporting, and notebook access. A new reader cannot hold that in their head. Splitting it into ten one-function files is also wrong: the reader then jumps across ten shallow modules with no shared contract.

The target is a few **deep modules**: each hides a real decision behind a small interface.

## Code

```python
# Shallow: the caller must know sharding, progress, and engine details.
run_etl(args, engine, schema, run_id, progress, shard_tasks, batch_size)

# Deep: the caller states intent; the module hides the rest.
resume_ingest(source="licit", schema="licit") -> IngestReport
```

```python
# Deep domain rule: the caller passes facts, not SQL.
def classify_wallet(facts: WalletFacts) -> str:
    if facts.is_blacklisted:
        return "illicit"
    if facts.min_hop is not None and 1 <= facts.min_hop <= 5:
        return "suspicious"
    if facts.in_licit_accounts:
        return "licit"
    return "unlabeled"
```

## Rules

1. Split by **hidden decision**, not line count.
2. A module must hide more than it exposes; if the interface is as complex as the body, it is shallow.
3. Do not create one file per function. Do not keep a god module.
4. Prefer **simple** (one concern, not interleaved) over **easy** (familiar but tangled).
5. Name the unit and the decision in the module name: `cohort_priority.py`, `ingest_progress.py`.

## Debate (Correct me if I am wrong)

- Is `src/scripts/etl/extract/main.py` one god module, or six legitimate modules that happen to share a file?
-> The goal is identifying which pieces can actually hide their internal decisions from the caller, rather than blindly splitting lines or creating shallow interdependent modules.
- Which is the first real seam: `db.py`, `progress.py`, or `plan.py`?
-> With limited memory and early stage of the project, we should go with `plan.py`. It presents a more fitting abstract level for the current project scope (pure mathematical planning of shard boundaries testable in memory), while `progress.py` (state tracking) can follow once the execution engine stabilizes.
- Does `classify_wallet` belong in a domain module or in the cohort builder?
-> Put it in a domain module so the core research rule is isolated, lightweight, and unit-testable without database or ETL dependencies. The cohort builder executes the matching SQL `CASE WHEN` at scale, backed by a parity test so Python and SQL never drift.
