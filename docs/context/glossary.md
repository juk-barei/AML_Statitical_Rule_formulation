# Glossary — canonical terms

Status: authoritative. Use these words in every doc, task, and notebook.

## Rules and hypotheses

| Term | Canonical form | Meaning | Never write |
| --- | --- | --- | --- |
| Rule | `S1`–`S6` | AML decision function and thresholds in `docs/hypothesis.md`. | "rule H2" |
| Research question | `H1`–`H6` | Empirical claim a rule assumes; `Hn` ↔ `Sn`. | "hypothesis S2" |
| Null hypothesis | `H0(Hn)` | Population parameter equal across groups. | "H0 of the rule" |
| Alternative hypothesis | `Ha(Hn)` | The rule's predicted direction. **Never `H1`** — that is research question 1. | `H1(H2)` |
| Verdict | `support` / `contradict` / `underpowered` | Evidence decision, not proof of a rule. | "hypothesis proven" |

A mean test is a **precursor**. A **rule verdict** compares pass rates (`P(rule passes | group)`), ROC, or PR — not means.

## Cohorts and frames

- Implemented levels: `illicit`, `suspicious`, `unlabeled`. The term `background` is retired.
- `licit` is the external DB **after** removing illicit/suspicious overlap; it is the third *target* level, not yet implemented.
- Frame suffix: `_U` = unlabeled frame (current), `_L` = licit frame (target). Examples: `H0_U`, `Ha_L`.
