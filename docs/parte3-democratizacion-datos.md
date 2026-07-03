# Parte 3: Explotación y Acceso a los Datos

La consulta completa está en [`sql/parte3_clientes_rentables.sql`](../sql/parte3_clientes_rentables.sql).

## Valor estratégico y operativo

La consulta identifica a los clientes más rentables combinando tres señales disponibles en el modelo dimensional: volumen transaccional, diversidad de productos contratados (cross-sell) y exposición a riesgo (penalizando clientes con alta proporción de transacciones marcadas por centrales de riesgo). El resultado (`score_rentabilidad`) no es solo un reporte estático: es la base para varios flujos de negocio concretos:

- **Retención y banca preferencial**: el equipo comercial puede priorizar contacto proactivo con los clientes de mayor score antes de que consideren cambiarse de entidad.
- **Cross-sell dirigido**: clientes con volumen alto pero pocos productos distintos son candidatos naturales para ofertas de nuevos productos (tarjeta de crédito, inversión).
- **Ajuste de políticas de riesgo**: al separar `transacciones_con_reporte_riesgo` como columna explícita, el equipo de riesgo puede cruzar rentabilidad con exposición sin tener que pedir una consulta ad-hoc al equipo de datos.

## Democratización de datos

Para que esta información sea consumible por analistas y áreas de negocio sin que cada uno dependa del equipo de datos para escribir SQL contra las tablas base:

1. **Vistas curadas en `marts`, nunca acceso directo a `raw`.** Se recomienda materializar esta consulta (o una versión parametrizada) como una vista o tabla programada (`bq scheduled query` / `dbt` en una evolución futura) dentro de `marts`, y otorgar a los analistas `roles/bigquery.dataViewer` **scoped a nivel de dataset `marts`** — nunca sobre `raw` (que contiene datos crudos sin limpiar y la tabla de rechazados) ni el rol amplio `bigquery.jobUser` a nivel de proyecto sin restricción.
2. **Dashboard de autoservicio.** Esa vista puede conectarse directamente a Looker Studio (o Looker/Power BI) para que comercial y retención consuman un tablero interactivo — filtros por ciudad, producto, rango de fechas — sin necesitar saber SQL ni tener acceso a BigQuery directamente.
3. **Seguridad a nivel de columna (column-level security), ya implementada.** `correo`, `telefono` y `direccion` en `dim_cliente` tienen un policy tag de Data Catalog (`terraform/data_governance.tf`); solo el Service Account del pipeline tiene el rol `datacatalog.categoryFineGrainedReader` para poder comparar valores reales durante el `MERGE` de SCD2. Cualquier otro usuario con acceso a `marts` —incluidos analistas con `dataViewer`— recibe `Access Denied` al referenciar esas columnas en una consulta (verificado en vivo), no un valor enmascarado: la variante de *masking* (sustituir por un hash en vez de negar el acceso) requiere que el proyecto pertenezca a una organización de Cloud Identity/Workspace, que esta cuenta personal no tiene. Esto permite democratizar el acceso a las métricas de negocio (montos, scores, conteos) sin exponer PII a toda la organización.
4. **Catálogo de datos documentado.** Las descripciones de tabla/columna ya se definen como código en Terraform (`description = "..."` en cada `google_bigquery_dataset`/`google_bigquery_table`), lo que las hace consultables desde BigQuery Studio o Data Catalog. Esto es lo que permite que un analista entienda qué significa `score_rentabilidad` (y cómo se calcula) sin tener que preguntarle al equipo de datos — condición necesaria para que el autoservicio funcione en la práctica, no solo en el acceso técnico.
5. **Auditoría como habilitador de la democratización, no como freno.** Abrir el acceso solo es seguro si es auditable: Cloud Audit Logs registra cambios de permisos, y `INFORMATION_SCHEMA.JOBS` en BigQuery permite ver qué usuario ejecutó qué consulta, cuándo y sobre qué tablas. Esto es lo que permite ampliar el acceso de forma responsable — cualquier uso indebido queda atribuido a un usuario concreto, en vez de tener que restringir el acceso por defecto ante la falta de trazabilidad.

## Consideraciones de seguridad y control de acceso (resumen)

| Control | Aplicado a | Objetivo |
|---|---|---|
| IAM a nivel de dataset (`dataViewer` en `marts` solamente) | Analistas y áreas de negocio | Evita acceso a datos crudos/sin limpiar |
| Column-level security (policy tag, acceso denegado sin rol) | `correo`, `telefono`, `direccion` en `dim_cliente` | Minimiza exposición de PII en el autoservicio — implementado y verificado en vivo |
| Service Account de mínimo privilegio (`bigquery.dataEditor`, `bigquery.jobUser`, `storage.objectAdmin` scoped al bucket) | Pipeline automatizado | El pipeline nunca corre con permisos de owner/editor |
| Cloud Audit Logs + `INFORMATION_SCHEMA.JOBS` | Todo el proyecto | Atribución de cada consulta/cambio a un usuario, habilita auditoría posterior |
| Particionamiento + clustering en la consulta | `fact_transacciones` | Evita escaneos completos de tabla, controla costo en un modelo de autoservicio con muchos usuarios concurrentes |
