import pandas as pd

from pipeline.quality import (
    TIPO_TRANSACCION_CATALOG,
    clean_dataframe,
    fix_mojibake,
    normalize_catalog_value,
)


def _sample_row(**overrides):
    row = {
        "tipo de identificaciÃ³n": "CC",
        "nÃºmero de identificaciÃ³n": "123456",
        "nÃºmero de cuenta": "999888",
        "nombres": "Cliente Prueba",
        "tipo transacciÃ³n": "COMPRA",
        "monto transacciÃ³n": 100000.0,
        "tipo de producto": "CUENTA DE AHORROS",
        "ciudad": "MEDELLÃN",
        "fecha-hora": "2024-02-28 10:00:00",
        "fecha de nacimiento": "1990-05-10 00:00:00",
        "direcciÃ³n del cliente": "Calle 1 #1-1",
        "telÃ©fono del cliente": "3000000000",
        "correo del cliente": "cliente@mail.com",
        "reporte centrales de riesgo": False,
        "monto reporte de central de riesgo": 0.0,
        "tiempo en mora del reporte de riesgo": 0,
    }
    row.update(overrides)
    return row


def test_fix_mojibake_restores_accents():
    assert fix_mojibake("identificaciÃ³n") == "identificación"


def test_fix_mojibake_leaves_clean_text_untouched():
    assert fix_mojibake("Cali") == "Cali"


def test_normalize_catalog_value_maps_variant_to_canonical():
    assert normalize_catalog_value("deposito", TIPO_TRANSACCION_CATALOG) == "DEPÓSITO"


def test_clean_dataframe_deduplicates_exact_duplicate_rows():
    df = pd.DataFrame([_sample_row(), _sample_row()])
    valid_df, rejected_df = clean_dataframe(df, batch_id="test-batch")
    assert len(valid_df) == 1
    assert len(rejected_df) == 0


def test_clean_dataframe_nulls_placeholder_birthdate():
    df = pd.DataFrame([_sample_row(**{"fecha de nacimiento": "1800-01-01 00:00:00"})])
    valid_df, _ = clean_dataframe(df, batch_id="test-batch")
    assert pd.isna(valid_df.iloc[0]["fecha_nacimiento"])


def test_clean_dataframe_rejects_underage_client():
    df = pd.DataFrame([_sample_row(**{"fecha de nacimiento": "2020-01-01 00:00:00"})])
    valid_df, rejected_df = clean_dataframe(df, batch_id="test-batch")
    assert len(valid_df) == 0
    assert rejected_df.iloc[0]["motivo_rechazo"] == "edad_invalida"


def test_clean_dataframe_rejects_non_positive_amount():
    df = pd.DataFrame([_sample_row(**{"monto transacciÃ³n": 0.0})])
    valid_df, rejected_df = clean_dataframe(df, batch_id="test-batch")
    assert len(valid_df) == 0
    assert rejected_df.iloc[0]["motivo_rechazo"] == "monto_invalido"


def test_clean_dataframe_normalizes_city_variants():
    df = pd.DataFrame([_sample_row(**{"ciudad": "MEDELLIN"})])
    valid_df, _ = clean_dataframe(df, batch_id="test-batch")
    assert valid_df.iloc[0]["ciudad"] == "MEDELLÍN"


def test_clean_dataframe_marks_missing_email():
    df = pd.DataFrame([_sample_row(**{"correo del cliente": None})])
    valid_df, _ = clean_dataframe(df, batch_id="test-batch")
    assert valid_df.iloc[0]["correo_disponible"] == False  # noqa: E712
