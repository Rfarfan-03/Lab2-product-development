"""Construcción de features con la información disponible al pronosticar.

Para la fecha ``d`` de una tienda y familia se usan:
- calendario de ``d`` y feriados que aplican a la ciudad de la tienda (nacional o local);
- promociones del día, que llegan en la solicitud;
- ventas de fechas estrictamente anteriores a ``d`` (lags y medias móviles).

La misma función sirve para entrenar (objetivos = filas del histórico) y para predecir
(objetivos = familias de la solicitud), así que no hay diferencias entre ambos caminos.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

CATEGORICAS = ["tienda_id", "familia_id", "tipo_tienda"]
CALENDARIO = [
    "dia_semana",
    "dia_mes",
    "mes",
    "dia_anio",
    "es_feriado",
    "es_medio_dia",
    "es_comercial",
    "es_pago",
    "manana_feriado",
    "ayer_feriado",
]
LAGS = [1, 2, 3, 7, 14, 28]
HISTORIA = [f"lag_{k}" for k in LAGS] + [
    "media_7",
    "media_28",
    "media_mismo_dia_4",
    "std_7",
    "dias_desde_ultima_venta",
]
FEATURES = CATEGORICAS + CALENDARIO + ["en_promocion"] + HISTORIA

# Días de historia que necesita una predicción (la ventana más larga)
DIAS_HISTORIA_NECESARIOS = 35


def tabla_feriados(feriados: pd.DataFrame, tiendas: pd.DataFrame) -> pd.DataFrame:
    """Indicadores de feriado por tienda y fecha, según la ciudad de la tienda."""
    filas = []
    for _, t in tiendas.iterrows():
        aplica = feriados[(feriados["ambito"] == "nacional") | (feriados["ambito"] == t["ciudad"])]
        for _, f in aplica.iterrows():
            filas.append({"tienda_id": int(t["tienda_id"]), "fecha": f["fecha"], "tipo": f["tipo"]})
    if not filas:
        return pd.DataFrame(columns=["tienda_id", "fecha", "es_feriado", "es_medio_dia", "es_comercial", "es_pago"])
    df = pd.DataFrame(filas)
    indicadores = pd.crosstab([df["tienda_id"], df["fecha"]], df["tipo"]).clip(upper=1)
    indicadores = indicadores.reindex(columns=["feriado", "medio_dia", "comercial", "pago"], fill_value=0)
    indicadores.columns = ["es_feriado", "es_medio_dia", "es_comercial", "es_pago"]
    return indicadores.reset_index()


def construir_features(
    historia: pd.DataFrame,
    objetivos: pd.DataFrame,
    feriados: pd.DataFrame,
    tiendas: pd.DataFrame,
) -> pd.DataFrame:
    """Devuelve ``objetivos`` con las columnas de ``FEATURES`` agregadas.

    ``historia``: fecha, tienda_id, familia_id, ventas.
    ``objetivos``: fecha, tienda_id, familia_id, en_promocion (y opcionalmente ventas).
    """
    obj = objetivos.copy()
    obj["fecha"] = pd.to_datetime(obj["fecha"])
    hist = historia[["fecha", "tienda_id", "familia_id", "ventas"]].copy()
    hist["fecha"] = pd.to_datetime(hist["fecha"])

    obj = obj.merge(_features_de_historia(hist, obj), on=["fecha", "tienda_id", "familia_id"], how="left")

    # calendario
    obj["dia_semana"] = obj["fecha"].dt.dayofweek
    obj["dia_mes"] = obj["fecha"].dt.day
    obj["mes"] = obj["fecha"].dt.month
    obj["dia_anio"] = obj["fecha"].dt.dayofyear

    # feriados de la ciudad de la tienda (el día, la víspera y el día siguiente)
    fer = tabla_feriados(feriados, tiendas)
    obj = obj.merge(fer, on=["tienda_id", "fecha"], how="left")
    feriado_dia = fer[["tienda_id", "fecha", "es_feriado"]]
    manana = feriado_dia.assign(fecha=feriado_dia["fecha"] - pd.Timedelta(days=1)).rename(
        columns={"es_feriado": "manana_feriado"}
    )
    ayer = feriado_dia.assign(fecha=feriado_dia["fecha"] + pd.Timedelta(days=1)).rename(
        columns={"es_feriado": "ayer_feriado"}
    )
    obj = obj.merge(manana, on=["tienda_id", "fecha"], how="left").merge(ayer, on=["tienda_id", "fecha"], how="left")
    for c in ["es_feriado", "es_medio_dia", "es_comercial", "es_pago", "manana_feriado", "ayer_feriado"]:
        obj[c] = obj[c].fillna(0).astype(int)

    tipos = tiendas.set_index("tienda_id")["tipo"]
    obj["tipo_tienda"] = obj["tienda_id"].map(tipos)
    obj["en_promocion"] = pd.to_numeric(obj["en_promocion"], errors="coerce")
    return obj


def _features_de_historia(hist: pd.DataFrame, obj: pd.DataFrame) -> pd.DataFrame:
    """Lags y medias móviles usando solo fechas anteriores a cada objetivo."""
    inicio = min(hist["fecha"].min(), obj["fecha"].min()) if not hist.empty else obj["fecha"].min()
    fin = obj["fecha"].max()
    fechas = pd.date_range(inicio, fin, freq="D")

    series = hist.pivot_table(index="fecha", columns=["tienda_id", "familia_id"], values="ventas", aggfunc="last")
    claves = pd.MultiIndex.from_frame(obj[["tienda_id", "familia_id"]].drop_duplicates())
    series = series.reindex(index=fechas, columns=series.columns.union(claves))
    series.index.name = "fecha"
    series.columns.names = ["tienda_id", "familia_id"]

    previas = series.shift(1)  # en la fila d solo hay ventas hasta d-1
    calculos: dict[str, pd.DataFrame] = {f"lag_{k}": series.shift(k) for k in LAGS}
    calculos["media_7"] = previas.rolling(7, min_periods=1).mean()
    calculos["media_28"] = previas.rolling(28, min_periods=1).mean()
    calculos["std_7"] = previas.rolling(7, min_periods=2).std()
    mismo_dia = np.stack([series.shift(k).to_numpy() for k in (7, 14, 21, 28)])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # columnas sin datos
        media_mismo = np.nanmean(mismo_dia, axis=0)
    calculos["media_mismo_dia_4"] = pd.DataFrame(media_mismo, index=series.index, columns=series.columns)

    # días transcurridos desde la última fecha con dato (útil si faltan observaciones)
    hay_dato = previas.notna()
    posicion = pd.DataFrame(
        np.where(hay_dato, np.arange(len(series))[:, None], np.nan), index=series.index, columns=series.columns
    ).ffill()
    calculos["dias_desde_ultima_venta"] = pd.DataFrame(
        np.arange(len(series))[:, None] - posicion.to_numpy() + 1, index=series.index, columns=series.columns
    )

    largas = [df.stack(["tienda_id", "familia_id"], future_stack=True).rename(nombre) for nombre, df in calculos.items()]
    resultado = pd.concat(largas, axis=1).reset_index()
    llaves = obj[["fecha", "tienda_id", "familia_id"]].drop_duplicates()
    return llaves.merge(resultado, on=["fecha", "tienda_id", "familia_id"], how="left")
