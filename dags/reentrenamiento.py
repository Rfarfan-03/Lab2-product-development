"""DAG de reentrenamiento del modelo de pronóstico de NovaMercado.

Se dispara desde ``POST /admin/reentrenar`` (sin programación periódica). Usa el histórico
y las observaciones registradas en la base de datos del producto, entrena el baseline y
LightGBM, registra el mejor en MLflow y mueve el alias ``vigente`` solo si cumple el criterio
de reemplazo. Un fallo deja el modelo vigente intacto.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

DAG_ID = "reentrenamiento_modelo"


def _engine():
    import os

    from sqlalchemy import create_engine

    return create_engine(os.environ["NOVA_DB_URL"], pool_pre_ping=True)


def reentrenar(**context):
    import os

    from novamercado.db import repositorio
    from novamercado.modelo import datos
    from novamercado.modelo.entrenamiento import entrenar_y_registrar

    run_id = context["dag_run"].run_id
    datos_dir = os.environ.get("DATOS_DIR", "/datos")
    engine = _engine()
    repositorio.crear_tablas(engine)

    with engine.connect() as con:
        ventas = repositorio.ventas_para_entrenar(con)

    resultado = entrenar_y_registrar(
        ventas,
        datos.cargar_feriados(datos_dir),
        datos.cargar_tiendas(datos_dir),
        datos.cargar_costos(datos_dir),
        origen="reentrenamiento",
    )

    with engine.begin() as con:
        repositorio.finalizar_reentrenamiento(
            con,
            run_id,
            estado="exitoso",
            promovido=resultado.promovido,
            version=resultado.version,
            version_candidata=resultado.version_candidata,
            motivo=resultado.motivo,
        )
    return {"promovido": resultado.promovido, "version": resultado.version, "motivo": resultado.motivo}


def registrar_fallo(context):
    """Si la tarea falla, se registra el motivo; el alias del modelo no se tocó."""
    from novamercado.db import repositorio
    from novamercado.modelo.registro import version_vigente

    try:
        vigente = version_vigente()
        version = str(vigente.version) if vigente else None
    except Exception:
        version = None
    error = context.get("exception")
    with _engine().begin() as con:
        repositorio.finalizar_reentrenamiento(
            con,
            context["dag_run"].run_id,
            estado="fallido",
            promovido=False,
            version=version,
            motivo=f"El reentrenamiento falló ({type(error).__name__}: {error}); se mantiene el modelo vigente",
        )


with DAG(
    dag_id=DAG_ID,
    description="Reentrena con histórico + observaciones y aplica el criterio de reemplazo",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,  # dos reentrenamientos no compiten por el alias
    dagrun_timeout=timedelta(minutes=10),
    tags=["novamercado"],
) as dag:
    PythonOperator(
        task_id="reentrenar",
        python_callable=reentrenar,
        retries=0,
        execution_timeout=timedelta(minutes=9),
        on_failure_callback=registrar_fallo,
    )
