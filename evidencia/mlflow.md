# Evidencia: MLflow

Experimento `novamercado-ventas` (id 1).

## Runs de entrenamiento

Cada entrenamiento es un run padre con dos runs anidados (baseline y LightGBM). Las métricas `val_*` se calculan sobre la ventana de validación (últimos 28 días disponibles).

| Inicio | Run | Padre | Origen | Datos hasta | val_costo | val_mae | val_rmse | val_wape |
|---|---|---|---|---|---|---|---|---|
| 2026-11-16 05:08:54 UTC | entrenamiento-inicial | — | inicial | 2026-02-28 | — | — | — | — |
| 2026-11-16 05:08:54 UTC | baseline | entrenamiento-inicial | inicial | 2026-02-28 | 105 869.3 | 45.9 | 85.4 | 0.215 |
| 2026-11-16 05:08:55 UTC | lightgbm | entrenamiento-inicial | inicial | 2026-02-28 | 90 966.2 | 37.8 | 69.5 | 0.177 |
| 2026-11-16 05:10:33 UTC | entrenamiento-reentrenamiento | — | reentrenamiento | 2026-03-07 | — | — | — | — |
| 2026-11-16 05:10:33 UTC | baseline | entrenamiento-reentrenamiento | reentrenamiento | 2026-03-07 | 103 042.4 | 45.9 | 84.5 | 0.214 |
| 2026-11-16 05:10:33 UTC | lightgbm | entrenamiento-reentrenamiento | reentrenamiento | 2026-03-07 | 88 692.6 | 38.2 | 68.8 | 0.178 |

Resultado de cada entrenamiento (run padre):

| Run | Candidato | Versión candidata | Costo candidato | Costo vigente | Promovido | Motivo |
|---|---|---|---|---|---|---|
| entrenamiento-inicial | lightgbm | 1 | 90 966 | — | sí | No hay modelo vigente; costo en validación 90 966 |
| entrenamiento-reentrenamiento | lightgbm | 2 | 88 693 | 88 886 | sí | Costo en validación 88 693 vs 88 886 del vigente |

## Model Registry

Modelo registrado `novamercado-ventas`. Alias: `vigente` → versión 2

| Versión | Alias | Tipo | Origen | Entrenado hasta | Validación desde | Costo validación | Run |
|---|---|---|---|---|---|---|---|
| 1 |  | lightgbm | inicial | 2026-01-31 | 2026-02-01 | 90966.20 | `7c0e74bf` |
| 2 | vigente | lightgbm | reentrenamiento | 2026-02-07 | 2026-02-08 | 88692.60 | `aab589da` |
