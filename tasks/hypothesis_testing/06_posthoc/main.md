# Step 6 — Post-hoc comparisons

- **Status:** todo
- **Blocked by:** [Step 5](../05_omnibus_test/main.md)
- **Blocks:** [Step 7](../07_effect_size/main.md), [Step 8](../08_conclusion/main.md)
- **Updated:** 2026-11-22

## Objective

Identify which group means or distributions differ, with family-wise error control.

## Resources / context

- `outputs/tests/omnibus.csv`
- `docs/context/test_plan.md`
- statsmodels/SciPy post-hoc docs

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/tests/posthoc.csv` | pairwise results |
| update | `docs/context/test_plan.md` | post-hoc record |

## Implementation points

- Control family-wise error.
- Report each pair with CI.
- Separate Welch and KW paths.

## Hypothesis trackers

| Hypothesis | Tracker | Status | Focus |
| --- | --- | --- | --- |
| H2 | [`H2.md`](../H2.md) | todo | lifetime + burst |
| H4 | [`H4.md`](../H4.md) | blocked | Jaccard + coverage |
| H6 | [`H6.md`](../H6.md) | todo | CV + direction |

`H1`, `H3`, `H5` are deferred and have no tracker; see [`../DEFERRED.md`](../DEFERRED.md).

## Shared tasks

| File | Status | Blocked by | Output |
| --- | --- | --- | --- |
| `01_games_howell.md` | blocked | Step 5 Welch | pairwise table |
| `02_dunn.md` | blocked | Step 5 KW | pairwise table |
| `03_pairwise_effect_cis.md` | blocked | Step 5 | effect + CI table |
| `04_multiplicity_control.md` | todo | — | correction policy |
