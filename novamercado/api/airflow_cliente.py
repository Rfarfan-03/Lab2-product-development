"""Cliente mínimo de la REST API de Airflow (disparar y consultar ejecuciones del DAG)."""

from __future__ import annotations

import requests

DAG_REENTRENAMIENTO = "reentrenamiento_modelo"


class AirflowNoDisponible(Exception):
    pass


class ClienteAirflow:
    def __init__(self, url: str, usuario: str, clave: str, dag_id: str = DAG_REENTRENAMIENTO, timeout: float = 10):
        self.url = url.rstrip("/")
        self.auth = (usuario, clave)
        self.dag_id = dag_id
        self.timeout = timeout

    def _llamar(self, metodo: str, ruta: str, **kwargs) -> requests.Response:
        try:
            return requests.request(
                metodo, f"{self.url}/api/v1{ruta}", auth=self.auth, timeout=self.timeout, **kwargs
            )
        except requests.RequestException as e:
            raise AirflowNoDisponible(str(e)) from e

    def disparar(self, id_ejecucion: str) -> None:
        r = self._llamar("POST", f"/dags/{self.dag_id}/dagRuns", json={"dag_run_id": id_ejecucion, "conf": {}})
        if r.status_code != 200:
            raise AirflowNoDisponible(f"Airflow respondió {r.status_code}: {r.text[:300]}")

    def estado(self, id_ejecucion: str) -> str | None:
        """Estado de Airflow (queued, running, success, failed) o None si no existe."""
        r = self._llamar("GET", f"/dags/{self.dag_id}/dagRuns/{id_ejecucion}")
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise AirflowNoDisponible(f"Airflow respondió {r.status_code}")
        return r.json().get("state")

    def disponible(self) -> bool:
        try:
            r = self._llamar("GET", "/health")
        except AirflowNoDisponible:
            return False
        return r.status_code == 200
