from datetime import datetime, timezone

from google.cloud import bigquery

from pipeline.config import Config

DIM_PRODUCTO_MERGE = """
MERGE `{project}.{marts}.dim_producto` AS target
USING (
  SELECT DISTINCT tipo_producto
  FROM `{project}.{raw}.stg_transacciones`
  WHERE _batch_id = @batch_id AND tipo_producto IS NOT NULL
) AS source
ON target.tipo_producto = source.tipo_producto
WHEN NOT MATCHED THEN
  INSERT (sk_producto, tipo_producto, _actualizado_en)
  VALUES (FARM_FINGERPRINT(source.tipo_producto), source.tipo_producto, CURRENT_TIMESTAMP())
"""

DIM_TIPO_TRANSACCION_MERGE = """
MERGE `{project}.{marts}.dim_tipo_transaccion` AS target
USING (
  SELECT DISTINCT tipo_transaccion
  FROM `{project}.{raw}.stg_transacciones`
  WHERE _batch_id = @batch_id AND tipo_transaccion IS NOT NULL
) AS source
ON target.tipo_transaccion = source.tipo_transaccion
WHEN NOT MATCHED THEN
  INSERT (sk_tipo_transaccion, tipo_transaccion, _actualizado_en)
  VALUES (FARM_FINGERPRINT(source.tipo_transaccion), source.tipo_transaccion, CURRENT_TIMESTAMP())
"""

DIM_CIUDAD_MERGE = """
MERGE `{project}.{marts}.dim_ciudad` AS target
USING (
  SELECT DISTINCT ciudad
  FROM `{project}.{raw}.stg_transacciones`
  WHERE _batch_id = @batch_id AND ciudad IS NOT NULL
) AS source
ON target.ciudad = source.ciudad
WHEN NOT MATCHED THEN
  INSERT (sk_ciudad, ciudad, _actualizado_en)
  VALUES (FARM_FINGERPRINT(source.ciudad), source.ciudad, CURRENT_TIMESTAMP())
"""

DIM_CLIENTE_CLOSE_CHANGED = """
UPDATE `{project}.{marts}.dim_cliente` AS target
SET fecha_fin_vigencia = @load_ts, es_vigente = FALSE
WHERE es_vigente = TRUE
  AND numero_identificacion IN (
    SELECT s.numero_identificacion
    FROM `{project}.{raw}.stg_transacciones` s
    JOIN `{project}.{marts}.dim_cliente` dc
      ON dc.numero_identificacion = s.numero_identificacion AND dc.es_vigente = TRUE
    WHERE s._batch_id = @batch_id
      AND (
        COALESCE(dc.direccion, '') != COALESCE(s.direccion_cliente, '')
        OR COALESCE(dc.telefono, '') != COALESCE(s.telefono_cliente, '')
        OR COALESCE(dc.correo, '') != COALESCE(s.correo_cliente, '')
        OR COALESCE(dc.nombres, '') != COALESCE(s.nombres, '')
      )
  )
"""

DIM_CLIENTE_INSERT_NEW = """
INSERT INTO `{project}.{marts}.dim_cliente`
  (sk_cliente, numero_identificacion, tipo_identificacion, nombres, fecha_nacimiento,
   direccion, telefono, correo, correo_disponible, fecha_inicio_vigencia, fecha_fin_vigencia, es_vigente)
SELECT
  FARM_FINGERPRINT(CONCAT(s.numero_identificacion, '|', CAST(@load_ts AS STRING))),
  s.numero_identificacion,
  ANY_VALUE(s.tipo_identificacion),
  ANY_VALUE(s.nombres),
  ANY_VALUE(s.fecha_nacimiento),
  ANY_VALUE(s.direccion_cliente),
  ANY_VALUE(s.telefono_cliente),
  ANY_VALUE(s.correo_cliente),
  ANY_VALUE(s.correo_cliente) IS NOT NULL,
  @load_ts,
  CAST(NULL AS TIMESTAMP),
  TRUE
FROM `{project}.{raw}.stg_transacciones` s
WHERE s._batch_id = @batch_id
  AND s.numero_identificacion NOT IN (
    SELECT numero_identificacion FROM `{project}.{marts}.dim_cliente` WHERE es_vigente = TRUE
  )
GROUP BY s.numero_identificacion
"""

DIM_CUENTA_MERGE = """
MERGE `{project}.{marts}.dim_cuenta` AS target
USING (
  SELECT DISTINCT
    s.numero_cuenta,
    dc.sk_cliente,
    FARM_FINGERPRINT(s.tipo_producto) AS sk_producto
  FROM `{project}.{raw}.stg_transacciones` s
  JOIN `{project}.{marts}.dim_cliente` dc
    ON dc.numero_identificacion = s.numero_identificacion AND dc.es_vigente = TRUE
  WHERE s._batch_id = @batch_id AND s.numero_cuenta IS NOT NULL
) AS source
ON target.numero_cuenta = source.numero_cuenta
WHEN MATCHED THEN
  UPDATE SET sk_cliente = source.sk_cliente, sk_producto = source.sk_producto,
             _actualizado_en = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (sk_cuenta, numero_cuenta, sk_cliente, sk_producto, _actualizado_en)
  VALUES (FARM_FINGERPRINT(source.numero_cuenta), source.numero_cuenta, source.sk_cliente,
          source.sk_producto, CURRENT_TIMESTAMP())
"""

FACT_TRANSACCIONES_MERGE = """
MERGE `{project}.{marts}.fact_transacciones` AS target
USING (
  SELECT
    TO_HEX(SHA256(CONCAT(
      s.numero_identificacion, '|', COALESCE(s.numero_cuenta, ''), '|', s.tipo_transaccion, '|',
      CAST(s.fecha_hora_transaccion AS STRING), '|', CAST(s.monto_transaccion AS STRING)
    ))) AS sk_transaccion,
    dc.sk_cliente,
    dcu.sk_cuenta,
    FARM_FINGERPRINT(s.tipo_producto) AS sk_producto,
    FARM_FINGERPRINT(s.tipo_transaccion) AS sk_tipo_transaccion,
    FARM_FINGERPRINT(s.ciudad) AS sk_ciudad,
    CAST(FORMAT_DATE('%Y%m%d', DATE(s.fecha_hora_transaccion)) AS INT64) AS sk_fecha,
    s.fecha_hora_transaccion,
    s.monto_transaccion,
    s.reporte_centrales_riesgo,
    s.monto_reporte_riesgo,
    s.tiempo_mora_riesgo_dias,
    s._batch_id
  FROM `{project}.{raw}.stg_transacciones` s
  LEFT JOIN `{project}.{marts}.dim_cliente` dc
    ON dc.numero_identificacion = s.numero_identificacion AND dc.es_vigente = TRUE
  LEFT JOIN `{project}.{marts}.dim_cuenta` dcu
    ON dcu.numero_cuenta = s.numero_cuenta
  WHERE s._batch_id = @batch_id AND s.fecha_hora_transaccion IS NOT NULL
) AS source
ON target.sk_transaccion = source.sk_transaccion
WHEN NOT MATCHED THEN
  INSERT (sk_transaccion, sk_cliente, sk_cuenta, sk_producto, sk_tipo_transaccion, sk_ciudad, sk_fecha,
          fecha_hora_transaccion, monto_transaccion, reporte_centrales_riesgo, monto_reporte_riesgo,
          tiempo_mora_riesgo_dias, _batch_id, _loaded_at)
  VALUES (source.sk_transaccion, source.sk_cliente, source.sk_cuenta, source.sk_producto,
          source.sk_tipo_transaccion, source.sk_ciudad, source.sk_fecha, source.fecha_hora_transaccion,
          source.monto_transaccion, source.reporte_centrales_riesgo, source.monto_reporte_riesgo,
          source.tiempo_mora_riesgo_dias, source._batch_id, CURRENT_TIMESTAMP())
"""

ORDERED_TRANSFORM_STEPS = [
    DIM_PRODUCTO_MERGE,
    DIM_TIPO_TRANSACCION_MERGE,
    DIM_CIUDAD_MERGE,
    DIM_CLIENTE_CLOSE_CHANGED,
    DIM_CLIENTE_INSERT_NEW,
    DIM_CUENTA_MERGE,
    FACT_TRANSACCIONES_MERGE,
]


def run_dimensional_transform(config: Config, batch_id: str) -> None:
    client = bigquery.Client(project=config.project_id)
    load_ts_iso = datetime.now(timezone.utc).isoformat()

    for template in ORDERED_TRANSFORM_STEPS:
        sql = template.format(
            project=config.project_id, raw=config.raw_dataset, marts=config.marts_dataset
        )
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("batch_id", "STRING", batch_id),
                bigquery.ScalarQueryParameter("load_ts", "TIMESTAMP", load_ts_iso),
            ]
        )
        client.query(sql, job_config=job_config).result()
