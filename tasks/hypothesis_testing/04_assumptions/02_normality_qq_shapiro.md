# Normality: Q–Q and Shapiro

- **Status:** blocked
- **Blocked by:** Step 1 response
- **Blocks:** `04_transform_decision.md`
- **Owner:** subagent
- **Output:** Q–Q/Shapiro results
- **Updated:** 2026-11-20

## Objective

Inspect residual Q–Q plots and Shapiro–Wilk per group. Do not use Shapiro as a hard gate at huge n.

## Resources / context

- `docs/context/assumptions.md`
- SciPy `shapiro` docs
- NIST/SEMATECH

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/diagnostics/normality.csv` | Q–Q/Shapiro results |
| update | `docs/context/assumptions.md` | normality findings |

## Implementation points

- Residual Q–Q per group.
- Shapiro is not a hard gate at huge n.
- Report skew and tails.

## Done when

- Plots are saved.
- Skew and tail behavior are described.
