# Alpha and multiplicity

- **Status:** done
- **Blocked by:** —
- **Blocks:** Steps 5–7
- **Owner:** subagent
- **Output:** alpha policy
- **Updated:** 2026-11-20

## Objective

Set alpha = 0.05, define the response family, and choose Holm correction for multiple responses.

## Resources / context

- NIST/SEMATECH
- `statsmodels` multiple-testing docs
- `docs/flow.md` — test and weight plan

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/test_plan.md` | alpha and Holm policy |

## Implementation points

- Alpha = 0.05.
- Family = primary + secondary responses.
- Holm correction; state before testing.

## Done when

- Family is listed.
- Correction is stated before testing.
