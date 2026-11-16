from datetime import date

import pytest

from novamercado.limpieza import SolicitudRechazada, limpiar_prediccion
from tests.conftest import copia


def promos(solicitud):
    return {f.familia_id: f.en_promocion for f in solicitud.familias}


def acciones(registro):
    return [(o.campo, o.accion) for o in registro.observaciones]


def test_solicitud_valida_queda_ok(catalogo, prediccion_valida):
    sol, reg = limpiar_prediccion(prediccion_valida, catalogo)
    assert reg.estado == "ok"
    assert reg.observaciones == []
    assert sol.tienda_id == 5
    assert sol.fecha == date(2025, 11, 17)
    assert promos(sol)["bebidas"] == 8
    assert len(sol.familias) == 12


# ---------------------------------------------------------------- E01 tienda


@pytest.mark.parametrize("valor", ["T05", "5", 5.0, "Tienda 5", "t-05", "NovaMercado Quetzaltenango"])
def test_e01_tienda_se_repara(catalogo, prediccion_valida, valor):
    p = copia(prediccion_valida)
    p["tienda_id"] = valor
    sol, reg = limpiar_prediccion(p, catalogo)
    assert sol.tienda_id == 5
    assert reg.estado == "corregido"
    assert acciones(reg) == [("tienda_id", "reparar")]


@pytest.mark.parametrize("valor", [99, "T99", "abc", None, True, 5.5, [5]])
def test_tienda_invalida_o_inexistente_se_rechaza(catalogo, prediccion_valida, valor):
    p = copia(prediccion_valida)
    p["tienda_id"] = valor
    with pytest.raises(SolicitudRechazada):
        limpiar_prediccion(p, catalogo)


# ---------------------------------------------------------------- E02 familia


def test_e02_familia_escrita_de_otra_forma(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["familias"][5]["familia_id"] = "Frutas y Verduras"
    p["familias"][6]["familia_id"] = "LÁCTEOS"
    p["familias"][0]["familia_id"] = "abarrotes "
    sol, reg = limpiar_prediccion(p, catalogo)
    assert reg.estado == "corregido"
    assert set(promos(sol)) >= {"frutas_verduras", "lacteos", "abarrotes"}
    assert ("familias[6].familia_id", "reparar") in acciones(reg)
    assert len(sol.familias) == 12


def test_familia_con_error_de_escritura_se_advierte(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["familias"][0]["familia_id"] = "abarotes"
    sol, reg = limpiar_prediccion(p, catalogo)
    assert "abarrotes" in promos(sol)
    assert ("familias[0].familia_id", "advertir") in acciones(reg)
    assert reg.estado == "advertencia"


def test_familia_desconocida_se_descarta_y_se_completa(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["familias"].append({"familia_id": "juguetes", "en_promocion": 2})
    sol, reg = limpiar_prediccion(p, catalogo)
    assert "juguetes" not in promos(sol)
    assert reg.estado == "advertencia"


# ---------------------------------------------------------------- E03 promoción


def test_e03_promocion_como_texto_o_decimal(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["familias"][2]["en_promocion"] = 8.0
    p["familias"][11]["en_promocion"] = "9"
    sol, reg = limpiar_prediccion(p, catalogo)
    assert reg.estado == "corregido"
    assert promos(sol)["bebidas"] == 8
    assert promos(sol)["snacks"] == 9


@pytest.mark.parametrize("valor", [None, "muchas", -3, True])
def test_promocion_no_interpretable_supone_cero(catalogo, prediccion_valida, valor):
    p = copia(prediccion_valida)
    p["familias"][2]["en_promocion"] = valor
    sol, reg = limpiar_prediccion(p, catalogo)
    assert promos(sol)["bebidas"] == 0
    assert ("familias[2].en_promocion", "advertir") in acciones(reg)


def test_promocion_ausente_supone_cero(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    del p["familias"][2]["en_promocion"]
    sol, reg = limpiar_prediccion(p, catalogo)
    assert promos(sol)["bebidas"] == 0
    assert reg.estado == "advertencia"


def test_promocion_fuera_de_rango_historico_se_advierte(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["familias"][2]["en_promocion"] = 500
    sol, reg = limpiar_prediccion(p, catalogo)
    assert promos(sol)["bebidas"] == 500
    assert reg.estado == "advertencia"


# ---------------------------------------------------------------- E04 fecha


@pytest.mark.parametrize("valor", ["2025-11-17T00:00:00", "17/11/2025", "2025/11/17"])
def test_e04_fecha_en_otro_formato(catalogo, prediccion_valida, valor):
    p = copia(prediccion_valida)
    p["fecha"] = valor
    sol, reg = limpiar_prediccion(p, catalogo)
    assert sol.fecha == date(2025, 11, 17)
    assert acciones(reg) == [("fecha", "reparar")]


@pytest.mark.parametrize("valor", ["2025-13-01", "ayer", None, ""])
def test_fecha_invalida_se_rechaza(catalogo, prediccion_valida, valor):
    p = copia(prediccion_valida)
    p["fecha"] = valor
    with pytest.raises(SolicitudRechazada):
        limpiar_prediccion(p, catalogo)


def test_fecha_anterior_a_apertura_se_rechaza(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["tienda_id"] = 10
    p["fecha"] = "2025-01-01"
    with pytest.raises(SolicitudRechazada):
        limpiar_prediccion(p, catalogo)


def test_fecha_fuera_de_cobertura_de_feriados_se_advierte(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["fecha"] = "2027-03-01"
    _, reg = limpiar_prediccion(p, catalogo)
    assert ("fecha", "advertir") in acciones(reg)


def test_no_se_usa_el_reloj_del_sistema(catalogo, prediccion_valida):
    # una fecha "pasada" respecto al reloj real sigue siendo válida
    p = copia(prediccion_valida)
    p["fecha"] = "2024-06-01"
    sol, reg = limpiar_prediccion(p, catalogo)
    assert reg.estado == "ok"


# ---------------------------------------------------------------- E05 faltantes


def test_e05_faltan_familias_se_completan_con_advertencia(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["familias"] = [f for f in p["familias"] if f["familia_id"] not in {"bebe", "mascotas"}]
    sol, reg = limpiar_prediccion(p, catalogo)
    assert len(sol.familias) == 12
    assert promos(sol)["bebe"] == 0 and promos(sol)["mascotas"] == 0
    assert acciones(reg) == [("familias", "advertir")]


def test_solo_se_completan_familias_que_la_tienda_vende(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["tienda_id"] = 10
    p["familias"] = [f for f in p["familias"] if f["familia_id"] != "licores"]
    sol, reg = limpiar_prediccion(p, catalogo)
    assert "licores" not in promos(sol)
    assert reg.estado == "ok"


# ---------------------------------------------------------------- E06 repetidas


def test_e06_familia_repetida_con_valores_distintos(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["familias"].append({"familia_id": "abarrotes", "en_promocion": 3})
    sol, reg = limpiar_prediccion(p, catalogo)
    assert promos(sol)["abarrotes"] == 3
    assert ("familias[12]", "advertir") in acciones(reg)
    assert len(sol.familias) == 12


def test_familia_repetida_identica_se_repara(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["familias"].append({"familia_id": "abarrotes", "en_promocion": 0})
    _, reg = limpiar_prediccion(p, catalogo)
    assert acciones(reg) == [("familias[12]", "reparar")]


# ---------------------------------------------------------------- E07 campos


def test_e07_campo_renombrado(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["tienda"] = p.pop("tienda_id")
    sol, reg = limpiar_prediccion(p, catalogo)
    assert sol.tienda_id == 5
    assert acciones(reg) == [("tienda_id", "reparar")]


def test_campo_renombrado_en_elemento(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["familias"][2] = {"familia": "bebidas", "promocion": 8}
    sol, reg = limpiar_prediccion(p, catalogo)
    assert promos(sol)["bebidas"] == 8
    assert reg.estado == "corregido"


def test_campo_desconocido_se_ignora_con_advertencia(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["comentario"] = "urgente"
    _, reg = limpiar_prediccion(p, catalogo)
    assert acciones(reg) == [("comentario", "advertir")]


def test_campos_en_conflicto_se_rechazan(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["tienda"] = 6
    with pytest.raises(SolicitudRechazada):
        limpiar_prediccion(p, catalogo)


# ---------------------------------------------------------------- estructura


@pytest.mark.parametrize("payload", [None, [], "texto", 5])
def test_cuerpo_que_no_es_objeto_se_rechaza(catalogo, payload):
    with pytest.raises(SolicitudRechazada):
        limpiar_prediccion(payload, catalogo)


@pytest.mark.parametrize("campo", ["tienda_id", "fecha", "familias"])
def test_campo_obligatorio_ausente_se_rechaza(catalogo, prediccion_valida, campo):
    p = copia(prediccion_valida)
    del p[campo]
    with pytest.raises(SolicitudRechazada):
        limpiar_prediccion(p, catalogo)


@pytest.mark.parametrize("familias", [[], {}, "abarrotes"])
def test_familias_vacia_o_no_lista_se_rechaza(catalogo, prediccion_valida, familias):
    p = copia(prediccion_valida)
    p["familias"] = familias
    with pytest.raises(SolicitudRechazada):
        limpiar_prediccion(p, catalogo)


def test_elemento_que_no_es_objeto_se_ignora(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["familias"].append("abarrotes")
    _, reg = limpiar_prediccion(p, catalogo)
    assert ("familias[12]", "advertir") in acciones(reg)


def test_mensaje_de_rechazo_explica_el_motivo(catalogo, prediccion_valida):
    p = copia(prediccion_valida)
    p["tienda_id"] = 99
    with pytest.raises(SolicitudRechazada, match="99"):
        limpiar_prediccion(p, catalogo)
