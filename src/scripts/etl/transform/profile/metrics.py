"""Small, pure-ish metric helpers over SQLAlchemy tables.

The caller owns the connection and the read bound; these helpers only build
aggregate queries. They never materialize rows in pandas.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import Connection, Table, distinct, exists, func, select


def count_rows(connection: Connection, table: Table) -> int:
    return int(
        connection.execute(select(func.count()).select_from(table)).scalar_one()
    )


def count_distinct(connection: Connection, table: Table, column: str) -> int:
    return int(
        connection.execute(
            select(func.count(distinct(table.c[column])))
        ).scalar_one()
    )


def count_non_null(connection: Connection, table: Table, column: str) -> int:
    return int(
        connection.execute(select(func.count(table.c[column]))).scalar_one()
    )


def null_counts(connection: Connection, table: Table, columns: Iterable[str]) -> dict[str, int]:
    names = tuple(columns)
    if not names:
        return {}
    parts = [func.count(table.c[name]).label(name) for name in names]
    row = connection.execute(select(*parts).select_from(table)).mappings().one()
    total = count_rows(connection, table)
    return {name: total - int(row[name]) for name in names}


def distinct_counts(connection: Connection, table: Table, columns: Iterable[str]) -> dict[str, int]:
    names = tuple(columns)
    if not names:
        return {}
    parts = [func.count(distinct(table.c[name])).label(name) for name in names]
    row = connection.execute(select(*parts).select_from(table)).mappings().one()
    return {name: int(row[name]) for name in names}


def min_max(connection: Connection, table: Table, columns: Iterable[str]) -> dict[str, tuple[Any, Any]]:
    names = tuple(columns)
    if not names:
        return {}
    parts: list[Any] = []
    for name in names:
        parts.extend(
            [
                func.min(table.c[name]).label(f"min__{name}"),
                func.max(table.c[name]).label(f"max__{name}"),
            ]
        )
    row = connection.execute(select(*parts).select_from(table)).mappings().one()
    return {name: (row[f"min__{name}"], row[f"max__{name}"]) for name in names}


def group_counts(connection: Connection, table: Table, column: str) -> list[tuple[Any, int]]:
    rows = connection.execute(
        select(table.c[column], func.count().label("n"))
        .group_by(table.c[column])
        .order_by(func.count().desc())
    ).all()
    return [(value, int(count)) for value, count in rows]


def overlap_count(
    connection: Connection,
    left: Table,
    left_column: str,
    right: Table,
    right_column: str,
) -> int:
    """Count distinct left keys that have at least one match in right."""
    right_match = exists(
        select(1).select_from(right).where(right.c[right_column] == left.c[left_column])
    )
    query = select(func.count(distinct(left.c[left_column]))).where(
        left.c[left_column].is_not(None),
        right_match,
    )
    # pi-lens-ignore: python-sql-injection -- SQLAlchemy Core; identifiers are reflected table columns
    return int(connection.execute(query).scalar_one())


def share(part: int, total: int) -> float:
    return (part / total) if total else 0.0
