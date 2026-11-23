# Local profile foundation — F, A, B

- **Status:** in_progress
- **Blocked by:** —
- **Blocks:** cohort builder, licit EDA, feature profile
- **Owner:** lead + subagents
- **Output:** local profile/quality/overlap CSVs + reusable profile contracts
- **Updated:** 2026-11-22

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
| create | `src/scripts/etl/profile/schema.py` | `DatasetRef`, `ProfileRecord`, `StageManifest`, `ComparisonRecord` |
| create | `src/scripts/etl/profile/adapters.py` | read-only `PostgresDataset`, partial-run detection |
| create | `src/scripts/etl/profile/metrics.py` | aggregate helpers |
| create | `src/scripts/etl/profile/profile_local.py` | local schema/column/relation profile |
| create | `src/scripts/etl/profile/profile_quality.py` | local quality checks |
| create | `src/scripts/etl/profile/profile_overlap_local.py` | local cohort/overlap/n-flow |
| create | `src/scripts/etl/profile/run_profile.py` | local/quality/overlap orchestrator |
| create | `src/scripts/etl/profile/tests/test_profile_core.py` | contract + n-flow checks |
| create | `outputs/etl/profile/local_*.csv` | snapshot-tagged outputs |

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

- `run_profile --parts local,quality,overlap` completes.
- Core checks pass.
- `local_cohort_counts`, `group_overlap`, `nflow`, and `hop_seed` are snapshot-tagged.
- No mirror writes and no `ingest.py` edits.
EOF

cd /home/annoy/projects/team/capstone-1/dev/data_analysis && python3 - <<'PY'
from pathlib import Path
p=Path('tasks/etl/README.md')
t=p.read_text()
t=t.replace('| [`04_web_serving.md`](04_web_serving.md) | todo | `03_export_pipeline.md` | web application | wallet-level serving table |','| [`04_web_serving.md`](04_web_serving.md) | todo | `03_export_pipeline.md` | web application | wallet-level serving table |\n| [`05_local_profiling.md`](05_local_profiling.md) | in_progress | — | cohort builder, licit EDA | local profile/quality/overlap CSVs + contracts |')
p.write_text(t)
print('updated tasks/etl/README.md')
PY