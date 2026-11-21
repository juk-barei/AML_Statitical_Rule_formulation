# Agent contract and repo directives

- **Status:** done
- **Blocked by:** —
- **Blocks:** all tasks
- **Owner:** main
- **Output:** `AGENTS.md`, README block, renamed stats file
- **Updated:** 2026-11-20

## Objective

Capture data authority, cohort priority, dependence rules, script/notebook split, citation rule, concise docs, and the task tracker. Rename `statisitical_info.md` to `statistical_info.md`.

## Resources / context

- conversation feedback
- `AGENTS.md` — data authority, cohort priority, task rules
- `README.md`
- `docs/context/statistical_info.md`

## Files

| Action | Path | Purpose |
| --- | --- | --- |
| update | `AGENTS.md` | data, cohort, inference, and task rules |
| update | `README.md` | current directives block |
| rename | `docs/context/statisitical_info.md -> docs/context/statistical_info.md` | filename correction |
| update | `.gitignore` | allow `.env.example` |

## Implementation points

- Keep rules short and enforceable.
- Record script/notebook split and citation rule.
- Keep `.env` ignored; expose only `.env.example`.

## Done when

- `AGENTS.md` updated.
- README directives block added.
- Old filename has no references.
