import pytest

from novamercado.limpieza import SolicitudRechazada, limpiar_observaciones
from tests.conftest import copia


def ventas(sol):
    return {v.familia_id: v.ventas for v in sol.ventas}


def acciones(registro):
    return [(o.campo, o.accion) for o in registro.observaciones]


def test_observacion_valida_queda_ok(catalogo, observacion_valida):
    sol, reg = limpiar_observaciones(observacion_valida, catalogo)
    assert reg.estado == "ok"
    assert len(sol.ventas) == 12


def test_e08_ventas_negativas_se_descartan(catalogo, observacion_valida):
    o = copia(observacion_valida)
    o["ventas"][5]["ventas"] = -4
    sol, reg = limpiar_observaciones(o, catalogo)
    assert o["ventas"][5]["familia_id"] not in ventas(sol)
    assert len(sol.ventas) == 11
    assert acciones(reg) == [("ventas[5].ventas", "advertir")]


@pytest.mark.parametrize("valor, esperado", [("1,234", 1234), ("812,0", 812), ("50", 50), (50.0, 50)])
def test_e10_numero_con_formato_se_repara(catalogo, observacion_valida, valor, esperado):
    o = copia(observacion_valida)
    o["ventas"][1]["ventas"] = valor
    sol, reg = limpiar_observaciones(o, catalogo)
    assert ventas(sol)[o["ventas"][1]["familia_id"]] == esperado
    assert acciones(reg) == [("ventas[1].ventas", "reparar")]


@pytest.mark.parametrize("valor", [None, "n/a", True])
def test_ventas_no_interpretables_se_descartan(catalogo, observacion_valida, valor):
    o = copia(observacion_valida)
    o["ventas"][1]["ventas"] = valor
    sol, reg = limpiar_observaciones(o, catalogo)
    assert len(sol.ventas) == 11
    assert reg.estado == "advertencia"


def test_ventas_decimales_se_redondean_con_advertencia(catalogo, observacion_valida):
    o = copia(observacion_valida)
    o["ventas"][1]["ventas"] = 10.4
    sol, reg = limpiar_observaciones(o, catalogo)
    assert ventas(sol)[o["ventas"][1]["familia_id"]] == 10
    assert reg.estado == "advertencia"


def test_familia_repetida_en_observacion(catalogo, observacion_valida):
    o = copia(observacion_valida)
    primera = o["ventas"][0]["familia_id"]
    o["ventas"].append({"familia_id": primera, "ventas": 7})
    sol, reg = limpiar_observaciones(o, catalogo)
    assert ventas(sol)[primera] == 7
    assert reg.estado == "advertencia"


def test_observacion_parcial_no_genera_advertencia(catalogo, observacion_valida):
    o = copia(observacion_valida)
    o["ventas"] = o["ventas"][:3]
    sol, reg = limpiar_observaciones(o, catalogo)
    assert len(sol.ventas) == 3
    assert reg.estado == "ok"


def test_todas_las_ventas_invalidas_no_se_rechaza(catalogo, observacion_valida):
    o = copia(observacion_valida)
    for v in o["ventas"]:
        v["ventas"] = -1
    sol, reg = limpiar_observaciones(o, catalogo)
    assert sol.ventas == []
    assert reg.estado == "advertencia"


def test_campos_y_formatos_reparados(catalogo, observacion_valida):
    o = copia(observacion_valida)
    o["tienda"] = "T05"
    del o["tienda_id"]
    o["fecha"] = "17/11/2025"
    o["ventas"][6]["familia_id"] = "LÁCTEOS"
    sol, reg = limpiar_observaciones(o, catalogo)
    assert sol.tienda_id == 5
    assert reg.estado == "corregido"


@pytest.mark.parametrize("campo", ["tienda_id", "fecha", "ventas"])
def test_campo_obligatorio_ausente_se_rechaza(catalogo, observacion_valida, campo):
    o = copia(observacion_valida)
    del o[campo]
    with pytest.raises(SolicitudRechazada):
        limpiar_observaciones(o, catalogo)


def test_ventas_vacia_se_rechaza(catalogo, observacion_valida):
    o = copia(observacion_valida)
    o["ventas"] = []
    with pytest.raises(SolicitudRechazada):
        limpiar_observaciones(o, catalogo)
