# Research evidence

Evidence used by the proposed concept files. **Not normative.** The baseline is the numbered topic files in the parent directory; these reports are the longer argument behind them.

| File | Covers | Status |
| --- | --- | --- |
| [`software-design-foundations.md`](software-design-foundations.md) | complexity, modules, layers, profiling, testing, performance | research |
| [`software-design-foundations.provenance.md`](software-design-foundations.provenance.md) | sources and blocked checks | provenance |
| [`sql-pragmatic-craft.md`](sql-pragmatic-craft.md) | SQL for Smarties, The Pragmatic Programmer, external-book audit | research |
| [`sql-pragmatic-craft.provenance.md`](sql-pragmatic-craft.provenance.md) | sources and blocked checks | provenance |

## External book — blocked

The book the user believed was added is **not present** under `docs/external_resources/`. That folder contains only the five lecture PDFs. The only file under `resources/books/` is a 902-byte blockchain note, not a book.

To unblock: place the book in `docs/external_resources/` and provide its filename/title/author/edition, then re-run the audit. Until then, no claim about its relevance is made.

## How this feeds the baseline

- `10-sql-rules.md` draws on SQL for Smarties + PostgreSQL docs.
- `04`, `06`, `07`, and `08` draw on the Pragmatic Programmer + existing concept files.
- `09-references.md` lists the sources; this folder holds the long reports.
