"""Fixtures comunes. Las pruebas no dependen de los datos publicados ni de MLflow."""

from __future__ import annotations

import copy
from datetime import date

import pytest

from novamercado.catalogo import Catalogo, Tienda

FAMILIAS = {
    "abarrotes": "Abarrotes",
    "bebidas": "Bebidas",
    "lacteos": "Lácteos",
    "carnes": "Carnes",
    "panaderia": "Panadería",
    "frutas_verduras": "Frutas y verduras",
    "limpieza": "Limpieza",
    "cuidado_personal": "Cuidado personal",
    "licores": "Licores",
    "snacks": "Snacks y dulces",
    "bebe": "Bebé",
    "mascotas": "Mascotas",
}


@pytest.fixture
def catalogo() -> Catalogo:
    tiendas = {
        5: Tienda(5, "NovaMercado Quetzaltenango", "Quetzaltenango", "hipermercado", date(2019, 1, 1)),
        6: Tienda(6, "NovaMercado Antigua", "Antigua Guatemala", "supermercado", date(2019, 1, 1)),
        10: Tienda(10, "NovaMercado Express Zona 16", "Guatemala", "express", date(2025, 3, 15)),
    }
    todas = frozenset(FAMILIAS)
    return Catalogo(
        tiendas=tiendas,
        familias=dict(FAMILIAS),
        familias_por_tienda={5: todas, 6: todas, 10: todas - {"licores"}},
        promocion_maxima={f: 19 for f in FAMILIAS},
        ultima_fecha_feriados=date(2026, 12, 31),
    )


_PROMOS = {"bebidas": 8, "snacks": 9}


@pytest.fixture
def prediccion_valida() -> dict:
    return {
        "tienda_id": 5,
        "fecha": "2025-11-17",
        "familias": [
            {"familia_id": f, "en_promocion": _PROMOS.get(f, 0)} for f in sorted(FAMILIAS)
        ],
    }


@pytest.fixture
def observacion_valida() -> dict:
    return {
        "tienda_id": 5,
        "fecha": "2025-11-17",
        "ventas": [{"familia_id": f, "ventas": 100 + i} for i, f in enumerate(sorted(FAMILIAS))],
    }


def copia(d: dict) -> dict:
    return copy.deepcopy(d)
