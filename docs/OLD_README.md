# Data and Statistical Analysis for Rule formulation for AML in Crypto

> Historical archive. Superseded by [`../README.md`](../README.md). Paths below may refer to the pre-refactor layout.

- **Hypothesis covered**: 2,4,6

## Prerequisites
You can adopt the project to your development workflow. As of mine, I use `uv` as the package manager. Here is the list of prerequisites:
- `uv`: [install here only if you want](https://docs.astral.sh/uv/getting-started/installation/)
- minimum `python-version`: 3.14

## QuickStart
As the dataset files are too big, I don't include in here. Run the following commands
In the root directory (`data_analysis`):
1. Create and enter the datasets directory

```mkdir -p datasets```

2. Download files from Google Drive using gdown (Ensure you replace the URL with your target Google Drive folder link)

```gdown --folder https://drive.google.com/drive/folders/16k2BfE3yQ5nHYVRCJZfpcqm6NdiagCxE -O datasets/```

3. Unzip any nested zip archives

```unzip "datasets/*.zip" -d datasets/```

4. Clean up downloaded zip files

```rm -f datasets/*.zip```

5. Sync the packages

```uv sync```

6. setup build tools for project:

```uv pip install -e .```

7. Activate the virtual environment:

```source .venv/bin/activate```

8. Add database credentials to `src/.env`:

```dotenv
ONLINE_DATABASE_LINK=postgresql://user:password@host:port/database
LOCAL_DB_NAME=capstone_1
LOCAL_DB_USER=your_user
LOCAL_DB_HOST=localhost
LOCAL_DB_PASS=your_password
```

9. Ingest the cloud tables into the local PostgreSQL mirror in batches. The
   script uses up to five worker processes:

```bash
python3 src/scripts/ETL.py --workers 5 --batch-size 50000
```

Use `--status` from another terminal to watch progress while rows are still
being written:

```bash
python3 src/scripts/ETL.py --status
```

The final per-table source/local row-count report is written to
`outputs/ETL/ingestion_report.csv`.

10. Open `src/notebooks/1_EDA.ipynb`. It is now read-only against the local
    mirror and calls `load_analysis_tables()` from `src/scripts/ETL.py`.

11. **NOT WORKING YET**: Run the whole workflow:

`python3 main.py`

Result will be stored in the `outputs` directory.
For now run in each file. Eg:

```python3 src/scripts/processing.py --debug 1```

## How to use this directory
- `src`: source code for analytical task.
- `docs`: look at the hypothesis and resources
- `datasets`: datasets for doing the statistical analysis
- `outputs`: the output from the analysis(figures, documentation, files...).

### How to use the `src` directory
- `.ipynb` files are for temporary inspection or intro.
- `.py` files are the real deal. They are the content.

**Note**: I am doing a personal experiment to see if using `.py` files will make the data/ML coding more smooth than using `.ipynb` files. And `.py` is a text file that could be opened in terminal-based text editor with no need for plugin. `.ipynb` files requires me to install plugin, pushing me to use either jupyterlab or vscode with plugins.
**NOTE**: ETL is in `src/scripts/ETL.py`. It is the only code that writes to the database. The notebook only reads the local mirror, so ingestion can continue while analysis cells are running.

### ETL options

```bash
# Ingest every discovered table (default: all tables)
python3 src/scripts/ETL.py

# Resume the latest failed/interrupted run; completed shards are skipped
python3 src/scripts/ETL.py --resume

# Plan and count source rows without writing
python3 src/scripts/ETL.py --dry-run

# Ingest selected tables, or skip index creation
python3 src/scripts/ETL.py --tables accounts,transactions
python3 src/scripts/ETL.py --skip-indexes

# Print the latest run progress
python3 src/scripts/ETL.py --status
```

Progress is stored in the local `_etl_progress` table (one row per shard) and
`_etl_runs` (one row per run). The notebook's `print_ingestion_status()` reads
the same tables.

See [outputs/eval_columns.md](outputs/eval_columns.md) for the H2/H4/H6 column
contract and the columns that are intentionally dropped from the analysis view.
## Checklists
**Note**: This is just draft. For the whole flow breakdown, look at [flow.md](docs/flow.md)
### Main:
- [Done] Loading:Implement the file ingestion with command line options.
- [ ] Processing: Implement EDA with report of insights and main decision to `outputs/`
- [ ] Aggregate data for missing columns.
- [ ] Data visualization: Implement Q-Q plot with Sharpio-Wiki Test for non normalized value to assume normal distribution for all rules when $n$ grows.
- [ ] Implement the t-test for Hypothesis testing on $H_0$ of each distribution.
- [ ] Formalize the rules based pattern and Hypothesis testing.
- [ ] Implement Evaluation on the rule formalization.

### Optional:
- [ ] Implement the visualization for main insights.

## Questions
- Should the study on assumption of normal distribution be further studied for if pattern in real-life doesn't represent normal distribution then we also study the Box Cox transformation?

## LICENSE
The Repository is under the MIT LICENSE.

## Author: Layhok Leng
