"""Pruebas del modelado. Usan datos sintéticos y MLflow local en archivos (sin servidor)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from novamercado.modelo import metricas
from novamercado.modelo.criterio import decidir_reemplazo
from novamercado.modelo.features import FEATURES, construir_features
from novamercado.modelo.modelos import ModeloBaseline, ModeloLightGBM, a_cantidad

FAMILIAS = ["abarrotes", "panaderia", "licores"]


@pytest.fixture
def costos():
    return pd.DataFrame(
        {
            "familia_id": FAMILIAS,
            "costo_faltante": [1.0, 1.0, 2.0],
            "costo_sobrante": [0.2, 2.5, 0.1],
        }
    )


@pytest.fixture
def tiendas():
    return pd.DataFrame(
        {
            "tienda_id": [1, 2],
            "nombre": ["A", "B"],
            "ciudad": ["Guatemala", "Cobán"],
            "departamento": ["Guatemala", "Alta Verapaz"],
            "tipo": ["hipermercado", "express"],
            "fecha_apertura": pd.to_datetime(["2019-01-01", "2019-01-01"]),
        }
    )


@pytest.fixture
def feriados():
    return pd.DataFrame(
        {
            "fecha": pd.to_datetime(["2024-03-10", "2024-03-20"]),
            "nombre": ["Nacional", "Local Cobán"],
            "tipo": ["feriado", "feriado"],
            "ambito": ["nacional", "Cobán"],
        }
    )


@pytest.fixture
def ventas():
    rng = np.random.default_rng(0)
    filas = []
    for fecha in pd.date_range("2024-01-01", periods=150, freq="D"):
        for tienda, escala in [(1, 100), (2, 20)]:
            for i, familia in enumerate(FAMILIAS):
                media = escala * (1 + i) * (1.3 if fecha.dayofweek >= 5 else 1.0)
                filas.append(
                    {
                        "fecha": fecha,
                        "tienda_id": tienda,
                        "familia_id": familia,
                        "ventas": int(rng.poisson(media)),
                        "en_promocion": int(rng.integers(0, 3)),
                    }
                )
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ métricas y criterio


def test_cuantil_newsvendor(costos):
    q = metricas.cuantil_por_familia(costos)
    assert q["abarrotes"] == pytest.approx(1 / 1.2)
    assert q["panaderia"] == pytest.approx(1 / 3.5)
    assert q["licores"] == pytest.approx(2 / 2.1)


def test_costo_segun_costos_csv(costos):
    c = metricas.costo([10, 10], [7, 14], ["licores", "panaderia"], costos)
    # licores: faltan 3 × 2.0 ; panadería: sobran 4 × 2.5
    assert c.tolist() == [6.0, 10.0]


def test_cantidad_sugerida_entera_no_negativa():
    assert a_cantidad([-3.2, 2.5, np.nan, 7.6]).tolist() == [0, 2, 0, 8]


def test_criterio_sin_vigente_promueve():
    promovido, motivo = decidir_reemplazo(100.0, None)
    assert promovido and "No hay modelo vigente" in motivo


def test_criterio_promueve_solo_si_mejora():
    assert decidir_reemplazo(18210, 19940) == (True, "Costo en validación 18 210 vs 19 940 del vigente")
    assert decidir_reemplazo(19940, 19940)[0] is False
    assert decidir_reemplazo(20000, 19940)[0] is False


# ------------------------------------------------------------------ features


def test_features_solo_usan_dias_anteriores(ventas, feriados, tiendas):
    objetivo = pd.DataFrame(
        [{"fecha": pd.Timestamp("2024-02-15"), "tienda_id": 1, "familia_id": "abarrotes", "en_promocion": 0}]
    )
    # una venta enorme el mismo día no debe influir en sus propias features
    historia = ventas.copy()
    historia.loc[
        (historia.fecha == "2024-02-15") & (historia.tienda_id == 1) & (historia.familia_id == "abarrotes"), "ventas"
    ] = 10**6
    f = construir_features(historia, objetivo, feriados, tiendas).iloc[0]
    anterior = ventas[
        (ventas.fecha == "2024-02-14") & (ventas.tienda_id == 1) & (ventas.familia_id == "abarrotes")
    ].ventas.iloc[0]
    assert f["lag_1"] == anterior
    assert f[[c for c in FEATURES if c.startswith(("lag_", "media_"))]].max() < 10**6


def test_features_sin_historia_quedan_nulas(feriados, tiendas):
    objetivo = pd.DataFrame([{"fecha": "2024-05-01", "tienda_id": 1, "familia_id": "abarrotes", "en_promocion": 2}])
    f = construir_features(objetivo.assign(ventas=np.nan).iloc[0:0], objetivo, feriados, tiendas).iloc[0]
    assert np.isnan(f["lag_1"]) and np.isnan(f["media_7"])


def test_feriado_local_solo_aplica_a_su_ciudad(ventas, feriados, tiendas):
    obj = pd.DataFrame(
        [
            {"fecha": "2024-03-20", "tienda_id": 1, "familia_id": "abarrotes", "en_promocion": 0},
            {"fecha": "2024-03-20", "tienda_id": 2, "familia_id": "abarrotes", "en_promocion": 0},
            {"fecha": "2024-03-10", "tienda_id": 1, "familia_id": "abarrotes", "en_promocion": 0},
        ]
    )
    f = construir_features(ventas, obj, feriados, tiendas)
    assert f["es_feriado"].tolist() == [0, 1, 1]
    assert construir_features(
        ventas, obj.assign(fecha="2024-03-19"), feriados, tiendas
    )["manana_feriado"].tolist() == [0, 1, 0]


# ------------------------------------------------------------------ modelos


def test_modelos_producen_predicciones_validas(ventas, feriados, tiendas, costos):
    df = construir_features(ventas, ventas, feriados, tiendas)
    tr, va = df[df.fecha < "2024-05-01"], df[df.fecha >= "2024-05-01"]
    q = metricas.cuantil_por_familia(costos)
    for modelo in [ModeloBaseline(q).ajustar(tr), ModeloLightGBM(q, {"min_data_in_leaf": 5}, 30).ajustar(tr)]:
        pred = modelo.predict(None, va)
        assert list(pred.columns) == ["venta_esperada", "cantidad_sugerida"]
        assert (pred["cantidad_sugerida"] >= 0).all()
        assert pred["cantidad_sugerida"].dtype.kind == "i"


def test_cantidad_sugerida_sigue_los_costos(ventas, feriados, tiendas, costos):
    """Licores (faltar cuesta mucho) sugiere sobre lo esperado; panadería, por debajo."""
    df = construir_features(ventas, ventas, feriados, tiendas)
    tr, va = df[df.fecha < "2024-05-01"], df[df.fecha >= "2024-05-01"]
    modelo = ModeloLightGBM(metricas.cuantil_por_familia(costos), {"min_data_in_leaf": 5}, 60).ajustar(tr)
    pred = modelo.predict(None, va).assign(familia_id=va["familia_id"].to_numpy())
    margen = (pred["cantidad_sugerida"] - pred["venta_esperada"]).groupby(pred["familia_id"]).mean()
    assert margen["licores"] > 0 > margen["panaderia"]


# ------------------------------------------------------------------ entrenamiento + MLflow local


def test_entrenamiento_registra_y_aplica_criterio(tmp_path, monkeypatch, ventas, feriados, tiendas, costos):
    import mlflow

    from novamercado.modelo import entrenamiento
    from novamercado.modelo.registro import version_vigente

    uri = (tmp_path / "mlruns").as_uri()
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    args = dict(params_lightgbm={"min_data_in_leaf": 5}, rondas_lightgbm=20, dias_validacion=14)

    primero = entrenamiento.entrenar_y_registrar(ventas, feriados, tiendas, costos, origen="prueba", **args)
    assert primero.promovido and primero.version == "1"
    assert str(version_vigente().version) == "1"

    # mismo dato y mismo modelo: no mejora estrictamente ⇒ no se promueve y el alias no cambia
    segundo = entrenamiento.entrenar_y_registrar(ventas, feriados, tiendas, costos, origen="prueba", **args)
    assert not segundo.promovido
    assert segundo.version == "1" and segundo.version_candidata == "2"
    assert str(version_vigente().version) == "1"

    # un fallo durante el entrenamiento no toca el alias
    monkeypatch.setattr(entrenamiento, "dividir", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("falla")))
    with pytest.raises(RuntimeError):
        entrenamiento.entrenar_y_registrar(ventas, feriados, tiendas, costos, origen="prueba", **args)
    assert str(version_vigente().version) == "1"
