"""Read-only PostgreSQL benchmarks for representative local queries.

Every query runs as ``EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)``; the script
writes one row per run to ``query_benchmarks.csv`` and the raw plan to
``query_plans/<query>.json``. Query results are never exported.

    python -m src.scripts.etl.profile.benchmark_queries --schema licit \
      --queries accounts_count --limit 1000
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, bindparam, text

from src.scripts.config import PROFILING_OUTPUT_DIR
from src.scripts.etl.ingest import get_local_engine, validate_schema_name
from src.scripts.etl.profile.schema import utc_snapshot_id


@dataclass(frozen=True)
class BenchmarkQuery:
    """A named, schema-qualified read-only query and its source tables."""

    name: str
    sql: str
    relations: tuple[str, ...]


# {limit} is an empty string or ``LIMIT n``; it bounds the driving scan so a
# smoke run does not execute a full-table benchmark by accident.
QUERIES: tuple[BenchmarkQuery, ...] = (
    BenchmarkQuery(
        name="accounts_count",
        sql="""
        SELECT count(*) AS n
        FROM (SELECT 1 FROM {schema}.accounts {limit}) AS sampled
        """,
        relations=("accounts",),
    ),
    BenchmarkQuery(
        name="transactions_count",
        sql="""
        SELECT count(*) AS n
        FROM (SELECT 1 FROM {schema}.transactions {limit}) AS sampled
        """,
        relations=("transactions",),
    ),
    BenchmarkQuery(
        name="blacklist_anti_join",
        sql="""
        SELECT count(*) AS n
        FROM (SELECT address FROM {schema}.accounts {limit}) AS a
        WHERE NOT EXISTS (
            SELECT 1
            FROM {schema}.blacklisted_wallets AS b
            WHERE b.wallet_address = a.address
        )
        """,
        relations=("accounts", "blacklisted_wallets"),
    ),
    BenchmarkQuery(
        name="hop_min_per_wallet",
        sql="""
        SELECT wallet_address, min(hop_level) AS min_hop
        FROM (SELECT wallet_address, hop_level FROM {schema}.wallet_hops {limit}) AS h
        GROUP BY wallet_address
        """,
        relations=("wallet_hops",),
    ),
    BenchmarkQuery(
        name="token_aggregate",
        sql="""
        SELECT token_symbol, count(*) AS tx_count, sum(amount) AS volume
        FROM (SELECT token_symbol, amount FROM {schema}.transactions {limit}) AS t
        GROUP BY token_symbol
        """,
        relations=("transactions",),
    ),
    BenchmarkQuery(
        name="cohort_priority_join",
        sql="""
        SELECT
            CASE
                WHEN b.wallet_address IS NOT NULL THEN 'illicit'
                WHEN h.min_hop BETWEEN 1 AND 5 THEN 'suspicious'
                ELSE 'unlabeled'
            END AS wallet_class,
            count(*) AS n
        FROM (SELECT address FROM {schema}.accounts {limit}) AS a
        LEFT JOIN (
            SELECT wallet_address, min(hop_level) AS min_hop
            FROM {schema}.wallet_hops
            GROUP BY wallet_address
        ) AS h ON h.wallet_address = a.address
        LEFT JOIN {schema}.blacklisted_wallets AS b
            ON b.wallet_address = a.address
        GROUP BY 1
        """,
        relations=("accounts", "wallet_hops", "blacklisted_wallets"),
    ),
    BenchmarkQuery(
        name="h2_lifetime_aggregate",
        sql="""
        WITH events AS (
            (SELECT from_address AS wallet_address, block_timestamp
             FROM {schema}.transactions
             WHERE from_address IS NOT NULL
             {limit})
            UNION ALL
            (SELECT to_address AS wallet_address, block_timestamp
             FROM {schema}.transactions
             WHERE to_address IS NOT NULL
             {limit})
        )
        SELECT
            wallet_address,
            count(*) AS event_count,
            extract(epoch FROM (max(block_timestamp) - min(block_timestamp)))
                / 86400.0 AS tx_lifetime_days
        FROM events
        GROUP BY wallet_address
        HAVING count(*) >= 2
        """,
        relations=("transactions",),
    ),
    BenchmarkQuery(
        name="h4_jaccard_aggregate",
        sql="""
        WITH funders AS (
            SELECT to_address AS wallet_address, from_address AS counterparty
            FROM (SELECT token_symbol, from_address, to_address
                  FROM {schema}.transactions {limit}) AS tx
            WHERE token_symbol = 'TRX'
              AND from_address IS NOT NULL
              AND to_address IS NOT NULL
            GROUP BY 1, 2
        ),
        recipients AS (
            SELECT from_address AS wallet_address, to_address AS counterparty
            FROM (SELECT token_symbol, from_address, to_address
                  FROM {schema}.transactions {limit}) AS tx
            WHERE token_symbol = 'USDT'
              AND from_address IS NOT NULL
              AND to_address IS NOT NULL
            GROUP BY 1, 2
        )
        SELECT
            COALESCE(f.wallet_address, r.wallet_address) AS wallet_address,
            count(*) FILTER (
                WHERE f.counterparty IS NOT NULL AND r.counterparty IS NOT NULL
            ) AS intersection_count,
            count(*) AS union_count
        FROM funders AS f
        FULL OUTER JOIN recipients AS r
            ON r.wallet_address = f.wallet_address
           AND r.counterparty = f.counterparty
        GROUP BY 1
        """,
        relations=("transactions",),
    ),
    BenchmarkQuery(
        name="h6_cv_aggregate",
        sql="""
        WITH events AS (
            SELECT from_address AS wallet_address, block_timestamp, block_number
            FROM (SELECT from_address, block_timestamp, block_number
                  FROM {schema}.transactions {limit}) AS tx
            WHERE from_address IS NOT NULL
            UNION ALL
            SELECT to_address AS wallet_address, block_timestamp, block_number
            FROM (SELECT to_address, block_timestamp, block_number
                  FROM {schema}.transactions {limit}) AS tx
            WHERE to_address IS NOT NULL
        ),
        gaps AS (
            SELECT
                wallet_address,
                extract(epoch FROM (
                    block_timestamp - lag(block_timestamp) OVER (
                        PARTITION BY wallet_address
                        ORDER BY block_timestamp, block_number
                    )
                )) AS gap_seconds
            FROM events
        )
        SELECT
            wallet_address,
            count(*) AS event_count,
            stddev_samp(gap_seconds) / nullif(avg(gap_seconds), 0) AS cv_delta_t
        FROM gaps
        WHERE gap_seconds IS NOT NULL
        GROUP BY wallet_address
        HAVING count(*) >= 4
        """,
        relations=("transactions",),
    ),
)

QUERIES_BY_NAME = {query.name: query for query in QUERIES}

BENCHMARK_FIELDS = (
    "query",
    "schema",
    "sql_hash",
    "repeat_index",
    "planning_ms",
    "execution_ms",
    "total_ms",
    "rows_returned",
    "shared_hit_blocks",
    "shared_read_blocks",
    "temp_read_blocks",
    "temp_written_blocks",
    "relation_sizes_json",
    "plan_path",
    "snapshot_id",
)


@dataclass(frozen=True)
class PlanStats:
    """The fields of an EXPLAIN JSON payload used for one benchmark row."""

    planning_ms: float | None
    execution_ms: float | None
    total_ms: float | None
    rows_returned: int
    shared_hit_blocks: int
    shared_read_blocks: int
    temp_read_blocks: int
    temp_written_blocks: int


def _as_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _as_int(value: Any) -> int:
    return 0 if value is None else int(value)


def _round_ms(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def parse_explain(payload: Any) -> PlanStats:
    """Parse ``EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`` output.

    psycopg returns the JSON column already decoded as a list; a JSON string is
    accepted for fixtures and other drivers.
    """
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, list):
        if not payload:
            raise ValueError("EXPLAIN payload is empty")
        root = payload[0]
    elif isinstance(payload, dict) and "Plan" in payload:
        root = payload
    else:
        raise ValueError("EXPLAIN payload has no Plan object")

    plan = root.get("Plan") or {}
    planning_ms = _as_float(root.get("Planning Time"))
    execution_ms = _as_float(root.get("Execution Time"))
    total_ms = (
        planning_ms + execution_ms
        if planning_ms is not None and execution_ms is not None
        else None
    )
    return PlanStats(
        planning_ms=planning_ms,
        execution_ms=execution_ms,
        total_ms=total_ms,
        rows_returned=_as_int(plan.get("Actual Rows")),
        shared_hit_blocks=_as_int(plan.get("Shared Hit Blocks")),
        shared_read_blocks=_as_int(plan.get("Shared Read Blocks")),
        temp_read_blocks=_as_int(plan.get("Temp Read Blocks")),
        temp_written_blocks=_as_int(plan.get("Temp Written Blocks")),
    )


def select_queries(spec: str) -> tuple[BenchmarkQuery, ...]:
    """Resolve ``all`` or a comma-separated query list."""
    if spec.strip() == "all":
        return QUERIES
    names = [name.strip() for name in spec.split(",") if name.strip()]
    if not names:
        raise ValueError("--queries must be 'all' or a comma-separated list")
    unknown = sorted(set(names) - set(QUERIES_BY_NAME))
    if unknown:
        raise ValueError(
            f"unknown queries: {', '.join(unknown)}; "
            f"available: {', '.join(QUERIES_BY_NAME)}"
        )
    return tuple(QUERIES_BY_NAME[name] for name in dict.fromkeys(names))


def render_query(name: str, schema: str, limit: int | None = None) -> str:
    """Render one registry query with a validated schema and optional row bound."""
    query = QUERIES_BY_NAME.get(name)
    if query is None:
        raise ValueError(f"unknown query: {name}")
    schema = validate_schema_name(schema)
    if limit is not None:
        if limit <= 0:
            raise ValueError("--limit must be positive")
        limit_clause = f"LIMIT {int(limit)}"
    else:
        limit_clause = ""
    return " ".join(query.sql.format(schema=schema, limit=limit_clause).split())


def sql_hash(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def explain_json(connection: Connection, sql: str) -> Any:
    """Run one read-only EXPLAIN and return its JSON payload."""
    # pi-lens-ignore: python-sql-injection -- fixed registry SQL, schema and limit validated
    statement = text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}")
    # pi-lens-ignore: python-sql-injection -- fixed registry SQL, schema and limit validated
    return connection.execute(statement).scalar_one()


def relation_sizes(
    connection: Connection,
    schema: str,
    tables: tuple[str, ...],
) -> dict[str, dict[str, int]]:
    """Return total, index, and heap sizes for the requested tables."""
    schema = validate_schema_name(schema)
    names = tuple(validate_schema_name(table) for table in tables)
    if not names:
        return {}
    query = text(
        """
        SELECT c.relname AS table_name,
               pg_total_relation_size(c.oid) AS total_bytes,
               pg_indexes_size(c.oid) AS index_bytes,
               pg_relation_size(c.oid) AS relation_bytes
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = :schema
          AND c.relname IN :tables
        """
    ).bindparams(bindparam("tables", expanding=True))
    # pi-lens-ignore: python-sql-injection -- static SQL; schema and tables validated
    rows = connection.execute(query, {"schema": schema, "tables": names}).mappings()
    return {
        str(row["table_name"]): {
            "total_bytes": int(row["total_bytes"]),
            "index_bytes": int(row["index_bytes"]),
            "relation_bytes": int(row["relation_bytes"]),
        }
        for row in rows
    }


def benchmark_row(
    *,
    query: BenchmarkQuery,
    schema: str,
    sql: str,
    stats: PlanStats,
    repeat_index: int,
    plan_path: str,
    snapshot_id: str,
    sizes: dict[str, dict[str, int]],
) -> dict[str, Any]:
    """Build one CSV row from parsed plan output."""
    return {
        "query": query.name,
        "schema": schema,
        "sql_hash": sql_hash(sql),
        "repeat_index": repeat_index,
        "planning_ms": _round_ms(stats.planning_ms),
        "execution_ms": _round_ms(stats.execution_ms),
        "total_ms": _round_ms(stats.total_ms),
        "rows_returned": stats.rows_returned,
        "shared_hit_blocks": stats.shared_hit_blocks,
        "shared_read_blocks": stats.shared_read_blocks,
        "temp_read_blocks": stats.temp_read_blocks,
        "temp_written_blocks": stats.temp_written_blocks,
        "relation_sizes_json": json.dumps(sizes, sort_keys=True),
        "plan_path": plan_path,
        "snapshot_id": snapshot_id,
    }


def write_benchmarks(rows: list[dict[str, Any]], output_dir: Path) -> Path:
    """Write benchmark rows to ``query_benchmarks.csv``."""
    path = output_dir / "query_benchmarks.csv"
    output_dir.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(BENCHMARK_FIELDS)
        for row in rows:
            writer.writerow([row[field] for field in BENCHMARK_FIELDS])
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--queries", default="all")
    parser.add_argument("--output-dir", default=str(PROFILING_OUTPUT_DIR))
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--snapshot-id", default="")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    schemas = [
        validate_schema_name(item.strip())
        for item in args.schema.split(",")
        if item.strip()
    ]
    if not schemas:
        raise ValueError("at least one schema is required")
    queries = select_queries(args.queries)
    snapshot_id = args.snapshot_id or utc_snapshot_id()
    output_dir = Path(args.output_dir)

    if args.dry_run:
        for schema in schemas:
            for query in queries:
                print(f"[{schema}] {query.name}")
                print(render_query(query.name, schema, args.limit))
        print(f"would write {output_dir / 'query_benchmarks.csv'}")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    plans_dir = output_dir / "query_plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    engine = get_local_engine()
    try:
        with engine.connect() as connection:
            # pi-lens-ignore: python-sql-injection -- static statement
            connection.execute(text("SET TRANSACTION READ ONLY"))
            for schema in schemas:
                for query in queries:
                    sql = render_query(query.name, schema, args.limit)
                    sizes = relation_sizes(connection, schema, query.relations)
                    stats: PlanStats | None = None
                    for repeat_index in range(1, args.repeat + 1):
                        payload = explain_json(connection, sql)
                        stats = parse_explain(payload)
                        plan_path = f"query_plans/{schema}.{query.name}.json"
                        (output_dir / plan_path).write_text(
                            json.dumps(payload, indent=2),
                            encoding="utf-8",
                        )
                        rows.append(
                            benchmark_row(
                                query=query,
                                schema=schema,
                                sql=sql,
                                stats=stats,
                                repeat_index=repeat_index,
                                plan_path=plan_path,
                                snapshot_id=snapshot_id,
                                sizes=sizes,
                            )
                        )
                    if stats is not None:
                        print(
                            f"[{schema}] {query.name}: "
                            f"planning={stats.planning_ms} ms "
                            f"execution={stats.execution_ms} ms "
                            f"rows={stats.rows_returned}"
                        )
    finally:
        engine.dispose()

    path = write_benchmarks(rows, output_dir)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
