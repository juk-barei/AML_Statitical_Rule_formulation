# Step 8 — Conclusion in context

- **Status:** in_progress
- **Blocked by:** Steps [1](../01_response_factor_groups/main.md)–[7](../07_effect_size/main.md)
- **Blocks:** phase-2 weight calibration
- **Updated:** 2026-11-22

## Objective

Turn the results into a rule-level verdict in context: supported, not supported, or inconclusive. Separate mean-difference evidence from threshold-rule evidence.

**Test path:** verdicts consume whichever branch Steps 5–7 declared. Map: [`../test_paths.md`](../test_paths.md). Deferred `H1`/`H3`/`H5`: [`../DEFERRED.md`](../DEFERRED.md).

## Resources / context

- Steps 1–7 outputs
- `docs/hypothesis.md` — H2/H4/H6 definitions and thresholds
- `docs/flow.md` — test and weight plan
- `docs/context/test_plan.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `docs/context/final_report.md` | rule verdicts and limitations |
| update | `tasks/08_conclusion/main.md` | step status |

## Implementation points

- Separate mean evidence from threshold evidence.
- Name licit substitution.
- State limitations explicitly.

## Hypothesis trackers

| Hypothesis | Tracker | Status | Focus |
| --- | --- | --- | --- |
| H2 | [`H2.md`](../H2.md) | in_progress | lifetime + burst |
| H4 | [`H4.md`](../H4.md) | blocked | Jaccard + coverage |
| H6 | [`H6.md`](../H6.md) | in_progress | CV + direction |

`H1`, `H3`, `H5` are deferred and have no tracker; see [`../DEFERRED.md`](../DEFERRED.md).

## Shared tasks

| File | Status | Blocked by | Output |
| --- | --- | --- | --- |
| `01_rule_support_verdicts.md` | blocked | Steps 5–7 | H2/H4/H6 verdicts |
| `02_limitations.md` | todo | — | limitations section |
| `03_reporting_template.md` | todo | — | result sentence |
| `04_next_phase_handoff.md` | todo | — | weight/threshold plan |
| `05_artifact_manifest.md` | todo | — | outputs list |
