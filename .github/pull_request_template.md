<!-- Created: 2026-11-27 | Last updated: 2026-11-27 | Edit count: 1 -->
## Scope & Classification

<!-- Must match docs/dev/github_convention.md and AGENTS.md (one narrow scope per PR) -->

- **Area:** `ETL` / `EDA` / `HP_TEST` / `STL` / `general`
- **Subcategory:** *(e.g. `extract`, `clean`, `cohort`, `features`, `load`, `profile`, `univariate`, `h2`, `general`)*
- **Label:** `FEAT` / `BUG` / `DOC` *(use `DOC` only when zero code is changed)*
- **Branch:** `<author>/<area>-<subcategory>`
- **Related task / issue:** *(link to `tasks/...` or `#issue`, or `N/A`)*

## Summary

<!-- Explain WHAT changed and WHY (scenario, problem solved, trade-offs). Keep it concise and technical. -->

- 
- 

## Changed Paths

<!-- Confirm changes stay inside one subcategory, its tests, and its docs -->

- Code: ``
- Tests: ``
- Outputs: ``
- Docs / Tasks: ``

## Data & Quantitative Evidence

<!-- Required for ETL, EDA, Hypothesis Testing, and Statistical Learning PRs. Mark N/A for doc-only PRs. -->

- **Data source / Snapshot ID:** *(e.g. local PostgreSQL mirror or `phase1_raw_illicit_<UTC>` — never `datasets/*.csv`)*
- **Row counts & denominators (`wallet_class × filter` n-flow):**
- **Memory / query check (if SQL or Parquet changed):** *(e.g. SQL-first aggregation, `EXPLAIN (ANALYZE, BUFFERS)` or DuckDB spill notes)*

## Verification

<!-- Paste the exact commands run from the repo root and their pass/fail outcome -->

```bash
# Example:
# pytest src/scripts/etl/transform/profile/tests
# mypy src/scripts/...
```

- **Result:** 

## Checklist

### Git & Scope (`docs/dev/github_convention.md`)
- [ ] Branch follows `<author>/<area>-<subcategory>` and is based on up-to-date `main`.
- [ ] Commit messages follow `[LABEL-subcategory]: <short imperative description>` (lowercase subcategory).
- [ ] Diff touches **one narrow scope** only (no unrelated refactors or cross-folder edits).

### Architecture, SQL & Style (`AGENTS.md`, `CONTRIBUTING.md`, `docs/dev/software_concepts/`)
- [ ] Respects layer boundaries (`L0` mirror is read-only outside `extract/main.py`; `load/main.py` is the sole exporter; notebooks are read-only).
- [ ] SQL-first & memory-safe (no full-table pandas loads, no `SELECT *` on event tables, no `LIMIT` on reported counts).
- [ ] SQL rules followed (no `NOT IN` — uses `NOT EXISTS`, no hop fan-out joins, explicit `GROUP BY`, `IS DISTINCT FROM` where nullable).
- [ ] Naming & typing followed (`wallet_class`, units in names, static type hints, no empty names like `df`/`res`/`tmp`, paths imported from `src/scripts/config.py`).
- [ ] Terminology & cohort rules followed (`S1`–`S6` vs `H1`–`H6`, `H0`/`Ha`, blacklist wins at every hop, `unlabeled` never called `licit`, no crossed `wallet_class × hop`).

### Tests, Outputs, Hygiene & Docs
- [ ] Tests live in the owning `<stage>/tests/` directory (pure-rule, SQL fixture, and n-flow checks where applicable).
- [ ] Outputs follow the Hedgehog layout under `outputs/<area>/...` (no test outputs in `outputs/`).
- [ ] No secrets (`src/.env`, credentials, DB URIs) or unintended `hex_address` columns committed/exported.
- [ ] Affected docs (`README.md`, `docs/dev/`, `tasks/`) updated with date and edit count.
