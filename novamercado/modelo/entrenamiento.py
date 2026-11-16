"""Entrenamiento, evaluación, registro en MLflow y decisión de reemplazo.

Flujo de cada ejecución:
1. Features sobre todas las ventas disponibles (histórico + observaciones registradas).
2. Ventana de validación = últimos ``VENTANA_VALIDACION_DIAS`` días; se entrena con lo anterior.
3. Se entrenan el baseline y LightGBM; cada uno queda como run anidado en MLflow con sus
   métricas técnicas y la métrica de negocio (costo).
4. El candidato de menor costo se registra como nueva versión del modelo.
5. El vigente se evalúa en la misma ventana y ``criterio.decidir_reemplazo`` decide; solo
   si se promueve se mueve el alias. Si algo falla antes, el alias no cambia.

Los modelos no se reentrenan con la ventana de validación: así, en la siguiente ejecución
la nueva ventana (posterior) tampoco fue vista por el vigente y la comparación es justa.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import mlflow
import mlflow.pyfunc
import pandas as pd
from mlflow.tracking import MlflowClient

from novamercado.modelo import datos as datos_mod
from novamercado.modelo import metricas
from novamercado.modelo.criterio import decidir_reemplazo
from novamercado.modelo.features import construir_features
from novamercado.modelo.modelos import ModeloBaseline, ModeloLightGBM, ModeloVentas, a_cantidad
from novamercado.modelo.registro import (
    ALIAS_VIGENTE,
    EXPERIMENTO,
    NOMBRE_MODELO,
    uri_version,
    version_vigente,
)

log = logging.getLogger(__name__)

VENTANA_VALIDACION_DIAS = 28
PARAMS_LIGHTGBM = {
    "learning_rate": 0.03,
    "num_leaves": 31,
    "min_data_in_leaf": 100,
    "feature_fraction": 0.8,
}
RONDAS_LIGHTGBM = 800

REQUISITOS_PIP = ["pandas==2.1.4", "numpy==1.26.4", "lightgbm==4.5.0", "mlflow-skinny==2.16.2"]


@dataclass
class ResultadoEntrenamiento:
    promovido: bool
    version: str | None  # versión vigente al terminar
    version_candidata: str
    motivo: str
    costo_candidato: float
    costo_vigente: float | None


def preparar(ventas: pd.DataFrame, feriados: pd.DataFrame, tiendas: pd.DataFrame) -> pd.DataFrame:
    ventas = ventas.dropna(subset=["ventas"])
    df = construir_features(ventas, ventas, feriados, tiendas)
    return df.sort_values(["fecha", "tienda_id", "familia_id"]).reset_index(drop=True)


def dividir(df: pd.DataFrame, dias: int = VENTANA_VALIDACION_DIAS):
    inicio_validacion = df["fecha"].max() - pd.Timedelta(days=dias - 1)
    return df[df["fecha"] < inicio_validacion], df[df["fecha"] >= inicio_validacion], inicio_validacion


def evaluar_modelo(modelo, valid: pd.DataFrame, costos: pd.DataFrame) -> dict[str, float]:
    if isinstance(modelo, ModeloVentas):
        esperada, sugerida = modelo.predecir(valid)
        sugerida = a_cantidad(sugerida)
    else:  # pyfunc cargado desde MLflow
        pred = modelo.predict(valid)
        esperada, sugerida = pred["venta_esperada"], pred["cantidad_sugerida"]
    return metricas.evaluar(valid["ventas"], esperada, sugerida, valid["familia_id"], costos)


def entrenar_y_registrar(
    ventas: pd.DataFrame,
    feriados: pd.DataFrame,
    tiendas: pd.DataFrame,
    costos: pd.DataFrame,
    origen: str,
    params_lightgbm: dict | None = None,
    rondas_lightgbm: int = RONDAS_LIGHTGBM,
    dias_validacion: int = VENTANA_VALIDACION_DIAS,
) -> ResultadoEntrenamiento:
    cliente = MlflowClient()
    mlflow.set_experiment(EXPERIMENTO)
    cuantiles = metricas.cuantil_por_familia(costos)
    params = params_lightgbm or PARAMS_LIGHTGBM

    df = preparar(ventas, feriados, tiendas)
    train, valid, inicio_validacion = dividir(df, dias_validacion)
    contexto = {
        "origen": origen,
        "filas_entrenamiento": len(train),
        "filas_validacion": len(valid),
        "fecha_inicio_datos": df["fecha"].min().date().isoformat(),
        "fecha_fin_entrenamiento": train["fecha"].max().date().isoformat(),
        "inicio_validacion": inicio_validacion.date().isoformat(),
        "fecha_fin_datos": df["fecha"].max().date().isoformat(),
    }

    with mlflow.start_run(run_name=f"entrenamiento-{origen}") as padre:
        mlflow.log_params(contexto)
        mlflow.log_dict(cuantiles, "cuantiles_por_familia.json")

        candidatos = []
        for nombre, modelo in [
            ("baseline", ModeloBaseline(cuantiles)),
            ("lightgbm", ModeloLightGBM(cuantiles, params, rondas_lightgbm)),
        ]:
            with mlflow.start_run(run_name=nombre, nested=True) as run:
                modelo.ajustar(train)
                resultado = evaluar_modelo(modelo, valid, costos)
                mlflow.log_params({"modelo": nombre, **contexto})
                if nombre == "lightgbm":
                    mlflow.log_params({**params, "rondas": rondas_lightgbm})
                mlflow.log_metrics({f"val_{k}": v for k, v in resultado.items()})
                mlflow.pyfunc.log_model("modelo", python_model=modelo, pip_requirements=REQUISITOS_PIP)
                candidatos.append((resultado["costo"], nombre, run.info.run_id))
                log.info("%s: %s", nombre, resultado)

        costo_candidato, nombre, run_id = min(candidatos)
        version = str(mlflow.register_model(f"runs:/{run_id}/modelo", NOMBRE_MODELO).version)
        for clave, valor in {**contexto, "tipo_modelo": nombre, "costo_validacion": f"{costo_candidato:.2f}"}.items():
            cliente.set_model_version_tag(NOMBRE_MODELO, version, clave, str(valor))

        vigente = version_vigente(cliente)
        costo_vigente = None
        if vigente is not None:
            modelo_vigente = mlflow.pyfunc.load_model(uri_version(vigente.version))
            costo_vigente = evaluar_modelo(modelo_vigente, valid, costos)["costo"]

        promovido, motivo = decidir_reemplazo(costo_candidato, costo_vigente)
        if promovido:
            cliente.set_registered_model_alias(NOMBRE_MODELO, ALIAS_VIGENTE, version)
        version_final = version if promovido else (str(vigente.version) if vigente else None)

        mlflow.log_params({"candidato": nombre, "version_candidata": version})
        mlflow.log_metrics(
            {"costo_candidato": costo_candidato, "promovido": int(promovido)}
            | ({"costo_vigente": costo_vigente} if costo_vigente is not None else {})
        )
        mlflow.set_tags({"motivo": motivo, "version_vigente": str(version_final), "run_padre": padre.info.run_id})

    return ResultadoEntrenamiento(
        promovido=promovido,
        version=version_final,
        version_candidata=version,
        motivo=motivo,
        costo_candidato=costo_candidato,
        costo_vigente=costo_vigente,
    )


def main() -> None:
    """Entrena con los archivos publicados (sin observaciones) y registra el resultado."""
    logging.basicConfig(level=logging.INFO)
    datos_dir = os.environ.get("DATOS_DIR", "/datos")
    resultado = entrenar_y_registrar(
        datos_mod.cargar_historico(datos_dir),
        datos_mod.cargar_feriados(datos_dir),
        datos_mod.cargar_tiendas(datos_dir),
        datos_mod.cargar_costos(datos_dir),
        origen="manual",
    )
    print(resultado)


if __name__ == "__main__":
    main()
