-- ============================================================
--  Migration 002 — Prescription support
--  Run: mysql -u root -p mathurapharmeasy < migrations/002_prescription.sql
-- ============================================================

USE mathurapharmeasy;

-- Add prescription_url column to orders table (idempotent)
ALTER TABLE orders
  ADD COLUMN IF NOT EXISTS prescription_url VARCHAR(500) DEFAULT NULL
  AFTER notes;

-- Change default for requires_rx on medicines to 1 (Prescription Required)
ALTER TABLE medicines
  ALTER COLUMN requires_rx SET DEFAULT 1;
