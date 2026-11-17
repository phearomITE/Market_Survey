-- CMFB Market Survey: Rename EXPREZ Can 500ml ORD -> EXPREZ Can ORD and EXPREZ Can 500ml NCP -> EXPREZ Can NCP
-- Safe to run more than once on PostgreSQL.

WITH product_map(old_name, new_name) AS (
    VALUES
        ('EXPREZ Can 500ml ORD', 'EXPREZ Can ORD'),
        ('EXPREZ Can 500ml NCP', 'EXPREZ Can NCP'),
        ('EXPREZ Can 500ml', 'EXPREZ Can ORD'),
        ('EXPREZ Can 330ml ORD', 'EXPREZ Can ORD'),
        ('EXPREZ Can 330ml NCP', 'EXPREZ Can NCP'),
        ('EXPREZ Can 330ml', 'EXPREZ Can ORD'),
        ('EXPREZ Can', 'EXPREZ Can ORD')
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
    'EXPREZ Can 500ml ORD',
    'EXPREZ Can 500ml NCP',
    'EXPREZ Can 500ml',
    'EXPREZ Can 330ml ORD',
    'EXPREZ Can 330ml NCP',
    'EXPREZ Can 330ml'
);

WITH comp_map(old_name, new_name) AS (
    VALUES
        ('EXPREZ Can 500ml ORD', 'EXPREZ Can ORD'),
        ('EXPREZ Can 500ml', 'EXPREZ Can ORD'),
        ('EXPREZ Can 330ml ORD', 'EXPREZ Can ORD'),
        ('EXPREZ Can 330ml', 'EXPREZ Can ORD')
)
UPDATE kobo_competitor_metrics old_row
SET product_name = comp_map.new_name
FROM comp_map
WHERE old_row.product_name = comp_map.old_name
  AND NOT EXISTS (
      SELECT 1
      FROM kobo_competitor_metrics new_row
      WHERE new_row.submission_id = old_row.submission_id
        AND new_row.product_name = comp_map.new_name
  );

DELETE FROM kobo_competitor_metrics
WHERE product_name IN (
    'EXPREZ Can 500ml ORD',
    'EXPREZ Can 500ml',
    'EXPREZ Can 330ml ORD',
    'EXPREZ Can 330ml'
);
