"""Catálogos publicados (tiendas, familias, feriados) que la limpieza necesita."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Tienda:
    tienda_id: int
    nombre: str
    ciudad: str
    tipo: str
    fecha_apertura: date


@dataclass(frozen=True)
class Catalogo:
    tiendas: dict[int, Tienda]
    familias: dict[str, str]  # familia_id -> nombre
    familias_por_tienda: dict[int, frozenset[str]]
    promocion_maxima: dict[str, int]  # máximo histórico de en_promocion por familia
    ultima_fecha_feriados: date | None  # hasta dónde cubre feriados.csv

    def familias_de(self, tienda_id: int) -> frozenset[str]:
        return self.familias_por_tienda.get(tienda_id, frozenset(self.familias))


def _leer(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def cargar_catalogo(datos_dir: str | Path) -> Catalogo:
    datos = Path(datos_dir)

    tiendas = {
        int(r["tienda_id"]): Tienda(
            tienda_id=int(r["tienda_id"]),
            nombre=r["nombre"],
            ciudad=r["ciudad"],
            tipo=r["tipo"],
            fecha_apertura=date.fromisoformat(r["fecha_apertura"]),
        )
        for r in _leer(datos / "tiendas.csv")
    }
    familias = {r["familia_id"]: r["nombre"] for r in _leer(datos / "familias.csv")}

    por_tienda: dict[int, set[str]] = defaultdict(set)
    promo_max: dict[str, int] = defaultdict(int)
    for r in _leer(datos / "historico_ventas.csv"):
        por_tienda[int(r["tienda_id"])].add(r["familia_id"])
        promo_max[r["familia_id"]] = max(promo_max[r["familia_id"]], int(r["en_promocion"]))

    fechas_feriados = [date.fromisoformat(r["fecha"]) for r in _leer(datos / "feriados.csv")]

    return Catalogo(
        tiendas=tiendas,
        familias=familias,
        familias_por_tienda={t: frozenset(f) for t, f in por_tienda.items()},
        promocion_maxima=dict(promo_max),
        ultima_fecha_feriados=max(fechas_feriados) if fechas_feriados else None,
    )
