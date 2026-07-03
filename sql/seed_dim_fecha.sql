INSERT INTO `pelagic-plexus-360917.marts.dim_fecha`
SELECT
  CAST(FORMAT_DATE('%Y%m%d', d) AS INT64) AS sk_fecha,
  d AS fecha,
  EXTRACT(YEAR FROM d) AS anio,
  EXTRACT(MONTH FROM d) AS mes,
  EXTRACT(DAY FROM d) AS dia,
  FORMAT_DATE('%A', d) AS dia_semana,
  EXTRACT(DAYOFWEEK FROM d) IN (1, 7) AS es_fin_de_semana
FROM UNNEST(GENERATE_DATE_ARRAY('2020-01-01', '2030-12-31', INTERVAL 1 DAY)) AS d;
