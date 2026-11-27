-- =============================================================================
-- L2 Step 1: Materialized wallet-grain cohort table (1 row per wallet).
--
-- Source schemas (read-only L0):
--   illicit.accounts
--   illicit.blacklisted_wallets
--   illicit.wallet_hops
--   licit.accounts
--   licit.seed_wallets
--   licit.wallet_hops
-- Target (derived L2):
--   transform.cohort_wallet
--
-- Directly executable in psql / DBeaver (no template placeholders).
-- Enforces AGENTS.md & docs/dev/software_concepts/10-sql-rules.md:
--   - Priority: illicit (blacklist label=1 OR hop 0) > suspicious (hop 1..5, not
--     blacklisted) > licit (licit.accounts minus illicit/suspicious) > unlabeled.
--   - Full reconciled universe: accounts union + blacklist + hop 0..5 wallets
--     (retains ~27,017 hop-only wallets with in_accounts_table = FALSE).
--   - Pre-aggregates wallet_hops BEFORE joining (zero fan-out).
--   - NULL-safe anti-joins (no NOT IN anywhere).
--   - min_hop_level is strictly nested inside suspicious (NULL elsewhere).
--   - Drops hex_address; sorted by (wallet_class, wallet_address) for Parquet
--     row-group pruning.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS transform;

DROP TABLE IF EXISTS transform.cohort_wallet;

CREATE TABLE transform.cohort_wallet AS
WITH illicit_acc AS (
    SELECT DISTINCT address AS wallet_address
    FROM illicit.accounts
    WHERE address IS NOT NULL
),
licit_acc AS (
    SELECT DISTINCT address AS wallet_address
    FROM licit.accounts
    WHERE address IS NOT NULL
),
blacklist AS (
    SELECT
        wallet_address,
        MIN(blacklisted_utc) AS blacklisted_utc,
        BOOL_OR(blacklisted_utc IS NOT NULL) AS has_blacklist_timestamp
    FROM illicit.blacklisted_wallets
    WHERE label = 1
      AND wallet_address IS NOT NULL
    GROUP BY wallet_address
),
hop0 AS (
    SELECT DISTINCT wallet_address
    FROM illicit.wallet_hops
    WHERE hop_level = 0
      AND wallet_address IS NOT NULL
),
hop_agg AS (
    SELECT
        wallet_address,
        MIN(hop_level)::SMALLINT AS raw_min_hop_level,
        MAX(hop_level)::SMALLINT AS max_hop_level,
        COUNT(DISTINCT seed_address)::INTEGER AS seed_count,
        COUNT(*)::INTEGER AS hop_row_count
    FROM illicit.wallet_hops
    WHERE hop_level BETWEEN 1 AND 5
      AND wallet_address IS NOT NULL
    GROUP BY wallet_address
),
primary_seed AS (
    SELECT wallet_address, seed_address AS primary_seed_address
    FROM (
        SELECT
            wallet_address,
            seed_address,
            ROW_NUMBER() OVER (
                PARTITION BY wallet_address
                ORDER BY hop_level ASC, discovered_at ASC NULLS LAST, seed_address ASC
            ) AS rn
        FROM illicit.wallet_hops
        WHERE hop_level BETWEEN 1 AND 5
          AND wallet_address IS NOT NULL
          AND seed_address IS NOT NULL
    ) ranked_seeds
    WHERE rn = 1
),
licit_seeds AS (
    SELECT DISTINCT wallet_address
    FROM licit.seed_wallets
    WHERE wallet_address IS NOT NULL
),
contaminated_licit_seeds AS (
    SELECT ls.wallet_address
    FROM licit_seeds ls
    WHERE EXISTS (
        SELECT 1
        FROM blacklist b
        WHERE b.wallet_address = ls.wallet_address
    )
),
from_contaminated_licit AS (
    SELECT DISTINCT lh.wallet_address
    FROM licit.wallet_hops lh
    WHERE lh.wallet_address IS NOT NULL
      AND EXISTS (
          SELECT 1
          FROM contaminated_licit_seeds cs
          WHERE cs.wallet_address = lh.seed_address
      )
),
universe AS (
    SELECT wallet_address FROM illicit_acc
    UNION
    SELECT wallet_address FROM licit_acc
    UNION
    SELECT wallet_address FROM blacklist
    UNION
    SELECT wallet_address FROM hop0
    UNION
    SELECT wallet_address FROM hop_agg
),
classified AS (
    SELECT
        u.wallet_address,
        CASE
            WHEN b.wallet_address IS NOT NULL OR h0.wallet_address IS NOT NULL THEN 'illicit'
            WHEN ha.wallet_address IS NOT NULL THEN 'suspicious'
            WHEN la.wallet_address IS NOT NULL THEN 'licit'
            ELSE 'unlabeled'
        END AS wallet_class,
        CASE
            WHEN b.wallet_address IS NULL AND h0.wallet_address IS NULL THEN ha.raw_min_hop_level
            ELSE NULL
        END AS min_hop_level,
        ha.max_hop_level,
        COALESCE(ha.seed_count, 0)::INTEGER AS seed_count,
        COALESCE(ha.hop_row_count, 0)::INTEGER AS hop_row_count,
        ps.primary_seed_address,
        (ia.wallet_address IS NOT NULL OR la.wallet_address IS NOT NULL) AS in_accounts_table,
        (ia.wallet_address IS NOT NULL) AS in_illicit_accounts,
        (la.wallet_address IS NOT NULL) AS in_licit_accounts,
        (ls.wallet_address IS NOT NULL) AS is_licit_seed,
        (cs.wallet_address IS NOT NULL) AS is_contaminated_licit_seed,
        (fc.wallet_address IS NOT NULL) AS from_contaminated_licit_seed,
        COALESCE(b.has_blacklist_timestamp, FALSE) AS has_blacklist_timestamp,
        b.blacklisted_utc
    FROM universe u
    LEFT JOIN illicit_acc ia ON ia.wallet_address = u.wallet_address
    LEFT JOIN licit_acc la ON la.wallet_address = u.wallet_address
    LEFT JOIN blacklist b ON b.wallet_address = u.wallet_address
    LEFT JOIN hop0 h0 ON h0.wallet_address = u.wallet_address
    LEFT JOIN hop_agg ha ON ha.wallet_address = u.wallet_address
    LEFT JOIN primary_seed ps ON ps.wallet_address = u.wallet_address
    LEFT JOIN licit_seeds ls ON ls.wallet_address = u.wallet_address
    LEFT JOIN contaminated_licit_seeds cs ON cs.wallet_address = u.wallet_address
    LEFT JOIN from_contaminated_licit fc ON fc.wallet_address = u.wallet_address
)
SELECT
    wallet_address,
    wallet_class,
    min_hop_level,
    max_hop_level,
    seed_count,
    hop_row_count,
    primary_seed_address,
    in_accounts_table,
    in_illicit_accounts,
    in_licit_accounts,
    is_licit_seed,
    is_contaminated_licit_seed,
    from_contaminated_licit_seed,
    has_blacklist_timestamp,
    blacklisted_utc
FROM classified
ORDER BY wallet_class, wallet_address;
