# Stage-Aware EDA Profile Plotting Mechanism
<!-- Last updated: 2026-11-27 | Edit count: 1 -->

Explains how `src/scripts/eda/profile/` renders reproducible profiling figures
across `raw`, `transformed`, and `compare` stages without reading raw mirror
tables into memory.

## Scenario: why EDA profile plots consume ETL CSVs, not raw tables

Scanning `15.0M` illicit transactions and `11.3M` licit transactions inside a
plotting script couples visual iteration to multi-minute SQL/Parquet scans and
risks accidental pandas OOMs. Worse, if raw and transformed plots compute their
own ad-hoc aggregations, a chart can silently drift from the frozen ETL
denominators reported in `outputs/etl/transform/profile/`.

Instead, `etl/transform/profile` computes full-frame aggregates once per stage
and writes compact CSVs (`<100 KB` each). `eda/profile` treats those CSVs as
its sole read-only input.

## Data path & stage routing

```text
outputs/etl/transform/profile/
  ├── raw/*.csv          ──┐
  └── transformed/*.csv  ──┴─▶ ProfileBundle (io.py)
                                 ├─▶ --stage raw         ─▶ outputs/eda/profile/raw/{01..11}.{png,csv} + manifest.json
                                 ├─▶ --stage transformed ─▶ outputs/eda/profile/transformed/{01..11}.{png,csv} + manifest.json
                                 └─▶ --stage compare     ─▶ outputs/eda/profile/compare/12_*.{png,csv} + manifest.json
```

### Graceful degradation on `transformed`

The `raw` stage contains both PostgreSQL mirror audits (`local_illicit_db_overview.csv`,
`local_quality.csv`, `local_nflow.csv`) and DuckDB Parquet stage profiles
(`local_wallet_distributions.csv`, `local_wallet_histograms.csv`,
`local_sampling_frame.csv`, `local_pretransform_cleaning.csv`). When
`profile_stage.py --stage transformed` runs over frozen transformed Parquet
snapshots, mirror-only CSVs may not exist.

`ProfileBundle` tracks `loaded_tables` and `missing_tables`. Each plot spec in
`main.py` checks `_can_run_plot(bundle, ...)` before rendering:
- Available plots render normally and record their artifact in `manifest.json`.
- Unavailable mirror-only plots are recorded under `manifest.json["skipped"]`
  with the missing table keys instead of aborting the stage run.

### Mixed-snapshot refusal in `compare` mode

Per [`docs/dev/software_concepts/03-profiling-and-comparison.md`](../../software_concepts/03-profiling-and-comparison.md),
`validate_compare_compatibility()` refuses to render Plot 12 if `raw` and
`transformed` come from incompatible snapshot phases (for example, `phase1_raw_*`
vs `phase2_transformed_*`). Passing `--allow-cross-snapshot` overrides the gate
only when an explicit cross-phase diagnostic is requested.

### Shared engine between CLI and Jupyter notebooks

Every plotting function has the signature:

```python
plot_*(bundle, *, out_path: Path | None = None, verbose: bool = True) -> tuple[Figure, Axes | np.ndarray, pd.DataFrame]
```

- **Headless CLI** (`python -m src.scripts.eda.profile.main --stage raw`): saves
  each figure PNG alongside its exact supporting CSV (`05_cohort_composition_nflow.png`
  + `.csv`) and closes the figure to keep RSS flat.
- **Notebooks** (`src/notebooks/`): call the same function with `out_path=None`
  to display inline alongside prose without duplicating plotting code.

## Limits

- Plots 08–11 reflect the exact bin edges and quantiles emitted by
  `profile_stage.py`. Custom bin widths or bivariate scatterplots belong in
  `src/scripts/eda/{univariate,bivariate}/`, not `eda/profile/`.
- `local_illicit_db_overview.csv` carries `TABLESAMPLE` estimates for null cell
  counts on large tables; Plot 02 therefore relies exclusively on exact Parquet
  column scans (`local_{illicit,licit}_columns.csv`).

## Verification

```bash
python -m unittest src.scripts.eda.profile.tests.test_eda_profile
python -m src.scripts.eda.profile.main --stage raw
```
