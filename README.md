# Data and Statistical Analysis for Rule formulation for AML in Crypto
- **Hypothesis covered**: 2,4,6
## Current directives
Agent-facing rules are in [`AGENTS.md`](AGENTS.md). Current corrections:
- Analysis data is the **PostgreSQL mirror**. `datasets/*.csv` is a stale, partial export; do not mix the two.
- **Cohorts:** `illicit` = blacklist ∪ hop-0; `suspicious` = `min(hop) 1–5` and not blacklisted; `licit` = external licit DB (**ingestion pending**); `unlabeled` = provisional, **not licit**.
- **Priority:** any blacklist record at hop 1–5 makes the wallet illicit, not suspicious — not just hop 3.
- **Inference:** non-parametric tests relax normality/variance, not dependence. `suspicious` is nested; use seed-cluster inference or report it as descriptive. Illicit vs licit is the clean independent contrast once licit is ingested.
- **Workflow:** EDA follows Lecture 02; inference follows the Lecture 05 eight-step ANOVA workflow. `src/scripts/ETL.py` is the only writer; notebooks are read-only.
- Drop `hex_address` from analysis views unless a task explicitly needs it.

See [`docs/context/step_1_profiling_samples.md`](docs/context/step_1_profiling_samples.md) for the step-1 record.

## Prerequisites
You can adopt the project to your development workflow. As of mine, I use `uv` as the package manager. Here is the list of prerequisites:
- `uv`: [install here only if you want](https://docs.astral.sh/uv/getting-started/installation/)
- minimum `python-version`: 3.14

## QuickStart
As the dataset files are too big, I don't include in here. You can use the database I provided for phase 1 and set it in .env file. Further instruction is in step 6. Run the following commands In the root directory (`data_analysis`):
1. Sync the packages:

   ```bash
   uv sync
   ```

2. Install the project in editable mode:

   ```bash
   uv pip install -e .
   ```

   This registers `src` as an importable package in `.venv`, so the analysis
   code is importable as `src.scripts.ETL` from any working directory. The
   package layout relies on these two files; do not rename or delete them:

   - `src/__init__.py`
   - `src/scripts/__init__.py`

   Verify the install before starting Jupyter:

   ```bash
   python3 -c "from src.scripts.ETL import load_analysis_tables, print_ingestion_status; print('import ok')"
   ```

   Re-run `uv pip install -e .` after moving or renaming modules under `src/`.

5. Activate the virtual environment:

   ```bash
   source .venv/bin/activate
   ```

   Alternatively, prefix commands with `uv run` and skip activation.

6. Add database credentials to `src/.env`:

   ```dotenv
   ILLICIT_ONLINE_DATABASE_LINK=postgresql://user:password@host:port/database
   LICIT_ONLINE_DATABASE_LINK=postgresql://user:password@host:port/database
   LOCAL_DB_NAME=capstone_1
   LOCAL_DB_USER=your_user
   LOCAL_DB_HOST=localhost
   LOCAL_DB_PASS=your_password
   ```

7. Ingest the cloud tables into the local PostgreSQL mirror in batches. The
   script uses up to five worker processes:
   ```bash
   python3 src/scripts/ETL.py --workers 5 --batch-size 50000
   ```
8. Use `--status` from another terminal to watch progress while rows are still
   being written:

   ```bash
   python3 src/scripts/ETL.py --status
   ```
   Alternatively, you can also use command named `ingest`. cuz I have built it as command in build file. I recommend this usage than the other one for ease of usage.
   ```bash
   ingest --status
   ```
   The final per-table source/local row-count report is written to
   `outputs/ETL/ingestion_report.csv`.

9. Open `src/notebooks/1.1_ILLICIT_EDA.ipynb`. It is read-only against the local db mirror
   and imports `load_analysis_tables()` from `src/scripts/ETL.py`. Its artifacts
   are written to `outputs/EDA_ILLICIT/`; the external licit series has a
   separate notebook and output directory:

   ```python
   from src.scripts.ETL import load_analysis_tables, print_ingestion_status
   ```
   Restart the Jupyter kernel after re-running `uv pip install -e .` so the
   new import path is picked up.

## How to use this directory
- `src`: source code for analytical task.
- `docs`: look at the hypothesis and resources
- `datasets`: datasets for doing the statistical analysis
- `outputs`: the output from the analysis(figures, documentation, files...).
- `tasks`:  Keep track of all tasks in sequence. Feel free to draft ideas in ther. start at [tasks/README.md](tasks/README.md).
- `tasks/hypothesis_testing`: 8-step tracker for hypothesis testing for agents and humans.

### How to use the `src` directory
- `scripts` / `.py` files are for temporary inspection or intro.
- `notebooks` / `.ipynb` files are the real deal. They are the content.

### ETL options
```bash
# See all options and help messages
ingest --help
# Ingest every discovered table from the illicit DB into public
ingest

# Ingest the licit DB into a separate schema
ingest --source licit --schema licit --source-schema public

# Cap rows per table (useful for a fixed phase-1 sample)
ingest --source illicit --schema illicit \
  --row-limits accounts=100000,transactions=500000,wallet_hops=200000

# Read a specific source/table
ingest --source illicit --schema illicit --tables accounts

# Resume the latest failed/interrupted run; completed shards are skipped
ingest --resume

# Plan and count source rows without writing
ingest --dry-run

# Ingest selected tables, or skip index creation
ingest --tables accounts,transactions
ingest --skip-indexes

# Print the latest run progress
ingest --status
```
Progress is stored in the local `_etl_progress` table (one row per shard) and
`_etl_runs` (one row per run). The notebook's `print_ingestion_status()` reads
the same tables.

See [outputs/eval_columns.md](outputs/eval_columns.md) for the H2/H4/H6 column
contract and the columns that are intentionally dropped from the analysis view.

## LICENSE
The Repository is under the MIT LICENSE.

## Author: Layhok Leng
