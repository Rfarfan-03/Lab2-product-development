FROM apache/airflow:2.10.3-python3.11

# libgomp1: requerida por LightGBM
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
USER airflow

# Mismas versiones que la API para que el modelo entrenado aquí se cargue igual allá.
# Se fija apache-airflow en la misma instalación para que pip no lo modifique.
RUN pip install --no-cache-dir \
    "apache-airflow==2.10.3" \
    "lightgbm==4.5.0" \
    "mlflow-skinny==2.16.2"

COPY --chown=airflow:root novamercado/ /opt/airflow/novamercado/
COPY --chown=airflow:root dags/ /opt/airflow/dags/

ENV PYTHONPATH=/opt/airflow
