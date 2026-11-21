# Equal variance: Levene

- **Status:** blocked
- **Blocked by:** Step 1 response
- **Blocks:** `04_transform_decision.md`
- **Owner:** subagent
- **Output:** Levene results
- **Updated:** 2026-11-20

## Objective

Run Levene’s test and report the SD ratio per response. Flag CV and raw lifetime as heteroscedastic.

## Resources / context

- `docs/context/assumptions.md`
- SciPy `levene` docs
- NIST/SEMATECH

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `outputs/diagnostics/levene.csv` | Levene and SD ratios |
| update | `docs/context/assumptions.md` | variance findings |

## Implementation points

- Levene statistic and p per response.
- Report SD ratios.
- Flag CV and raw lifetime.

## Done when

- Test statistic and p are reported.
- SD ratios are reported.
