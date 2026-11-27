-- =============================================================================
-- L1 Step 1: Cross-schema transaction union, deduplication, and non-destructive
--            quality flagging.
--
-- Source schemas (read-only L0): illicit.transactions, licit.transactions
-- Target schema (derived L1):    transform.clean_transactions
--                                transform.clean_tx_conflicts
--
-- Directly executable in psql / DBeaver (no template placeholders).
-- Rules enforced (see docs/dev/software_concepts/10-sql-rules.md):
--   - Identical cleaning flags applied to both schemas.
--   - Deterministic dedupe via ROW_NUMBER() (never DISTINCT ON without ORDER BY).
--   - NULL-safe conflict detection via IS DISTINCT FROM.
--   - Never mutates or indexes L0 mirror tables; drops hex_address if present.
--   - Non-destructive: sentinel, above_supply, zero, pre_mainnet, dust, and
--     4444.444444 TRX rows stay in clean_transactions with explicit flags.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS transform;

DROP TABLE IF EXISTS transform.clean_tx_conflicts;
DROP TABLE IF EXISTS transform.clean_transactions;

-- 1A. Audit table of cross-schema tx_hash field conflicts (expected ~3,200 rows)
CREATE TABLE transform.clean_tx_conflicts AS
SELECT
    i.tx_hash,
    i.token_symbol AS illicit_token_symbol,
    l.token_symbol AS licit_token_symbol,
    i.amount::DOUBLE PRECISION AS illicit_amount,
    l.amount::DOUBLE PRECISION AS licit_amount,
    i.amount::TEXT AS illicit_amount_exact,
    l.amount::TEXT AS licit_amount_exact,
    i.block_timestamp AS illicit_block_timestamp,
    l.block_timestamp AS licit_block_timestamp,
    i.from_address AS illicit_from_address,
    l.from_address AS licit_from_address,
    i.to_address AS illicit_to_address,
    l.to_address AS licit_to_address,
    (i.token_symbol IS DISTINCT FROM l.token_symbol) AS diff_token,
    (i.amount IS DISTINCT FROM l.amount) AS diff_amount,
    (i.block_timestamp IS DISTINCT FROM l.block_timestamp) AS diff_ts,
    (i.from_address IS DISTINCT FROM l.from_address) AS diff_from,
    (i.to_address IS DISTINCT FROM l.to_address) AS diff_to
FROM illicit.transactions i
INNER JOIN licit.transactions l
    ON i.tx_hash = l.tx_hash
WHERE i.token_symbol IS DISTINCT FROM l.token_symbol
   OR i.amount IS DISTINCT FROM l.amount
   OR i.block_timestamp IS DISTINCT FROM l.block_timestamp
   OR i.from_address IS DISTINCT FROM l.from_address
   OR i.to_address IS DISTINCT FROM l.to_address;

-- 1B. Materialized L1 clean_transactions (1 row per unique tx_hash)
CREATE TABLE transform.clean_transactions AS
WITH raw_union AS (
    SELECT
        tx_hash,
        block_number,
        block_timestamp,
        from_address,
        to_address,
        token_symbol,
        contract_address,
        amount::DOUBLE PRECISION AS amount,
        amount::TEXT AS amount_exact,
        fee_trx,
        created_at,
        'illicit'::TEXT AS source_schema,
        1 AS src_rank
    FROM illicit.transactions
    UNION ALL
    SELECT
        tx_hash,
        block_number,
        block_timestamp,
        from_address,
        to_address,
        token_symbol,
        contract_address,
        amount::DOUBLE PRECISION AS amount,
        amount::TEXT AS amount_exact,
        fee_trx,
        created_at,
        'licit'::TEXT AS source_schema,
        2 AS src_rank
    FROM licit.transactions
),
flagged AS (
    SELECT
        tx_hash,
        block_number,
        block_timestamp,
        from_address,
        to_address,
        token_symbol,
        contract_address,
        amount,
        amount_exact,
        fee_trx,
        created_at,
        source_schema,
        src_rank,
        CASE
            WHEN amount IS NULL OR amount = 'NaN'::DOUBLE PRECISION THEN 'null'
            WHEN amount < 0 THEN 'negative'
            WHEN amount >= 1e70
              OR LTRIM(SPLIT_PART(amount_exact, '.', 1), '-') IN (
                    '115792089237316200000000000000000000000000000000000000000000000000000000',
                    '115792089237316195423570985008687907853269984665640564039457584007913129',
                    '115792089237316190183760311394656140241344763643041023198016376741560320',
                    '57896044618658100000000000000000000000000000000000000000000000000000000'
                 ) THEN 'sentinel'
            WHEN (token_symbol = 'USDT' AND amount > 94248192941.363764)
              OR (token_symbol = 'TRX' AND amount > 100000000000.0) THEN 'above_supply'
            WHEN amount = 0 THEN 'zero'
            WHEN amount < 0.01 THEN 'dust'
            WHEN amount > 1000000.0 THEN 'large_review'
            ELSE 'ok'
        END AS amount_flag,
        CASE
            WHEN block_timestamp IS NULL THEN 'null'
            WHEN block_timestamp < TIMESTAMPTZ '2018-06-25 00:00:00+00' THEN 'pre_mainnet'
            WHEN block_timestamp > TIMESTAMPTZ '2026-11-27 00:00:00+00' THEN 'future'
            ELSE 'ok'
        END AS timestamp_flag,
        (token_symbol = 'TRX' AND ABS(amount - 0.000001) < 1e-12) AS is_1sun_dust,
        (token_symbol = 'TRX' AND ABS(amount - 4444.444444) < 1e-5) AS is_trx_4444_artifact
    FROM raw_union
),
ranked AS (
    SELECT
        f.*,
        COUNT(*) OVER (PARTITION BY f.tx_hash) > 1 AS in_both_schemas,
        ROW_NUMBER() OVER (
            PARTITION BY f.tx_hash
            ORDER BY
                CASE WHEN f.amount_flag IN ('null', 'negative', 'sentinel', 'above_supply') THEN 1 ELSE 0 END ASC,
                CASE WHEN f.timestamp_flag <> 'ok' THEN 1 ELSE 0 END ASC,
                f.src_rank ASC
        ) AS rn
    FROM flagged f
)
SELECT
    r.tx_hash,
    r.block_number,
    r.block_timestamp,
    r.from_address,
    r.to_address,
    r.token_symbol,
    r.contract_address,
    r.amount,
    r.amount_exact,
    r.fee_trx,
    r.created_at,
    r.source_schema,
    r.in_both_schemas,
    (c.tx_hash IS NOT NULL) AS has_cross_schema_conflict,
    r.amount_flag,
    r.timestamp_flag,
    r.is_1sun_dust,
    r.is_trx_4444_artifact,
    (
        r.timestamp_flag = 'ok'
        AND r.amount_flag NOT IN ('null', 'negative', 'sentinel', 'above_supply', 'zero')
    ) AS is_valid_for_features
FROM ranked r
LEFT JOIN transform.clean_tx_conflicts c
    ON c.tx_hash = r.tx_hash
WHERE r.rn = 1;
