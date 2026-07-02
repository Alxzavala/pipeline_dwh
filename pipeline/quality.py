import unicodedata
from datetime import date

import pandas as pd

PLACEHOLDER_BIRTHDATE = date(1800, 1, 1)
MIN_AGE_YEARS = 18
MAX_AGE_YEARS = 100

COLUMN_MAP = {
    "tipo de identificación": "tipo_identificacion",
    "número de identificación": "numero_identificacion",
    "número de cuenta": "numero_cuenta",
    "nombres": "nombres",
    "tipo transacción": "tipo_transaccion",
    "monto transacción": "monto_transaccion",
    "tipo de producto": "tipo_producto",
    "ciudad": "ciudad",
    "fecha-hora": "fecha_hora_transaccion",
    "fecha de nacimiento": "fecha_nacimiento",
    "dirección del cliente": "direccion_cliente",
    "teléfono del cliente": "telefono_cliente",
    "correo del cliente": "correo_cliente",
    "reporte centrales de riesgo": "reporte_centrales_riesgo",
    "monto reporte de central de riesgo": "monto_reporte_riesgo",
    "tiempo en mora del reporte de riesgo": "tiempo_mora_riesgo_dias",
}

TIPO_TRANSACCION_CATALOG = {
    "COMPRA": "COMPRA",
    "TRANSFERENCIA": "TRANSFERENCIA",
    "RETIRO": "RETIRO",
    "DEPOSITO": "DEPÓSITO",
    "PAGO": "PAGO",
}

TIPO_PRODUCTO_CATALOG = {
    "INVERSION": "INVERSIÓN",
    "CUENTA DE AHORROS": "CUENTA DE AHORROS",
    "CUENTA CORRIENTE": "CUENTA CORRIENTE",
    "TARJETA DE CREDITO": "TARJETA DE CRÉDITO",
    "PRESTAMO PERSONAL": "PRÉSTAMO PERSONAL",
}

CIUDAD_CATALOG = {
    "MEDELLIN": "MEDELLÍN",
    "BOGOTA": "BOGOTÁ",
    "BARRANQUILLA": "BARRANQUILLA",
    "BUCARAMANGA": "BUCARAMANGA",
    "CARTAGENA": "CARTAGENA",
    "CALI": "CALI",
    "PEREIRA": "PEREIRA",
}


def fix_mojibake(text):
    if not isinstance(text, str) or "Ã" not in text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def normalize_catalog_value(raw_value, catalog: dict):
    if not isinstance(raw_value, str):
        return raw_value
    fixed = fix_mojibake(raw_value).strip()
    key = strip_accents(fixed).upper()
    return catalog.get(key, fixed)


def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    fixed_columns = {col: fix_mojibake(col).strip().lower() for col in df.columns}
    df = df.rename(columns=fixed_columns)
    return df.rename(columns=COLUMN_MAP)


def _is_invalid_age(birth_date, transaction_ts) -> bool:
    if pd.isna(birth_date) or pd.isna(transaction_ts):
        return False
    age_years = (transaction_ts.date() - birth_date).days / 365.25
    return age_years < MIN_AGE_YEARS or age_years > MAX_AGE_YEARS


def clean_dataframe(df: pd.DataFrame, batch_id: str):
    df = normalize_headers(df.copy())

    for text_col in ("tipo_identificacion", "nombres", "direccion_cliente",
                      "telefono_cliente", "correo_cliente"):
        df[text_col] = df[text_col].map(fix_mojibake)

    df["tipo_transaccion"] = df["tipo_transaccion"].map(
        lambda v: normalize_catalog_value(v, TIPO_TRANSACCION_CATALOG)
    )
    df["tipo_producto"] = df["tipo_producto"].map(
        lambda v: normalize_catalog_value(v, TIPO_PRODUCTO_CATALOG)
    )
    df["ciudad"] = df["ciudad"].map(lambda v: normalize_catalog_value(v, CIUDAD_CATALOG))

    df["fecha_hora_transaccion"] = pd.to_datetime(df["fecha_hora_transaccion"], errors="coerce")
    df["fecha_nacimiento"] = pd.to_datetime(df["fecha_nacimiento"], errors="coerce").dt.date
    df.loc[df["fecha_nacimiento"] == PLACEHOLDER_BIRTHDATE, "fecha_nacimiento"] = pd.NaT

    df["correo_disponible"] = df["correo_cliente"].notna() & (
        df["correo_cliente"].astype(str).str.strip() != ""
    )

    df = df.drop_duplicates(
        subset=[c for c in df.columns if not c.startswith("_")], keep="first"
    ).reset_index(drop=True)

    reject_masks = {
        "identificacion_nula": df["numero_identificacion"].isna()
        | (df["numero_identificacion"].astype(str).str.strip() == ""),
        "monto_invalido": ~(df["monto_transaccion"] > 0),
        "tipo_transaccion_desconocido": ~df["tipo_transaccion"].isin(
            TIPO_TRANSACCION_CATALOG.values()
        ),
        "edad_invalida": df.apply(
            lambda row: _is_invalid_age(row["fecha_nacimiento"], row["fecha_hora_transaccion"]),
            axis=1,
        ),
    }

    combined_reject_mask = pd.Series(False, index=df.index)
    rejected_rows = []
    for motivo, mask in reject_masks.items():
        newly_rejected = mask & ~combined_reject_mask
        if newly_rejected.any():
            batch_rejects = df.loc[newly_rejected].copy()
            batch_rejects["motivo_rechazo"] = motivo
            rejected_rows.append(batch_rejects)
        combined_reject_mask |= mask

    valid_df = df.loc[~combined_reject_mask].copy()
    valid_df["_batch_id"] = batch_id
    valid_df["_loaded_at"] = pd.Timestamp.utcnow()

    if rejected_rows:
        rejected_df = pd.concat(rejected_rows, ignore_index=True)
        rejected_df["_batch_id"] = batch_id
        rejected_df["_loaded_at"] = pd.Timestamp.utcnow()
    else:
        rejected_df = pd.DataFrame(
            columns=list(df.columns) + ["motivo_rechazo", "_batch_id", "_loaded_at"]
        )

    return valid_df, rejected_df
