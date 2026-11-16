"""Modelo vigente en memoria.

La API predice siempre con el modelo que tiene cargado; consultar MLflow solo sirve para
saber si hay una versión vigente distinta y cargarla. Si MLflow no responde, el modelo
cargado se conserva.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModeloCargado:
    modelo: Any  # objeto con predict(DataFrame) -> DataFrame
    nombre: str
    alias: str
    version: str


class GestorModelo:
    def __init__(
        self,
        consultar_version: Callable[[], str | None] | None = None,
        cargar_version: Callable[[str], ModeloCargado] | None = None,
    ):
        self._consultar_version = consultar_version
        self._cargar_version = cargar_version
        self._actual: ModeloCargado | None = None
        self._lock = threading.Lock()

    @property
    def actual(self) -> ModeloCargado | None:
        return self._actual

    def establecer(self, modelo: ModeloCargado) -> None:
        with self._lock:
            self._actual = modelo

    def actualizar(self) -> bool:
        """Carga la versión vigente si es distinta de la cargada. Devuelve True si cambió.

        Lanza la excepción si MLflow no responde; el modelo cargado no se toca.
        """
        if self._consultar_version is None or self._cargar_version is None:
            return False
        version = self._consultar_version()
        if version is None or (self._actual is not None and self._actual.version == version):
            return False
        nuevo = self._cargar_version(version)
        self.establecer(nuevo)
        log.info("Modelo vigente cargado: %s versión %s", nuevo.nombre, nuevo.version)
        return True


def gestor_mlflow() -> GestorModelo:
    """Gestor conectado al Model Registry de MLflow (MLFLOW_TRACKING_URI)."""
    import mlflow.pyfunc

    from novamercado.modelo.registro import ALIAS_VIGENTE, NOMBRE_MODELO, uri_version, version_vigente

    def consultar() -> str | None:
        v = version_vigente()
        return str(v.version) if v is not None else None

    def cargar(version: str) -> ModeloCargado:
        modelo = mlflow.pyfunc.load_model(uri_version(version))
        return ModeloCargado(modelo=modelo, nombre=NOMBRE_MODELO, alias=ALIAS_VIGENTE, version=version)

    return GestorModelo(consultar, cargar)
