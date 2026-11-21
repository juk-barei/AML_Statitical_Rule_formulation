# Bootstrap confidence intervals

- **Status:** blocked
- **Blocked by:** Step 5
- **Blocks:** Step 8
- **Owner:** subagent
- **Output:** bootstrap CIs
- **Updated:** 2026-11-20

## Objective

Bootstrap over seeds, not wallets, to respect clustering. Report 95% CIs for the chosen effect sizes.

## Resources / context

- `docs/context/independence.md`
- `outputs/cohorts/cohort_wallet_table.csv`
- bootstrap docs

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `scripts/bootstrap_effects.py` | seed-level bootstrap |
| create | `outputs/effects/bootstrap_ci.csv` | 95% CIs |

## Implementation points

- Resample seeds, not wallets.
- Report iterations and method.
- Use the same seeds across pairs.

## Done when

- Resampling unit is seeds.
- CI method and iterations are stated.
