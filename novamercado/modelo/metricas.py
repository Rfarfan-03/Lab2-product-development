"""Métrica de negocio (costos.csv) y métricas técnicas del pronóstico."""

from __future__ import annotations

import numpy as np
import pandas as pd


def cuantil_por_familia(costos: pd.DataFrame) -> dict[str, float]:
    """Cuantil que minimiza el costo esperado de cada familia (newsvendor).

    Con costo = c_f·max(real−q, 0) + c_s·max(q−real, 0), el q óptimo es el cuantil
    c_f / (c_f + c_s) de la distribución de la demanda.
    """
    return {
        r.familia_id: float(r.costo_faltante / (r.costo_faltante + r.costo_sobrante))
        for r in costos.itertuples()
    }


def costo(real, sugerido, familias, costos: pd.DataFrame) -> np.ndarray:
    """Costo por fila según costos.csv."""
    c = costos.set_index("familia_id")
    cf = pd.Series(familias).map(c["costo_faltante"]).to_numpy(dtype=float)
    cs = pd.Series(familias).map(c["costo_sobrante"]).to_numpy(dtype=float)
    real = np.asarray(real, dtype=float)
    sugerido = np.asarray(sugerido, dtype=float)
    return cf * np.maximum(real - sugerido, 0) + cs * np.maximum(sugerido - real, 0)


def evaluar(
    real, venta_esperada, cantidad_sugerida, familias, costos: pd.DataFrame
) -> dict[str, float]:
    real = np.asarray(real, dtype=float)
    esperada = np.asarray(venta_esperada, dtype=float)
    error = esperada - real
    total_real = np.abs(real).sum()
    return {
        "costo": float(costo(real, cantidad_sugerida, familias, costos).sum()),
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt((error**2).mean())),
        "wape": float(np.abs(error).sum() / total_real) if total_real else float("nan"),
        "sesgo": float(error.mean()),
    }
