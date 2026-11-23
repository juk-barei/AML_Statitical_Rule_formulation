# Step 1 concepts, example, and answer structure

**Definitions.** *Response* = continuous outcome measured once per experimental unit. *Factor* = categorical variable whose levels define groups. *Level* = one category. *Unit* = the thing measured (a wallet). *Replication* = independent units per level. *Fixed effect* = levels are the only ones of interest; *random effect* = levels are sampled from a population. *Nested* = levels of B occur only inside one level of A; *crossed* = every A×B cell can occur.

**Lecture example.** Response = exam score; factor = teaching method with 3 levels (lecture, flipped, project); unit = student; n = 5 per level. H0: μA = μB = μC; F(2,12) = 11.36, p = 0.0017, η² = 0.65.

**Capstone mapping.** Response = one rule metric per wallet (primary: `log1p(tx_lifetime_days)`; secondary: `log1p(cv_delta_t)`). Factor = wallet class, 3 levels: illicit, suspicious, licit (external DB, cleaned of illicit/suspicious overlap; unlabeled is provisional). Unit = wallet. Hop depth is nested in suspicious, not crossed.

**Answer structure for Task 01.** 1) Objective and scope; 2) definitions table; 3) classification verdict; 4) response candidates and eligibility; 5) factor/group/nesting specification; 6) independence and test consequences; 7) step-2 handoff; 8) evidence ledger.
