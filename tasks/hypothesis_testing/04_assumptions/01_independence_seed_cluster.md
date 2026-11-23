# Independence and seed clustering

- **Status:** blocked
- **Blocked by:** Step 1 cohort
- **Blocks:** Step 5
- **Owner:** subagent
- **Output:** dependence verdict
- **Updated:** 2026-11-20

## Objective

Document that suspicious is graph-derived from blacklisted seeds and that hop rows are not independent. Decide seed-cluster inference or a nested/descriptive arm.

## Resources / context

- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `AGENTS.md` — data authority, cohort priority, task rules
- `docs/context/cohort_contract.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `docs/context/independence.md` | clustering and inference rule |

## Implementation points

- All seed addresses are blacklisted; suspicious is graph-derived.
- 194,674 multi-hop and 216,776 multi-seed wallets.
- Use seed-cluster inference; non-parametric does not fix dependence.

## Done when

- Clustering unit is named.
- Non-parametric caveat is explicit.
- Test path follows the verdict.
