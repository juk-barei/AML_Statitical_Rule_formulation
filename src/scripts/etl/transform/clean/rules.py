"""Pure L1 cleaning rules (database-free domain core).

Mirrors the SQL predicates in ``01_clean_transactions.sql`` so unit tests can
verify every boundary without a database and parity tests can assert 1-for-1
agreement between Python and SQL.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

# Documented physical ceilings and anomaly boundaries (verified on 2026-11-23 raw snapshots).
USDT_SUPPLY_CEILING = 94_248_192_941.363764  # Tronscan TRON USDT total supply (2026-11-10)
TRX_SUPPLY_CEILING = 100_000_000_000.0  # TRON TRX historical ceiling (> ~86-95B circulating)
UINT256_SENTINEL_FLOOR = 1e70  # catches 2^256/1e6 (~1.1579e71) and 2^255/1e6 (~5.7896e70)
DUST_UPPER_BOUND = 0.01
ONE_SUN_TRX = 0.000001
TRX_4444_ARTIFACT = 4444.444444
TRX_4444_TOLERANCE = 1e-5
LARGE_REVIEW_LOWER_BOUND = 1_000_000.0

TRON_MAINNET_START = datetime(2018, 6, 25, tzinfo=UTC)
DEFAULT_FUTURE_CUTOFF = datetime(2026, 11, 27, tzinfo=UTC)

EXACT_SENTINEL_PREFIXES: frozenset[str] = frozenset(
    {
        "115792089237316200000000000000000000000000000000000000000000000000000000",
        "115792089237316195423570985008687907853269984665640564039457584007913129",
        "115792089237316190183760311394656140241344763643041023198016376741560320",
        "57896044618658100000000000000000000000000000000000000000000000000000000",
    }
)

INVALID_AMOUNT_FLAGS: frozenset[str] = frozenset({"null", "negative", "sentinel", "above_supply"})


@dataclass(frozen=True)
class TxRowFacts:
    """Minimal transaction row facts used for deterministic cross-schema dedupe."""

    source_schema: str  # "illicit" (rank 1) or "licit" (rank 2)
    token_symbol: str
    amount: float | None
    block_timestamp: datetime | None
    amount_exact: str | None = None


def supply_ceiling_for(token_symbol: str) -> float:
    """Return physical supply ceiling for a supported token symbol."""
    if token_symbol == "USDT":
        return USDT_SUPPLY_CEILING
    if token_symbol == "TRX":
        return TRX_SUPPLY_CEILING
    raise ValueError(f"unsupported token_symbol: {token_symbol!r}")


def classify_amount_flag(
    amount: float | None,
    token_symbol: str,
    *,
    amount_exact: str | None = None,
) -> str:
    """Classify transaction amount under strict priority order:

    null -> negative -> sentinel -> above_supply -> zero -> dust -> large_review -> ok.
    """
    if amount is None or (isinstance(amount, float) and math.isnan(amount)):
        return "null"
    if amount < 0:
        return "negative"
    if amount >= UINT256_SENTINEL_FLOOR or (
        amount_exact is not None
        and amount_exact.split(".", 1)[0].lstrip("-") in EXACT_SENTINEL_PREFIXES
    ):
        return "sentinel"
    if amount > supply_ceiling_for(token_symbol):
        return "above_supply"
    if amount == 0:
        return "zero"
    if amount < DUST_UPPER_BOUND:
        return "dust"
    if amount > LARGE_REVIEW_LOWER_BOUND:
        return "large_review"
    return "ok"


def classify_timestamp_flag(
    timestamp: datetime | None,
    *,
    future_cutoff: datetime = DEFAULT_FUTURE_CUTOFF,
) -> str:
    """Classify block_timestamp against TRON mainnet launch and snapshot cutoff."""
    if timestamp is None:
        return "null"
    ts = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)
    if ts < TRON_MAINNET_START:
        return "pre_mainnet"
    if ts > future_cutoff:
        return "future"
    return "ok"


def is_1sun_dust(amount: float | None, token_symbol: str) -> bool:
    """Return True for exact 1-SUN (0.000001 TRX) spam/memo transfers."""
    if amount is None or token_symbol != "TRX":
        return False
    return abs(amount - ONE_SUN_TRX) < 1e-12


def is_trx_4444_artifact(amount: float | None, token_symbol: str) -> bool:
    """Return True for the upstream 0.225-rate 4444.444444 TRX artifact."""
    if amount is None or token_symbol != "TRX":
        return False
    return abs(amount - TRX_4444_ARTIFACT) < TRX_4444_TOLERANCE


def is_valid_for_features(amount_flag: str, timestamp_flag: str) -> bool:
    """Baseline L3 eligibility for monetary/temporal flow events (excludes zero/impossible/pre_mainnet)."""
    return timestamp_flag == "ok" and amount_flag not in (INVALID_AMOUNT_FLAGS | {"zero"})


def dedupe_sort_key(facts: TxRowFacts) -> tuple[int, int, int]:
    """Deterministic tie-break key matching ROW_NUMBER() in 01_clean_transactions.sql.

    Lower tuple wins:
      1. Valid amount flag before sentinel/above_supply/negative/null
      2. Valid timestamp flag ('ok') before pre_mainnet/future/null
      3. illicit (1) before licit (2) because illicit carries non-zero fee_trx
         and has zero 4444.444444 / >100B TRX corruption.
    """
    amt_flag = classify_amount_flag(
        facts.amount, facts.token_symbol, amount_exact=facts.amount_exact
    )
    ts_flag = classify_timestamp_flag(facts.block_timestamp)
    src_rank = 1 if facts.source_schema == "illicit" else 2
    return (
        1 if amt_flag in INVALID_AMOUNT_FLAGS else 0,
        1 if ts_flag != "ok" else 0,
        src_rank,
    )
