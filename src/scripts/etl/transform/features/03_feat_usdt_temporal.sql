-- =============================================================================
-- L3 Step 3: H1 USDT pass-through speed (IN -> subsequent OUT lag) and
--            H2 USDT 1-hour burst ratio (both >=5 gate and >=1 sensitivity).
--
-- Source (L1):  transform.clean_transactions
-- Target (stg): transform._stg_feat_usdt_temporal
--
-- Window frame rules (docs/dev/software_concepts/10-sql-rules.md Rule 6):
--   - prev_in_ts uses explicit ROWS frame with deterministic tie-break
--     (IN ordered before OUT on identical timestamps, then tx_hash).
--   - win_1h_vol uses RANGE BETWEEN INTERVAL '1 hour' PRECEDING AND CURRENT ROW
--     because burst volume is defined over a 1-hour calendar time window.
-- =============================================================================

DROP TABLE IF EXISTS transform._stg_feat_usdt_temporal;

CREATE TABLE transform._stg_feat_usdt_temporal AS
WITH usdt_events AS (
    SELECT
        from_address AS wallet_address,
        'OUT'::TEXT AS direction,
        block_timestamp,
        tx_hash,
        amount
    FROM transform.clean_transactions
    WHERE is_valid_for_features
      AND token_symbol = 'USDT'
    UNION ALL
    SELECT
        to_address AS wallet_address,
        'IN'::TEXT AS direction,
        block_timestamp,
        tx_hash,
        amount
    FROM transform.clean_transactions
    WHERE is_valid_for_features
      AND token_symbol = 'USDT'
),
usdt_win AS (
    SELECT
        wallet_address,
        direction,
        block_timestamp,
        amount,
        MAX(CASE WHEN direction = 'IN' THEN block_timestamp END) OVER (
            PARTITION BY wallet_address
            ORDER BY block_timestamp ASC, CASE WHEN direction = 'IN' THEN 0 ELSE 1 END ASC, tx_hash ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS prev_in_ts,
        SUM(amount) OVER (
            PARTITION BY wallet_address
            ORDER BY block_timestamp ASC
            RANGE BETWEEN INTERVAL '1 hour' PRECEDING AND CURRENT ROW
        ) AS win_1h_vol
    FROM usdt_events
)
SELECT
    wallet_address,
    COUNT(*)::BIGINT AS usdt_event_count,
    SUM(amount) AS total_usdt_vol,
    MAX(win_1h_vol) / NULLIF(SUM(amount), 0.0) AS burst_ratio_usdt_any,
    CASE
        WHEN COUNT(*) >= 5
        THEN MAX(win_1h_vol) / NULLIF(SUM(amount), 0.0)
        ELSE NULL
    END AS burst_ratio_usdt,
    MIN(
        CASE
            WHEN direction = 'OUT' AND prev_in_ts IS NOT NULL AND block_timestamp >= prev_in_ts
            THEN EXTRACT(EPOCH FROM (block_timestamp - prev_in_ts))
            ELSE NULL
        END
    ) AS min_passthrough_sec_usdt
FROM usdt_win
GROUP BY wallet_address;
