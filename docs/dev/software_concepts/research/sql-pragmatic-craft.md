# SQL for Smarties, The Pragmatic Programmer, and the missing external book

## Executive summary

**SQL for Smarties** is useful here for a narrow set of SQL habits: think in sets, use `NOT EXISTS` for nullable anti-joins, use `EXISTS` when a join would fan out, treat constraints as a boundary decision, and let the database compose the rule. It is not a guide for the mirror schema: the book predates SQL:2023, its `CREATE ASSERTION` advice has no PostgreSQL implementation, and its OLTP puzzle examples mostly do not transfer to wallet-level analytics. (S1, S2, S5, S11)

**The Pragmatic Programmer** is mostly already covered by the concept files: DRY as knowledge, orthogonality, tracer bullets, small steps, testing, naming, and documentation. The real gaps are small: a contract/assertion rule, a quarantine rule for known-broken state, a prototype/spike rule, the DRY acid test, and a boundary for "good enough." The career/team/agile chapters do not belong in this repo. (S13, S14, S17, S18, S19)

**The added external book cannot be identified.** `docs/external_resources/` contains only the five lecture PDFs. No book file exists anywhere in the `capstone-1` tree. The audit is blocked pending the book's title and path. (S22)

## 1. SQL for Smarties: what transfers

### 1.1 Set-based thinking is already policy

Celko's core claim is to give up row-at-a-time thinking and let SQL process sets. (S3) The repo already says "PostgreSQL computes; pandas displays" and forbids full-table pandas reads. The book adds the reason: row-at-a-time code moves the rule into a language the query planner cannot reorder or push down. That matters because the transform layer is still empty; every cohort and feature query is still unwritten. (S21)

### 1.2 NULL and anti-join rules

The most concrete transfer is the `NOT IN` trap. With a nullable right-hand side, `x NOT IN (1, 2, NULL)` can evaluate to UNKNOWN, not TRUE. PostgreSQL's manual warns about exactly this. (S4, S6) Libkin and Peterfreund show the classic `NOT IN` ↔ `NOT EXISTS` rewrite is not valid when NULLs are present. (S7)

Repo rule:

```sql
-- Correct anti-join against a nullable column
SELECT a.address
FROM accounts a
WHERE NOT EXISTS (
    SELECT 1
    FROM blacklisted_wallets b
    WHERE b.wallet_address = a.address
);
```

If `NOT IN` is used, add `WHERE col IS NOT NULL` and test it. For NULL-safe equality, use `IS DISTINCT FROM`, which returns TRUE/FALSE and never UNKNOWN. (S6) Celko's 2024 article adds the DDL/DML asymmetry: a `CHECK` passes on UNKNOWN, while a `WHERE` keeps only TRUE. (S4)

### 1.3 EXISTS vs JOIN

`wallet_hops` has multiple rows per wallet. Joining it just to ask "does this wallet appear at hop 1–5?" multiplies rows and corrupts `COUNT(*)`-based n-flow. `EXISTS` answers presence without fan-out; when the hop value is needed, aggregate first:

```sql
WITH wallet_hop AS (
    SELECT wallet_address, MIN(hop_level) AS min_hop
    FROM wallet_hops
    GROUP BY wallet_address
)
SELECT ...
FROM accounts a
LEFT JOIN wallet_hop h ON h.wallet_address = a.address;
```

This matches the cohort contract: `suspicious = min(hop_level) ∈ 1..5` and not blacklisted. (S21) Brass & Goldberg classify uncorrelated `EXISTS` subqueries as semantic errors — a missing join condition — which is a cheap SQL fixture test. (S12)

### 1.4 Constraints belong at the export/serving boundary

Celko is right that constraints are a data-integrity tool. Two corrections for this repo:

1. The mirror is deliberately unconstrained: `ingest.py` creates tables from compiled types with no keys or checks. That is correct for a fidelity mirror; adding constraints the source does not guarantee would abort loads. (S21)
2. `CREATE ASSERTION` is not implemented by PostgreSQL; it is on the unsupported-features list. (S11) Use `CHECK`/`NOT NULL`/`UNIQUE`/`FOREIGN KEY` on the tables the repo owns (exports, serving), or scheduled assertion tests.

Also audit the silent `TEXT` fallback in `source_type_to_local_sql`; a numeric column that falls through changes sort, `SUM`, and comparison semantics without an error. (S21)

### 1.5 Composition rules worth adopting

- Use `FILTER (WHERE ...)` for multiple arm counts in one scan.
- Use `GROUPING()` with `GROUPING SETS`/`ROLLUP`; otherwise a "not grouped" NULL is indistinguishable from a real NULL. (S23)
- Use explicit `ROWS` frames for per-wallet running totals; the default `RANGE` frame treats peers alike, and tied timestamps are common. (S10)
- List every non-aggregated column in `GROUP BY`; the mirror has no primary keys, so PostgreSQL cannot infer functional dependency. (S9)
- Do not use `CASE` as a divide-by-zero guard around an aggregate; aggregates are computed before `CASE`. (S24)
- Reject `NATURAL JOIN`; a new same-named column silently changes the join. (S23)
- `DISTINCT ON` is a PostgreSQL extension and is unpredictable without `ORDER BY`; prefer `row_number() = 1` in a CTE when the rule must be testable. (S8)

### 1.6 What to reject

- `CREATE ASSERTION` as a PostgreSQL design (S11).
- The portability goal: this repo runs PostgreSQL for analysis and serving; portability matters only at the export boundary. (S1)
- OLTP puzzles (auctions, inventory, relational division) as templates for wallet features. (S1)
- The assumption that "set-based is faster" is universal; the defensible claim is planner visibility, not a measured speed-up.

## 2. The Pragmatic Programmer: what is already covered

The 2019 edition is a rewrite, not a reprint; the authors say "roughly one-third of the topics are brand new." (S15) The 1999 edition is a different text, not a page-for-page predecessor. (S16) The 2019 DRY chapter explicitly corrects the first edition's code-only reading. (S14)

The publisher's 100 tips and the two 2019 sample chapters are the primary text used here. (S13, S14, S15) Already covered by the concept files:

- DRY as knowledge, not text — `04-abstraction-and-dry.md`.
- Orthogonality and one-way dependencies — `02-layers-and-boundaries.md`.
- Tracer bullets — `08-migration-checklist.md`.
- Testing, refactoring, small steps — `06-testing.md`, `08`.
- Naming, comments, docs — `05-naming-and-comments.md`.
- Reproducible runs and manifests — `07-performance-and-observability.md`.

Do not add a "Pragmatic Programmer" concept file; it would duplicate four existing files. (S21) A shared H2/H4/H6 base runner would also be the wrong abstraction: duplication is cheaper than the wrong abstraction until the shape stabilises. (S20)

### 2.1 Real gaps worth one line each

| Gap | Rule | Where |
| --- | --- | --- |
| DRY acid test | "If one facet changes and you must edit it in two formats/places, it is one rule; if two things merely look alike, it is two rules." | `04` |
| Contracts/assertions | Validate inputs at trust boundaries with `raise`, not bare `assert` (`-O` strips it); assert only programmer invariants; one manifest schema per layer. | `06` or new `10` |
| Quarantine | If a known-broken state cannot be fixed now, label it (`is_partial`, red shard, blocked export) so nobody can quote it as clean. | `07` |
| Prototype/spike | A spike answers one question, is time-boxed, lives outside `src/`, and is deleted; if it survives, it is a tracer bullet and needs tests. | `07` |
| Good-enough boundary | Good-enough applies to tooling and exploratory scope; it never applies to denominators, eligibility, cohort priority, or the frozen snapshot. | `03` or `08` |
| Per-commit tests | Run the small/medium suite on every commit; the repo currently has no CI trigger. | `08` |
| Programming by coincidence | A test that passes for an unknown reason is a coincidence, not a pass. | `06` |

### 2.2 What to reject or limit

- Career, team, requirements, and agile chapters: out of scope for a one-maintainer data repo.
- "Fix it right then and there" when the source is timing out: use the police-tape half — label and block the export, do not fake completeness.
- "Good enough" as a justification for a 54.6%-complete licit arm. The boundary sentence must travel with the rule.
- Anecdotal prescriptions as technical evidence. Use the book for diagnostics and vocabulary, not as proof.

## 3. The external book: blocked

`docs/external_resources/` contains exactly:

- Lecture 01 — Descriptive Statistics
- Lecture 02 — Exploratory Data Analysis
- Lecture 03 — Probability Distributions
- Lecture 04 — Hypothesis Testing
- Lecture 05 — ANOVA

A tree-wide scan found no `.epub`, `.djvu`, `.mobi`, `.azw`, or archive book. The only file under `resources/books/` is a 902-byte, 9-line blockchain note, not a book. `paper4.pdf` and `paper5.pdf` are byte-identical; `paper_2_investigation_of_illicit_tron_wallet.md` is 1 byte. (S22)

**Blocked — title/path needed.** Re-add the book to `docs/external_resources/` or provide its filename, title, author, and edition. Until then, no claim about its relevance is possible.

## 4. Proposed minimal changes

All are edits to `proposed` concept files; none changes a status. User approval still required.

1. `04-abstraction-and-dry.md`: add the DRY acid test. (S14)
2. `06-testing.md`: add a Contracts block (raise vs assert, `-O`, manifest schema) and the "unknown reason" done-criterion. (S13)
3. `07-performance-and-observability.md`: add quarantine and spike rules. (S18, S17)
4. `03-profiling-and-comparison.md` or `08`: add the good-enough boundary. (S19)
5. `08-migration-checklist.md`: state that the steps are tracer bullets and add per-commit tests. (S17, S13)
6. `09-references.md`: add Hunt & Thomas 2019, Celko 5th ed., PostgreSQL 17 docs, Libkin & Peterfreund. (S1, S5, S7, S13)

Do not add a separate Pragmatic Programmer file. The SQL rules belong in the transform SQL header/tests, not a new concept file.

## 5. Open questions

- Is the external book one of the five lecture PDFs under a different name, or truly absent?
- Do we want a separate `10-contracts-and-assertions.md`, or a six-line block in `06-testing.md`?
- Should `NOT IN` be banned outright in transform SQL, or allowed only with an explicit `IS NOT NULL` and a test?
- Is the server PostgreSQL major version 17? The client is 17.12, but the server version was not captured during the audit.
- Do we add `10-contracts-and-assertions.md` now, or wait until the cohort/feature builders reveal the invariants?

## Sources

| ID | Source | URL |
| --- | --- | --- |
| S1 | Celko, *SQL for Smarties*, 5th ed. (Elsevier) | https://shop.elsevier.com/books/joe-celkos-sql-for-smarties/celko/978-0-12-800761-7 |
| S2 | Celko, *SQL for Smarties*, 4th ed. front matter/TOC | https://booksite.elsevier.com/samplechapters/9780123820228/01~Front_Matter.pdf |
| S3 | Celko, "SQL and the Snare of Three-Valued Logic" (2009) | https://www.red-gate.com/simple-talk/databases/sql-server/learn/sql-and-the-snare-of-three-valued-logic |
| S4 | Celko, "SQL Logic" (2024) | https://www.red-gate.com/simple-talk/databases/theory-and-design/sql-logic |
| S5 | PostgreSQL 17, Constraints | https://www.postgresql.org/docs/17/ddl-constraints.html |
| S6 | PostgreSQL 17, Subquery Expressions | https://www.postgresql.org/docs/17/functions-subquery.html |
| S7 | Libkin & Peterfreund, "SQL Nulls and Two-Valued Logic" | https://arxiv.org/abs/2012.13198 |
| S8 | PostgreSQL 17, SELECT | https://www.postgresql.org/docs/17/sql-select.html |
| S9 | PostgreSQL 17, WITH Queries | https://www.postgresql.org/docs/17/queries-with.html |
| S10 | PostgreSQL 17, Window Functions | https://www.postgresql.org/docs/17/tutorial-window.html |
| S11 | PostgreSQL 17, Unsupported Features | https://www.postgresql.org/docs/17/unsupported-features-sql-standard.html |
| S12 | Brass & Goldberg, "Semantic Errors in SQL Queries" | https://doi.org/10.1016/j.jss.2005.06.028 |
| S13 | PragProg, *Pragmatic Programmer Tips* | https://pragprog.com/tips/ |
| S14 | Thomas & Hunt, Topic 9: DRY (sample) | https://media.pragprog.com/titles/tpp20/dry.pdf |
| S15 | Thomas & Hunt, Preface to the Second Edition | https://media.pragprog.com/titles/tpp20/preface2.pdf |
| S16 | Hunt & Thomas, 1999 sample pages | https://ptgmedia.pearsoncmg.com/images/9780201616224/samplepages/020161622X.pdf |
| S17 | Venners, "Tracer Bullets and Prototypes" | https://www.artima.com/articles/tracer-bullets-and-prototypes |
| S18 | Venners, "Don't Live with Broken Windows" | https://www.artima.com/articles/dont-live-with-broken-windows |
| S19 | Venners, "Good Enough Software" | https://www.artima.com/articles/good-enough-software |
| S20 | Metz, "The Wrong Abstraction" | https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction |
| S21 | Repo concept files and `AGENTS.md` | local |
| S22 | External-resource audit | `outputs/.drafts/sql-pragmatic-craft-research-external.md` |
| S23 | PostgreSQL 17, Table Expressions | https://www.postgresql.org/docs/17/queries-table-expressions.html |
| S24 | PostgreSQL 17, Value Expressions | https://www.postgresql.org/docs/17/sql-expressions.html |

---

## Citation status

- **SQL for Smarties:** publisher TOCs for the 5th and 4th editions and Celko's separately published articles were read; the book body was not available in an authorised copy, so no book prose is quoted. Every SQL behaviour claim is checked against PostgreSQL 17 documentation.
- **The Pragmatic Programmer:** publisher tip card, errata, 2019 preface, the DRY and "Don't Outrun Your Headlights" samples, and 1999 front matter were read; the full 2019 text was paywalled. Claims outside the samples are limited to tip text and author interviews.
- **External book:** audit is local and read-only; no book file exists in the inspected tree. Status is BLOCKED — title/path needed.
- **Repo claims:** checked against the local concept files and `AGENTS.md`.

**Verification: PASS WITH NOTES** — citations are mapped, but the two books' full texts were not read and the external book is blocked.
