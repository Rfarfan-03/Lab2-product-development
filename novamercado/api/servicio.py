"""Lógica de los endpoints: limpieza → modelo → registro en la base de datos.

Los endpoints de FastAPI solo delegan aquí; la limpieza vive en ``novamercado.limpieza``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd
from sqlalchemy.engine import Engine

from novamercado.api.gestor_modelo import GestorModelo
from novamercado.catalogo import Catalogo
from novamercado.db import repositorio
from novamercado.esquemas import (
    PrediccionFamilia,
    RespuestaObservaciones,
    RespuestaPrediccion,
)
from novamercado.limpieza import SolicitudRechazada, limpiar_observaciones, limpiar_prediccion
from novamercado.modelo.features import DIAS_HISTORIA_NECESARIOS, construir_features

log = logging.getLogger(__name__)


@dataclass
class Resultado:
    codigo: int
    cuerpo: dict


class SinModelo(Exception):
    pass


class Servicio:
    def __init__(
        self,
        engine: Engine,
        catalogo: Catalogo,
        feriados: pd.DataFrame,
        tiendas: pd.DataFrame,
        gestor: GestorModelo,
    ):
        self.engine = engine
        self.catalogo = catalogo
        self.feriados = feriados
        self.tiendas = tiendas
        self.gestor = gestor

    # ------------------------------------------------------------------ predicción

    def predecir(self, payload: Any) -> Resultado:
        try:
            solicitud, registro = limpiar_prediccion(payload, self.catalogo)
        except SolicitudRechazada as e:
            return self._rechazar("prediccion", payload, e.detalle)

        cargado = self.gestor.actual
        if cargado is None:
            with self.engine.begin() as con:
                repositorio.registrar_solicitud(
                    con, "prediccion", payload, "no_atendida",
                    tienda_id=solicitud.tienda_id, fecha=solicitud.fecha,
                    detalle_rechazo="no hay un modelo cargado",
                )
            return Resultado(503, {"detail": "no hay un modelo cargado todavía"})

        objetivos = pd.DataFrame(
            [
                {
                    "fecha": pd.Timestamp(solicitud.fecha),
                    "tienda_id": solicitud.tienda_id,
                    "familia_id": f.familia_id,
                    "en_promocion": f.en_promocion,
                }
                for f in solicitud.familias
            ]
        )
        with self.engine.connect() as con:
            historia = repositorio.historia_reciente(con, solicitud.tienda_id, solicitud.fecha, DIAS_HISTORIA_NECESARIOS)
        X = construir_features(historia, objetivos, self.feriados, self.tiendas)
        salida = cargado.modelo.predict(X)

        predicciones = [
            PrediccionFamilia(
                familia_id=f.familia_id,
                venta_esperada=float(esperada),
                cantidad_sugerida=int(sugerida),
            )
            for f, esperada, sugerida in zip(
                solicitud.familias, salida["venta_esperada"], salida["cantidad_sugerida"]
            )
        ]
        calidad = registro.a_calidad()
        respuesta = RespuestaPrediccion(
            tienda_id=solicitud.tienda_id,
            fecha=solicitud.fecha.isoformat(),
            version_modelo=cargado.version,
            predicciones=predicciones,
            calidad=calidad,
        )

        with self.engine.begin() as con:
            solicitud_id = repositorio.registrar_solicitud(
                con, "prediccion", payload, calidad.estado,
                tienda_id=solicitud.tienda_id, fecha=solicitud.fecha,
                observaciones_calidad=calidad.observaciones,
            )
            repositorio.registrar_predicciones(
                con,
                solicitud_id,
                [
                    {
                        "tienda_id": solicitud.tienda_id,
                        "fecha": solicitud.fecha,
                        "familia_id": p.familia_id,
                        "en_promocion": f.en_promocion,
                        "venta_esperada": p.venta_esperada,
                        "cantidad_sugerida": p.cantidad_sugerida,
                        "version_modelo": cargado.version,
                    }
                    for p, f in zip(predicciones, solicitud.familias)
                ],
            )
        return Resultado(200, respuesta.model_dump())

    # ------------------------------------------------------------------ observaciones

    def observar(self, payload: Any) -> Resultado:
        try:
            solicitud, registro = limpiar_observaciones(payload, self.catalogo)
        except SolicitudRechazada as e:
            return self._rechazar("observaciones", payload, e.detalle)

        calidad = registro.a_calidad()
        with self.engine.begin() as con:
            solicitud_id = repositorio.registrar_solicitud(
                con, "observaciones", payload, calidad.estado,
                tienda_id=solicitud.tienda_id, fecha=solicitud.fecha,
                observaciones_calidad=calidad.observaciones,
            )
            guardados = repositorio.guardar_observaciones(con, solicitud, solicitud_id)
        return Resultado(200, RespuestaObservaciones(registros_guardados=guardados, calidad=calidad).model_dump())

    # ------------------------------------------------------------------ comunes

    def _rechazar(self, tipo: str, payload: Any, detalle: str) -> Resultado:
        with self.engine.begin() as con:
            repositorio.registrar_solicitud(con, tipo, payload, "rechazada", detalle_rechazo=detalle)
        return Resultado(422, {"detail": detalle})

    def rechazar_cuerpo_invalido(self, tipo: str, cuerpo_crudo: str, detalle: str) -> Resultado:
        return self._rechazar(tipo, {"cuerpo_crudo": cuerpo_crudo}, detalle)
