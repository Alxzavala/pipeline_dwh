terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "pelagic-plexus-360917-tfstate"
    prefix = "dwh-pipeline"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  required_apis = [
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "billingbudgets.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "sts.googleapis.com",
  ]
}

resource "google_project_service" "required" {
  for_each           = toset(local.required_apis)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
