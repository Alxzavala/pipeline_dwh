variable "project_id" {
  type        = string
  description = "GCP project ID (set in terraform.tfvars, not committed)"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "bq_location" {
  type    = string
  default = "us-central1"
}

variable "billing_account_id" {
  type        = string
  description = "Billing account ID (set in terraform.tfvars, not committed)"
  sensitive   = true
}

variable "alert_email" {
  type        = string
  description = "Email for monitoring/budget alerts (set in terraform.tfvars, not committed)"
  sensitive   = true
}

variable "budget_amount_usd" {
  type    = number
  default = 2
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "github_repository" {
  type        = string
  description = "owner/repo en GitHub autorizado a asumir el Service Account via Workload Identity Federation"
}
