# Seed-cluster permutation

- **Status:** blocked
- **Blocked by:** Step 4 independence verdict
- **Blocks:** Step 7
- **Owner:** subagent
- **Output:** permutation result
- **Updated:** 2026-11-20

## Objective

Permute group labels at the seed level or use a cluster bootstrap to quantify uncertainty without i.i.d. assumptions.

## Resources / context

- `docs/context/independence.md`
- `outputs/cohorts/cohort_wallet_table.csv`
- SciPy/NumPy

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `scripts/seed_permutation.py` | seed-level permutation |
| create | `outputs/tests/permutation.csv` | permutation p and CI |

## Implementation points

- Resample seeds, not wallets.
- Keep group sizes fixed where appropriate.
- Report iterations and seed.

## Done when

- Resampling unit is seeds.
- CI and permutation p are reported.
