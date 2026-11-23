# Sampling evaluation

- **Status:** done
- **Blocked by:** `06_online_db_refresh_profile.md`
- **Blocks:** Step 4 assumptions, Step 8 limitations
- **Owner:** subagent
- **Output:** sampling note
- **Updated:** 2026-11-20

## Objective

Assess how the data was collected and sampled. State whether the sampling supports the proposed groups and tests.

## Resources / context

- `docs/context/statistical_info.md`
- `src/scripts/ETL.py` — ingestion, loader, and source-link behavior
- `docs/hypothesis.md` — H2/H4/H6 definitions and thresholds

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| create | `docs/context/sampling_evaluation.md` | sampling frame and selection risks |
| update | `docs/context/statistical_info.md` | sampling verdict |

## Implementation points

- Describe collection frame, time range, and inclusion rules.
- State whether the sample supports 3-group tests.
- Feed limitations into Step 8.

## Done when

- Sampling frame and coverage are described.
- Selection risks are listed.
- Limitations feed Step 8.
