# SQL rules

- **Status:** accepted 
- **Parent:** [`README.md`](README.md)
- **Use when:** writing a transform, a cohort query, a feature query, or a data-quality check.

## Scenario

A cohort query asks "which wallets are not blacklisted?" with:

```sql
SELECT address FROM accounts
WHERE address NOT IN (SELECT wallet_address FROM blacklisted_wallets);
```

If `blacklisted_wallets.wallet_address` contains a NULL, the result can be empty even when there are non-blacklisted wallets. A second query joins `wallet_hops` to `accounts` to test hop presence; because a wallet has several hop rows, the join multiplies wallets and the `COUNT(*)` n-flow is wrong.

## Code

```sql
-- Anti-join: NULL-safe, no fan-out.
SELECT accounts.address
FROM accounts
WHERE NOT EXISTS (
    SELECT 1
    FROM blacklisted_wallets bl
    WHERE bl.wallet_address = accounts.address
);

-- Presence without fan-out; aggregate when the hop value is needed.
WITH wallet_hop AS (
    SELECT wallet_address, MIN(hop_level) AS min_hop
    FROM wallet_hops
    GROUP BY wallet_address
)
SELECT accounts.address, hop.min_hop
FROM accounts
LEFT JOIN wallet_hop hop ON hop.wallet_address = accounts.address;

-- NULL-safe comparison.
SELECT *
FROM cohort_wallet
WHERE wallet_class IS DISTINCT FROM previous_wallet_class;
```

## Rules

1. **Ban `NOT IN` in transform SQL; always use `NOT EXISTS`** so nullable columns can never silently empty a result set. (S31)
2. **Use `EXISTS` for presence, aggregate before joining for values.** Never join a multi-row hop table just to ask whether a wallet appears.
3. **Use `IS DISTINCT FROM`** for NULL-safe comparison.
4. **Put constraints on owned tables, not the mirror.** `CHECK`/`NOT NULL`/`UNIQUE`/`FOREIGN KEY` belong to exports and serving; PostgreSQL does not implement `CREATE ASSERTION`. (S32)
5. **Use `FILTER` and `GROUPING()`** when producing multiple arm counts or grouping sets; a "not grouped" NULL is not a real NULL.
6. **Use explicit `ROWS` frames** for per-wallet running totals; the default `RANGE` frame treats tied timestamps as peers.
7. **List every non-aggregated column** in `GROUP BY`; the mirror has no primary keys, so functional-dependency inference will not fire.
8. **Do not use `CASE` as a divide-by-zero guard** around an aggregate; aggregates are computed before `CASE`.
9. **Reject `NATURAL JOIN`.** A new same-named column silently changes the join.
10. **Do not use `DISTINCT ON` without `ORDER BY`.** Prefer `row_number() = 1` in a CTE when the rule must be testable.
11. **State `count(*)` vs `count(column)`.** Aggregates ignore NULL; the denominator changes.
12. **Test the nullable anti-join and the fan-out case** on a tiny fixture.

## Debate

- Should `NOT IN` be banned outright in transform SQL, or allowed with an explicit `IS NOT NULL`?
-> banned outright to prevent inaccuracy for complex join and situation of each column.
- Is the mirror's lack of constraints acceptable, or should the export writer enforce them earlier?
-> I think it is acceptable for now, we are not building the best version in one phase.
- Do we need a SQL lint for `NATURAL JOIN`/`NOT IN`, or are fixture tests enough?
-> Just fixture tests are enough. try to put some loose for now.
- Should `10-sql-rules.md` merge into `02-layers-and-boundaries.md` later?
-> Keep `10-sql-rules.md` separate: `02` covers layer architecture while `10` is a focused SQL syntax/semantics reference with almost zero duplication, matching `README.md`'s short, topic-scoped design.
