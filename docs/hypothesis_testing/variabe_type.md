# Variable types for H2, H4, H6

**Status:** reference for test selection. **Unit:** one wallet. **Canonical terms:** `docs/context/glossary.md`.

Detail is necessary here because variable type, scale, and dependence determine the test; a single "continuous" label is not enough.

## 1. Rule-to-variable map

| Hypothesis | Rule condition | Required source variables | Derived wallet-level variable | Type / scale | Current implementation / gap |
| --- | --- | --- | --- | --- | --- |
| **H2 (S2)** — lifetime | total operational lifetime ≤ 7 days | `wallet_first_seen_date`, `current_date` (rule text); `transactions.block_timestamp` (implementation) | `tx_lifetime_days = max(block_timestamp) − min(block_timestamp)` | Continuous, ratio, days | Rule text says first-seen → current date; implementation uses transaction span. `accounts.first_seen_timestamp` and `created_date` are ~96% null (`outputs/profiling/columns.csv`). These are different variables; decide before testing. |
| **H2 (S2)** — burst | max 1-hour transaction volume (in+out) ≥ 75% of lifetime volume | `transactions.amount`, `block_timestamp`, `from_address`, `to_address`, `token_symbol` | `total_volume_usdt`, `max_1h_volume_usdt`, `burst_ratio = max_1h / total` | Continuous, bounded [0,1] | Implemented on **USDT only**; `docs/hypothesis.md` says volume in+out, not token-specific (`docs/context/feature_audit.md`). Token scope unresolved. |
| **H2** — activity floor | eligibility guard, not a rule condition | `transactions.token_symbol`, `from_address`, `to_address` | `usdt_event_count` | Discrete count | Floor `N ≥ 5` USDT events. H2 pass rates reverse when this floor is applied (`docs/context/feature_audit.md`). Report both. |
| **H4 (S4)** — Jaccard | Jaccard index of TRX funders vs USDT recipients ≥ 0.50 | `transactions.token_symbol`, `from_address`, `to_address`; `contract_address` to identify USDT | `trx_funder_count`, `usdt_recipient_count`, `jaccard_index` | Continuous, bounded [0,1] | Uses distinct `(wallet, counterparty)` pairs; amounts not needed. Defined only when both sets are non-empty. “TRX funder” is any TRX transfer, not necessarily gas. |
| **H6 (S6)** — CV | N ≥ 5 events in an operational session and CV of inter-arrival times < 0.15 | `tx_hash`, `block_timestamp`, `block_number`, `from_address`, `to_address`, `direction` (IN/OUT) | `wallet_events`, `inter_arrival_seconds`, `cv_delta_t = std / mean`, `event_count` | Continuous, ratio; count | Implementation pools IN and OUT events and does not carry `direction` (`docs/context/feature_audit.md`). “Operational session” is not defined; CV uses the whole observed history. |
| **All** — grouping | `wallet_class` | `blacklisted_wallets.wallet_address`, `.label`; `wallet_hops.wallet_address`, `.hop_level`, `.seed_address` | `wallet_class` = `illicit` / `suspicious` / `unlabeled` (current); `licit` target after cleaning | Categorical, nominal, 3 levels | Priority: illicit > suspicious > licit > unlabeled. Current third level is `unlabeled`, not `licit` (`AGENTS.md:8,22`). |

## 2. Analysis variables and types

| Variable | Type / scale | Role | Distribution / missingness | Test implication |
| --- | --- | --- | --- | --- |
| `wallet_class` | Categorical, nominal, 3 levels | Factor | Current: illicit, suspicious, unlabeled. Licit requires cleaning: 2,977 blacklisted licit accounts and 49.7% of a 5,000 suspicious sample overlap licit (`docs/context/cohort_contract.md:14`). | One-way factor. Do not cross with hop. |
| `tx_lifetime_days` | Continuous, ratio, days | H2 primary response | Right-skewed; 6,324 illicit with ≥2 events. | `log1p` + Welch ANOVA; KW/Dunn as sensitivity; seed-cluster bootstrap. |
| `burst_ratio` | Continuous, bounded [0,1] | H2 descriptive / threshold | Mass at 1 for one-shot wallets; 4,640 illicit with ≥5 USDT events. | Pass-rate / ROC; beta regression if modelled continuously. Not a primary ANOVA response. |
| `jaccard_index` | Continuous, bounded [0,1] | H4 descriptive / threshold | Zero-inflated: zero for 77.7% of eligible illicit; 4,938 eligible; 13 pass ≥0.50. | Pass-rate / ROC / Fisher; not ANOVA. Report 13/4,938 with CI. |
| `cv_delta_t` | Continuous, ratio | H6 secondary response | Right-skewed; 5,695 illicit with ≥5 events and mean gap > 0; 0 pass <0.15. | `log1p` + Welch ANOVA; KW/Dunn sensitivity; but direction is missing and premise is opposite. |
| `event_count` | Discrete count | Eligibility / activity covariate | 5,709 illicit with ≥5 events. | Negative binomial / Poisson; or use as activity band. Not a primary response. |
| `total_volume_usdt` | Continuous, ratio, token units | Descriptive | Heavy-tailed; USDT only. | `log1p`; descriptive, not primary. |
| `max_1h_volume_usdt` | Continuous, ratio, token units | Numerator of `burst_ratio` | Heavy-tailed; USDT only. | `log1p`; descriptive. |
| `account_lifetime_days` | Continuous, ratio, days | Covariate / descriptive | ~96% null in illicit `accounts`; not the H2 primary feature. | Do not substitute for `tx_lifetime_days` without stating the change. |
| `hop_level` | Ordinal, 0–5 | Nested factor / sensitivity | Exists only for suspicious (1–5); hop 0 is illicit. | Ordinal trend within suspicious; not crossed with class. |
| `seed_address` | Identifier / cluster | Random effect | 5,931 seeds; 216,776 wallets reachable from >1 seed. | Mixed model or seed-cluster bootstrap; not a fixed factor. |
| `token_symbol` | Categorical, nominal (USDT, TRX) | Filter / stratifier | H2 burst is USDT-only; H4 needs both. | Decide token scope before testing; native TRX is largely gas. |
| `direction` | Categorical, nominal (IN/OUT) | H6 requirement | Required by `docs/hypothesis.md`; not carried in the current event table. | Build IN and OUT series separately; do not use `wallet_hops.direction` (that is BACKWARD/FORWARD traversal). |
| `h2_pass`, `h4_pass`, `h6_pass` | Binary | Rule verdict | H2 has two conjuncts; H4 13/4,938; H6 0/5,709. | Two-proportion test / Fisher / cluster bootstrap; report risk difference and CI. |
| `wallet_address`, `tx_hash`, `via_tx_hash` | Identifier | Join / dedup | Not analysis variables. | Drop from analysis views unless needed. |

## 3. Parametric vs non-parametric decision

| Variable family | Parametric path | Non-parametric path | Project decision |
| --- | --- | --- | --- |
| Continuous, right-skewed (lifetime, CV, volume) | `log1p` then Welch ANOVA + Games–Howell | Kruskal–Wallis + Dunn as sensitivity | Use `log1p` + Welch as primary; KW/Dunn only on independent arms. Non-parametric tests do not fix dependence (`AGENTS.md:30-31`; `docs/context/test_plan.md:14`). |
| Bounded ratio with mass at 0 or 1 (burst, Jaccard) | Beta regression / logit | KW or pass-rate comparison | Use pass-rate / ROC / PR for rule verdicts. KW tests distributions, not medians. |
| Binary pass/flag | Two-proportion z / logistic | Fisher exact / permutation | Rule verdict = `P(pass \| group)`, not a mean test (`docs/context/glossary.md:15`). |
| Count (event count) | Negative binomial / Poisson | KW | Use as eligibility or activity band; not the primary response. |
| Ordinal (hop level) | Ordinal logistic / trend test | KW | Nested inside suspicious; not crossed with class. |
| Categorical nominal (class, token, direction) | Factorial / chi-square association | Fisher exact | Factor or stratifier; decide token scope before testing. |
| Cluster (seed) | Mixed model | Seed-cluster bootstrap / permutation | All seeds are blacklisted; do not use i.i.d. F-tests or i.i.d. KW on the full suspicious set (`docs/context/test_plan.md:12`). |

## 4. Hypothesis-specific cautions

- **H2 is a conjunction, not one mean.** `tx_lifetime_days` is the primary response and a precursor; `burst_ratio` is descriptive. A mean test alone cannot validate H2 (`docs/context/test_plan.md:18`; `docs/context/step_1_profiling_samples.md:98`). The rule verdict is the joint pass rate.
- **H4 is zero-inflated and rare.** Jaccard is defined only when both sets are non-empty; only 13/4,938 eligible illicit wallets pass ≥0.50. Use counts and intervals, not a mean test.
- **H6 has three gaps.** Direction is not carried; the “operational session” is undefined; and the observed CV ordering is opposite the premise (0/5,709 illicit pass). Treat it as a falsification test, not confirmation.
- **Grouping is not independent.** `suspicious` is graph-derived from blacklisted seeds; 194,674 wallets appear at >1 hop and 216,776 are reachable from >1 seed (`docs/context/step_1_profiling_samples.md:65`). Inference is at the seed-cluster level.

## 5. Code and data references

- Rule definitions: `docs/hypothesis.md`; duplicate rule list: `docs/hypothesis_testing/all_hypothesis.md`.
- Feature implementation: `src/notebooks/1.1_ILLICIT_EDA.ipynb` cells 85 (H2), 87 (H4), 89 (H6), 91 (pass flags), 226 (data dictionary).
- Source columns and null shares: `outputs/profiling/columns.csv`.
- Response eligibility and support: `docs/context/step_1_profiling_samples.md:85-104`; `docs/context/test_plan.md`.
- Test ladder and dependence: `docs/context/test_plan.md`; `AGENTS.md`.
