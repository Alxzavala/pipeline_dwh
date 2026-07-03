import argparse
import sys

import pandas as pd
from google.cloud import bigquery
from google.cloud import logging as cloud_logging

from pipeline.config import Config
from pipeline.extract import load_dataframe_to_staging, upload_to_raw_bucket
from pipeline.quality import clean_dataframe
from pipeline.transform import run_dimensional_transform


def run_pipeline(config: Config, csv_path: str, batch_id: str) -> dict:
    df = pd.read_csv(csv_path, encoding="utf-8")
    valid_df, rejected_df = clean_dataframe(df, batch_id=batch_id)

    upload_to_raw_bucket(config, csv_path, blob_name=f"landing/{batch_id}.csv")
    loaded_rows = load_dataframe_to_staging(config, valid_df, batch_id=batch_id)

    if not rejected_df.empty:
        _load_rejected_rows(config, rejected_df, batch_id)

    run_dimensional_transform(config, batch_id=batch_id)

    return {
        "batch_id": batch_id,
        "filas_leidas": len(df),
        "filas_validas": loaded_rows,
        "filas_rechazadas": len(rejected_df),
    }


def _load_rejected_rows(config: Config, rejected_df: pd.DataFrame, batch_id: str) -> None:
    client = bigquery.Client(project=config.project_id)
    table_ref = f"{config.project_id}.{config.raw_dataset}.rechazados"
    payload = pd.DataFrame(
        {
            "fila_original": rejected_df.astype(str).apply(lambda r: r.to_json(), axis=1),
            "motivo_rechazo": rejected_df["motivo_rechazo"],
            "_batch_id": batch_id,
            "_loaded_at": pd.Timestamp.utcnow(),
        }
    )
    job = client.load_table_from_dataframe(
        payload,
        table_ref,
        job_config=bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_APPEND),
    )
    job.result()


def _log_pipeline_failure(config: Config, batch_id: str, reason: str) -> None:
    logging_client = cloud_logging.Client(project=config.project_id)
    logger = logging_client.logger("dwh-pipeline")
    logger.log_struct(
        {"event": "pipeline_failed", "batch_id": batch_id, "reason": reason}, severity="ERROR"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline ETL/ELT DWH bancario")
    parser.add_argument("--csv-path", required=True)
    parser.add_argument("--batch-id", required=True)
    args = parser.parse_args()

    config = Config.from_env()

    try:
        result = run_pipeline(config, args.csv_path, args.batch_id)
    except Exception as exc:  # noqa: BLE001 - top-level CLI boundary, must not crash silently
        _log_pipeline_failure(config, args.batch_id, reason=str(exc))
        print(f"ERROR: pipeline_failed - {exc}", file=sys.stderr)
        sys.exit(1)

    print(
        f"batch_id={result['batch_id']} leidas={result['filas_leidas']} "
        f"validas={result['filas_validas']} rechazadas={result['filas_rechazadas']}"
    )

    if result["filas_validas"] == 0:
        _log_pipeline_failure(config, args.batch_id, reason="cero filas validas cargadas")
        print("ERROR: pipeline_failed - ninguna fila valida cargada", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
