"""Assert-based checks for the query benchmark parser and CSV output."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from src.scripts.etl.extract.main import get_local_engine
from src.scripts.etl.transform.profile.benchmark_queries import (
    BENCHMARK_FIELDS,
    QUERIES,
    PlanStats,
    benchmark_row,
    explain_json,
    parse_explain,
    render_query,
    select_queries,
    write_benchmarks,
)

REQUIRED_QUERIES = {
    "accounts_count",
    "transactions_count",
    "blacklist_anti_join",
    "hop_min_per_wallet",
    "token_aggregate",
    "cohort_priority_join",
    "h2_lifetime_aggregate",
    "h4_jaccard_aggregate",
    "h6_cv_aggregate",
}


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def rejects(callable_object, message: str) -> None:
    try:
        callable_object()
    except ValueError:
        return
    raise AssertionError(message)


def test_parse_explain_payload() -> None:
    payload = [
        {
            "Plan": {
                "Node Type": "Aggregate",
                "Actual Rows": 1.0,
                "Shared Hit Blocks": 12,
                "Shared Read Blocks": 34,
                "Temp Read Blocks": 5,
                "Temp Written Blocks": 6,
            },
            "Planning Time": 0.25,
            "Execution Time": 1.75,
            "Triggers": [],
        }
    ]
    stats = parse_explain(payload)
    check(stats.planning_ms == 0.25, "planning time")
    check(stats.execution_ms == 1.75, "execution time")
    check(stats.total_ms == 2.0, "total time")
    check(stats.rows_returned == 1, "rows returned")
    check(stats.shared_hit_blocks == 12, "shared hit blocks")
    check(stats.shared_read_blocks == 34, "shared read blocks")
    check(stats.temp_read_blocks == 5, "temp read blocks")
    check(stats.temp_written_blocks == 6, "temp written blocks")

    from_string = parse_explain(json.dumps(payload))
    check(from_string == stats, "decoded and string payloads must match")
    rejects(lambda: parse_explain([]), "empty payload must raise")
    rejects(lambda: parse_explain({"Total": 1}), "payload without Plan must raise")


def test_query_registry_and_rendering() -> None:
    names = {query.name for query in QUERIES}
    check(REQUIRED_QUERIES.issubset(names), "registry must contain every required query")
    check(select_queries("all") == QUERIES, "all selects the whole registry")
    check(
        select_queries("accounts_count, token_aggregate,accounts_count")
        == (QUERIES[0], QUERIES[4]),
        "selection trims and deduplicates",
    )
    rejects(lambda: select_queries(""), "empty selection must raise")
    rejects(lambda: select_queries("missing_query"), "unknown query must raise")

    sql = render_query("accounts_count", "licit", 1000)
    check("licit.accounts" in sql, "schema is rendered")
    check("LIMIT 1000" in sql, "limit is rendered")
    check("LIMIT" not in render_query("accounts_count", "licit"), "no default limit")
    rejects(lambda: render_query("accounts_count", "bad-name"), "invalid schema")
    rejects(lambda: render_query("accounts_count", "licit", 0), "non-positive limit")


def test_csv_formatting() -> None:
    query = QUERIES[0]
    sql = render_query(query.name, "licit", 1000)
    stats = PlanStats(
        planning_ms=0.5,
        execution_ms=2.5,
        total_ms=3.0,
        rows_returned=1,
        shared_hit_blocks=7,
        shared_read_blocks=8,
        temp_read_blocks=0,
        temp_written_blocks=9,
    )
    row = benchmark_row(
        query=query,
        schema="licit",
        sql=sql,
        stats=stats,
        repeat_index=1,
        plan_path="query_plans/accounts_count.json",
        snapshot_id="2026-11-23T00:00:00Z",
        sizes={"accounts": {"total_bytes": 100, "index_bytes": 20, "relation_bytes": 80}},
    )
    with TemporaryDirectory() as temp_dir:
        path = write_benchmarks([row], Path(temp_dir))
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            check(tuple(reader.fieldnames or ()) == BENCHMARK_FIELDS, "CSV header")
            rows = list(reader)
        check(len(rows) == 1, "one CSV row")
        check(rows[0]["query"] == "accounts_count", "query column")
        check(rows[0]["total_ms"] == "3.0", "numeric column formatting")
        check(rows[0]["plan_path"] == "query_plans/accounts_count.json", "plan path")
        sizes = json.loads(rows[0]["relation_sizes_json"])
        check(sizes["accounts"]["index_bytes"] == 20, "relation sizes JSON")


def test_explain_smoke() -> None:
    """Run a bounded EXPLAIN against the local mirror; skip if unavailable."""
    try:
        engine = get_local_engine()
    except (RuntimeError, SQLAlchemyError, OSError) as error:
        print(f"explain smoke skipped: {type(error).__name__}")
        return
    try:
        if not inspect(engine).has_table("accounts", schema="licit"):
            print("explain smoke skipped: licit.accounts is not present")
            return
        with engine.connect() as connection:
            payload = explain_json(
                connection,
                "SELECT address FROM licit.accounts LIMIT 1",
            )
        stats = parse_explain(payload)
        planning = stats.planning_ms
        execution = stats.execution_ms
        if planning is None or execution is None:
            raise AssertionError("planning and execution time are recorded")
        check(
            stats.total_ms == planning + execution,
            "total time is planning + execution",
        )
        check(stats.rows_returned == 1, "bounded query returns one row")
    except (SQLAlchemyError, OSError) as error:
        print(f"explain smoke skipped: {type(error).__name__}")
    finally:
        engine.dispose()


test_parse_explain_payload()
test_query_registry_and_rendering()
test_csv_formatting()
test_explain_smoke()
print("benchmark checks passed")
