# Current progress vs the 8-step ANOVA workflow

Status: **completed** / **not completed** / **not started**.

| Step | Status | Evidence / gap |
| --- | --- | --- |
| 1. Response, factor, groups | **Not completed** | Online profile done; cohort contract drafted. Licit overlaps illicit/suspicious and still needs cleaning. |
| 2. H0, H1, α | **In progress** | `docs/context/test_plan.md`: H0_U written for illicit/suspicious/unlabeled; H0_L awaits licit cleaning. |
| 3. Explore boxplots/means | **Not completed** | Plot code exists; notebook not restructured or executed. |
| 4. Assumptions | **Not started** | No Shapiro–Wilk, Levene, Q–Q, or independence diagnostics. |
| 5. F-test / Welch / KW | **Not started** | No omnibus test implemented. |
| 6. Post-hoc Tukey | **Not started** | No Games–Howell, Dunn, or Tukey. |
| 7. Effect size η² | **Not started** | Cliff’s delta only; no η²/ω². |
| 8. Conclusion in context | **Not completed** | Screening verdicts only; no ANOVA conclusion. |

**Gaps.** Local PostgreSQL is down; licit is contaminated (2,977 blacklisted accounts; 49.7% of a suspicious sample); H4 has 13 illicit passes, H6 has 0; online counts are live and move between runs.
