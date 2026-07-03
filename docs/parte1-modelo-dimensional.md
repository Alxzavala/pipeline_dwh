# Parte 1: Modelado y Arquitectura de Datos

## 1. Modelo dimensional

Esquema estrella, implementado en BigQuery (dataset `marts`):

```
                          ┌───────────────────┐
                          │    DIM_FECHA       │
                          │  sk_fecha (PK)      │
                          │  fecha, anio, mes,   │
                          │  dia, dia_semana,    │
                          │  es_fin_de_semana    │
                          └─────────┬───────────┘
                                    │
┌──────────────────┐     ┌─────────▼──────────┐     ┌───────────────────┐
│   DIM_CLIENTE     │     │                     │     │   DIM_PRODUCTO     │
│  sk_cliente (PK)   │◄────┤                     ├────►│  sk_producto (PK)   │
│  numero_ident.      │     │                     │     │  tipo_producto      │
│  nombres            │     │  FACT_TRANSACCIONES │     └───────────────────┘
│  fecha_nacimiento    │     │                     │
│  direccion/telefono/ │     │  sk_transaccion (PK) │     ┌───────────────────┐
│  correo (SCD2)       │     │  sk_cliente (FK)     │     │ DIM_TIPO_TRANSACCION│
│  fecha_inicio/fin_   │     │  sk_cuenta (FK)      ├────►│  sk_tipo_trans (PK)  │
│  vigencia, es_vigente│     │  sk_producto (FK)     │     │  tipo_transaccion    │
└─────────┬─────────┘     │  sk_tipo_trans (FK)   │     └───────────────────┘
          │                │  sk_ciudad (FK)       │
┌─────────▼─────────┐     │  sk_fecha (FK)         │     ┌───────────────────┐
│    DIM_CUENTA       │     │  fecha_hora_transaccion│     │    DIM_CIUDAD       │
│  sk_cuenta (PK)      │◄────┤  monto_transaccion     ├────►│  sk_ciudad (PK)      │
│  numero_cuenta        │     │  reporte_centrales_    │     │  ciudad              │
│  sk_cliente (FK)       │     │  riesgo, monto_reporte │     └───────────────────┘
│  sk_producto (FK)       │     │  _riesgo, tiempo_mora  │
└───────────────────┘     │  _riesgo_dias           │
                          └─────────────────────┘
```

**Grano de la tabla de hechos:** una fila = una transacción bancaria individual.

### Tabla de hechos: `FACT_TRANSACCIONES`
- Medidas: `monto_transaccion`, `monto_reporte_riesgo`, `tiempo_mora_riesgo_dias`.
- Degenerate dimension: `reporte_centrales_riesgo` (booleano, snapshot del estado de central de riesgo al momento de la transacción).
- Clave sustituta (`sk_transaccion`): hash SHA-256 determinístico de la clave de negocio (identificación + cuenta + tipo transacción + fecha-hora + monto), que hace el `MERGE` de carga idempotente sin necesidad de una secuencia autoincremental.

### Dimensiones
- **`DIM_CLIENTE`** — SCD Tipo 2 real: `numero_identificacion`, `tipo_identificacion`, `nombres`, `fecha_nacimiento`, `direccion`, `telefono`, `correo`, `correo_disponible`, `fecha_inicio_vigencia`, `fecha_fin_vigencia`, `es_vigente`. Se versiona porque dirección, teléfono y correo cambian en el tiempo, y el histórico de esos cambios es información de negocio relevante (ej. para análisis de comportamiento o auditoría de contacto).
- **`DIM_CUENTA`** — SCD Tipo 1 (siempre refleja el cliente/producto vigente asociado a la cuenta).
- **`DIM_PRODUCTO`**, **`DIM_TIPO_TRANSACCION`**, **`DIM_CIUDAD`** — dimensiones simples de baja cardinalidad, upsert idempotente (`MERGE ... WHEN NOT MATCHED THEN INSERT`).
- **`DIM_FECHA`** — dimensión de calendario estándar, generada una sola vez (rango 2020-2030) independientemente de la carga de transacciones.

## 2. Justificación del modelo: estrella sobre copo de nieve

Se eligió **esquema estrella** (no copo de nieve) por tres razones concretas para este caso de uso:

1. **Performance de lectura.** Las consultas de BI (ej. "ventas por producto y ciudad del último trimestre") requieren menos `JOIN`s contra un esquema estrella. En un motor columnar como BigQuery, cada `JOIN` adicional que introduciría un copo de nieve (normalizar `DIM_PRODUCTO` en `DIM_CATEGORIA_PRODUCTO`, por ejemplo) añade costo de shuffle sin un beneficio real de almacenamiento, porque BigQuery ya comprime automáticamente valores repetidos en columnas de baja cardinalidad.
2. **Simplicidad para herramientas de BI y analistas.** Looker Studio, Power BI y analistas SQL generan queries más simples y predecibles contra un esquema estrella. Copo de nieve traslada la complejidad de "cuántos `JOIN`s necesito" del modelador al usuario final, lo cual va en contra del objetivo de democratización de datos (ver Parte 3).
3. **El argumento de ahorro de storage del copo de nieve no aplica en BigQuery.** El copo de nieve normaliza atributos de dimensión (ej. separar `ciudad` en su propia tabla de "región") para reducir duplicación de texto. En un motor de almacenamiento columnar con compresión automática, ese ahorro es marginal, mientras que el costo de los `JOIN`s extra en tiempo de consulta es real y medible.

La única normalización parcial que sí se aplicó es `DIM_CUENTA` como dimensión independiente (en vez de degenerar `numero_cuenta` directamente en el hecho), porque una cuenta tiene su propio ciclo de vida (cliente y producto asociado pueden cambiar) que amerita una clave sustituta propia.

## 3. Estrategia de particionamiento y clustering

| Tabla | Partición | Clustering | Consulta que optimiza |
|---|---|---|---|
| `fact_transacciones` | `DATE(fecha_hora_transaccion)`, diaria | `sk_cliente, sk_producto` | Reportes por rango de fechas (partition pruning: BigQuery solo escanea las particiones dentro del `WHERE`); historial completo de un cliente específico; análisis agregado por tipo de producto |
| `raw.stg_transacciones` | `DATE(fecha_hora_transaccion)`, diaria | — | Reprocesamiento o auditoría de un batch/día específico de staging sin escanear todo el histórico crudo |
| `dim_cliente` | — | `numero_identificacion` | Lookups puntuales de un cliente por su número de identificación (la forma más común de buscar un cliente) |
| `dim_cuenta` | — | `numero_cuenta` | Resolución de la cuenta asociada a una transacción durante el `MERGE` de carga, y lookups directos por número de cuenta |

El particionamiento diario en `fact_transacciones` es la optimización de mayor impacto: cualquier consulta con un filtro `WHERE fecha_hora_transaccion >= ...` (como la de la Parte 3) solo escanea los bytes de las particiones relevantes, no la tabla completa — esto es lo que en BigQuery se traduce directamente en menor costo (se cobra por bytes escaneados) y menor latencia.

## 4. Calidad y gobernanza de datos a lo largo del pipeline

**Calidad (implementada en `pipeline/quality.py`):**
- Corrección de mojibake en encabezados y valores de texto (el CSV origen llega con codificación UTF-8 mal decodificada como Latin-1).
- Deduplicación de filas exactamente duplicadas antes de cargar a staging.
- Normalización de catálogos (`tipo_transaccion`, `tipo_producto`, `ciudad`) contra variantes de acentuación/mayúsculas, incluyendo variantes de mojibake truncado detectadas en el dataset real.
- El valor placeholder `1800-01-01` en `fecha_nacimiento` se trata como fecha desconocida (nulo), no como un error.
- Validación de edad (18-100 años al momento de la transacción) y de monto positivo; filas que fallan van a una tabla de cuarentena (`raw.rechazados`) con el motivo exacto de rechazo, en vez de perderse silenciosamente o bloquear todo el batch.

**Gobernanza:**
- Separación de datasets por capa: `raw` (staging, solo accesible por el Service Account del pipeline) vs. `marts` (modelo dimensional, con acceso de solo lectura para analistas vía `roles/bigquery.dataViewer` scoped al dataset).
- Recomendación de **column-level security** (policy tags de BigQuery) sobre `correo` y `telefono` en `dim_cliente`, de forma que solo un grupo autorizado de "PII viewers" vea el valor real; el resto de usuarios ve el campo enmascarado.
- Descripciones de tabla y columna documentadas directamente en la definición de Terraform (`description = "..."`), sirviendo como catálogo de datos mínimo consultable desde Data Catalog / BigQuery Studio.
- Principio de mínimo privilegio en IAM: el Service Account del pipeline tiene únicamente `bigquery.dataEditor`, `bigquery.jobUser` (a nivel de proyecto) y `storage.objectAdmin` (scoped al bucket, no a nivel de proyecto) — sin roles `owner`/`editor`.

## 5. Trazabilidad y auditoría

- **Columnas técnicas** en todas las tablas de staging y hechos: `_batch_id` (identifica el lote de carga), `_source_file` (archivo/lote de origen), `_loaded_at` (timestamp de carga). Cualquier fila puede rastrearse hasta el batch y momento exacto en que entró al sistema.
- **Logging estructurado**: cada ejecución del pipeline emite eventos a Cloud Logging (`jsonPayload.event`), incluyendo fallos (`pipeline_failed`) con el motivo exacto — esto alimenta directamente la alerta de monitoreo de la Parte 4.
- **Cloud Audit Logs** (nativo de GCP, sin configuración adicional) registra cambios de IAM y accesos administrativos sobre los datasets, permitiendo auditar quién modificó permisos o esquema.
- **El historial SCD2 de `DIM_CLIENTE` es en sí mismo un mecanismo de auditoría**: cada cambio de dirección/teléfono/correo de un cliente queda registrado como una nueva versión con su rango de vigencia, en vez de sobrescribirse — se puede reconstruir el estado exacto de los datos de un cliente en cualquier fecha histórica.
