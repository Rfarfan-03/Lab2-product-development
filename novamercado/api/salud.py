"""``GET /health``: estado de la API y de sus dependencias.

Las dependencias se revisan en cada consulta con tiempos de espera cortos, así que una
caída de MLflow (o de otra dependencia) se refleja de inmediato y el estado vuelve a ``ok``
en cuanto la dependencia responde de nuevo.
"""

from __future__ import annotations

from typing import Callable

import requests
from sqlalchemy import text
from sqlalchemy.engine import Engine

from novamercado.api.gestor_modelo import GestorModelo
from novamercado.api.servicio import Resultado
from novamercado.esquemas import EstadoSalud

TIEMPO_ESPERA_SEG = 3


def verificar_bd(engine: Engine) -> Callable[[], bool]:
    def verificar() -> bool:
        try:
            with engine.connect() as con:
                con.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    return verificar


def verificar_mlflow(uri: str) -> Callable[[], bool]:
    def verificar() -> bool:
        try:
            return requests.get(f"{uri.rstrip('/')}/health", timeout=TIEMPO_ESPERA_SEG).status_code == 200
        except requests.RequestException:
            return False

    return verificar


def verificar_airflow(url: str) -> Callable[[], bool]:
    """Airflow está disponible si su webserver responde y el scheduler está sano."""

    def verificar() -> bool:
        try:
            r = requests.get(f"{url.rstrip('/')}/health", timeout=TIEMPO_ESPERA_SEG)
            return r.status_code == 200 and r.json().get("scheduler", {}).get("status") == "healthy"
        except (requests.RequestException, ValueError):
            return False

    return verificar


class VerificadorSalud:
    def __init__(self, gestor: GestorModelo, dependencias: dict[str, Callable[[], bool]]):
        self.gestor = gestor
        self.dependencias = dependencias  # nombre -> función que devuelve True si responde

    def estado(self) -> Resultado:
        caidas = [nombre for nombre, verificar in self.dependencias.items() if not verificar()]
        if self.gestor.actual is None:
            motivo = "no hay un modelo cargado todavía"
            if caidas:
                motivo += f"; no disponible: {', '.join(caidas)}"
            return Resultado(503, EstadoSalud(estado="degradado", motivo=motivo).model_dump())
        if caidas:
            motivo = (
                f"no disponible: {', '.join(caidas)}; se responde con el modelo cargado "
                f"(versión {self.gestor.actual.version})"
            )
            return Resultado(200, EstadoSalud(estado="degradado", motivo=motivo).model_dump())
        return Resultado(200, EstadoSalud(estado="ok").model_dump(exclude_none=True))
