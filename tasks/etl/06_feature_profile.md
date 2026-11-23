# Local feature profile — C

- **Status:** blocked
- **Blocked by:** full-frame cohort/transaction join is too slow; group counts do not reconcile with `local_cohort_counts.csv`
- **Blocks:** H2/H4/H6 profiling, feature/cohort profiling comparison
- **Owner:** worker subagent + lead review
- **Output:** `outputs/etl/profile/local_feature_profile.csv`, `local_feature_nflow.csv`
- **Updated:** 2026-11-23

## Objective

Profile H2/H4/H6 wallet-level features from the local mirror without writing a
feature table. Record eligibility, zero mass, quantiles, pass counts, and the
definition assumptions (H2 token scope, H6 direction/session).

## Resources / context

- `src/scripts/etl/profile/schema.py`, `adapters.py`, `metrics.py`
- `src/scripts/etl/profile/profile_overlap_local.py` — cohort priority to mirror
- `docs/hypothesis_testing/variabe_type.md`
- accepted concepts `02`, `05`, `07`, `10`; testing reference `06`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `src/scripts/etl/profile/profile_features.py` | feature profile |
| create | `src/scripts/etl/profile/tests/test_profile_features.py` | tests |
| create | `outputs/etl/profile/local_feature_*.csv` | outputs |

## Implementation points

- H2 lifetime, USDT burst ratio, USDT event count.
- H4 Jaccard; both-set eligibility.
- H6 event count and CV; record missing direction/undefined session.
- Group by cohort priority; reconcile group counts with `local_cohort_counts.csv`.
- SQL-first, bounded smoke mode, no mirror writes, no `ingest.py` edits.

## Current result

- `profile_features.py` and `test_profile_features.py` exist; ruff/pyright and unit checks pass.
- A bounded smoke run completed earlier, but the full-frame run is blocked:
  - the cohort/transaction join is too slow for a full pass;
  - the account-only feature frame excludes 36,842 hop-only wallets that the overlap profile counts as suspicious;
  - the full group counts therefore fail reconciliation.
- Do not call the bounded feature CSV a full profile. Re-run after the cohort table is frozen.

## Done when

- A frozen cohort/frame table exists.
- Full feature profile completes within the memory/time budget.
- Group counts reconcile with the cohort profile.
- Long-format profile and n-flow outputs are snapshot-tagged.
EOF
