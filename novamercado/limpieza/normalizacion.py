"""Reglas generales para interpretar valores que llegan en mal estado.

Cada función devuelve el valor interpretado junto con la acción que implica:
- ``None``: el valor ya venía en el formato del contrato.
- ``"reparar"``: la corrección es inequívoca.
- ``"advertir"``: se interpretó con un supuesto.
Si el valor no se puede interpretar, el valor devuelto es ``None`` y quien llama decide
la política (rechazar la solicitud o descartar el elemento).
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any

REPARAR = "reparar"
ADVERTIR = "advertir"


@dataclass(frozen=True)
class Interpretacion:
    valor: Any
    accion: str | None = None
    detalle: str | None = None

    @property
    def valida(self) -> bool:
        return self.valor is not None


INVALIDA = Interpretacion(None)


# --------------------------------------------------------------------------- texto


def quitar_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def normalizar_texto(texto: str) -> str:
    """Minúsculas, sin acentos y con cualquier separador convertido en ``_``."""
    texto = quitar_acentos(texto).lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", texto).strip("_")


_PALABRAS_VACIAS_CLAVE = {"id", "en", "de", "del", "la", "el", "los", "las"}


def _tokens(texto: str) -> list[str]:
    # separa camelCase ("tiendaId" -> "tienda Id") antes de normalizar
    texto = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", texto)
    return [t for t in normalizar_texto(texto).split("_") if t]


def formas_de_clave(clave: str) -> set[str]:
    """Formas compactas de un nombre de campo, para reconocer variantes.

    ``tienda_id``, ``tienda``, ``TiendaId`` e ``id_tienda`` comparten la forma ``tienda``;
    ``en_promocion`` y ``promociones`` comparten ``promocion``.
    """
    compacta = "".join(t for t in _tokens(clave) if t not in _PALABRAS_VACIAS_CLAVE)
    if not compacta:
        return set()
    formas = {compacta}
    if compacta.endswith("es") and len(compacta) > 4:
        formas.add(compacta[:-2])
    if compacta.endswith("s") and len(compacta) > 3:
        formas.add(compacta[:-1])
    return formas


# --------------------------------------------------------------------------- números


def _texto_a_numero(texto: str) -> float | None:
    s = texto.strip().replace(" ", "").replace(" ", "").replace("_", "")
    if not s:
        return None
    signo = ""
    if s[0] in "+-":
        signo, s = s[0], s[1:]
    if not s:
        return None

    if "," in s and "." in s:
        # el último separador es el decimal; el otro es de miles
        decimal = "," if s.rfind(",") > s.rfind(".") else "."
        miles = "." if decimal == "," else ","
        entera, _, fraccion = s.rpartition(decimal)
        grupos = entera.split(miles)
        if not _grupos_de_miles_validos(grupos) or not fraccion.isdigit():
            return None
        s = "".join(grupos) + "." + fraccion
    elif "," in s or "." in s:
        sep = "," if "," in s else "."
        partes = s.split(sep)
        if len(partes) > 2 or (
            len(partes) == 2 and len(partes[1]) == 3 and not partes[0].startswith("0")
        ):
            # "1,234" / "1.234.567": separador de miles
            if not _grupos_de_miles_validos(partes):
                return None
            s = "".join(partes)
        else:
            # "812,0" / "2.5": separador decimal
            s = partes[0] + "." + partes[1]
    try:
        numero = float(signo + s)
    except ValueError:
        return None
    return numero if math.isfinite(numero) else None


def _grupos_de_miles_validos(grupos: list[str]) -> bool:
    if not grupos or not all(g.isdigit() for g in grupos):
        return False
    return 1 <= len(grupos[0]) <= 3 and all(len(g) == 3 for g in grupos[1:])


def interpretar_numero(valor: Any) -> tuple[float | None, bool]:
    """Devuelve ``(numero, venia_como_texto)``. Los booleanos no son números."""
    if isinstance(valor, bool) or valor is None:
        return None, False
    if isinstance(valor, int):
        return float(valor), False
    if isinstance(valor, float):
        return (valor if math.isfinite(valor) else None), False
    if isinstance(valor, str):
        return _texto_a_numero(valor), True
    return None, False


def interpretar_conteo(valor: Any, campo: str) -> Interpretacion:
    """Interpreta una cantidad entera (unidades, productos en promoción).

    No decide sobre negativos: eso depende del campo y lo resuelve quien llama.
    """
    numero, venia_como_texto = interpretar_numero(valor)
    if numero is None:
        return INVALIDA
    if numero.is_integer():
        entero = int(numero)
        if venia_como_texto or isinstance(valor, float):
            return Interpretacion(entero, REPARAR, f"{valor!r} se interpretó como {entero}")
        return Interpretacion(entero)
    redondeado = int(round(numero))
    return Interpretacion(
        redondeado,
        ADVERTIR,
        f"{valor!r} no es un entero; se redondeó a {redondeado}",
    )


# --------------------------------------------------------------------------- fechas


def _fecha_o_none(anio: int, mes: int, dia: int) -> date | None:
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def interpretar_fecha(valor: Any) -> Interpretacion:
    """Interpreta una fecha. El formato del contrato es ``AAAA-MM-DD``.

    No consulta el reloj del sistema: solo valida que la fecha exista en el calendario.
    """
    if isinstance(valor, bool) or valor is None:
        return INVALIDA
    if isinstance(valor, int):
        valor = str(valor)
    if not isinstance(valor, str):
        return INVALIDA
    s = valor.strip()

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        f = _fecha_o_none(int(s[:4]), int(s[5:7]), int(s[8:10]))
        if f is None:
            return INVALIDA
        if s != valor:
            return Interpretacion(f, REPARAR, f"{valor!r} se interpretó como '{f.isoformat()}'")
        return Interpretacion(f)

    def reparada(f: date | None) -> Interpretacion:
        if f is None:
            return INVALIDA
        return Interpretacion(f, REPARAR, f"{valor!r} se interpretó como '{f.isoformat()}'")

    # Fecha con hora: "2025-11-17T00:00:00", "2025-11-17 08:30"
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?", s)
    if m:
        return reparada(_fecha_o_none(int(m[1]), int(m[2]), int(m[3])))

    # Año primero con otro separador: "2025/11/17", "2025.11.17"
    m = re.fullmatch(r"(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})", s)
    if m:
        return reparada(_fecha_o_none(int(m[1]), int(m[2]), int(m[3])))

    # Compacta: "20251117"
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
    if m:
        return reparada(_fecha_o_none(int(m[1]), int(m[2]), int(m[3])))

    # Año al final: "17/11/2025", "11-17-2025"
    m = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", s)
    if m:
        a, b, anio = int(m[1]), int(m[2]), int(m[3])
        if a > 12 and b <= 12:  # solo puede ser día/mes
            return reparada(_fecha_o_none(anio, b, a))
        if b > 12 and a <= 12:  # solo puede ser mes/día
            return reparada(_fecha_o_none(anio, a, b))
        if a == b:
            return reparada(_fecha_o_none(anio, a, a))
        f = _fecha_o_none(anio, b, a)
        if f is None:
            return INVALIDA
        # ambigua: se supone día/mes/año, el orden usado en Guatemala
        return Interpretacion(
            f,
            ADVERTIR,
            f"{valor!r} es ambigua; se supuso día/mes/año: '{f.isoformat()}'",
        )

    return INVALIDA
