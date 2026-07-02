resource "google_monitoring_notification_channel" "email" {
  project      = var.project_id
  display_name = "Alerta pipeline DWH - email"
  type         = "email"

  labels = {
    email_address = var.alert_email
  }
}

resource "google_logging_metric" "pipeline_failures" {
  project = var.project_id
  name    = "pipeline_dwh_failures"
  filter  = "resource.type=\"global\" AND jsonPayload.event=\"pipeline_failed\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_monitoring_alert_policy" "pipeline_failure_alert" {
  project      = var.project_id
  display_name = "Fallo en pipeline de ingesta DWH bancario"
  combiner     = "OR"

  conditions {
    display_name = "pipeline_dwh_failures > 0"

    condition_threshold {
      filter          = "resource.type=\"global\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.pipeline_failures.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_COUNT"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]

  depends_on = [google_project_service.required]
}

# NOTE: this resource is intentionally NOT managed by Terraform (commented out).
# `terraform apply` failed with a 400 INVALID_ARGUMENT: the "ML" billing account's
# currency is MXN, not USD (var.budget_amount_usd/"USD" hardcoded below mismatched
# the account's actual currency). It was also blocked separately by an ADC
# "quota project" error from the billingbudgets API client. Created manually
# instead via the documented fallback:
#   gcloud billing budgets create --billing-account=REDACTED-BILLING-ACCOUNT-ID \
#     --display-name=budget-prueba-tecnica-dwh --budget-amount=40MXN \
#     --threshold-rule=percent=0.5 --threshold-rule=percent=1.0 \
#     --filter-projects=projects/pelagic-plexus-360917
#   gcloud billing budgets update <budget-name> \
#     --notifications-rule-monitoring-notification-channels=<email channel id>
# Live budget: billingAccounts/REDACTED-BILLING-ACCOUNT-ID/budgets/b32d7ea2-5920-483d-92b5-c77da17a2b88
# (~$2 USD equivalent at 40 MXN, same two threshold rules, same email notification channel).
#
# resource "google_billing_budget" "cost_guard" {
#   billing_account = var.billing_account_id
#   display_name    = "budget-prueba-tecnica-dwh"
#
#   budget_filter {
#     projects = ["projects/${var.project_id}"]
#   }
#
#   amount {
#     specified_amount {
#       currency_code = "USD"
#       units         = tostring(var.budget_amount_usd)
#     }
#   }
#
#   threshold_rules {
#     threshold_percent = 0.5
#   }
#   threshold_rules {
#     threshold_percent = 1.0
#   }
#
#   all_updates_rule {
#     monitoring_notification_channels = [google_monitoring_notification_channel.email.id]
#     disable_default_iam_recipients   = false
#   }
# }
