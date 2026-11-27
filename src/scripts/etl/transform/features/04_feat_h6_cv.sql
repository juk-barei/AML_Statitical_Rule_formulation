-- =============================================================================
-- L3 Step 4: H6 inter-arrival time CV (all clean non-zero events AND OUT-only
--            directional sensitivity).
--
-- Source (L1 + stg): {transform_schema}.clean_transactions, {transform_schema}._stg_feat_scalar
-- Target (stg):      {transform_schema}._stg_feat_h6_cv
--
-- Pre-filters to wallets with total_tx_count >= 5 via EXISTS so window sorting
-- skips the ~8.5M single-tx / inactive wallets.
-- =============================================================================

DROP TABLE IF EXISTS {transform_schema}._stg_feat_h6_cv;

CREATE TABLE {transform_schema}._stg_feat_h6_cv AS
WITH elig_all AS (
    SELECT wallet_address
    FROM {transform_schema}._stg_feat_scalar
    WHERE total_tx_count >= 5
),
events AS (
    SELECT
        t.from_address AS wallet_address,
        'OUT'::TEXT AS direction,
        t.block_timestamp,
        t.tx_hash
    FROM {transform_schema}.clean_transactions t
    WHERE t.is_valid_for_features
      AND EXISTS (SELECT 1 FROM elig_all e WHERE e.wallet_address = t.from_address)
    UNION ALL
    SELECT
        t.to_address AS wallet_address,
        'IN'::TEXT AS direction,
        t.block_timestamp,
        t.tx_hash
    FROM {transform_schema}.clean_transactions t
    WHERE t.is_valid_for_features
      AND EXISTS (SELECT 1 FROM elig_all e WHERE e.wallet_address = t.to_address)
),
all_gaps AS (
    SELECT
        wallet_address,
        EXTRACT(EPOCH FROM (
            block_timestamp - LAG(block_timestamp) OVER (
                PARTITION BY wallet_address
                ORDER BY block_timestamp ASC, tx_hash ASC
            )
        )) AS gap_sec
    FROM events
),
all_agg AS (
    SELECT
        wallet_address,
        CASE
            WHEN COUNT(*) >= 5
            THEN STDDEV_SAMP(gap_sec) / NULLIF(AVG(gap_sec), 0.0)
            ELSE NULL
        END AS cv_delta_t_all
    FROM all_gaps
    GROUP BY wallet_address
),
out_gaps AS (
    SELECT
        wallet_address,
        EXTRACT(EPOCH FROM (
            block_timestamp - LAG(block_timestamp) OVER (
                PARTITION BY wallet_address
                ORDER BY block_timestamp ASC, tx_hash ASC
            )
        )) AS gap_sec
    FROM events
    WHERE direction = 'OUT'
),
out_agg AS (
    SELECT
        wallet_address,
        CASE
            WHEN COUNT(*) >= 5
            THEN STDDEV_SAMP(gap_sec) / NULLIF(AVG(gap_sec), 0.0)
            ELSE NULL
        END AS cv_delta_t_out
    FROM out_gaps
    GROUP BY wallet_address
)
SELECT
    COALESCE(a.wallet_address, o.wallet_address) AS wallet_address,
    a.cv_delta_t_all,
    o.cv_delta_t_out
FROM all_agg a
FULL OUTER JOIN out_agg o
    ON a.wallet_address = o.wallet_address;
