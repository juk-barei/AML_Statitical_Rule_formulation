# Software design foundations for this repo

**Scope:** how to design and implement the code in this TRON AML data-analysis repo: ETL, profiling, cohort/feature transforms, hypothesis tests, and exports. This is a design brief, not a style guide.

## Executive summary

The repo does not need a framework or a full Clean Architecture. It needs **a small number of deep modules, one-way data dependencies, explicit stage contracts, and tests for its own rules**. The useful ideas are:

1. Optimize for the next reader's information load, not line count. \[S1]\[S2]
2. Prefer deep modules with narrow interfaces; avoid both a god module and classitis. \[S2]
3. Use Clean Code selectively. Its advice on very small methods and comments is contested and not empirically settled. \[S1]\[S6]\[S7]
4. Treat DRY as "one place for one piece of knowledge", not "no similar code". A premature abstraction is more expensive than duplication. \[S9]
5. Apply SOLID only where a real seam exists. Full onion/hexagonal layouts over-engineer small repos. \[S10]\[S11]
6. Separate pure decisions (priority, formulas, n-flow, statistics) from I/O (SQL, files, env). \[S13]
7. Make before/after transformation comparison a first-class output, not a notebook afterthought. \[S16]
8. Measure before optimizing; bound every read; prefer plain scripts plus manifests over an orchestrator until a second pipeline/operator exists. \[S14]\[S16]

## 1. The actual design problem

The repo is a small, data-heavy batch system:

- two source PostgreSQL databases are mirrored into local schemas by `ingest.py`;
- profiling reads schema, counts, overlap, and features;
- transforms produce cohort and feature tables;
- hypothesis tests read those tables;
- exports freeze a snapshot for handoff. \[S27]\[S29]

It has three constraints that dominate design:

1. **Memory.** The illicit source transaction table is ~15.0M rows and the licit source table ~11.3M at the 2026-11-22 profile; the local licit mirror holds 6.18M so far. Full-table pandas reads do not fit the 8 GB target. SQL must compute; pandas displays. \[S16]\[S27]
2. **Partial data.** Licit accounts are complete, but licit transactions are only 54.6% and three shards failed on source timeout. Any design must record coverage and refuse to call a partial run frozen. \[S16]\[S30]
3. **Drift.** Local and online counts move. Every output needs a snapshot id, schema, row counts, and a partial flag. \[S16]\[S29]

The current code already has good raw material: `TableSpec`, `ShardTask`, `ShardResult`, resume/progress tables, a coverage verifier, and strong task contracts. \[S27]\[S30] The design problem is not "add architecture"; it is "stop one module from owning six responsibilities and stop each new script from re-inventing database access and output shape."

## 2. What to take from software design

### 2.1 Complexity is the criterion

Ousterhout defines complexity as what makes a system hard to understand and modify; the key cost is how much information a developer must hold in their head. \[S1] Brooks separates essential complexity (inherent in the problem) from accidental complexity (introduced by tools and representations). \[S3] Moseley and Marks argue that much accidental complexity can be removed. \[S4]

For this repo:

- Essential: sharding, resume, source drift, partial ingestion, seed-cluster dependence, heavy-tailed data.
- Accidental: duplicate engine/env code, inconsistent output schemas, copy-pasted SQL filters, full-table pandas reads, scripts that each invent their own CSV columns.

The design should remove the accidental kind first.

### 2.2 Deep modules and information hiding

A deep module hides a lot of implementation behind a simple interface; a shallow module exposes an interface nearly as complex as its functionality. Ousterhout calls the proliferation of tiny classes "classitis." \[S2] Parnas's criterion is the same idea: decompose by what each module hides, not by flowchart steps. \[S5]

This is not an argument for one giant module. `ingest.py` is 2,071 lines and owns environment loading, engine creation, planning, COPY, progress, reporting, and notebook access. Its interface exposes too much and its tests need a database. It is a **god module**, not a deep module. The target is a small set of modules that each hide a real decision:

- database/environment access;
- shard planning;
- shard copy;
- progress/reporting;
- CLI orchestration.

A 2,000-line module with six reasons to change is too shallow in the sense that matters; splitting it into ten one-function files with no shared contract is also shallow. The right split is by hidden decision.

### 2.3 Clean Code is one source, not the baseline

The Ousterhout/Martin debate is a primary record of the disagreement. Ousterhout argues that very small methods can be over-decomposed and that comments are often valuable; Martin argues for small, well-named methods and treats comments as a necessary evil. \[S1] Empirical work is mixed: a Delft dissertation found that giving developers "clean code" did not automatically produce the claimed short-term productivity gains, and a 2021 study of 31,687 Java files questioned whether code smells cause lower quality in the way the common story assumes. \[S6]\[S7]

The usable position: use Clean Code as a list of heuristics, not a rulebook. Prefer measurable properties — fewer concepts per module, stable interfaces, tests that pin behaviour — over book compliance. Do not split a coherent module just to satisfy a line-count rule.

### 2.4 DRY is about knowledge, not syntax

Sandi Metz's "wrong abstraction" pattern is the relevant warning: extract duplication, then add parameters and conditionals as callers diverge, until the shared code is harder than the duplication. Her advice is "prefer duplication over the wrong abstraction" and, when trapped, inline it again and re-extract only the stable common knowledge. \[S8]

For this repo:

- The cohort priority rule is knowledge; it must live in one place.
- Two hypothesis runners with similar boilerplate but different estimands are not necessarily the same knowledge; duplication may be cheaper than a premature shared runner.
- Two SQL blocks that look alike today may diverge when H2 token scope or H6 direction is fixed; do not abstract them until the rule is stable.

### 2.5 SOLID and hexagonal architecture are conditional

SOLID names real failure modes, but applying all of it to a small repo adds interfaces, factories, and layers that exist only to satisfy the pattern. Krämer notes that SOLID principles are principles, not rules, and become a necessity mainly at larger scale. \[S9] Rentea documents how onion/hexagonal architectures applied by the book create overengineering and slow refactoring. \[S10]

This repo has exactly one real seam: profiling/comparison must read PostgreSQL now and Parquet/CSV later. That justifies a small adapter interface, not a hexagon. It does not justify a repository class per table or a use-case object per script.

### 2.6 Simple vs easy

Hickey distinguishes **simple** (one fold, not interleaved) from **easy** (near at hand). A familiar framework can be easy and complex. \[S11] A pipeline framework may be easy to install and complex to operate; a plain script plus a manifest may be less easy and simpler. For a one-person batch repo, simple wins until a second scheduled pipeline or a second operator appears. \[S16]

### 2.7 Functional core, imperative shell

The functional-core/imperative-shell pattern puts pure decisions in a core and I/O in a thin shell. Testing the core needs no doubles; the shell has few conditionals. \[S12]

For this repo:

- Core: `cohort_priority`, feature formulas, eligibility rules, n-flow arithmetic, test statistics.
- Shell: SQL execution, file writing, environment loading, CLI.

The core must not import SQLAlchemy or read `.env`. That is what makes fast tests possible without the 15M-row mirror.

## 3. Architecture: five layers, one writer each

Use the medallion idea (raw → cleaned → business-ready) but keep the repo's own names. \[S16] Five layers are enough:

| Layer | Contents | Writer | Readers | Invariant |
|---|---|---|---|---|
| L0 raw | `illicit.*`, `licit.*` mirror tables | `ingest.py` only | L1 only | row count per table matches source at snapshot |
| L1 clean | typed, deduped, null-policy applied | transform SQL | L2 only | `clean.n <= raw.n - documented_drops` |
| L2 cohort | one row per wallet: group, hop, seed, flags | cohort builder | L3, analysis | exactly one group per wallet |
| L3 features | one row per wallet: H2/H4/H6 columns | feature builder | analysis | one row per wallet |
| L4 analysis | profile/test outputs | profiling/test runners | humans | reads only L2 + L3 + manifest |
| L5 export | frozen snapshot + manifest | `load.py` | downstream | status, counts, hashes, denominator |

The important part is not the layer names; it is the **contract at each boundary**: who writes it, what its grain is, and what may read it. `nflow.csv` and `manifest.json` are part of the contract, not reporting extras. \[S16]\[S27] The transform rules themselves are stated in `transform/README.md` \[S28].

## 4. Module boundaries for this repo

A target shape, not a demand to split everything now:

```text
src/scripts/
  config.py
  etl/
    db.py                 # env, links, engine, identifiers, read-only access
    specs.py              # TableSpec, ShardTask, ShardResult
    plan.py               # shard planning
    copy.py               # COPY/ingest shard
    progress.py           # run/progress/report
    cli.py                # argparse + orchestration
    ingest.py             # compatibility facade while migrating
    profile/
      schema.py           # DatasetRef, ProfileRecord, StageManifest
      adapters.py         # Postgres now; Parquet/CSV later
      metrics.py          # pure metric functions
      compare.py          # before/after comparison
      profile_local.py
      profile_quality.py
      profile_overlap_local.py
      profile_features.py
      benchmark.py
      run_profile.py
    transform/
      cohort_wallet.sql
      features_h2_h4_h6.sql
      build_cohort.py
      build_features.py
  eda/
    plots.py              # reusable plot functions, no full-table loads
  hypothesis_testing/
    shared/               # load_cohort, nflow, assumptions, omnibus, posthoc, effect_size
    h2/ h4/ h6/
```

Migration order:

1. Extract `db.py` (environment, links, engine, `quote_identifier`, `qualified_name`). This removes the profile→ingest coupling without touching the ingest algorithm.
2. Keep `ingest.py` as the public facade; move planning/copy/progress only when tests need them.
3. Add `profile/schema.py` and the Postgres adapter; do not add a Parquet adapter until DuckDB/pyarrow is installed.
4. Add stage manifests to transforms.
5. Add the comparison engine.
6. Add hypothesis helpers last, after the cohort/feature contracts are stable.

Do not split `ingest.py` into ten files just to satisfy a diagram. Extract a module when it hides a decision and removes a real dependency.

## 5. Profiling and before/after comparison

Profiling should answer four questions:

1. What is in the mirror now? rows, columns, nulls, cardinality, time range, table/index size.
2. Is it internally consistent? duplicates, orphan keys, bad timestamps, non-positive amounts, token/contract mismatches, hop ranges.
3. Who is in which cohort? local illicit/suspicious/licit/unlabeled counts, overlap, hop and seed distribution, n-flow.
4. How expensive is each operation? row counts, bytes, index use, `EXPLAIN ANALYZE`, rows/sec, memory estimates.

The before/after comparison is a first-class output, not a notebook afterthought. Compare five stages:

```text
raw → cleaned → eligible → feature-level → cohort/analysis
```

For each stage, compare:

- row flow and retention per group/filter;
- group movement (raw label vs final group crosstab);
- missingness, zero mass, duplicates, orphans;
- distribution shift (quantiles, mean/SD, skew, zero share) in original and transformed units;
- hypothesis support (eligibility n, pass counts, denominators);
- compute cost (runtime, rows scanned, bytes, plan change).

Output one long-format table:

```text
snapshot_id, stage_before, stage_after, dataset, grain, group, feature,
metric, value_before, value_after, delta, delta_pct,
n_before, n_after, denominator_note, is_partial
```

The comparison is descriptive only. It is not a p-value and must not be used to choose a hypothesis after seeing results.

Use a small shared contract:

- `DatasetRef` — source, schema/path, grain, snapshot, filters.
- `ProfileRecord` — dataset, stage, table, column, metric, value, denominator, group, notes.
- `StageManifest` — input/output table, rows in/out, filters, SQL hash, snapshot, `is_partial`.
- `ComparisonRecord` — before/after values, delta, denominators.

Both profiling and transforms import the contract. The transform code does **not** import profiling code, so there is no circular dependency. Hypothesis code imports only the cohort/feature outputs, never raw tables.

## 6. Testing strategy

Google classifies tests by size (resources) and scope (code), and recommends small tests whenever possible because they keep the suite fast and reliable. \[S13]\[S14] The repo currently has one test file for ETL arguments; there are no fixture tests for priority, features, or n-flow. \[S16]

Ship four test types:

| Type | Test | Runs on |
|---|---|---|
| Small | priority rules, feature formulas, n-flow arithmetic | pure fixtures |
| Small | profile record schema, allowed metrics | in-memory rows |
| Medium | cohort SQL on a tiny fixture schema | local PostgreSQL |
| Large | shard sum == table count; n-flow totals | real mirror |
| Golden | hash a bounded wallet sample | real table |

Test **your** rules, not PostgreSQL built-ins. The priority rule, the H2/H4/H6 formulas, and the n-flow arithmetic are the things that can silently change.

## 7. Performance and observability

The 8 GB target is a design constraint. The repo already states the right rules: SQL-first aggregation, bounded samples, server-side cursors, `COPY`, and no full-table pandas. \[S16]\[S27] Add:

- a benchmark script with representative queries and `EXPLAIN (ANALYZE, BUFFERS)`;
- a declared row bound on every read helper;
- `snapshot_id`, `run_id`, `is_partial`, and per-table coverage in every output;
- stage manifests with row counts, filters, and SQL hashes;
- failure artefacts (coverage report, n-flow, plan) instead of a metrics platform.

Do not build a monitoring stack. For a batch research pipeline, three artefacts are enough: the run report, the stage manifest, and the n-flow table.

## 7.1 Source-backed patterns

The data-quality checks are not ad hoc: declarative constraints are the established pattern for large datasets [S15], and dbt's generic tests (`unique`, `not_null`, `accepted_values`, `relationships`) are a compact vocabulary for the same idea [S17]. dbt unit tests use static `given`/`expect` fixtures before materialisation [S18]; pytest fixtures and Hypothesis provide the Python equivalents for fixture setup and property checks [S25][S26].

Idempotent writers follow Airflow's task rules: same outcome on re-run, no plain `INSERT`, no wall-clock inside the computation [S19]. Stage manifests borrow the job/run/dataset vocabulary from OpenLineage [S20]. The memory-safe tools are PostgreSQL `DECLARE` [S21], psycopg `ServerCursor` [S22], `COPY` [S23], and Parquet's columnar layout [S24].

The transform rules themselves live in `transform/README.md`: one rule, one place; SQL computes; n-flow per group × filter [S28].

## 8. What not to build

- Full Clean Architecture / onion / hexagonal blueprint.
- A repository class per table.
- A generic plugin system for metrics or transforms.
- A pipeline framework before a second scheduled pipeline or a second operator exists. \[S16]
- A shared abstraction for H2/H4/H6 runners before the common shape is stable.
- A `utils.py` dumping ground.
- Full-table pandas reads "just for profiling."
- Tests that require the 15M-row mirror before they can run.

## 9. Open questions

1. Is extracting `db.py` enough to remove the profile→ingest coupling, or is a separate `access.py` needed?
2. Should `ingest.py` remain the public facade, or should the CLI move to `cli.py` immediately?
3. Do we need a Parquet adapter now, or can the comparison run on PostgreSQL/CSV until DuckDB is installed?
4. What is the smallest stage-manifest schema that is still useful for before/after comparison?
5. How much notebook code should move into `eda/plots.py` before the cohort table is frozen?

## 10. Disagreements and limitations

- The Clean Code debate is partly rhetorical; no decisive controlled experiment settles it. The empirical code-smell literature is mixed, not a blanket refutation.
- "Deep modules" can be abused to justify a god module if the interface is not actually simple.
- SOLID critiques often attack strawman implementations; the principles can still help at a real seam.
- The recommendation to stay on plain scripts is a judgement about operational cost, not a benchmark result. It is falsifiable: add a second scheduled pipeline or a second operator and re-evaluate.
- The data research is stronger than the practice research: the data brief was completed by a researcher child, while the principles and practice children failed on a provider timeout and were covered by lead direct research.

## References

\[S1] Ousterhout, J., & Martin, R. C. — *A Philosophy of Software Design vs Clean Code* — https://github.com/johnousterhout/aposd-vs-clean-code/
\[S2] Behrens, C. — *Summary of "A Philosophy of Software Design"* — https://carstenbehrens.com/posts/summary-of-a-philosophy-of-software-design-by-john-ousterhout/
\[S3] Brooks, F. P. — *No Silver Bullet* (1987) — https://doi.org/10.1109/MC.1987.1663532
\[S4] Moseley, B., & Marks, P. — *Out of the Tar Pit* (2006) — https://curtclifton.net/papers/MoseleyMarks06a.pdf
\[S5] Parnas, D. L. — *On the Criteria To Be Used in Decomposing Systems into Modules* (1972) — https://doi.org/10.1145/361598.361623
\[S6] Ammerlaan, E. — *Effects of Refactoring on Productivity in Relation to Code Understandability* (2014) — http://resolver.tudelft.nl/uuid:bb857573-ca20-44ee-921a-30e66ee3767c
\[S7] Amit, I., Ben Ezra, N., & Feitelson, D. G. — *Follow Your Nose: Which Code Smells are Worth Chasing?* (2021) — https://arxiv.org/abs/2103.01861
\[S8] Metz, S. — *The Wrong Abstraction* (2016) — https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction
\[S9] Krämer, F. — *Are the SOLID Principles Problematic?* (2025) — https://florian-kraemer.net/software-architecture/2025/02/24/Are-the-SOLID-Principles-problematic.html
\[S10] Rentea, V. — *Overengineering in Onion/Hexagonal Architectures* (2023) — https://victorrentea.ro/blog/overengineering-in-onion-hexagonal-architectures/
\[S11] Hickey, R. — *Simple Made Easy* (2011) — https://github.com/matthiasn/talk-transcripts/blob/master/Hickey_Rich/SimpleMadeEasy-mostly-text.md
\[S12] Destroy All Software — *Functional Core, Imperative Shell* (2012) — https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell/
\[S13] Google — *Software Engineering at Google*, Ch. 11 — https://abseil.io/resources/swe-book/html/ch11.html
\[S14] Google — *Software Engineering at Google*, Ch. 12 — https://abseil.io/resources/swe-book/html/ch12.html
\[S15] Schelter et al. — *Automating Large-Scale Data Quality Verification* (2018) — https://www.vldb.org/pvldb/vol11/p1781-schelter.pdf
\[S16] `outputs/.drafts/software-design-foundations-research-data.md` — data-intensive architecture brief
\[S17] dbt Docs — *Add data tests to your DAG* — https://docs.getdbt.com/docs/build/data-tests
\[S18] dbt Docs — *Unit tests* — https://docs.getdbt.com/docs/build/unit-tests
\[S19] Apache Airflow — *Best Practices* — https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html
\[S20] OpenLineage — *Object Model* — https://openlineage.io/docs/spec/object-model
\[S21] PostgreSQL — *DECLARE* — https://www.postgresql.org/docs/current/sql-declare.html
\[S22] psycopg 3 — *Cursor types* — https://www.psycopg.org/psycopg3/docs/advanced/cursors.html
\[S23] PostgreSQL — *COPY* — https://www.postgresql.org/docs/current/sql-copy.html
\[S24] Apache Parquet — *File Format* — https://parquet.apache.org/docs/file-format/
\[S25] pytest — *About fixtures* — https://docs.pytest.org/en/stable/explanation/fixtures.html
\[S26] Hypothesis — https://hypothesis.readthedocs.io/en/latest/
\[S27] Repo — `src/scripts/etl/README.md`
\[S28] Repo — `src/scripts/etl/transform/README.md`
\[S29] Repo — `AGENTS.md`, `tasks/hypothesis_testing/README.md`
\[S30] Repo — `src/scripts/etl/verify_ingestion.py`


---

## Citation status

- **S1–S4, S8, S10–S14:** fetched and read as HTML/PDF; claims are limited to the fetched text.
- **S5, S3:** DOI metadata only; the papers were not fetched in full. Claims are limited to their well-known definitions and are marked as metadata-level.
- **S6–S7:** abstract/search metadata only; the specific findings are stated as the authors' abstracts report them.
- **S9:** search metadata only; the article was not fetched in full.
- **S11:** transcript fetched.
- **S15–S26:** source evidence recorded in `outputs/.drafts/software-design-foundations-research-data.md` by the data-research child; the lead did not re-fetch every URL. Treat those as secondary verification.
- **S27–S30:** local repo files read directly.
- **Blocked:** the principles and practice researcher children failed with a model-provider connection timeout; the lead substituted direct search/fetch. The verifier/reviewer subagents were not used because the same provider was failing; this is a lead review, not an independent verification.

**Verification: PASS WITH NOTES** — citations are mapped, but S5/S3 are metadata-level and S15–S26 are second-hand from the data-research child.
