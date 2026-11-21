# Feature-definition audit

- **Status:** done
- **Blocked by:** —
- **Blocks:** Steps 3–5
- **Owner:** subagent
- **Output:** feature fix list
- **Updated:** 2026-11-20

## Objective

Reconcile implemented features with `docs/hypothesis.md`: H2 burst uses USDT-only vs in+out; H6 ignores direction; H4 coverage; activity floor; drop `hex_address`.

## Resources / context

- `docs/hypothesis.md` — H2/H4/H6 definitions and thresholds
- `src/notebooks/1.1_ILLICIT_EDA.ipynb` — current EDA and executed outputs
- `docs/untitled.md`
- `src/scripts/ETL.py` — ingestion, loader, and source-link behavior

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `docs/context/feature_audit.md` | feature drift and fix list |
| update | `src/notebooks/1.1_ILLICIT_EDA.ipynb` | only after fixes are approved |

## Implementation points

- H2 burst: USDT-only vs in+out.
- H6: direction is currently unused.
- H4 coverage and activity floor; drop `hex_address`.

## Done when

- Each drift has a file/line reference.
- Fix or explicit defer decision.
- No silent redefinition.
