# Test plan — Step 2

**Snapshot:** online profile 2026-11-20T10:57Z; overlap 11:12Z. Counts are live and drift; freeze an extract before testing.

**Responses.** Primary `log1p(tx_lifetime_days)` (≥2 events); secondary `log1p(cv_delta_t)` (≥5 events); `burst_ratio` and `jaccard_index` descriptive.

**H0/Ha — current frame (licit not clean).** H0_U: μ_illicit = μ_suspicious = μ_unlabeled. Ha_U: at least one mean differs.
**H0/Ha — target frame (after licit cleaning).** H0_L: μ_illicit = μ_suspicious = μ_licit. Ha_L: at least one mean differs. Step 2 is **in progress** until H0_L can be run; use H0_U and name the substitution.

**Alpha and family.** α = 0.05. Holm over the two omnibus tests (primary, secondary); a separate Holm family for pairwise comparisons.

**Dependence.** All 5,931 seeds are blacklisted, so seed permutation cannot generate a valid null for illicit vs suspicious without breaking cluster integrity. Primary contrast after cleaning is illicit vs licit; suspicious is nested/descriptive. Use seed-cluster bootstrap CIs; if per-arm clusters are few, report descriptive or use a wild cluster bootstrap. Do not use i.i.d. F-tests.

**Test ladder.** Welch ANOVA + Games–Howell; Kruskal–Wallis + Dunn only on independent arms and only as a distributional sensitivity (it does not test the mean H0). Classic ANOVA is reference only. Non-parametric tests do not fix dependence.

**Basis.** NIST/SEMATECH §7.4.2.2; SciPy `f_oneway`, `mannwhitneyu`, `kruskal`; Parsons et al. 2018; Cameron & Miller 2015; Abadie et al. 2023.

**Rule caveats.** H2 has two conjuncts; burst is descriptive, so a mean test alone cannot validate H2. H6 is currently opposite the premise (illicit CV highest); the two-sided omnibus is a falsification test, not confirmation.

**Sample.** Use all eligible illicit wallets (≈6,300), then 50,000 per comparison arm, seed-cluster sampled. 500,000 per arm is infeasible.

**Blocked:** local PostgreSQL down; licit cleaning.
