"""Modelos de pronóstico empaquetados como pyfunc de MLflow.

Ambos reciben el DataFrame de ``features.construir_features`` y devuelven
``venta_esperada`` (pronóstico puntual) y ``cantidad_sugerida`` (cuantil de costo mínimo
de cada familia, ver ``metricas.cuantil_por_familia``).
"""

from __future__ import annotations

import lightgbm as lgb
import mlflow.pyfunc
import numpy as np
import pandas as pd

from novamercado.modelo.features import CATEGORICAS, FEATURES


def a_cantidad(valores) -> np.ndarray:
    """Cantidad sugerida: entero no negativo."""
    return np.maximum(np.rint(np.nan_to_num(np.asarray(valores, dtype=float))), 0).astype(int)


class ModeloVentas(mlflow.pyfunc.PythonModel):
    tipo = "base"

    def __init__(self, cuantiles: dict[str, float]):
        self.cuantiles = dict(cuantiles)

    def predecir(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError

    def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
        esperada, sugerida = self.predecir(model_input)
        return pd.DataFrame(
            {"venta_esperada": np.round(esperada, 2), "cantidad_sugerida": a_cantidad(sugerida)},
            index=model_input.index,
        )


class ModeloBaseline(ModeloVentas):
    """Referencia simple.

    venta_esperada: media del mismo día de la semana en las 4 semanas previas
    (si falta, media de los últimos 7 días; si falta, el último dato).
    cantidad_sugerida: venta_esperada por un factor por familia, igual al cuantil de costo
    mínimo del cociente real/esperada observado en entrenamiento.
    """

    tipo = "baseline"

    def __init__(self, cuantiles: dict[str, float]):
        super().__init__(cuantiles)
        self.factores: dict[str, float] = {}

    @staticmethod
    def _base(X: pd.DataFrame) -> np.ndarray:
        base = X["media_mismo_dia_4"].fillna(X["media_7"]).fillna(X["lag_1"]).fillna(0)
        return base.to_numpy(dtype=float)

    def ajustar(self, train: pd.DataFrame) -> "ModeloBaseline":
        base = self._base(train)
        valido = base > 0
        cociente = pd.Series(train["ventas"].to_numpy(dtype=float)[valido] / base[valido])
        familias = train["familia_id"].to_numpy()[valido]
        for familia, tau in self.cuantiles.items():
            valores = cociente[familias == familia]
            self.factores[familia] = float(valores.quantile(tau)) if len(valores) else 1.0
        return self

    def predecir(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        base = self._base(X)
        factor = X["familia_id"].map(self.factores).fillna(1.0).to_numpy(dtype=float)
        return base, base * factor


class ModeloLightGBM(ModeloVentas):
    """Gradient boosting (LightGBM).

    - Un modelo de la media para ``venta_esperada``.
    - Un modelo de regresión cuantílica por cada cuantil de costo mínimo distinto, para
      ``cantidad_sugerida``: minimiza la pérdida pinball, que es proporcional al costo
      de costos.csv para ese cuantil.
    """

    tipo = "lightgbm"

    def __init__(self, cuantiles: dict[str, float], params: dict, rondas: int):
        super().__init__(cuantiles)
        self.params = dict(params)
        self.rondas = rondas
        self.categorias: dict[str, list] = {}
        self.modelo_media: lgb.Booster | None = None
        self.modelos_cuantil: dict[float, lgb.Booster] = {}

    def _matriz(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df[FEATURES].copy()
        for c in CATEGORICAS:
            X[c] = pd.Categorical(X[c], categories=self.categorias[c])
        return X.astype({c: float for c in FEATURES if c not in CATEGORICAS})

    def ajustar(self, train: pd.DataFrame) -> "ModeloLightGBM":
        self.categorias = {c: sorted(train[c].dropna().unique().tolist()) for c in CATEGORICAS}
        X = self._matriz(train)
        y = train["ventas"].to_numpy(dtype=float)
        base = {"verbosity": -1, "seed": 42, "deterministic": True, "num_threads": 0, **self.params}

        datos = lgb.Dataset(X, y, categorical_feature=CATEGORICAS, free_raw_data=False)
        self.modelo_media = lgb.train({**base, "objective": "regression"}, datos, self.rondas)
        for tau in sorted(set(self.cuantiles.values())):
            self.modelos_cuantil[tau] = lgb.train(
                {**base, "objective": "quantile", "alpha": tau}, datos, self.rondas
            )
        return self

    def predecir(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        M = self._matriz(X)
        esperada = np.maximum(self.modelo_media.predict(M), 0)
        sugerida = esperada.copy()
        taus = X["familia_id"].map(self.cuantiles).to_numpy()
        for tau, modelo in self.modelos_cuantil.items():
            filas = taus == tau
            if filas.any():
                sugerida[filas] = modelo.predict(M[filas])
        return esperada, sugerida
