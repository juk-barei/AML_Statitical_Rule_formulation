"""Stage-aware loader and contract validator for ETL profile CSVs."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.scripts.config import EDA_OUTPUT_DIR, PROFILING_OUTPUT_DIR
from src.scripts.etl.transform.profile.schema import VALID_STAGES, stage_output_dir

VALID_EDA_STAGES: tuple[str, ...] = (*VALID_STAGES, "compare")

PROFILE_FILES: dict[str, str] = {
    "illicit_db_overview": "local_illicit_db_overview.csv",
    "licit_db_overview": "local_licit_db_overview.csv",
    "illicit_coverage": "local_illicit_coverage.csv",
    "licit_coverage": "local_licit_coverage.csv",
    "illicit_columns": "local_illicit_columns.csv",
    "licit_columns": "local_licit_columns.csv",
    "transform_columns": "local_transform_columns.csv",
    "quality": "local_quality.csv",
    "pretransform_cleaning": "local_pretransform_cleaning.csv",
    "cohort_counts": "local_cohort_counts.csv",
    "nflow": "local_nflow.csv",
    "group_overlap": "local_group_overlap.csv",
    "hop_seed": "local_hop_seed.csv",
    "sampling_frame": "local_sampling_frame.csv",
    "wallet_distributions": "local_wallet_distributions.csv",
    "wallet_histograms": "local_wallet_histograms.csv",
    "feature_nflow": "local_feature_nflow.csv",
    "relations": "relations.csv",
    "query_benchmarks": "query_benchmarks.csv",
}


@dataclass(frozen=True)
class ProfileMetadata:
    """Provenance metadata extracted from loaded profile CSVs."""

    stage: str
    snapshot_at: str
    is_partial: bool
    source_dir: Path
    loaded_tables: tuple[str, ...]
    missing_tables: tuple[str, ...]


@dataclass
class ProfileBundle:
    """Loaded compact CSV tables for a single profiling stage."""

    stage: str
    source_dir: Path
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    missing_tables: list[str] = field(default_factory=list)

    def has(self, *names: str) -> bool:
        return all(n in self.tables and not self.tables[n].empty for n in names)

    def get(self, name: str) -> pd.DataFrame:
        if name not in self.tables:
            raise KeyError(
                f"Profile table {name!r} not available in stage={self.stage!r} ({self.source_dir})"
            )
        return self.tables[name]

    def snapshot_for(self, *names: str) -> tuple[str, bool]:
        """Extract snapshot label and partial flag from one or more tables."""
        snaps: list[str] = []
        partial = False
        for name in names:
            df = self.tables.get(name)
            if df is None or df.empty:
                continue
            for col in ("snapshot_at", "snapshot_id"):
                if col in df.columns:
                    vals = [str(v) for v in df[col].dropna().unique() if str(v)]
                    snaps.extend(vals)
                    break
            if "is_partial" in df.columns:
                partial_vals = df["is_partial"].dropna().astype(str).str.lower()
                if (partial_vals == "true").any():
                    # Ignore known stale auxiliary crawl state when evaluating core tables.
                    if "table" in df.columns:
                        core = df[df["table"] != "pipeline_crawl_state"]
                        core_partial = core["is_partial"].dropna().astype(str).str.lower()
                        if (core_partial == "true").any():
                            partial = True
                    else:
                        partial = True
        unique_snaps = sorted(set(snaps))
        if not unique_snaps:
            return ("unknown", partial)
        if len(unique_snaps) == 1:
            return (unique_snaps[0], partial)
        return (" ; ".join(unique_snaps), partial)

    @property
    def metadata(self) -> ProfileMetadata:
        snap, is_partial = self.snapshot_for(*self.tables.keys())
        return ProfileMetadata(
            stage=self.stage,
            snapshot_at=snap,
            is_partial=is_partial,
            source_dir=self.source_dir,
            loaded_tables=tuple(sorted(self.tables.keys())),
            missing_tables=tuple(sorted(self.missing_tables)),
        )


def resolve_eda_profile_output_dir(
    stage: str,
    base_dir: Path | None = None,
) -> Path:
    """Resolve stage output directory under outputs/eda/profile/<stage>."""
    if stage not in VALID_EDA_STAGES:
        raise ValueError(f"stage must be one of {VALID_EDA_STAGES}, got {stage!r}")
    root = base_dir if base_dir is not None else (EDA_OUTPUT_DIR / "profile")
    return root if root.name == stage else root / stage


def load_profile_bundle(
    stage: str,
    *,
    profile_base_dir: Path | None = None,
) -> ProfileBundle:
    """Load available ETL profile CSVs for one stage ('raw' or 'transformed')."""
    if stage not in VALID_STAGES:
        raise ValueError(f"load_profile_bundle expects stage in {VALID_STAGES}, got {stage!r}")
    base = profile_base_dir if profile_base_dir is not None else PROFILING_OUTPUT_DIR
    stage_dir = stage_output_dir(base, stage)
    if not stage_dir.exists():
        raise FileNotFoundError(f"Profile stage directory does not exist: {stage_dir}")

    tables: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for key, filename in PROFILE_FILES.items():
        path = stage_dir / filename
        if path.exists() and path.stat().st_size > 0:
            tables[key] = pd.read_csv(path)
        else:
            missing.append(key)

    return ProfileBundle(
        stage=stage,
        source_dir=stage_dir,
        tables=tables,
        missing_tables=missing,
    )


def _snapshot_phase_token(snapshot_str: str) -> str:
    """Extract phase prefix (e.g. 'phase1') across composite snapshot labels if present."""
    parts = [p.strip() for chunk in snapshot_str.split(";") for p in chunk.split("+") if p.strip()]
    for part in parts:
        if part.startswith("phase") and "_" in part:
            return part.split("_", 1)[0]
    return parts[0] if parts else snapshot_str.strip()


def validate_compare_compatibility(
    raw_bundle: ProfileBundle,
    transformed_bundle: ProfileBundle,
    *,
    allow_cross_snapshot: bool = False,
) -> tuple[str, str]:
    """Verify raw and transformed bundles belong to the same snapshot family.

    Raises ValueError if snapshots are incompatible unless allow_cross_snapshot=True.
    """
    primary_tables = ("wallet_distributions", "feature_nflow")
    fallback_tables = ("cohort_counts", "pretransform_cleaning")
    raw_snap, _ = raw_bundle.snapshot_for(*primary_tables)
    if raw_snap == "unknown":
        raw_snap, _ = raw_bundle.snapshot_for(*fallback_tables)
    tr_snap, _ = transformed_bundle.snapshot_for(*primary_tables)
    if tr_snap == "unknown":
        tr_snap, _ = transformed_bundle.snapshot_for(*fallback_tables)
    if raw_snap == "unknown" or tr_snap == "unknown":
        raise ValueError(
            f"Refusing to compare missing snapshots: raw={raw_snap!r}, transformed={tr_snap!r}"
        )
    if not allow_cross_snapshot:
        raw_phase = _snapshot_phase_token(raw_snap)
        tr_phase = _snapshot_phase_token(tr_snap)
        same_exact = raw_snap == tr_snap
        same_phase_pair = (
            raw_phase == tr_phase
            and raw_phase.startswith("phase")
            and "raw" in raw_snap
            and "transformed" in tr_snap
        )
        if not (same_exact or same_phase_pair):
            raise ValueError(
                "Refusing to compare mixed snapshots: "
                f"raw={raw_snap!r} vs transformed={tr_snap!r}. "
                "Re-export transformed from the same phase/snapshot or pass allow_cross_snapshot=True."
            )
    return raw_snap, tr_snap
