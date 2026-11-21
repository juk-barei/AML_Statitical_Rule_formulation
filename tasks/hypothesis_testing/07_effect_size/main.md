# Step 7 — Effect size

- **Status:** todo
- **Blocked by:** [Step 5](../05_omnibus_test/main.md), [Step 6](../06_posthoc/main.md)
- **Blocks:** [Step 8](../08_conclusion/main.md)
- **Updated:** 2026-11-20

## Objective

Report practical magnitude, not only significance: eta-squared/omega-squared, Cliff’s delta, and bootstrap CIs.

## Resources / context

- `outputs/tests/omnibus.csv`
- `outputs/tests/posthoc.csv`
- NIST/SEMATECH effect-size guidance

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/effects/effect_sizes.csv` | effect-size table |
| update | `docs/context/test_plan.md` | effect-size record |

## Implementation points

- Report eta/omega squared.
- Report Cliff’s delta and CI.
- Do not stop at p-values.

## Hypothesis folders

| Hypothesis | Folder | Status | Focus |
| --- | --- | --- | --- |
| H1 | `H1/main.md` | blocked | deferred; not in phase-1 scope |
| H2 | `H2/main.md` | todo | lifetime + burst |
| H3 | `H3/main.md` | blocked | deferred; not in phase-1 scope |
| H4 | `H4/main.md` | blocked | Jaccard + coverage |
| H5 | `H5/main.md` | blocked | deferred; not in phase-1 scope |
| H6 | `H6/main.md` | todo | CV + direction |

## Shared tasks

| File | Status | Blocked by | Output |
| --- | --- | --- | --- |
| `01_eta_omega_squared.md` | blocked | Step 5 | effect-size table |
| `02_cliffs_delta.md` | blocked | Step 6 | pairwise effects |
| `03_bootstrap_ci.md` | blocked | Step 5 | bootstrap CIs |
| `04_reporting_effect_sizes.md` | todo | — | reporting template |
