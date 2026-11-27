# `etl/transform/cohort` — L2 Wallet Cohort Priority Table (Proposal)
<!-- Created: 2026-11-27 | Last updated: 2026-11-27 | Edit count: 1 -->

Materializes the authoritative 1-row-per-wallet `transform.cohort_wallet` table enforcing priority **`illicit > suspicious > licit > unlabeled`**, strict hop nesting (`min_hop_level` populated only for `suspicious`), and reconciled full-universe membership (`9,876,867` wallets including `27,017` hop-only wallets).

## Files

| File | Role |
| --- | --- |
| `rules.py` | Pure Python cohort priority, nesting, and partition invariant helpers. |
| `01_cohort_wallet.sql` | Full-universe union, pre-aggregated hop multiplicity, deterministic `primary_seed_address`, and contaminated licit-seed provenance flags. |
| `02_cohort_indexes.sql` | Post-materialization `PRIMARY KEY`, `CHECK` constraints (class + hop nesting), and secondary indexes on `transform.cohort_wallet`. |
| `main.py` | Thin CLI runner with `--dry-run`, `--step`, invariant checks, and CSV output writer (`outputs/etl/transform/cohort/`). |
| `tests/test_cohort.py` | Pure-rule checks, `10-sql-rules.md` static guardrails, and in-memory DuckDB nullable anti-join + hop fan-out fixture tests. |

## Step-by-Step Execution (Manual Review Mode)

```bash
# Preview SQL without touching PostgreSQL
python -m src.scripts.etl.transform.cohort.main --dry-run

# Execute step by step when approved
python -m src.scripts.etl.transform.cohort.main --step 01_cohort_wallet
python -m src.scripts.etl.transform.cohort.main --step 02_cohort_indexes
python -m src.scripts.etl.transform.cohort.main --step nflow
```

## Verification

```bash
# Pure-Python + in-memory DuckDB parity checks (never touches PostgreSQL)
python -m src.scripts.etl.transform.cohort.tests.test_cohort
```

Architecture and trade-offs: [`docs/dev/etl/transform/cohort/l2-cohort-priority-and-nesting.md`](../../../../../docs/dev/etl/transform/cohort/l2-cohort-priority-and-nesting.md).
