"""Lectura de los archivos publicados y combinación con las observaciones registradas."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMNAS_VENTAS = ["fecha", "tienda_id", "familia_id", "ventas", "en_promocion"]


def cargar_historico(datos_dir: str | Path) -> pd.DataFrame:
    df = pd.read_csv(Path(datos_dir) / "historico_ventas.csv", parse_dates=["fecha"])
    return df[COLUMNAS_VENTAS]


def cargar_feriados(datos_dir: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(datos_dir) / "feriados.csv", parse_dates=["fecha"], encoding="utf-8")


def cargar_tiendas(datos_dir: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(datos_dir) / "tiendas.csv", parse_dates=["fecha_apertura"], encoding="utf-8")


def cargar_costos(datos_dir: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(datos_dir) / "costos.csv")


def combinar_ventas(historico: pd.DataFrame, observaciones: pd.DataFrame | None) -> pd.DataFrame:
    """Une el histórico con las observaciones registradas.

    Si una observación coincide con un registro del histórico (misma tienda, familia y
    fecha) prevalece la observación. Las observaciones no traen ``en_promocion``; quien
    llama puede adjuntarlo desde las solicitudes de pronóstico registradas (o dejarlo nulo).
    """
    if observaciones is None or observaciones.empty:
        return historico.copy()
    obs = observaciones.copy()
    obs["fecha"] = pd.to_datetime(obs["fecha"])
    if "en_promocion" not in obs:
        obs["en_promocion"] = float("nan")
    combinado = pd.concat([historico, obs[COLUMNAS_VENTAS]], ignore_index=True)
    combinado = combinado.drop_duplicates(["fecha", "tienda_id", "familia_id"], keep="last")
    return combinado.sort_values(["fecha", "tienda_id", "familia_id"]).reset_index(drop=True)
