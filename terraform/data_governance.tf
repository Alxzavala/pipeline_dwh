# Column-level security for PII in dim_cliente (correo, telefono, direccion).
# Uses BigQuery's native mechanism: a Data Catalog policy tag attached to the
# column. Any principal without the fine-grained reader role below gets a
# permission-denied error querying these columns at all (no value, masked or
# otherwise) - BigQuery's stricter "deny" mode rather than a masking policy.
#
# A masking policy (replacing the value with a SHA256 hash instead of denying
# access outright) was the original design, but google_bigquery_datapolicy_data_policy
# requires the project to belong to a Cloud Identity/Workspace organization -
# this project is a personal GCP account with no organization, so that
# resource can't be created here. In a production setup under an
# organization, add it back to swap "deny" for "hash".
#
# The pipeline service account IS granted the fine-grained reader role,
# because pipeline/transform.py's SCD2 change detection
# (COALESCE(dc.telefono, '') != COALESCE(s.telefono_cliente, '')) needs to
# read real values, not be denied access to its own MERGE logic.

resource "google_data_catalog_taxonomy" "pii" {
  project                = var.project_id
  region                 = var.bq_location
  display_name           = "dwh-pii-taxonomy"
  description            = "Clasificacion de PII para el DWH bancario"
  activated_policy_types = ["FINE_GRAINED_ACCESS_CONTROL"]

  depends_on = [google_project_service.required]
}

resource "google_data_catalog_policy_tag" "pii_contacto" {
  taxonomy     = google_data_catalog_taxonomy.pii.id
  display_name = "PII - Datos de contacto"
  description  = "Correo, telefono y direccion del cliente"
}

# The pipeline SA needs to see real values to do SCD2 change detection.
resource "google_data_catalog_policy_tag_iam_member" "pipeline_pii_reader" {
  policy_tag = google_data_catalog_policy_tag.pii_contacto.name
  role       = "roles/datacatalog.categoryFineGrainedReader"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
}
