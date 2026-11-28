# Cohort contract v2
<!-- Last updated: 2026-11-28 | Edit count: 2 -->

- **Status:** done (materialized in PR #41 `src/scripts/etl/transform/cohort/` and exported in `phase1_transformed_transform_20261127T224625Z`)
- **Blocked by:** `02_group_validation.md` (done)
- **Blocks:** `05_licit_ingestion_etl.md` (done), Steps 2–8 (unblocked)
- **Owner:** subagent + user execution
- **Output:** `outputs/etl/load/phase1_transformed_transform_20261127T224625Z/phase1_transformed_transform_20261127T224625Z__cohort_wallet.parquet` (`9,876,867` wallets)
- **Updated:** 2026-11-28

## Objective

Define `illicit = blacklist ∪ hop-0`, `suspicious = min(hop) 1–5 minus blacklist`, `licit = external DB minus illicit/suspicious`, `unlabeled = rest`. Any blacklist record at hop 1–5 is illicit.

## Result (reconciled snapshot `phase1_transformed_transform_20261127T224625Z`)

- `illicit`: `17,046` (`8,306` blacklisted wallets in hops promoted to `illicit`)
- `suspicious`: `3,959,525` (`min_hop_level ∈ 1..5`, strictly nested; includes `27,017` hop-only wallets)
- `licit`: `5,180,495` (`6,614,681` raw minus `3,387` illicit and `1,430,799` suspicious overlap; `6/721` contaminated seeds flagged)
- `unlabeled`: `719,801`
- Total: `9,876,867` wallets (1 row per wallet, `min_hop_level IS NULL` outside `suspicious`).
