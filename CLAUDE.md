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
docker-compose.yml     # API, bootstrap, db (producto), airflow-db, mlflow, airflow-*
docker/api/            # Imagen de la API y sus dependencias fijadas
docker/airflow/        # Imagen de Airflow (incluye los DAGs)
novamercado/           # Código Python del producto
  api/                 # FastAPI: main.py (endpoints delgados), servicio.py, gestor_modelo.py
  db/                  # Tablas (SQLAlchemy Core) y repositorio de la BD del producto
  esquemas.py          # Modelos Pydantic del contrato (solicitudes limpias y respuestas)
  catalogo.py          # Carga de tiendas, familias y feriados publicados
  limpieza/            # Política reparar / advertir / rechazar (sin dependencias de FastAPI)
  modelo/              # Features, baseline, LightGBM, métricas, criterio, entrenamiento/MLflow
dags/                  # DAGs de Airflow
tests/                 # Pruebas con pytest
evidencia/             # Evidencia de funcionamiento (respuestas, MLflow, Airflow, operación)
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

## Persistencia

Tablas: `historico_ventas` (cargado una vez si está vacía), `solicitudes` (todas, incluidas
rechazadas, con el cuerpo crudo), `correcciones`, `predicciones` (con `version_modelo`) y
`observaciones` (PK tienda+fecha+familia; solo se insertan filas nuevas o con ventas distintas).
El código de BD debe funcionar en SQLAlchemy 1.4 (versión de Airflow) y en SQLite (pruebas).

## Modelado

- `features.construir_features` es la única fuente de features, para entrenar y para predecir;
  solo usa ventas de fechas anteriores a la fecha objetivo.
- `cantidad_sugerida` = cuantil c_faltante/(c_faltante+c_sobrante) de cada familia (newsvendor).
- Registro: modelo `novamercado-ventas`, alias `vigente`. Cada entrenamiento registra al mejor
  candidato como versión nueva; el alias solo se mueve si `criterio.decidir_reemplazo` lo aprueba
  (costo estrictamente menor en la misma ventana de validación de 28 días).
- Las versiones de pandas, numpy, lightgbm y mlflow-skinny deben coincidir entre la API y Airflow.

## Arranque y salud

- `bootstrap` (imagen de la API, `python -m novamercado.arranque`): crea tablas, carga el histórico
  y entrena/registra el primer modelo solo si no hay alias `vigente`. En reinicios no repite nada.
- `repositorio.preparar_bd` usa un advisory lock para que la API y el bootstrap no compitan.
- `GET /health` revisa en vivo BD, MLflow y Airflow (timeouts de 3 s) y el modelo cargado:
  `ok`, `degradado` + `motivo`, o 503 mientras no haya modelo.
- La API usa `MLFLOW_HTTP_REQUEST_MAX_RETRIES=0` para no bloquearse si MLflow está caído.

## Reentrenamiento

- `POST /admin/reentrenar` crea la fila en `reentrenamientos` y dispara el DAG
  `reentrenamiento_modelo` por la REST API de Airflow con `dag_run_id` = id devuelto.
- El DAG (`dags/reentrenamiento.py`) entrena con `repositorio.ventas_para_entrenar` y escribe
  el resultado en `reentrenamientos`; si falla, `registrar_fallo` lo deja como `fallido`.
- `GET /admin/reentrenar/{id}` lee la fila y, mientras siga en curso, consulta a Airflow para
  detectar ejecuciones fallidas sin registro.
- `MonitorModelo` (hilo de la API) revisa el alias cada `MODELO_REFRESCO_SEG` (30 s) y carga la
  versión nueva sin reiniciar; si MLflow no responde, conserva el modelo en memoria.

UIs locales: API http://localhost:8000/docs · MLflow http://localhost:5000 · Airflow http://localhost:8080

## Documentación

`README.md` (cómo levantar el producto) y `DECISIONES.md` (políticas y justificación) deben
mantenerse coherentes con el código: si cambia una política de limpieza, el umbral de similitud,
las features, la cantidad sugerida o el criterio de reemplazo, actualizar `DECISIONES.md`.

## Flujo de trabajo

Una rama por bloque de trabajo; se sube la rama y el PR se abre desde GitHub. No hacer
commits directos a `main`.
