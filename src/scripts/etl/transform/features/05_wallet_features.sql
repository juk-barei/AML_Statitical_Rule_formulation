-- =============================================================================
-- L3 Step 5: Assemble flat wallet-grain L3 table transform.wallet_features
--            for ALL hypotheses (H1-H6), with explicit eligibility flags and
--            stateless log1p transforms only (no stateful ML scaling).
--
-- Source (L2 + stg):
--   {transform_schema}.cohort_wallet
--   {transform_schema}._stg_feat_scalar
--   {transform_schema}._stg_feat_degrees
--   {transform_schema}._stg_feat_h4
--   {transform_schema}._stg_feat_usdt_temporal
--   {transform_schema}._stg_feat_h6_cv
-- Target (L3):
--   {transform_schema}.wallet_features (1 row per wallet = cohort_wallet)
-- =============================================================================

DROP TABLE IF EXISTS {transform_schema}.wallet_features;

CREATE TABLE {transform_schema}.wallet_features AS
SELECT
    -- L2 cohort identity & provenance
    c.wallet_address,
    c.wallet_class,
    c.min_hop_level,
    c.max_hop_level,
    c.seed_count,
    c.hop_row_count,
    c.primary_seed_address,
    c.in_accounts_table,
    c.in_illicit_accounts,
    c.in_licit_accounts,
    c.is_licit_seed,
    c.is_contaminated_licit_seed,
    c.from_contaminated_licit_seed,

    -- Shared activity counts & volumes (fee_trx intentionally excluded)
    COALESCE(s.total_tx_count, 0)::BIGINT AS total_tx_count,
    COALESCE(s.zero_tx_count, 0)::BIGINT AS zero_tx_count,
    COALESCE(s.usdt_tx_count, 0)::BIGINT AS usdt_tx_count,
    COALESCE(s.trx_tx_count, 0)::BIGINT AS trx_tx_count,
    COALESCE(s.trx_tx_count_excl_4444, 0)::BIGINT AS trx_tx_count_excl_4444,
    COALESCE(s.trx_tx_count_nodust, 0)::BIGINT AS trx_tx_count_nodust,
    s.usdt_volume,
    s.usdt_in_volume,
    s.usdt_out_volume,
    s.trx_volume,
    s.trx_volume_excl_4444,

    -- H3 counterparty degrees, fan-out/in ratio, and amount CV
    COALESCE(d.in_degree_all, 0)::BIGINT AS in_degree_all,
    COALESCE(d.out_degree_all, 0)::BIGINT AS out_degree_all,
    COALESCE(d.in_degree_usdt, 0)::BIGINT AS in_degree_usdt,
    COALESCE(d.out_degree_usdt, 0)::BIGINT AS out_degree_usdt,
    CASE
        WHEN COALESCE(d.in_degree_usdt, 0) + COALESCE(d.out_degree_usdt, 0) > 0
        THEN (COALESCE(d.out_degree_usdt, 0) + 1.0) / (COALESCE(d.in_degree_usdt, 0) + 1.0)
        ELSE NULL
    END AS fan_out_in_ratio_usdt,
    s.amount_cv_usdt,

    -- H1 pass-through speed & in/out ratio
    CASE
        WHEN s.usdt_in_volume > 0 AND s.usdt_out_volume > 0
        THEN s.usdt_out_volume / NULLIF(s.usdt_in_volume, 0.0)
        ELSE NULL
    END AS in_out_vol_ratio_usdt,
    u.min_passthrough_sec_usdt,
    CASE
        WHEN u.min_passthrough_sec_usdt IS NOT NULL
        THEN CASE WHEN u.min_passthrough_sec_usdt <= 900.0 THEN 1.0 ELSE 0.0 END
        ELSE NULL
    END AS h1_pass_15m,

    -- H2 lifetime & USDT burst ratio (both >=5 gate and >=1 sensitivity)
    s.tx_lifetime_days,
    u.burst_ratio_usdt,
    u.burst_ratio_usdt_any,
    CASE
        WHEN s.tx_lifetime_days IS NOT NULL AND u.burst_ratio_usdt IS NOT NULL
        THEN CASE WHEN s.tx_lifetime_days <= 7.0 AND u.burst_ratio_usdt >= 0.75 THEN 1.0 ELSE 0.0 END
        ELSE NULL
    END AS h2_pass_ge5,
    CASE
        WHEN u.burst_ratio_usdt_any IS NOT NULL
        THEN CASE WHEN COALESCE(s.tx_lifetime_days, 0.0) <= 7.0 AND u.burst_ratio_usdt_any >= 0.75 THEN 1.0 ELSE 0.0 END
        ELSE NULL
    END AS h2_pass_any_usdt,

    -- H4 TRX-funder / USDT-recipient Jaccard
    j.jaccard_index,
    CASE
        WHEN j.jaccard_index IS NOT NULL
        THEN CASE WHEN j.jaccard_index >= 0.50 THEN 1.0 ELSE 0.0 END
        ELSE NULL
    END AS h4_pass,

    -- H6 inter-arrival CV (all-direction and OUT-only directional sensitivity)
    h6.cv_delta_t_all,
    h6.cv_delta_t_out,
    CASE
        WHEN h6.cv_delta_t_all IS NOT NULL
        THEN CASE WHEN h6.cv_delta_t_all < 0.15 THEN 1.0 ELSE 0.0 END
        ELSE NULL
    END AS h6_pass_all,
    CASE
        WHEN h6.cv_delta_t_out IS NOT NULL
        THEN CASE WHEN h6.cv_delta_t_out < 0.15 THEN 1.0 ELSE 0.0 END
        ELSE NULL
    END AS h6_pass_out,

    -- Stateless monotonic transforms ONLY (stateful ML scaling stays in statistical_learning/)
    CASE WHEN s.tx_lifetime_days IS NOT NULL THEN LN(1.0 + s.tx_lifetime_days) ELSE NULL END AS log1p_tx_lifetime_days,
    CASE WHEN h6.cv_delta_t_all IS NOT NULL THEN LN(1.0 + h6.cv_delta_t_all) ELSE NULL END AS log1p_cv_delta_t_all,
    CASE WHEN h6.cv_delta_t_out IS NOT NULL THEN LN(1.0 + h6.cv_delta_t_out) ELSE NULL END AS log1p_cv_delta_t_out,
    CASE WHEN s.usdt_volume IS NOT NULL THEN LN(1.0 + s.usdt_volume) ELSE NULL END AS log1p_usdt_volume,
    CASE WHEN s.trx_volume IS NOT NULL THEN LN(1.0 + s.trx_volume) ELSE NULL END AS log1p_trx_volume,
    LN(1.0 + COALESCE(s.total_tx_count, 0)::DOUBLE PRECISION) AS log1p_total_tx_count,
    CASE WHEN u.min_passthrough_sec_usdt IS NOT NULL THEN LN(1.0 + u.min_passthrough_sec_usdt) ELSE NULL END AS log1p_min_passthrough_sec_usdt,

    -- Explicit eligibility gates for downstream n-flow accounting
    (u.min_passthrough_sec_usdt IS NOT NULL) AS elig_h1,
    (s.tx_lifetime_days IS NOT NULL AND u.burst_ratio_usdt IS NOT NULL) AS elig_h2_ge5,
    (u.burst_ratio_usdt_any IS NOT NULL) AS elig_h2_any,
    (s.amount_cv_usdt IS NOT NULL) AS elig_h3,
    (j.jaccard_index IS NOT NULL) AS elig_h4,
    (h6.cv_delta_t_all IS NOT NULL) AS elig_h6_all,
    (h6.cv_delta_t_out IS NOT NULL) AS elig_h6_out
FROM {transform_schema}.cohort_wallet c
LEFT JOIN {transform_schema}._stg_feat_scalar s
    ON s.wallet_address = c.wallet_address
LEFT JOIN {transform_schema}._stg_feat_degrees d
    ON d.wallet_address = c.wallet_address
LEFT JOIN {transform_schema}._stg_feat_h4 j
    ON j.wallet_address = c.wallet_address
LEFT JOIN {transform_schema}._stg_feat_usdt_temporal u
    ON u.wallet_address = c.wallet_address
LEFT JOIN {transform_schema}._stg_feat_h6_cv h6
    ON h6.wallet_address = c.wallet_address
ORDER BY c.wallet_class, c.wallet_address;

-- Post-materialization PK + cleanup of intermediate staging tables
ALTER TABLE {transform_schema}.wallet_features
    ADD CONSTRAINT pk_wallet_features PRIMARY KEY (wallet_address);

DROP TABLE IF EXISTS {transform_schema}._stg_feat_scalar;
DROP TABLE IF EXISTS {transform_schema}._stg_feat_degrees;
DROP TABLE IF EXISTS {transform_schema}._stg_feat_h4;
DROP TABLE IF EXISTS {transform_schema}._stg_feat_usdt_temporal;
DROP TABLE IF EXISTS {transform_schema}._stg_feat_h6_cv;
