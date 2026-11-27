# Local profile foundation — F, A, B

- **Status:** done
- **Blocked by:** —
- **Blocks:** cohort builder, licit EDA, feature profile
- **Owner:** lead + subagents
- **Output:** local profile/quality/overlap/pretransform CSVs + reusable profile contracts
- **Updated:** 2026-11-27

## Objective

Add a read-only local profile suite before the cohort/feature builders: shared
contracts, local schema/quality, and local cohort/overlap/n-flow. Do not change
`ingest.py` until the user has run ingestion.

## Resources / context

- `docs/dev/software_concepts/02-layers-and-boundaries.md` (accepted)
- `docs/dev/software_concepts/05-naming-and-comments.md` (accepted)
- `docs/dev/software_concepts/07-performance-and-observability.md` (accepted)
- `docs/dev/software_concepts/10-sql-rules.md` (accepted)
- `docs/dev/software_concepts/06-testing.md` (proposed; used as reference)
- `docs/dev/software_concepts/03-profiling-and-comparison.md` (proposed)

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `src/scripts/etl/transform/profile/schema.py` | `DatasetRef`, `ProfileRecord`, `StageManifest`, `ComparisonRecord` |
| create | `src/scripts/etl/transform/profile/adapters.py` | read-only `PostgresDataset`, partial-run detection |
| create | `src/scripts/etl/transform/profile/metrics.py` | aggregate helpers |
| create | `src/scripts/etl/transform/profile/profile_local.py` | local schema/column/relation profile |
| create | `src/scripts/etl/transform/profile/profile_quality.py` | local quality checks |
| create | `src/scripts/etl/transform/profile/profile_overlap_local.py` | local cohort/overlap/n-flow |
| create | `src/scripts/etl/transform/profile/run_profile.py` | local/quality/overlap orchestrator |
| create | `src/scripts/etl/transform/profile/tests/test_profile_core.py` | contract + n-flow checks |
| create | `outputs/etl/transform/profile/local_*.csv` | snapshot-tagged outputs |

## Implementation points

- **F (done):** shared contracts, Postgres adapter, metric helpers, orchestrator.
- **A (done):** local profile in quick/full modes; `is_partial` from `_etl_progress`.
- **B (done):** local cohort priority, overlap, n-flow, hop/seed multiplicity; assert partition.
- **No `ingest.py` changes.** Ingestion remains the user's run tomorrow.
- **Still pending:** feature profile (C), benchmark (D), local-vs-online comparison (E).

## Snapshot

All current outputs use `2026-11-22T16:30:00Z`. `is_partial=True` for licit because
transactions are 54.6% complete.

## Done when

- `run_profile --parts local,quality,overlap` and `--parts pretransform` complete.
- Core and pretransform checks pass; zero negative nulls.
- `local_cohort_counts`, `group_overlap`, `nflow`, `hop_seed`, `pretransform_cleaning`, and `sampling_frame` are snapshot-tagged.
- No mirror writes and no `extract/main.py` edits.