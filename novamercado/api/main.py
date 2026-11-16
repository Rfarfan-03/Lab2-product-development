"""Aplicación FastAPI del servicio de pronóstico de NovaMercado.

Los endpoints del contrato (Anexo del laboratorio) se agregan en los siguientes PRs.
"""

from fastapi import FastAPI

app = FastAPI(title="NovaMercado - Pronóstico diario de ventas")
