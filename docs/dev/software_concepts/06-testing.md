# Testing

- **Status:**accepted. 
- **Parent:** [`README.md`](README.md)
- **Use when:** adding a rule, a transform, a feature, a profile, or a test runner.

Testing is the largest concept file on purpose. If the rules below are not met, the rest of the design is not finished.

## Scenario

A cohort builder looks correct on the full mirror. Six weeks later a blacklisted wallet at hop 3 appears as `suspicious`, because the priority test was never written. A feature table changes silently when a window boundary moves, because there was no golden sample. A partial licit run is quoted as complete, because the n-flow check only printed a warning.

The full mirror is the worst place to discover these. Test the rules on a five-wallet fixture first.

## Test sizes

| Size | What it covers | Runs on | Must be fast |
| --- | --- | --- | --- |
| Small | pure rules, formulas, n-flow arithmetic, naming/contract | in-memory rows | yes |
| Medium | SQL transform, priority join, coverage verifier | local PostgreSQL fixture schema | yes |
| Large | shard sums, full n-flow reconciliation, drift | real mirror | manual/nightly |
| Golden | bounded wallet sample hash | real table | manual/release |

Small and medium tests must not require the 11M-row mirror. If a test needs the full mirror, it is a large test.

## What to test per layer

| Layer | Required test |
| --- | --- |
| L0 raw | row count per shard sums to table count; coverage status |
| L1 clean | dedupe/null rules on a tiny fixture; no duplicate `tx_hash` / `transaction_hash` |
| L2 cohort | priority is total; one group per wallet; blacklist at hop 3 is illicit |
| L3 features | each formula on a known fixture; eligibility n-flow |
| L4 analysis | result table shape; n-flow reconciliation; no raw-table read |
| L5 export | manifest fields; hashes; partial flag; row count = n-flow |

## Exact rules

1. **Test the rule, not the library.** Do not test PostgreSQL `sum`/`count`; test your priority, formula, filter, and reconciliation.
2. **One test per rule and per edge case.** A rule with a boundary gets a boundary test.
3. **Every SQL transform gets a fixture test.** Create a tiny schema with 5–10 accounts and 20 transactions; assert exact output rows.
4. **Every stage gets an n-flow test.** `n_out + n_dropped = n_in`; per-group totals reconcile.
5. **Every priority/formula gets a property test.** Group assignment is a partition; hop is monotonic; removing rows cannot increase a count.
6. **Every feature table gets a golden test.** Hash a deterministic 1,000-wallet sample; diff after a refactor.
7. **Data-quality checks fail the run, not warn.** Duplicate keys, null keys, orphan FKs, invalid groups.
8. **Test names state unit + condition + expected.** `test_classify_wallet_blacklist_at_hop_three_is_illicit`.
9. **Fixtures cover the ugly cases.** Zero events, one-shot wallet, blacklist at hop 3, licit ∩ suspicious, multi-seed wallet, zero inflow, null timestamp.
10. **No full-table pandas in a test.** Use a bounded fixture or a SQL aggregate.
11. **Coverage is branch coverage for critical rules, not a global percentage.**
12. **A test must be reproducible.** Fixed seed, fixed snapshot, no `datetime.now()`.
13. **Test the nullable anti-join and fan-out cases.** A `NOT IN`/`NOT EXISTS` fixture and a multi-hop join fixture are required for SQL transforms.
14. **A test that passes for an unknown reason is a coincidence, not a pass.** Investigate or delete it.

## Contracts and assertions

A contract is what a boundary promises: a `WalletFacts`, a cohort row, a manifest, a result table. Validate at trust boundaries; assert only internal invariants.

```python
# Boundary input: validate, do not assert.
def load_snapshot(path: Path) -> Snapshot:
    if not path.exists():
        raise FileNotFoundError(path)
    ...

# Internal invariant: assert is fine.
def classify_wallet(facts: WalletFacts) -> str:
    assert facts.wallet_address is not None
    ...
```

- Use `raise` for user/source/file/config errors. `python -O` strips `assert`, so an assertion is not validation.
- Use `assert` only for “this should be impossible” programmer states.
- One schema per layer boundary; validate required manifest keys before writing.
- Fail closed for data quality. If a known-broken source cannot be fixed, quarantine it (`is_partial`, blocked export), do not warn and continue.

## Code

```python
def test_classify_wallet_blacklist_at_hop_three_is_illicit():
    facts = WalletFacts(
        wallet_address="T...",
        is_blacklisted=True,
        min_hop=3,
        in_licit_accounts=True,
    )
    assert classify_wallet(facts) == "illicit"


def test_nflow_reconciles():
    assert n_out + n_dropped == n_in


def test_cohort_is_a_partition(cohort):
    assert cohort["wallet_address"].is_unique
    assert set(cohort["wallet_class"]) <= {"illicit", "suspicious", "licit", "unlabeled"}
    assert cohort["wallet_class"].notna().all()
```

```python
from hypothesis import given, strategies as st

@given(st.lists(st.builds(WalletFacts), max_size=50))
def test_group_is_total(wallets):
    groups = [classify_wallet(w) for w in wallets]
    assert all(g in GROUPS for g in groups)
```

```python
# Medium: run the real SQL against a tiny fixture schema.
def test_cohort_sql_blacklist_wins(pg_fixture):
    load_fixture(pg_fixture, "cohort_edge_cases.sql")
    rows = run_sql(pg_fixture, "cohort_wallet.sql")
    assert rows[("T...",)] == "illicit"
```

```python
# Golden: deterministic sample, not the full table.
def test_feature_sample_hash():
    sample = read_wallet_sample(limit=1_000, order_by="wallet_address")
    assert sha256_rows(sample) == "expected..."
```

```python
# Data quality: fail, do not warn.
def test_no_orphan_transactions(conn):
    assert conn.scalar(ORPHAN_TX_SQL) == 0
```

## Test layout

```text
src/scripts/etl/extract/tests/
  test_parquet_source.py
  test_extract_args.py
src/scripts/etl/transform/cohort/tests/
  test_cohort_priority.py
  test_nflow.py
src/scripts/etl/transform/features/tests/
  test_features.py
src/scripts/etl/transform/profile/tests/
  test_profile_core.py
  test_profile_features.py
  test_benchmark.py
src/scripts/etl/load/tests/
  test_load_export.py
src/scripts/hypothesis_testing/tests/
  test_load_cohort.py
  test_result_shape.py
```

Use pytest as the target runner (add `pytest` to `pyproject.toml` dev dependencies); migrate existing assert-based scripts (`extract/tests/validate_*.py`, `load/tests/load_export.py`) to pytest naming.

## Done when

- Every rule has a small test.
- Every SQL transform has a fixture test.
- Every stage has an n-flow assertion.
- The full-mirror checks are separated as large tests.
- A partial run cannot pass as complete.
- The golden sample is deterministic and committed.

## Debate

- Is 1,000 wallets the right golden sample, or should it be stratified by group/hop?
-> Stratified by `wallet_class` and hop (with a small fixed cap per stratum, ~1,000 total) so rare arms like `illicit` (0.54%) and hop-5 edge cases are guaranteed coverage while the committed golden fixture stays tiny and fast.
- Which rules deserve property tests first: priority, hop monotonicity, or n-flow?
-> Priority (`classify_wallet`) and n-flow conservation first (both are small, pure-Python property tests protecting cohort integrity and denominators); add hop monotonicity when the hop SQL transform is written.
- Should data-quality failures fail the run or produce a `status: partial` artefact?
-> Data-quality failures (duplicate keys, NULL addresses, orphan FKs, invalid `wallet_class`, broken n-flow) fail the run hard. Network/shard timeouts during `extract` stay quarantined as `is_partial=True` so downloads can resume, while downstream export/analysis refuses to treat partial runs as complete.
- Do we add pytest now, or keep assert-based scripts until the cohort builder exists?
-> Add `pytest` now to unify existing `profile/tests/test_*.py` with upcoming `extract`/`transform`/`load` tests.
