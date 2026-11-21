# AGENTS.md — project contract

This file is the short, enforceable contract for agents working in this repo.
Detailed evidence and decisions live in `docs/context/step_1_profiling_samples.md`.

## Data authority

- Terminology is canonical in `docs/context/glossary.md`: rules are `S1`–`S6`, research questions `H1`–`H6`, null/alternative `H0`/`Ha` (never `H1`), and the third implemented level is `unlabeled` (never `background`).
- **PostgreSQL mirror** is the analysis dataset. `src/scripts/ETL.py` is the only writer.
- `datasets/*.csv` is a **stale, partial export**. Never mix CSV and mirror counts in one table or conclusion.
- State the snapshot and row counts beside any quantitative claim.
- Use `src/.env.example` as the variable contract. Never read or print `src/.env`; `ETL.py` loads it internally.
- Never print connection strings or credentials.

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
- Follow the Lecture 05 eight-step ANOVA workflow: response/factor/groups → H0/H1/α → explore → assumptions → test → post-hoc → effect size → conclusion.
- Report effect sizes and exact denominators, not only p-values.

## Workflow and outputs

- EDA follows the Lecture 02 structure: data types/chart map → univariate numerical → univariate categorical → numerical–numerical → numerical–categorical → categorical–categorical → multivariate.
- Keep the three-group comparison inside the numerical–categorical section (side-by-side boxplots, overlaid densities, mean ± SD).
- `src/scripts/` is for helper functions and small agent/people profiling; create it if absent. Code there must be reproducible and print the numbers it supports. But make sure to call module in this to `src/notebooks/` when possible.
- `src/notebooks/` is for official analysis code. Notebooks are read-only against the mirror.
- Cite the script path and line number for every number or insight taken from code.
- Put durable decisions in `docs/context/`; keep docs under 200 words unless the detail is absolutely necessary.

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
