# Step 8 — Conclusion in context

- **Status:** in_progress
- **Blocked by:** Steps [1](../01_response_factor_groups/main.md)–[7](../07_effect_size/main.md)
- **Blocks:** phase-2 weight calibration
- **Updated:** 2026-11-20

## Objective

Turn the results into a rule-level verdict in context: supported, not supported, or inconclusive. Separate mean-difference evidence from threshold-rule evidence.

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

## Hypothesis folders

| Hypothesis | Folder | Status | Focus |
| --- | --- | --- | --- |
| H1 | `H1/main.md` | blocked | deferred; not in phase-1 scope |
| H2 | `H2/main.md` | in_progress | lifetime + burst |
| H3 | `H3/main.md` | blocked | deferred; not in phase-1 scope |
| H4 | `H4/main.md` | blocked | Jaccard + coverage |
| H5 | `H5/main.md` | blocked | deferred; not in phase-1 scope |
| H6 | `H6/main.md` | in_progress | CV + direction |

## Shared tasks

| File | Status | Blocked by | Output |
| --- | --- | --- | --- |
| `01_rule_support_verdicts.md` | blocked | Steps 5–7 | H2/H4/H6 verdicts |
| `02_limitations.md` | todo | — | limitations section |
| `03_reporting_template.md` | todo | — | result sentence |
| `04_next_phase_handoff.md` | todo | — | weight/threshold plan |
| `05_artifact_manifest.md` | todo | — | outputs list |
