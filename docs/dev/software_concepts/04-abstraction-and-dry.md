# Abstraction and DRY

- **Status:** Accepted 
- **Parent:** [`README.md`](README.md)
- **Use when:** tempted to extract a shared helper, base class, or framework.

## Scenario

*(Pre-implementation guardrail — `src/scripts/hypothesis_testing/{h2,h4,h6,shared}` do not have runner scripts yet.)* H2 and H6 runners will both load a cohort, filter eligibility, call an omnibus test, and write a result. Extracting a `BaseHypothesisRunner` now feels DRY. Six weeks later H4 needs a pass-rate path with no omnibus, H2 needs a joint pass-rate, and H6 needs an inverted-direction warning. The base class grows flags and branches; the abstraction is now harder than the duplication.

Contrast the cohort priority rule: it is the **same knowledge** in every arm. If it appears twice, extract it once.

## Code

```python
# Wrong abstraction: two estimators forced into one shape too early.
class BaseRunner:
    def run(self, use_omnibus=True, use_pass_rate=False, invert=False): ...

# Better: small shared pieces, separate runners.
def load_eligible_cohort(path: Path, response: str) -> pd.DataFrame: ...
def run_welch(df: pd.DataFrame, response: str) -> OmnibusResult: ...
def run_pass_rate(df: pd.DataFrame, rule: str) -> PassRateResult: ...

# Each hypothesis composes only what it needs.
```

## Rules

1. **Acid test:** if one facet of the code changes and you must edit it in two formats or two places, it is one rule; if two things merely look alike, they are two rules.
2. Extract a shared module when the **knowledge** is the same, not when the syntax looks similar.
3. Prefer duplication while the rule is still being discovered. Re-extract when it stabilises.
4. One rule, one place: cohort priority, feature formulas, n-flow arithmetic.
5. Do not build a `utils.py` dumping ground.
6. Do not build a generic plugin system for metrics or transforms.
7. Do not apply SOLID by rule. Use dependency inversion only at a real seam (database vs Parquet/CSV).
8. Full onion/hexagonal layouts are overkill for this repo.
9. When an abstraction needs a parameter to disable a branch for one caller, it is probably wrong. Inline it, delete the unused branches, and re-extract only the stable knowledge.

## Debate

- Is the H2/H6 shared runner already stable, or still diverging?
-> Still diverging (and not yet written). Keep H2, H4, and H6 as separate, simple runners first and only extract into `shared/` after real overlap stabilizes.
- Which duplicated block is knowledge (extract) and which is coincidence (leave)?
-> Decide case-by-case based on context using the Change Acid Test (ask the user for context when a real duplication occurs): extract only when both places encode the same rule/knowledge that must change together (e.g., cohort priority, feature formulas, n-flow); leave coincidental lookalikes separate.
- Would a `BaseRunner` save more than it costs in conditional paths?
-> No `BaseRunner` inheritance for 3 hypotheses. Use small composable functions in `shared/`, with the hard limit of no caller-specific boolean flags to disable branches.
