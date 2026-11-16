# Evidencia de funcionamiento

Generada levantando el producto desde cero (`docker compose down -v` + `docker compose up -d`) y
operándolo contra sus endpoints.

| Archivo | Contenido |
|---|---|
| [api_respuestas.md](api_respuestas.md) | Respuestas de la API ante solicitudes válidas, corregidas, con advertencia y rechazadas (incluye problemas fuera del catálogo) |
| [operacion.md](operacion.md) | Una semana simulada de operación, reentrenamiento con promoción, interrupción de MLflow, reentrenamiento fallido, reinicio sin borrar volúmenes y arranque desde cero |
| [mlflow.md](mlflow.md) | Experimento, runs (baseline y LightGBM) con métricas técnicas y de costo, versiones del modelo y alias `vigente` |
| [airflow.md](airflow.md) | Ejecuciones del DAG `reentrenamiento_modelo` (exitosa y fallida) |

Las mismas ejecuciones pueden verse en las interfaces web mientras el producto está levantado:
MLflow en http://localhost:5000 y Airflow en http://localhost:8080 (usuario y contraseña de `.env`).

Nota sobre la simulación: no hay ventas reales posteriores al histórico, así que en
[operacion.md](operacion.md) se usan como ventas "reales" las del mismo día de la semana del año anterior.
