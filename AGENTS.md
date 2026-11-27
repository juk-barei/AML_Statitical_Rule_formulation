# AGENTS.md — project contract
<!-- Last updated: 2026-11-27 | Edit count: 5 -->

This file is the short, enforceable contract for agents working in this repo.
Detailed evidence and decisions live in `docs/context/step_1_profiling_samples.md`.

## Task execution

Branch, label, and scope rules are in `docs/dev/github_convention.md`; this section is the gate an agent runs before touching files.

### 1. Scope gate (before any work)

- Read `docs/dev/github_convention.md` and classify the request: area (`ETL`, `EDA`, `HP_TEST`, `STL`), subcategory (the folder that owns the change), and label (`BUG`, `FEAT`, `DOC`).
- A phase is committable only when it touches one narrow scope: one subcategory, its matching tests, and the docs that describe it. If the request crosses subcategories, split it into phases.
- **Stall before editing** when the working tree already holds enough unrelated change for a commit, or when the request would mix scopes. Do not open, create, or modify task files for the new work yet.

### 2. Stall response

Tell the user, in this order:

1. **Alert:** the uncommitted change or cross-scope request, and why `github_convention.md` blocks starting now.
2. **Recommendation:** branch `author/<area>-<subcategory>` and commit `[LABEL-subcategory]: <short imperative description>`. Use `[DOC-...]` only when the change is documentation-only; otherwise `[FEAT-...]` / `[BUG-...]` even if docs are included.
3. **Plan to completion:** every phase needed to finish the request, each with its location (project paths), scope, and verification. Each phase must fit one branch/commit scope.
4. **Approval question:** ask the user to approve the phase plan before adding it to the task list. Do not execute any phase in the same turn as the stall.

The user commits, creates the branch, or approves the plan first.

### 3. Phase loop

- Approved phases become the task list; one phase is one active task.
- Before phase N, verify the prerequisite is real: correct branch, expected commit present, and no unrelated uncommitted files. If not, stall again with §2.
- Execute only phase N inside its declared paths. Do not fix neighbouring scopes, rename unrelated files, or expand the phase.
- Verify phase N (tests, lint, render, or file state) and report the evidence.
- Stop and ask the user to review. Recommend that phase's commit message. Do not start phase N+1 until the user commits and explicitly asks.
- **Documentation freshness trigger:** At the end of every phase, stage migration, rename, or ingestion milestone, the agent must enter an audit check for documentation staleness. If paths (e.g. script renames), cohort invariants (e.g. ingestion status), or task trackers have drifted from the codebase reality, the agent MUST explicitly alert and remind the user to update documentation across `AGENTS.md`, `README.md`, `docs/`, and `tasks/` to ensure continuous relevancy and prevent drift before moving on.
- A new request while a phase is in progress goes through §1 again; it is not an extension of the current phase.

Every stall and phase report names the location (directories/files), scope (area / subcategory / label), and the exact next action for the user.

## Data authority
- Terminology is canonical in `docs/context/glossary.md`: rules are `S1`–`S6`, research questions `H1`–`H6`, null/alternative `H0`/`Ha` (never `H1`), and the third implemented level is `unlabeled` (never `background`).
- **PostgreSQL mirror** is the analysis dataset. `src/scripts/etl/extract/main.py` is the only writer of the local mirror; `src/scripts/etl/load/main.py` is the designated writer for shared exports.
- `datasets/*.csv` is a **stale, partial export**. Never mix CSV and mirror counts in one table or conclusion.
- State the snapshot and row counts beside any quantitative claim.
- Use `src/.env.example` as the variable contract. Never read or print `src/.env`; the ETL modules load it internally.
- Never print connection strings or credentials.

## Data access, memory, and export

- **PostgreSQL computes; pandas displays.** Push filters, joins, cohort priority, eligibility, deduplication, and feature aggregation into SQL. Never load `accounts`, `transactions`, or `wallet_hops` wholesale into pandas.
- **Return small results.** Select only needed columns; return wallet-level aggregates or a bounded sample (`50k–100k` rows). `LIMIT` is for exploration only; reported counts must come from full-frame SQL.
- **Stream row-level work.** Use `engine.connect().execution_options(stream_results=True)` with `pd.read_sql_query(..., chunksize=50_000)` and process one chunk or wallet group at a time.
- **The L0 mirror (`illicit.*`, `licit.*`) is read-only outside `extract/main.py`.** Notebooks and ad-hoc scripts must not `INSERT`, `UPDATE`, `DELETE`, or run DDL against the mirror.
- **Cleaning is a documented rule, not an eyeball edit.** Express it in transform SQL (as a CTE/view, or materialized view/table in a dedicated transform schema with documented `DROP SCHEMA` cleanup at project end), apply it identically to every arm, and report the n-flow. Never silently drop zero-event or undefined rows.
- **Export contract:** Parquet is the analysis handoff; CSV only for small manifests/data dictionaries; managed PostgreSQL only for the wallet-level serving table. DuckDB queries Parquet; it does not replace the mirror or the serving database.
- **Indexing by consumer role:** Keep L0 (`illicit.*`, `licit.*`) unindexed and read-only. In a dedicated local transform schema, create join-key indexes (e.g., `wallet_address` on materialized L1/L2) only when a PostgreSQL transform join needs them and only **after** bulk materialization; Parquet `COPY` export is a sequential scan and does not benefit from B-tree indexes. Analytical consumers (`H1`–`H6`) scan frozen Parquet snapshots without DB indexes; `wallet_serving` in managed PostgreSQL creates `address PRIMARY KEY` after bulk load for concurrent point lookups (plus secondary indexes owned by the web app team).
- **Freeze before export.** Record snapshot time, source, per-table row counts, exclusions, and a manifest/hash. Never mix mirror, sample, and CSV counts.
- **Export naming:** the default snapshot id is `phase<N>_<stage>_<schema>_<UTC>`. `N` is the positive integer in `[tool.capstone].phase` in `pyproject.toml`; `stage` is `raw` or `transformed`. `manifest.json` records `snapshot`, `directory`, `phase`, `stage`, and `schema`. Do not hardcode the phase or publish a snapshot without those fields.
- **Sampling:** sample wallets, never transaction rows. Census small/rare arms; keep all events for selected wallets. Record seed, strata, cluster, and weights.

Details and code patterns: `src/scripts/etl/README.md`.

## Repository layout

- Code areas are `src/scripts/{etl,eda,hypothesis_testing,statistical_learning}`.
- **ETL has exactly three stages**, matching its name: `src/scripts/etl/{extract,transform,load}`. `profile/` is not a stage; it is a read-only first step inside `transform/`.
- **Each stage entry point is `main.py`** inside its stage directory, so the folder supplies the context: `extract/main.py`, not `extract/extract.py`; and `load/main.py`, not `load/load.py`. Helper modules keep their own names.
- **Tests live with the stage they test**, in `<stage>/tests/`: `extract/tests/`, `load/tests/`, and `transform/<module>/tests/`. There is no top-level `etl/tests/`, and no `outputs/etl/tests/`.
- `outputs/` mirrors those areas: every artifact goes under the area that produces it.
  - ETL: `outputs/etl/{extract,transform,load}`. Profiling writes stage-scoped outputs to `outputs/etl/transform/profile/{raw,transformed}/` (`raw` baseline vs. post-transform); handoff snapshots live in `outputs/etl/load/phase<N>_<stage>_<schema>_<UTC>/`.
  - EDA: `outputs/eda/{univariate,bivariate,multivariate,profile,additional}`.
  - Hypothesis testing: `outputs/hypothesis_testing/{shared,h2,h4,h6}`.
  - Statistical learning: `outputs/statistical_learning/`.
- Trackers mirror the same split: `tasks/etl/`, `tasks/eda/`, `tasks/statistical_learning/`; the 8-step workflow stays in `tasks/hypothesis_testing/`.
- Do not create a new top-level output or task folder without updating this contract and `src/scripts/README.md`.
- `src/scripts/etl/extract/main.py` writes ETL outputs; `src/scripts/etl/load/main.py` writes handoff exports. Notebooks write only under their producer area.
- Software-design baseline: start at `docs/dev/software_concepts/README.md`. Files with user-set `Status: Accept`, `accepted`, `Accepted`, or `approved` are normative; `proposed`/`draft` are reference only. Current accepted baseline: `01`, `02`, `03`, `04`, `05`, `07`, `09`, `10`. Agents must not change a status; only the user approves. `docs/dev/software_concepts/research/` is evidence, not policy.
- Variable/function names are provisional. Renaming is allowed when a name becomes ambiguous or the project grows; update Python, SQL, tests, docs, and output columns in one change, and do not keep aliases.

## Cohort contract

| Group | Rule |
| --- | --- |
| `illicit` | Blacklisted wallets (`blacklisted_wallets`) plus hop-0 wallets |
| `suspicious` | `min(hop_level) ∈ 1..5` **and** not blacklisted |
| `licit` | External licit database (`LICIT_ONLINE_DATABASE_LINK`); 100% ingested into mirror |
| `unlabeled` | Universe minus illicit and suspicious; **provisional**, never called licit |

**Priority:** blacklist wins at every hop. Any wallet with a blacklist record at hop 1–5 is **illicit**, not suspicious — not just hop 3.

**Nesting:** hop depth is nested inside `suspicious`, not crossed with `wallet_class`. Do not fit a crossed `class × hop` two-way ANOVA.

## Inference rules

- Non-parametric tests (Mann–Whitney, Kruskal–Wallis, Dunn) relax normality and equal-variance assumptions. They **do not** fix dependence.
- `suspicious` is graph-derived from blacklisted seeds and is not an independent sample. Use seed-cluster permutation/bootstrap, a mixed model, or report it as a nested/descriptive arm.
- Now that licit is ingested into mirror, the clean independent contrast is **illicit vs licit**. Check overlap and sampling-frame compatibility before pooling.
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
- **Write in term of analogy or scenario or example**: Try to make it clear with the way you emphasize a concept via direct scenario and code. Let the reader read it shortly and think longer. Don't simplify, be direct and clear, the user can't understand is the user's skill issue. 
- **One source of truth.** `docs/dev/` holds architecture and tooling; module `README.md` files hold pipeline behavior; `docs/context/` holds durable decisions; `tasks/` holds status. Link instead of duplicating.
- **Mark history as history.** Do not present stale line numbers or pre-refactor behavior as current.
- **Documentation freshness and drift trigger.** Documentation must never lag behind code state. After any series of updates (e.g., module renames, stage migrations, database ingestion completion, or schema adjustments), the agent triggers an audit state: scan `AGENTS.md`, `README.md`, `docs/`, and `tasks/` for stale references and explicitly remind the user to update their documentation to reflect current reality.
- Have date of edit and write. Has edit count on it as well. Write a new files has edit counts of 1 next time it is 2, and so on.

## `docs/dev/` notes

`docs/dev/` holds post-implementation technical notes: the mechanism, the reason it was chosen, and its limits. It is not an API reference, a usage guide, or a copy of the code.

- **Area mirrors production.** The top level mirrors the `src/scripts/` areas: `etl/`, `eda/`, `hypothesis_testing/`, `statistical_learning/`.
- **Unit names the owner.** The next level is the script or module that owns the mechanism (`etl/extract/`, `etl/load/`, `etl/transform/profile/`, `hypothesis_testing/shared/`). When no script owns it, use the analysis or output stage (`eda/univariate/`, `etl/transform/`). When both exist, the script wins: export notes live in `etl/load/`, not `etl/export/`. Do not create one directory per source file.
- **File names the concept.** Name the file for the mechanism, not for the folder: `etl/load/duckdb-and-reproducible-exports.md`, not `etl/load/load.md`.
- **Two deliberate exceptions.** `software_concepts/` is the only pre-implementation space; it holds user-approved design blueprints. `hypothesis_testing/general/` holds concepts shared across H2/H4/H6; per-hypothesis notes go in `h2/`, `h4/`, `h6/`.
- **Ship with the code.** Write the note after the implementation settles. A note that only restates the implementation is not a note.
- **Empty units are placeholders.** A directory may exist before its first note; do not create a file only to fill it.

**Boundary with code.** The split is scope and lifetime, not topic.

- A comment states only what must be true at that line: why the obvious edit is wrong, an invariant at the point it is enforced, a constant's provenance, or a shortcut. Edit it with the code; a stale comment is a bug.
- A docstring states the call contract: args, returns, raises, units, snapshot.
- `docs/dev/` states the mechanism, rejected alternatives, limits, and how to verify — anything that survives a rewrite of the function.
- If a comment needs a table, a diagram, or more than about three lines, it is a doc: move it and leave a one-line anchor.
- One fact has one home: docs own the mechanism, the comment owns only the local consequence, and the other side links.

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
- Report an n-flow table (`wallet_class × filter`) for every response.

## Open items

- Profile licit schema, coverage, and overlap with the blacklist (licit database ingestion is 100% complete).
- Build the authoritative cohort table with `illicit / suspicious / licit / unlabeled`.
- Add written H0/H1 per response and run the assumption checks.
## Terminology
- Hedgehog analogy: Hedgehog mode is about organization of files and directory that reflects each other in src/scripts/, outputs/, and tasks/. It is about having clear separation in each section clearly like ETL has Extract, load, and transform. Inside Extract there are Extract from parquet, online db. In load there are load to parquet, csv, or online db.
- When I askeed you to help me with hedgehog situation or mode, I meant to ask you to help find category for that directory I am asking you about, and also consider crating reflected or connecting directory in other parts of the project as well/ Ex: I ask about hedgehog analogy for transform directory in src/scripts/etl/transform. You can try to think of the right way to categorize takss in transform here given the context and info and also  think of what directories to create in outputs/ and tasks and in docs/dev/.
