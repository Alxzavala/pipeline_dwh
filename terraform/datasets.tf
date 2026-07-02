resource "google_bigquery_dataset" "raw" {
  dataset_id  = "raw"
  project     = var.project_id
  location    = var.bq_location
  description = "Zona de staging (landing) de datos crudos - simula la capa RAW del Data Lake"

  labels = {
    env   = var.environment
    layer = "raw"
  }

  depends_on = [google_project_service.required]
}

resource "google_bigquery_dataset" "marts" {
  dataset_id  = "marts"
  project     = var.project_id
  location    = var.bq_location
  description = "Modelo dimensional (esquema estrella) para analitica de transacciones bancarias"

  labels = {
    env   = var.environment
    layer = "marts"
  }

  depends_on = [google_project_service.required]
}
