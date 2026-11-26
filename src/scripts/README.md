# `src/scripts`

Analysis code, split by pipeline area. Each area's outputs mirror that area's folder under `outputs/`.

Project-wide rules — data authority, cohort contract, inference, workflow — live in [`AGENTS.md`](../../AGENTS.md). This README is only the index for the code.

Run everything as modules **from the repo root** so the `src` package is importable:

```bash
python -m src.scripts.etl.extract.main --help
```

## Areas

| Area | Code | Outputs | Details |
| --- | --- | --- | --- |
| ETL | `src/scripts/etl/` | `outputs/etl/{extract,transform,load}` (profile is inside `outputs/etl/transform/profile/`) | [`etl/README.md`](etl/README.md) |
| EDA | `src/scripts/eda/` | `outputs/eda/{univariate,bivariate,multivariate,profile,additional}` | [`eda/README.md`](eda/README.md) |
| Hypothesis testing | `src/scripts/hypothesis_testing/` | `outputs/hypothesis_testing/{shared,h2,h4,h6}` | [`hypothesis_testing/README.md`](hypothesis_testing/README.md) |
| Statistical learning | `src/scripts/statistical_learning/` | `outputs/statistical_learning/` | [`statistical_learning/README.md`](statistical_learning/README.md) |

**Output rule:** every artifact goes under the area that produced it — `src/scripts/eda/` writes only to `outputs/eda/`, `src/scripts/etl/` only to `outputs/etl/`, and so on. ETL has three stage folders that mirror its name: `outputs/etl/{extract,transform,load}`. Handoff snapshots are one directory per snapshot: `outputs/etl/load/<snapshot>/`. Do not add a top-level output folder without updating `AGENTS.md` and this table.

**Writer rule:** `src/scripts/etl/extract/main.py` is the only writer of the local PostgreSQL mirror; `src/scripts/etl/load/main.py` is the designated writer for shared exports. Notebooks in `src/notebooks/` are read-only against the mirror.

**Test rule:** tests live in a `tests/` folder inside the stage they test — `extract/tests/`, `transform/<module>/tests/`, `load/tests/`. There is no shared top-level `tests/` folder under an area.

## Shared modules

| Module | Purpose |
| --- | --- |
| `config.py` | Path constants: `ROOT`, `SRC` (`datasets/`), `OUTPUT` (`outputs/`), per-area output dirs (`ETL_OUTPUT_DIR`, `EDA_OUTPUT_DIR`, `HYPOTHESIS_TESTING_OUTPUT_DIR`, `STATISTICAL_LEARNING_OUTPUT_DIR`, `PROFILING_OUTPUT_DIR`), plus terminal/report constants. Import paths from here, never hardcode them. Stage moves are in progress; `PROFILING_OUTPUT_DIR` is still being moved under the transform stage. |
| `archive/` | Retired helpers (`loaders.py`, `processing.py`) kept for the author's later experiments. Do not import from here. |

`datasets/*.csv` is a stale, partial export; see `AGENTS.md` before using it.
