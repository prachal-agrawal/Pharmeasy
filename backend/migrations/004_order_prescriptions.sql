-- ============================================================
--  Migration 004 — order_prescriptions mapping table
--
--  Replaces the single prescription_url JSON blob on the
--  orders row with a proper one-to-many child table so each
--  uploaded prescription image gets its own row.
--
--  Steps performed:
--    1. Create order_prescriptions table.
--    2. Back-fill rows for legacy orders that stored a plain
--       (non-JSON) URL directly in prescription_url.
--    3. Orders whose prescription_url starts with '[' contain
--       a JSON array — run migrate_rx_data.py to handle those.
--
--  Run:
--    mysql -u root -p mathurapharmeasy < migrations/004_order_prescriptions.sql
--    python backend/migrate_rx_data.py          # back-fills JSON-array orders
-- ============================================================

USE mathurapharmeasy;

-- 1. Create the mapping table (idempotent)
CREATE TABLE IF NOT EXISTS order_prescriptions (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_id   INT UNSIGNED NOT NULL,
  url        VARCHAR(500) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_order_url (order_id, url),
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  INDEX idx_order (order_id)
) ENGINE=InnoDB;

-- 2. Migrate legacy plain-string URLs (single prescription, not JSON)
INSERT IGNORE INTO order_prescriptions (order_id, url, created_at)
SELECT id, prescription_url, created_at
FROM   orders
WHERE  prescription_url IS NOT NULL
  AND  TRIM(prescription_url) != ''
  AND  LEFT(TRIM(prescription_url), 1) != '['
  AND  LEFT(TRIM(prescription_url), 1) != '"';

-- JSON-array orders (prescription_url LIKE '[%') are handled by
-- the Python script:  python backend/migrate_rx_data.py
