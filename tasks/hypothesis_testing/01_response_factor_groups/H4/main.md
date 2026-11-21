# H4 — TRX gas co-occurrence

- **Status:** blocked
- **Blocked by:** data support
- **Blocks:** next step / final verdict
- **Owner:** subagent
- **Output:** docs/context/hypotheses/H4.md
- **Updated:** 2026-11-20

## Objective

Apply Step 1 (response, eligibility, feature formula, and support) to H4: `jaccard_index` descriptive. Rule: Jaccard ≥ 0.50, only when both sets are non-empty.

## Resources / context

- `docs/hypothesis.md` — H4 rule
- `docs/context/step_1_profiling_samples.md` — response and cohort decisions
- `../main.md` — shared tasks for this step
- `AGENTS.md` — data authority and dependence rules

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `docs/context/hypotheses/H4.md` | response, eligibility, and support note |
| create | `outputs/profiling/H4_support.csv` | eligibility/support counts |

## Implementation points

- Jaccard only on both-set wallets.
- Only 13 illicit passes; do not call it supported.
- Report zero mass and denominator.
