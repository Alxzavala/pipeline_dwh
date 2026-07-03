-- Parte 3: clientes mas rentables segun historial transaccional.
-- Optimizacion: filtro sobre fecha_hora_transaccion (columna de particionamiento de
-- fact_transacciones) habilita partition pruning; el JOIN por sk_cliente aprovecha
-- el clustering de ambas tablas (fact_transacciones y dim_cliente).
SELECT
  dc.numero_identificacion,
  dc.nombres,
  COUNT(DISTINCT f.sk_transaccion) AS total_transacciones,
  COUNT(DISTINCT f.sk_producto) AS productos_distintos,
  ROUND(SUM(f.monto_transaccion), 2) AS volumen_transaccional_total,
  ROUND(AVG(f.monto_transaccion), 2) AS ticket_promedio,
  COUNTIF(f.reporte_centrales_riesgo) AS transacciones_con_reporte_riesgo,
  ROUND(
    SUM(f.monto_transaccion)
      * (1 + 0.1 * COUNT(DISTINCT f.sk_producto))
      * (1 - LEAST(0.5, SAFE_DIVIDE(COUNTIF(f.reporte_centrales_riesgo), COUNT(*)))),
    2
  ) AS score_rentabilidad
FROM `pelagic-plexus-360917.marts.fact_transacciones` AS f
JOIN `pelagic-plexus-360917.marts.dim_cliente` AS dc
  ON dc.sk_cliente = f.sk_cliente AND dc.es_vigente = TRUE
-- Ventana de 3 anios (en vez de los 365 dias tipicos de produccion) para que
-- este demo siga devolviendo resultados sobre el dataset de prueba (fechado
-- 2024-02-28); el patron de partition pruning sobre fecha_hora_transaccion
-- es el mismo independientemente del ancho de la ventana.
WHERE f.fecha_hora_transaccion >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1095 DAY)
GROUP BY dc.numero_identificacion, dc.nombres
ORDER BY score_rentabilidad DESC
LIMIT 20;
