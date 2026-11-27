-- =============================================================================
-- L3 Step 1: Scalar wallet counts, volumes, H2 tx_lifetime_days, H3 amount_cv_usdt,
--            and dust / 4444.444444 TRX sensitivity metrics.
--
-- Source (L1):  {transform_schema}.clean_transactions
-- Target (stg): {transform_schema}._stg_feat_scalar
--
-- Rules enforced:
--   - Uses ONLY L1 clean_transactions (never touches L0 raw tables).
--   - Excludes fee_trx (100% zero in licit; schema-origin leakage).
--   - Keeps zero-amount valid-timestamp events strictly in zero_tx_count.
--   - Uses NULLIF(..., 0) for divide-by-zero protection (10-sql-rules.md Rule 8).
-- =============================================================================

DROP TABLE IF EXISTS {transform_schema}._stg_feat_scalar;

CREATE TABLE {transform_schema}._stg_feat_scalar AS
WITH wallet_events AS (
    SELECT
        from_address AS wallet_address,
        'OUT'::TEXT AS direction,
        block_timestamp,
        token_symbol,
        amount,
        amount_flag,
        is_trx_4444_artifact,
        is_valid_for_features,
        (timestamp_flag = 'ok' AND amount_flag = 'zero') AS is_clean_zero
    FROM {transform_schema}.clean_transactions
    WHERE timestamp_flag = 'ok'
      AND (is_valid_for_features OR amount_flag = 'zero')
    UNION ALL
    SELECT
        to_address AS wallet_address,
        'IN'::TEXT AS direction,
        block_timestamp,
        token_symbol,
        amount,
        amount_flag,
        is_trx_4444_artifact,
        is_valid_for_features,
        (timestamp_flag = 'ok' AND amount_flag = 'zero') AS is_clean_zero
    FROM {transform_schema}.clean_transactions
    WHERE timestamp_flag = 'ok'
      AND (is_valid_for_features OR amount_flag = 'zero')
)
SELECT
    wallet_address,
    COUNT(*) FILTER (WHERE is_valid_for_features)::BIGINT AS total_tx_count,
    COUNT(*) FILTER (WHERE is_clean_zero)::BIGINT AS zero_tx_count,
    COUNT(*) FILTER (WHERE is_valid_for_features AND token_symbol = 'USDT')::BIGINT AS usdt_tx_count,
    COUNT(*) FILTER (WHERE is_valid_for_features AND token_symbol = 'TRX')::BIGINT AS trx_tx_count,
    COUNT(*) FILTER (WHERE is_valid_for_features AND token_symbol = 'TRX' AND NOT is_trx_4444_artifact)::BIGINT AS trx_tx_count_excl_4444,
    COUNT(*) FILTER (WHERE is_valid_for_features AND token_symbol = 'TRX' AND amount_flag <> 'dust')::BIGINT AS trx_tx_count_nodust,
    SUM(amount) FILTER (WHERE is_valid_for_features AND token_symbol = 'USDT') AS usdt_volume,
    SUM(amount) FILTER (WHERE is_valid_for_features AND token_symbol = 'USDT' AND direction = 'IN') AS usdt_in_volume,
    SUM(amount) FILTER (WHERE is_valid_for_features AND token_symbol = 'USDT' AND direction = 'OUT') AS usdt_out_volume,
    SUM(amount) FILTER (WHERE is_valid_for_features AND token_symbol = 'TRX') AS trx_volume,
    SUM(amount) FILTER (WHERE is_valid_for_features AND token_symbol = 'TRX' AND NOT is_trx_4444_artifact) AS trx_volume_excl_4444,
    CASE
        WHEN COUNT(*) FILTER (WHERE is_valid_for_features) >= 2
        THEN EXTRACT(EPOCH FROM (
            MAX(block_timestamp) FILTER (WHERE is_valid_for_features)
            - MIN(block_timestamp) FILTER (WHERE is_valid_for_features)
        )) / 86400.0
        ELSE NULL
    END AS tx_lifetime_days,
    CASE
        WHEN COUNT(*) FILTER (WHERE is_valid_for_features AND token_symbol = 'USDT') >= 5
        THEN (STDDEV_SAMP(amount) FILTER (WHERE is_valid_for_features AND token_symbol = 'USDT'))
             / NULLIF(AVG(amount) FILTER (WHERE is_valid_for_features AND token_symbol = 'USDT'), 0.0)
        ELSE NULL
    END AS amount_cv_usdt
FROM wallet_events
GROUP BY wallet_address;
