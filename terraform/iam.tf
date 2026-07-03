resource "google_service_account" "pipeline" {
  account_id   = "dwh-pipeline-sa"
  display_name = "Service Account - Pipeline ETL DWH Bancario"
  project      = var.project_id
}

resource "google_project_iam_member" "pipeline_bq_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_storage_bucket_iam_member" "pipeline_bucket_admin" {
  bucket = google_storage_bucket.raw_zone.name
  # storage.admin (not objectAdmin) so Terraform can read/manage bucket-level
  # metadata (storage.buckets.get/getIamPolicy) for the google_storage_bucket
  # resource itself, not just objects inside it.
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

# The same identity doubles as the CI/CD Terraform runner (via WIF, restricted
# to this exact GitHub repo — see the WIF provider's attribute_condition
# below), so it also needs permission to manage the infra this repo declares:
# API enablement, monitoring/logging resources, IAM bindings, and the state
# bucket itself. A dedicated Terraform-only SA would be a cleaner separation
# of runtime-vs-infra-admin duties, but is out of scope for this exercise.
resource "google_storage_bucket_iam_member" "pipeline_tfstate_admin" {
  bucket = "pelagic-plexus-360917-tfstate"
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_monitoring_editor" {
  project = var.project_id
  role    = "roles/monitoring.editor"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_logging_config_writer" {
  project = var.project_id
  role    = "roles/logging.configWriter"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_serviceusage_admin" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageAdmin"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_workload_identity_pool_admin" {
  project = var.project_id
  role    = "roles/iam.workloadIdentityPoolAdmin"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_service_account_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_project_iam_admin" {
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

# Needed for CI's Terraform apply to manage google_data_catalog_taxonomy /
# google_data_catalog_policy_tag (data_governance.tf) - distinct from the
# per-tag categoryFineGrainedReader role granted there, which only lets the
# SA read PII values at query time, not manage the taxonomy resource itself.
resource "google_project_iam_member" "pipeline_datacatalog_admin" {
  project = var.project_id
  role    = "roles/datacatalog.categoryAdmin"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions-pool"
  project                   = var.project_id
  display_name              = "GitHub Actions Pool"

  depends_on = [google_project_service.required]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  project                            = var.project_id
  display_name                       = "GitHub Actions Provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "wif_binding" {
  service_account_id = google_service_account.pipeline.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}
