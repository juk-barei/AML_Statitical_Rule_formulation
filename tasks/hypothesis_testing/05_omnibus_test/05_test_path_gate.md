# Test path gate

- **Status:** todo
- **Blocked by:** `04_transform_decision.md`
- **Blocks:** `01_welch_anova.md`, `02_kruskal_wallis.md`
- **Owner:** subagent
- **Output:** test-path table in `docs/context/test_plan.md`
- **Updated:** 2026-11-22

## Objective

Declare which branch of Steps 5–7 is live for each response, from Step 4 evidence and before any p-value is computed. This is the only place the parametric/non-parametric branch is opened or closed.

## Resources / context

- `docs/context/assumptions.md` — Step 4 verdict
- `docs/context/test_plan.md` — pre-specified ladder
- `tasks/hypothesis_testing/test_paths.md` — branch map
- `04_assumptions/04_transform_decision.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/test_plan.md` | per-response chosen path |
| update | `tasks/hypothesis_testing/05_omnibus_test/main.md` | branch task statuses |

## Implementation points

- Parametric branch: normality acceptable after `log1p` and Levene tolerable → Welch primary, Games–Howell, KW stays sensitivity.
- Non-parametric branch: residual non-normality not fixed by transform → KW primary for the distribution, Dunn for pairs, Welch demoted to reference. Mean `H0` is then **not** tested.
- Dependence applies to both: seed-cluster permutation/bootstrap always runs.
- Record per hypothesis and response: primary, sensitivity, reference.
- Set each branch task to `in_progress` or `blocked — test path not selected`; never mark an untaken branch `done`.
- `H4` stays on the descriptive path while support is 13 passes (`H4.md`).

## Done when

- `test_plan.md` names the live path per hypothesis and response.
- No branch is left ambiguous.
- The table exists before any Step 5 result is computed.
