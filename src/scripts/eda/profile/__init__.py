"""Stage-aware EDA profiling plots over compact ETL profile CSVs."""
from src.scripts.eda.profile.io import (
    ProfileBundle,
    ProfileMetadata,
    load_profile_bundle,
    resolve_eda_profile_output_dir,
    validate_compare_compatibility,
)
from src.scripts.eda.profile.plots_cohort_frame import (
    plot_cohort_composition_nflow,
    plot_cross_schema_overlap,
    plot_hop_and_seed_structure,
)
from src.scripts.eda.profile.plots_compare import plot_raw_vs_transformed_shift
from src.scripts.eda.profile.plots_features import (
    plot_feature_eligibility_nflow,
    plot_feature_histograms_grid,
    plot_feature_quantile_ranges,
    plot_feature_skew_zero_tail,
)
from src.scripts.eda.profile.plots_schema_quality import (
    plot_column_missingness_dtypes,
    plot_quality_and_cleaning_anomalies,
    plot_table_overview_coverage,
    plot_tx_volume_by_year,
)

__all__ = [
    "ProfileBundle",
    "ProfileMetadata",
    "load_profile_bundle",
    "resolve_eda_profile_output_dir",
    "validate_compare_compatibility",
    "plot_table_overview_coverage",
    "plot_column_missingness_dtypes",
    "plot_quality_and_cleaning_anomalies",
    "plot_tx_volume_by_year",
    "plot_cohort_composition_nflow",
    "plot_cross_schema_overlap",
    "plot_hop_and_seed_structure",
    "plot_feature_eligibility_nflow",
    "plot_feature_skew_zero_tail",
    "plot_feature_quantile_ranges",
    "plot_feature_histograms_grid",
    "plot_raw_vs_transformed_shift",
]
