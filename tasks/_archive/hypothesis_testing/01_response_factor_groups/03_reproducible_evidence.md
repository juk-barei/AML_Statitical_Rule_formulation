# Reproducible evidence script

- **Status:** done
- **Blocked by:** —
- **Blocks:** all numeric tasks
- **Owner:** subagent
- **Output:** `scripts/` + cited line numbers
- **Updated:** 2026-11-20

## Objective

Write the logic used to produce the profile and group counts. Every number used later must be reproducible from this script.

## Resources / context

- `scripts/profile_databases.py`
- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `AGENTS.md` — data authority, cohort priority, task rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `scripts/profile_databases.py` | table/column profiling logic |
| update | `scripts/profile_overlap.py` | cross-database overlap logic |
| update | `docs/context/statistical_info.md` | reported counts and script citations |

## Implementation points

- Deterministic output; no hard-coded counts.
- Every reported number maps to a script path + line.
- `profile_databases.py` and `profile_overlap.py` reproduce the stored CSV outputs.

## Done when

- Script runs from the documented env contract.
- Every reported number maps to a script path + line.
- No hard-coded counts.
