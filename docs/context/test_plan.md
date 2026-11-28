# Test plan — Step 2
<!-- Last updated: 2026-11-28 | Edit count: 2 -->

**Snapshot:** Frozen transformed Parquet snapshot `phase1_transformed_transform_20261127T224625Z` (`9,876,867` wallets; `17,046` illicit, `3,959,525` suspicious, `5,180,495` licit, `719,801` unlabeled). Query directly via DuckDB over `wallet_features.parquet` / `cohort_wallet.parquet`.

**Responses.** Primary `log1p_tx_lifetime_days` (`≥2` clean non-zero events: `16,041` illicit, `871,241` licit, `2,515,876` suspicious, `122,212` unlabeled); secondary `log1p_cv_delta_t_all` (`≥5` events & mean gap > 0: `15,218` illicit, `124,258` licit) plus OUT-only sensitivity `log1p_cv_delta_t_out`; `burst_ratio_usdt` (`elig_h2_ge5`: `12,764` illicit, `37,965` licit) and `jaccard_index` (`elig_h4`: `13,417` illicit, `135,588` licit) descriptive + binary pass-rate verdicts.

**H0/Ha — active clean frame (`_L`).**
- **Primary clean two-arm contrast:** `H0_L: μ_illicit = μ_licit` vs. `Ha_L: μ_illicit ≠ μ_licit` (two-sided), plus binary rule-verdict pass-rate contrast `P(pass | illicit)` vs. `P(pass | licit)`.
- **Three-arm omnibus (with nested caveat):** `H0_L: μ_illicit = μ_suspicious = μ_licit` vs. `Ha_L: at least one mean differs` (`suspicious` treated as seed-clustered/descriptive; `unlabeled` kept separate and never pooled into `licit`).

**Alpha and family.** `α = 0.05`. Holm over the two confirmatory continuous omnibus tests (`H2` primary, `H6` secondary); separate Holm families for pairwise comparisons and binary rule pass-rate tests.

**Dependence.** All `16,371` illicit seeds are blacklisted (`1,249,966` multi-seed wallets), so `suspicious` is not i.i.d. Primary independent contrast is **illicit vs. licit**; `suspicious` uses `primary_seed_address` cluster bootstrap CIs or descriptive nested reporting. Do not use i.i.d. F-tests or i.i.d. KW on the full suspicious set.

**Test ladder.** Welch ANOVA + Games–Howell; Kruskal–Wallis + Dunn on independent arms (`illicit` vs. `licit`) as distributional sensitivity only. Classic ANOVA is reference only. Non-parametric tests do not fix dependence.

**Rule caveats & sensitivities.** H2 is a conjunction (`burst_ratio_usdt` descriptive; report both `h2_pass_ge5` and `h2_pass_any_usdt`). H4 has rare illicit support (`52 / 13,417 = 0.39%` vs. `9,096 / 135,588 = 6.71%` licit); keep descriptive/proportion with Wilson CI and run no-dust TRX sensitivity (`NOT is_1sun_dust`). H6 is opposite the premise (`24` illicit, `611` licit pass `h6_pass_all`); treat two-sided omnibus as falsification and report `cv_delta_t_out`. Always pair TRX comparisons with `*_excl_4444` and `*_nodust` sensitivities; ban `fee_trx`.

**Sample.** Census all eligible `illicit` wallets (`12,764`–`16,041`); census or bounded stratified sample (`50,000`–`100,000`, seed-cluster sampled for `suspicious`) for large arms, with activity-band stratification reported alongside full-frame n-flow.

**Basis.** NIST/SEMATECH §7.4.2.2; SciPy `f_oneway`, `mannwhitneyu`, `kruskal`; Parsons et al. 2018; Cameron & Miller 2015; Abadie et al. 2023.
