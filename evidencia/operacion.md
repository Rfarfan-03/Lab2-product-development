# Evidencia: operación (reentrenamiento, MLflow caído, reinicio)

## Simulación de una semana de operación

Para cada día del 2026-03-01 al 2026-03-07: pronóstico de cada tienda y, después, las ventas reales del día. Como no hay ventas reales posteriores al histórico, se usan como ventas simuladas las del mismo día de la semana del año anterior. El costo se calcula con `costos.csv` sobre `cantidad_sugerida`.

| Fecha | Tiendas | Costo de las sugerencias |
|---|---|---|
| 2026-03-01 | 9 | 3 599 |
| 2026-03-02 | 9 | 3 001 |
| 2026-03-03 | 9 | 2 555 |
| 2026-03-04 | 9 | 2 430 |
| 2026-03-05 | 9 | 2 350 |
| 2026-03-06 | 9 | 2 987 |
| 2026-03-07 | 9 | 3 498 |

## Reentrenamiento con las observaciones registradas

`POST /admin/reentrenar` → **HTTP 202**
```json
{
  "id": "reentrenamiento-fa9bbc5fbbf846ba8572958fc27ab780"
}
```
Consulta inmediata:
```json
{
  "estado": "en_curso"
}
```
Al terminar (~46 s):
```json
{
  "estado": "exitoso",
  "promovido": true,
  "version": "2",
  "motivo": "Costo en validación 88 693 vs 88 886 del vigente"
}
```

## Interrupción de MLflow

- `docker compose stop mlflow` → `/health` pasó a `degradado` en **4 s**:
```json
{
  "estado": "degradado",
  "motivo": "no disponible: MLflow; se responde con el modelo cargado (versión 1)"
}
```
- Predicción con MLflow caído → **HTTP 200**, `version_modelo` = `1` (modelo en memoria).
- Reentrenamiento con MLflow caído (`reentrenamiento-668178e718254dc1b6a3b6ff615280dc`) → no afecta al vigente:
```json
{
  "estado": "fallido",
  "promovido": false,
  "version": "2",
  "motivo": "El reentrenamiento falló (MlflowException: API request to http://mlflow:5000/api/2.0/mlflow/experiments/get-by-name failed with exception HTTPConnectionPool(host='mlflow', port=5000): Max retries exceeded with url: /api/2.0/mlflow/experiments/get-by-name?experiment_name=novamercado-ventas (Caused by NameResolutionError(\"<urllib3.connection.HTTPConnection object at 0x788bd2105490>: Failed to resolve 'mlflow' ([Errno -2] Name or service not known)\"))); se mantiene el modelo vigente"
}
```
- `docker compose start mlflow` → `/health` volvió a `ok` en **2 s**.

## Id desconocido

`GET /admin/reentrenar/no-existe` → **HTTP 404**
```json
{
  "detail": "no existe la ejecución 'no-existe'"
}
```
## Detener y volver a levantar (sin borrar volúmenes)

`docker compose down` seguido de `docker compose up -d`:

- `/health` volvió a `ok` en **32 s**.
- Servicio `bootstrap`: `Ya existe el modelo vigente (versión 2); no se entrena` (no repite la carga ni el entrenamiento).
- `GET /modelo`: `{"nombre":"novamercado-ventas","alias":"vigente","version":"2"}`
- Base de datos antes: 150 solicitudes, 912 predicciones, 756 observaciones; después: 150 solicitudes, 912 predicciones, 756 observaciones.

## Arranque desde cero

Con los volúmenes vacíos, `docker compose up -d` dejó `/health` en `ok` en **103 s** (sin contar la construcción
de imágenes): el servicio `bootstrap` cargó el histórico (83 052 filas), entrenó baseline y LightGBM y registró la
versión 1 con el alias `vigente`; la API la cargó sin reinicio.
