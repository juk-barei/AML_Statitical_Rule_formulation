"""Fast checks for the ETL CLI argument helpers."""
from src.scripts.etl.ingest import (
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

parquet_args = parse_args(
    [
        "--source",
        "parquet",
        "--source-path",
        "/absolute/snapshot",
        "--schema",
        "illicit",
    ]
)
check(parquet_args.source == "parquet", "parquet source")
check(parquet_args.source_path == "/absolute/snapshot", "parquet path")
check(parquet_args.schema == "illicit", "parquet target schema")
check(parquet_args.skip_hash is False, "hash verification defaults on")
check(parse_args([]).source == "illicit", "online source default")

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
