# Glossary — canonical terms
<!-- Last updated: 2026-11-28 | Edit count: 2 -->

Status: authoritative. Use these words in every doc, task, and notebook.

## Rules and hypotheses

| Term | Canonical form | Meaning | Never write |
| --- | --- | --- | --- |
| Rule | `S1`–`S6` | AML decision function and thresholds in `docs/dev/hypothesis_testing/general/all_hypothesis.md`. | "rule H2" |
| Research question | `H1`–`H6` | Empirical claim a rule assumes; `Hn` ↔ `Sn`. | "hypothesis S2" |
| Null hypothesis | `H0(Hn)` | Population parameter equal across groups. | "H0 of the rule" |
| Alternative hypothesis | `Ha(Hn)` | The rule's predicted direction. **Never `H1`** — that is research question 1. | `H1(H2)` |
| Verdict | `support` / `contradict` / `underpowered` | Evidence decision, not proof of a rule. | "hypothesis proven" |

A mean test is a **precursor**. A **rule verdict** compares pass rates (`P(rule passes | group)`), ROC, or PR — not means.

## Cohorts and frames

- Implemented levels (frozen in `phase1_transformed_transform_20261127T224625Z`, `cohort_wallet.parquet`): `illicit` (`17,046`), `suspicious` (`3,959,525`), `licit` (`5,180,495`), and `unlabeled` (`719,801`). Total: `9,876,867` wallets. The term `background` is retired.
- `licit` is the external DB **after** removing `illicit` and `suspicious` overlap (`1,434,186` removed). Never pool `unlabeled` into `licit`.
- Frame suffix: `_U` = legacy unlabeled frame (historical pre-transform), `_L` = clean licit frame (current active target). Examples: `H0_L`, `Ha_L`.
