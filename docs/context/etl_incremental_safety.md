# ETL incremental safety

Current behavior in `src/scripts/ETL.py`:

- `create_target_tables` truncates a matching target table; if columns differ, it drops and recreates.
- `--resume` skips completed shards. It does **not** discover new source rows from an earlier run.
- A new run replaces the target table; it does not append.

**Rule:** after the online DB grows, start a **new run** (no `--resume`) to refresh. Use `--resume` only to finish an interrupted shard set.

Use `--source illicit|licit` and `--schema` to keep the two sources apart. `--row-limits` caps rows per table. `--source-schema` selects the online schema. The local PostgreSQL must be running before any write test; it was down on 2026-11-20.
