# Software concepts

Short, topic-scoped notes for how code is designed in this repo. Read the file for the decision you are making, not the whole folder.

Each file has the same shape: **Status → Scenario → Code → Rule → Debate**. That is deliberate: you can challenge one rule without re-reading a 3,000-word essay.

## Approval gate

- `Status: draft` — reference only.
- `Status: proposed` — ready for review; **not normative**.
- `Status: approved` — normative; may be cited from `AGENTS.md`, tasks, code, and reviews.
- `Status: Accept` / `accepted` / `Accepted` — user-set acceptance variants; treat them as accepted unless the user changes the line.
- `Status: superseded` — replaced.

**Only the user changes `Status:` to `approved`.** Agents must not edit the status line. An unapproved file cannot be cited as a project rule. When approved, add `Approved by:` and `Approved on:`.

Accepted by the user: `01`, `02`, `03`, `04`, `05`, `07`, `09`, `10`. Still proposed: `06`, `08`. The index below is the source of truth.

## Index

| File | Topic | Status |
| --- | --- | --- |
| [`01-complexity-and-modules.md`](01-complexity-and-modules.md) | complexity, deep modules, simple vs easy | Accept (user-set) |
| [`02-layers-and-boundaries.md`](02-layers-and-boundaries.md) | L0–L5, one-way dependencies, functional core | accepted |
| [`03-profiling-and-comparison.md`](03-profiling-and-comparison.md) | raw→clean→eligible→feature comparison, manifests | Accepted |
| [`04-abstraction-and-dry.md`](04-abstraction-and-dry.md) | Clean Code, SOLID, DRY, wrong abstraction | Accepted |
| [`05-naming-and-comments.md`](05-naming-and-comments.md) | exact naming rules, comments, rename policy | Accepted |
| [`06-testing.md`](06-testing.md) | fixture, property, n-flow, golden, data-quality tests | proposed |
| [`07-performance-and-observability.md`](07-performance-and-observability.md) | 16–23 GB bounds, SQL-first, benchmarks, manifests | Accepted |
| [`08-migration-checklist.md`](08-migration-checklist.md) | ordered implementation checklist | proposed |
| [`09-references.md`](09-references.md) | sources and full research link | Accepted |
| [`10-sql-rules.md`](10-sql-rules.md) | NULL-safe anti-joins, fan-out, constraints, PostgreSQL composition | accepted |

## Reading order

1. **Complexity and modules** — why we split at all.
2. **Layers and boundaries** — where the split goes.
3. **Profiling and comparison** — how we see the data before/after transforms.
4. **Abstraction and DRY** — when not to split.
5. **Naming and comments** — the exact low-level rules.
6. **Testing** — the largest section; read before merging code.
7. **Performance and observability** — the 8 GB constraint.
8. **SQL rules** — the exact SQL patterns and anti-patterns.
9. **Migration checklist** — the order to implement.
10. **References** — evidence and the full research report.

## Research evidence

Longer reports live in [`research/`](research/README.md). They are evidence, not baseline. The baseline is the numbered topic files.

- [`research/software-design-foundations.md`](research/software-design-foundations.md) — complexity, modules, layers, profiling, testing.
- [`research/sql-pragmatic-craft.md`](research/sql-pragmatic-craft.md) — SQL for Smarties, The Pragmatic Programmer, external-book audit.
- The external book is still **not present**; see [`research/README.md`](research/README.md).

## Rule for adding a concept

Create a new topic file, add it to the index, keep it under 200 words unless detail is necessary, and leave it `proposed`. The user approves by editing `Status:`.
