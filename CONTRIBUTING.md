# Contributing to TRON AML Data & Statistical Analysis
<!-- Created: 2026-11-27 | Last updated: 2026-11-27 | Edit count: 1 -->

This repository is a structured research and data-engineering pipeline for AML wallet rule formulation on TRON. Every rule below exists to prevent three real failure modes: **silently corrupting research denominators**, **exhausting laptop RAM on 26M+ transaction rows**, and **tangled multi-folder branches that cannot be reviewed**.

Read this guide before opening your first branch. It explains how the repository is organized, how to extend it without breaking its style, and how branches, commits, and pull requests are reviewed.

---

## 1. Source-of-Truth Map

Do not duplicate rules across files. One fact has one home — check the authoritative document for your task before writing code:

| Document | Owns |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Enforceable project contract: scope gate, data authority, cohort rules, inference constraints, documentation standards, and task tracking. |
| [`docs/dev/github_convention.md`](docs/dev/github_convention.md) | Branch naming, commit label/subcategory rules, and narrow-scope git discipline. |
| [`docs/dev/software_concepts/README.md`](docs/dev/software_concepts/README.md) | Accepted software design baseline (`01`–`05`, `07`, `09`, `10` are normative; `06`, `08` are `proposed` reference only). |
| [`docs/context/glossary.md`](docs/context/glossary.md) | Canonical research terminology (`S1`–`S6`, `H1`–`H6`, `H0`/`Ha`, cohorts, verdicts). |
| [`src/scripts/README.md`](src/scripts/README.md) | Code index, shared `config.py` path constants, writer rules, and output mapping. |
| [`src/scripts/etl/README.md`](src/scripts/etl/README.md) | ETL pipeline commands (`extract`, `transform`, `load`), Parquet export contract, and memory-safe SQL patterns. |
| [`tasks/hypothesis_testing/README.md`](tasks/hypothesis_testing/README.md) | Live 8-step ANOVA workflow tracker (active Phase-1 hypothesis-testing scope: `H2`, `H4`, `H6`). |

---

## 2. Local Environment Setup

All commands run from the repository root (`data_analysis/`). Minimum Python version is **3.14** (`pyproject.toml`).

```bash
# 1. Install core + dev dependencies (pytest, mypy, hypothesis, pandas-stubs)
uv sync --extra dev

# Optional: JupyterLab for official notebooks
uv sync --extra dev --extra notebooks

# 2. Register `src` as an editable package so `python -m src.scripts...` resolves everywhere
uv pip install -e .
```

**Environment variables:**

1. Copy [`src/.env.example`](src/.env.example) to `src/.env` and fill in your local PostgreSQL mirror credentials (`LOCAL_DB_*`) and any source links you need.
2. **Never commit, paste, or print `src/.env` or connection strings** in code, logs, notebooks, or PR descriptions. ETL modules load `src/.env` internally via `src/scripts/etl/db.py`.

**Sanity check:**

```bash
# Verify mirror ingestion status (never mutate the mirror manually)
python -m src.scripts.etl.extract.main --status --schema illicit
python -m src.scripts.etl.extract.main --status --schema licit

# Run stage-local tests
pytest src/scripts/etl/transform/profile/tests
python -m src.scripts.etl.load.tests.load_export
```

---

## 3. Repository Architecture — The Hedgehog Layout

This repository uses the **Hedgehog layout**: every pipeline area is mirrored across code, outputs, tasks, and technical notes so a teammate can jump from a script to its artifacts, tracker, and design rationale without guessing paths.

| Area | Code (`src/scripts/`) | Outputs (`outputs/`) | Trackers (`tasks/`) | Tech Notes (`docs/dev/`) |
| --- | --- | --- | --- | --- |
| **ETL** | `etl/{extract,transform,load}` | `etl/{extract,transform,load}` | `etl/` | `etl/{extract,transform,load}` |
| **EDA** | `eda/{univariate,bivariate,multivariate,profile,additional}` | `eda/{univariate,bivariate,multivariate,profile,additional}` | `eda/` | `eda/...` |
| **Hypothesis Testing** | `hypothesis_testing/{shared,h2,h4,h6}` | `hypothesis_testing/{shared,h2,h4,h6}` | `hypothesis_testing/` | `hypothesis_testing/{general,h2,h4,h6}` |
| **Statistical Learning** | `statistical_learning/` | `statistical_learning/` | `statistical_learning/` | `statistical_learning/` |

### Structural Invariants

- **ETL has exactly three stages:** `extract/`, `transform/`, `load/`. Profiling is **not** a fourth stage — it is the read-only first step inside `transform/profile/` writing to `outputs/etl/transform/profile/{raw,transformed}/`.
- **Transform sections (`L1`–`L3`):** `src/scripts/etl/transform/{profile,clean,cohort,features}/` (see [`src/scripts/etl/transform/README.md`](src/scripts/etl/transform/README.md)).
- **Entry points are named `main.py`:** the folder supplies the context (`extract/main.py`, `load/main.py`), not `extract/extract.py`. Helper modules keep descriptive names.
- **Tests live with the stage they test:** `extract/tests/`, `transform/<section>/tests/`, `load/tests/`, `eda/<section>/tests/`. Do **not** create a top-level `tests/` folder under an area or write test files into `outputs/`.
- **Notebooks live in `src/notebooks/`** and import reusable functions from `src/scripts/`. Notebooks are strictly **read-only** against the PostgreSQL mirror.
- **Never hardcode repo paths:** import path constants (`ROOT`, `OUTPUT`, `ETL_OUTPUT_DIR`, `EDA_OUTPUT_DIR`, etc.) from `src/scripts/config.py`.
- **Do not import from `src/scripts/archive/`:** those are retired helpers.

---

## 4. Data Authority, Layers & Performance Rules

### One-Way Layer Architecture (`L0 → L5`)

Dependencies flow strictly downward (details in [`02-layers-and-boundaries.md`](docs/dev/software_concepts/02-layers-and-boundaries.md)):

| Layer | Owns | Sole Writer | Allowed Readers |
| --- | --- | --- | --- |
| **L0 Raw** | Local PostgreSQL mirror (`illicit.*`, `licit.*`) | `src/scripts/etl/extract/main.py` | L1 transform SQL (read-only) |
| **L1 Clean** | Cross-schema union, `tx_hash` dedupe (`AS transaction_hash`), type unification, drop `hex_address`, non-destructive row flags | `etl/transform/clean/` | L2 cohort builder |
| **L2 Cohort** | 1-row-per-wallet `cohort_wallet` (`wallet_class`, nested `min_hop_level`, seed multiplicity) | `etl/transform/cohort/` | L3 features, L4 analysis |
| **L3 Features** | Wallet-grain aggregates for **all `H1`–`H6`** + eligibility gates + stateless transforms (`log1p`) | `etl/transform/features/` | L4 analysis, L5 export |
| **L4 Analysis** | Profiling, EDA, hypothesis tests (`H2`/`H4`/`H6`), statistical learning | Area modules / notebooks | Humans |
| **L5 Export** | Frozen Parquet + zstd handoff snapshots (`outputs/etl/load/<snapshot>/`) + `manifest.json` + SHA-256 | `src/scripts/etl/load/main.py` | Teammates & web serving |

**Hard boundaries:**
- **Never mix `datasets/*.csv` with PostgreSQL mirror counts.** `datasets/*.csv` is a stale, partial export.
- **Never run `INSERT`, `UPDATE`, `DELETE`, or DDL against `illicit.*` or `licit.*`** outside `extract/main.py`.
- **Transform prepares `H1`–`H6`; hypothesis testing narrows to `H2`/`H4`/`H6` after export.** Do not strip `H1`/`H3`/`H5` features out of `etl/transform/` — teammates depend on the transformed snapshot for those hypotheses and the web app.
- **Stateless vs. stateful scaling:** stateless monotonic transforms (`log1p`, ratios) belong in `etl/transform/features/` (L3). Stateful scalers (Z-score, min-max, `RobustScaler`, percentile Winsorization) **must live in `src/scripts/statistical_learning/`** and fit strictly on training folds to prevent leakage.

### Memory & SQL-First Discipline (16–23 GB Team Target)

> **Failure scenario:** Loading `illicit.transactions` (~15.2M rows) or `licit.transactions` (~11.3M rows) directly into pandas expands 40-char address strings and hashes by 5×–10× and hangs the machine before a single plot renders.

Follow these rules (see [`07-performance-and-observability.md`](docs/dev/software_concepts/07-performance-and-observability.md)):

1. **PostgreSQL computes; pandas displays.** Push filters, joins, deduplication, cohort priority, and wallet aggregations into SQL.
2. **Return small results only.** Select explicit columns (never `SELECT *` on event tables) and return wallet-level aggregates or a bounded sample (`50k–100k` wallets).
3. **Never use `LIMIT` for reported counts.** `LIMIT` is for smoke tests only; reported counts must come from full-frame SQL or full-frame DuckDB scans over frozen Parquet snapshots.
4. **Stream row-level work:** use `engine.connect().execution_options(stream_results=True)` with `pd.read_sql_query(..., chunksize=50_000)`.
5. **Use `COPY` + DuckDB for bulk exports and out-of-core Parquet scans**, not `DataFrame.to_parquet()` over raw transactions.
6. **Sample wallets, never transaction rows.** Keep all events for every selected wallet; record seed, strata, cluster, and weights.

### Mandatory SQL Rules

From [`10-sql-rules.md`](docs/dev/software_concepts/10-sql-rules.md):

- **Ban `NOT IN` in transform SQL** — always use `NOT EXISTS` so a single `NULL` never empties the result set.
- **Prevent fan-out:** use `EXISTS` for presence, or aggregate (`GROUP BY wallet_address`) before joining multi-row tables like `wallet_hops`.
- **Use `IS DISTINCT FROM`** for NULL-safe comparisons.
- **Use explicit `ROWS` frames** for per-wallet running windows (not default `RANGE`).
- **List every non-aggregated column in `GROUP BY`** (L0 mirror tables have no primary keys).
- **Reject `NATURAL JOIN`** and never use `DISTINCT ON` without `ORDER BY`.
- **Keep L0 unindexed;** create join-key indexes only on materialized L1/L2 tables in a dedicated transform schema *after* bulk load when a PostgreSQL join needs them.

---

## 5. Code Style, Naming & Design Baseline

Our normative coding rules live in [`01-complexity-and-modules.md`](docs/dev/software_concepts/01-complexity-and-modules.md), [`04-abstraction-and-dry.md`](docs/dev/software_concepts/04-abstraction-and-dry.md), and [`05-naming-and-comments.md`](docs/dev/software_concepts/05-naming-and-comments.md).

### Naming & Typing

- **Casing:** `snake_case` for variables/functions/modules, `PascalCase` for classes/dataclasses, `UPPER_SNAKE_CASE` for constants.
- **Static type hints are mandatory** on public functions and helpers (check with `mypy`). Do not hide simple types behind aliases unless a complex nested signature repeats.
- **Ban empty names:** never use `data`, `df`, `tmp`, `res`, `result`, `val`, `obj` as function parameters or return names (a local `df` is tolerated only inside a ≤10-line scope where the table is obvious).
- **Name domain, stage, and unit:** `clean_transactions`, `eligible_wallets`, `holding_minutes`, `out_in_volume_ratio`, `wallet_count`. Booleans read as assertions (`is_blacklisted`, `has_both_sets`), never `flag` or `not_blacklisted`.
- **Canonical column names:**
  - Always use **`wallet_class`** in Python, SQL, and output columns (never `group`, `class`, or `label`).
  - Alias raw `tx_hash` once as **`transaction_hash`** in L1 `clean` so L2–L5 use `transaction_hash` consistently.
  - Drop `hex_address` from analysis views and exports unless explicitly required.
- **Rename cleanly without shims:** variable/function names are provisional; when renaming, update Python, SQL, tests, docs, and output columns in **one change** and leave no compatibility aliases behind.

### Module Design & Comments

- **Deep modules over shallow wrappers:** split by hidden decision, not line count. No `utils.py` dumping grounds and no premature `BaseRunner` class hierarchies with caller-specific boolean flags.
- **Pure core, imperative shell:** keep domain rules (e.g., `classify_wallet(facts)`) pure and unit-testable without a database; keep SQL/CLI/file I/O in the shell.
- **Docstring every public module, class, and function:** summary, args, returns, raises, units, and snapshot binding.
- **Comments explain *why*, not *what*:** document invariants (`-- blacklist wins at every hop`), rule provenance (`-- S2: lifetime <= 7 days`), and shortcuts (`# shortcut: <limit>; upgrade when <condition>`). Use `# TODO(task-id): ...` — never bare `TODO`, commented-out code, or `# =====` banners.

### Research & Statistical Integrity

- **Terminology ([`docs/context/glossary.md`](docs/context/glossary.md)):** rules are `S1`–`S6`; research questions are `H1`–`H6`; null/alternative are `H0`/`Ha` (**never `H1`** for the alternative hypothesis).
- **Cohort priority:** `illicit` (blacklisted wallets + hop-0 — **blacklist wins at every hop 1–5**) > `suspicious` (`min(hop_level) ∈ 1..5` and not blacklisted) > `licit` > `unlabeled` (provisional; **never call `unlabeled` licit**).
- **Hop nesting:** hop depth is nested inside `suspicious` — **never** fit a crossed `wallet_class × hop` two-way ANOVA.
- **Dependence & reporting:** `suspicious` is graph-derived from blacklisted seeds (not independent); non-parametric tests do not fix dependence — use seed-cluster permutation/bootstrap, mixed models, or report it descriptively. Always report **snapshot ID, exact denominators, `wallet_class × filter` n-flow tables, and effect sizes** — never p-values alone, and never silently drop zeros or undefined rows.

---

## 6. How to Expand the Repository

Use the matching recipe when adding new functionality:

### Adding an ETL Transform or Feature (`src/scripts/etl/transform/`)

1. Place SQL and Python wrappers in the matching layer folder: `clean/` (L1), `cohort/` (L2), or `features/` (L3).
2. Apply cleaning and eligibility rules **identically across every cohort arm** and emit a `wallet_class × filter` n-flow table.
3. Add tests in `src/scripts/etl/transform/<section>/tests/`:
   - a **pure-rule unit test** (no DB),
   - a **SQL fixture test** (including nullable anti-join / fan-out edge cases), and
   - an **n-flow assertion** verifying counts reconcile.
4. Write outputs under `outputs/etl/transform/<section>/` and document the mechanism/limits in `docs/dev/etl/transform/<section>/`.

### Adding an EDA Module or Plot (`src/scripts/eda/`)

1. Follow the Lecture 02 order in [`src/scripts/eda/README.md`](src/scripts/eda/README.md) (`profile`, `univariate`, `bivariate`, `multivariate`, `additional`).
2. Write **reusable module functions** (one function per plot, returning `(fig, ax)`), accepting bounded DataFrames or profile CSVs — never inline throwaway logic inside notebooks.
3. Print the supporting numbers alongside every figure and save both figure and supporting table under `outputs/eda/<section>/` with snapshot ID, arm, and denominator.
4. Add unit/smoke tests under `src/scripts/eda/<section>/tests/`.

### Adding Hypothesis Testing (`src/scripts/hypothesis_testing/`) or Statistical Learning (`src/scripts/statistical_learning/`)

- Follow the Lecture 05 eight-step ANOVA workflow tracked in [`tasks/hypothesis_testing/README.md`](tasks/hypothesis_testing/README.md).
- Keep `h2/`, `h4/`, `h6/` runners separate and composable; extract to `shared/` only when knowledge genuinely stabilizes across hypotheses.
- Update the touched step `main.md` and hypothesis tracker (`H2.md`, `H4.md`, or `H6.md`), moving `done` task files to `tasks/_archive/hypothesis_testing/<step>/` (never delete done tasks).

### Adding a New Top-Level Directory or Software Concept

- **New top-level area/output/task folder:** update [`AGENTS.md`](AGENTS.md) and [`src/scripts/README.md`](src/scripts/README.md) in the same PR so the Hedgehog mapping stays intact.
- **New architecture blueprint (`docs/dev/software_concepts/`):** create a numbered topic file (`Status → Scenario → Code → Rule → Debate`), add it to the index with `Status: proposed`, and let the project maintainer approve it. Never flip `Status:` to `approved` yourself.
- **Post-implementation technical notes (`docs/dev/<area>/<unit>/<mechanism>.md`):** write after implementation settles; explain mechanism, trade-offs, failure modes, and verification. Include a date and edit-count header (`<!-- Created: YYYY-MM-DD | Last updated: YYYY-MM-DD | Edit count: 1 -->`) and increment it on each edit.

---

## 7. Git Workflow: Branches, Commits & Pull Requests

Full rules live in [`docs/dev/github_convention.md`](docs/dev/github_convention.md).

### 1. Keep Every Branch Narrow-Scoped

A branch and PR must own **one subcategory**, its matching tests, and the docs that describe it. Do not mix unrelated folders or bundle drive-by cleanups into a feature branch. Many small, clean branches are expected and encouraged.

### 2. Branch Naming

Always branch from an up-to-date `main`:

```text
<author>/<area>-<subcategory>
```

Examples:
- `layhok/etl-clean`
- `layhok/eda-profile`
- `hong/hp_test-h2`
- `layhok/general-contributing` *(use `general` only for repo-wide files that do not belong to a pipeline area)*

### 3. Commit Message Format

```text
[LABEL-subcategory]: <short imperative description>
```

- **Labels:**
  - `FEAT` — new feature, script, transform, plot, or notebook code (use `FEAT` even if docs are updated alongside the code).
  - `BUG` — bug fix, cleanup of stale files, refactor fix, or dependency fix.
  - `DOC` — **documentation-only** commits with zero code changes.
- **Subcategory:** always **lowercase** (`extract`, `transform`, `load`, `clean`, `cohort`, `features`, `profile`, `univariate`, `bivariate`, `h2`, `h4`, `h6`, or `general` for repo-wide docs/config only).

Examples:
- `[FEAT-cohort]: implement blacklist-first wallet_class priority SQL and fixture tests`
- `[BUG-univariate]: fix log-scale tick formatting on fan-in distribution plot`
- `[DOC-load]: document Parquet zstd export contract and manifest schema`
- `[DOC-general]: add contributing guide, code of conduct, and PR template`

### 4. Pre-PR Verification Checklist

Before opening a Pull Request against `main`:

1. **Tests pass:** run the stage's `pytest` / verification scripts and `mypy` on modified modules.
2. **Scope is clean:** `git diff --stat main` touches only the declared subcategory, its tests, and its docs.
3. **No leaks or stale artifacts:** no `src/.env`, credentials, raw `hex_address` exports, or unlabelled partial numbers.
4. **Docs & trackers are fresh:** update affected module `README.md`, `docs/dev/` notes (with date + edit count), and `tasks/` statuses.
5. **Fill out the PR template completely:** GitHub automatically loads [`.github/pull_request_template.md`](.github/pull_request_template.md) — include exact commands run and quantitative evidence (snapshot ID, denominators, n-flow) for any data or analysis change.

---

## 8. Code of Conduct

All contributors are expected to follow [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Direct technical critiques are welcome; personal attacks, sloppy unverified claims, and silent data shortcuts are not.
