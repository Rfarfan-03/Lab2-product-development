"""Pruebas del contrato de la API (Anexo).

Sin servidor de MLflow ni PostgreSQL: SQLite en memoria y un modelo falso inyectado.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool

from novamercado.api.gestor_modelo import GestorModelo, ModeloCargado
from novamercado.api.main import crear_app
from novamercado.api.servicio import Servicio
from novamercado.db import repositorio
from novamercado.db.esquema import correcciones, historico_ventas, observaciones, predicciones, solicitudes
from tests.conftest import copia


class ModeloFalso:
    """Devuelve venta_esperada = 100 + en_promocion y guarda las features recibidas."""

    def __init__(self):
        self.ultimas_features = None

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        self.ultimas_features = X.copy()
        esperada = 100.0 + X["en_promocion"].fillna(0)
        return pd.DataFrame({"venta_esperada": esperada + 0.25, "cantidad_sugerida": (esperada + 5).astype(int)})


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    repositorio.crear_tablas(eng)
    return eng


@pytest.fixture
def modelo_falso():
    return ModeloFalso()


@pytest.fixture
def gestor(modelo_falso):
    g = GestorModelo()
    g.establecer(ModeloCargado(modelo=modelo_falso, nombre="novamercado-ventas", alias="vigente", version="7"))
    return g


@pytest.fixture
def tiendas_df(catalogo):
    return pd.DataFrame(
        [
            {"tienda_id": t.tienda_id, "nombre": t.nombre, "ciudad": t.ciudad, "tipo": t.tipo,
             "fecha_apertura": pd.Timestamp(t.fecha_apertura)}
            for t in catalogo.tiendas.values()
        ]
    )


@pytest.fixture
def feriados_df():
    return pd.DataFrame({"fecha": pd.to_datetime(["2025-11-01"]), "nombre": ["x"], "tipo": ["feriado"], "ambito": ["nacional"]})


@pytest.fixture
def cliente(engine, catalogo, feriados_df, tiendas_df, gestor):
    servicio = Servicio(engine, catalogo, feriados_df, tiendas_df, gestor)
    with TestClient(crear_app(servicio)) as c:
        yield c


def contar(engine, tabla, *condiciones):
    with engine.connect() as con:
        return con.execute(select(func.count()).select_from(tabla).where(*condiciones)).scalar()


# ------------------------------------------------------------------ POST /v1/prediccion


def test_prediccion_valida_cumple_el_contrato(cliente, prediccion_valida):
    r = cliente.post("/v1/prediccion", json=prediccion_valida)
    assert r.status_code == 200
    body = r.json()
    assert body["tienda_id"] == 5
    assert body["fecha"] == "2025-11-17"
    assert body["version_modelo"] == "7"
    assert body["calidad"] == {"estado": "ok", "observaciones": []}
    assert len(body["predicciones"]) == 12
    for p in body["predicciones"]:
        assert set(p) >= {"familia_id", "venta_esperada", "cantidad_sugerida"}
        assert isinstance(p["cantidad_sugerida"], int) and p["cantidad_sugerida"] >= 0
        assert isinstance(p["venta_esperada"], float)
    bebidas = next(p for p in body["predicciones"] if p["familia_id"] == "bebidas")
    assert bebidas["venta_esperada"] == 108.25  # usó en_promocion = 8


def test_prediccion_corregida_informa_que_hizo(cliente, prediccion_valida):
    p = copia(prediccion_valida)
    p["familias"][6]["familia_id"] = "LÁCTEOS"
    body = cliente.post("/v1/prediccion", json=p).json()
    assert body["calidad"]["estado"] == "corregido"
    assert body["calidad"]["observaciones"] == [
        {"campo": "familias[6].familia_id", "accion": "reparar", "detalle": "'LÁCTEOS' se interpretó como 'lacteos'"}
    ]


def test_prediccion_con_advertencia(cliente, prediccion_valida):
    p = copia(prediccion_valida)
    p["familias"] = p["familias"][:10]
    body = cliente.post("/v1/prediccion", json=p).json()
    assert body["calidad"]["estado"] == "advertencia"
    assert len(body["predicciones"]) == 12


def test_rechazo_responde_422_con_detail(cliente, engine, prediccion_valida):
    p = copia(prediccion_valida)
    p["tienda_id"] = 99
    r = cliente.post("/v1/prediccion", json=p)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str) and "99" in r.json()["detail"]
    assert contar(engine, solicitudes, solicitudes.c.estado == "rechazada") == 1


def test_cuerpo_no_json_responde_422(cliente, engine):
    r = cliente.post("/v1/prediccion", content=b"{no es json", headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)
    assert contar(engine, solicitudes, solicitudes.c.estado == "rechazada") == 1


def test_cuerpo_vacio_responde_422(cliente):
    assert cliente.post("/v1/prediccion").status_code == 422


def test_prediccion_queda_registrada_con_su_version(cliente, engine, prediccion_valida):
    p = copia(prediccion_valida)
    p["tienda_id"] = "T05"
    cliente.post("/v1/prediccion", json=p)
    assert contar(engine, solicitudes, solicitudes.c.estado == "corregido") == 1
    assert contar(engine, predicciones, predicciones.c.version_modelo == "7") == 12
    assert contar(engine, correcciones, correcciones.c.accion == "reparar") == 1


def test_misma_fecha_puede_solicitarse_mas_de_una_vez(cliente, engine, prediccion_valida):
    assert cliente.post("/v1/prediccion", json=prediccion_valida).status_code == 200
    assert cliente.post("/v1/prediccion", json=prediccion_valida).status_code == 200
    assert contar(engine, predicciones) == 24


def test_sin_modelo_responde_503(engine, catalogo, feriados_df, tiendas_df, prediccion_valida):
    servicio = Servicio(engine, catalogo, feriados_df, tiendas_df, GestorModelo())
    with TestClient(crear_app(servicio)) as c:
        assert c.post("/v1/prediccion", json=prediccion_valida).status_code == 503
        assert c.get("/modelo").status_code == 503


# ------------------------------------------------------------------ historia usada al predecir


def test_prediccion_usa_la_observacion_del_dia_anterior(cliente, modelo_falso, observacion_valida, prediccion_valida):
    obs = copia(observacion_valida)
    obs["fecha"] = "2025-11-16"
    cliente.post("/v1/observaciones", json=obs)
    cliente.post("/v1/prediccion", json=prediccion_valida)
    X = modelo_falso.ultimas_features.set_index("familia_id")
    esperado = {v["familia_id"]: v["ventas"] for v in obs["ventas"]}
    assert X.loc["abarrotes", "lag_1"] == esperado["abarrotes"]


def test_prediccion_no_usa_observaciones_del_mismo_dia_ni_posteriores(cliente, modelo_falso, observacion_valida, prediccion_valida):
    for fecha in ["2025-11-17", "2025-11-18"]:
        obs = copia(observacion_valida)
        obs["fecha"] = fecha
        cliente.post("/v1/observaciones", json=obs)
    cliente.post("/v1/prediccion", json=prediccion_valida)
    X = modelo_falso.ultimas_features
    assert X["lag_1"].isna().all() and X["media_28"].isna().all()


def test_observacion_prevalece_sobre_el_historico(engine, cliente, modelo_falso, observacion_valida, prediccion_valida):
    with engine.begin() as con:
        con.execute(
            historico_ventas.insert(),
            [{"fecha": date(2025, 11, 16), "tienda_id": 5, "familia_id": "abarrotes", "ventas": 1, "en_promocion": 0}],
        )
    obs = copia(observacion_valida)
    obs["fecha"] = "2025-11-16"
    obs["ventas"] = [{"familia_id": "abarrotes", "ventas": 555}]
    cliente.post("/v1/observaciones", json=obs)
    cliente.post("/v1/prediccion", json=prediccion_valida)
    X = modelo_falso.ultimas_features.set_index("familia_id")
    assert X.loc["abarrotes", "lag_1"] == 555


# ------------------------------------------------------------------ POST /v1/observaciones


def test_observaciones_validas(cliente, engine, observacion_valida):
    r = cliente.post("/v1/observaciones", json=observacion_valida)
    assert r.status_code == 200
    assert r.json() == {"registros_guardados": 12, "calidad": {"estado": "ok", "observaciones": []}}
    assert contar(engine, observaciones) == 12


def test_e09_observacion_repetida_es_idempotente(cliente, engine, observacion_valida):
    cliente.post("/v1/observaciones", json=observacion_valida)
    r = cliente.post("/v1/observaciones", json=observacion_valida)
    assert r.status_code == 200
    assert r.json()["registros_guardados"] == 0
    assert contar(engine, observaciones) == 12


def test_observacion_corregida_cuenta_solo_lo_modificado(cliente, engine, observacion_valida):
    cliente.post("/v1/observaciones", json=observacion_valida)
    o = copia(observacion_valida)
    o["ventas"][0]["ventas"] += 1
    assert cliente.post("/v1/observaciones", json=o).json()["registros_guardados"] == 1
    assert contar(engine, observaciones) == 12


def test_reparacion_de_formato_no_cuenta_como_cambio(cliente, observacion_valida):
    cliente.post("/v1/observaciones", json=observacion_valida)
    o = copia(observacion_valida)
    o["ventas"][0]["ventas"] = str(o["ventas"][0]["ventas"])
    body = cliente.post("/v1/observaciones", json=o).json()
    assert body["registros_guardados"] == 0
    assert body["calidad"]["estado"] == "corregido"


def test_e08_observacion_negativa_no_se_guarda(cliente, engine, observacion_valida):
    o = copia(observacion_valida)
    o["ventas"][5]["ventas"] = -4
    body = cliente.post("/v1/observaciones", json=o).json()
    assert body["registros_guardados"] == 11
    assert body["calidad"]["estado"] == "advertencia"
    assert contar(engine, observaciones) == 11


def test_observacion_rechazada(cliente, observacion_valida):
    o = copia(observacion_valida)
    del o["fecha"]
    r = cliente.post("/v1/observaciones", json=o)
    assert r.status_code == 422 and isinstance(r.json()["detail"], str)


# ------------------------------------------------------------------ GET /modelo


def test_modelo_vigente(cliente):
    r = cliente.get("/modelo")
    assert r.status_code == 200
    assert r.json() == {"nombre": "novamercado-ventas", "alias": "vigente", "version": "7"}


# ------------------------------------------------------------------ datos para reentrenar


def test_ventas_para_entrenar_adjunta_la_promocion_solicitada(cliente, engine, prediccion_valida, observacion_valida):
    cliente.post("/v1/prediccion", json=prediccion_valida)
    cliente.post("/v1/observaciones", json=observacion_valida)
    with engine.connect() as con:
        df = repositorio.ventas_para_entrenar(con)
    fila = df[(df.familia_id == "bebidas") & (df.fecha == "2025-11-17")].iloc[0]
    assert fila["en_promocion"] == 8
    assert len(df) == 12
