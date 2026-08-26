-- KB Market Survey V34: align database with the exact report-template products.
-- Safe to run more than once on PostgreSQL.

ALTER TABLE IF EXISTS kobo_competitor_metrics
    ADD COLUMN IF NOT EXISTS stock_status VARCHAR(80);

-- Own products: update only when the target row does not already exist.
WITH product_map(old_name, new_name) AS (
    VALUES
        ('CBC 4.4', 'CBC 4.4 NCP'),
        ('CB Original', 'CB Original NCP'),
        ('CB LITE', 'CB LITE NCP'),
        ('CB BLACK', 'CB BLACK NCP'),
        ('ភេសជ្ជៈប៉ូវកម្លាំង​កម្ពុជា', 'CAMBODIA ED'),
        ('EXPREZ ត្រសក់ផ្អែម', 'EXPREZ Melon')
)
UPDATE kobo_product_metrics old_row
SET product_name = product_map.new_name
FROM product_map
WHERE old_row.product_name = product_map.old_name
  AND NOT EXISTS (
      SELECT 1
      FROM kobo_product_metrics new_row
      WHERE new_row.submission_id = old_row.submission_id
        AND new_row.product_name = product_map.new_name
  );

DELETE FROM kobo_product_metrics
WHERE product_name IN (
    'CBC 4.4', 'CB Original', 'CB LITE', 'CB BLACK',
    'ភេសជ្ជៈប៉ូវកម្លាំង​កម្ពុជា', 'EXPREZ ត្រសក់ផ្អែម'
);

-- Competitors: old generic beer names map to the NCP versions.
WITH competitor_map(old_name, new_name) AS (
    VALUES
        ('GB Original', 'GB Original NCP'),
        ('GB  Original', 'GB Original NCP'),
        ('GB SNOW', 'GB SNOW NCP'),
        ('Hanuman Lite', 'Hanuman LITE NCP'),
        ('Krud', 'Krud NCP'),
        ('Krud Lite', 'Krud LITE NCP'),
        ('Greet Lite', 'Greet LITE NCP'),
        ('Great Lite', 'Greet LITE NCP'),
        ('Hanuman Black', 'Hanuman Black NCP')
)
UPDATE kobo_competitor_metrics old_row
SET product_name = competitor_map.new_name
FROM competitor_map
WHERE old_row.product_name = competitor_map.old_name
  AND NOT EXISTS (
      SELECT 1
      FROM kobo_competitor_metrics new_row
      WHERE new_row.submission_id = old_row.submission_id
        AND new_row.product_name = competitor_map.new_name
  );

DELETE FROM kobo_competitor_metrics
WHERE product_name IN (
    'GB Original', 'GB  Original', 'GB SNOW', 'Hanuman Lite',
    'Krud', 'Krud Lite', 'Greet Lite', 'Great Lite', 'Hanuman Black'
);
