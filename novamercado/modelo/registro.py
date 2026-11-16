"""Acceso al Model Registry de MLflow. El modelo vigente se identifica con un alias."""

from __future__ import annotations

from mlflow.entities.model_registry import ModelVersion
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

NOMBRE_MODELO = "novamercado-ventas"
ALIAS_VIGENTE = "vigente"
EXPERIMENTO = "novamercado-ventas"


def version_vigente(cliente: MlflowClient | None = None) -> ModelVersion | None:
    """Versión con el alias vigente, o ``None`` si todavía no existe ninguna."""
    cliente = cliente or MlflowClient()
    try:
        return cliente.get_model_version_by_alias(NOMBRE_MODELO, ALIAS_VIGENTE)
    except MlflowException as e:
        if e.error_code in ("RESOURCE_DOES_NOT_EXIST", "INVALID_PARAMETER_VALUE"):
            return None
        raise


def uri_version(version: str) -> str:
    return f"models:/{NOMBRE_MODELO}/{version}"
