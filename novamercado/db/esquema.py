"""Tablas de la base de datos del producto (SQLAlchemy Core, compatible con 1.4 y 2.0)."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    func,
)

metadata = MetaData()

# Histórico publicado, cargado una sola vez al levantar el producto desde cero
historico_ventas = Table(
    "historico_ventas",
    metadata,
    Column("fecha", Date, primary_key=True),
    Column("tienda_id", Integer, primary_key=True),
    Column("familia_id", String(50), primary_key=True),
    Column("ventas", Integer, nullable=False),
    Column("en_promocion", Integer),
)

# Toda solicitud recibida, incluidas las rechazadas
solicitudes = Table(
    "solicitudes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tipo", String(20), nullable=False),  # prediccion | observaciones
    Column("recibida_en", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("tienda_id", Integer),
    Column("fecha", Date),
    Column("estado", String(20), nullable=False),  # ok | corregido | advertencia | rechazada
    Column("detalle_rechazo", Text),
    Column("cuerpo", JSON),  # cuerpo tal como llegó
)

# Correcciones aplicadas (acciones reparar / advertir de calidad.observaciones)
correcciones = Table(
    "correcciones",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("solicitud_id", Integer, ForeignKey("solicitudes.id"), nullable=False, index=True),
    Column("campo", Text, nullable=False),
    Column("accion", String(20), nullable=False),
    Column("detalle", Text, nullable=False),
)

predicciones = Table(
    "predicciones",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("solicitud_id", Integer, ForeignKey("solicitudes.id"), nullable=False, index=True),
    Column("tienda_id", Integer, nullable=False),
    Column("fecha", Date, nullable=False),
    Column("familia_id", String(50), nullable=False),
    Column("en_promocion", Integer, nullable=False),
    Column("venta_esperada", Float, nullable=False),
    Column("cantidad_sugerida", Integer, nullable=False),
    Column("version_modelo", String(50), nullable=False),
)
Index("ix_predicciones_tienda_fecha", predicciones.c.tienda_id, predicciones.c.fecha)

# Ejecuciones de reentrenamiento (id = dag_run_id de Airflow)
reentrenamientos = Table(
    "reentrenamientos",
    metadata,
    Column("id", String(100), primary_key=True),
    Column("estado", String(20), nullable=False),  # en_curso | exitoso | fallido
    Column("promovido", Boolean),
    Column("version", String(50)),  # versión vigente al terminar
    Column("version_candidata", String(50)),
    Column("motivo", Text),
    Column("solicitado_en", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("terminado_en", DateTime(timezone=True)),
)

# Ventas reales: una fila por tienda, fecha y familia (registro idempotente)
observaciones = Table(
    "observaciones",
    metadata,
    Column("fecha", Date, primary_key=True),
    Column("tienda_id", Integer, primary_key=True),
    Column("familia_id", String(50), primary_key=True),
    Column("ventas", Integer, nullable=False),
    Column("solicitud_id", Integer, ForeignKey("solicitudes.id"), nullable=False),
    Column("actualizada_en", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)
