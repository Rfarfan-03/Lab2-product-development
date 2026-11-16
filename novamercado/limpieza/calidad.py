"""Registro de lo que la limpieza hizo con cada solicitud."""

from __future__ import annotations

from dataclasses import dataclass, field

from novamercado.esquemas import Calidad, ObservacionCalidad
from novamercado.limpieza.normalizacion import ADVERTIR, REPARAR


class SolicitudRechazada(Exception):
    """La solicitud no se puede atender; se responde 422 con ``detail``."""

    def __init__(self, detalle: str):
        super().__init__(detalle)
        self.detalle = detalle


@dataclass
class RegistroCalidad:
    observaciones: list[ObservacionCalidad] = field(default_factory=list)

    def reparar(self, campo: str, detalle: str) -> None:
        self.observaciones.append(ObservacionCalidad(campo=campo, accion=REPARAR, detalle=detalle))

    def advertir(self, campo: str, detalle: str) -> None:
        self.observaciones.append(ObservacionCalidad(campo=campo, accion=ADVERTIR, detalle=detalle))

    def registrar(self, campo: str, accion: str | None, detalle: str | None) -> None:
        if accion == REPARAR:
            self.reparar(campo, detalle or "")
        elif accion == ADVERTIR:
            self.advertir(campo, detalle or "")

    @property
    def estado(self) -> str:
        acciones = {o.accion for o in self.observaciones}
        if ADVERTIR in acciones:
            return "advertencia"
        if REPARAR in acciones:
            return "corregido"
        return "ok"

    def a_calidad(self) -> Calidad:
        return Calidad(estado=self.estado, observaciones=list(self.observaciones))
