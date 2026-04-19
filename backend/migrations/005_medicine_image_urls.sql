-- Multiple product images per medicine (ordered gallery). Primary display URL
-- remains `image_url` (first image), synced by the API.

ALTER TABLE medicines
  ADD COLUMN image_urls JSON NULL
    COMMENT 'JSON array of /uploads/... paths'
    AFTER image_url;

UPDATE medicines
SET image_urls = JSON_ARRAY(image_url)
WHERE image_url IS NOT NULL
  AND TRIM(image_url) != ''
  AND image_urls IS NULL;
