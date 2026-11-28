# `eda/profile` — stage-aware profile visualization
<!-- Last updated: 2026-11-28 | Edit count: 2 -->

Generates diagnostic figures and companion summary tables for data profiling across
`raw`, `transformed`, and `compare` (`raw → transformed`) stages.

Inputs come exclusively from the compact pre-aggregated ETL profile CSVs under
`outputs/etl/transform/profile/{raw,transformed}/`; no function queries or loads
raw `accounts`, `transactions`, or `wallet_hops` tables into pandas.

## Commands

```bash
# Baseline raw profile plots (Plots 01–11)
python -m src.scripts.eda.profile.main --stage raw

# Post-transform profile plots (Plots 01–11; uses transform_* overview/columns + post-L1 cleaning/cohort CSVs)
python -m src.scripts.eda.profile.main --stage transformed

# Subset of plot groups (schema, cohort, features)
python -m src.scripts.eda.profile.main --stage raw --groups schema,cohort

# Raw vs. transformed shift audit (Plot 12; refuses mixed snapshot phases)
python -m src.scripts.eda.profile.main --stage compare
```

## Outputs

Every run writes paired `.png` + `.csv` artifacts plus a `manifest.json` under:

- `outputs/eda/profile/raw/`
- `outputs/eda/profile/transformed/`
- `outputs/eda/profile/compare/`

Every figure stamps `stage`, `snapshot_at`, exact denominator, and `is_partial` in
its footer. Notebooks in `src/notebooks/` import any `plot_*` function directly to
display the same figure inline without duplicating plotting code.

## Modules

| Module | Role |
| --- | --- |
| `io.py` | Stage-aware CSV bundle loader (`ProfileBundle`), output routing, snapshot compatibility gate |
| `style.py` | Palette constants, matplotlib theme, figure stamping, paired PNG+CSV writer |
| `plots_schema_quality.py` | Plots 01–04: table coverage, column missingness/dtypes, quality & L1 anomalies, annual tx volume |
| `plots_cohort_frame.py` | Plots 05–07: cohort composition & n-flow, cross-schema overlap, hop nesting & seed clusters |
| `plots_features.py` | Plots 08–11: H1–H6 eligibility heatmap, zero/tail/skew diagnostics, quantile ranges, histograms |
| `plots_compare.py` | Plot 12: raw vs. transformed eligibility, median shift, and cleaning reduction |
| `main.py` | CLI runner and manifest writer |

## Design notes

- Color harmony, CVD safety, and per-plot visual encoding:
  [`docs/dev/eda/profile/color-theory-and-visual-encoding.md`](../../../../../docs/dev/eda/profile/color-theory-and-visual-encoding.md)
- Stage-routing mechanism and snapshot guard:
  [`docs/dev/eda/profile/stage-aware-profile-plots.md`](../../../../../docs/dev/eda/profile/stage-aware-profile-plots.md)

## Tests

```bash
python -m unittest src.scripts.eda.profile.tests.test_eda_profile
```
