# Step 7 — Effect size

- **Status:** todo
- **Blocked by:** [Step 5](../05_omnibus_test/main.md), [Step 6](../06_posthoc/main.md)
- **Blocks:** [Step 8](../08_conclusion/main.md)
- **Updated:** 2026-11-22

## Objective

Report practical magnitude, not only significance: eta-squared/omega-squared, Cliff’s delta, and bootstrap CIs.

**Test path:** both effect sizes are reported when the branch splits; they answer different questions. Map: [`../test_paths.md`](../test_paths.md).

## Resources / context

- `outputs/hypothesis_testing/shared/omnibus.csv`
- `outputs/hypothesis_testing/shared/posthoc.csv`
- NIST/SEMATECH effect-size guidance

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/hypothesis_testing/shared/effect_sizes.csv` | effect-size table |
| update | `docs/context/test_plan.md` | effect-size record |

## Implementation points

- Report eta/omega squared.
- Report Cliff’s delta and CI.
- Do not stop at p-values.

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
| `01_eta_omega_squared.md` | blocked | Step 5 | effect-size table |
| `02_cliffs_delta.md` | blocked | Step 6 | pairwise effects |
| `03_bootstrap_ci.md` | blocked | Step 5 | bootstrap CIs |
| `04_reporting_effect_sizes.md` | todo | — | reporting template |
