# Artifact manifest

- **Status:** todo
- **Blocked by:** —
- **Blocks:** Step 8
- **Owner:** subagent
- **Output:** outputs list
- **Updated:** 2026-11-20

## Objective

List scripts, tables, figures, cohort exports, and docs produced by the analysis, with paths and status.

## Resources / context

- `outputs/` tree
- `tasks/` tracker
- `docs/context/final_report.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `docs/context/artifact_manifest.md` | artifact paths and status |

## Implementation points

- List scripts, tables, figures, cohort exports.
- Mark missing or stale artifacts.
- Keep paths repo-relative.

## Done when

- Every artifact has a path.
- Missing artifacts are flagged.
