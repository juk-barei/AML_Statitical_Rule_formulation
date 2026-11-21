# Task tracker

Live tracker for the 8-step ANOVA workflow.

- **Status:** `todo` / `in_progress` / `blocked` / `done`
- Each step directory has `main.md` (objective + shared task table), `H1`–`H6/main.md`, and shared task files.
- Phase-1 active hypotheses are **H2, H4, H6**; **H1, H3, H5 are deferred**.
- Every other `.md` file at the step root is one shared subtask or helper task.
- Update after every run: status, blocked by, blocks, output, updated.
- Keep entries concise; link to docs/scripts instead of duplicating them.

## Task file shape

Every task and `main.md` records:

- **Resources / context** — docs, code, data, and references used.
- **Files** — `create`, `update`, `delete`, or `rename`, with exact paths.
- **Implementation points** — the main points only.

## Steps

1. `01_response_factor_groups`
2. `02_hypotheses_alpha`
3. `03_explore`
4. `04_assumptions`
5. `05_omnibus_test`
6. `06_posthoc`
7. `07_effect_size`
8. `08_conclusion`
