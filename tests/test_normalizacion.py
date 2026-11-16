from datetime import date

import pytest

from novamercado.limpieza.normalizacion import (
    ADVERTIR,
    REPARAR,
    formas_de_clave,
    interpretar_conteo,
    interpretar_fecha,
    interpretar_numero,
    normalizar_texto,
)


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("LÁCTEOS", "lacteos"),
        ("lacteos ", "lacteos"),
        ("Frutas y Verduras", "frutas_y_verduras"),
        ("cuidado-personal", "cuidado_personal"),
    ],
)
def test_normalizar_texto(entrada, esperado):
    assert normalizar_texto(entrada) == esperado


@pytest.mark.parametrize("clave", ["tienda", "Tienda", "TiendaId", "id_tienda", "tienda-id"])
def test_formas_de_clave_tienda(clave):
    assert formas_de_clave(clave) & formas_de_clave("tienda_id")


def test_formas_de_clave_promocion():
    assert formas_de_clave("promociones") & formas_de_clave("en_promocion")


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        (5, 5.0),
        (2.0, 2.0),
        ("3", 3.0),
        ("1,234", 1234.0),
        ("812,0", 812.0),
        ("1.234.567", 1234567.0),
        ("1.234,5", 1234.5),
        ("1,234.5", 1234.5),
        ("2.5", 2.5),
        ("0,500", 0.5),
        (" 1 234 ", 1234.0),
        ("-4", -4.0),
    ],
)
def test_interpretar_numero(entrada, esperado):
    assert interpretar_numero(entrada)[0] == esperado


@pytest.mark.parametrize("entrada", [True, None, "abc", "", "1,23,4", float("nan"), [], {}])
def test_interpretar_numero_invalido(entrada):
    assert interpretar_numero(entrada)[0] is None


def test_conteo_entero_sin_cambios():
    r = interpretar_conteo(7, "x")
    assert (r.valor, r.accion) == (7, None)


@pytest.mark.parametrize("entrada", ["3", 2.0, "1,234", "812,0"])
def test_conteo_reparado(entrada):
    assert interpretar_conteo(entrada, "x").accion == REPARAR


def test_conteo_decimal_se_redondea_con_advertencia():
    r = interpretar_conteo(2.6, "x")
    assert (r.valor, r.accion) == (3, ADVERTIR)


@pytest.mark.parametrize(
    "entrada, esperado, accion",
    [
        ("2025-11-17", date(2025, 11, 17), None),
        ("2025-11-17T00:00:00", date(2025, 11, 17), REPARAR),
        ("2025-11-17 08:30", date(2025, 11, 17), REPARAR),
        ("17/11/2025", date(2025, 11, 17), REPARAR),
        ("11/17/2025", date(2025, 11, 17), REPARAR),
        ("2025/11/17", date(2025, 11, 17), REPARAR),
        ("20251117", date(2025, 11, 17), REPARAR),
        ("05/05/2025", date(2025, 5, 5), REPARAR),
        ("05/11/2025", date(2025, 11, 5), ADVERTIR),
    ],
)
def test_interpretar_fecha(entrada, esperado, accion):
    r = interpretar_fecha(entrada)
    assert (r.valor, r.accion) == (esperado, accion)


@pytest.mark.parametrize("entrada", ["2025-02-30", "mañana", "", None, True, "32/13/2025"])
def test_interpretar_fecha_invalida(entrada):
    assert not interpretar_fecha(entrada).valida
