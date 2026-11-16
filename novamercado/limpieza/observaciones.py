"""Limpieza de solicitudes de ``POST /v1/observaciones``.

Las observaciones son la verdad con la que se reentrena, por eso no se inventan valores:
un registro de ventas que no se puede interpretar sin supuestos sobre su magnitud
(negativo, vacío, no numérico) se descarta con advertencia en lugar de guardarse.
"""

from __future__ import annotations

from typing import Any

from novamercado.catalogo import Catalogo
from novamercado.esquemas import SolicitudObservaciones, VentaObservada
from novamercado.limpieza.calidad import RegistroCalidad, SolicitudRechazada
from novamercado.limpieza.comunes import (
    CamposEnConflicto,
    interpretar_familia,
    mapear_campos,
    resolver_fecha,
    resolver_tienda,
)
from novamercado.limpieza.normalizacion import interpretar_conteo

CAMPOS = ["tienda_id", "fecha", "ventas"]
CAMPOS_VENTA = ["familia_id", "ventas"]


def limpiar_observaciones(
    payload: Any, catalogo: Catalogo
) -> tuple[SolicitudObservaciones, RegistroCalidad]:
    registro = RegistroCalidad()

    if not isinstance(payload, dict):
        raise SolicitudRechazada("el cuerpo de la solicitud debe ser un objeto JSON")
    try:
        campos = mapear_campos(payload, CAMPOS, "", registro)
    except CamposEnConflicto as e:
        raise SolicitudRechazada(str(e)) from e

    tienda_id = resolver_tienda(campos, catalogo, registro)
    fecha = resolver_fecha(campos, tienda_id, catalogo, registro)

    if "ventas" not in campos:
        raise SolicitudRechazada("falta el campo obligatorio 'ventas'")
    ventas = campos["ventas"]
    if not isinstance(ventas, list):
        raise SolicitudRechazada("'ventas' debe ser una lista")
    if not ventas:
        raise SolicitudRechazada("'ventas' está vacía: no hay ventas que registrar")

    vendidas = catalogo.familias_de(tienda_id)
    valores: dict[str, int] = {}

    for i, elemento in enumerate(ventas):
        ruta = f"ventas[{i}]"
        r = _limpiar_venta(elemento, ruta, catalogo, vendidas, registro)
        if r is None:
            continue
        familia_id, unidades = r
        if familia_id in valores:
            anterior = valores[familia_id]
            if anterior == unidades:
                registro.reparar(ruta, f"'{familia_id}' repetida con el mismo valor; se ignoró la repetición")
            else:
                registro.advertir(
                    ruta,
                    f"'{familia_id}' repetida con ventas {anterior} y {unidades}; se usó el último valor ({unidades})",
                )
                valores[familia_id] = unidades
            continue
        valores[familia_id] = unidades

    solicitud = SolicitudObservaciones(
        tienda_id=tienda_id,
        fecha=fecha,
        ventas=[VentaObservada(familia_id=f, ventas=v) for f, v in valores.items()],
    )
    return solicitud, registro


def _limpiar_venta(
    elemento: Any,
    ruta: str,
    catalogo: Catalogo,
    vendidas: frozenset[str],
    registro: RegistroCalidad,
) -> tuple[str, int] | None:
    if not isinstance(elemento, dict):
        registro.advertir(ruta, "el elemento no es un objeto; se descartó")
        return None
    try:
        campos = mapear_campos(elemento, CAMPOS_VENTA, f"{ruta}.", registro)
    except CamposEnConflicto as e:
        registro.advertir(ruta, f"{e}; se descartó el elemento")
        return None

    if "familia_id" not in campos:
        registro.advertir(ruta, "el elemento no trae 'familia_id'; se descartó")
        return None
    valor = campos["familia_id"]
    fam = interpretar_familia(valor, catalogo)
    if not fam.valida:
        registro.advertir(f"{ruta}.familia_id", f"familia {valor!r} desconocida; se descartó el elemento")
        return None
    if fam.valor not in vendidas:
        registro.advertir(f"{ruta}.familia_id", f"la tienda no vende la familia '{fam.valor}'; se descartó el elemento")
        return None
    registro.registrar(f"{ruta}.familia_id", fam.accion, fam.detalle)

    campo_ventas = f"{ruta}.ventas"
    if campos.get("ventas") is None:
        registro.advertir(campo_ventas, "no se indicaron las ventas; se descartó el registro")
        return None
    valor = campos["ventas"]
    unidades = interpretar_conteo(valor, "ventas")
    if not unidades.valida:
        registro.advertir(campo_ventas, f"ventas {valor!r} no es un número; se descartó el registro")
        return None
    if unidades.valor < 0:
        registro.advertir(
            campo_ventas,
            f"ventas {valor!r} es negativo (posible devolución); se descartó el registro",
        )
        return None
    registro.registrar(campo_ventas, unidades.accion, unidades.detalle)
    return fam.valor, unidades.valor
