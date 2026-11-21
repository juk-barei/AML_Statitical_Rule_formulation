# Validate the three-group design

- **Status:** done
- **Blocked by:** `01_profile_illicit_licit.md`
- **Blocks:** `04_cohort_contract_v2.md`
- **Owner:** subagent
- **Output:** verdict in `docs/context/statistical_info.md`
- **Updated:** 2026-11-20

## Objective

Test whether illicit / suspicious / licit are mutually exclusive, non-overlapping, and supported by the observed sampling. Check blacklist overlap, hop overlap, and licit frame.

## Resources / context

- `docs/context/statistical_info.md` — proposed groups and profiling
- `docs/context/step_1_profiling_samples.md` — cohort/response decisions
- `docs/hypothesis.md` — H2/H4/H6 definitions and thresholds
- `scripts/profile_databases.py`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/statistical_info.md` | group verdict |
| create | `outputs/profiling/group_overlap.csv` | illicit/suspicious/licit overlap |

## Implementation points

- Check mutual exclusivity and priority at every hop.
- Check licit overlap with blacklist and hop wallets.
- State whether 3 groups fit or a fallback is required.

## Done when

- Group rule and priority are explicit.
- Overlap counts are reported.
- Recommendation is 3 groups or a documented fallback.
