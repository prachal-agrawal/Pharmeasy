-- ============================================================
--  Migration 001 — Generic Alternatives Infrastructure
--  Run ONCE against an existing mathurapharmeasy database:
--    mysql -u root -p mathurapharmeasy < migrations/001_generic_alternatives.sql
-- ============================================================

USE medkart;

-- ── 1. Extend medicines with composition + manufacturer ────────
-- (Safe to re-run: each ALTER is guarded by a check in the procedure below)
DROP PROCEDURE IF EXISTS _add_col_if_missing;
DELIMITER $$
CREATE PROCEDURE _add_col_if_missing()
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'medicines' AND COLUMN_NAME = 'salt_composition'
  ) THEN
    ALTER TABLE medicines ADD COLUMN salt_composition VARCHAR(300) DEFAULT NULL AFTER brand;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'medicines' AND COLUMN_NAME = 'manufacturer'
  ) THEN
    ALTER TABLE medicines ADD COLUMN manufacturer VARCHAR(200) DEFAULT NULL AFTER salt_composition;
  END IF;
END$$
DELIMITER ;
CALL _add_col_if_missing();
DROP PROCEDURE IF EXISTS _add_col_if_missing;

-- ── 2. Generic Alternatives mapping table ────────────────────
CREATE TABLE IF NOT EXISTS medicine_alternatives (
  id                      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  source_medicine_id      INT UNSIGNED NOT NULL COMMENT 'The branded / pricier medicine',
  alternative_medicine_id INT UNSIGNED NOT NULL COMMENT 'The generic / cheaper alternative',
  is_active               TINYINT(1)   NOT NULL DEFAULT 1,
  created_at              DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_source_alt (source_medicine_id, alternative_medicine_id),
  FOREIGN KEY (source_medicine_id)      REFERENCES medicines(id) ON DELETE CASCADE,
  FOREIGN KEY (alternative_medicine_id) REFERENCES medicines(id) ON DELETE CASCADE,
  INDEX idx_source (source_medicine_id)
) ENGINE=InnoDB;

-- ── 3. Seed: salt_composition + manufacturer on existing meds ─
UPDATE medicines SET
  salt_composition = 'Paracetamol (500mg)',
  manufacturer     = 'Micro Labs Ltd'
WHERE id = 1;  -- Paracetamol 500mg / Dolo-Calpol

UPDATE medicines SET
  salt_composition = 'Azithromycin (500mg)',
  manufacturer     = 'Pfizer Ltd'
WHERE id = 2;  -- Azithromycin / Zithromax

UPDATE medicines SET
  salt_composition = 'Cetirizine Hydrochloride (10mg)',
  manufacturer     = 'UCB India Pvt Ltd'
WHERE id = 3;  -- Cetirizine / Zyrtec

UPDATE medicines SET
  salt_composition = 'Pantoprazole Sodium (40mg)',
  manufacturer     = 'Alkem Laboratories'
WHERE id = 4;  -- Pantoprazole / Pantop

UPDATE medicines SET
  salt_composition = 'Metformin Hydrochloride (500mg)',
  manufacturer     = 'Merck Ltd'
WHERE id = 5;  -- Metformin / Glucophage

UPDATE medicines SET
  salt_composition = 'Amlodipine Besylate (5mg)',
  manufacturer     = 'Pfizer Ltd'
WHERE id = 6;  -- Amlodipine / Norvasc

UPDATE medicines SET
  salt_composition = 'Cholecalciferol (60000 IU)',
  manufacturer     = 'Elder Pharmaceuticals'
WHERE id = 7;  -- Vitamin D3

UPDATE medicines SET
  salt_composition = 'Ibuprofen (400mg)',
  manufacturer     = 'Abbott India Ltd'
WHERE id = 8;  -- Ibuprofen / Brufen

UPDATE medicines SET
  salt_composition = 'Diclofenac Diethylamine (1.16% w/w) + Linseed Oil + Methyl Salicylate + Menthol',
  manufacturer     = 'Cipla Ltd'
WHERE id = 9;  -- Omnigel

UPDATE medicines SET
  salt_composition = 'Amoxicillin (500mg)',
  manufacturer     = 'GlaxoSmithKline Pharmaceuticals'
WHERE id = 10;  -- Amoxicillin / Mox

-- ── 4. Add generic medicines (cheaper alternatives) ───────────
-- Generic Paracetamol 650mg (cheaper version of med id=1 but 650mg)
INSERT INTO medicines (name, brand, category_id, salt_composition, manufacturer, uses, side_effects, safety_points, warning, requires_rx, rating, rating_count)
VALUES (
  'Calpol 650mg Tablet',
  'GlaxoSmithKline',
  1,
  'Paracetamol (650mg)',
  'GlaxoSmithKline Pharmaceuticals',
  'Fever, mild to moderate pain, headache, body ache',
  '["Nausea (rare)","Rash or allergic reaction","Liver damage if overdosed"]',
  '["Do not exceed 4g/day for adults","Avoid alcohol while taking","Keep away from children"]',
  'Overdose can cause serious liver damage.',
  0, 4.3, 5420
)
ON DUPLICATE KEY UPDATE id=id;

SET @calpol_id = LAST_INSERT_ID();

INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order)
SELECT @calpol_id,'650mg Strip of 15', 29.10, 22.40, 600, 'CALPOL-650-15', 1
WHERE @calpol_id > 0
ON DUPLICATE KEY UPDATE id=id;

INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order)
SELECT @calpol_id,'650mg Box of 100', 175.00, 140.00, 300, 'CALPOL-650-100', 2
WHERE @calpol_id > 0
ON DUPLICATE KEY UPDATE id=id;

-- Generic Cetirizine (cheaper alternative to med id=3)
INSERT INTO medicines (name, brand, category_id, salt_composition, manufacturer, uses, side_effects, safety_points, warning, requires_rx, rating, rating_count)
VALUES (
  'Cetcip 10mg Tablet',
  'Cipla Ltd',
  3,
  'Cetirizine Hydrochloride (10mg)',
  'Cipla Ltd',
  'Hay fever, allergic rhinitis, hives, itching, watery eyes',
  '["Drowsiness (common)","Dry mouth","Headache","Fatigue"]',
  '["Avoid driving if drowsy","Do not exceed 10mg/day","Avoid alcohol"]',
  'May cause drowsiness. Use caution while operating machinery.',
  0, 4.2, 3100
)
ON DUPLICATE KEY UPDATE id=id;

SET @cetcip_id = LAST_INSERT_ID();

INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order)
SELECT @cetcip_id,'10mg Strip of 10', 38.00, 32.00, 500, 'CETCIP-10-10', 1
WHERE @cetcip_id > 0
ON DUPLICATE KEY UPDATE id=id;

-- Generic Ibuprofen (cheaper alternative to med id=8)
INSERT INTO medicines (name, brand, category_id, salt_composition, manufacturer, uses, side_effects, safety_points, warning, requires_rx, rating, rating_count)
VALUES (
  'Ibugesic 400mg Tablet',
  'Cipla Ltd',
  1,
  'Ibuprofen (400mg)',
  'Cipla Ltd',
  'Pain, inflammation, fever, menstrual cramps, arthritis',
  '["Stomach irritation","Nausea","Heartburn","Dizziness"]',
  '["Always take with food","Avoid on empty stomach","Not for children under 6 months"]',
  'Can worsen kidney function. Avoid if you have stomach ulcers or kidney disease.',
  0, 4.1, 2890
)
ON DUPLICATE KEY UPDATE id=id;

SET @ibugesic_id = LAST_INSERT_ID();

INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order)
SELECT @ibugesic_id,'400mg Strip of 15', 30.00, 24.00, 450, 'IBUG-400-15', 1
WHERE @ibugesic_id > 0
ON DUPLICATE KEY UPDATE id=id;

-- ── 5. Wire up the alternatives ───────────────────────────────
-- Paracetamol 500mg (id=1) → Calpol 650mg
INSERT IGNORE INTO medicine_alternatives (source_medicine_id, alternative_medicine_id)
SELECT 1, id FROM medicines WHERE name='Calpol 650mg Tablet' LIMIT 1;

-- Cetirizine (id=3) → Cetcip
INSERT IGNORE INTO medicine_alternatives (source_medicine_id, alternative_medicine_id)
SELECT 3, id FROM medicines WHERE name='Cetcip 10mg Tablet' LIMIT 1;

-- Ibuprofen (id=8) → Ibugesic
INSERT IGNORE INTO medicine_alternatives (source_medicine_id, alternative_medicine_id)
SELECT 8, id FROM medicines WHERE name='Ibugesic 400mg Tablet' LIMIT 1;
