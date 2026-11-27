-- =============================================================================
-- L1 Step 2: Non-destructive hop-edge audit table for H5 graph sensitivity.
--
-- Source (read-only L0): illicit.wallet_hops
-- Joined to L1:          transform.clean_transactions
-- Target (derived L1):   transform.clean_wallet_hops
--
-- Directly executable in psql / DBeaver (no template placeholders).
-- Keeps 100% of illicit.wallet_hops rows (never silently drops hop-0 NULLs or
-- the ~108k edges whose via_tx_hash is absent from transactions). Adds explicit
-- via_tx_status so H5 can test sensitivity with/without dust or missing edges.
-- =============================================================================

DROP TABLE IF EXISTS transform.clean_wallet_hops;

CREATE TABLE transform.clean_wallet_hops AS
SELECT
    h.hop_id,
    h.wallet_address,
    h.seed_address,
    h.parent_address,
    h.via_tx_hash,
    h.hop_level,
    h.direction,
    h.discovered_at,
    CASE
        WHEN h.via_tx_hash IS NULL THEN 'null_hop0'
        WHEN tx.tx_hash IS NULL THEN 'missing_tx'
        ELSE tx.amount_flag
    END AS via_tx_status,
    tx.timestamp_flag AS via_tx_timestamp_flag,
    COALESCE(tx.is_1sun_dust, FALSE) AS via_tx_is_1sun_dust,
    COALESCE(tx.is_trx_4444_artifact, FALSE) AS via_tx_is_trx_4444_artifact
FROM illicit.wallet_hops h
LEFT JOIN transform.clean_transactions tx
    ON tx.tx_hash = h.via_tx_hash;
