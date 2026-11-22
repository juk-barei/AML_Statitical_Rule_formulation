# `etl/profile` — data-engineering profiling

Read-only profiling of the source and local databases from a **data-engineering** point of view: schema, row counts, column types, relations, and wallet overlap. It answers "what do we have, and does it match?" — not "what does the data mean?". Analytical storytelling on these numbers belongs to [`../../eda/`](../../eda/README.md).

No writes: profiling only runs `SELECT` and writes CSV files. It never creates, alters, or inserts into the mirror.

## Scripts

| Script | Purpose | Output |
| --- | --- | --- |
| `profile_databases.py` | Schema, column, relation, and row profile of the illicit + licit databases | `outputs/etl/profile/{db_overview,columns,relations}.csv` |
| `profile_overlap.py` | Wallet overlap between the illicit and licit databases, per cohort group | `outputs/etl/profile/{group_overlap,cohort_counts,local_cohort_check}.csv` |

```bash
python -m src.scripts.etl.profile.profile_databases
python -m src.scripts.etl.profile.profile_overlap
python -m src.scripts.etl.profile.profile_databases --output-dir outputs/etl/profile
```

Variables come from `src/.env.example`; never read or print `src/.env`.

## Output and consumption

Both scripts write to `outputs/etl/profile/` (from `PROFILING_OUTPUT_DIR` in `src/scripts/config.py`).

EDA consumes these CSVs directly: charts in `outputs/eda/profile/` and the univariate/bivariate sections are built from them, so record the snapshot when the profile is regenerated. A chart built from a stale profile must say so.
