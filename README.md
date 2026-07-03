# Pipeline DWH Bancario — GCP

Data Warehouse en Google Cloud Platform que integra
transacciones, datos de clientes y riesgo crediticio de una entidad bancaria en un
modelo dimensional (esquema estrella) sobre BigQuery, con pipeline ETL/ELT, CI/CD e
infraestructura como código.

## Arquitectura

```
CSV origen → GCS (raw zone) → BigQuery raw.stg_transacciones (staging)
  → transformación SQL (MERGE) → BigQuery marts.* (modelo dimensional)
```

- **Terraform** gestiona toda la infraestructura: bucket GCS, datasets/tablas de
  BigQuery, Service Account de mínimo privilegio, Workload Identity Federation para
  CI/CD, y monitoreo/alertas.
- **Python** (`pipeline/`) implementa extracción, limpieza/validación de datos y
  orquestación; las transformaciones dimensionales corren como SQL dentro de BigQuery
  (patrón ELT).
- **GitHub Actions** ejecuta lint, tests, `terraform plan`/`apply` y el pipeline bajo
  demanda, autenticado vía Workload Identity Federation (sin llaves JSON estáticas).

Ver [`docs/parte1-modelo-dimensional.md`](docs/parte1-modelo-dimensional.md) para el
diseño completo del modelo dimensional y [`docs/parte3-democratizacion-datos.md`](docs/parte3-democratizacion-datos.md)
para la estrategia de acceso y democratización de datos.

## Estructura del repositorio

```
docs/            Documento de diseño (Parte 1) y democratización de datos (Parte 3)
terraform/       Infraestructura como código
pipeline/        ETL en Python (extract, quality, transform, main)
scripts/         Utilidad para generar los lotes de prueba de carga incremental
sql/             DDL de seed (dim_fecha) y query de Parte 3
tests/           Tests de calidad de datos y del orquestador
.github/workflows/ CI/CD
```

## Prerrequisitos

- `gcloud` CLI autenticado (`gcloud auth login` + `gcloud auth application-default login`)
- Terraform >= 1.5
- Python 3.12

## Configuración inicial

```bash
# 1. Vincular facturación al proyecto (una sola vez)
gcloud billing projects link pelagic-plexus-360917 --billing-account=<ID_CUENTA_FACTURACION>

# 2. Aplicar infraestructura
cd terraform
cp terraform.tfvars.example terraform.tfvars   
terraform init
terraform apply

# 3. Entorno Python
cd ..
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

# 4. Cargar la dimensión de fechas (una sola vez)
bq query --project_id=pelagic-plexus-360917 --use_legacy_sql=false < sql/seed_dim_fecha.sql
```

## Uso

```bash
export GCP_PROJECT_ID=pelagic-plexus-360917
export RAW_BUCKET=pelagic-plexus-360917-raw-zone

# Generar lotes de prueba (carga incremental) a partir del CSV fuente
.venv/Scripts/python -m scripts.split_batches --source-csv data/datos_transacciones_prueba.csv --output-dir data

# Correr el pipeline
.venv/Scripts/python -m pipeline.main --csv-path data/batch_1.csv --batch-id batch_1
.venv/Scripts/python -m pipeline.main --csv-path data/batch_2.csv --batch-id batch_2
```

## Tests

```bash
.venv/Scripts/pytest tests -v
.venv/Scripts/ruff check pipeline scripts tests
cd terraform && terraform validate && terraform fmt -check -recursive
```

## CI/CD

`.github/workflows/ci-cd.yml`: `lint` → `test` → `terraform plan` (en PRs) /
`terraform apply` (en push a `main`, con aprobación manual vía GitHub Environment
`production`) → `run-pipeline` (manual, `workflow_dispatch`).

Antes de que el workflow funcione, configura en el repo de GitHub (Settings → Secrets
and variables → Actions):
- `WIF_PROVIDER`: salida `workload_identity_provider` de `terraform output`
- `WIF_SERVICE_ACCOUNT`: salida `pipeline_service_account_email` de `terraform output`

Y en Settings → Environments, crea un environment `production` con al menos un
revisor requerido, para que el `terraform apply` automático en `main` pida aprobación
manual antes de aplicar cambios de infraestructura.

## Monitoreo

El pipeline emite un log estructurado (`jsonPayload.event=pipeline_failed`) a Cloud
Logging en cualquier fallo. Una métrica basada en logs y una política de alertas
(ambas gestionadas por Terraform) notifican por correo ante cualquier fallo —
verificado en vivo: log → métrica → alerta → correo recibido.
