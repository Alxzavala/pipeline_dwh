resource "google_bigquery_table" "stg_transacciones" {
  dataset_id          = google_bigquery_dataset.raw.dataset_id
  table_id            = "stg_transacciones"
  project             = var.project_id
  deletion_protection = false

  schema = jsonencode([
    { name = "tipo_identificacion", type = "STRING", mode = "NULLABLE" },
    { name = "numero_identificacion", type = "STRING", mode = "REQUIRED" },
    { name = "numero_cuenta", type = "STRING", mode = "NULLABLE" },
    { name = "nombres", type = "STRING", mode = "NULLABLE" },
    { name = "tipo_transaccion", type = "STRING", mode = "NULLABLE" },
    { name = "monto_transaccion", type = "NUMERIC", mode = "NULLABLE" },
    { name = "tipo_producto", type = "STRING", mode = "NULLABLE" },
    { name = "ciudad", type = "STRING", mode = "NULLABLE" },
    { name = "fecha_hora_transaccion", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "fecha_nacimiento", type = "DATE", mode = "NULLABLE" },
    { name = "direccion_cliente", type = "STRING", mode = "NULLABLE" },
    { name = "telefono_cliente", type = "STRING", mode = "NULLABLE" },
    { name = "correo_cliente", type = "STRING", mode = "NULLABLE" },
    { name = "reporte_centrales_riesgo", type = "BOOLEAN", mode = "NULLABLE" },
    { name = "monto_reporte_riesgo", type = "NUMERIC", mode = "NULLABLE" },
    { name = "tiempo_mora_riesgo_dias", type = "INTEGER", mode = "NULLABLE" },
    { name = "_batch_id", type = "STRING", mode = "REQUIRED" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_loaded_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])

  time_partitioning {
    type  = "DAY"
    field = "fecha_hora_transaccion"
  }

  depends_on = [google_project_service.required]
}

resource "google_bigquery_table" "rechazados" {
  dataset_id          = google_bigquery_dataset.raw.dataset_id
  table_id            = "rechazados"
  project             = var.project_id
  deletion_protection = false

  schema = jsonencode([
    { name = "fila_original", type = "STRING", mode = "NULLABLE" },
    { name = "motivo_rechazo", type = "STRING", mode = "REQUIRED" },
    { name = "_batch_id", type = "STRING", mode = "REQUIRED" },
    { name = "_loaded_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "dim_fecha" {
  dataset_id          = google_bigquery_dataset.marts.dataset_id
  table_id            = "dim_fecha"
  project             = var.project_id
  deletion_protection = false

  schema = jsonencode([
    { name = "sk_fecha", type = "INTEGER", mode = "REQUIRED" },
    { name = "fecha", type = "DATE", mode = "REQUIRED" },
    { name = "anio", type = "INTEGER", mode = "REQUIRED" },
    { name = "mes", type = "INTEGER", mode = "REQUIRED" },
    { name = "dia", type = "INTEGER", mode = "REQUIRED" },
    { name = "dia_semana", type = "STRING", mode = "REQUIRED" },
    { name = "es_fin_de_semana", type = "BOOLEAN", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "dim_producto" {
  dataset_id          = google_bigquery_dataset.marts.dataset_id
  table_id            = "dim_producto"
  project             = var.project_id
  deletion_protection = false

  schema = jsonencode([
    { name = "sk_producto", type = "INTEGER", mode = "REQUIRED" },
    { name = "tipo_producto", type = "STRING", mode = "REQUIRED" },
    { name = "_actualizado_en", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "dim_tipo_transaccion" {
  dataset_id          = google_bigquery_dataset.marts.dataset_id
  table_id            = "dim_tipo_transaccion"
  project             = var.project_id
  deletion_protection = false

  schema = jsonencode([
    { name = "sk_tipo_transaccion", type = "INTEGER", mode = "REQUIRED" },
    { name = "tipo_transaccion", type = "STRING", mode = "REQUIRED" },
    { name = "_actualizado_en", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "dim_ciudad" {
  dataset_id          = google_bigquery_dataset.marts.dataset_id
  table_id            = "dim_ciudad"
  project             = var.project_id
  deletion_protection = false

  schema = jsonencode([
    { name = "sk_ciudad", type = "INTEGER", mode = "REQUIRED" },
    { name = "ciudad", type = "STRING", mode = "REQUIRED" },
    { name = "_actualizado_en", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "dim_cliente" {
  dataset_id          = google_bigquery_dataset.marts.dataset_id
  table_id            = "dim_cliente"
  project             = var.project_id
  deletion_protection = false
  clustering          = ["numero_identificacion"]

  schema = jsonencode([
    { name = "sk_cliente", type = "INTEGER", mode = "REQUIRED" },
    { name = "numero_identificacion", type = "STRING", mode = "REQUIRED" },
    { name = "tipo_identificacion", type = "STRING", mode = "NULLABLE" },
    { name = "nombres", type = "STRING", mode = "NULLABLE" },
    { name = "fecha_nacimiento", type = "DATE", mode = "NULLABLE" },
    { name = "direccion", type = "STRING", mode = "NULLABLE", policyTags = { names = [google_data_catalog_policy_tag.pii_contacto.id] } },
    { name = "telefono", type = "STRING", mode = "NULLABLE", policyTags = { names = [google_data_catalog_policy_tag.pii_contacto.id] } },
    { name = "correo", type = "STRING", mode = "NULLABLE", policyTags = { names = [google_data_catalog_policy_tag.pii_contacto.id] } },
    { name = "correo_disponible", type = "BOOLEAN", mode = "REQUIRED" },
    { name = "fecha_inicio_vigencia", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "fecha_fin_vigencia", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "es_vigente", type = "BOOLEAN", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "dim_cuenta" {
  dataset_id          = google_bigquery_dataset.marts.dataset_id
  table_id            = "dim_cuenta"
  project             = var.project_id
  deletion_protection = false
  clustering          = ["numero_cuenta"]

  schema = jsonencode([
    { name = "sk_cuenta", type = "INTEGER", mode = "REQUIRED" },
    { name = "numero_cuenta", type = "STRING", mode = "REQUIRED" },
    { name = "sk_cliente", type = "INTEGER", mode = "NULLABLE" },
    { name = "sk_producto", type = "INTEGER", mode = "NULLABLE" },
    { name = "_actualizado_en", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "fact_transacciones" {
  dataset_id          = google_bigquery_dataset.marts.dataset_id
  table_id            = "fact_transacciones"
  project             = var.project_id
  deletion_protection = false
  clustering          = ["sk_cliente", "sk_producto"]

  schema = jsonencode([
    { name = "sk_transaccion", type = "STRING", mode = "REQUIRED" },
    { name = "sk_cliente", type = "INTEGER", mode = "NULLABLE" },
    { name = "sk_cuenta", type = "INTEGER", mode = "NULLABLE" },
    { name = "sk_producto", type = "INTEGER", mode = "NULLABLE" },
    { name = "sk_tipo_transaccion", type = "INTEGER", mode = "NULLABLE" },
    { name = "sk_ciudad", type = "INTEGER", mode = "NULLABLE" },
    { name = "sk_fecha", type = "INTEGER", mode = "NULLABLE" },
    { name = "fecha_hora_transaccion", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "monto_transaccion", type = "NUMERIC", mode = "NULLABLE" },
    { name = "reporte_centrales_riesgo", type = "BOOLEAN", mode = "NULLABLE" },
    { name = "monto_reporte_riesgo", type = "NUMERIC", mode = "NULLABLE" },
    { name = "tiempo_mora_riesgo_dias", type = "INTEGER", mode = "NULLABLE" },
    { name = "_batch_id", type = "STRING", mode = "REQUIRED" },
    { name = "_loaded_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])

  time_partitioning {
    type  = "DAY"
    field = "fecha_hora_transaccion"
  }
}
