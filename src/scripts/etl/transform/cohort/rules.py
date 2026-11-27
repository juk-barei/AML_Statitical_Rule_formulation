"""Pure L2 cohort priority and nesting rules (database-free domain core).

Matches ``01_cohort_wallet.sql`` and the canonical contract in ``AGENTS.md``:
  illicit > suspicious > licit > unlabeled
  - Blacklist wins at every hop (0..5).
  - Hop depth is strictly nested inside ``suspicious`` (NULL for all other classes).
  - Third fallback level is ``unlabeled`` (never ``background``).
"""
from __future__ import annotations

from dataclasses import dataclass

COHORT_ORDER: tuple[str, ...] = ("illicit", "suspicious", "licit", "unlabeled")
VALID_COHORTS: frozenset[str] = frozenset(COHORT_ORDER)


@dataclass(frozen=True)
class WalletFacts:
    """Boolean/scalar membership facts for one wallet."""

    is_blacklisted: bool = False
    is_hop0: bool = False
    min_hop_1_5: int | None = None
    in_licit_accounts: bool = False


def classify_wallet(facts: WalletFacts) -> str:
    """Assign deterministic cohort class under illicit > suspicious > licit > unlabeled."""
    if facts.is_blacklisted or facts.is_hop0:
        return "illicit"
    if facts.min_hop_1_5 is not None and 1 <= facts.min_hop_1_5 <= 5:
        return "suspicious"
    if facts.in_licit_accounts:
        return "licit"
    return "unlabeled"


def resolve_min_hop_level(wallet_class: str, min_hop_1_5: int | None) -> int | None:
    """Enforce nesting invariant: min_hop_level is populated ONLY for suspicious wallets."""
    if wallet_class != "suspicious":
        return None
    if min_hop_1_5 is None or not (1 <= min_hop_1_5 <= 5):
        raise ValueError(f"suspicious wallet must have min_hop_1_5 in 1..5, got {min_hop_1_5!r}")
    return min_hop_1_5


def assert_cohort_partition(universe_count: int, class_counts: dict[str, int]) -> None:
    """Verify exact mutually exclusive, collectively exhaustive cohort partition."""
    unknown = set(class_counts) - VALID_COHORTS
    if unknown:
        raise AssertionError(f"unexpected wallet_class values: {sorted(unknown)}")
    if any(v < 0 for v in class_counts.values()):
        raise AssertionError(f"negative cohort count in {class_counts}")
    total = sum(class_counts.values())
    if total != universe_count:
        raise AssertionError(
            f"cohort partition mismatch: sum({class_counts}) = {total} != universe {universe_count}"
        )
