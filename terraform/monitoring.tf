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

resource "google_billing_budget" "cost_guard" {
  billing_account = var.billing_account_id
  display_name    = "budget-prueba-tecnica-dwh"

  budget_filter {
    projects = ["projects/${var.project_id}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_amount_usd)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  all_updates_rule {
    monitoring_notification_channels = [google_monitoring_notification_channel.email.id]
    disable_default_iam_recipients   = false
  }
}
