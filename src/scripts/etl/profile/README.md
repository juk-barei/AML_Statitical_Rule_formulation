# `etl/profile` — data-engineering profiling

Read-only profiling of the source and local databases: schema, row counts,
column types, relations, quality checks, and wallet overlap. It answers
"what do we have, and does it match?" — not "what does the data mean?".

No writes: profiling only runs `SELECT` and writes CSV files. It never creates,
alters, or inserts into the mirror.

## Scripts

| Script | Purpose | Output |
| --- | --- | --- |
| `profile_databases.py` | online schema/column/relation/row profile | `db_overview.csv`, `columns.csv`, `relations.csv` |
| `profile_overlap.py` | online illicit/licit overlap and cohort counts | `group_overlap.csv`, `cohort_counts.csv` |
| `profile_local.py` | local schema/column/relation profile; quick mode samples large tables | `local_<schema>_{db_overview,columns,relations}.csv` |
| `profile_quality.py` | duplicates, nulls, orphans, amounts, timestamps, token/contract, hops | `local_quality.csv` |
| `profile_overlap_local.py` | local cohort counts, overlap, n-flow, hop/seed multiplicity | `local_{cohort_counts,group_overlap,nflow,hop_seed}.csv` |
| `run_profile.py` | run `local`, `quality`, and `overlap` together | all of the above |
| `schema.py` | `DatasetRef`, `ProfileRecord`, `StageManifest`, `ComparisonRecord` | — |
| `adapters.py` | read-only `PostgresDataset`, partial-run detection | — |
| `metrics.py` | small SQL aggregate helpers | — |

## Run order

```bash
python -m src.scripts.etl.profile.run_profile --parts local,quality,overlap \
  --schemas illicit,licit --mode quick --snapshot-id 2026-11-22T16:30:00Z
```

Standalone:

```bash
python -m src.scripts.etl.profile.profile_local --schemas illicit,licit
python -m src.scripts.etl.profile.profile_quality --schemas illicit,licit
python -m src.scripts.etl.profile.profile_overlap_local
```

Use a fixed `--snapshot-id` when the outputs must be compared. `is_partial` is
recorded from the latest `_etl_progress` run, so a partial licit ingestion cannot
look complete.

Variables come from `src/.env.example`; never read or print `src/.env`.

## Output and consumption

All scripts write to `outputs/etl/profile/` (`PROFILING_OUTPUT_DIR`). EDA and the
cohort builder consume these CSVs; record the snapshot and denominator beside any
chart or claim. A chart built from a stale profile must say so.
