-- =============================================================================
-- L2 Step 2: Post-materialization primary key and join indexes on transform.cohort_wallet.
--
-- Created strictly AFTER bulk CREATE TABLE AS; never touches L0 mirror schemas.
-- =============================================================================

ALTER TABLE transform.cohort_wallet
    ADD CONSTRAINT pk_cohort_wallet PRIMARY KEY (wallet_address);

ALTER TABLE transform.cohort_wallet
    ADD CONSTRAINT chk_cohort_wallet_class
    CHECK (wallet_class IN ('illicit', 'suspicious', 'licit', 'unlabeled'));

ALTER TABLE transform.cohort_wallet
    ADD CONSTRAINT chk_cohort_hop_nesting
    CHECK (
        (wallet_class = 'suspicious' AND min_hop_level BETWEEN 1 AND 5)
        OR (wallet_class <> 'suspicious' AND min_hop_level IS NULL)
    );

CREATE INDEX IF NOT EXISTS idx_cohort_wallet_class
    ON transform.cohort_wallet (wallet_class);

CREATE INDEX IF NOT EXISTS idx_cohort_primary_seed
    ON transform.cohort_wallet (primary_seed_address)
    WHERE primary_seed_address IS NOT NULL;
