"""Arranque desde cero: carga los datos publicados y entrena el primer modelo.

Lo ejecuta el servicio ``bootstrap`` de Docker Compose cada vez que se levanta el producto:
- si la base de datos no tiene el histórico, lo carga;
- si no existe un modelo con el alias vigente, entrena y registra el primero;
- si ya existe, no repite ese trabajo.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from novamercado.db import repositorio
from novamercado.modelo import datos
from novamercado.modelo.entrenamiento import ResultadoEntrenamiento, entrenar_y_registrar
from novamercado.modelo.registro import version_vigente

log = logging.getLogger(__name__)


def esperar_mlflow(limite_seg: float = 300, pausa_seg: float = 5):
    """Espera a que el registro de MLflow responda. Devuelve la versión vigente (o None)."""
    inicio = time.monotonic()
    while True:
        try:
            return version_vigente()
        except Exception as e:
            if time.monotonic() - inicio > limite_seg:
                raise
            log.info("MLflow todavía no responde (%s); reintentando", e)
            time.sleep(pausa_seg)


def asegurar_modelo_inicial(engine: Engine, datos_dir: str | Path, **kwargs_entrenamiento) -> ResultadoEntrenamiento | None:
    """Entrena y registra el primer modelo solo si no hay uno vigente."""
    repositorio.preparar_bd(engine, datos_dir)

    vigente = esperar_mlflow()
    if vigente is not None:
        log.info("Ya existe el modelo vigente (versión %s); no se entrena", vigente.version)
        return None

    log.info("No hay modelo vigente: entrenando el primero")
    with engine.connect() as con:
        ventas = repositorio.ventas_para_entrenar(con)
    resultado = entrenar_y_registrar(
        ventas,
        datos.cargar_feriados(datos_dir),
        datos.cargar_tiendas(datos_dir),
        datos.cargar_costos(datos_dir),
        origen="inicial",
        **kwargs_entrenamiento,
    )
    log.info("Primer modelo: %s", resultado)
    return resultado


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    engine = create_engine(os.environ["NOVA_DB_URL"], pool_pre_ping=True)
    asegurar_modelo_inicial(engine, os.environ.get("DATOS_DIR", "/datos"))


if __name__ == "__main__":
    main()
