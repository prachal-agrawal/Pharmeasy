-- ============================================================
--  MathuraPharmeasy — Complete MySQL Schema v2
--  Run: mysql -u root -p < schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS mathurapharmeasy CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mathurapharmeasy;

-- ── Users ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(100) NOT NULL,
  email         VARCHAR(150) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  phone         VARCHAR(15),
  role          ENUM('customer','admin') NOT NULL DEFAULT 'customer',
  is_active     TINYINT(1) NOT NULL DEFAULT 1,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_email (email),
  INDEX idx_role  (role)
) ENGINE=InnoDB;

-- ── Addresses ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS addresses (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id    INT UNSIGNED NOT NULL,
  label      VARCHAR(50)  DEFAULT 'Home',
  name       VARCHAR(100) NOT NULL,
  phone      VARCHAR(15),
  line1      VARCHAR(200) NOT NULL,
  line2      VARCHAR(200),
  city       VARCHAR(100) NOT NULL,
  state      VARCHAR(100) NOT NULL,
  pin        VARCHAR(10)  NOT NULL,
  is_default TINYINT(1)   NOT NULL DEFAULT 0,
  created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_user (user_id)
) ENGINE=InnoDB;

-- ── Categories ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS categories (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(100) NOT NULL UNIQUE,
  slug       VARCHAR(100) NOT NULL UNIQUE,
  icon       VARCHAR(10),
  sort_order INT UNSIGNED DEFAULT 0
) ENGINE=InnoDB;

-- ── Medicines ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medicines (
  id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name             VARCHAR(200) NOT NULL,
  brand            VARCHAR(100) NOT NULL,
  salt_composition VARCHAR(300) DEFAULT NULL,
  manufacturer     VARCHAR(200) DEFAULT NULL,
  category_id      INT UNSIGNED NOT NULL,
  description      TEXT,
  uses             TEXT,
  side_effects     TEXT,
  safety_points    TEXT,
  warning          TEXT,
  requires_rx      TINYINT(1)   NOT NULL DEFAULT 1,
  is_active        TINYINT(1)   NOT NULL DEFAULT 1,
  image_url        VARCHAR(500),
  image_urls       JSON NULL COMMENT 'Ordered list of /uploads/... paths',
  rating           DECIMAL(3,2) DEFAULT 0.00,
  rating_count     INT UNSIGNED DEFAULT 0,
  created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (category_id) REFERENCES categories(id),
  FULLTEXT idx_search (name, brand, description, uses),
  INDEX idx_category (category_id),
  INDEX idx_active   (is_active)
) ENGINE=InnoDB;

-- ── Generic Alternatives ──────────────────────────────────────
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

-- ── Medicine Variants ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medicine_variants (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  medicine_id INT UNSIGNED NOT NULL,
  label       VARCHAR(100) NOT NULL,
  mrp         DECIMAL(10,2) NOT NULL,
  price       DECIMAL(10,2) NOT NULL,
  stock       INT UNSIGNED  NOT NULL DEFAULT 0,
  sku         VARCHAR(100)  UNIQUE,
  sort_order  INT UNSIGNED  DEFAULT 0,
  FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE,
  INDEX idx_medicine (medicine_id)
) ENGINE=InnoDB;

-- ── Orders ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
  id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_number     VARCHAR(20)  NOT NULL UNIQUE,
  user_id          INT UNSIGNED NOT NULL,
  address_id       INT UNSIGNED,
  address_snapshot JSON,
  status           ENUM('pending','confirmed','dispatched','delivered','cancelled') NOT NULL DEFAULT 'pending',
  subtotal         DECIMAL(10,2) NOT NULL,
  delivery_charge  DECIMAL(10,2) NOT NULL DEFAULT 0,
  discount         DECIMAL(10,2) NOT NULL DEFAULT 0,
  total            DECIMAL(10,2) NOT NULL,
  payment_method   ENUM('upi','card','cod','netbanking') NOT NULL DEFAULT 'cod',
  payment_status   ENUM('pending','paid','failed','refunded') NOT NULL DEFAULT 'pending',
  payment_ref      VARCHAR(200),
  notes            TEXT,
  prescription_url TEXT,                       -- JSON array of uploaded image URLs
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id)    REFERENCES users(id),
  FOREIGN KEY (address_id) REFERENCES addresses(id) ON DELETE SET NULL,
  INDEX idx_user    (user_id),
  INDEX idx_status  (status),
  INDEX idx_created (created_at)
) ENGINE=InnoDB;

-- ── Order Items ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_items (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_id      INT UNSIGNED NOT NULL,
  variant_id    INT UNSIGNED NOT NULL,
  medicine_id   INT UNSIGNED NOT NULL,
  name          VARCHAR(200)  NOT NULL,
  variant_label VARCHAR(100)  NOT NULL,
  price         DECIMAL(10,2) NOT NULL,
  quantity      INT UNSIGNED  NOT NULL DEFAULT 1,
  subtotal      DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (order_id)   REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (variant_id) REFERENCES medicine_variants(id),
  INDEX idx_order (order_id)
) ENGINE=InnoDB;

-- ── Order Status Log ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_status_log (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_id   INT UNSIGNED NOT NULL,
  status     VARCHAR(50)  NOT NULL,
  note       TEXT,
  changed_by INT UNSIGNED,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id)   REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (changed_by) REFERENCES users(id)  ON DELETE SET NULL
) ENGINE=InnoDB;

-- ── Cart Items ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cart_items (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id    INT UNSIGNED NOT NULL,
  variant_id INT UNSIGNED NOT NULL,
  quantity   INT UNSIGNED NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_user_variant (user_id, variant_id),
  FOREIGN KEY (user_id)    REFERENCES users(id)             ON DELETE CASCADE,
  FOREIGN KEY (variant_id) REFERENCES medicine_variants(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── Invoices ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invoices (
  id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_id       INT UNSIGNED NOT NULL UNIQUE,
  invoice_number VARCHAR(30)  NOT NULL UNIQUE,
  issued_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  pdf_url        VARCHAR(500),
  FOREIGN KEY (order_id) REFERENCES orders(id)
) ENGINE=InnoDB;

-- ── Order Prescriptions (one-to-many: one order → many images) ──
CREATE TABLE IF NOT EXISTS order_prescriptions (
  id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_id   INT UNSIGNED NOT NULL,
  url        VARCHAR(500) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_order_url (order_id, url),
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  INDEX idx_order (order_id)
) ENGINE=InnoDB;

-- ═════════════════════════════════════════════════════════════
--  SEED DATA
-- ═════════════════════════════════════════════════════════════

-- Admin user  (password = Admin@123)
INSERT INTO users (name, email, password_hash, role) VALUES
('Admin', 'admin@mathurapharmeasy.in',
 '$2b$12$Ep/HBov/HY/CYeQKQgnIPe5I3ypC8WuVW/r9YV1V/4kUxruwAsqPS',
 'admin')
ON DUPLICATE KEY UPDATE id=id;

-- Categories
INSERT INTO categories (name, slug, icon, sort_order) VALUES
('Pain Relief',   'pain-relief',  '💊', 1),
('Antibiotics',   'antibiotics',  '🔵', 2),
('Allergy',       'allergy',      '🌿', 3),
('Gastro',        'gastro',       '🟢', 4),
('Diabetes',      'diabetes',     '❤️', 5),
('Cardiac',       'cardiac',      '💗', 6),
('Supplements',   'supplements',  '☀️', 7),
('Gels & Sprays', 'gels-sprays',  '🧴', 8)
ON DUPLICATE KEY UPDATE id=id;

-- 10 Core Medicines
INSERT INTO medicines (name, brand, salt_composition, manufacturer, category_id, uses, side_effects, safety_points, warning, requires_rx, rating, rating_count) VALUES
('Paracetamol 500mg','Dolo / Calpol','Paracetamol (500mg)','Micro Labs Ltd',1,
 'Fever, mild to moderate pain, headache, body ache',
 '["Nausea (rare)","Rash or allergic reaction","Liver damage if overdosed","Stomach pain in high doses"]',
 '["Do not exceed 4g/day for adults","Avoid alcohol while taking","Safe in pregnancy when directed","Keep away from children"]',
 'Overdose can cause serious liver damage. Do not combine with other paracetamol products.',
 0, 4.6, 12340),

('Azithromycin','Zithromax / Azee','Azithromycin (500mg)','Pfizer Ltd',2,
 'Bacterial infections: chest, throat, ear, skin',
 '["Nausea and vomiting","Diarrhoea","Stomach cramps","Dizziness","Allergic reaction (rare)"]',
 '["Complete the full course","Take on empty stomach","Avoid antacids within 2 hrs","Tell doctor of heart conditions"]',
 'Prescription required. Avoid if allergic to macrolide antibiotics.',
 1, 4.3, 3812),

('Cetirizine','Zyrtec / Cetzine','Cetirizine Hydrochloride (10mg)','UCB India Pvt Ltd',3,
 'Hay fever, allergic rhinitis, hives, itching, watery eyes',
 '["Drowsiness (common)","Dry mouth","Headache","Fatigue","Mild stomach pain"]',
 '["Avoid driving if drowsy","Do not exceed 10mg/day","Safe for adults and children 6+","Avoid alcohol"]',
 'May cause drowsiness. Use caution while operating machinery.',
 0, 4.4, 6721),

('Pantoprazole','Pantop / Pan-D','Pantoprazole Sodium (40mg)','Alkem Laboratories',4,
 'Peptic ulcer, GERD, erosive esophagitis, H.pylori (combo)',
 '["Headache","Diarrhoea","Nausea","Flatulence","Abdominal pain"]',
 '["Take 30-60 mins before breakfast","Do not chew tablet","Short courses preferred","Long-term needs monitoring"]',
 'Long-term use over 12 weeks should be under medical supervision.',
 0, 4.2, 4503),

('Metformin','Glucophage / Glycomet','Metformin Hydrochloride (500mg)','Merck Ltd',5,
 'Type 2 diabetes, PCOS, pre-diabetes',
 '["Nausea initially","Diarrhoea","Stomach upset","Metallic taste","Lactic acidosis (rare)"]',
 '["Take with meals","Monitor kidney function","Pause before contrast scans","Do not use if eGFR below 30"]',
 'Prescription required. Stop if you experience muscle pain or difficulty breathing.',
 1, 4.5, 8902),

('Amlodipine','Norvasc / Amlong','Amlodipine Besylate (5mg)','Pfizer Ltd',6,
 'High blood pressure, angina, coronary artery disease',
 '["Ankle swelling","Flushing","Headache","Dizziness","Palpitations"]',
 '["Take at same time daily","Do not stop suddenly","Monitor BP weekly","Avoid grapefruit juice"]',
 'Prescription required. Do not stop abruptly — may cause rebound hypertension.',
 1, 4.4, 5612),

('Vitamin D3','Calcirol / Uprise','Cholecalciferol (60000 IU)','Elder Pharmaceuticals',7,
 'Vitamin D deficiency, bone health, immunity support',
 '["Nausea if overdosed","Constipation","Weakness","High calcium toxicity (rare)"]',
 '["One sachet per week not daily","Take with fatty meal","Check blood levels every 3 months","Avoid excess without blood test"]',
 'Vitamin D toxicity possible with excessive doses. Confirm deficiency with blood test first.',
 0, 4.5, 9234),

('Ibuprofen','Brufen / Combiflam','Ibuprofen (400mg)','Abbott India Ltd',1,
 'Pain, inflammation, fever, menstrual cramps, arthritis',
 '["Stomach irritation","Nausea","Heartburn","Dizziness","Kidney strain at high doses"]',
 '["Always take with food","Avoid on empty stomach","Not for children under 6 months","Avoid in last trimester"]',
 'Can worsen kidney function. Avoid if you have stomach ulcers or kidney disease.',
 0, 4.3, 7823),

('Omnigel Pain Relief Gel','Cipla Health','Diclofenac Diethylamine (1.16% w/w) + Linseed Oil + Methyl Salicylate + Menthol','Cipla Ltd',8,
 'Sprain, back pain, muscle pain, body pain, knee pain, joint pain',
 '["Skin irritation at application site","Redness or rash","Allergic reaction (rare)"]',
 '["Apply thin layer to affected area","Do not apply on open wounds","Wash hands after application","Avoid contact with eyes"]',
 'For external use only. Do not bandage tightly after application.',
 0, 4.5, 3603),

('Amoxicillin','Mox / Novamox','Amoxicillin (500mg)','GlaxoSmithKline Pharmaceuticals',2,
 'Throat, chest, ear, urinary tract, skin infections',
 '["Diarrhoea (very common)","Nausea","Rash","Allergic reaction","Yeast infection"]',
 '["Complete full course","Take with or without food","Tell doctor if penicillin allergic","Probiotics help reduce GI effects"]',
 'Prescription required. Penicillin allergy — do NOT take. Severe allergic reactions possible.',
 1, 4.2, 4201);

-- 3 Generic/Cheaper Alternatives
INSERT INTO medicines (name, brand, salt_composition, manufacturer, category_id, uses, side_effects, safety_points, warning, requires_rx, rating, rating_count) VALUES
('Calpol 650mg Tablet','GlaxoSmithKline','Paracetamol (650mg)','GlaxoSmithKline Pharmaceuticals',1,
 'Fever, mild to moderate pain, headache, body ache',
 '["Nausea (rare)","Rash or allergic reaction","Liver damage if overdosed"]',
 '["Do not exceed 4g/day for adults","Avoid alcohol while taking","Keep away from children"]',
 'Overdose can cause serious liver damage.',
 0, 4.3, 5420),

('Cetcip 10mg Tablet','Cipla Ltd','Cetirizine Hydrochloride (10mg)','Cipla Ltd',3,
 'Hay fever, allergic rhinitis, hives, itching, watery eyes',
 '["Drowsiness (common)","Dry mouth","Headache","Fatigue"]',
 '["Avoid driving if drowsy","Do not exceed 10mg/day","Avoid alcohol"]',
 'May cause drowsiness. Use caution while operating machinery.',
 0, 4.2, 3100),

('Ibugesic 400mg Tablet','Cipla Ltd','Ibuprofen (400mg)','Cipla Ltd',1,
 'Pain, inflammation, fever, menstrual cramps, arthritis',
 '["Stomach irritation","Nausea","Heartburn","Dizziness"]',
 '["Always take with food","Avoid on empty stomach","Not for children under 6 months"]',
 'Can worsen kidney function. Avoid if you have stomach ulcers or kidney disease.',
 0, 4.1, 2890);

-- Variants for each medicine
-- 1: Paracetamol
INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order) VALUES
(1,'500mg Strip of 15',  30.00,  28.00, 500, 'PARA-500-15',  1),
(1,'500mg Box of 100',  180.00, 165.00, 200, 'PARA-500-100', 2),
(1,'650mg Strip of 15',  35.00,  32.00, 400, 'PARA-650-15',  3);

-- 2: Azithromycin
INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order) VALUES
(2,'250mg Strip of 6',  200.00, 185.00,  80, 'AZITH-250-6', 1),
(2,'500mg Strip of 3',  210.00, 195.00,  60, 'AZITH-500-3', 2),
(2,'500mg Strip of 5',  340.00, 310.00,  40, 'AZITH-500-5', 3);

-- 3: Cetirizine
INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order) VALUES
(3,'10mg Strip of 10',   50.00,  45.00, 300, 'CETZ-10-10',  1),
(3,'10mg Strip of 30',  140.00, 125.00, 150, 'CETZ-10-30',  2),
(3,'5mg Syrup 60ml',     80.00,  72.00, 100, 'CETZ-5-SYR',  3);

-- 4: Pantoprazole
INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order) VALUES
(4,'40mg Strip of 15',   90.00,  78.00, 200, 'PANTO-40-15', 1),
(4,'40mg Box of 30',    170.00, 148.00, 100, 'PANTO-40-30', 2);

-- 5: Metformin
INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order) VALUES
(5,'500mg Strip of 20',  65.00,  55.00, 120, 'MET-500-20',  1),
(5,'850mg Strip of 20',  80.00,  68.00,  80, 'MET-850-20',  2),
(5,'1000mg Strip of 20', 95.00,  82.00,  60, 'MET-1000-20', 3);

-- 6: Amlodipine
INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order) VALUES
(6,'5mg Strip of 30',   130.00, 120.00,  80, 'AMLO-5-30',  1),
(6,'10mg Strip of 30',  175.00, 160.00,  50, 'AMLO-10-30', 2);

-- 7: Vitamin D3
INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order) VALUES
(7,'60K IU Sachet x4',   45.00,  38.00, 600, 'VITD3-60K-4',  1),
(7,'60K IU Sachet x8',   85.00,  72.00, 400, 'VITD3-60K-8',  2),
(7,'1000 IU Tab x60',   220.00, 195.00, 200, 'VITD3-1K-60',  3);

-- 8: Ibuprofen
INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order) VALUES
(8,'400mg Strip of 15',  38.00,  32.00, 350, 'IBU-400-15',  1),
(8,'400mg Box of 100',  220.00, 195.00, 150, 'IBU-400-100', 2),
(8,'200mg Syrup 100ml',  65.00,  58.00, 120, 'IBU-200-SYR', 3);

-- 9: Omnigel (all 6 sizes like the screenshot)
INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order) VALUES
(9,'10 gm Gel',    50.00,  41.10, 200, 'OMNI-10G',  1),
(9,'20 gm Gel',    85.00,  68.90, 180, 'OMNI-20G',  2),
(9,'30 gm Gel',   120.00,  96.80, 150, 'OMNI-30G',  3),
(9,'50 gm Gel',   160.00, 129.00, 120, 'OMNI-50G',  4),
(9,'75 gm Gel',   215.00, 173.00,  80, 'OMNI-75G',  5),
(9,'100 gm Gel',  245.00, 196.00,  60, 'OMNI-100G', 6);

-- 10: Amoxicillin
INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order) VALUES
(10,'250mg Strip of 10',  90.00,  78.00, 100, 'AMOX-250-10', 1),
(10,'500mg Strip of 10', 155.00, 140.00,  80, 'AMOX-500-10', 2),
(10,'500mg Box of 20',   295.00, 265.00,  50, 'AMOX-500-20', 3);

-- 11: Calpol 650mg (generic alternative to Paracetamol 500mg)
INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order) VALUES
(11,'650mg Strip of 15',  29.10, 22.40, 600, 'CALPOL-650-15',  1),
(11,'650mg Box of 100',  175.00,140.00, 300, 'CALPOL-650-100', 2);

-- 12: Cetcip 10mg (generic alternative to Cetirizine)
INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order) VALUES
(12,'10mg Strip of 10',  38.00, 32.00, 500, 'CETCIP-10-10', 1),
(12,'10mg Strip of 30', 105.00, 86.00, 250, 'CETCIP-10-30', 2);

-- 13: Ibugesic 400mg (generic alternative to Ibuprofen)
INSERT INTO medicine_variants (medicine_id, label, mrp, price, stock, sku, sort_order) VALUES
(13,'400mg Strip of 15',  30.00, 24.00, 450, 'IBUG-400-15',  1),
(13,'400mg Box of 100',  180.00,145.00, 200, 'IBUG-400-100', 2);

-- ── Generic Alternatives Mapping ─────────────────────────────
-- Paracetamol 500mg (1) → Calpol 650mg (11)
-- Cetirizine (3)        → Cetcip 10mg (12)
-- Ibuprofen (8)         → Ibugesic 400mg (13)
INSERT INTO medicine_alternatives (source_medicine_id, alternative_medicine_id) VALUES
(1, 11),
(3, 12),
(8, 13)
ON DUPLICATE KEY UPDATE is_active=1;
