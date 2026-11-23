# Test paths — parametric and non-parametric

- **Status:** in_progress
- **Updated:** 2026-11-22

Steps 4–8 already carry both paths side by side. They are **not** separate
folders: one task file per path, status decides which one is live.

| Step | Shared (always runs) | Parametric (mean) | Non-parametric (distribution) |
| --- | --- | --- | --- |
| 4 | `01_independence_seed_cluster.md`, `02_normality_qq_shapiro.md`, `03_equal_variance_levene.md`, `05_missingness_eligibility.md` | `04_transform_decision.md` → `log1p`, mean test viable | `04_transform_decision.md` → rank/permutation path |
| 5 | `03_cluster_permutation.md`, `04_test_decision_rule.md`, `05_test_path_gate.md` | `01_welch_anova.md` (primary) | `02_kruskal_wallis.md` (sensitivity) |
| 6 | `03_pairwise_effect_cis.md`, `04_multiplicity_control.md` | `01_games_howell.md` | `02_dunn.md` |
| 7 | `03_bootstrap_ci.md`, `04_reporting_effect_sizes.md` | `01_eta_omega_squared.md` | `02_cliffs_delta.md` |
| 8 | `02_limitations.md`, `03_reporting_template.md`, `04_next_phase_handoff.md`, `05_artifact_manifest.md` | `01_rule_support_verdicts.md` (chosen path) | same file |

## Rules

- **Parametric here means Welch**, not classic ANOVA. Classic `f_oneway` is
  reference only (`docs/context/test_plan.md`).
- Kruskal–Wallis is a **sensitivity** test for the distribution, never the sole
  test of the mean `H0`; it does not fix dependence.
- Dependence overrides the branch: seed-cluster permutation/bootstrap runs either way.
- Step 7 is the exception — both effect sizes are reported when the branch splits,
  because `η²/ω²` and Cliff's delta answer different questions.
- The branch is chosen from Step 4 evidence **before** any p-value is computed
  (`05_omnibus_test/04_test_decision_rule.md`). Switching after results is forbidden.
- The unused branch is set to `blocked — test path not selected` in the step
  table; it is never marked `done`.

Gate lives in [`05_omnibus_test/05_test_path_gate.md`](05_omnibus_test/05_test_path_gate.md).
