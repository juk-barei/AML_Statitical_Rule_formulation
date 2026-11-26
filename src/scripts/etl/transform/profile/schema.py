"""Shared profile contracts: dataset refs, profile rows, stage manifests."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_snapshot_id() -> str:
    """Return a compact UTC snapshot id for one profile run."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class DatasetRef:
    """A read-only dataset at one grain and snapshot."""

    name: str
    source: str
    table: str
    grain: str
    snapshot_id: str
    schema: str | None = None
    path: str | None = None
    is_partial: bool = False

    def __post_init__(self) -> None:
        if not self.name or not self.table or not self.grain:
            raise ValueError("name, table, and grain are required")
        if self.source not in {"postgres", "parquet", "csv"}:
            raise ValueError(f"unsupported source: {self.source}")


@dataclass(frozen=True)
class TableCoverage:
    """Per-table ingestion provenance, not a schema-wide status."""

    schema: str
    table: str
    run_id: str | None
    source_rows: int
    ingested_rows: int
    local_rows: int | None
    shard_count: int
    completed_shards: int
    failed_shards: int
    status: str
    is_partial: bool


@dataclass(frozen=True)
class ProfileRecord:
    """One metric for one table/column/wallet_class at one stage."""

    dataset: str
    stage: str
    table: str
    metric: str
    value: float | int | None
    denominator: int | None
    snapshot_id: str
    column: str | None = None
    wallet_class: str | None = None
    is_partial: bool = False
    method: str = "exact"
    note: str = ""

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        return (
            self.dataset,
            self.table,
            self.column or "",
            self.metric,
            self.wallet_class or "",
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "stage": self.stage,
            "table": self.table,
            "column": self.column,
            "metric": self.metric,
            "value": self.value,
            "denominator": self.denominator,
            "wallet_class": self.wallet_class,
            "snapshot_id": self.snapshot_id,
            "is_partial": self.is_partial,
            "method": self.method,
            "note": self.note,
        }


@dataclass(frozen=True)
class ComparisonRecord:
    """Before/after pair for one ProfileRecord key across stages."""

    key: tuple[str, str, str, str, str]
    stage_before: str
    stage_after: str
    value_before: float | int | None
    value_after: float | int | None
    delta: float | int | None
    delta_pct: float | None
    n_before: int | None
    n_after: int | None
    note: str = ""

    @classmethod
    def from_records(
        cls,
        before: ProfileRecord,
        after: ProfileRecord,
        *,
        note: str = "",
    ) -> ComparisonRecord:
        if before.key != after.key:
            raise ValueError("cannot compare different profile keys")
        if before.snapshot_id != after.snapshot_id:
            raise ValueError("cannot compare different snapshots")
        delta: float | int | None
        delta_pct: float | None
        if before.value is None or after.value is None:
            delta = None
            delta_pct = None
        else:
            delta = after.value - before.value
            delta_pct = (delta / before.value * 100.0) if before.value else None
        return cls(
            key=before.key,
            stage_before=before.stage,
            stage_after=after.stage,
            value_before=before.value,
            value_after=after.value,
            delta=delta,
            delta_pct=delta_pct,
            n_before=before.denominator,
            n_after=after.denominator,
            note=note,
        )

    def as_dict(self) -> dict[str, Any]:
        dataset, table, column, metric, wallet_class = self.key
        return {
            "dataset": dataset,
            "stage_before": self.stage_before,
            "stage_after": self.stage_after,
            "table": table,
            "column": column or None,
            "metric": metric,
            "wallet_class": wallet_class or None,
            "value_before": self.value_before,
            "value_after": self.value_after,
            "delta": self.delta,
            "delta_pct": self.delta_pct,
            "n_before": self.n_before,
            "n_after": self.n_after,
            "note": self.note,
        }


@dataclass(frozen=True)
class StageManifest:
    """What one transform stage read, wrote, and filtered."""

    stage: str
    input_table: str
    output_table: str
    rows_in: int
    rows_out: int
    snapshot_id: str
    filters: tuple[str, ...] = field(default_factory=tuple)
    sql_hash: str = ""
    is_partial: bool = False

    @property
    def rows_dropped(self) -> int:
        return self.rows_in - self.rows_out

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "input_table": self.input_table,
            "output_table": self.output_table,
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "rows_dropped": self.rows_dropped,
            "filters": list(self.filters),
            "sql_hash": self.sql_hash,
            "snapshot_id": self.snapshot_id,
            "is_partial": self.is_partial,
        }
