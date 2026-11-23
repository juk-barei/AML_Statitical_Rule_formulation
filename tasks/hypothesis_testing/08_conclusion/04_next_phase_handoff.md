# Phase-2 handoff

- **Status:** todo
- **Blocked by:** —
- **Blocks:** phase 2
- **Owner:** subagent
- **Output:** weight/threshold plan
- **Updated:** 2026-11-20

## Objective

Hand off supported features to weight estimation (logistic regression, mutual information, or ROC/PR optimisation) and threshold tuning.

## Resources / context

- `docs/flow.md` — test and weight plan
- `outputs/hypothesis_testing/shared/rule_verdicts.csv`
- `docs/hypothesis.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `docs/context/phase2_handoff.md` | weights and thresholds plan |

## Implementation points

- Hand off only supported features.
- List weight methods and threshold tuning.
- Do not call unsupported rules validated.

## Done when

- Dependencies are listed.
- Unsupported rules are not handed off as validated.
