"""Read-only data-quality checks for the local mirror.

Every check returns a failed-row count and its denominator. Checks are additive;
a missing table or column is recorded as skipped, not treated as zero failures.

    python -m src.scripts.etl.profile.profile_quality --schemas illicit,licit
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import Table, exists, func, select

from src.scripts.config import PROFILING_OUTPUT_DIR
from src.scripts.etl.extract.main import get_local_engine, validate_schema_name
from src.scripts.etl.transform.profile.adapters import PostgresDataset
from src.scripts.etl.transform.profile.schema import utc_snapshot_id

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
CHAIN_START = datetime(2018, 1, 1, tzinfo=UTC)


def _record(
    dataset: PostgresDataset,
    table: str,
    check: str,
    failed_rows: int | None,
    denominator: int | None,
    *,
    severity: str,
    status: str = "checked",
    note: str = "",
) -> dict[str, Any]:
    return {
        "schema": dataset.schema,
        "table": table,
        "check": check,
        "failed_rows": failed_rows,
        "denominator": denominator,
        "failed_share": (failed_rows / denominator) if failed_rows is not None and denominator else None,
        "severity": severity,
        "status": status,
        "note": note,
        "snapshot_at": dataset.snapshot_id,
        "is_partial": dataset.is_partial,
    }


def _scalar(connection, query) -> int:
    # pi-lens-ignore: python-sql-injection -- SQLAlchemy Core; no string interpolation
    return int(connection.execute(query).scalar_one())


def _table(dataset: PostgresDataset, name: str) -> Table | None:
    if not dataset.has_table(name):
        return None
    return dataset.table(name)


def _total(connection, table: Table) -> int:
    return _scalar(connection, select(func.count()).select_from(table))


def _check_duplicate_key(
    dataset: PostgresDataset,
    connection,
    table: Table,
    key: str,
    check: str,
) -> dict[str, Any]:
    total = _total(connection, table)
    distinct = _scalar(connection, select(func.count(func.distinct(table.c[key]))))
    return _record(dataset, table.name, check, total - distinct, total, severity="error")


def _check_null_key(
    dataset: PostgresDataset,
    connection,
    table: Table,
    key: str,
    check: str,
) -> dict[str, Any]:
    total = _total(connection, table)
    non_null = _scalar(connection, select(func.count(table.c[key])))
    return _record(dataset, table.name, check, total - non_null, total, severity="error")


def _check_orphans(
    dataset: PostgresDataset,
    connection,
    child: Table,
    parent: Table,
    child_key: str,
    parent_key: str,
    check: str,
) -> dict[str, Any]:
    denominator = _scalar(
        connection,
        select(func.count()).select_from(child).where(child.c[child_key].is_not(None)),
    )
    missing = exists(
        select(1).select_from(parent).where(parent.c[parent_key] == child.c[child_key])
    )
    failed = _scalar(
        connection,
        select(func.count())
        .select_from(child)
        .where(child.c[child_key].is_not(None), ~missing),
    )
    return _record(dataset, child.name, check, failed, denominator, severity="error")


def _check_non_positive(
    dataset: PostgresDataset,
    connection,
    table: Table,
    column: str,
    check: str,
) -> dict[str, Any]:
    denominator = _scalar(
        connection,
        select(func.count()).select_from(table).where(table.c[column].is_not(None)),
    )
    failed = _scalar(
        connection,
        select(func.count()).select_from(table).where(table.c[column] <= 0),
    )
    return _record(dataset, table.name, check, failed, denominator, severity="error")


def _check_null_column(
    dataset: PostgresDataset,
    connection,
    table: Table,
    column: str,
    check: str,
) -> dict[str, Any]:
    total = _total(connection, table)
    non_null = _scalar(connection, select(func.count(table.c[column])))
    return _record(dataset, table.name, check, total - non_null, total, severity="error")


def _check_usdt_contract(
    dataset: PostgresDataset,
    connection,
    table: Table,
) -> dict[str, Any]:
    usdt_filter = table.c.token_symbol == "USDT"
    denominator = _scalar(
        connection, select(func.count()).select_from(table).where(usdt_filter)
    )
    mismatch = usdt_filter & (
        table.c.contract_address.is_(None) | (table.c.contract_address != USDT_CONTRACT)
    )
    failed = _scalar(
        connection, select(func.count()).select_from(table).where(mismatch)
    )
    return _record(dataset, table.name, "usdt_contract_mismatch", failed, denominator, severity="error")


def _check_time_range(
    dataset: PostgresDataset,
    connection,
    table: Table,
    column: str,
    check: str,
    predicate,
    severity: str,
) -> dict[str, Any]:
    denominator = _scalar(
        connection,
        select(func.count()).select_from(table).where(table.c[column].is_not(None)),
    )
    failed = _scalar(
        connection,
        select(func.count()).select_from(table).where(predicate),
    )
    return _record(dataset, table.name, check, failed, denominator, severity=severity)


def _check_hop_range(
    dataset: PostgresDataset,
    connection,
    table: Table,
) -> dict[str, Any]:
    total = _total(connection, table)
    failed = _scalar(
        connection,
        select(func.count())
        .select_from(table)
        .where((table.c.hop_level < 0) | (table.c.hop_level > 5)),
    )
    return _record(dataset, table.name, "hop_level_outside_0_5", failed, total, severity="error")


def _check_direction(
    dataset: PostgresDataset,
    connection,
    table: Table,
) -> dict[str, Any]:
    total = _total(connection, table)
    failed = _scalar(
        connection,
        select(func.count())
        .select_from(table)
        .where(~table.c.direction.in_(("BACKWARD", "FORWARD"))),
    )
    return _record(dataset, table.name, "unexpected_direction", failed, total, severity="error")


def _check_address_format(
    dataset: PostgresDataset,
    connection,
    table: Table,
    column: str,
) -> dict[str, Any]:
    denominator = _scalar(
        connection,
        select(func.count()).select_from(table).where(table.c[column].is_not(None)),
    )
    failed = _scalar(
        connection,
        select(func.count())
        .select_from(table)
        .where(
            table.c[column].is_not(None),
            (func.length(table.c[column]) != 34) | (~table.c[column].like("T%")),
        ),
    )
    return _record(dataset, table.name, f"{column}_format", failed, denominator, severity="warn")


def _check_blacklist_label(
    dataset: PostgresDataset,
    connection,
    table: Table,
) -> dict[str, Any]:
    total = _total(connection, table)
    failed = _scalar(
        connection,
        select(func.count())
        .select_from(table)
        .where(table.c.label.is_(None) | ~table.c.label.in_((0, 1))),
    )
    return _record(dataset, table.name, "blacklist_label_not_0_1", failed, total, severity="error")


def collect_checks(dataset: PostgresDataset) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    accounts = _table(dataset, "accounts")
    transactions = _table(dataset, "transactions")
    hops = _table(dataset, "wallet_hops")
    blacklist = _table(dataset, "blacklisted_wallets")
    with dataset.engine.connect() as connection:
        if accounts is not None:
            rows.append(_check_duplicate_key(dataset, connection, accounts, "address", "duplicate_accounts"))
            rows.append(_check_null_key(dataset, connection, accounts, "address", "null_account_address"))
            rows.append(_check_address_format(dataset, connection, accounts, "address"))
        else:
            rows.append(_record(dataset, "accounts", "table_present", None, None, severity="info", status="skipped", note="table missing"))

        if transactions is not None:
            rows.append(_check_duplicate_key(dataset, connection, transactions, "tx_hash", "duplicate_tx_hash"))
            rows.append(_check_null_key(dataset, connection, transactions, "tx_hash", "null_tx_hash"))
            rows.append(_check_non_positive(dataset, connection, transactions, "amount", "non_positive_amount"))
            rows.append(_check_null_column(dataset, connection, transactions, "token_symbol", "null_token_symbol"))
            rows.append(_check_usdt_contract(dataset, connection, transactions))
            rows.append(
                _check_time_range(
                    dataset,
                    connection,
                    transactions,
                    "block_timestamp",
                    "future_block_timestamp",
                    transactions.c.block_timestamp > func.now(),
                    "warn",
                )
            )
            rows.append(
                _check_time_range(
                    dataset,
                    connection,
                    transactions,
                    "block_timestamp",
                    "pre_2018_block_timestamp",
                    transactions.c.block_timestamp < CHAIN_START,
                    "warn",
                )
            )
            if accounts is not None:
                rows.append(
                    _check_orphans(
                        dataset,
                        connection,
                        transactions,
                        accounts,
                        "from_address",
                        "address",
                        "orphan_from_address",
                    )
                )
                rows.append(
                    _check_orphans(
                        dataset,
                        connection,
                        transactions,
                        accounts,
                        "to_address",
                        "address",
                        "orphan_to_address",
                    )
                )
        else:
            rows.append(_record(dataset, "transactions", "table_present", None, None, severity="info", status="skipped", note="table missing"))

        if hops is not None:
            rows.append(_check_hop_range(dataset, connection, hops))
            rows.append(_check_direction(dataset, connection, hops))
        else:
            rows.append(_record(dataset, "wallet_hops", "table_present", None, None, severity="info", status="skipped", note="table missing"))

        if blacklist is not None:
            rows.append(_check_blacklist_label(dataset, connection, blacklist))
        else:
            rows.append(_record(dataset, "blacklisted_wallets", "table_present", None, None, severity="info", status="skipped", note="table missing"))
    return rows


def write_checks(rows: list[dict[str, Any]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "local_quality.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schemas", default="illicit,licit")
    parser.add_argument("--output-dir", default=str(PROFILING_OUTPUT_DIR))
    parser.add_argument("--snapshot-id", default="")
    args = parser.parse_args(argv)
    engine = get_local_engine()
    snapshot_id = args.snapshot_id or utc_snapshot_id()
    rows: list[dict[str, Any]] = []
    try:
        for schema in [s.strip() for s in args.schemas.split(",") if s.strip()]:
            dataset = PostgresDataset(
                engine=engine,
                schema=validate_schema_name(schema),
                snapshot_id=snapshot_id,
            )
            schema_rows = collect_checks(dataset)
            rows.extend(schema_rows)
            failed = sum(
                1
                for row in schema_rows
                if row["status"] == "checked" and (row["failed_rows"] or 0) > 0
            )
            print(f"[{schema}] checks={len(schema_rows)} with_failures={failed}")
    finally:
        engine.dispose()
    path = write_checks(rows, Path(args.output_dir))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
