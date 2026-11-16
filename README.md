# NovaMercado · Pronóstico diario de ventas

Servicio de ML en producción (Laboratorio 2, Product Development). Recibe solicitudes de pronóstico
por tienda y fecha, responde la venta esperada y la cantidad sugerida por familia de producto aunque
los datos lleguen en mal estado, registra predicciones y ventas reales, y reentrena su modelo con esa
información. Integra **FastAPI**, **PostgreSQL**, **MLflow** y **Apache Airflow** en un solo
`docker compose up`.

- Decisiones técnicas y de producto: [DECISIONES.md](DECISIONES.md)
- Evidencia de funcionamiento: [evidencia/](evidencia/README.md)

## Requisitos

- Docker con Docker Compose v2 (probado con Docker Desktop 29 y Compose 5.6).
- Unos 6 GB de memoria disponibles para Docker.
- Puertos libres: **8000** (API), **5000** (MLflow) y **8080** (Airflow).

## Levantar el producto desde cero

1. Clonar el repositorio y entrar a la carpeta:

   ```bash
   git clone https://github.com/Rfarfan-03/Lab2-product-development.git
   cd Lab2-product-development
   ```

2. **Colocar los archivos publicados en la carpeta `datos_lab2/`** en la raíz del repositorio
   (la carpeta no está versionada). Debe quedar así:

   ```
   datos_lab2/
   ├── tiendas.csv
   ├── familias.csv
   ├── historico_ventas.csv
   ├── feriados.csv
   ├── costos.csv
   ├── catalogo_errores.md      (no lo usa el servicio)
   └── ejemplos/                (no lo usa el servicio)
   ```

3. Crear el archivo de configuración a partir del ejemplo:

   ```bash
   cp .env.example .env
   ```

4. Levantar todo:

   ```bash
   docker compose up -d --build
   ```

5. Esperar a que el servicio esté listo. Desde cero tarda unos 2 minutos sin contar la construcción
   de imágenes: el servicio `bootstrap` carga el histórico en la base de datos, entrena el primer
   modelo y lo registra en MLflow; la API lo carga sola.

   ```bash
   curl http://localhost:8000/health
   # {"estado":"ok"}
   ```

   Mientras no hay modelo cargado, `/health` responde 503.

Al volver a levantar el producto (sin borrar volúmenes) se conserva todo lo registrado y no se repite
la carga de datos ni el entrenamiento inicial.

## Uso

| Endpoint | Descripción |
|---|---|
| `POST /v1/prediccion` | Pronóstico de un día para una tienda |
| `POST /v1/observaciones` | Ventas reales de un día para una tienda (idempotente) |
| `POST /admin/reentrenar` | Dispara el reentrenamiento (202 con `id`) |
| `GET /admin/reentrenar/{id}` | Estado de una ejecución de reentrenamiento |
| `GET /modelo` | Modelo vigente que usa el servicio |
| `GET /health` | Estado del servicio y sus dependencias |

Documentación interactiva: http://localhost:8000/docs

```bash
curl -X POST http://localhost:8000/v1/prediccion -H "content-type: application/json" \
     -d @datos_lab2/ejemplos/prediccion_valida.json

curl -X POST http://localhost:8000/admin/reentrenar
curl http://localhost:8000/admin/reentrenar/<id>
```

Interfaces web:

- MLflow: http://localhost:5000 (experimento y modelo `novamercado-ventas`, alias `vigente`)
- Airflow: http://localhost:8080 (DAG `reentrenamiento_modelo`; usuario y contraseña en `.env`)

## Operación

```bash
docker compose ps                 # estado de los servicios
docker compose logs -f api        # logs de la API
docker compose stop mlflow        # la API sigue respondiendo; /health pasa a "degradado"
docker compose start mlflow       # /health vuelve a "ok"
docker compose down               # detener conservando los datos (volúmenes)
docker compose down -v            # detener y BORRAR todo (vuelve al estado desde cero)
```

Si los puertos 5000 u 8080 están ocupados, se pueden cambiar `MLFLOW_HOST_PORT` y
`AIRFLOW_HOST_PORT` en `.env`. La API siempre usa el puerto 8000.

## Servicios

| Servicio | Imagen | Función |
|---|---|---|
| `api` | `python:3.11.10-slim` + dependencias fijadas | FastAPI en el puerto 8000 |
| `bootstrap` | misma imagen que la API | Arranque desde cero (se ejecuta y termina) |
| `db` | `postgres:16.4` | Base de datos del producto |
| `mlflow` | `ghcr.io/mlflow/mlflow:v2.16.2` | Tracking y Model Registry |
| `airflow-db` | `postgres:16.4` | Base de datos de Airflow (separada) |
| `airflow-init`, `airflow-webserver`, `airflow-scheduler` | `apache/airflow:2.10.3-python3.11` + dependencias | Reentrenamiento |

## Estructura del repositorio

```
docker-compose.yml      Orquestación de todos los servicios
.env.example            Variables de configuración (copiar a .env)
docker/api/             Imagen de la API y sus dependencias
docker/airflow/         Imagen de Airflow
dags/                   DAG de reentrenamiento
novamercado/
  api/                  Endpoints (main.py), servicio, administración, salud, recarga del modelo
  limpieza/             Defensa del contrato: reparar, advertir o rechazar
  modelo/               Features, modelos, métricas, criterio de reemplazo, entrenamiento
  db/                   Esquema y acceso a la base de datos del producto
  esquemas.py           Modelos Pydantic del contrato
  catalogo.py           Catálogos publicados
  arranque.py           Arranque desde cero
tests/                  Pruebas automatizadas (pytest)
evidencia/              Evidencia de funcionamiento
CLAUDE.md               Contexto para el agente de programación
DECISIONES.md           Decisiones y su justificación
```

## Pruebas

Las pruebas no necesitan Docker, MLflow, PostgreSQL ni los datos publicados: usan SQLite en memoria,
MLflow local en archivos temporales y modelos falsos.

```bash
pip install -r requirements-dev.txt     # Python 3.11
python -m pytest
```

O dentro de la imagen de la API, sin instalar nada localmente:

```bash
docker compose build api
docker run --rm -v "$PWD:/repo" -w /repo --entrypoint sh novamercado-api:local \
  -c "pip install -q pytest==8.3.3 httpx==0.27.2 && python -m pytest"
```
