# Web serving — wallet-level table

- **Status:** todo
- **Blocked by:** [`03_export_pipeline.md`](03_export_pipeline.md)
- **Blocks:** phase-2 web application
- **Owner:** worker
- **Output:** `wallet_serving` in managed PostgreSQL + read-only API role
- **Updated:** 2026-11-22

## Objective

Serve the phase-2 web application from a **wallet-level** table only. The app looks up one
address and reads its group, score, and rule flags; it never touches the mirror and never
receives credentials.

## Resources / context

- [`src/scripts/etl/README.md`](../../src/scripts/etl/README.md) — web-serving section and
  format decision
- `docs/context/export_contract.md` — the frozen snapshot this table is built from
- `tasks/hypothesis_testing/08_conclusion/04_next_phase_handoff.md` — what the phase-2
  owner receives
- `AGENTS.md` — credential ban and export rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `src/scripts/etl/load/main.py` | `--target serving` load path from the snapshot |
| create | `docs/context/web_serving.md` | table schema, role, and limits |

## Implementation points

- **Schema:** `wallet_serving(address PK, group, risk_score, rule_flags, min_hop, seed,
  updated_at)` — one row per wallet, no event table, no hex-form duplicate column.
- **Source:** loaded from `outputs/etl/load/<snapshot>/cohort_wallet.parquet`; the
  `snapshot` and load time are stored in the table so a stale row is detectable.
- **Access:** API connects with a read-only role granted `SELECT` on `wallet_serving`
  only; no other table, no DDL, no write grant.
- **Credentials:** live in the deployment environment, never in the repo, the snapshot, the
  manifest, or a task record.
- **Out of scope:** scoring addresses outside the snapshot needs a live feature job, not a
  static export — record it as a phase-2 decision, do not stub it here.

## Done when

- `wallet_serving` row count equals the snapshot's `cohort_wallet` row count.
- A read-only role returns a row for a known address and `NULL` for an unknown one.
- No raw event table and no credential is exposed to the app.
- `docs/context/web_serving.md` states the schema, the role, and the snapshot it came from.
