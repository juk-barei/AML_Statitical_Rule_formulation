# AGENTS.md — project contract

This file is the short, enforceable contract for agents working in this repo.
Detailed evidence and decisions live in `docs/context/step_1_profiling_samples.md`.

## Data authority

- Terminology is canonical in `docs/context/glossary.md`: rules are `S1`–`S6`, research questions `H1`–`H6`, null/alternative `H0`/`Ha` (never `H1`), and the third implemented level is `unlabeled` (never `background`).
- **PostgreSQL mirror** is the analysis dataset. `src/scripts/etl/ingest.py` is the only writer of the local mirror; `src/scripts/etl/load.py` is the designated writer for shared exports.
- `datasets/*.csv` is a **stale, partial export**. Never mix CSV and mirror counts in one table or conclusion.
- State the snapshot and row counts beside any quantitative claim.
- Use `src/.env.example` as the variable contract. Never read or print `src/.env`; the ETL modules load it internally.
- Never print connection strings or credentials.

## Data access, memory, and export

- **PostgreSQL computes; pandas displays.** Push filters, joins, cohort priority, eligibility, deduplication, and feature aggregation into SQL. Never load `accounts`, `transactions`, or `wallet_hops` wholesale into pandas.
- **Return small results.** Select only needed columns; return wallet-level aggregates or a bounded sample (`50k–100k` rows). `LIMIT` is for exploration only; reported counts must come from full-frame SQL.
- **Stream row-level work.** Use `engine.connect().execution_options(stream_results=True)` with `pd.read_sql_query(..., chunksize=50_000)` and process one chunk or wallet group at a time.
- **The mirror is read-only outside the ETL writers.** Notebooks and ad-hoc scripts must not `INSERT`, `UPDATE`, `DELETE`, or run DDL against the mirror.
- **Cleaning is a documented rule, not an eyeball edit.** Express it as a read-only CTE/view, apply it identically to every arm, and report the n-flow. Never silently drop zero-event or undefined rows.
- **Export contract:** Parquet is the analysis handoff; CSV only for small manifests/data dictionaries; managed PostgreSQL only for the wallet-level serving table. DuckDB queries Parquet; it does not replace the mirror or the serving database.
- **Freeze before export.** Record snapshot time, source, per-table row counts, exclusions, and a manifest/hash. Never mix mirror, sample, and CSV counts.
- **Sampling:** sample wallets, never transaction rows. Census small/rare arms; keep all events for selected wallets. Record seed, strata, cluster, and weights.

Details and code patterns: `src/scripts/etl/README.md`.

## Repository layout

- Code areas are `src/scripts/{etl,eda,hypothesis_testing,statistical_learning}`.
- `outputs/` mirrors those areas: every artifact goes under the area that produces it.
  - ETL: `outputs/etl/{profile,tests,transform,export}`; handoff snapshots live in `outputs/etl/export/<snapshot>/`.
  - EDA: `outputs/eda/{univariate,bivariate,multivariate,profile,additional}`.
  - Hypothesis testing: `outputs/hypothesis_testing/{shared,h2,h4,h6}`.
  - Statistical learning: `outputs/statistical_learning/`.
- Trackers mirror the same split: `tasks/etl/`, `tasks/eda/`, `tasks/statistical_learning/`; the 8-step workflow stays in `tasks/hypothesis_testing/`.
- Do not create a new top-level output or task folder without updating this contract and `src/scripts/README.md`.
- `src/scripts/etl/ingest.py` writes ETL outputs; `src/scripts/etl/load.py` writes handoff exports. Notebooks write only under their producer area.
- Software-design baseline: start at `docs/dev/software_concepts/README.md`. Files with user-set `Status: Accept`, `accepted`, `Accepted`, or `approved` are normative; `proposed`/`draft` are reference only. Current accepted baseline: `01`, `02`, `05`, `07`, `09`, `10`. Agents must not change a status; only the user approves. `docs/dev/software_concepts/research/` is evidence, not policy.
- Variable/function names are provisional. Renaming is allowed when a name becomes ambiguous or the project grows; update Python, SQL, tests, docs, and output columns in one change, and do not keep aliases.

## Cohort contract

| Group | Rule |
| --- | --- |
| `illicit` | Blacklisted wallets (`blacklisted_wallets`) plus hop-0 wallets |
| `suspicious` | `min(hop_level) ∈ 1..5` **and** not blacklisted |
| `licit` | External licit database (`LICIT_ONLINE_DATABASE_LINK`); ingestion pending |
| `unlabeled` | Universe minus illicit and suspicious; **provisional**, never called licit |

**Priority:** blacklist wins at every hop. Any wallet with a blacklist record at hop 1–5 is **illicit**, not suspicious — not just hop 3.

**Nesting:** hop depth is nested inside `suspicious`, not crossed with `wallet_class`. Do not fit a crossed `class × hop` two-way ANOVA.

## Inference rules

- Non-parametric tests (Mann–Whitney, Kruskal–Wallis, Dunn) relax normality and equal-variance assumptions. They **do not** fix dependence.
- `suspicious` is graph-derived from blacklisted seeds and is not an independent sample. Use seed-cluster permutation/bootstrap, a mixed model, or report it as a nested/descriptive arm.
- Once licit is ingested, the clean independent contrast is **illicit vs licit**. Check overlap and sampling-frame compatibility before pooling.
- Follow the Lecture 05 eight-step ANOVA workflow: response/factor/groups → H0/Ha/α → explore → assumptions → test → post-hoc → effect size → conclusion.
- Report effect sizes and exact denominators, not only p-values.

## Workflow and outputs

- EDA follows the Lecture 02 structure: data types/chart map → univariate numerical → univariate categorical → numerical–numerical → numerical–categorical → categorical–categorical → multivariate.
- Keep the three-group comparison inside the numerical–categorical section (side-by-side boxplots, overlaid densities, mean ± SD).
- `src/scripts/` holds reusable analysis code; `src/notebooks/` holds official analysis code. Scripts must be reproducible and print the numbers they support; notebooks import them.
- Notebooks are read-only against the mirror.
- Every new rule, transform, or feature ships with a test: a pure-rule test, a SQL fixture test, and an n-flow assertion where applicable. A transform without those is not `done`.
- Cite the script path and line number for every number or insight taken from code.
- Put durable decisions in `docs/context/`; put mechanism, tooling, and architecture notes in `docs/dev/`. Routine notes stay under 200 words; a technical reference may exceed that when the mechanism or trade-off requires depth.

## Documentation standard

- **Documentation ships with the change.** No technical concept is `done` until its `docs/dev/` note or module `README.md` explains how it works, why it was chosen, its limits, and the commands that operate it.
- **Write for a technical reader.** State the process model, data path, types, concurrency, memory/disk behavior, failure modes, trade-offs, versions, paths, flags, and verification. Do not substitute marketing language, unexplained analogies, or a command list for mechanism.
- **Depth follows the concept.** A routine note stays short; a technical reference gets enough depth to implement or audit the decision without re-deriving it.
- **One source of truth.** `docs/dev/` holds architecture and tooling; module `README.md` files hold pipeline behavior; `docs/context/` holds durable decisions; `tasks/` holds status. Link instead of duplicating.
- **Mark history as history.** Do not present stale line numbers or pre-refactor behavior as current.

## Subtask execution

- One subtask is one Markdown file or one update to existing files.
- Delegate subtasks to subagents and activate the matching skill for each agent.
- Fact-check current facts after each insight; report contradictions, gaps, or conflicting evidence instead of smoothing them over.

## Task tracking

- `tasks/` is the live tracker for the 8-step workflow; start at `tasks/hypothesis_testing/README.md`.
- Each step directory has `main.md` (objective + shared task table) and shared task files. Active hypotheses have one tracker each: `tasks/hypothesis_testing/H2.md`, `H4.md`, `H6.md`.
- Phase-1 active hypotheses are **H2, H4, H6**; **H1, H3, H5 are deferred** and have no tracker.
- Do not create per-step `H2/H4/H6` folders; update the hypothesis tracker instead.
- Every other `.md` file at the step root is one shared subtask or helper task.
- After every run, update the touched step `main.md`, hypothesis tracker (`H2.md`, `H4.md`, or `H6.md`), and task files: status, blocked by, blocks, output, updated.
- Each task records resources/context, file actions (`create` / `update` / `delete` / `rename`), and implementation points.
- Status vocabulary: `todo` / `in_progress` / `blocked` / `done`.
- Move `done` task files to `tasks/_archive/hypothesis_testing/<step>/`; keep the step `main.md` table pointing to the archived file. Do not delete done tasks.
- Keep entries concise; link to docs/scripts instead of duplicating them.

## Data hygiene

- Drop `hex_address` from analysis views unless a task explicitly needs the hex form.
- Resolve undefined responses by a stated eligibility rule, never by silently dropping zeros.
- Report an n-flow table (group × filter) for every response.

## Open items

- Ingest the licit database and profile its schema, coverage, and overlap with the blacklist.
- Build the authoritative cohort table with `illicit / suspicious / licit / unlabeled`.
- Add written H0/H1 per response and run the assumption checks.
