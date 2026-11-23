# Limitations

- **Status:** todo
- **Blocked by:** —
- **Blocks:** publication
- **Owner:** subagent
- **Output:** limitations section
- **Updated:** 2026-11-20

## Objective

State licit-pending status, graph-derived non-independence, sampling/coverage differences, blacklist drift, and address-vs-entity limits.

## Resources / context

- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `docs/context/independence.md`
- `docs/context/sampling_evaluation.md`
- `docs/hypothesis.md` — H2/H4/H6 definitions and thresholds

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/final_report.md` | limitations section |

## Implementation points

- Licit pending; do not call unlabeled licit.
- Graph-derived non-independence.
- Blacklist drift and address-vs-entity limits.

## Done when

- Limitations are specific.
- No unsupported generalization.
