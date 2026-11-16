import pytest
from pydantic import ValidationError

from novamercado.esquemas import (
    Calidad,
    EstadoReentrenamiento,
    ObservacionCalidad,
    PrediccionFamilia,
    RespuestaPrediccion,
)


def obs(accion):
    return ObservacionCalidad(campo="x", accion=accion, detalle="d")


def test_calidad_ok_sin_observaciones():
    assert Calidad(estado="ok").observaciones == []


@pytest.mark.parametrize(
    "estado, observaciones",
    [
        ("ok", ["reparar"]),
        ("corregido", []),
        ("corregido", ["reparar", "advertir"]),
        ("advertencia", ["reparar"]),
    ],
)
def test_calidad_incoherente_es_invalida(estado, observaciones):
    with pytest.raises(ValidationError):
        Calidad(estado=estado, observaciones=[obs(a) for a in observaciones])


def test_accion_fuera_del_contrato_es_invalida():
    with pytest.raises(ValidationError):
        ObservacionCalidad(campo="x", accion="rechazar", detalle="d")


def test_cantidad_sugerida_no_negativa():
    with pytest.raises(ValidationError):
        PrediccionFamilia(familia_id="abarrotes", venta_esperada=1.0, cantidad_sugerida=-1)


def test_respuesta_prediccion_tiene_los_campos_del_contrato():
    r = RespuestaPrediccion(
        tienda_id=5,
        fecha="2025-11-17",
        version_modelo="3",
        predicciones=[PrediccionFamilia(familia_id="abarrotes", venta_esperada=612.4, cantidad_sugerida=640)],
        calidad=Calidad(estado="corregido", observaciones=[obs("reparar")]),
    )
    datos = r.model_dump()
    assert set(datos) >= {"tienda_id", "fecha", "version_modelo", "predicciones", "calidad"}
    assert isinstance(datos["version_modelo"], str)
    assert set(datos["predicciones"][0]) >= {"familia_id", "venta_esperada", "cantidad_sugerida"}


def test_estado_reentrenamiento_en_curso_omite_campos_finales():
    datos = EstadoReentrenamiento(estado="en_curso").model_dump(exclude_none=True)
    assert datos == {"estado": "en_curso"}
