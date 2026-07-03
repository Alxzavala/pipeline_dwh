from decimal import Decimal

import pandas as pd
from google.cloud import bigquery, storage

from pipeline.config import Config

STAGING_SCHEMA = [
    bigquery.SchemaField("tipo_identificacion", "STRING"),
    bigquery.SchemaField("numero_identificacion", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("numero_cuenta", "STRING"),
    bigquery.SchemaField("nombres", "STRING"),
    bigquery.SchemaField("tipo_transaccion", "STRING"),
    bigquery.SchemaField("monto_transaccion", "NUMERIC"),
    bigquery.SchemaField("tipo_producto", "STRING"),
    bigquery.SchemaField("ciudad", "STRING"),
    bigquery.SchemaField("fecha_hora_transaccion", "TIMESTAMP"),
    bigquery.SchemaField("fecha_nacimiento", "DATE"),
    bigquery.SchemaField("direccion_cliente", "STRING"),
    bigquery.SchemaField("telefono_cliente", "STRING"),
    bigquery.SchemaField("correo_cliente", "STRING"),
    bigquery.SchemaField("reporte_centrales_riesgo", "BOOLEAN"),
    bigquery.SchemaField("monto_reporte_riesgo", "NUMERIC"),
    bigquery.SchemaField("tiempo_mora_riesgo_dias", "INTEGER"),
    bigquery.SchemaField("_batch_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("_source_file", "STRING"),
    bigquery.SchemaField("_loaded_at", "TIMESTAMP", mode="REQUIRED"),
]


def upload_to_raw_bucket(config: Config, local_path: str, blob_name: str) -> str:
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.raw_bucket)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(local_path)
    return f"gs://{config.raw_bucket}/{blob_name}"


def _coerce_string_columns(df: pd.DataFrame, string_fields: set) -> pd.DataFrame:
    df = df.copy()
    for col in string_fields & set(df.columns):
        if pd.api.types.is_integer_dtype(df[col]):
            df[col] = df[col].astype(str)
        elif pd.api.types.is_float_dtype(df[col]):
            df[col] = df[col].apply(
                lambda v: None if pd.isna(v) else (str(int(v)) if float(v).is_integer() else str(v))
            )
        else:
            df[col] = df[col].where(df[col].notna(), None)
    return df


def _coerce_numeric_columns(df: pd.DataFrame, numeric_fields: set) -> pd.DataFrame:
    df = df.copy()
    for col in numeric_fields & set(df.columns):
        df[col] = df[col].apply(lambda v: None if pd.isna(v) else Decimal(str(v)))
    return df


def load_dataframe_to_staging(config: Config, df, batch_id: str) -> int:
    client = bigquery.Client(project=config.project_id)
    table_ref = f"{config.project_id}.{config.raw_dataset}.stg_transacciones"
    load_columns = [f.name for f in STAGING_SCHEMA if f.name != "_source_file"]
    string_fields = {f.name for f in STAGING_SCHEMA if f.field_type == "STRING"}
    numeric_fields = {f.name for f in STAGING_SCHEMA if f.field_type == "NUMERIC"}

    upload_df = df[[c for c in load_columns if c in df.columns]].copy()
    upload_df = _coerce_string_columns(upload_df, string_fields)
    upload_df = _coerce_numeric_columns(upload_df, numeric_fields)
    upload_df["_source_file"] = batch_id

    # Retrying a failed batch must not double-load staging: delete any rows
    # from a prior (possibly partial) attempt at this batch_id before appending.
    client.query(
        f"DELETE FROM `{table_ref}` WHERE _batch_id = @batch_id",
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("batch_id", "STRING", batch_id)]
        ),
    ).result()

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        schema=STAGING_SCHEMA,
    )
    job = client.load_table_from_dataframe(upload_df, table_ref, job_config=job_config)
    job.result()
    return job.output_rows
