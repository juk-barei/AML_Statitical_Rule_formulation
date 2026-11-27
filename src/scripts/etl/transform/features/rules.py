"""Pure L3 H1-H6 feature formulas and eligibility rules (database-free core).

Matches ``01_feat_scalar.sql`` .. ``05_wallet_features.sql`` and ``profile_stage.py``
so Python unit tests and SQL fixture parity tests enforce 1-for-1 consistency.
"""
from __future__ import annotations

import math
import statistics
from collections.abc import Sequence

H1_MAX_PASSTHROUGH_SEC = 900.0  # 15 minutes
H2_MAX_LIFETIME_DAYS = 7.0
H2_MIN_BURST_RATIO = 0.75
H4_MIN_JACCARD = 0.50
H6_MAX_CV = 0.15

COHORT_ORDER: tuple[str, ...] = ("illicit", "suspicious", "licit", "unlabeled")

# (column_name, hypothesis, eligibility_filter, note)
FEATURE_NFLOW_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("total_tx_count", "shared", "all wallets", "clean non-zero events"),
    ("zero_tx_count", "shared", "all wallets", "flagged zero-amount events"),
    ("usdt_tx_count", "shared", "all wallets", "clean non-zero USDT events"),
    ("trx_tx_count", "shared", "all wallets", "clean non-zero TRX events (incl. dust & 4444)"),
    ("trx_tx_count_excl_4444", "shared", "all wallets", "sensitivity: TRX excluding 4444.444444 artifact"),
    ("trx_tx_count_nodust", "shared", "all wallets", "sensitivity: TRX excluding <0.01 dust"),
    ("usdt_volume", "shared", ">=1 non-zero USDT event", "total clean USDT in+out volume"),
    ("trx_volume", "shared", ">=1 non-zero TRX event", "total clean TRX in+out volume"),
    ("trx_volume_excl_4444", "shared", ">=1 non-4444 TRX event", "sensitivity: TRX volume excluding 4444.444444"),
    ("in_out_vol_ratio_usdt", "H1", "both USDT in>0 and out>0", "usdt_out_volume / usdt_in_volume"),
    ("min_passthrough_sec_usdt", "H1", "paired USDT IN -> subsequent OUT", "min seconds from prior IN to next OUT"),
    ("h1_pass_15m", "H1", "paired USDT IN -> subsequent OUT", "min_passthrough_sec_usdt <= 900s"),
    ("tx_lifetime_days", "H2", ">=2 non-zero events (all tokens)", "clean transaction span in days"),
    ("log1p_tx_lifetime_days", "H2", ">=2 non-zero events (all tokens)", "stateless log1p(tx_lifetime_days)"),
    ("burst_ratio_usdt", "H2", ">=5 non-zero USDT events", "max 1h USDT vol / total USDT vol"),
    ("h2_pass_ge5", "H2", ">=2 events and >=5 USDT events", "tx_lifetime_days <= 7 AND burst_ratio_usdt >= 0.75"),
    ("h2_pass_any_usdt", "H2", ">=1 non-zero USDT event", "activity-floor sensitivity (no >=5 gate)"),
    ("fan_out_in_ratio_usdt", "H3", ">=1 USDT event", "(out_degree_usdt + 1) / (in_degree_usdt + 1)"),
    ("amount_cv_usdt", "H3", ">=5 non-zero USDT events", "stddev_samp / avg of clean USDT amounts"),
    ("jaccard_index", "H4", "both TRX funders>0 and USDT recipients>0", "Jaccard(TRX funders, USDT recipients)"),
    ("h4_pass", "H4", "both TRX funders>0 and USDT recipients>0", "jaccard_index >= 0.50"),
    ("min_hop_level", "H5", "suspicious wallets (hop 1..5)", "nested inside suspicious; NULL elsewhere"),
    ("seed_count", "H5", "all wallets", "distinct illicit seed_address count"),
    ("cv_delta_t_all", "H6", ">=5 non-zero events and mean gap > 0", "all-direction inter-arrival CV"),
    ("log1p_cv_delta_t_all", "H6", ">=5 non-zero events and mean gap > 0", "stateless log1p(cv_delta_t_all)"),
    ("cv_delta_t_out", "H6", ">=5 non-zero OUT events and mean gap > 0", "OUT-only directional sensitivity"),
    ("h6_pass_all", "H6", ">=5 non-zero events and mean gap > 0", "cv_delta_t_all < 0.15"),
    ("h6_pass_out", "H6", ">=5 non-zero OUT events and mean gap > 0", "cv_delta_t_out < 0.15"),
)


def compute_log1p(value: float | None) -> float | None:
    """Stateless monotonic log1p transform for non-negative features."""
    if value is None:
        return None
    if value < 0:
        raise ValueError(f"log1p requires non-negative input, got {value}")
    return math.log1p(value)


def compute_tx_lifetime_days(timestamps_sec: Sequence[float]) -> float | None:
    """H2 transaction span in days; undefined (None) when fewer than 2 events."""
    if len(timestamps_sec) < 2:
        return None
    return (max(timestamps_sec) - min(timestamps_sec)) / 86400.0


def compute_fan_out_in_ratio(in_degree_usdt: int, out_degree_usdt: int) -> float | None:
    """H3 Laplace-smoothed fan-out/in ratio; undefined when both degrees are 0."""
    if in_degree_usdt + out_degree_usdt <= 0:
        return None
    return (out_degree_usdt + 1.0) / (in_degree_usdt + 1.0)


def compute_jaccard(trx_funders: set[str], usdt_recipients: set[str]) -> float | None:
    """H4 Jaccard(TRX funders, USDT recipients); undefined if either set is empty."""
    if not trx_funders or not usdt_recipients:
        return None
    union = trx_funders | usdt_recipients
    return len(trx_funders & usdt_recipients) / len(union)


def compute_cv(values: Sequence[float], *, min_events: int = 5) -> float | None:
    """Sample coefficient of variation (stddev_samp / mean) with activity & zero-mean guards."""
    if len(values) < min_events:
        return None
    mean_v = statistics.fmean(values)
    if mean_v <= 0:
        return None
    return statistics.stdev(values) / mean_v


def compute_interarrival_cv(timestamps_sec: Sequence[float], *, min_events: int = 5) -> float | None:
    """H6 inter-arrival time CV over sorted timestamps; requires >=5 events (4+ gaps) and mean gap > 0."""
    if len(timestamps_sec) < min_events:
        return None
    ordered = sorted(timestamps_sec)
    gaps = [ordered[i] - ordered[i - 1] for i in range(1, len(ordered))]
    if len(gaps) < 2:
        return None
    mean_gap = statistics.fmean(gaps)
    if mean_gap <= 0:
        return None
    return statistics.stdev(gaps) / mean_gap


def compute_min_passthrough_sec(events: Sequence[tuple[float, str]]) -> float | None:
    """H1 minimum lag (seconds) from a prior IN event to a subsequent OUT event.

    Each event is ``(timestamp_sec, direction)`` with direction in {'IN', 'OUT'}.
    Same-timestamp ties order IN before OUT, matching 03_feat_usdt_temporal.sql.
    """
    ordered = sorted(events, key=lambda e: (e[0], 0 if e[1] == "IN" else 1))
    last_in: float | None = None
    best: float | None = None
    for ts, direction in ordered:
        if direction == "OUT" and last_in is not None and ts >= last_in:
            lag = ts - last_in
            best = lag if best is None else min(best, lag)
        if direction == "IN":
            last_in = ts
    return best


def compute_burst_ratio_1h(
    events: Sequence[tuple[float, float]],
    *,
    min_events: int = 5,
) -> float | None:
    """H2 maximum rolling 1-hour (3600s) volume share over total volume."""
    if len(events) < min_events:
        return None
    total = sum(amt for _, amt in events)
    if total <= 0:
        return None
    ordered = sorted(events, key=lambda e: e[0])
    max_win = 0.0
    for i, (ts_i, _) in enumerate(ordered):
        win_sum = sum(amt for ts_j, amt in ordered[: i + 1] if ts_i - 3600.0 <= ts_j <= ts_i)
        if win_sum > max_win:
            max_win = win_sum
    return max_win / total
