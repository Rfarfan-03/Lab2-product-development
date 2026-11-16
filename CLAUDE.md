# CLAUDE.md

Contexto para agentes de programación que trabajen en este repositorio.

## Qué es

Servicio de ML en producción para NovaMercado (Laboratorio 2, Product Development):
pronóstico diario de ventas por tienda y familia de producto. Integra FastAPI, PostgreSQL,
MLflow y Apache Airflow, y se levanta completo con `docker compose up`.

## Regla de alcance

Implementar **solo** lo que pide el enunciado del laboratorio (requisitos 1–6, Anexo con el
contrato y entregables). No agregar endpoints, campos, servicios ni herramientas que el
enunciado no pida. Ante una ambigüedad, preguntar en lugar de inventar.

## Estructura

```
docker-compose.yml     # API, db (producto), airflow-db, mlflow, airflow-*
docker/api/            # Imagen de la API y sus dependencias fijadas
docker/airflow/        # Imagen de Airflow (incluye los DAGs)
novamercado/           # Código Python del producto
  api/                 # Aplicación FastAPI (endpoints delgados)
  esquemas.py          # Modelos Pydantic del contrato (solicitudes limpias y respuestas)
  catalogo.py          # Carga de tiendas, familias y feriados publicados
  limpieza/            # Política reparar / advertir / rechazar (sin dependencias de FastAPI)
dags/                  # DAGs de Airflow
tests/                 # Pruebas con pytest
datos_lab2/            # Archivos publicados por el equipo docente (NO versionados)
```

## Reglas del contrato que no se deben romper

- Puerto 8000; fechas `AAAA-MM-DD`; rechazos con 422 y campo `detail`.
- Las respuestas pueden tener campos extra, pero nunca omitir ni renombrar los del Anexo.
- `version_modelo`, `id`, `version`, `nombre`, `alias` son texto; `cantidad_sugerida` es entero ≥ 0.
- `calidad.estado` ∈ {ok, corregido, advertencia}; `accion` ∈ {reparar, advertir};
  `ok` no lleva observaciones; cualquier `advertir` ⇒ `advertencia`.
- `POST /v1/observaciones` es idempotente: reenviar lo mismo ⇒ `registros_guardados = 0`.

## Reglas de operación

- **No usar el reloj del sistema** para validar fechas: el servicio opera con fechas simuladas.
- Al predecir una fecha solo se usan observaciones de fechas anteriores.
- La lógica de limpieza vive en módulos de Python con pruebas, no dentro de los endpoints.
- Las pruebas de pytest no deben depender de un servidor de MLflow en ejecución.
- La API debe seguir respondiendo con el modelo en memoria si MLflow no está disponible.
- Datos y credenciales fuera del repositorio y de las imágenes (`.gitignore`, `.dockerignore`).
- Imágenes y dependencias con versiones fijas.
- El servicio de MLflow se llama `mlflow` en el Compose.

## Comandos

```bash
cp .env.example .env
docker compose up -d --build     # levantar todo
docker compose ps                # estado de los servicios
docker compose down              # detener (conserva volúmenes)

pip install -r requirements-dev.txt
python -m pytest                 # pruebas (no requieren datos, MLflow ni Docker)
```

## Limpieza de solicitudes

Flujo: cuerpo crudo → `novamercado.limpieza.limpiar_*` → solicitud canónica validada con
Pydantic + `RegistroCalidad`. `SolicitudRechazada` se traduce a 422 con `detail`.
Regla general: problemas a nivel de solicitud (cuerpo, tienda, fecha, lista) ⇒ rechazar;
problemas de un elemento ⇒ descartarlo/suponer con `advertir`; correcciones inequívocas ⇒ `reparar`.
Toda regla nueva debe ser general (no atada a un ejemplo del catálogo) y llevar prueba.

UIs locales: API http://localhost:8000/docs · MLflow http://localhost:5000 · Airflow http://localhost:8080

## Flujo de trabajo

Una rama por bloque de trabajo; se sube la rama y el PR se abre desde GitHub. No hacer
commits directos a `main`.
