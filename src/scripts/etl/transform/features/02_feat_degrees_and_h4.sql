-- =============================================================================
-- L3 Step 2: Single directed-edge deduplication -> H3 counterparty degrees and
--            H4 Jaccard(TRX funders, USDT recipients).
--
-- Source (L1):  {transform_schema}.clean_transactions
-- Target (stg): {transform_schema}._stg_feat_degrees
--               {transform_schema}._stg_feat_h4
--
-- Decomposes distinct directed edges once so PostgreSQL never builds multiple
-- 50M-row COUNT(DISTINCT) hash tables concurrently under an 8 GB budget.
-- =============================================================================

DROP TABLE IF EXISTS {transform_schema}._stg_feat_h4;
DROP TABLE IF EXISTS {transform_schema}._stg_feat_degrees;
DROP TABLE IF EXISTS {transform_schema}._stg_distinct_edges;

CREATE TABLE {transform_schema}._stg_distinct_edges AS
SELECT
    from_address,
    to_address,
    BOOL_OR(token_symbol = 'USDT') AS has_usdt,
    BOOL_OR(token_symbol = 'TRX') AS has_trx,
    BOOL_OR(token_symbol = 'TRX' AND amount_flag <> 'dust') AS has_trx_nodust
FROM {transform_schema}.clean_transactions
WHERE is_valid_for_features
GROUP BY from_address, to_address;

CREATE TABLE {transform_schema}._stg_feat_degrees AS
WITH out_d AS (
    SELECT
        from_address AS wallet_address,
        COUNT(*)::BIGINT AS out_degree_all,
        COUNT(*) FILTER (WHERE has_usdt)::BIGINT AS out_degree_usdt
    FROM {transform_schema}._stg_distinct_edges
    GROUP BY from_address
),
in_d AS (
    SELECT
        to_address AS wallet_address,
        COUNT(*)::BIGINT AS in_degree_all,
        COUNT(*) FILTER (WHERE has_usdt)::BIGINT AS in_degree_usdt,
        COUNT(*) FILTER (WHERE has_trx)::BIGINT AS trx_funder_count,
        COUNT(*) FILTER (WHERE has_trx_nodust)::BIGINT AS trx_funder_count_nodust
    FROM {transform_schema}._stg_distinct_edges
    GROUP BY to_address
)
SELECT
    COALESCE(o.wallet_address, i.wallet_address) AS wallet_address,
    COALESCE(i.in_degree_all, 0)::BIGINT AS in_degree_all,
    COALESCE(o.out_degree_all, 0)::BIGINT AS out_degree_all,
    COALESCE(i.in_degree_usdt, 0)::BIGINT AS in_degree_usdt,
    COALESCE(o.out_degree_usdt, 0)::BIGINT AS out_degree_usdt,
    COALESCE(i.trx_funder_count, 0)::BIGINT AS trx_funder_count,
    COALESCE(i.trx_funder_count_nodust, 0)::BIGINT AS trx_funder_count_nodust
FROM out_d o
FULL OUTER JOIN in_d i
    ON o.wallet_address = i.wallet_address;

CREATE TABLE {transform_schema}._stg_feat_h4 AS
WITH eligible_w AS (
    SELECT
        wallet_address,
        trx_funder_count,
        out_degree_usdt AS usdt_recipient_count
    FROM {transform_schema}._stg_feat_degrees
    WHERE trx_funder_count > 0
      AND out_degree_usdt > 0
),
trx_f AS (
    SELECT e.to_address AS wallet_address, e.from_address AS counterparty
    FROM {transform_schema}._stg_distinct_edges e
    WHERE e.has_trx
      AND EXISTS (
          SELECT 1 FROM eligible_w w WHERE w.wallet_address = e.to_address
      )
),
usdt_r AS (
    SELECT e.from_address AS wallet_address, e.to_address AS counterparty
    FROM {transform_schema}._stg_distinct_edges e
    WHERE e.has_usdt
      AND EXISTS (
          SELECT 1 FROM eligible_w w WHERE w.wallet_address = e.from_address
      )
),
inter AS (
    SELECT t.wallet_address, COUNT(*)::DOUBLE PRECISION AS inter_cnt
    FROM trx_f t
    INNER JOIN usdt_r u
        ON t.wallet_address = u.wallet_address
       AND t.counterparty = u.counterparty
    GROUP BY t.wallet_address
)
SELECT
    w.wallet_address,
    COALESCE(i.inter_cnt, 0.0)
        / NULLIF((w.trx_funder_count + w.usdt_recipient_count - COALESCE(i.inter_cnt, 0.0))::DOUBLE PRECISION, 0.0)
        AS jaccard_index
FROM eligible_w w
LEFT JOIN inter i
    ON i.wallet_address = w.wallet_address;

DROP TABLE IF EXISTS {transform_schema}._stg_distinct_edges;
