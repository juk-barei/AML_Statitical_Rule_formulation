# Data and Statistical Analysis for Rule formulation for AML in Crypto

Phase 1 tests whether rule-derived features separate illicit from licit crypto
wallets. Active hypotheses are **H2, H4, H6**; **H1, H3, H5** are deferred.

## Start here

- [`AGENTS.md`](AGENTS.md) — project contract: data authority, cohort definitions, inference rules, workflow, output layout. Read this first.
- [`src/scripts/README.md`](src/scripts/README.md) — code index: module areas, shared helpers, writer rule.
- [`tasks/hypothesis_testing/README.md`](tasks/hypothesis_testing/README.md) — the live 8-step ANOVA tracker for H2/H4/H6.
- [`tasks/etl/README.md`](tasks/etl/README.md) — the shared data gate every hypothesis depends on.

## Current directives

The enforceable version of each of these is in [`AGENTS.md`](AGENTS.md); this is
only a pointer, not a second copy of the rules.

- The **PostgreSQL mirror** is the analysis dataset; `datasets/*.csv` is a stale, partial export and is never mixed with mirror counts.
- Cohorts are `illicit`, `suspicious`, `licit`, `unlabeled` — see the cohort table in [`AGENTS.md`](AGENTS.md); blacklist priority applies at every hop, and `unlabeled` is never called licit.
- `suspicious` is graph-derived and nested, so inference needs seed-cluster permutation/bootstrap or a clearly descriptive framing; see the inference rules in [`AGENTS.md`](AGENTS.md).
- `src/scripts/etl/ingest.py` is the only writer of the mirror and `src/scripts/etl/load.py` the designated writer for exports; notebooks are read-only. Details in [`src/scripts/etl/README.md`](src/scripts/etl/README.md).
- EDA follows Lecture 02, inference follows the Lecture 05 eight-step ANOVA workflow; output folders mirror `src/scripts/` — see [`src/scripts/README.md`](src/scripts/README.md).

## Prerequisites

You can adopt the project to your development workflow. As of mine, I use `uv` as the package manager. Here is the list of prerequisites:

- `uv`: [install here only if you want](https://docs.astral.sh/uv/getting-started/installation/)
- minimum `python-version`: 3.14

## QuickStart

Run everything from the repo root (`data_analysis`).

1. Sync the packages:

   ```bash
   uv sync
   ```

2. Install the project in editable mode:

   ```bash
   uv pip install -e .
   ```

   This registers `src` as an importable package in `.venv`, so modules run as
   `python -m src.scripts...` from any working directory. The layout relies on
   `src/__init__.py` and `src/scripts/__init__.py`; do not rename or delete them.

3. Create `src/.env` from `src/.env.example` and fill in the database
   connection variables. `src/.env.example` is the variable contract; never
   commit or print `src/.env`.

4. Check where ingestion stands:

   ```bash
   python -m src.scripts.etl.ingest --status
   ```

   Ingestion and export rules are in [`src/scripts/etl/README.md`](src/scripts/etl/README.md).

5. Open `src/notebooks/1.1_ILLICIT_EDA.ipynb`. It is read-only against the local
   mirror and writes to `outputs/eda/`; the licit series has its own notebook,
   `src/notebooks/1.2_LICIT_EDA.ipynb`.

## Repository layout

| Path | Contents |
| --- | --- |
| [`src/`](src) | `scripts/` for analysis code and helpers, `notebooks/` for the official analysis notebooks. Areas and their output folders are indexed in [`src/scripts/README.md`](src/scripts/README.md). |
| [`docs/`](docs) | Durable decisions in `docs/context/`, hypothesis write-ups in `docs/hypothesis_testing/`, plus external references. |
| [`outputs/`](outputs) | Artifacts, one folder per producing area: `outputs/etl/{profile,tests,transform,export}`, `outputs/eda/{univariate,bivariate,multivariate,profile,additional}`, `outputs/hypothesis_testing/{shared,h2,h4,h6}`, `outputs/statistical_learning/`. Handoff snapshots live in `outputs/etl/export/<snapshot>/`. |
| [`tasks/`](tasks) | Task trackers: `tasks/etl/`, `tasks/eda/`, `tasks/hypothesis_testing/` (the 8-step workflow), `tasks/statistical_learning/`. Start at [`tasks/hypothesis_testing/README.md`](tasks/hypothesis_testing/README.md). |

## LICENSE

The Repository is under the MIT LICENSE.

## Author: Layhok Leng
