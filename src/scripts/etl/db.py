"""Shared database connection, environment, and schema-validation helpers for ETL.

All ETL stages (``extract``, ``transform``, ``load``) import read-only connection
and validation helpers from here so no stage depends on ``extract/main.py``.
"""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.scripts.config import ROOT

ENV_PATH = ROOT / "src" / ".env"
SOURCE_CONNECT_TIMEOUT_SECONDS = 60
LOCAL_CONNECT_TIMEOUT_SECONDS = 10


def safe_error_message(error: BaseException) -> str:
    """Return an error string with connection strings redacted."""
    message = f"{type(error).__name__}: {error}"
    message = re.sub(
        r"postgresql(?:\+\w+)?://[^\s]+",
        "postgresql://<redacted>",
        message,
    )
    message = re.sub(r"(password=)[^\s&]+", r"\1<redacted>", message)
    return message[:2000]


def load_environment() -> None:
    """Load ``src/.env`` if it exists; never print its contents."""
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=False)


def get_illicit_online_db_link() -> str:
    """Return ``ILLICIT_ONLINE_DATABASE_LINK`` from the environment."""
    link = os.getenv("ILLICIT_ONLINE_DATABASE_LINK")
    if not link:
        raise RuntimeError(
            "ILLICIT_ONLINE_DATABASE_LINK is not set. Add it to src/.env before running ETL."
        )
    return link


def get_licit_online_db_link() -> str:
    """Return ``LICIT_ONLINE_DATABASE_LINK`` from the environment."""
    link = os.getenv("LICIT_ONLINE_DATABASE_LINK")
    if not link:
        raise RuntimeError(
            "LICIT_ONLINE_DATABASE_LINK is not set. Add it to src/.env before running ETL."
        )
    return link


def get_source_link(source: str) -> str:
    """Return the online link for the requested source."""
    if source == "illicit":
        return get_illicit_online_db_link()
    if source == "licit":
        return get_licit_online_db_link()
    raise ValueError(f"Unknown source: {source}. Use 'illicit' or 'licit'.")


def get_local_db_link() -> str:
    """Build the SQLAlchemy URL for the local PostgreSQL mirror from ``src/.env``."""
    name = os.getenv("LOCAL_DB_NAME")
    user = os.getenv("LOCAL_DB_USER")
    host = os.getenv("LOCAL_DB_HOST")
    password = os.getenv("LOCAL_DB_PASS")
    missing = [
        variable_name
        for variable_name, value in {
            "LOCAL_DB_NAME": name,
            "LOCAL_DB_USER": user,
            "LOCAL_DB_HOST": host,
            "LOCAL_DB_PASS": password,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Local database variables are incomplete: " + ", ".join(missing)
        )
    assert name is not None and user is not None
    assert host is not None and password is not None
    return (
        f"postgresql+psycopg://{quote(user, safe='')}:{quote(password, safe='')}"
        f"@{host}/{name}"
    )


def force_psycopg_driver(link: str) -> str:
    """Use psycopg 3 when the environment gives a plain postgresql:// URL."""
    if link.startswith("postgresql://"):
        return "postgresql+psycopg://" + link[len("postgresql://") :]
    return link


def validate_schema_name(schema: str) -> str:
    """Return a safe PostgreSQL schema name."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
        raise ValueError(
            f"Invalid schema name: {schema!r}. Use letters, digits, and underscores."
        )
    return schema


def create_database_engine(
    link: str,
    *,
    is_source: bool,
    pool_size: int = 1,
    schema: str | None = None,
) -> Engine:
    """Create a SQLAlchemy engine for either an online source or the local mirror."""
    connect_timeout = (
        SOURCE_CONNECT_TIMEOUT_SECONDS if is_source else LOCAL_CONNECT_TIMEOUT_SECONDS
    )
    connect_args: dict[str, Any] = {"connect_timeout": connect_timeout}
    if schema:
        schema = validate_schema_name(schema)
        # Put the requested schema first; public is the fallback for extensions.
        connect_args["options"] = f"-csearch_path={schema},public"
    else:
        schema = "public"
    return create_engine(
        force_psycopg_driver(link),
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=0,
        connect_args=connect_args,
        # Statements qualify their tables with this schema; search_path only
        # remains as the fallback for extension lookups.
        execution_options={"capstone_schema": schema},
    )


def get_local_engine() -> Engine:
    """Create an engine for the local mirror (notebook-friendly)."""
    load_environment()
    return create_database_engine(get_local_db_link(), is_source=False)
