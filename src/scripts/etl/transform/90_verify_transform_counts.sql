-- =============================================================================
-- Read-only Verification SQL: Run after L1 (clean), L2 (cohort), and L3 (features)
-- Directly executable line-by-line in psql / DBeaver. Zero writes.
-- =============================================================================

-- 1. L1 row count & dedupe check (expected: 26,189,701 unique tx_hash)
SELECT
    COUNT(*) AS deduped_tx_rows,
    COUNT(*) FILTER (WHERE in_both_schemas) AS overlap_tx_hash,
    COUNT(*) FILTER (WHERE has_cross_schema_conflict) AS conflict_tx_hash,
    COUNT(*) FILTER (WHERE is_valid_for_features) AS valid_for_features,
    COUNT(*) FILTER (WHERE is_trx_4444_artifact) AS trx_4444_artifact_rows
FROM transform.clean_transactions;

-- 2. L1 flag breakdown by source_schema & token_symbol
SELECT
    source_schema,
    token_symbol,
    amount_flag,
    timestamp_flag,
    COUNT(*) AS rows
FROM transform.clean_transactions
GROUP BY source_schema, token_symbol, amount_flag, timestamp_flag
ORDER BY source_schema, token_symbol, amount_flag, timestamp_flag;

-- 3. L1 hop-edge audit check (expected: 6,965,210 rows, zero dropped)
SELECT via_tx_status, COUNT(*) AS hop_rows
FROM transform.clean_wallet_hops
GROUP BY via_tx_status
ORDER BY hop_rows DESC;

-- 4. L2 cohort partition check (expected total: 9,876,867)
SELECT
    wallet_class,
    COUNT(*) AS wallets_total,
    COUNT(*) FILTER (WHERE in_accounts_table) AS wallets_in_accounts,
    COUNT(*) FILTER (WHERE NOT in_accounts_table) AS wallets_hop_only,
    COUNT(*) FILTER (WHERE is_contaminated_licit_seed) AS contaminated_licit_seeds
FROM transform.cohort_wallet
GROUP BY wallet_class
ORDER BY wallet_class;

-- 5. L2 hop-nesting invariant check (MUST return 0)
SELECT COUNT(*) AS hop_nesting_violations
FROM transform.cohort_wallet
WHERE (wallet_class = 'suspicious' AND (min_hop_level IS NULL OR min_hop_level NOT BETWEEN 1 AND 5))
   OR (wallet_class <> 'suspicious' AND min_hop_level IS NOT NULL);

-- 6. L3 row-count parity with L2 cohort_wallet (diff MUST be 0)
SELECT
    (SELECT COUNT(*) FROM transform.cohort_wallet) AS l2_rows,
    (SELECT COUNT(*) FROM transform.wallet_features) AS l3_rows,
    (SELECT COUNT(*) FROM transform.wallet_features) - (SELECT COUNT(*) FROM transform.cohort_wallet) AS row_diff;

-- 7. L3 eligibility summary by wallet_class (H1-H6)
SELECT
    wallet_class,
    COUNT(*) AS n_cohort,
    COUNT(*) FILTER (WHERE elig_h1) AS n_elig_h1,
    COUNT(*) FILTER (WHERE elig_h2_ge5) AS n_elig_h2_ge5,
    COUNT(*) FILTER (WHERE elig_h2_any) AS n_elig_h2_any,
    COUNT(*) FILTER (WHERE elig_h3) AS n_elig_h3,
    COUNT(*) FILTER (WHERE elig_h4) AS n_elig_h4,
    COUNT(*) FILTER (WHERE elig_h6_all) AS n_elig_h6_all,
    COUNT(*) FILTER (WHERE elig_h6_out) AS n_elig_h6_out
FROM transform.wallet_features
GROUP BY wallet_class
ORDER BY wallet_class;
