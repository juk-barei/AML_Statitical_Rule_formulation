# Rule support verdicts

- **Status:** blocked
- **Blocked by:** Steps 5–7
- **Blocks:** phase 2
- **Owner:** subagent
- **Output:** H2/H4/H6 verdicts
- **Updated:** 2026-11-20

## Objective

For each rule, separate (a) mean feature difference from (b) threshold pass-rate support. Do not claim a rule works from a significant mean alone.

## Resources / context

- `outputs/tests/` results
- `docs/hypothesis.md` thresholds
- `docs/context/step_1_profiling_samples.md` — cohort/response decisions

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/report/rule_verdicts.csv` | H2/H4/H6 verdicts |
| update | `docs/context/final_report.md` | verdict section |

## Implementation points

- Mean difference ≠ rule support.
- Report pass rates and denominators.
- Name inverted or unsupported rules.

## Done when

- Each rule has a verdict and evidence.
- Threshold support is reported.
- Inversions are named.
