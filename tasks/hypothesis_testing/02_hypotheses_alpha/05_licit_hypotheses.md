# Licit-frame hypotheses

- **Status:** blocked
- **Blocked by:** licit cleaning in Step 1
- **Blocks:** H0_L execution
- **Owner:** subagent
- **Output:** updated `docs/context/test_plan.md`
- **Updated:** 2026-11-20

## Objective

Write H0_L/Ha_L for the cleaned licit frame: μ_illicit = μ_suspicious = μ_licit versus at least one mean differs. Do not substitute unlabeled without naming it.

## Resources / context

- `docs/context/test_plan.md` — current H0_U/H0_L split
- `docs/context/cohort_contract.md` — priority and cleaning rule
- `docs/context/statistical_info.md` — licit overlap
- `tasks/01_response_factor_groups/04_cohort_contract_v2.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/test_plan.md` | H0_L/Ha_L and group levels |
| update | `tasks/02_hypotheses_alpha/main.md` | status and table |

## Implementation points

- Name the three cleaned levels explicitly.
- Keep α = 0.05 and the two omnibus Holm family.
- Mark Step 2 done only when H0_L is executable.
