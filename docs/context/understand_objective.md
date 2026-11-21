# Product objective

**Goal.** Produce an interpretable, statistically defensible risk score for TRON wallets that ranks addresses for AML investigation. This is a prioritisation tool, not a guilt verdict and not a binary classifier.

**Phase 1 (current).** Define rules H1–H6 (scope: H2/H4/H6), build three wallet cohorts, test whether rule features separate them, calibrate thresholds, and combine weighted rule scores: `S(A) = Σ wᵢsᵢ`, `R(A) = min(10, S)`. Deliver a rule specification, evidence tables, and limitations on the seed data. This part is about rule based.

**Phase 2 (planned, from `docs/flow.md`).** Estimate weights from data (logistic regression, mutual information, or ROC/PR optimisation), validate out-of-sample, and monitor Type I/II error after deployment. Refresh with new blacklists. This part is basically building our model.

**Out of scope.** Proving criminality; precision/recall claims without an independent licit sample; treating unlabeled wallets as normal.

**Success.** Every retained rule has a documented response, separation evidence, effect size, threshold trade-off, and reproducible artifact.
