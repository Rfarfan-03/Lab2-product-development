"""Pruebas de /admin/reentrenar y de la recarga del modelo sin reinicio (sin Airflow ni MLflow)."""

from __future__ import annotations

from novamercado.api.gestor_modelo import GestorModelo, ModeloCargado
from novamercado.api.monitor import MonitorModelo
from novamercado.db import repositorio
from tests.test_api import (  # noqa: F401  (fixtures)
    airflow,
    cliente,
    engine,
    feriados_df,
    gestor,
    modelo_falso,
    tiendas_df,
)


def finalizar(engine, id_ejecucion, **kw):
    with engine.begin() as con:
        repositorio.finalizar_reentrenamiento(con, id_ejecucion, **kw)


# ------------------------------------------------------------------ POST /admin/reentrenar


def test_reentrenar_responde_202_con_id_texto(cliente, airflow):
    r = cliente.post("/admin/reentrenar")
    assert r.status_code == 202
    assert isinstance(r.json()["id"], str)
    assert airflow.disparos == [r.json()["id"]]


def test_reentrenar_sin_airflow_responde_503(cliente, airflow):
    airflow.disponible_ = False
    r = cliente.post("/admin/reentrenar")
    assert r.status_code == 503 and "detail" in r.json()


# ------------------------------------------------------------------ GET /admin/reentrenar/{id}


def test_estado_en_curso_no_incluye_campos_finales(cliente, airflow):
    id_ = cliente.post("/admin/reentrenar").json()["id"]
    airflow.estados[id_] = "running"
    assert cliente.get(f"/admin/reentrenar/{id_}").json() == {"estado": "en_curso"}


def test_estado_exitoso_con_promocion(cliente, engine):
    id_ = cliente.post("/admin/reentrenar").json()["id"]
    finalizar(engine, id_, estado="exitoso", promovido=True, version="8",
              motivo="Costo en validación 18 210 vs 19 940 del vigente")
    assert cliente.get(f"/admin/reentrenar/{id_}").json() == {
        "estado": "exitoso",
        "promovido": True,
        "version": "8",
        "motivo": "Costo en validación 18 210 vs 19 940 del vigente",
    }


def test_estado_exitoso_sin_promocion_conserva_version_vigente(cliente, engine):
    id_ = cliente.post("/admin/reentrenar").json()["id"]
    finalizar(engine, id_, estado="exitoso", promovido=False, version="7",
              motivo="Costo en validación 20 000 no mejora 19 940 del vigente")
    body = cliente.get(f"/admin/reentrenar/{id_}").json()
    assert body["promovido"] is False and body["version"] == "7"


def test_fallo_registrado_por_el_dag(cliente, engine):
    id_ = cliente.post("/admin/reentrenar").json()["id"]
    finalizar(engine, id_, estado="fallido", promovido=False, version=None, motivo="El reentrenamiento falló")
    body = cliente.get(f"/admin/reentrenar/{id_}").json()
    assert body == {"estado": "fallido", "promovido": False, "version": "7", "motivo": "El reentrenamiento falló"}


def test_fallo_detectado_en_airflow(cliente, airflow):
    id_ = cliente.post("/admin/reentrenar").json()["id"]
    airflow.estados[id_] = "failed"
    body = cliente.get(f"/admin/reentrenar/{id_}").json()
    assert body["estado"] == "fallido" and body["promovido"] is False and body["version"] == "7"


def test_airflow_caido_mantiene_en_curso(cliente, airflow):
    id_ = cliente.post("/admin/reentrenar").json()["id"]
    airflow.disponible_ = False
    assert cliente.get(f"/admin/reentrenar/{id_}").json() == {"estado": "en_curso"}


def test_id_desconocido_responde_404(cliente):
    assert cliente.get("/admin/reentrenar/no-existe").status_code == 404


# ------------------------------------------------------------------ recarga del modelo


def cargado(version):
    return ModeloCargado(modelo=object(), nombre="novamercado-ventas", alias="vigente", version=version)


def test_gestor_carga_la_nueva_version_vigente():
    vigente = {"v": "1"}
    g = GestorModelo(lambda: vigente["v"], cargado)
    assert g.actualizar() and g.actual.version == "1"
    assert not g.actualizar()  # misma versión: no recarga
    vigente["v"] = "2"
    assert g.actualizar() and g.actual.version == "2"


def test_monitor_conserva_el_modelo_si_mlflow_no_responde():
    estado = {"caido": False}

    def consultar():
        if estado["caido"]:
            raise ConnectionError("MLflow no responde")
        return "3"

    g = GestorModelo(consultar, cargado)
    monitor = MonitorModelo(g, intervalo=0.01)
    monitor.revisar()
    estado["caido"] = True
    monitor.revisar()  # no lanza
    assert g.actual.version == "3"


def test_monitor_recarga_sin_reiniciar(cliente):
    import time

    vigente = {"v": "1"}
    g = GestorModelo(lambda: vigente["v"], cargado)
    monitor = MonitorModelo(g, intervalo=0.02)
    monitor.iniciar()
    try:
        vigente["v"] = "5"
        limite = time.time() + 2
        while (g.actual is None or g.actual.version != "5") and time.time() < limite:
            time.sleep(0.01)
        assert g.actual.version == "5"
    finally:
        monitor.detener()
