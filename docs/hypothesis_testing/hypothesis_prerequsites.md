# Prerequisites for H2, H4, H6

**Purpose.** This file fixes the vocabulary and design objects needed before writing `H0`/`Ha` and choosing a test. It is not the final test plan and it does not add hypotheses after seeing results. `H2`, `H4`, `H6` are **research questions**; `H0`/`Ha` are the **statistical hypotheses**. Canonical terms: `docs/context/glossary.md`.

**Scope.** Phase-1 active questions: **H2, H4, H6**. `H1`, `H3`, `H5` are deferred (`AGENTS.md:55`). The current third level is `unlabeled`; `licit` is the target frame after cleaning (`AGENTS.md:8,22`).

**Snapshot warning.** Cohort counts (`illicit` 15,165–15,185; `suspicious` 3,598,120; `licit` 6,614,681 raw) are the **online 2026-11-20** profile. Response support and pass rates (6,324; 4,938; 5,709; medians) are the **local mirror 2026-11-19** profile. They are different snapshots; do not add or divide across them. Freeze one extract before executing any H0.

**Frame rule.** Where a null below names `licit`, it is the target `H0_L`. Until licit is cleaned, run the same null with `unlabeled` and report it as `H0_U` (`docs/context/test_plan.md:7-8`).

**How to read this.** Each section defines a term, gives a TRON example, states why the distinction matters, and then applies it to H2/H4/H6. Final H0 wording belongs in Step 2.

---

## 1. Hypotheses

### 1.1 Definitions and examples

| Term | Definition | TRON example / scenario | Why it matters |
| --- | --- | --- | --- |
| Research question | Empirical claim a rule assumes | H2 asks whether illicit wallets are short-lived and bursty; H4 asks whether they reuse the same TRX funders and USDT recipients; H6 asks whether their inter-arrival times are regular | It is not yet a testable statistical statement; it must be mapped to a response, factor, and groups |
| Statistical hypothesis | Statement about a population parameter or distribution | “Mean log lifetime is equal across wallet classes” | It fixes the estimand and the test |
| `H0` | Null: no difference / no effect | `H0: μ_illicit = μ_suspicious = μ_unlabeled` for `log1p(tx_lifetime_days)` | It is the statement the test can reject |
| `Ha` | Alternative: the predicted difference | `Ha: at least one mean differs` | Never call it `H1`; `H1` is research question 1 (`docs/context/glossary.md:9-15`) |
| One-sided vs two-sided | Whether the alternative has a direction | Two-sided omnibus for group differences; one-sided only if the rule predicts a direction in advance | Direction must be pre-specified, not chosen after seeing the data |
| Conjunction | Rule passes only if all conditions hold | H2 = lifetime ≤ 7 days **AND** burst ratio ≥ 0.75; H6 = N ≥ 5 **AND** CV < 0.15 | Marginal tests of each condition do not validate the conjunction (`docs/context/test_plan.md:18`) |
| Precursor vs rule verdict | A mean/location test asks whether groups differ on a feature; a rule verdict asks whether the rule passes at different rates | Mean lifetime difference is a precursor; `P(H2 pass \| group)` is the rule verdict | The project requires both, not one instead of the other (`docs/context/glossary.md:15`) |
| Effect size | Magnitude of the difference, independent of n | η²/ω², Cliff’s delta, risk difference | A p-value alone does not show practical separation |
| Alpha and multiplicity | Type I error rate and family-wise control | α = 0.05; Holm over the two omnibus tests (H2, H6); separate family for pairwise comparisons | Prevents fishing across responses and pairs (`docs/context/test_plan.md:10`) |

### 1.2 H2 (S2) — Temporal burstiness

**Status.** In progress in the task tracker; support is fragile.

**Rule.** A wallet scores high when its operational lifetime is ≤ 7 days **AND** its maximum 1-hour volume (in+out) is ≥ 75% of its lifetime volume (`docs/hypothesis.md`).

**Example scenario.** Wallet W receives 10,000 USDT on day 1 and sends 9,800 USDT out within 40 minutes. Its transaction span is 2 days and its burst ratio is 0.98, so it passes both conditions. Wallet V receives and sends small amounts over 60 days with a burst ratio of 0.05; it fails. Wallet U has only one USDT event; it may have `burst_ratio = 1.0` by construction, so the `N ≥ 5` activity floor is needed.

**Factor.** `wallet_class`, fixed, 3 levels (see §2).

**Responses.**
- Primary: `log1p(tx_lifetime_days)` — continuous, ratio, per wallet.
- Descriptive/threshold: `burst_ratio` — continuous, bounded [0,1].
- Rule verdict: `h2_pass` — binary conjunction.

**Groups.** `illicit`, `suspicious`, `unlabeled` now; `licit` after cleaning (see §4).

**Why this design.**
- H2 has two conjuncts, so a mean lifetime test alone cannot validate the rule (`docs/context/test_plan.md:18`).
- `burst_ratio` is descriptive because the implementation is USDT-only while the rule text says volume in+out, and because one-shot wallets have mass at 1.0 (`docs/context/feature_audit.md`).
- The activity floor reverses the pass-rate ranking: illicit 22.0% vs suspicious 55.6% before the floor; 8.0% vs 2.6% after (`docs/context/step_1_profiling_samples.md:102`).
- The observed illicit lifetime median is 93.1 days, longer than suspicious 31.6 and unlabeled 10.6, so the “short-lived” premise is not supported on this frame (`docs/context/step_1_profiling_samples.md:85-90`).

**Null ingredients (not final wording).**
- Omnibus: `H0_U: mean log lifetime equal across illicit/suspicious/unlabeled`; `Ha: at least one differs`. `H0_L` uses `licit` after cleaning.
- Rule support: `H0: P(H2 pass \| illicit) = P(H2 pass \| licit)`; `Ha: different`, or `illicit > licit` only if pre-specified.

**Candidate test family.** Welch ANOVA + Games–Howell on `log1p(tx_lifetime_days)`; Kruskal–Wallis + Dunn only as a distributional sensitivity on independent arms; seed-cluster bootstrap; pass-rate/ROC/PR for the rule. Non-parametric tests do not fix dependence (`AGENTS.md:30-31`).

### 1.3 H4 (S4) — TRX gas co-occurrence

**Status.** Blocked by data support (13 illicit passes).

**Rule.** Jaccard index of addresses funding TRX versus addresses receiving USDT is ≥ 0.50 (`docs/hypothesis.md`).

**Example scenario.** Wallet W receives TRX from A, B, C and sends USDT to B, C, D. The intersection is {B, C}; the union is {A, B, C, D}; J = 2/4 = 0.50, so it passes. A wallet with disjoint sets has J = 0. A wallet with only TRX or only USDT is ineligible because the denominator is undefined.

**Factor.** `wallet_class`, fixed, 3 levels.

**Responses.**
- `jaccard_index` — continuous, bounded [0,1], descriptive/threshold.
- Rule verdict: `h4_pass` — binary.
- There is no primary continuous H4 response in the current test plan.

**Groups.** Same three-level factor; see §4.

**Why this design.**
- Jaccard is defined only when both sets are non-empty (`docs/context/feature_audit.md`).
- It is zero-inflated: zero for 77.7% of eligible illicit wallets (`docs/context/step_1_profiling_samples.md:96`).
- Support is rare: 13/4,938 eligible illicit pass ≥ 0.50, versus 3,258/73,562 suspicious (4.43%) and 223/6,109 unlabeled (3.65%), so the rule is inverted relative to its premise (`docs/context/step_1_profiling_samples.md:103`).
- “TRX funder” is any TRX transfer, not necessarily a gas payment; this is a construct-validity caveat.

**Null ingredients (not final wording).**
- `H0: P(H4 pass \| illicit) = P(H4 pass \| licit)`; `Ha: different`, or `illicit > licit` if pre-specified.
- Descriptive: Jaccard distributions by group, including the zero mass.

**Candidate test family.** Two-proportion test / Fisher exact / cluster bootstrap for pass rates; distribution plots and bootstrap CIs for Jaccard. Report 13/4,938 with a Wilson or exact 95% CI; a count of 13 is not a rate of 13/4,938 without its interval. Do not use ANOVA on a zero-inflated bounded ratio with 13 events.

### 1.4 H6 (S6) — Interval consistency

**Status.** In progress; the observed direction is opposite the premise (0 illicit passes).

**Rule.** Transaction count N ≥ 5 within an operational session **AND** coefficient of variation of inter-arrival times < 0.15 (`docs/hypothesis.md`).

**Example scenario.** Wallet W has 10 events spaced almost exactly 6 minutes apart; its CV is near 0, so it passes. A human wallet with irregular gaps has a high CV and fails. A wallet with only 3 events is ineligible. If IN and OUT events are pooled, a regular alternating pattern can look more regular than either direction alone.

**Factor.** `wallet_class`, fixed, 3 levels.

**Responses.**
- Secondary: `log1p(cv_delta_t)` — continuous, ratio, per wallet.
- Rule verdict: `h6_pass` — binary conjunction.
- Supporting: `event_count` — discrete count, eligibility.

**Groups.** Same three-level factor; see §4.

**Why this design.**
- The rule requires `direction` (IN/OUT), but the current event table does not carry it (`docs/context/feature_audit.md`).
- “Operational session” is not defined; the implementation uses the whole observed history.
- The observed ordering is opposite the premise: illicit CV is highest (median 3.49 vs 1.45 suspicious, 1.21 unlabeled), and 0/5,709 illicit wallets pass CV < 0.15 (`docs/context/step_1_profiling_samples.md:94,104`).
- CV is sensitive to event count and zero gaps; the activity gate N ≥ 5 is part of the rule, not an optional filter.

**Null ingredients (not final wording).**
- Omnibus: `H0_U: mean log CV equal across illicit/suspicious/unlabeled`; `Ha: at least one differs`. `H0_L` uses `licit` after cleaning.
- Rule support: `H0: P(H6 pass \| illicit) = P(H6 pass \| licit)`; `Ha: different`, or `illicit > licit` if pre-specified.
- Because the observed direction is opposite, the two-sided omnibus is a falsification test, not confirmation (`docs/context/test_plan.md:18`).

**Candidate test family.** Welch ANOVA + Games–Howell on `log1p(cv_delta_t)`; Kruskal–Wallis + Dunn only as sensitivity on independent arms; seed-cluster bootstrap; pass-rate/ROC/PR for the rule. Report 0/5,709 with a rule-of-three or Wilson upper bound; zero observed passes does not mean a zero rate.

---

## 2. Factors

### 2.1 Definitions and examples

| Term | Definition | TRON example / scenario | Why it matters |
| --- | --- | --- | --- |
| Factor | Categorical predictor whose levels define the groups | `wallet_class` with levels illicit, suspicious, unlabeled | It defines what is being compared |
| Level | One category of a factor | `illicit` | Levels must match the cohort contract |
| Fixed effect | The levels are the only ones of interest | Wallet classes are fixed, not sampled from a population of classes | Fixed effects are estimated directly |
| Random effect | Levels are sampled from a population of levels | `seed_address`: blacklisted seeds are a sample of possible seeds | It changes the variance structure and the inference unit |
| Nested | Levels of B occur only inside one level of A | `hop_band` 1–5 exists only inside `suspicious` | A nested factor is not crossed; its interaction with class is not estimable |
| Crossed | Every A × B cell can occur | `wallet_class × hop_level` | Cells are structurally empty (licit has no hop; hop 0 is illicit), so the factorial is rejected (`docs/context/step_1_profiling_samples.md:113-117`) |
| Blocking | A nuisance variable used to reduce variance | `activity_band` (USDT event-count decile) | It is a sensitivity/matching device, not a primary factor |
| Covariate | Continuous adjustment variable | `event_count`; account age is risky because it overlaps H2 lifetime | Adjustment can remove the feature under test or introduce collinearity |

**Scenario.** Two wallets are reached from the same blacklisted seed. They are not independent observations even if they have different addresses. The seed is the cluster; the wallet is the unit. If hop level is treated as a second crossed factor, the design has empty cells.

### 2.2 Applied to H2, H4, H6

| Hypothesis | Factor | Levels | Random / nested | Reason |
| --- | --- | --- | --- | --- |
| H2 | `wallet_class` | illicit, suspicious, unlabeled (licit target) | `seed_address` random; hop nested in suspicious | Lifetime and burst are wallet-level responses; class is the only factor of interest |
| H4 | `wallet_class` | same | same | Jaccard is a wallet-level set overlap; no second factor is needed |
| H6 | `wallet_class` | same | same | CV is wallet-level; event count is eligibility, not a factor |

**Do not add** token standard as a second factor until the token scope is decided; native TRX is largely gas and would contaminate pass-through volume (`docs/context/feature_audit.md`). Do not add account age as a covariate without checking that it is not the H2 response in disguise.

---

## 3. Responses

### 3.1 Definitions and examples

| Term | Definition | TRON example / scenario | Why it matters |
| --- | --- | --- | --- |
| Response | Continuous outcome measured once per experimental unit | `log1p(tx_lifetime_days)` for one wallet | It is the quantity the test compares |
| Unit | The thing measured once | A wallet, not a transaction or hop row | Using transactions as units is pseudoreplication |
| Scale | Ratio, interval, count, or binary | Days (ratio), Jaccard (bounded ratio), event count (count), pass flag (binary) | Scale determines the candidate test |
| Eligibility | Response-defined domain restriction | H2 lifetime needs ≥2 events; H6 CV needs ≥5 events and mean gap >0 | The estimand becomes survivor-conditioned; report it |
| Transformation | Change of scale before modelling | `log1p` for lifetime, CV, and volume | Heavy tails are handled by the transform, not by switching to medians |
| n-flow | Counts at each filter | source → dedupe → overlap removal → label known → eligible → analysed | Prevents comparing “who has data” rather than “who is risky” |
| Denominator | The n used for a rate | 5,709 illicit for H6; 4,938 for H4 | Every pass rate needs its exact denominator |
| Missingness / censoring | Undefined or incomplete response | A wallet with only incoming funds has no holding time; a wallet that never sends has censored outflow | Drop only by a stated rule; never silently |

**Scenario.** A wallet with 1 transaction has no lifetime and no CV. A wallet with 10 transactions has both. Comparing them without an eligibility rule mixes different populations.

### 3.2 Applied to H2, H4, H6

| Hypothesis | Primary response | Type / scale | Secondary / descriptive | Eligibility | Transform | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| H2 | `tx_lifetime_days` | Continuous, ratio, days | `burst_ratio`; `h2_pass` | ≥2 events for lifetime; ≥5 USDT events for burst/floor | `log1p` | Lifetime is the broad-coverage precursor; burst is descriptive because of token scope and mass at 1 |
| H4 | none | — | `jaccard_index`; `h4_pass` | Both TRX-funder and USDT-recipient sets non-empty | None / logit if modelled | Zero-inflated and rare; pass rate is the estimand |
| H6 | `cv_delta_t` | Continuous, ratio | `event_count`; `h6_pass` | ≥5 events and mean gap >0 | `log1p` | CV is the secondary response; the rule adds the N ≥ 5 conjunction |

---

## 4. Groups

### 4.1 Definitions and examples

| Term | Definition | TRON example / scenario | Why it matters |
| --- | --- | --- | --- |
| Group / cohort | Set of wallets sharing a factor level | `illicit`, `suspicious`, `unlabeled` | Groups define the populations compared |
| Label | A wallet appears on the chosen blacklist at a snapshot | TronScan blacklist `label = 1` | A label is an administrative observation, not proof of criminality |
| Proximity | A wallet is reachable within k hops from a labeled seed | `min(hop_level) ∈ 1..5` | Proximity is a risk feature, not a label |
| Priority | The rule that resolves overlap | illicit > suspicious > licit > unlabeled | A blacklisted wallet at hop 3 is illicit, not suspicious (`docs/context/cohort_contract.md:12`) |
| Frame | The frozen population the inference is about | The frozen illicit/licit database extract, not all TRON wallets | Counts drift; freeze a snapshot before testing |
| Independence | Whether units are independent | Suspicious wallets reached from the same seed are dependent | i.i.d. tests understate variance |

**Scenario.** A wallet is blacklisted and also appears at hop 3. Priority makes it illicit. A wallet is in the licit database and also in the suspicious set; suspicious wins, and only the leftover is licit. The current licit database has 2,977 blacklisted accounts and 49.7% of a 5,000 suspicious sample in licit, so it is not a clean control (`docs/context/cohort_contract.md:14`).

### 4.2 Applied to H2, H4, H6

| Group | Operational rule | Current status | Role | Reason |
| --- | --- | --- | --- | --- |
| `illicit` | Blacklist `label = 1` at snapshot T; hop-0 adds no new wallets | 15,165–15,185 online; 6,324 local eligible for lifetime | Target arm | Small enough for a census; asserted positive, not proven |
| `suspicious` | `min(hop_level) ∈ 1..5` and not blacklisted | 3,598,120 | Nested / descriptive arm | Graph-derived from illicit seeds; not independent (`docs/context/step_1_profiling_samples.md:65`) |
| `unlabeled` | Universe minus illicit and suspicious | Not computed | Provisional baseline | Unknown, not negative; never call it licit |
| `licit` | External DB minus illicit and suspicious | 6,614,681 raw; contaminated | Target comparison arm after cleaning | Clean overlap before pooling; check sampling frame (`AGENTS.md:32`) |

**Applied to all three hypotheses.** The factor is the same three-level `wallet_class`; the primary clean contrast after cleaning is **illicit vs licit**. `suspicious` is nested/descriptive because it is constructed from the illicit seeds. Use seed-cluster bootstrap or a mixed model; do not use i.i.d. F-tests or i.i.d. Kruskal–Wallis on the full suspicious set (`docs/context/test_plan.md:12`).

---

## 5. Summary: prerequisites for H0 and test choice

| Item | H2 | H4 | H6 |
| --- | --- | --- | --- |
| Research question | Are illicit wallets short-lived and bursty? | Do illicit wallets reuse the same TRX funders and USDT recipients? | Are illicit wallets’ inter-arrival times regular? |
| Rule | lifetime ≤ 7d AND burst ≥ 0.75 | Jaccard ≥ 0.50 | N ≥ 5 AND CV < 0.15 |
| Factor | `wallet_class` | `wallet_class` | `wallet_class` |
| Primary response | `log1p(tx_lifetime_days)` | none (Jaccard descriptive) | `log1p(cv_delta_t)` |
| Rule verdict | `h2_pass` (joint) | `h4_pass` | `h6_pass` (joint) |
| Groups | illicit / suspicious / unlabeled; licit target | same | same |
| Null ingredient | Mean log lifetime equal; pass rate equal | Pass rate equal | Mean log CV equal; pass rate equal |
| Test family | Welch + Games–Howell; KW/Dunn sensitivity; cluster bootstrap; pass rate/ROC | Proportion/Fisher; cluster bootstrap; no ANOVA | Welch + Games–Howell; KW/Dunn sensitivity; cluster bootstrap; pass rate |
| Main reason | Conjunction; burst descriptive; floor reverses | Zero-inflated; 13/4,938 | Direction missing; premise opposite; 0/5,709 |

---

## 6. Decisions required before writing H0

1. **H2 lifetime definition:** rule text “first seen → current date” vs implementation “max − min transaction timestamp”.
2. **H2 token scope:** USDT-only vs all tokens in+out.
3. **H4 TRX funder definition:** any TRX transfer vs gas-only transfer; both-set eligibility.
4. **H6 direction and session:** build IN and OUT series separately; define “operational session”.
5. **H6 direction of the test:** two-sided falsification because the observed CV is opposite the premise.
6. **Third group:** run `H0_U` with `unlabeled` now; run `H0_L` only after licit cleaning.
7. **Independence:** seed-cluster bootstrap or mixed model; report design effect.
8. **Alpha and multiplicity:** α = 0.05; Holm over H2/H6 omnibus; separate family for pairwise and for H4 proportions.
9. **Sample:** census eligible illicit (~6,300); ~50,000 per large arm; n-flow for every response.
10. **Effect sizes:** η²/ω², Cliff’s delta, risk difference/CI; exact denominators.

---

## 7. Sources

- Rule definitions: `docs/hypothesis.md`; duplicate list: `docs/hypothesis_testing/all_hypothesis.md`.
- Variable types and test implications: `docs/hypothesis_testing/variabe_type.md`.
- Cohort contract: `docs/context/cohort_contract.md`.
- Response eligibility and support: `docs/context/step_1_profiling_samples.md:85-104`.
- Test ladder, alpha, dependence: `docs/context/test_plan.md`.
- Feature gaps: `docs/context/feature_audit.md`.
- Feature implementation: `src/notebooks/1.1_ILLICIT_EDA.ipynb` cells 85 (H2), 87 (H4), 89 (H6), 91 (pass flags), 226 (data dictionary).
- Sampling and frame: `outputs/nested-sampling-aml-wallets.md`.
