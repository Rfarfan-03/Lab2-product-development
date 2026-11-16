"""Lógica de ``POST /admin/reentrenar`` y ``GET /admin/reentrenar/{id}``."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.engine import Engine

from novamercado.api.airflow_cliente import AirflowNoDisponible, ClienteAirflow
from novamercado.api.gestor_modelo import GestorModelo
from novamercado.api.servicio import Resultado
from novamercado.db import repositorio
from novamercado.esquemas import EstadoReentrenamiento, RespuestaReentrenar

log = logging.getLogger(__name__)

FINALES = ("exitoso", "fallido")


class AdminReentrenamiento:
    def __init__(self, engine: Engine, airflow: ClienteAirflow, gestor: GestorModelo):
        self.engine = engine
        self.airflow = airflow
        self.gestor = gestor

    def iniciar(self) -> Resultado:
        id_ejecucion = f"reentrenamiento-{uuid.uuid4().hex}"
        # La fila existe antes de disparar: el DAG siempre encuentra dónde dejar su resultado
        with self.engine.begin() as con:
            repositorio.registrar_reentrenamiento(con, id_ejecucion)
        try:
            self.airflow.disparar(id_ejecucion)
        except AirflowNoDisponible as e:
            log.warning("No se pudo iniciar el reentrenamiento: %s", e)
            with self.engine.begin() as con:
                repositorio.finalizar_reentrenamiento(
                    con, id_ejecucion, "fallido", False, self._version_actual(),
                    f"No se pudo iniciar en Airflow: {e}",
                )
            return Resultado(503, {"detail": "no se pudo iniciar el reentrenamiento: Airflow no está disponible"})
        return Resultado(202, RespuestaReentrenar(id=id_ejecucion).model_dump())

    def consultar(self, id_ejecucion: str) -> Resultado:
        with self.engine.connect() as con:
            fila = repositorio.obtener_reentrenamiento(con, id_ejecucion)
        if fila is None:
            return Resultado(404, {"detail": f"no existe la ejecución '{id_ejecucion}'"})

        if fila["estado"] not in FINALES:
            fila = self._sincronizar_con_airflow(id_ejecucion, fila)

        if fila["estado"] not in FINALES:
            return Resultado(200, EstadoReentrenamiento(estado="en_curso").model_dump(exclude_none=True))
        estado = EstadoReentrenamiento(
            estado=fila["estado"],
            promovido=bool(fila["promovido"]),
            version=fila["version"] or self._version_actual(),
            motivo=fila["motivo"] or "",
        )
        return Resultado(200, estado.model_dump(exclude_none=True))

    def _sincronizar_con_airflow(self, id_ejecucion: str, fila: dict) -> dict:
        """Detecta ejecuciones que Airflow terminó sin que el DAG registrara su resultado."""
        try:
            estado_airflow = self.airflow.estado(id_ejecucion)
        except AirflowNoDisponible:
            return fila  # sin información nueva: sigue en curso
        if estado_airflow == "failed":
            with self.engine.begin() as con:
                fila = repositorio.obtener_reentrenamiento(con, id_ejecucion)
                if fila["estado"] not in FINALES:
                    repositorio.finalizar_reentrenamiento(
                        con, id_ejecucion, "fallido", False, self._version_actual(),
                        "La ejecución falló en Airflow; se mantiene el modelo vigente",
                    )
                    fila = repositorio.obtener_reentrenamiento(con, id_ejecucion)
        elif estado_airflow == "success":
            with self.engine.connect() as con:
                fila = repositorio.obtener_reentrenamiento(con, id_ejecucion)
        return fila

    def _version_actual(self) -> str | None:
        """Versión vigente: la del último reentrenamiento terminado o, si no hay, la cargada."""
        with self.engine.connect() as con:
            registrada = repositorio.ultima_version_vigente_registrada(con)
        if registrada:
            return registrada
        cargado = self.gestor.actual
        return cargado.version if cargado else None
