-- =============================================================================
-- L1 Step 3: Post-materialization indexes on derived L1 tables ONLY.
--
-- Per AGENTS.md & src/scripts/etl/transform/README.md:
--   - NEVER index L0 mirror schemas (illicit.*, licit.*).
--   - Build join-key indexes on transform.* ONLY AFTER bulk CREATE TABLE AS.
--   - Optional for Parquet COPY export (sequential scan), useful for L1->L3
--     PostgreSQL joins and point validation queries.
-- =============================================================================

ALTER TABLE transform.clean_transactions
    ADD CONSTRAINT pk_clean_transactions PRIMARY KEY (tx_hash);

CREATE INDEX IF NOT EXISTS idx_clean_tx_from_address
    ON transform.clean_transactions (from_address)
    WHERE is_valid_for_features;

CREATE INDEX IF NOT EXISTS idx_clean_tx_to_address
    ON transform.clean_transactions (to_address)
    WHERE is_valid_for_features;

CREATE INDEX IF NOT EXISTS idx_clean_wallet_hops_wallet
    ON transform.clean_wallet_hops (wallet_address);
