"""Operaciones sobre la base de datos del producto."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.engine import Connection, Engine

from novamercado.db.esquema import (
    correcciones,
    historico_ventas,
    metadata,
    observaciones,
    predicciones,
    reentrenamientos,
    solicitudes,
)
from novamercado.esquemas import ObservacionCalidad, SolicitudObservaciones

log = logging.getLogger(__name__)


def crear_tablas(engine: Engine) -> None:
    metadata.create_all(engine)


def cargar_historico_si_vacio(engine: Engine, datos_dir: str | Path) -> int:
    """Carga historico_ventas.csv solo si la tabla está vacía. Devuelve filas cargadas."""
    with engine.begin() as con:
        if con.execute(select(func.count()).select_from(historico_ventas)).scalar():
            return 0
        df = pd.read_csv(Path(datos_dir) / "historico_ventas.csv", parse_dates=["fecha"])
        df["fecha"] = df["fecha"].dt.date
        filas = df[["fecha", "tienda_id", "familia_id", "ventas", "en_promocion"]].to_dict("records")
        for i in range(0, len(filas), 5000):
            con.execute(insert(historico_ventas), filas[i : i + 5000])
    log.info("Histórico cargado: %d filas", len(filas))
    return len(filas)


# --------------------------------------------------------------------------- solicitudes


def registrar_solicitud(
    con: Connection,
    tipo: str,
    cuerpo: Any,
    estado: str,
    tienda_id: int | None = None,
    fecha: date | None = None,
    detalle_rechazo: str | None = None,
    observaciones_calidad: list[ObservacionCalidad] | None = None,
) -> int:
    solicitud_id = con.execute(
        insert(solicitudes).values(
            tipo=tipo,
            cuerpo=cuerpo,
            estado=estado,
            tienda_id=tienda_id,
            fecha=fecha,
            detalle_rechazo=detalle_rechazo,
        )
    ).inserted_primary_key[0]
    if observaciones_calidad:
        con.execute(
            insert(correcciones),
            [
                {"solicitud_id": solicitud_id, "campo": o.campo, "accion": o.accion, "detalle": o.detalle}
                for o in observaciones_calidad
            ],
        )
    return solicitud_id


def registrar_predicciones(con: Connection, solicitud_id: int, filas: list[dict]) -> None:
    con.execute(insert(predicciones), [{"solicitud_id": solicitud_id, **f} for f in filas])


# --------------------------------------------------------------------------- observaciones


def guardar_observaciones(con: Connection, solicitud: SolicitudObservaciones, solicitud_id: int) -> int:
    """Inserta o actualiza ventas reales. Devuelve cuántos registros son nuevos o cambiaron.

    Reenviar una observación idéntica no modifica nada y devuelve 0.
    """
    if not solicitud.ventas:
        return 0
    familias = [v.familia_id for v in solicitud.ventas]
    existentes = dict(
        con.execute(
            select(observaciones.c.familia_id, observaciones.c.ventas).where(
                and_(
                    observaciones.c.tienda_id == solicitud.tienda_id,
                    observaciones.c.fecha == solicitud.fecha,
                    observaciones.c.familia_id.in_(familias),
                )
            )
        ).all()
    )
    guardados = 0
    for v in solicitud.ventas:
        if v.familia_id not in existentes:
            con.execute(
                insert(observaciones).values(
                    fecha=solicitud.fecha,
                    tienda_id=solicitud.tienda_id,
                    familia_id=v.familia_id,
                    ventas=v.ventas,
                    solicitud_id=solicitud_id,
                )
            )
            guardados += 1
        elif existentes[v.familia_id] != v.ventas:
            con.execute(
                update(observaciones)
                .where(
                    and_(
                        observaciones.c.tienda_id == solicitud.tienda_id,
                        observaciones.c.fecha == solicitud.fecha,
                        observaciones.c.familia_id == v.familia_id,
                    )
                )
                .values(ventas=v.ventas, solicitud_id=solicitud_id)
            )
            guardados += 1
    return guardados


# --------------------------------------------------------------------------- historia para predecir


def historia_reciente(con: Connection, tienda_id: int, fecha: date, dias: int) -> pd.DataFrame:
    """Ventas de la tienda en los ``dias`` anteriores a ``fecha`` (sin incluirla).

    Combina el histórico publicado y las observaciones registradas; si ambos tienen la
    misma tienda, familia y fecha, prevalece la observación.
    """
    desde = fecha - timedelta(days=dias)
    columnas = ["fecha", "tienda_id", "familia_id", "ventas"]
    partes = []
    for tabla in (historico_ventas, observaciones):  # el orden define la prioridad
        filas = con.execute(
            select(tabla.c.fecha, tabla.c.tienda_id, tabla.c.familia_id, tabla.c.ventas).where(
                and_(tabla.c.tienda_id == tienda_id, tabla.c.fecha >= desde, tabla.c.fecha < fecha)
            )
        ).all()
        partes.append(pd.DataFrame(filas, columns=columnas))
    df = pd.concat(partes, ignore_index=True)
    df = df.drop_duplicates(["fecha", "tienda_id", "familia_id"], keep="last")
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["ventas"] = df["ventas"].astype(float)
    return df


# --------------------------------------------------------------------------- reentrenamientos


def registrar_reentrenamiento(con: Connection, id_ejecucion: str) -> None:
    con.execute(insert(reentrenamientos).values(id=id_ejecucion, estado="en_curso"))


def finalizar_reentrenamiento(
    con: Connection,
    id_ejecucion: str,
    estado: str,
    promovido: bool,
    version: str | None,
    motivo: str,
    version_candidata: str | None = None,
) -> None:
    """Guarda el resultado; crea la fila si la ejecución no se pidió por la API."""
    valores = dict(
        estado=estado,
        promovido=promovido,
        version=version,
        version_candidata=version_candidata,
        motivo=motivo,
        terminado_en=func.now(),
    )
    actualizadas = con.execute(
        update(reentrenamientos).where(reentrenamientos.c.id == id_ejecucion).values(**valores)
    ).rowcount
    if not actualizadas:
        con.execute(insert(reentrenamientos).values(id=id_ejecucion, **valores))


def obtener_reentrenamiento(con: Connection, id_ejecucion: str) -> dict | None:
    fila = con.execute(select(reentrenamientos).where(reentrenamientos.c.id == id_ejecucion)).mappings().first()
    return dict(fila) if fila else None


# --------------------------------------------------------------------------- datos para reentrenar


def ventas_para_entrenar(con: Connection) -> pd.DataFrame:
    """Histórico + observaciones registradas, con la promoción informada en la última
    solicitud de pronóstico de esa tienda, fecha y familia (las observaciones no la traen)."""
    hist = pd.DataFrame(
        con.execute(
            select(
                historico_ventas.c.fecha,
                historico_ventas.c.tienda_id,
                historico_ventas.c.familia_id,
                historico_ventas.c.ventas,
                historico_ventas.c.en_promocion,
            )
        ).all(),
        columns=["fecha", "tienda_id", "familia_id", "ventas", "en_promocion"],
    )
    obs = pd.DataFrame(
        con.execute(
            select(observaciones.c.fecha, observaciones.c.tienda_id, observaciones.c.familia_id, observaciones.c.ventas)
        ).all(),
        columns=["fecha", "tienda_id", "familia_id", "ventas"],
    )
    ultima = (
        select(func.max(predicciones.c.id).label("id"))
        .group_by(predicciones.c.tienda_id, predicciones.c.fecha, predicciones.c.familia_id)
        .subquery()
    )
    promos = pd.DataFrame(
        con.execute(
            select(predicciones.c.fecha, predicciones.c.tienda_id, predicciones.c.familia_id, predicciones.c.en_promocion)
            .join(ultima, predicciones.c.id == ultima.c.id)
        ).all(),
        columns=["fecha", "tienda_id", "familia_id", "en_promocion"],
    )
    obs = obs.merge(promos, on=["fecha", "tienda_id", "familia_id"], how="left")
    df = pd.concat([hist, obs], ignore_index=True)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.drop_duplicates(["fecha", "tienda_id", "familia_id"], keep="last")
    return df.sort_values(["fecha", "tienda_id", "familia_id"]).reset_index(drop=True)
