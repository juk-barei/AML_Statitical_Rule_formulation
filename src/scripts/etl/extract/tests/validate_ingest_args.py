"""Fast checks for the ETL CLI argument helpers."""
import contextlib
import io

from src.scripts.etl.extract.main import (
    ShardTask,
    build_batch_query,
    parse_args,
    parse_row_limits,
    validate_schema_name,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


check(parse_row_limits("") == {}, "empty row limits")
check(
    parse_row_limits("accounts=1000,transactions=5") == {
        "accounts": 1000,
        "transactions": 5,
    },
    "table row limits",
)
check(parse_row_limits("all=10") == {"all": 10}, "fallback row limit")
check(validate_schema_name("licit_2026") == "licit_2026", "valid schema")
def rejects_schema(value: str) -> bool:
    try:
        validate_schema_name(value)
    except ValueError:
        return True
    return False


for bad in ["bad-name", "1schema", "schema;drop"]:
    check(rejects_schema(bad), f"schema should fail: {bad}")

default_args = parse_args([])
check(default_args.source == "online_db", "online_db source default")
check(default_args.pos_db_type is None, "pos db type has no default")

online_args = parse_args(
    [
        "--source",
        "online_db",
        "--pos-db-type",
        "licit",
        "--pos-workers",
        "3",
        "--pos-shards-per-table",
        "2",
        "--pos-source-schema",
        "public",
    ]
)
check(online_args.source == "online_db", "online source")
check(online_args.pos_db_type == "licit", "online db type")
check(online_args.pos_workers == 3, "online workers")
check(online_args.pos_shards_per_table == 2, "online shards")

parquet_args = parse_args(
    [
        "--source",
        "parquet",
        "--parq-source-path",
        "/absolute/snapshot",
        "--parq-skip-hash",
        "--schema",
        "illicit",
    ]
)
check(parquet_args.source == "parquet", "parquet source")
check(
    parquet_args.parq_source_path == "/absolute/snapshot",
    "parquet path",
)
check(parquet_args.parq_skip_hash is True, "parquet hash switch")
check(parquet_args.schema == "illicit", "parquet target schema")


def rejects_cli(argv: list[str]) -> bool:
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            parse_args(argv)
    except SystemExit:
        return True
    return False


check(rejects_cli(["--source", "illicit"]), "source must be online_db/parquet")
check(
    rejects_cli(["--source", "parquet", "--source-path", "/old/flag"]),
    "old source-path flag must fail",
)

keyset_task = ShardTask(
    run_id="r",
    table_name="transactions",
    target_name="transactions",
    shard_index=0,
    shard_count=5,
    where_sql='WHERE "tx_hash" IS NOT NULL',
    where_params={},
    source_rows=1,
    columns=("tx_hash",),
    order_columns=("tx_hash",),
    batch_size=10,
    keyset=True,
)
first_query = build_batch_query(keyset_task, "public")
check("OFFSET" in first_query, "first keyset batch must use OFFSET 0")
next_query = build_batch_query(keyset_task, "public", last_key="abc")
check("OFFSET" not in next_query, "keyset batch must not use OFFSET")
check('"tx_hash" > :last_key' in next_query, "keyset batch must advance the key")
check(
    "AND" in next_query,
    "keyset where clause must be combined with the shard filter",
)
print("ETL argument checks passed")
