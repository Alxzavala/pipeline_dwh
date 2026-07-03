from unittest.mock import patch

import pandas as pd
import pytest

from pipeline.config import Config
from pipeline.main import run_pipeline


@pytest.fixture
def config():
    return Config(
        project_id="test-project",
        bq_location="us-central1",
        raw_dataset="raw",
        marts_dataset="marts",
        raw_bucket="test-bucket",
    )


@patch("pipeline.main.run_dimensional_transform")
@patch("pipeline.main.load_dataframe_to_staging")
@patch("pipeline.main.upload_to_raw_bucket")
@patch("pipeline.main.pd.read_csv")
def test_run_pipeline_reports_counts(
    mock_read_csv, mock_upload, mock_load_staging, mock_transform, config, tmp_path
):
    mock_read_csv.return_value = pd.DataFrame(
        [
            {
                "tipo de identificación": "CC",
                "número de identificación": "1",
                "número de cuenta": "1",
                "nombres": "A",
                "tipo transacción": "COMPRA",
                "monto transacción": 1000.0,
                "tipo de producto": "CUENTA DE AHORROS",
                "ciudad": "CALI",
                "fecha-hora": "2024-02-28 10:00:00",
                "fecha de nacimiento": "1990-01-01 00:00:00",
                "dirección del cliente": "x",
                "teléfono del cliente": "300",
                "correo del cliente": "a@a.com",
                "reporte centrales de riesgo": False,
                "monto reporte de central de riesgo": 0.0,
                "tiempo en mora del reporte de riesgo": 0,
            }
        ]
    )
    mock_load_staging.return_value = 1

    result = run_pipeline(config, csv_path="fake.csv", batch_id="batch_test")

    assert result == {
        "batch_id": "batch_test",
        "filas_leidas": 1,
        "filas_validas": 1,
        "filas_rechazadas": 0,
    }
    mock_upload.assert_called_once()
    mock_transform.assert_called_once_with(config, batch_id="batch_test")
