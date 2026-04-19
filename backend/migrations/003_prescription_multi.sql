-- ============================================================
--  Migration 003 — Multi-prescription support
--  Widens prescription_url to TEXT so it can hold a JSON array
--  of uploaded prescription image URLs.
--
--  Run:
--    mysql -u root -p mathurapharmeasy < migrations/003_prescription_multi.sql
-- ============================================================

USE mathurapharmeasy;

-- Widen column to TEXT (idempotent — MODIFY is safe to re-run)
ALTER TABLE orders
  MODIFY COLUMN prescription_url TEXT DEFAULT NULL;
