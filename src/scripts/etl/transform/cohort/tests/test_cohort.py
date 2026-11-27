"""Unit, static SQL guardrail, and in-memory DuckDB fixture tests for L2 cohort."""
from __future__ import annotations

import re
from pathlib import Path

import duckdb

from src.scripts.etl.transform.cohort.main import SQL_STEPS, main, render_sql
from src.scripts.etl.transform.cohort.rules import (
    WalletFacts,
    assert_cohort_partition,
    classify_wallet,
    resolve_min_hop_level,
)

SQL_DIR = Path(__file__).resolve().parents[1]


def test_pure_cohort_priority_and_nesting() -> None:
    # Blacklist wins at every hop (0..5) and over licit
    assert classify_wallet(WalletFacts(is_blacklisted=True, min_hop_1_5=3, in_licit_accounts=True)) == "illicit"
    assert classify_wallet(WalletFacts(is_hop0=True, in_licit_accounts=True)) == "illicit"
    # Suspicious wins over licit
    assert classify_wallet(WalletFacts(min_hop_1_5=2, in_licit_accounts=True)) == "suspicious"
    # Clean licit
    assert classify_wallet(WalletFacts(in_licit_accounts=True)) == "licit"
    # Fallback is unlabeled (never background)
    assert classify_wallet(WalletFacts()) == "unlabeled"

    assert resolve_min_hop_level("illicit", 3) is None
    assert resolve_min_hop_level("suspicious", 2) == 2
    assert resolve_min_hop_level("licit", None) is None
    assert resolve_min_hop_level("unlabeled", None) is None

    assert_cohort_partition(10, {"illicit": 1, "suspicious": 3, "licit": 4, "unlabeled": 2})


def test_sql_guardrails() -> None:
    """Enforce docs/dev/software_concepts/10-sql-rules.md across L2 SQL files."""
    for _, filename in SQL_STEPS:
        sql_text = (SQL_DIR / filename).read_text(encoding="utf-8")
        no_comments = re.sub(r"--[^\n]*", "", sql_text)
        assert not re.search(r"\bNOT\s+IN\b", no_comments, re.IGNORECASE)
        assert not re.search(r"\bNATURAL\s+JOIN\b", no_comments, re.IGNORECASE)
        assert not re.search(r"\bDISTINCT\s+ON\b", no_comments, re.IGNORECASE)
        assert "hex_address" not in no_comments
        assert "background" not in no_comments.lower()
        assert "{" not in no_comments and "}" not in no_comments


def test_sql_fixture_nullable_antijoin_and_fanout() -> None:
    """Verify nullable anti-join, hop fan-out prevention, priority, and hop-only accounting."""
    con = duckdb.connect()
    try:
        con.execute("CREATE SCHEMA illicit; CREATE SCHEMA licit;")
        con.execute(
            """
            CREATE TABLE illicit.accounts (address VARCHAR);
            CREATE TABLE licit.accounts (address VARCHAR);
            CREATE TABLE illicit.blacklisted_wallets (
                wallet_address VARCHAR, blacklisted_utc TIMESTAMPTZ, label INTEGER
            );
            CREATE TABLE illicit.wallet_hops (
                hop_id BIGINT, wallet_address VARCHAR, seed_address VARCHAR,
                hop_level SMALLINT, discovered_at TIMESTAMPTZ
            );
            CREATE TABLE licit.seed_wallets (wallet_address VARCHAR);
            CREATE TABLE licit.wallet_hops (
                hop_id BIGINT, wallet_address VARCHAR, seed_address VARCHAR, hop_level SMALLINT
            );
            """
        )
        con.execute(
            """
            INSERT INTO illicit.accounts VALUES
                ('W_BL_HOP3'), ('W_SUS_MULTI'), ('W_UNLABELED'), ('W_BL_SEED_LICIT');
            INSERT INTO licit.accounts VALUES
                ('W_BL_SEED_LICIT'), ('W_SUS_MULTI'), ('W_LICIT_CLEAN'), ('W_LICIT_FROM_BAD_SEED');
            -- Include a NULL wallet_address row to prove NULL-safety (10-sql-rules.md Rule 12)
            INSERT INTO illicit.blacklisted_wallets VALUES
                ('W_BL_HOP3',       NULL, 1),
                ('W_BL_SEED_LICIT', TIMESTAMPTZ '2025-05-01 00:00:00+00', 1),
                ('W_LABEL_ZERO',    NULL, 0),
                (NULL,              NULL, 1);
            -- W_SUS_MULTI has 3 hop rows across 2 seeds (fan-out test!)
            -- W_HOP_ONLY is absent from accounts (reconciliation test!)
            -- W_BL_HOP3 is at hop 3 AND blacklisted (blacklist-wins-at-every-hop test!)
            INSERT INTO illicit.wallet_hops VALUES
                (1, 'W_BL_HOP3',   'SEED_A', 3, TIMESTAMPTZ '2026-11-01 00:00:00+00'),
                (2, 'W_SUS_MULTI', 'SEED_B', 4, TIMESTAMPTZ '2026-11-02 00:00:00+00'),
                (3, 'W_SUS_MULTI', 'SEED_A', 2, TIMESTAMPTZ '2026-11-01 00:00:00+00'),
                (4, 'W_SUS_MULTI', 'SEED_C', 2, TIMESTAMPTZ '2026-11-03 00:00:00+00'),
                (5, 'W_HOP_ONLY',  'SEED_A', 1, TIMESTAMPTZ '2026-11-01 00:00:00+00');
            INSERT INTO licit.seed_wallets VALUES ('W_BL_SEED_LICIT'), ('W_LICIT_CLEAN');
            INSERT INTO licit.wallet_hops VALUES
                (1, 'W_LICIT_FROM_BAD_SEED', 'W_BL_SEED_LICIT', 1);
            """
        )

        sql_01 = render_sql(
            "01_cohort_wallet.sql",
            transform_schema="transform",
            illicit_schema="illicit",
            licit_schema="licit",
        )
        con.execute(sql_01)

        rows = con.execute(
            """
            SELECT wallet_address, wallet_class, min_hop_level, max_hop_level,
                   seed_count, hop_row_count, primary_seed_address,
                   in_accounts_table, is_contaminated_licit_seed,
                   from_contaminated_licit_seed, has_blacklist_timestamp
            FROM transform.cohort_wallet
            ORDER BY wallet_address
            """
        ).fetchall()

        # Exactly 7 distinct wallets in universe (zero fan-out; W_LABEL_ZERO & NULL excluded)
        assert len(rows) == 7
        by_w = {r[0]: r for r in rows}

        # 1. Blacklisted at hop 3 -> illicit, min_hop_level MUST be NULL, missing blacklist ts preserved
        assert by_w["W_BL_HOP3"][1] == "illicit"
        assert by_w["W_BL_HOP3"][2] is None
        assert by_w["W_BL_HOP3"][10] is False

        # 2. Contaminated licit seed -> illicit, flagged is_contaminated_licit_seed=True
        assert by_w["W_BL_SEED_LICIT"][1] == "illicit"
        assert by_w["W_BL_SEED_LICIT"][2] is None
        assert by_w["W_BL_SEED_LICIT"][8] is True
        assert by_w["W_BL_SEED_LICIT"][10] is True

        # 3. Multi-hop, multi-seed wallet overlapping licit -> suspicious (no fan-out!)
        #    min_hop=2, max_hop=4, seed_count=3, hop_row_count=3, primary_seed='SEED_A' (earliest at hop 2)
        assert by_w["W_SUS_MULTI"][1] == "suspicious"
        assert by_w["W_SUS_MULTI"][2] == 2
        assert by_w["W_SUS_MULTI"][3] == 4
        assert by_w["W_SUS_MULTI"][4] == 3
        assert by_w["W_SUS_MULTI"][5] == 3
        assert by_w["W_SUS_MULTI"][6] == "SEED_A"

        # 4. Hop-only wallet absent from accounts -> suspicious with in_accounts_table=False
        assert by_w["W_HOP_ONLY"][1] == "suspicious"
        assert by_w["W_HOP_ONLY"][2] == 1
        assert by_w["W_HOP_ONLY"][7] is False

        # 5. Clean licit & wallet descended from contaminated licit seed
        assert by_w["W_LICIT_CLEAN"][1] == "licit"
        assert by_w["W_LICIT_CLEAN"][2] is None
        assert by_w["W_LICIT_FROM_BAD_SEED"][1] == "licit"
        assert by_w["W_LICIT_FROM_BAD_SEED"][9] is True

        # 6. Unlabeled remainder
        assert by_w["W_UNLABELED"][1] == "unlabeled"
        assert by_w["W_UNLABELED"][2] is None

        # Exact partition check
        counts = dict(
            con.execute(
                "SELECT wallet_class, COUNT(*) FROM transform.cohort_wallet GROUP BY wallet_class"
            ).fetchall()
        )
        assert_cohort_partition(7, counts)
    finally:
        con.close()


def test_cli_dry_run() -> None:
    assert main(["--dry-run", "--step", "all"]) == 0


if __name__ == "__main__":
    test_pure_cohort_priority_and_nesting()
    test_sql_guardrails()
    test_sql_fixture_nullable_antijoin_and_fanout()
    test_cli_dry_run()
    print("L2 cohort checks passed")
