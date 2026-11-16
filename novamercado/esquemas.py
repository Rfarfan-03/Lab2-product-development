"""Modelos de Pydantic del contrato del servicio (Anexo del laboratorio).

Las solicitudes llegan crudas y pasan primero por ``novamercado.limpieza``; estos modelos
validan la forma canónica resultante y la forma de cada respuesta.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EstadoCalidad = Literal["ok", "corregido", "advertencia"]
AccionCalidad = Literal["reparar", "advertir"]


class _Estricto(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


# --------------------------------------------------------------------------- calidad


class ObservacionCalidad(BaseModel):
    campo: str
    accion: AccionCalidad
    detalle: str


class Calidad(BaseModel):
    estado: EstadoCalidad
    observaciones: list[ObservacionCalidad] = Field(default_factory=list)

    @model_validator(mode="after")
    def _estado_coherente(self) -> "Calidad":
        acciones = {o.accion for o in self.observaciones}
        esperado = (
            "advertencia" if "advertir" in acciones else "corregido" if acciones else "ok"
        )
        if self.estado != esperado:
            raise ValueError(
                f"estado '{self.estado}' no corresponde a las observaciones (se esperaba '{esperado}')"
            )
        return self


# --------------------------------------------------------------------------- predicción


class FamiliaSolicitada(_Estricto):
    familia_id: str
    en_promocion: int = Field(ge=0)


class SolicitudPrediccion(_Estricto):
    """Solicitud de pronóstico ya limpia."""

    tienda_id: int
    fecha: date
    familias: list[FamiliaSolicitada] = Field(min_length=1)


class PrediccionFamilia(BaseModel):
    familia_id: str
    venta_esperada: float
    cantidad_sugerida: int = Field(ge=0)


class RespuestaPrediccion(BaseModel):
    tienda_id: int
    fecha: str
    version_modelo: str
    predicciones: list[PrediccionFamilia]
    calidad: Calidad


# --------------------------------------------------------------------------- observaciones


class VentaObservada(_Estricto):
    familia_id: str
    ventas: int = Field(ge=0)


class SolicitudObservaciones(_Estricto):
    """Observación de ventas reales ya limpia (puede quedar sin ventas válidas)."""

    tienda_id: int
    fecha: date
    ventas: list[VentaObservada]


class RespuestaObservaciones(BaseModel):
    registros_guardados: int = Field(ge=0)
    calidad: Calidad


# --------------------------------------------------------------------------- administración


class RespuestaReentrenar(BaseModel):
    id: str


class EstadoReentrenamiento(BaseModel):
    estado: Literal["en_curso", "exitoso", "fallido"]
    # Se incluyen solo cuando la ejecución termina
    promovido: bool | None = None
    version: str | None = None
    motivo: str | None = None


class InfoModelo(BaseModel):
    nombre: str
    alias: str
    version: str


class EstadoSalud(BaseModel):
    estado: Literal["ok", "degradado"]
    motivo: str | None = None
