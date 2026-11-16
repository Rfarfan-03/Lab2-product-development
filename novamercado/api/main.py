"""Aplicación FastAPI del servicio de pronóstico de NovaMercado (contrato del Anexo)."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import Body, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine

from novamercado.api.admin import AdminReentrenamiento
from novamercado.api.airflow_cliente import ClienteAirflow
from novamercado.api.gestor_modelo import gestor_mlflow
from novamercado.api.monitor import MonitorModelo
from novamercado.api.servicio import Resultado, Servicio
from novamercado.catalogo import cargar_catalogo
from novamercado.db import repositorio
from novamercado.esquemas import InfoModelo
from novamercado.modelo import datos as datos_mod

log = logging.getLogger(__name__)


@dataclass
class Componentes:
    servicio: Servicio
    admin: AdminReentrenamiento
    monitor: MonitorModelo | None = None


def componentes_desde_entorno() -> Componentes:
    """Arma el servicio con la configuración de las variables de entorno."""
    datos_dir = os.environ.get("DATOS_DIR", "/datos")
    engine = create_engine(os.environ["NOVA_DB_URL"], pool_pre_ping=True)
    repositorio.crear_tablas(engine)
    repositorio.cargar_historico_si_vacio(engine, datos_dir)

    gestor = gestor_mlflow()
    monitor = MonitorModelo(gestor, intervalo=float(os.environ.get("MODELO_REFRESCO_SEG", "30")))
    monitor.revisar()  # primera carga; si MLflow no responde, el monitor reintenta

    servicio = Servicio(
        engine=engine,
        catalogo=cargar_catalogo(datos_dir),
        feriados=datos_mod.cargar_feriados(datos_dir),
        tiendas=datos_mod.cargar_tiendas(datos_dir),
        gestor=gestor,
    )
    airflow = ClienteAirflow(
        os.environ["AIRFLOW_URL"], os.environ["AIRFLOW_USER"], os.environ["AIRFLOW_PASSWORD"]
    )
    return Componentes(servicio, AdminReentrenamiento(engine, airflow, gestor), monitor)


def _respuesta(r: Resultado) -> JSONResponse:
    return JSONResponse(status_code=r.codigo, content=r.cuerpo)


def crear_app(componentes: Componentes | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        c = componentes or componentes_desde_entorno()
        app.state.servicio, app.state.admin = c.servicio, c.admin
        if c.monitor:
            c.monitor.iniciar()
        yield
        if c.monitor:
            c.monitor.detener()

    app = FastAPI(title="NovaMercado - Pronóstico diario de ventas", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def cuerpo_invalido(request: Request, exc: RequestValidationError):
        # Cuerpo que no es JSON válido: se registra y se rechaza con detail en texto
        crudo = (await request.body()).decode("utf-8", errors="replace")
        tipo = "observaciones" if request.url.path.endswith("observaciones") else "prediccion"
        r = request.app.state.servicio.rechazar_cuerpo_invalido(
            tipo, crudo, "el cuerpo de la solicitud no es un JSON válido"
        )
        return _respuesta(r)

    @app.post("/v1/prediccion")
    def prediccion(request: Request, payload: Any = Body(None)):
        return _respuesta(request.app.state.servicio.predecir(payload))

    @app.post("/v1/observaciones")
    def observaciones(request: Request, payload: Any = Body(None)):
        return _respuesta(request.app.state.servicio.observar(payload))

    @app.post("/admin/reentrenar", status_code=202)
    def reentrenar(request: Request):
        return _respuesta(request.app.state.admin.iniciar())

    @app.get("/admin/reentrenar/{id_ejecucion}")
    def estado_reentrenamiento(request: Request, id_ejecucion: str):
        return _respuesta(request.app.state.admin.consultar(id_ejecucion))

    @app.get("/modelo", response_model=InfoModelo)
    def modelo(request: Request):
        cargado = request.app.state.servicio.gestor.actual
        if cargado is None:
            return JSONResponse(status_code=503, content={"detail": "no hay un modelo cargado todavía"})
        return InfoModelo(nombre=cargado.nombre, alias=cargado.alias, version=cargado.version)

    return app


logging.basicConfig(level=logging.INFO)
app = crear_app()
