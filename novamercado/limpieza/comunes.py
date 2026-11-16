"""Piezas de limpieza compartidas por predicción y observaciones."""

from __future__ import annotations

import difflib
import re
from datetime import date
from typing import Any

from novamercado.catalogo import Catalogo
from novamercado.limpieza.calidad import RegistroCalidad, SolicitudRechazada
from novamercado.limpieza.normalizacion import (
    ADVERTIR,
    INVALIDA,
    REPARAR,
    Interpretacion,
    formas_de_clave,
    interpretar_fecha,
    interpretar_numero,
    normalizar_texto,
)


class CamposEnConflicto(Exception):
    pass


def mapear_campos(
    objeto: dict[str, Any], campos: list[str], ruta: str, registro: RegistroCalidad
) -> dict[str, Any]:
    """Asocia las claves recibidas con los campos del contrato.

    - Clave idéntica al contrato: se usa tal cual.
    - Clave con otra forma (``tienda``, ``TiendaId``): se repara si corresponde a un único campo.
    - Clave que no corresponde a ningún campo: se ignora con advertencia.
    - Dos claves para el mismo campo con valores distintos: ``CamposEnConflicto``.
    """
    formas_campo = {c: formas_de_clave(c) for c in campos}
    resultado: dict[str, Any] = {}
    origen: dict[str, str] = {}

    claves = sorted(objeto, key=lambda k: k not in campos)  # primero las exactas
    for clave in claves:
        valor = objeto[clave]
        if clave in campos:
            destino = clave
        else:
            formas = formas_de_clave(str(clave))
            candidatos = [c for c, fc in formas_campo.items() if formas & fc]
            if len(candidatos) != 1:
                registro.advertir(f"{ruta}{clave}", f"campo '{clave}' no pertenece al contrato; se ignoró")
                continue
            destino = candidatos[0]

        if destino in resultado:
            if resultado[destino] != valor:
                raise CamposEnConflicto(
                    f"los campos '{origen[destino]}' y '{clave}' traen valores distintos para '{destino}'"
                )
            registro.reparar(f"{ruta}{destino}", f"campo '{clave}' repetido con el mismo valor; se ignoró")
            continue

        resultado[destino] = valor
        origen[destino] = clave
        if clave != destino:
            registro.reparar(f"{ruta}{destino}", f"el campo '{clave}' se interpretó como '{destino}'")
    return resultado


# --------------------------------------------------------------------------- tienda


def interpretar_tienda(valor: Any, catalogo: Catalogo) -> Interpretacion:
    """Identificador de tienda: entero, texto numérico, prefijo (``T05``) o nombre."""
    if isinstance(valor, bool) or valor is None:
        return INVALIDA
    if isinstance(valor, int):
        return Interpretacion(valor)
    if isinstance(valor, float):
        if valor.is_integer():
            return Interpretacion(int(valor), REPARAR, f"{valor!r} se interpretó como {int(valor)}")
        return INVALIDA
    if not isinstance(valor, str):
        return INVALIDA

    s = valor.strip()
    numero, _ = interpretar_numero(s)
    if numero is not None:
        if numero.is_integer():
            return Interpretacion(int(numero), REPARAR, f"{valor!r} se interpretó como {int(numero)}")
        return INVALIDA

    # Prefijo de letras seguido del número: "T05", "Tienda 5", "T-05"
    m = re.fullmatch(r"[^\W\d_]+[\s\-_#.]*(\d+)", s)
    if m:
        tid = int(m[1])
        return Interpretacion(tid, REPARAR, f"{valor!r} se interpretó como {tid}")

    # Nombre de la tienda, con o sin la marca
    buscado = normalizar_texto(s)
    for tienda in catalogo.tiendas.values():
        nombre = normalizar_texto(tienda.nombre)
        if buscado in (nombre, nombre.removeprefix("novamercado_")):
            return Interpretacion(
                tienda.tienda_id, REPARAR, f"{valor!r} se interpretó como {tienda.tienda_id}"
            )
    return INVALIDA


def resolver_tienda(campos: dict[str, Any], catalogo: Catalogo, registro: RegistroCalidad) -> int:
    if "tienda_id" not in campos:
        raise SolicitudRechazada("falta el campo obligatorio 'tienda_id'")
    valor = campos["tienda_id"]
    r = interpretar_tienda(valor, catalogo)
    if not r.valida:
        raise SolicitudRechazada(f"tienda_id {valor!r} no es un identificador de tienda válido")
    if r.valor not in catalogo.tiendas:
        raise SolicitudRechazada(f"la tienda {r.valor} no existe en el catálogo de tiendas")
    registro.registrar("tienda_id", r.accion, r.detalle)
    return r.valor


# --------------------------------------------------------------------------- fecha


def resolver_fecha(
    campos: dict[str, Any], tienda_id: int, catalogo: Catalogo, registro: RegistroCalidad
) -> date:
    if "fecha" not in campos:
        raise SolicitudRechazada("falta el campo obligatorio 'fecha'")
    valor = campos["fecha"]
    r = interpretar_fecha(valor)
    if not r.valida:
        raise SolicitudRechazada(f"fecha {valor!r} no es una fecha válida (formato AAAA-MM-DD)")
    apertura = catalogo.tiendas[tienda_id].fecha_apertura
    if r.valor < apertura:
        raise SolicitudRechazada(
            f"la fecha {r.valor.isoformat()} es anterior a la apertura de la tienda {tienda_id} "
            f"({apertura.isoformat()})"
        )
    registro.registrar("fecha", r.accion, r.detalle)
    return r.valor


# --------------------------------------------------------------------------- familia


def _formas_familia(texto: str) -> set[str]:
    n = normalizar_texto(texto)
    sin_conectores = "_".join(t for t in n.split("_") if t not in {"y", "e", "de"})
    return {n, n.replace("_", ""), sin_conectores, sin_conectores.replace("_", "")}


def interpretar_familia(valor: Any, catalogo: Catalogo) -> Interpretacion:
    """Familia por su id o su nombre, sin importar mayúsculas, acentos ni separadores.

    Una coincidencia aproximada única (error de escritura) se acepta con advertencia.
    """
    if not isinstance(valor, str):
        return INVALIDA
    if valor in catalogo.familias:
        return Interpretacion(valor)

    indice: dict[str, str] = {}
    for fid, nombre in catalogo.familias.items():
        for forma in _formas_familia(fid) | _formas_familia(nombre):
            indice[forma] = fid

    for forma in _formas_familia(valor):
        if forma in indice:
            fid = indice[forma]
            return Interpretacion(fid, REPARAR, f"{valor!r} se interpretó como '{fid}'")

    n = normalizar_texto(valor)
    cercanas = difflib.get_close_matches(n, list(indice), n=5, cutoff=0.85)
    ids = {indice[c] for c in cercanas}
    if len(ids) == 1:
        fid = ids.pop()
        return Interpretacion(fid, ADVERTIR, f"{valor!r} no coincide exactamente; se supuso '{fid}'")
    return INVALIDA
