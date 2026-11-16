"""Limpieza de solicitudes de ``POST /v1/prediccion``.

Política general:
- Problemas en datos de la solicitud completa (cuerpo, tienda, fecha, lista de familias)
  que no se pueden interpretar ⇒ rechazar (422): no hay a quién o para cuándo pronosticar.
- Problemas en un elemento de la lista ⇒ se descarta ese elemento con advertencia; la familia
  queda como faltante y se completa con el supuesto documentado.
- Correcciones inequívocas ⇒ reparar; interpretaciones con supuestos ⇒ advertir.
"""

from __future__ import annotations

from typing import Any

from novamercado.catalogo import Catalogo
from novamercado.esquemas import FamiliaSolicitada, SolicitudPrediccion
from novamercado.limpieza.calidad import RegistroCalidad, SolicitudRechazada
from novamercado.limpieza.comunes import (
    CamposEnConflicto,
    interpretar_familia,
    mapear_campos,
    resolver_fecha,
    resolver_tienda,
)
from novamercado.limpieza.normalizacion import interpretar_conteo

CAMPOS = ["tienda_id", "fecha", "familias"]
CAMPOS_FAMILIA = ["familia_id", "en_promocion"]

PROMOCION_SUPUESTA = 0


def limpiar_prediccion(
    payload: Any, catalogo: Catalogo
) -> tuple[SolicitudPrediccion, RegistroCalidad]:
    registro = RegistroCalidad()

    if not isinstance(payload, dict):
        raise SolicitudRechazada("el cuerpo de la solicitud debe ser un objeto JSON")
    try:
        campos = mapear_campos(payload, CAMPOS, "", registro)
    except CamposEnConflicto as e:
        raise SolicitudRechazada(str(e)) from e

    tienda_id = resolver_tienda(campos, catalogo, registro)
    fecha = resolver_fecha(campos, tienda_id, catalogo, registro)

    if catalogo.ultima_fecha_feriados and fecha > catalogo.ultima_fecha_feriados:
        registro.advertir(
            "fecha",
            f"la fecha es posterior a la cobertura de feriados.csv "
            f"({catalogo.ultima_fecha_feriados.isoformat()}); se supuso que no es feriado",
        )

    if "familias" not in campos:
        raise SolicitudRechazada("falta el campo obligatorio 'familias'")
    familias = campos["familias"]
    if not isinstance(familias, list):
        raise SolicitudRechazada("'familias' debe ser una lista")
    if not familias:
        raise SolicitudRechazada("'familias' está vacía: no hay familias que pronosticar")

    vendidas = catalogo.familias_de(tienda_id)
    promociones: dict[str, int] = {}  # conserva el orden de la solicitud

    for i, elemento in enumerate(familias):
        ruta = f"familias[{i}]"
        r = _limpiar_familia(elemento, ruta, catalogo, vendidas, registro)
        if r is None:
            continue
        familia_id, promo = r
        if familia_id in promociones:
            anterior = promociones[familia_id]
            if anterior == promo:
                registro.reparar(ruta, f"'{familia_id}' repetida con el mismo valor; se ignoró la repetición")
            else:
                registro.advertir(
                    ruta,
                    f"'{familia_id}' repetida con en_promocion {anterior} y {promo}; se usó el último valor ({promo})",
                )
                promociones[familia_id] = promo
            continue
        promociones[familia_id] = promo

    faltantes = sorted(vendidas - promociones.keys())
    if faltantes:
        registro.advertir(
            "familias",
            f"faltan familias que la tienda vende ({', '.join(faltantes)}); "
            f"se pronosticaron suponiendo en_promocion = {PROMOCION_SUPUESTA}",
        )
        for fid in faltantes:
            promociones[fid] = PROMOCION_SUPUESTA

    solicitud = SolicitudPrediccion(
        tienda_id=tienda_id,
        fecha=fecha,
        familias=[FamiliaSolicitada(familia_id=f, en_promocion=p) for f, p in promociones.items()],
    )
    return solicitud, registro


def _limpiar_familia(
    elemento: Any,
    ruta: str,
    catalogo: Catalogo,
    vendidas: frozenset[str],
    registro: RegistroCalidad,
) -> tuple[str, int] | None:
    """Devuelve ``(familia_id, en_promocion)`` o ``None`` si el elemento se descarta."""
    if not isinstance(elemento, dict):
        registro.advertir(ruta, "el elemento no es un objeto; se ignoró")
        return None
    try:
        campos = mapear_campos(elemento, CAMPOS_FAMILIA, f"{ruta}.", registro)
    except CamposEnConflicto as e:
        registro.advertir(ruta, f"{e}; se ignoró el elemento")
        return None

    if "familia_id" not in campos:
        registro.advertir(ruta, "el elemento no trae 'familia_id'; se ignoró")
        return None
    valor = campos["familia_id"]
    fam = interpretar_familia(valor, catalogo)
    if not fam.valida:
        registro.advertir(f"{ruta}.familia_id", f"familia {valor!r} desconocida; se ignoró el elemento")
        return None
    if fam.valor not in vendidas:
        registro.advertir(f"{ruta}.familia_id", f"la tienda no vende la familia '{fam.valor}'; se ignoró el elemento")
        return None
    registro.registrar(f"{ruta}.familia_id", fam.accion, fam.detalle)

    campo_promo = f"{ruta}.en_promocion"
    if campos.get("en_promocion") is None:
        registro.advertir(campo_promo, f"no se indicó en_promocion; se supuso {PROMOCION_SUPUESTA}")
        return fam.valor, PROMOCION_SUPUESTA

    valor = campos["en_promocion"]
    promo = interpretar_conteo(valor, "en_promocion")
    if not promo.valida:
        registro.advertir(campo_promo, f"en_promocion {valor!r} no es un número; se supuso {PROMOCION_SUPUESTA}")
        return fam.valor, PROMOCION_SUPUESTA
    if promo.valor < 0:
        registro.advertir(campo_promo, f"en_promocion {valor!r} es negativo; se supuso {PROMOCION_SUPUESTA}")
        return fam.valor, PROMOCION_SUPUESTA
    registro.registrar(campo_promo, promo.accion, promo.detalle)

    maximo = catalogo.promocion_maxima.get(fam.valor)
    if maximo is not None and promo.valor > maximo:
        registro.advertir(
            campo_promo,
            f"en_promocion {promo.valor} supera el máximo histórico de la familia ({maximo}); "
            "el pronóstico puede ser menos confiable",
        )
    return fam.valor, promo.valor
