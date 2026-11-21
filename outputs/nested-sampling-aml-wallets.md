# Nested sampling and incomplete AML labels: a phase-1 design brief

- **Slug:** `nested-sampling-aml-wallets`
- **Date:** 2026-11-21
- **Scope:** TRON illicit/licit wallet study; phase-1 hypothesis testing and label collection
- **Status:** Revised after verification; sources checked 2026-11-21

## Executive summary

1. **Treat the online databases as frames, not as probability samples of all TRON wallets.** A second-stage sample of a database is a probability sample of that database, but it is not a probability sample of the larger population unless the first-stage inclusion probabilities are known [51]. They are not recorded for a crawl or an external list. Restrict phase-1 claims to the frozen database frame, or use model-based inference and say so [20][17][15].
2. **If you sample, you are doing two-phase or multistage sampling, and the design must be documented.** Sampling wallets from an assembled feature table is two-phase sampling; sampling seeds and then wallets is multistage cluster sampling [51][29][37]. The design weight is the product of the stage probabilities, and the variance has a between-cluster component [51][54]. Without first-stage probabilities, any weight is a pseudo-weight [20][37].
3. **Clean the frame first, then draw.** Deduplicate, resolve the illicit/suspicious/licit overlap, apply the priority rule, and freeze the frame size before sampling [51][6]. Frame cleaning changes `N` and the inclusion probabilities; doing it after the draw cannot be repaired by weighting [51]. Measurement cleaning can happen after the draw, but must be pre-specified and applied identically to every arm [4].
4. **Use a census for the small and rare arms, and a fixed sample for the large arms.** Take all eligible illicit wallets. Take all eligible rule-pass wallets for rare rules. For the **suspicious** arm, use a fixed 50,000 sample stratified by hop 1–5 and clustered by seed [5][8]. For the **licit** arm, use a cleaned 50,000 sample stratified by activity band (or simple random sample); do not apply hop strata or crawl-seed clusters to licit, because that frame has neither [6][8].
5. **Separate the illicit label from the hop-expanded proximity cohort.** The blacklist is a label source, not a complete census of illicit wallets [43][13]. Wallets reached within five hops are "suspicious/reachable", not confirmed illicit [28][49]. Phase 1 should use a frozen, label-complete-as-available blacklist as the illicit arm and keep the hop cohort as a separate descriptive/risk-ranking arm [6].
6. **Ask the collaborator for all available blacklisted addresses at a snapshot, and do not let new 5-hop expansion change the phase-1 label set.** "All available" means every address on the chosen label sources at a recorded date, not every illicit wallet in existence [43][13]. Continue hop expansion in phase 2 for feature generation and risk scoring, with an out-of-sample evaluation [6].
7. **Report rare rule support as counts and intervals, not as a p-value or a point estimate.** The current local counts are 13/4,938 Jaccard passes and 0/5,709 CV passes [4]. The key fact is that 13 is the **total count of passes in the eligible population**, so a sample can miss all of them. A 50,000 sample drawn from the whole illicit frame (about 4.24M wallets at the online snapshot) would have an expected 0.15 passes at the whole-frame rate; a 50,000 sample drawn from the 4,938 eligible wallets would have an expected 132 passes. The census rule does not depend on either expectation: it follows from 13 being the population total and from the need for a denominator that is not chosen by the outcome [33][44].
8. **Do not use all the suspicious wallets to get a smaller p-value.** Hop expansion is degree- and path-dependent, and wallets reached from the same seed are dependent [54][30]. The effective sample size is closer to the number of independent clusters than to the wallet count; estimate the intra-cluster correlation and report the design effect and `n_eff = n / deff` [54][22][5].
9. **Do not treat unlabelled wallets as licit.** The unlabelled set is unknown, not negative [55][34]. Treating it as licit biases precision down and sensitivity up in predictable directions, and the bias is differential by hop stratum [34]. The project already uses `unlabeled`; keep that convention [6].
10. **Freeze and document the draw as a design, not a row count.** Record the snapshot, source, hash, row counts per arm, exclusions, sampling unit, strata, cluster, allocation, random seed, weights/pseudo-weights, design effect, and effective sample size [10][46][42]. Write a documented analysis plan; because the phase-1 outcomes have already been inspected, do not call it a blind pre-registration [42].

## 1. The nested-sample question

### 1.1 Two different populations

There are two different estimands:

- **Frame estimand:** "Among the wallets in the frozen illicit and licit databases, do the groups differ?" Here the database is the population. A probability sample of it is defensible, with a finite population correction if the sampling fraction is material [51].
- **Target estimand:** "Among all TRON wallets, do the groups differ?" Here the database is a first-stage sample, and the first-stage selection is the binding constraint. A second-stage sample cannot repair coverage bias introduced by the crawl or by the choice of external list [20][41].

The distinction matters because the first-stage inclusion probabilities for the crawl and the external list are not recorded. The illicit database is a collection of accounts reached from seeds; the licit database is an external list whose inclusion rules and time window are not documented. Neither has a recorded `π`, so neither is a probability sample of all TRON wallets [20][15][6].

### 1.2 Two-stage versus two-phase

The terms are often used loosely, but they imply different designs:

- **Two-stage / multistage:** different units at each stage. Example: select seeds, then select wallets within each seed. The seed is the primary sampling unit and the wallet is the secondary sampling unit. The design is clustered, and the variance must reflect the between-seed component.
- **Two-phase / double sampling:** the same units are measured twice. Phase 1 collects cheap auxiliary information on a large sample; phase 2 collects the expensive variables on a subsample, often stratified by phase-1 information [29][37].

Sampling wallets out of an already-assembled feature table is two-phase sampling. It is not automatically "sampling a sample" in the damaging sense, but its variance depends on what is declared about phase 1. The R `survey` documentation is explicit: if phase-1 probabilities or finite population corrections are omitted, `twophase` treats phase 1 as simple random sampling from an infinite population; totals are wrong, and means/quantiles/regressions are "correct" only under that assumption [37].

For this study:

- If the analysis sample is drawn **after** the feature table is built, state that the database is the frame population and the draw is a two-phase subsample of that frame. Report it as a sample of the database.
- If the analysis sample is drawn **by selecting seeds and then wallets**, state that it is a multistage cluster sample. Report the number of seeds, the wallets per seed, and the design effect.
- Do not describe either design as a probability sample of all TRON wallets.

### 1.3 When the first stage is unknown

A non-probability first stage cannot be fixed by a larger second stage. More data from a biased mechanism can be worse, not better: Meng's decomposition shows that the error of a sample mean grows with `√N` when the data-defect correlation is uncontrolled, and that a 1% self-selected sample of about 2.3 million can have the same mean squared error as a simple random sample of about 400 [41]. Keiding and Louis make the related point for self-selected entry: such studies often have little reference to a well-defined study base, and transporting their results requires compatible causal structure [32].

There are four defensible positions, in descending strength:

1. **Restrict inference to the frame population.** Say "among wallets in the frozen databases". This is the cleanest and is sufficient for phase-1 hypothesis testing about these data.
2. **Post-stratify or rake to external margins** (for example, chain-wide activity bands), and report it as a sensitivity, not a fix. Calibration fixes known margins, not the joint distribution or unmeasured selection [18][51].
3. **Fit a model-based or transportability analysis** with explicit assumptions. This requires covariates and a defensible model; it is not design-based [20][36].
4. **Report descriptive sample statistics and state that population precision is not identified.** This is the AAPOR position for non-probability samples without a validated model: state that precision measures are not provided [10].

Inverse-probability and propensity weighting need a reference probability sample. Valliant and Dever show that mean estimators which ignore the reference-sample weights are biased even when the volunteering-propensity model is correct [52]. Bethlehem documents that undercoverage and self-selection both bias web samples; adjustment weighting and reference surveys help, but self-selection still leads to unreliable outcomes [12]. The study does not currently have a probability reference sample, so the first position is the honest one.

### 1.4 Clean first or sample first

Separate two operations:

- **Frame cleaning:** deduplicate, resolve the illicit/suspicious/licit overlap, apply the priority rule, decide the eligibility domain, and freeze `N`. This changes the frame and the inclusion probabilities. It must happen before the draw.
- **Measurement cleaning:** winsorising, missing-value handling, recomputing features, adjudicating labels from behaviour. This does not change `π` and is safer after the draw, provided it is pre-specified and applied identically to every arm.

The UN manual defines an accurate frame as one where each member appears once and only once; omissions and duplicates violate the probability criterion, and the frame should be corrected before sampling [51]. If duplicates are discovered after selection, the adjusted inclusion probability is `π = 1 − Π(1 − π_k)` over the duplicate listings; unknown eligibility is handled by estimating the eligible proportion among unknown cases [51]. In this project, frame cleaning includes the priority rule: any blacklist record at hop 1–5 is illicit, not suspicious; licit is the leftover after removing illicit and suspicious overlap; `unlabeled` is the remainder.

The current local data show why this matters. The local mirror has 2,125,343 illicit accounts and 11,418 blacklisted wallets; the local licit schema has 3,149,914 accounts, of which 843 are in the illicit blacklist and 5 of 721 licit seeds are blacklisted [9a]. The online profile from 2026-11-21 shows 4,754,230 illicit accounts, 16,507 blacklisted wallets, and 6,614,681 licit accounts [2]. The online overlap is 2,977 blacklisted licit accounts and 6/721 licit seeds; a 5,000 suspicious sample reports 49.7% present in licit accounts [3]. These are different snapshots. Sampling before cleaning would mix them and make the inclusion probabilities undefined.

**Eligibility is a response-defined domain restriction, not a neutral sampling exclusion.** Requiring at least two events for `log1p(tx_lifetime_days)` and at least five for CV conditions the estimand on activity: only 6,324 of 11,418 blacklisted wallets (55.4%) clear the lifetime gate, and 4,709 have no transaction at all [4]. Applying the rule identically to every arm removes *differential* selection, but the estimand becomes "mean lifetime among wallets active enough to have at least two events", which is a survivor-conditioned quantity. State that in the report; do not present the eligibility rule as if it were a sampling frame.

There are two CV denominators in the project documents. The test plan reports 0/5,709; the profiling note reports 5,695 illicit wallets with CV defined. The 5,709 is the number with at least five events; the 5,695 is the number with at least five events and a defined CV. Use 5,709 for the event-count denominator and 5,695 for the CV-defined denominator, and say which one a percentage uses [4][5].

### 1.5 Census or sample, by arm

| Arm | Phase-1 recommendation | Why |
|---|---|---|
| **Illicit (confirmed blacklist)** | **Census of all eligible wallets** | Small (about 6,300 eligible for lifetime; 5,695 for CV), and it is the target arm. Subsampling it throws away scarce cases and cannot be repaired by adding controls [4]. |
| **Suspicious (hop-expanded)** | **Fixed sample, about 50,000, stratified by hop 1–5 and clustered by seed**; keep the full cohort for descriptive counts | Large (1.34M local; 3.6M online), graph-derived, and dependent. More rows do not create more independent evidence [5][54][30]. |
| **Licit (cleaned)** | **Fixed sample, about 50,000, simple or stratified by activity band**; full cleaned frame for coverage and rule-pass denominators | Large (3.1M local partial; 6.6M online before cleaning), and contaminated until overlap is removed [3][9a]. It has no hop levels and no crawl-seed clusters, so those design variables do not apply. |
| **Unlabeled** | **Fixed sample, about 50,000, only if used as the provisional third level** | It is a baseline, not a control. Name the substitution in every conclusion [6]. |
| **Rare rules (H4, H6)** | **Census of all eligible wallets**; report `k/n` with Wilson or exact intervals | H4 has 13/4,938 passes; H6 has 0/5,709. A random sample can contain zero cases [4][33]. |
| **Rule-pass counts** | **Census denominators** or a case-control design with all cases and a sample of controls | Prevalence and rule-support estimates need the full case count or inverse-probability weights [33][44]. |

The arithmetic needs to be stated with its denominator. At the eligible-frame rate, 13/4,938 = 0.263%; a 50,000 draw from the 4,938 eligible wallets would have an expected 132 passes, not 13. At the whole-frame rate, 13/4.24M = 0.0003%; a 50,000 draw from the whole illicit frame would have an expected 0.15 passes. The census conclusion does not depend on either number: 13 is the total count of passes, so any sample can contain at most 13 and most draws will contain zero. That is why the rare arm needs the census, not a bigger sample [33][44].

The case-control literature is explicit: sampling all available events and a fraction of nonevents is efficient and valid with the correct weighted estimator; the intercept must be corrected before reporting absolute risks [33][44]. For this study, the "cases" are the rule passes, not the illicit wallets. If the question is "what fraction of illicit wallets pass H4?", take all eligible illicit wallets and compute the proportion. If the question is "does H4 separate illicit from licit?", take all H4-passing illicit wallets and a sample of non-passing illicit wallets, plus a comparable licit sample, and use a case-control analysis.

On the current online counts, the licit arm is 6,614,681 before cleaning [2]. Removing 2,977 blacklisted accounts is negligible; removing the estimated 49.7% suspicious overlap is not. A rough estimate is 6.61M − 0.497 × 3.60M ≈ 4.82M, but that is an extrapolation from a 5,000-row sample whose draw method is not recorded [3]. Compute the cleaned `N` from the actual overlap join before quoting it or using it in a finite population correction.

## 2. Incomplete illicit labels and hop expansion

### 2.1 What the blacklist is

An "illicit" label is not one construct. Published blockchain forensics builds labels from regulatory designation lists, issuer-level blacklists such as Tether's USDT freeze list, and taint or graph-proximity scores; address clustering is an entity-resolution step, not a label source [40][25][28]. These answer different questions: "is this address legally blocked", "can this address move USDT", "who probably controls it", and "how close is it to known bad". Pooling them pools different constructs.

Official sanctions lists are explicitly non-exhaustive at the address level. OFAC states that including certain virtual-currency addresses "may assist the industry in identifying other virtual currency addresses that may be associated with blocked persons ... even if those other addresses are not explicitly listed" [43]. The FATF standard requires freezing designated persons' assets and screening transfers, while acknowledging that identifying information can be held separately from the blockchain [21]. Neither document claims address-level completeness.

Labels also change. Treasury removed the Tornado Cash designations from the SDN List in March 2025, including the listed ETH addresses [50]. An industry audit of Tether's USDT blacklist reports 11,085 freeze events against 11,045 distinct addresses between November 2017 and August 2026, of which 1,303 addresses were later released; the audit is self-reported and not peer-reviewed [13]. The same audit attributes 8,017 events and 7,987 distinct addresses to TRON, with 958 releases [13]. A wallet labelled illicit in one extract may be unlabelled or released in the next. The label is an observation about an administrative action at a date, not a stable property of the wallet.

The licit list is also not a clean control. The online overlap is 2,977 blacklisted licit accounts, 6/721 licit seeds, and 49.7% of a 5,000 suspicious sample present in licit accounts [3]. That overlap suggests the licit list and the hop expansion are not independent frames. Treat the licit arm as an external comparison whose inclusion rules are unknown, not as a verified legitimate population.

### 2.2 Label versus proximity

The distinction is the core of the second question:

- **Label:** the address appears on a chosen blacklist/sanctions/issuer list at a frozen snapshot. This is the confirmed-positive frame, subject to the list's own coverage and noise.
- **Proximity:** the address is reachable from a labeled seed within `k` hops. This is a risk feature, not a label. It is degree- and path-dependent, and it over-flags.

Taint analysis is the formal version of proximity. Address-level taint marks an address as tainted if it receives from a tainted address, including all coins it holds; the method explicitly carries a risk of false incrimination [28][48]. A fixed-spread taint experiment left almost half the nodes equally tainted: it did not miss nodes that received tainted funds, but it also included many nodes that should not be tainted [28]. A direct statement from the taint literature is that there is no accepted evaluation method to measure accuracy [49]. In plain terms: "reachable from a bad wallet within five hops" is a proximity flag, not a label.

The hop-expanded cohort is also a link-tracing sample, not a probability sample. A chain-referral sample is analogous to a random walk on a network, and a random walk in equilibrium occupies a node with probability proportional to degree; well-connected individuals are over-represented [54][30]. Inclusion is path-dependent, and de-duplicating a wallet reached by many paths does not make the inclusion probability simple. Adaptive cluster sampling can be design-unbiased for a rare clustered population, but only when the adaptive design's inclusion probabilities are derived [47]. A five-hop expansion does not supply those probabilities.

The empirical record on RDS is a warning against over-reading hop depth. Gile and Handcock show that the convenience sample of seeds can induce bias, and that the number of waves typically used is likely insufficient for the nodal mixing required for asymptotic unbiasedness [22]. Goel and Salganik simulated RDS on 85 known networks and found it substantially less accurate than generally acknowledged; reported confidence intervals were misleadingly narrow, driven by high variance rather than bias [23]. McCreesh et al. compared an RDS survey with total-population data and found that RDS inference often failed to reduce bias; only 31–37% of estimates were closer to the true proportion than the raw sample proportion, and only 50–74% of bootstrap 95% CIs included the population proportion [39]. These results do not transfer automatically to a wallet traversal, but they make the burden of proof heavier, not lighter.

### 2.3 What to ask the collaborator

Ask for **all available blacklisted addresses at a frozen snapshot**, with source and date. Do not ask him to expand every 5-hop relation for phase 1. The two requests are different:

1. **Label census:** every address on the chosen blacklist/sanctions/issuer sources at snapshot date `T`. Record the source list, the number of addresses, the number added/removed since the previous snapshot, and any deduplication. If the sources are public, fetch them directly rather than relying on a hop-limited extract.
2. **Proximity cohort:** the current 5-hop expansion, frozen at snapshot `T`, kept as a separate `suspicious/reachable` arm. Do not let new hop expansion change the phase-1 label set.

Clarify the provenance of the collaborator's "banned accounts". If they are addresses that were reached by hops and then confirmed by a source, they may be a convenience subset of the positive class. If they are a direct export of a public blacklist, they are a label census. The distinction determines whether the positive set is a random subset of positives or a graph-selected subset. The positive-unlabelled literature formalises the difference: the standard correction assumes the labelled positives were selected completely at random (SCAR), and a seed-and-hop expansion is not a uniform random subset [19][11]. If SCAR fails, the constant-factor correction is not licensed.

If the collaborator cannot provide all sources, ask for the **largest available label snapshot** and a written description of how it was assembled. A label census of roughly 11,000–17,000 TRON blacklist addresses is small enough to be feasible [2][4]. The 11,045 Tether figure is an Ethereum+Tron total from the audit; the TRON-only figure is 7,987 addresses [13]. The 5-hop expansion is the large object (1.3M–3.6M suspicious wallets), not the blacklist. The priority is to complete the label set, not to expand the proximity set.

### 2.4 Phase 1 versus phase 2

| Data use | Phase 1 | Phase 2 |
|---|---|---|
| **Illicit label** | Frozen label census at `T`; all eligible wallets | Extend with new labels; evaluate on newly added labels only |
| **Suspicious/reachable** | Frozen 5-hop cohort; separate descriptive arm; cluster-aware summaries | Continue expansion for risk scoring; use as features, not labels |
| **Licit** | Clean overlap; fixed sample for means; full frame for coverage/pass rates | Extend/refresh; check sampling-frame compatibility |
| **Unlabeled** | Provisional third level; named substitution | Reclassify only with new labels |
| **Rule thresholds** | Report support and intervals at current thresholds | Tune thresholds on held-out labels/time |

The phase-2 evaluation should be out-of-sample. If the phase-2 labels are added after the phase-1 rules were chosen, scoring the phase-1 rules on the **newly added** labels is a label-maturity check. Re-running on the enlarged set is weaker because the enlarged set was not used to choose the rules.

## 3. Recommended phase-1 protocol

1. **Freeze the sources.** Record the online database names, snapshot date/time, row counts, and a hash/checksum of the extract. Freeze the blacklist snapshot and the licit list separately. Do not mix the local mirror counts and the online counts in one table.
2. **Build the cleaned frame.** Deduplicate to the analysis unit (wallet, not address cluster, unless you explicitly choose actor-level inference). Apply the priority rule: any blacklist record at hop 1–5 is illicit; suspicious is `min(hop) ∈ 1..5` minus blacklist; licit is the external list minus illicit and suspicious; unlabeled is the rest. Report the number removed at each step [6][51].
3. **Fix the eligibility domain.** For each response, state the eligibility rule (for example, `≥2 events` for lifetime, `≥5 events` for CV) and apply it identically to every arm. Report the n-flow: source → dedupe → overlap removal → label known → eligible → analysed. State that the estimand is survivor-conditioned; do not drop zero-event wallets silently [4].
4. **Take the census where the arm is small or the event is rare.** All eligible illicit wallets. All eligible rule-pass wallets for H4/H6 [33]. Report `k/n` and a Wilson or exact 95% CI [24][14]. For H4, the current observed rate is 13/4,938 (0.263%); for H6, 0/5,709 [4]. A zero count does not mean zero rate; the rule-of-three upper bound is about 3/5,709 = 0.053%, and a Wilson interval gives 0–0.067% (local arithmetic) [24][14]. Because the illicit arm is a census, these intervals are superpopulation statements about a hypothetical draw, not sampling error for the reported proportion; say which interpretation you intend.
5. **Draw the fixed sample for the large arms.** For suspicious: about 50,000, stratified by hop 1–5 and clustered by seed. For licit: about 50,000 after cleaning, simple or stratified by activity band; no hop or crawl-seed variable. For unlabeled: about 50,000 if used as the provisional third level. Record the random seed, the allocation, the achieved `n`, and the weights/pseudo-weights [5][46].
6. **Define the cluster variable before drawing.** If the cluster is `seed_address`, a wallet reachable from more than one seed has an ambiguous cluster assignment; the project records 216,776 such wallets [4]. Decide whether to assign each wallet to its first/strongest seed, duplicate it across clusters with weights, or use a multi-membership model. A seed cluster also spans all hop levels, so "hop-stratified and seed-clustered" requires a rule for assigning clusters to strata. State the rule; otherwise the design is not reproducible.
7. **Compute features in SQL, not in a dataframe.** Build the feature table at the wallet level from the frozen frame, then export only the analysis columns. Keep `hex_address` out of the analysis view. Do not compute features from the label set, seed identity, hop distance, or suspicious-set membership in phase 1; those are label derivatives and create leakage [31].
8. **Use cluster-aware inference.** Welch ANOVA or Games–Howell for the mean comparisons; seed-cluster bootstrap for CIs; a mixed model with seed random effects as an alternative. Report the design effect and `n_eff = n / deff`. Do not use i.i.d. Kruskal–Wallis or Dunn on the full suspicious set; non-parametric tests do not fix dependence [5][54].
9. **Report effect sizes and denominators.** η²/ω², Cliff's delta, and bootstrap CIs. Report exact `n` per arm and per filter. Do not stop at p-values [10].
10. **Separate mean evidence from rule evidence.** A significant mean difference is a precursor, not a rule verdict. The rule verdict compares pass rates or tail quantiles with intervals. H2 has two conjuncts; burst is descriptive; a mean test alone cannot validate H2. H6 is currently opposite the premise (illicit CV highest); the two-sided omnibus is a falsification test [5][4].
11. **Write a documented analysis plan, not a blind pre-registration.** The phase-1 outcomes have already been inspected: H6 is opposite the premise (0/5,709) and H4 is inverted relative to its premise (13/4,938 vs 3,258/73,562) [4]. Record the primary contrasts, sample size, and stopping rule now, and label the document as a post-inspection analysis plan [42]. Version-control the draw script and record the seed [46].
12. **Do not rebalance for prevalence or rule support.** Random undersampling, oversampling, and SMOTE overestimate the minority-class probability and do not improve AUROC; shifting the threshold is a better alternative [53]. Models without imbalance correction have equal or better calibration [16]. If a phase-2 classifier needs balanced training data, use the rebalanced model for ranking only and recalibrate on the un-rebalanced prevalence.
13. **Hold out label completion for phase 2.** Freeze the phase-1 snapshot. When the collaborator adds labels, score the phase-1 rules on the newly added labels only, and report the label-maturity result separately. Do not let the new labels change the phase-1 threshold choice.

## 4. What this changes in the current repo

- **`docs/context/test_plan.md`:** keep the 50,000-per-arm recommendation, but state the estimand as the frozen database frame, not the TRON population. Add the design-effect/`n_eff` requirement and the census rule for H4/H6 [5][51]. **The ≈6,300 provenance is unresolved:** the test plan's header says "online profile 2026-11-20T10:57Z", while the local eligible count is 6,324 [5][4]. The two numbers are close enough that ≈6,300 may be a stale carry-over, not a snapshot difference. Reconcile it before drawing; do not present it as a verified local count.
- **`docs/context/cohort_contract.md`:** add the snapshot date and the source for each count; separate the local mirror counts from the online counts [6][7]. State that "illicit" means "on the chosen blacklist at snapshot `T`", not "all illicit wallets" [43]. Drop the unsourced 15,165 lower bound or attribute it to "across runs, no run table"; the only artifact shows 15,185 [1].
- **`docs/context/statistical_info.md`:** the 2026-11-20 online counts and the 2026-11-21 `db_overview.csv` counts differ [7][2]. Freeze one snapshot and cite it everywhere; do not mix the 11-20 overlap with the 11-21 overview.
- **`docs/context/sampling_evaluation.md`:** add the frame-vs-population distinction, the non-probability first stage, and the phase-1 census-vs-sample rule [8][20][51]. Avoid implying that the per-arm sample is representative of all TRON wallets.
- **`tasks/hypothesis_testing/01_response_factor_groups/05_licit_ingestion_etl.md`:** the task records "blocked: local PostgreSQL down", but the local licit schema holds 3,149,914 accounts at the 2026-11-21T08:58Z snapshot, and the latest licit run had 6 completed, 5 running, and 3 pending shards [9a]. Note that `pg_isready` without `-h` checks the Unix socket; the server is reachable on TCP `localhost:5432`. Update the task to `in_progress` and record the observed shard state. The local licit count is a moving partial, not a final `N`.

## 5. Caveats and disagreements

- **No source validates hop expansion on TRON wallet graphs specifically.** The network-sampling evidence comes from social networks and RDS; the taint evidence comes from Bitcoin [54][30][28]. The mechanisms (degree bias, path dependence, false positives) are likely to transfer, but the magnitudes are unknown. TRON-specific peer-reviewed research is scarce [38]; the one reviewed TRON/USDT fraud study uses a suspicious-versus-random address dataset rather than a probability sample [35].
- **RDS asymptotic guarantees do not transfer to a hop expansion.** RDS requires a recruitment protocol, reciprocal network-size reporting, and a mixing process. A blockchain traversal has none of these by default. The honest label is "link-tracing/snowball", not RDS [26][27].
- **The blacklist is not truth.** It is an administrative snapshot with false negatives (incomplete collection) and false positives (releases, over-broad clustering) [43][13][28]. "All available banned accounts" is a label census, not a census of illicit activity.
- **The local and online counts drift.** The local mirror has 2,125,343 illicit accounts and 11,418 blacklisted wallets; the 2026-11-21 online profile has 4,754,230 and 16,507 [2][9a]. The local licit schema had 3,149,914 accounts while ingestion was running [9a]. Any `N` used for a finite population correction or a census/sample decision must come from a frozen extract, not a live query [51].
- **The 49.7% overlap is a point estimate from an undocumented draw.** It is 2,485/5,000; a Wilson 95% CI is about 48.3–51.1%, and `group_overlap.csv` records only "sample of 5000 suspicious hop 1-5 wallets" [3]. Do not quote 49.7% to one decimal place as if it were a population rate, and compute the cleaned licit `N` from the actual join.
- **The literature disagrees on RDS in finite samples.** Salganik and Heckathorn claim asymptotic unbiasedness under specified conditions [45]; Gile and Handcock, Goel and Salganik, and McCreesh et al. document seed bias, insufficient mixing, high variance, and misleading CIs [22][23][39]. For a five-hop expansion, the sceptical empirical papers are the relevant evidence.
- **The literature disagrees on rebalancing.** The risk-prediction literature finds resampling harmful for calibration [53][16]; the fraud-detection literature sometimes finds it helpful for ranking [53]. Both can be true. For phase-1 prevalence and rule support, the calibration argument governs.
- **Some sources were read at abstract level.** The full texts of several paywalled articles were not available. The claims are limited to what the abstracts and official pages state, and the source notes mark the reading status. The direct cross-check notes [9] record the search terms, the rate-limited queries, and the local read-only checks.

## 6. Open questions

1. **What is the provenance of the collaborator's banned list?** A direct export of a public blacklist is a label census; a hop-expanded set that was later confirmed is a convenience subset. The answer determines whether the positive set is SCAR or graph-selected [19][11].
2. **What is the target estimand?** "Wallets in the frozen databases" or "all TRON wallets"? The first is defensible; the second requires a probability reference sample or a transportability model that the project does not currently have [20][32].
3. **What is the licit sampling frame?** The list's coverage, inclusion rules, and time window are unknown [8]. Before pooling, check whether the licit frame is compatible with the illicit frame [6]. The 49.7% overlap suggests it may not be independent.
4. **How many independent seeds are there, and what is the design effect?** The test plan says 5,931 seeds are blacklisted [5]. The effective sample size depends on the intra-seed correlation, which must be estimated, not assumed [22][51].
5. **How is a multi-seed wallet assigned to a cluster, and how is a cluster assigned to a hop stratum?** The project records 216,776 wallets reachable from more than one seed [4]. Without a rule, "hop-stratified and seed-clustered" is underspecified.
6. **Can the collaborator provide a second, independent label source?** A second source would allow a coverage/capture-recapture check, but only if the sources are independent; nested or shared-source lists are not independent samples.
7. **What was the draw method for the 5,000 suspicious sample?** If it was not random, the 49.7% overlap is an artefact, not an estimate [3].

## Sources

### Project artifacts and local data

1. `outputs/profiling/cohort_counts.csv` — cohort counts, snapshot 2026-11-20T11:12:46Z (illicit blacklist 15,185; suspicious 3,598,120; licit accounts 6,614,681; licit seed_wallets 721).
2. `outputs/profiling/db_overview.csv` — table row counts, snapshot 2026-11-21T03:53:36Z (illicit accounts 4,754,230; blacklisted_wallets 16,507; licit accounts 6,614,681).
3. `outputs/profiling/group_overlap.csv` — overlap counts, snapshot 2026-11-20T11:12:46Z (blacklist ∩ licit 2,977; blacklist ∩ licit seeds 6/721; 2,485/5,000 suspicious sample in licit).
4. `docs/context/step_1_profiling_samples.md` — local mirror counts (accounts 2,125,343; blacklisted wallets 11,418; suspicious 1,338,468); eligibility counts (6,324 ≥2 events; 5,695 ≥5 events and CV defined); H4 13/4,938 and H6 0/5,709; n-flow requirement; selection warning; 216,776 multi-seed wallets.
5. `docs/context/test_plan.md` — responses and eligibility gates; 50,000 per comparison arm; seed-cluster bootstrap; H2/H6 caveats; 5,931 distinct seeds.
6. `docs/context/cohort_contract.md` — unit = wallet; priority illicit > suspicious > licit > unlabeled; arm definitions and counts.
7. `docs/context/statistical_info.md` — online profile snapshot 2026-11-20T10:57Z (illicit accounts 4,540,183; blacklist 15,165–15,185); overlap 2,977 / 6 of 721 / 49.7%.
8. `docs/context/sampling_evaluation.md` — licit frame not clean; freeze a timestamp; 50,000 per comparison arm.
9. `outputs/.drafts/nested-sampling-aml-wallets-research-direct.md` — direct cross-check notes and local SQL checks, 2026-11-21.
9a. `outputs/profiling/local_cohort_check.csv` — local read-only SQL counts at 2026-11-21T08:58Z (illicit 2,125,343; blacklist 11,418; suspicious 1,338,468; licit 3,149,914; licit seeds 721; 843 blacklist overlap; 5/721 seed overlap; latest licit run 6 completed / 5 running / 3 pending shards). PostgreSQL TCP `localhost:5432`; the Unix socket was absent.

### Literature

10. American Association for Public Opinion Research (n.d., accessed 2026-11-21). *Transparency Initiative — Disclosure Elements*. https://aapor.org/standards-and-ethics/transparency-initiative/
11. Bekker, J., & Davis, J. (2020). Learning from positive and unlabeled data: a survey. *Machine Learning* 109:719–760. https://doi.org/10.1007/s10994-020-05877-5
12. Bethlehem, J. (2010). Selection Bias in Web Surveys. *International Statistical Review* 78(2):161–188. https://doi.org/10.1111/j.1751-5823.2010.00112.x
13. Bitquery (2026). *The Tether Freeze Regime*. https://bitquery.io/investigations/tether-blacklist-audit
14. Brown, L. D., Cai, T. T., & DasGupta, A. (2001). Interval Estimation for a Binomial Proportion. *Statistical Science* 16(2):101–133. https://doi.org/10.1214/ss/1009213286
15. Buelens, B., Burger, J., & van den Brakel, J. A. (2018). Comparing Inference Methods for Non-probability Samples. *International Statistical Review* 86(2):322–343. https://doi.org/10.1111/insr.12253
16. Carriero, A., Luijken, K., de Hond, A., Moons, K. G. M., van Calster, B., & van Smeden, M. (2025). The Harms of Class Imbalance Corrections for Machine Learning Based Prediction Models: A Simulation Study. *Statistics in Medicine* 44(3–4):e10320. https://doi.org/10.1002/sim.10320
17. Cornesse, C., Blom, A. G., Dutwin, D., Krosnick, J. A., De Leeuw, E. D., Legleye, S., Pasek, J., Pennay, D., Phillips, B., Sakshaug, J. W., Struminskaya, B., & Wenz, A. (2020). A Review of Conceptual Approaches and Empirical Evidence on Probability and Nonprobability Sample Survey Research. *JSSAM* 8(1):4–36. https://doi.org/10.1093/jssam/smz041
18. Deville, J.-C., & Särndal, C.-E. (1992). Calibration Estimators in Survey Sampling. *JASA* 87(418):376–382. https://doi.org/10.1080/01621459.1992.10475217
19. Elkan, C., & Noto, K. (2008). Learning classifiers from only positive and unlabeled data. *KDD* 2008:213–220. https://doi.org/10.1145/1401890.1401920
20. Elliott, M. R., & Valliant, R. (2017). Inference for Nonprobability Samples. *Statistical Science* 32(2):249–264. https://doi.org/10.1214/16-STS598
21. FATF (2021). *Updated Guidance for a Risk-Based Approach for Virtual Assets and VASPs*. https://www.fatf-gafi.org/content/dam/fatf-gafi/guidance/Updated-Guidance-VA-VASP.pdf
22. Gile, K. J., & Handcock, M. S. (2010). Respondent-Driven Sampling: An Assessment of Current Methodology. *Sociological Methodology* 40(1):285–327. https://doi.org/10.1111/j.1467-9531.2010.01223.x
23. Goel, S., & Salganik, M. J. (2010). Assessing respondent-driven sampling. *PNAS* 107(15):6743–6747. https://doi.org/10.1073/pnas.1000261107
24. Hanley, J. A., & Lippman-Hand, A. (1983). If Nothing Goes Wrong, Is Everything All Right? *JAMA* 249(13):1743–1745. https://doi.org/10.1001/jama.1983.03330370053031
25. Harrigan, M., & Fretter, C. (2016). The Unreasonable Effectiveness of Address Clustering. *IEEE ATC* 2016:368–373. https://doi.org/10.1109/UIC-ATC-ScalCom-CBDCom-IoP-SmartWorld.2016.0071
26. Heckathorn, D. D. (2002). Respondent-Driven Sampling II. *Social Problems* 49(1):11–34. https://doi.org/10.1525/sp.2002.49.1.11
27. Heckathorn, D. D. (2011). Comment: Snowball versus Respondent-Driven Sampling. *Sociological Methodology* 41(1):355–366. https://doi.org/10.1111/j.1467-9531.2011.01244.x
28. Hercog, A., & Povše, D. (2019). Taint analysis of the Bitcoin network. arXiv:1907.01538. https://arxiv.org/abs/1907.01538
29. Hidiroglou, M. A. (2001). Double Sampling. *Survey Methodology* 27(2):143–154. https://www150.statcan.gc.ca/n1/pub/12-001-x/2001002/article/6091-eng.pdf
30. Illenberger, J., & Flötteröd, G. (2012). Estimating network properties from snowball sampled data. *Social Networks* 34(4):701–711. https://doi.org/10.1016/j.socnet.2012.09.001
31. Kaufman, S., Rosset, S., Perlich, C., & Stitelman, O. (2012). Leakage in Data Mining: Formulation, Detection, and Avoidance. *ACM TKDD* 6(4):15. https://doi.org/10.1145/2382577.2382579
32. Keiding, N., & Louis, T. A. (2016). Perils and Potentials of Self-Selected Entry to Epidemiological Studies and Surveys. *JRSS A* 179(2):319–376. https://doi.org/10.1111/rssa.12136
33. King, G., & Zeng, L. (2001). Logistic Regression in Rare Events Data. *Political Analysis* 9(2):137–163. https://doi.org/10.1093/oxfordjournals.pan.a004868
34. Kossinets, G. (2006). Effects of missing data in social networks. *Social Networks* 28(3):247–268. https://doi.org/10.1016/j.socnet.2005.07.002
35. Lam, Y. A., Chow, K.-P., & Yiu, S.-M. (2025). Uncovering Fraudulent Patterns in USDT Transactions on the TRON Blockchain with EDA and Machine Learning Techniques. ICDF2C 2024, LNICST 613:233–248. https://doi.org/10.1007/978-3-031-89363-6_13
36. Little, R. J. A. (2004). To Model or Not To Model? *JASA* 99(466):546–556. https://doi.org/10.1198/016214504000000467
37. Lumley, T. (2026). *survey: Analysis of Complex Survey Samples*, R package version 4.5. https://cran.r-project.org/web/packages/survey/survey.pdf
38. Mao, Q., Wang, J., Feng, Z., Zhang, Y., & Yan, J. (2025). Decoding TRON: A Comprehensive Framework for Large-Scale Blockchain Data Extraction and Exploration. arXiv:2509.16292. https://arxiv.org/abs/2509.16292
39. McCreesh, N., Frost, S., Seeley, J., Katongole, J., Tarsh, M. N., Ndunguse, R., ... & White, R. G. (2012). Evaluation of Respondent-driven Sampling. *Epidemiology* 23(1):138–147. https://doi.org/10.1097/EDE.0b013e31823ac17c
40. Meiklejohn, S., Pomarole, M., Jordan, G., Levchenko, K., McCoy, D., Voelker, G. M., & Savage, S. (2013). A Fistful of Bitcoins. *IMC* 2013:127–140. https://doi.org/10.1145/2504730.2504747
41. Meng, X.-L. (2018). Statistical paradises and paradoxes in big data (I). *Annals of Applied Statistics* 12(2):685–726. https://doi.org/10.1214/18-AOAS1161SF
42. Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). The preregistration revolution. *PNAS* 115(11):2600–2606. https://doi.org/10.1073/pnas.1708274114
43. OFAC (2021). *Sanctions Compliance Guidance for the Virtual Currency Industry*. https://ofac.treasury.gov/media/913571/download?inline=
44. Prentice, R. L., & Pyke, R. (1979). Logistic disease incidence models and case-control studies. *Biometrika* 66(3):403–411. https://doi.org/10.1093/biomet/66.3.403
45. Salganik, M. J., & Heckathorn, D. D. (2004). Sampling and Estimation in Hidden Populations Using Respondent-Driven Sampling. *Sociological Methodology* 34(1):193–240. https://doi.org/10.1111/j.0081-1750.2004.00152.x
46. Sandve, G. K., Nekrutenko, A., Taylor, J., & Hovig, E. (2013). Ten Simple Rules for Reproducible Computational Research. *PLoS Computational Biology* 9(10):e1003285. https://doi.org/10.1371/journal.pcbi.1003285
47. Thompson, S. K. (1990). Adaptive Cluster Sampling. *JASA* 85(412):1050–1059. https://doi.org/10.1080/01621459.1990.10474975
48. Tironsakkul, T., Maarek, M., Eross, A., & Just, M. (2020). Tracking Mixed Bitcoins. arXiv:2009.14007. https://arxiv.org/abs/2009.14007
49. Tironsakkul, T., Maarek, M., Eross, A., & Just, M. (2019). Probing the Mystery of Cryptocurrency Theft. arXiv:1906.05754. https://arxiv.org/abs/1906.05754
50. U.S. Treasury (2025). *Tornado Cash Delisting*, 21 March 2025. https://home.treasury.gov/news/press-releases/sb0057 ; address-level removal: https://ofac.treasury.gov/recent-actions/20250321
51. UN DESA (2008). *Designing Household Survey Samples: Practical Guidelines*. https://unstats.un.org/unsd/publication/seriesf/Seriesf_98E.pdf
52. Valliant, R., & Dever, J. A. (2011). Estimating Propensity Adjustments for Volunteer Web Surveys. *Sociological Methods & Research* 40(1):105–137. https://doi.org/10.1177/0049124110392533
53. van den Goorbergh, R., van Smeden, M., Timmerman, D., & Van Calster, B. (2022). The harm of class imbalance corrections for risk prediction models. *JAMIA* 29(9):1525–1532. https://doi.org/10.1093/jamia/ocac093
54. Volz, E., & Heckathorn, D. D. (2008). Probability Based Estimation Theory for Respondent Driven Sampling. *Journal of Official Statistics* 24(1):79–97. https://www.scb.se/contentassets/ca21efb41fee47d293bbee5bf7be7fb3/probability-based-estimation-theory-for-respondent-driven-sampling.pdf
55. Weber, M., Domeniconi, G., Chen, J., Weidele, D. K. I., Bellei, C., Robinson, T., & Leiserson, C. E. (2019). Anti-Money Laundering in Bitcoin: Experimenting with Graph Convolutional Networks for Financial Forensics. arXiv:1908.02591. https://arxiv.org/abs/1908.02591
