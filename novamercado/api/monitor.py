"""Tarea de fondo: mantiene cargado el modelo vigente sin reiniciar la API.

Cada ``intervalo`` segundos consulta el alias en MLflow y, si apunta a otra versión, la
carga. Con 30 s, un modelo promovido empieza a usarse muy por debajo de los 2 minutos
exigidos. Si MLflow no responde, la API sigue con el modelo que ya tenía.
"""

from __future__ import annotations

import logging
import threading

from novamercado.api.gestor_modelo import GestorModelo

log = logging.getLogger(__name__)


class MonitorModelo:
    def __init__(self, gestor: GestorModelo, intervalo: float = 30.0):
        self.gestor = gestor
        self.intervalo = intervalo
        self._detener = threading.Event()
        self._hilo = threading.Thread(target=self._ciclo, name="monitor-modelo", daemon=True)

    def iniciar(self) -> None:
        self._hilo.start()

    def detener(self) -> None:
        self._detener.set()
        self._hilo.join(timeout=5)

    def revisar(self) -> None:
        try:
            self.gestor.actualizar()
        except Exception as e:  # MLflow caído o versión no cargable: se conserva la actual
            log.warning("No se pudo actualizar el modelo vigente: %s", e)

    def _ciclo(self) -> None:
        while not self._detener.wait(self.intervalo):
            self.revisar()
