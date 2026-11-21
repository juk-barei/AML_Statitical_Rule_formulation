"""Fast checks for the ETL CLI argument helpers."""
from src.scripts.ETL import parse_row_limits, validate_schema_name


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
print("ETL argument checks passed")
