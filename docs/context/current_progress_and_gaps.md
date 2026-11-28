# Current progress vs the 8-step ANOVA workflow
<!-- Last updated: 2026-11-28 | Edit count: 2 -->

Status: **completed** / **in progress** / **not started**.
Frozen dataset: `phase1_transformed_transform_20261127T224625Z` (`9,876,867` wallets; `17,046` illicit, `3,959,525` suspicious, `5,180,495` licit, `719,801` unlabeled).

| Step | Status | Evidence / gap |
| --- | --- | --- |
| 1. Response, factor, groups | **In progress** | L1–L3 ETL and frozen clean 4-arm `cohort_wallet.parquet` + `wallet_features.parquet` complete. Remaining: run `profile_stage --stage transformed` + `compare_stages` audit and `1.2_LICIT_EDA.ipynb`. |
| 2. H0, Ha, α | **In progress** | `docs/context/test_plan.md` updated for clean `H0_L`/`Ha_L` (`illicit` vs. `licit`) on the frozen snapshot; finalize `05_licit_hypotheses.md` sign-off. |
| 3. Explore boxplots/means | **Not started (unblocked)** | `eda/profile` raw plots done; transformed/compare profile plots + Lecture 02 `eda/{univariate,bivariate,multivariate}` modules and notebook refactor remain. |
| 4. Assumptions | **Not started** | No Shapiro–Wilk, Levene, Q–Q, or seed-cluster dependence diagnostics yet. |
| 5. F-test / Welch / KW | **Not started** | No omnibus test scripts in `src/scripts/hypothesis_testing/`. |
| 6. Post-hoc Games–Howell / Dunn | **Not started** | No pairwise post-hoc scripts implemented. |
| 7. Effect size η² / ω² / Cliff's δ | **Not started** | No seed-cluster bootstrap CIs or η²/ω² implemented. |
| 8. Conclusion in context | **Not started** | No final `verdict.md` reports for `H2`, `H4`, `H6`. |

**Key analytical cautions (frozen snapshot):** Licit cleaning is **complete** (`1,434,186` overlaps removed), but activity asymmetry is severe (`elig_h2_ge5` retains `74.9%` of illicit vs. `0.73%` of licit), `H4` has only `52 / 13,417` illicit passes (`0.39%` vs. `6.71%` licit), and `H6` has only `24 / 15,218` illicit passes (`h6_pass_all`).
