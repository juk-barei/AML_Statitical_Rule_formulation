# L1 Cleaning Builder (`clean/`) — Proposal
<!-- Created: 2026-11-27 | Last updated: 2026-11-27 | Edit count: 1 -->

- **Status:** todo (scripts proposed; awaiting manual line-by-line execution by user)
- **Blocked by:** `06_feature_profile.md` (done)
- **Blocks:** `11_l3_features.md`, `12_transformed_export_audit.md`
- **Owner:** user manual execution + agent proposal
- **Output:** `transform.clean_transactions`, `transform.clean_tx_conflicts`, `transform.clean_wallet_hops`, `outputs/etl/transform/clean/{clean_nflow,clean_flag_breakdown}.csv`
- **Updated:** 2026-11-27

## Resources / context

- `docs/context/transform_phase_recommendations.md`
- `docs/context/ingestion_anomaly_validation.md`
- `docs/dev/software_concepts/02-layers-and-boundaries.md` (accepted)
- `docs/dev/software_concepts/10-sql-rules.md` (accepted)

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `src/scripts/etl/transform/clean/rules.py` | Pure L1 flag & tie-break rules |
| create | `src/scripts/etl/transform/clean/01_clean_transactions.sql` | Cross-schema dedupe + non-destructive flags + conflict audit table |
| create | `src/scripts/etl/transform/clean/02_clean_wallet_hops.sql` | Hop-edge `via_tx_status` audit table |
| create | `src/scripts/etl/transform/clean/03_clean_indexes.sql` | Post-materialization indexes on `transform.*` |
| create | `src/scripts/etl/transform/clean/main.py` | Step-by-step CLI runner + n-flow CSV exporter |
| create | `src/scripts/etl/transform/clean/README.md` | Module runbook |
| create | `src/scripts/etl/transform/clean/tests/test_clean.py` | Unit, SQL guardrail, and in-memory DuckDB parity checks |
| create | `docs/dev/etl/transform/clean/l1-transaction-cleaning.md` | Architecture & failure-mode note |

## Implementation points

- Deduplicate `26,343,989` union rows → `26,189,701` unique `tx_hash` via deterministic `ROW_NUMBER()`.
- Flag `sentinel`, `above_supply`, `zero`, `dust`, `large_review`, `pre_mainnet`, `is_1sun_dust`, and `is_trx_4444_artifact` identically across both schemas.
- Never alter L0 schemas (`illicit.*`, `licit.*`).

## Done when

- `python -m src.scripts.etl.transform.clean.tests.test_clean` passes (verified).
- User reviews & executes `01_clean_transactions` → `02_clean_wallet_hops` → `03_clean_indexes` → `nflow`.
- `clean_nflow.csv` reconciles `n_in - n_out == n_dropped` and `deduped_rows == 26,189,701`.
