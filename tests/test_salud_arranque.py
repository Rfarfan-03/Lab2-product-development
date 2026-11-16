"""Pruebas de GET /health y del arranque desde cero (sin servidores externos)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from novamercado.api.admin import AdminReentrenamiento
from novamercado.api.gestor_modelo import GestorModelo
from novamercado.api.main import Componentes, crear_app
from novamercado.api.salud import VerificadorSalud
from novamercado.api.servicio import Servicio
from tests.test_api import AirflowFalso, engine, feriados_df, gestor, modelo_falso, tiendas_df  # noqa: F401

# ------------------------------------------------------------------ GET /health


@pytest.fixture
def dependencias():
    return {"base de datos": True, "MLflow": True, "Airflow": True}


def cliente_salud(engine, catalogo, feriados_df, tiendas_df, gestor, dependencias):
    verificadores = {nombre: (lambda n=nombre: dependencias[n]) for nombre in dependencias}
    servicio = Servicio(engine, catalogo, feriados_df, tiendas_df, gestor)
    componentes = Componentes(
        servicio, AdminReentrenamiento(engine, AirflowFalso(), gestor), VerificadorSalud(gestor, verificadores)
    )
    return TestClient(crear_app(componentes))


def test_health_ok(engine, catalogo, feriados_df, tiendas_df, gestor, dependencias):
    with cliente_salud(engine, catalogo, feriados_df, tiendas_df, gestor, dependencias) as c:
        r = c.get("/health")
    assert r.status_code == 200 and r.json() == {"estado": "ok"}


def test_health_degradado_si_mlflow_no_responde(engine, catalogo, feriados_df, tiendas_df, gestor, dependencias, prediccion_valida):
    with cliente_salud(engine, catalogo, feriados_df, tiendas_df, gestor, dependencias) as c:
        dependencias["MLflow"] = False
        r = c.get("/health")
        assert r.status_code == 200
        assert r.json()["estado"] == "degradado" and "MLflow" in r.json()["motivo"]
        # la API sigue respondiendo con el modelo cargado
        assert c.post("/v1/prediccion", json=prediccion_valida).status_code == 200
        dependencias["MLflow"] = True
        assert c.get("/health").json() == {"estado": "ok"}


def test_health_503_sin_modelo(engine, catalogo, feriados_df, tiendas_df, dependencias):
    with cliente_salud(engine, catalogo, feriados_df, tiendas_df, GestorModelo(), dependencias) as c:
        r = c.get("/health")
    assert r.status_code == 503 and r.json()["estado"] == "degradado"


@pytest.mark.parametrize("caida", ["base de datos", "Airflow"])
def test_health_degradado_por_otras_dependencias(engine, catalogo, feriados_df, tiendas_df, gestor, dependencias, caida):
    dependencias[caida] = False
    with cliente_salud(engine, catalogo, feriados_df, tiendas_df, gestor, dependencias) as c:
        body = c.get("/health").json()
    assert body["estado"] == "degradado" and caida in body["motivo"]


def test_verificadores_reales_detectan_servicio_inexistente():
    from novamercado.api.salud import verificar_airflow, verificar_mlflow

    assert verificar_mlflow("http://127.0.0.1:9")() is False
    assert verificar_airflow("http://127.0.0.1:9")() is False


# ------------------------------------------------------------------ arranque desde cero


def test_arranque_entrena_solo_si_no_hay_vigente(tmp_path, monkeypatch):
    import mlflow
    from sqlalchemy import create_engine, func, select

    from novamercado import arranque
    from novamercado.db.esquema import historico_ventas
    from tests.test_modelado import FAMILIAS

    # datos publicados mínimos en un directorio temporal
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(1)
    filas = [
        {"fecha": f.date().isoformat(), "tienda_id": 1, "familia_id": fam, "ventas": int(rng.poisson(50)), "en_promocion": 0}
        for f in pd.date_range("2024-01-01", periods=90) for fam in FAMILIAS
    ]
    pd.DataFrame(filas).to_csv(tmp_path / "historico_ventas.csv", index=False)
    pd.DataFrame({"fecha": ["2024-02-01"], "nombre": ["x"], "tipo": ["feriado"], "ambito": ["nacional"]}).to_csv(
        tmp_path / "feriados.csv", index=False
    )
    pd.DataFrame(
        {"tienda_id": [1], "nombre": ["A"], "ciudad": ["Guatemala"], "departamento": ["Guatemala"],
         "tipo": ["express"], "fecha_apertura": ["2019-01-01"]}
    ).to_csv(tmp_path / "tiendas.csv", index=False)
    pd.DataFrame(
        {"familia_id": FAMILIAS, "costo_faltante": [1.0, 1.0, 2.0], "costo_sobrante": [0.2, 2.5, 0.1]}
    ).to_csv(tmp_path / "costos.csv", index=False)

    uri = (tmp_path / "mlruns").as_uri()
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    eng = create_engine(f"sqlite:///{tmp_path / 'nova.db'}")
    args = dict(params_lightgbm={"min_data_in_leaf": 5}, rondas_lightgbm=10, dias_validacion=14)

    primero = arranque.asegurar_modelo_inicial(eng, tmp_path, **args)
    assert primero is not None and primero.promovido and primero.version == "1"
    with eng.connect() as con:
        assert con.execute(select(func.count()).select_from(historico_ventas)).scalar() == len(filas)

    # segundo arranque: conserva lo que hay, no entrena ni recarga el histórico
    assert arranque.asegurar_modelo_inicial(eng, tmp_path, **args) is None
    with eng.connect() as con:
        assert con.execute(select(func.count()).select_from(historico_ventas)).scalar() == len(filas)
