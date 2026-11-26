# References

- **Status:** Accepted 
- **Parent:** [`README.md`](README.md)
- **Full research:** [`research/software-design-foundations.md`](research/software-design-foundations.md)
- **Provenance:** [`research/software-design-foundations.provenance.md`](research/software-design-foundations.provenance.md)
- **SQL/Pragmatic research:** [`research/sql-pragmatic-craft.md`](research/sql-pragmatic-craft.md)
- **SQL/Pragmatic provenance:** [`research/sql-pragmatic-craft.provenance.md`](research/sql-pragmatic-craft.provenance.md)

## Design principles

| ID | Source | URL |
| --- | --- | --- |
| S1 | Ousterhout & Martin, *A Philosophy of Software Design vs Clean Code* | <https://github.com/johnousterhout/aposd-vs-clean-code/> |
| S2 | Behrens, summary of *A Philosophy of Software Design* | <https://carstenbehrens.com/posts/summary-of-a-philosophy-of-software-design-by-john-ousterhout/> |
| S3 | Brooks, *No Silver Bullet* (1987) | <https://doi.org/10.1109/MC.1987.1663532> |
| S4 | Moseley & Marks, *Out of the Tar Pit* (2006) | <https://curtclifton.net/papers/MoseleyMarks06a.pdf> |
| S5 | Parnas, *On the Criteria To Be Used in Decomposing Systems into Modules* (1972) | <https://doi.org/10.1145/361598.361623> |
| S6 | Ammerlaan, refactoring/productivity dissertation (2014) | <http://resolver.tudelft.nl/uuid:bb857573-ca20-44ee-921a-30e66ee3767c> |
| S7 | Amit, Ben Ezra & Feitelson, *Follow Your Nose* (2021) | <https://arxiv.org/abs/2103.01861> |
| S8 | Metz, *The Wrong Abstraction* (2016) | <https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction> |
| S9 | Krämer, *Are the SOLID Principles Problematic?* (2025) | <https://florian-kraemer.net/software-architecture/2025/02/24/Are-the-SOLID-Principles-problematic.html> |
| S10 | Rentea, *Overengineering in Onion/Hexagonal Architectures* (2023) | <https://victorrentea.ro/blog/overengineering-in-onion-hexagonal-architectures/> |
| S11 | Hickey, *Simple Made Easy* (2011) | <https://github.com/matthiasn/talk-transcripts/blob/master/Hickey_Rich/SimpleMadeEasy-mostly-text.md> |
| S12 | Destroy All Software, *Functional Core, Imperative Shell* (2012) | <https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell/> |

## Testing, data quality, and pipelines

| ID | Source | URL |
| --- | --- | --- |
| S13 | Google, *Software Engineering at Google*, Ch. 11 | <https://abseil.io/resources/swe-book/html/ch11.html> |
| S14 | Google, *Software Engineering at Google*, Ch. 12 | <https://abseil.io/resources/swe-book/html/ch12.html> |
| S15 | Schelter et al., *Automating Large-Scale Data Quality Verification* (2018) | <https://www.vldb.org/pvldb/vol11/p1781-schelter.pdf> |
| S16 | Data-intensive architecture research brief | `outputs/.drafts/software-design-foundations-research-data.md` |
| S17 | dbt, *Add data tests to your DAG* | <https://docs.getdbt.com/docs/build/data-tests> |
| S18 | dbt, *Unit tests* | <https://docs.getdbt.com/docs/build/unit-tests> |
| S19 | Airflow, *Best Practices* | <https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html> |
| S20 | OpenLineage, *Object Model* | <https://openlineage.io/docs/spec/object-model> |
| S21 | PostgreSQL, *DECLARE* | <https://www.postgresql.org/docs/current/sql-declare.html> |
| S22 | psycopg 3, *Cursor types* | <https://www.psycopg.org/psycopg3/docs/advanced/cursors.html> |
| S23 | PostgreSQL, *COPY* | <https://www.postgresql.org/docs/current/sql-copy.html> |
| S24 | Apache Parquet, *File Format* | <https://parquet.apache.org/docs/file-format/> |
| S25 | pytest, *About fixtures* | <https://docs.pytest.org/en/stable/explanation/fixtures.html> |
| S26 | Hypothesis | <https://hypothesis.readthedocs.io/en/latest/> |

## SQL and PostgreSQL

| ID | Source | URL |
| --- | --- | --- |
| S31 | PostgreSQL 17, Subquery Expressions (`NOT IN`/`EXISTS`) | <https://www.postgresql.org/docs/17/functions-subquery.html> |
| S32 | PostgreSQL 17, Constraints | <https://www.postgresql.org/docs/17/ddl-constraints.html> |
| S33 | Celko, *SQL for Smarties*, 5th ed. | <https://shop.elsevier.com/books/joe-celkos-sql-for-smarties/celko/978-0-12-800761-7> |
| S34 | Celko, *SQL for Smarties*, 4th ed. TOC | <https://booksite.elsevier.com/samplechapters/9780123820228/01~Front_Matter.pdf> |
| S35 | Celko, "SQL and the Snare of Three-Valued Logic" | <https://www.red-gate.com/simple-talk/databases/sql-server/learn/sql-and-the-snare-of-three-valued-logic> |
| S36 | Libkin & Peterfreund, "SQL Nulls and Two-Valued Logic" | <https://arxiv.org/abs/2012.13198> |
| S37 | PostgreSQL 17, SELECT | <https://www.postgresql.org/docs/17/sql-select.html> |
| S38 | PostgreSQL 17, WITH Queries | <https://www.postgresql.org/docs/17/queries-with.html> |
| S39 | PostgreSQL 17, Window Functions | <https://www.postgresql.org/docs/17/tutorial-window.html> |
| S40 | PostgreSQL 17, Table Expressions | <https://www.postgresql.org/docs/17/queries-table-expressions.html> |
| S41 | PostgreSQL 17, Value Expressions | <https://www.postgresql.org/docs/17/sql-expressions.html> |
| S42 | PostgreSQL 17, Unsupported Features | <https://www.postgresql.org/docs/17/unsupported-features-sql-standard.html> |
| S43 | Brass & Goldberg, "Semantic Errors in SQL Queries" | <https://doi.org/10.1016/j.jss.2005.06.028> |

## Pragmatic Programmer

| ID | Source | URL |
| --- | --- | --- |
| P1 | PragProg, *Pragmatic Programmer Tips* | <https://pragprog.com/tips/> |
| P2 | Thomas & Hunt, Topic 9: DRY (sample) | <https://media.pragprog.com/titles/tpp20/dry.pdf> |
| P3 | Thomas & Hunt, Preface to the Second Edition | <https://media.pragprog.com/titles/tpp20/preface2.pdf> |
| P4 | Hunt & Thomas, 1999 sample pages | <https://ptgmedia.pearsoncmg.com/images/9780201616224/samplepages/020161622X.pdf> |
| P5 | Venners, "Tracer Bullets and Prototypes" | <https://www.artima.com/articles/tracer-bullets-and-prototypes> |
| P6 | Venners, "Don't Live with Broken Windows" | <https://www.artima.com/articles/dont-live-with-broken-windows> |
| P7 | Venners, "Good Enough Software" | <https://www.artima.com/articles/good-enough-software> |

## Repo evidence

| ID | Source |
| --- | --- |
| S27 | `src/scripts/etl/README.md` |
| S28 | `src/scripts/etl/transform/README.md` |
| S29 | `AGENTS.md`, `tasks/hypothesis_testing/README.md` |
| S30 | `src/scripts/etl/extract/verify_ingestion.py` |

## Evidence quality

- S1–S4, S8, S10–S14: fetched and read as HTML/PDF.
- S5, S3: DOI metadata only.
- S6–S7, S9: abstract/search metadata only.
- S15–S26: recorded by the data-research child; not all URLs re-fetched by the lead.
- S31–S43: PostgreSQL 17 docs and Celko sources; the book body was not read, only publisher TOCs and Celko articles.
- P1–P7: PragProg tips and samples; the full 2019 text was paywalled.
- Full caveats: `research/software-design-foundations.provenance.md` and `research/sql-pragmatic-craft.provenance.md`.
