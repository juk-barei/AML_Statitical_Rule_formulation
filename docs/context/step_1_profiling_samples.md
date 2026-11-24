# Step 1 — Response, factor, and groups

> **Snapshot update (2026-11-20):** the online DB profile is in `docs/context/statistical_info.md` and `docs/context/cohort_contract.md`. The counts below are the older local-mirror snapshot; do not mix them with online counts.

**Scope:** Task 1 of the 8-step ANOVA workflow in `Lecture_05_ANOVA.pdf`, applied to the TRON AML wallet data. This is a design specification, not a test. It fixes the unit, response, factor, groups, and independence structure before H0/Ha are written.

**Data authority:** all counts below come from the local PostgreSQL mirror that `1.1_ILLICIT_EDA.ipynb` actually reads (verified 2026-11-19: 2,125,343 accounts; 5,023,780 transactions; 1,736,551 hop rows). The CSV export in `datasets/` is a smaller, stale snapshot and is **not** used for inference.

**One-line answer.** Response: a wallet-level continuous rule feature — primary `log1p(tx_lifetime_days)` (H2), secondary `log1p(cv_delta_t)` (H6). Factor: `wallet_class`, fixed, 3 levels. Groups: **illicit**, **suspicious**, and **licit** — but the third implemented level is **unlabeled**, not licit, because the licit database is not ingested. Unit: a wallet; hop depth is nested inside suspicious, not crossed with class.

## 1. What step 1 must decide

Step 1 fixes five things: (a) the experimental unit, (b) the response variable and its eligibility/scale, (c) the factor(s) and levels, (d) the group-construction rule with label provenance, and (e) the independence/nesting structure. If these are implicit, the later F-test answers an ambiguous question. Definitions follow the NIST/SEMATECH one-way ANOVA model and Larson's applied description [1], [2], [3].

| Term | Definition | This dataset |
|---|---|---|
| Response | Single continuous outcome measured once per experimental unit | One rule metric per wallet, computed without `group` or hop |
| Factor | Categorical independent variable whose levels define groups | `wallet_class` |
| Levels | The k categories compared by the F-test | illicit, suspicious, licit (implemented: unlabeled) |
| Experimental unit | Smallest unit receiving one level and contributing one response | **Wallet**, not a transaction or hop row |
| Replication | Independent units within a level; equal n = balanced | n per class *after* response eligibility |
| Fixed effect | Levels are the only ones of interest | `wallet_class` |
| Random effect | Levels are sampled from a population of levels | `seed_cluster` |
| Nested vs crossed | Nested: B exists only inside one A. Crossed: every A×B cell can occur | Hop depth is **nested** in suspicious; class × hop is not crossed |

## 2. Snapshot reconciliation (read this before any number)

The repo contains two incompatible snapshots. Mixing them was the main error in the first draft of this document.

| Quantity | PostgreSQL mirror (analysis) | `datasets/*.csv` (stale export) |
|---|---:|---:|
| Accounts / universe | 2,125,343 | 664,385 |
| Transactions | 5,023,780 | 1,804,853 |
| Blacklisted wallets | 11,418 | 8,946 |
| Hop rows / hop wallets | 1,736,551 / 1,342,721 | 72,912 / 62,166 |
| Distinct `seed_address` values | 5,931 | 478 |
| Wallet at hop 0 | 478 | 478 |
| Hop direction | BACKWARD 925,394; FORWARD 811,157 | FORWARD only |
| Illicit with any transaction | 6,709 / 11,418 (58.8%) | 1,922 / 8,946 (21.5%) |
| Suspicious | 1,338,468 | 61,276 |
| Unlabeled | 775,457 | 594,166 |

The notebook itself flags the CSV as partial. Every count below is mirror-based; the CSV is retained only as a provenance check.

## 3. Is the proposed three-group classification correct?

**Verdict: partly correct.** The three-tier taxonomy is the right target for a graded risk score, but two operational definitions are wrong and one is incomplete.

**What is correct.**
- Three tiers are appropriate because the project produces a score, not a binary verdict.
- The priority rule is correct: blacklist wins over hop proximity. A hop-3 wallet that is also blacklisted is illicit, not suspicious.
- `suspicious = min(hop_level) 1–5, not blacklisted` matches the traversal and is a reasonable *proximity* label.

**What must change.**

1. **The third implemented cohort is not licit.** `1.1_ILLICIT_EDA.ipynb` says explicitly: "The third cohort is called **background**, not 'licit'." (retired term; now **unlabeled**.) The mirror agrees: the three cohorts are illicit 11,418 (0.54%), suspicious 1,338,468 (62.98%), unlabeled 775,457 (36.49%). The licit link is defined in `ETL.py` but never called, and `1.2_LICIT_EDA.ipynb` is empty. 
Response: This is because I have not accessed it. The one u got from notebook is old info before I get the link to licit address. You can check this claim by using the environment variable I give you in .env.example in dev/ folder. Note: you do not have access to the .env file directly. This should be a dedicated subtask for you to profile illicit and licit data. You can do so by writing a scripts file to profile them (shape, relation, columns, type of data in each colunns), does 3 groups really licit fit and whether they should indeed become 3 groups before you do the task 1. You are allowed to access web and research skill for this case. After completing this subtask, write to docs/context/statistical_info.md. Additional profiling should be done in scripts folder so I know how you get these number from. Cite the scripts file and line of code when you use result of the code logic. Update this to AGENTS.md to always do that. Update to AGENTS.md that scripts folder is for all helper functions and small profiling from agents or ppl while notebooks is for real code and be used at official.
Also update AGENTS.md that subtask is for subagents and activate skills of each agents accordingly with fact check on current fact always after getting insights to see for contradiction and avoid overseeing gaps or conflicted info. anotehr update is always write concise docs file (under 200 words) and only go over when absolutely neccessary. One last is that a subtask is one md file or update on existing files.

2. **Unlabeled contains direct blacklisted counterparties.** Of 409,632 distinct counterparties of blacklisted transactions, 10.0% are labelled unlabeled, 88.9% suspicious, and 1.0% illicit. A set containing wallets that directly transacted with blacklisted wallets cannot be "wallets that have not interacted with illicit users." The correct name is **unlabeled**, not licit.
-> write scripts file of logic you used to get these numbes and other numbers and insights of the answers. This is a subtask for subagents.

3. **"Never interacted" is absence of evidence.** The hop graph is bidirectional (925,394 BACKWARD; 811,157 FORWARD) and capped at hop 5. A wallet at hop ≥6, reachable only outside the crawl, or on the unobserved side of a transaction is neither illicit nor suspicious; its interaction status is unknown.

4. **Suspicious is not an independent sample.** All 478 hop-0 wallets and all 5,931 distinct `seed_address` values are blacklisted, so the suspicious set is graph-derived from the illicit set. 194,674 wallets appear at more than one hop level, 216,776 are reachable from more than one `seed_address`, and 3,775 blacklisted wallets appear at hop ≥1. Group membership is constructed from the illicit set, so independence is violated by design, not by chance.

5. **The illicit arm is still selected.** 6,709 of 11,418 blacklisted wallets (58.8%) have any transaction; 4,709 (41.2%) have none; 5,709 (50.0%) have ≥5 events. Behavioural comparisons run on the observable half of the illicit arm.

6. **Hop 1–5 is a gradient, not one population.** Suspicious median lifetime is 69.4, 34.9, 25.5, 23.7 and 17.7 days at hops 1–5; CV is 1.27, 1.18, 1.17, 1.26 and 1.10. Hop sizes are 278,469, 279,048, 285,273, 257,111 and 238,567. The gradient is real but bounded; pooling is defensible only with hop as a nested sensitivity factor.

| Corrected group | Operational rule | n | Share | Certainty | Role |
|---|---|---:|---:|---|---|
| `illicit` | TronScan blacklist, `label = 1` | 11,418 | 0.54% | Asserted positive | Target arm |
| `suspicious` | `min(hop_level) ∈ 1..5`, not blacklisted | 1,338,468 | 62.98% | Inferred proximity | Nested arm |
| `unlabeled` | Universe minus illicit and suspicious | 775,457 | 36.49% | No label | Baseline only |
| `licit` | Second cloud DB (`LICIT_ONLINE_DATABASE_LINK`) | 0 ingested | — | External | Blocked |

**Decision.** Keep three levels, but do not call the complement licit. Until the second cloud database is ingested, report `illicit / suspicious / unlabeled` and state that the design has two labelled arms plus an unlabeled baseline. The external licit arm is the only defensible third level. I have not ingested but I will soon.
as of now, both licit and illict online db are updated with new info that even my local ingestio of illicit is  outdated. I will have to select fixed amount for this phase but I have not profiled info sampling of samples yet. This could be a dedicated sub task that you access the online dbs profiling overview and update me and recommend fixed amount to work for now while letting the dbs online continue to ingest. look into if there will be problem for me to ingest illicit more to existing one or not based on logic in ingesting file.( now i updated link to licit cuz I plan to ingest licit but i used the same code logic for illict ingestion last time). doubt the sampling of those data collection and evalute them as well. write update to existing or new file if not exist for this answer.

## 4. Response variable

A response must be continuous, measured per wallet, computable without `group` or hop, defined for enough wallets in every arm, and not degenerate. The scale is part of the definition: heavy-tailed money/time features are analysed on `log1p`, with original units reported for interpretation.

| Response | Meaning | Eligibility | n illicit | n suspicious | n unlabeled | Original median I / S / U | Verdict |
|---|---|---|---:|---:|---:|---|---|
| `log1p(tx_lifetime_days)` | log(1 + last transaction − first transaction) | ≥2 events | 6,324 | 528,354 | 169,640 | 93.1 / 31.6 / 10.6 days | **Primary** |
| `log1p(cv_delta_t)` | log(1 + SD ÷ mean inter-arrival time) | ≥5 events, CV defined | 5,695 | 144,410 | 32,340 | 3.49 / 1.45 / 1.21 | **Secondary** |
| `burst_ratio` | max 1-hour USDT volume ÷ total USDT volume | ≥5 USDT events | 4,640 | 82,214 | 24,749 | 0.958 / 0.992 / 1.00 | Descriptive only |
| `jaccard_index` | TRX funders vs USDT recipients, Jaccard | both sets non-empty | 4,938 | 73,562 | 6,109 | 0 / 0 / 0 | Descriptive only |

**Primary — `log1p(tx_lifetime_days)` (H2).** It has the broadest illicit coverage (55.4% of the arm), the clearest ordered medians (93.1 > 31.6 > 10.6 days), and the log transform removes most of the skew: log-mean 4.15 / 3.36 / 2.49, log-SD 2.02 / 1.78 / 1.87, skew −0.38 / −0.10 / +0.29. It maps directly to H2's lifetime construct and uses no group information.

**Secondary — `log1p(cv_delta_t)` (H6).** It has adequate support (5,695 illicit; 144,410 suspicious; 32,340 unlabeled), but only 10.8% of suspicious wallets are eligible and the ordering is **opposite** the H6 premise: illicit CV is highest (median 3.49), not lowest. Log-mean is 1.57 / 0.98 / 0.81; log-SD 0.45 / 0.45 / 0.26. Treat it as a secondary test that may falsify H6, not as confirmation.

**Descriptive only — `burst_ratio` and `jaccard_index`.** Burst is estimable only for the small USDT-active minority (6.1% of suspicious; 3.2% of unlabeled). Jaccard is zero for 77.7% of eligible illicit wallets, 92.3% of suspicious, and 96.1% of unlabeled; only 13 illicit wallets pass J ≥ 0.5. Neither is a valid primary ANOVA response under the current formulas; they need redesign before testing.

**The rule is a threshold, not a mean.** Even the primary ANOVA tests mean log-lifetime, not the H2 rule "lifetime ≤ 7 days and burst ≥ 75%." The mean test is a **precursor** ("do the groups differ on the feature?"), not a rule verdict. Rule verdicts require pass-rate or tail-quantile tests. This distinction is essential: a feature can have a significant mean difference while the threshold rule has no support.

**Support warning.** The current rules are not supported in the expected direction before calibration:

- **H2 pass rates (among 731,508 wallets with ≥1 USDT event; 6,643 illicit, 361,344 suspicious, 363,521 unlabeled):** illicit 22.0%, suspicious 55.6%, unlabeled 82.4% before the activity floor; with the ≥5-USDT-event floor, 8.0%, 2.6%, 1.4%. The floor reverses the ranking, so the result is fragile to the eligibility rule.
- **H4 pass rates (among both-set eligible wallets):** 13 / 4,938 illicit (0.26%), 3,258 / 73,562 suspicious (4.43%), 223 / 6,109 unlabeled (3.65%). The rule is inverted relative to its premise.
- **H6 pass rates (among wallets with ≥5 events):** 0 / 5,709 illicit; 859 / 144,608 suspicious (0.59%); 176 / 32,447 unlabeled (0.54%). There is no illicit support at CV < 0.15.

**Selection warning.** Response availability is not random: illicit coverage ranges from 40.6% (burst) to 55.4% (lifetime); suspicious coverage ranges from 6.1% to 39.5%. Every response must carry an n-flow table (group × eligibility filter). Without it, the F-test compares who has data, not who is risky.

**Choice rule.** The primary was selected on construct validity, coverage, ordered medians, and post-transform distribution shape — not on p-values. All four responses are still reported; if treated as a family, apply Holm correction.

## 5. Factor, groups, and nesting

- **Factor 1 — `wallet_class` (fixed, 3 levels).** Levels are the corrected taxonomy above. The factor is fixed because these are the only classes of interest, not a random sample of classes.
- **Factor 2 — `hop_band` (nested, 5 levels).** `hop_band ∈ {1,2,3,4,5}` exists only inside suspicious. It is not crossed with class: licit has no hop, and hop 0 is illicit. A `class × hop` factorial therefore has structurally empty cells; its interaction is not estimable.
- **Blocking/sensitivity — `activity_band`.** USDT event-count decile, used for matched comparisons because every response correlates with activity volume. Do not fit a full `class × decile` factorial; use stratification, matching, or a covariate.
- **Random/cluster effect — `seed_cluster`.** All 5,931 distinct `seed_address` values are blacklisted; 478 wallets appear at hop 0; 216,776 wallets are reachable from more than one seed. Inference should be at the seed level (cluster bootstrap, permutation over seeds, or a mixed model), not at the 1.34M wallet or 1.74M hop-row level. Treating hop rows as independent observations is pseudoreplication.

**Rejected model.** A 3 × 6 two-way ANOVA of class × hop depth. It cannot be estimated because the cells are empty by construction. The correct structure is one-way class, plus a within-suspicious hop trend or hop-band sensitivity analysis. Incomplete factorial layouts are technically fittable, but the interaction is not cleanly interpretable here.

## 6. Test consequences

The nominal step-5 test is one-way ANOVA. After the log transform, the primary response is much better behaved than the raw data, but the design still fails the independence assumption:

- **Variance:** lifetime log-SD ratio 1.13 (2.02 vs 1.87) is acceptable; CV log-SD ratio 1.76 (0.45 vs 0.26) is not. Raw lifetime SD is 1,505 / 433 / 267 days.
- **Normality:** log-lifetime skew is −0.38 / −0.10 / +0.29, acceptable in large samples; CV log-skew is 0.46 / 1.10 / 0.29.
- **Non-independence:** suspicious is graph-derived from the same blacklist; 216,776 wallets share multiple seeds; 194,674 appear at multiple hop levels.
- **Unbalanced n:** 11,418 vs 1,338,468 vs 775,457 before eligibility, and different denominators after each filter.

Pre-specify, in this order:

1. **Welch ANOVA** on `log1p(tx_lifetime_days)` as the omnibus test (does not assume equal variances).
2. **Games–Howell** for pairwise comparisons.
3. **Kruskal–Wallis + Dunn** on the untransformed or ranked response as a sensitivity analysis.
4. **Seed-cluster bootstrap CIs and Cliff's delta** as the headline effect evidence.
5. **η² or ω²** for effect size; report exact *p*, both df, and the post-hoc result.

Classic ANOVA may be reported as a reference, not as the sole test. If the licit database arrives, first test whether its sampling frame matches. If it does not, do not pool it into the same ANOVA: compare illicit vs suspicious within-frame and report licit as an external benchmark.

## 7. Step-1 record and handoff

- [x] Unit = wallet; one row per wallet; no hop row or transaction is an observation.
- [x] Class rule with precedence: illicit > suspicious > unlabeled.
- [x] n per class and n-flow per response.
- [x] Response formulas, log scale, and eligibility gates.
- [x] Nesting: class fixed; hop nested in suspicious; seed random/cluster.
- [ ] Licit ingestion and sampling-frame check.
- [ ] H0/Ha per response (step 2).
- [ ] Assumption diagnostics (step 4).

**Blocked, not failed:** the licit arm (`ETL.py` defines `LICIT_ONLINE_DATABASE_LINK` but only calls the illicit link; `1.2_LICIT_EDA.ipynb` is empty); H4 support (13 illicit passes); H6 threshold support (0 illicit passes). These are reported as support failures, not as evidence for or against a rule.

**Step-2 handoff.** For the primary response, the hypotheses will be `H0: μ_illicit = μ_suspicious = μ_licit` versus `Ha: at least one mean differs`, at α = 0.05, with Welch/Games–Howell and rank-based sensitivity paths fixed in advance. The implemented test will use the unlabeled third level until licit is ingested, and the conclusion must name that substitution.

## 8. Evidence ledger

**Internal:** `docs/context/statistical_info.md` (proposed groups); `docs/hypothesis.md` (H2/H4/H6 and thresholds); `docs/flow.md` (test plan and weights); `src/notebooks/1.1_ILLICIT_EDA.ipynb` §0.2–0.3, §4.2, §5.2–5.4 (executed outputs for H2/H4); `src/scripts/etl/extract/main.py` L225–241, L1396, L1659–1672; PostgreSQL mirror tables `accounts`, `transactions`, `blacklisted_wallets`, `wallet_hops` (counts and features recomputed read-only). `outputs/eval_columns.md` is referenced but absent.

**External:** NIST/SEMATECH e-Handbook §7.4.2 [1], [2]; SciPy `f_oneway` [3]; statsmodels `anova_lm` [4]; Larson, *Analysis of Variance*, Circulation 2008 [5]; Elwert & Winship on endogenous selection [6]; Parsons et al. on unit-of-analysis error [7]; FATF Recommendations 20–21 [8]; Weber et al., Elliptic [9]; Elmougy & Liu, Elliptic++ [10]; Meiklejohn et al. on address clustering [11]; Tironsakkul et al. on taint analysis [12]; TRON resource model [13].

[1]: https://www.itl.nist.gov/div898/handbook/prc/section4/prc421.htm  
[2]: https://www.itl.nist.gov/div898/handbook/prc/section4/prc422.htm  
[3]: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.f_oneway.html  
[4]: https://www.statsmodels.org/stable/generated/statsmodels.stats.anova.anova_lm.html  
[5]: https://doi.org/10.1161/CIRCULATIONAHA.107.654335  
[6]: https://doi.org/10.1146/annurev-soc-071913-043455  
[7]: https://pmc.ncbi.nlm.nih.gov/articles/PMC5762161/  
[8]: https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Guidance-rba-virtual-assets-2021.html  
[9]: https://arxiv.org/abs/1908.02591  
[10]: https://doi.org/10.1145/3580305.3599803  
[11]: https://doi.org/10.1145/2504730.2504747  
[12]: https://doi.org/10.1016/j.fsidi.2022.301475  
[13]: https://developers.tron.network/docs/resource-model
