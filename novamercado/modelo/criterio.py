"""Criterio explícito para decidir si un modelo nuevo reemplaza al vigente.

Se compara el costo de negocio (costos.csv) de ambos modelos sobre la misma ventana de
validación: las últimas semanas de datos disponibles, que ninguno de los dos usó para
entrenar. El candidato reemplaza al vigente solo si su costo es estrictamente menor.
"""

from __future__ import annotations


def formatear_costo(valor: float) -> str:
    return f"{round(valor):,}".replace(",", " ")


def decidir_reemplazo(costo_candidato: float, costo_vigente: float | None) -> tuple[bool, str]:
    if costo_vigente is None:
        return True, f"No hay modelo vigente; costo en validación {formatear_costo(costo_candidato)}"
    if costo_candidato < costo_vigente:
        return True, (
            f"Costo en validación {formatear_costo(costo_candidato)} "
            f"vs {formatear_costo(costo_vigente)} del vigente"
        )
    return False, (
        f"Costo en validación {formatear_costo(costo_candidato)} no mejora "
        f"{formatear_costo(costo_vigente)} del vigente"
    )
