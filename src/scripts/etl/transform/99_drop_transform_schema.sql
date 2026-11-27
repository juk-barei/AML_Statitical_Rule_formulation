-- =============================================================================
-- End-of-project cleanup: drop ONLY the derived transform schema.
--
-- Run ONLY AFTER:
--   1. Frozen Parquet snapshot exported under outputs/etl/load/phase1_transformed_*
--   2. manifest.json SHA-256 hashes verified
--   3. profile_stage.py --stage transformed & compare_stages.py passed
--
-- Strictly preserves L0 mirror schemas (illicit.*, licit.*).
-- =============================================================================

DROP SCHEMA IF EXISTS transform CASCADE;
