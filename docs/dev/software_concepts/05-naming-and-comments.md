# Naming and comments

- **Status:** Accepted 
- **Parent:** [`README.md`](README.md)
- **Use when:** naming a variable, function, column, SQL alias, or writing a comment.

## Scenario

A function receives `df`, returns `res`, and filters on `t`. A reader cannot tell whether `t` is minutes, seconds, a threshold, or a token. A comment says `# increment counter` above `count += 1`; it repeats the code and will be stale after the next edit.

The reader should not need the comment to decode the name.

## Naming rules — exact

1. **Casing.** `snake_case` for variables, functions, modules; `PascalCase` for classes/dataclasses; `UPPER_SNAKE_CASE` for module constants.
2. **No empty names.** Ban `data`, `df`, `tmp`, `res`, `result`, `val`, `obj` as function parameters or return names. A local `df` is allowed only inside a ≤10-line scope where the table is obvious.
3. **Name the domain object.** `wallets`, `transactions`, `cohort_rows`, `wallet_facts` — not `items`.
4. **Name the unit.** Suffix `_seconds`, `_minutes`, `_days`, `_usdt`, `_trx`, `_ratio`, `_share`, `_count`. Use `holding_minutes`, `out_in_volume_ratio`, `wallet_count`.
5. **Name the stage.** Prefix raw/clean/eligible/feature/cohort when more than one stage is in scope: `clean_transactions`, `eligible_wallets`, `cohort_wallet`.
6. **Booleans read as assertions.** `is_blacklisted`, `has_both_sets`, `can_clear`, `should_include`. Never `not_blacklisted` or `flag`.
7. **Collections are plural.** `wallets`, `seed_addresses`; mappings end `_by_`: `wallets_by_group`.
8. **Identifiers match the schema.** `wallet_address`, `transaction_hash` (aliased once from raw `tx_hash` in L1 `clean`), `seed_address`, `min_hop`. Do not invent `addr` or `hop_min` in Python and map later.
9. **Factor and output column.** Use `wallet_class` everywhere — in Python, SQL, and output columns. Do not use `group` (SQL reserved word), `class` (Python reserved word), or `label`.
10. **SQL aliases follow the same rules.** `transactions`, `bl`, `hop` are acceptable aliases because they name the table; `a`, `b`, `t1`, `wf` are not.
11. **No type prefixes.** `address_str`, `df_wallets`, `dict_seed` — the type is in the annotation.
12. **No single letters** except `i`, `j` loop indices and `x`, `y` in a formula. No `d`, `t`, `r` for domain values.
13. Always has static type hinting. Type hinting should not be abstracted behind a variable name unless repeated and is complex or very nested. Balance readability, and abstraction for easy comparison of type across functions.

```python
# Bad
def calc(df, t=15):
    return df[df["holding"] < t]

# Good
def select_short_holding_wallets(
    wallets: pd.DataFrame,
    max_holding_minutes: float = 15,
) -> pd.DataFrame:
    return wallets.loc[wallets["holding_minutes"] < max_holding_minutes]
```

## Comment rules — exact

1. **Docstring every public module, class, and function.** One-line summary; args, returns, raises; units; snapshot if the result is snapshot-bound.
2. **Comments explain why, not what.** If the code says it, do not repeat it.
3. **Comment non-obvious invariants and external constraints.** Example: “blacklist wins at every hop”; “16 GB team target: stream, do not materialize.”
4. **SQL rule comments name the rule and source.** `-- S2: lifetime <= 7 days (docs/hypothesis.md)`.
5. **Thresholds state provenance.** `# 15 min is provisional; calibrate in Step 8, not here.`
6. **TODOs carry a task id.** `# TODO(task-05): replace with the frozen cohort path.` No bare `TODO`/`FIXME`.
7. **No commented-out code.** Use git history.
8. **No decorative banners or `# =====` separators.** Use functions and module docs.
9. **A stale comment is a bug.** If you change the code, change the comment in the same edit.
10. **Prefer renaming over explaining.** If a comment has to explain a name, rename the variable.
11. **Shortcut comments use the repo form.** `# shortcut: <limit>; upgrade when <condition>.`

```python
# Bad
# increment count
count += 1

# Good
# The source returns duplicate rows for multi-seed wallets; count distinct wallets.
unique_wallet_count = wallets["wallet_address"].nunique()
```

## Rename policy — open by design

Names are **provisional**. Renaming is expected when the project grows or a name becomes ambiguous.

When renaming:

1. Rename in **one change** across Python, SQL, tests, docs, and output columns.
2. Do **not** keep aliases or compatibility shims inside the repo.
3. If an external consumer exists, bump `feature_version` and record the rename in the manifest/changelog.
4. Update the data dictionary and any saved fixtures/golden files.
5. Prefer the domain term over historical abbreviations; alias raw L0 `tx_hash` to `transaction_hash` once in L1 `clean` so L2–L5 use `transaction` consistently.
6. Do not rename a published snapshot column in place; create a new version.

## Debate

- Is `wallet_class` the right factor name, or should code use `group` everywhere?
-> Use `wallet_class` everywhere — in Python, SQL, and output columns. It is more informative than `group` (which is also a SQL reserved word), and linguistically refers to the domain class of wallets rather than a Python type.
- Should `tx` be allowed, or should Python use `transaction` even when SQL uses `tx_hash`?
-> Alias `tx_hash AS transaction_hash` once in L1 `clean` so L2–L5 Python and SQL use `transaction` / `transaction_hash` consistently without mapping comments or abbreviation overhead for newcomers.
- Which current names are already misleading enough to rename before the cohort builder?
-> Rename before building the cohort builder: `group` → `wallet_class` (`profile_features.py`), `wf` → `wallet_features_subquery` / `features` (`profile_features.py`), and `ingest_*` → `extract_*` inside `src/scripts/etl/extract/`.
