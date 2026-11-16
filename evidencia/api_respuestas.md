# Evidencia: respuestas de la API

Generada contra el producto levantado desde cero con `docker compose up`.

## POST /v1/prediccion

### Solicitud válida

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "version_modelo": "1",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 1582.35,
      "cantidad_sugerida": 1860
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 119.65,
      "cantidad_sugerida": 149
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 1009.61,
      "cantidad_sugerida": 1363
    },
    "... (12 familias en total)"
  ],
  "calidad": {
    "estado": "ok",
    "observaciones": []
  }
}
```

### Tienda con prefijo y como texto

Solicitud (recortada):
```json
{
  "tienda_id": "T-05",
  "fecha": "2026-03-01",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "version_modelo": "1",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 1582.35,
      "cantidad_sugerida": 1860
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 119.65,
      "cantidad_sugerida": 149
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 1009.61,
      "cantidad_sugerida": 1363
    },
    "... (12 familias en total)"
  ],
  "calidad": {
    "estado": "corregido",
    "observaciones": [
      {
        "campo": "tienda_id",
        "accion": "reparar",
        "detalle": "'T-05' se interpretó como 5"
      }
    ]
  }
}
```

### Familias escritas de otra forma

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "familias": [
    {
      "familia_id": "ABARROTES ",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "version_modelo": "1",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 1582.35,
      "cantidad_sugerida": 1860
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 119.65,
      "cantidad_sugerida": 149
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 1009.61,
      "cantidad_sugerida": 1363
    },
    "... (12 familias en total)"
  ],
  "calidad": {
    "estado": "corregido",
    "observaciones": [
      {
        "campo": "familias[0].familia_id",
        "accion": "reparar",
        "detalle": "'ABARROTES ' se interpretó como 'abarrotes'"
      },
      {
        "campo": "familias[4].familia_id",
        "accion": "reparar",
        "detalle": "'Cuidado Personal' se interpretó como 'cuidado_personal'"
      }
    ]
  }
}
```

### Promoción como texto con decimal

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": "3,0"
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "version_modelo": "1",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 1582.35,
      "cantidad_sugerida": 1860
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 119.65,
      "cantidad_sugerida": 149
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 1158.48,
      "cantidad_sugerida": 1516
    },
    "... (12 familias en total)"
  ],
  "calidad": {
    "estado": "corregido",
    "observaciones": [
      {
        "campo": "familias[2].en_promocion",
        "accion": "reparar",
        "detalle": "'3,0' se interpretó como 3"
      }
    ]
  }
}
```

### Fecha con hora (ISO)

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01T00:00:00",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "version_modelo": "1",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 1582.35,
      "cantidad_sugerida": 1860
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 119.65,
      "cantidad_sugerida": 149
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 1009.61,
      "cantidad_sugerida": 1363
    },
    "... (12 familias en total)"
  ],
  "calidad": {
    "estado": "corregido",
    "observaciones": [
      {
        "campo": "fecha",
        "accion": "reparar",
        "detalle": "'2026-03-01T00:00:00' se interpretó como '2026-03-01'"
      }
    ]
  }
}
```

### Fecha ambigua día/mes

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "03/01/2026",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "tienda_id": 5,
  "fecha": "2026-01-03",
  "version_modelo": "1",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 1324.92,
      "cantidad_sugerida": 1574
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 119.81,
      "cantidad_sugerida": 138
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 1090.83,
      "cantidad_sugerida": 1301
    },
    "... (12 familias en total)"
  ],
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "fecha",
        "accion": "advertir",
        "detalle": "'03/01/2026' es ambigua; se supuso día/mes/año: '2026-01-03'"
      }
    ]
  }
}
```

### Faltan familias

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "version_modelo": "1",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 1582.35,
      "cantidad_sugerida": 1860
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 119.65,
      "cantidad_sugerida": 149
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 1009.61,
      "cantidad_sugerida": 1363
    },
    "... (12 familias en total)"
  ],
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltan familias que la tienda vende (mascotas, panaderia, snacks); se pronosticaron suponiendo en_promocion = 0"
      }
    ]
  }
}
```

### Familia repetida con valores distintos

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "version_modelo": "1",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 1582.35,
      "cantidad_sugerida": 1860
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 119.65,
      "cantidad_sugerida": 149
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 1171.22,
      "cantidad_sugerida": 1528
    },
    "... (12 familias en total)"
  ],
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "familias[12]",
        "accion": "advertir",
        "detalle": "'bebidas' repetida con en_promocion 0 y 5; se usó el último valor (5)"
      }
    ]
  }
}
```

### Campos con otro nombre (fuera del catálogo: camelCase)

Solicitud (recortada):
```json
{
  "fecha": "2026-03-01",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ],
  "tiendaId": 5
}
```
Respuesta **HTTP 200**:
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "version_modelo": "1",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 1582.35,
      "cantidad_sugerida": 1860
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 119.65,
      "cantidad_sugerida": 149
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 1009.61,
      "cantidad_sugerida": 1363
    },
    "... (12 familias en total)"
  ],
  "calidad": {
    "estado": "corregido",
    "observaciones": [
      {
        "campo": "tienda_id",
        "accion": "reparar",
        "detalle": "el campo 'tiendaId' se interpretó como 'tienda_id'"
      },
      {
        "campo": "familias[1].en_promocion",
        "accion": "reparar",
        "detalle": "el campo 'promocion' se interpretó como 'en_promocion'"
      }
    ]
  }
}
```

### Familia con error de escritura por debajo del umbral de similitud (fuera del catálogo)

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "version_modelo": "1",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 1582.35,
      "cantidad_sugerida": 1860
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 119.65,
      "cantidad_sugerida": 149
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 1009.61,
      "cantidad_sugerida": 1363
    },
    "... (12 familias en total)"
  ],
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "familias[3].familia_id",
        "accion": "advertir",
        "detalle": "familia 'carnez' desconocida; se ignoró el elemento"
      },
      {
        "campo": "familias",
        "accion": "advertir",
        "detalle": "faltan familias que la tienda vende (carnes); se pronosticaron suponiendo en_promocion = 0"
      }
    ]
  }
}
```

### Campo desconocido (fuera del catálogo)

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ],
  "sucursal_origen": "norte"
}
```
Respuesta **HTTP 200**:
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "version_modelo": "1",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 1582.35,
      "cantidad_sugerida": 1860
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 119.65,
      "cantidad_sugerida": 149
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 1009.61,
      "cantidad_sugerida": 1363
    },
    "... (12 familias en total)"
  ],
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "sucursal_origen",
        "accion": "advertir",
        "detalle": "campo 'sucursal_origen' no pertenece al contrato; se ignoró"
      }
    ]
  }
}
```

### Promoción negativa (fuera del catálogo)

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "version_modelo": "1",
  "predicciones": [
    {
      "familia_id": "abarrotes",
      "venta_esperada": 1582.35,
      "cantidad_sugerida": 1860
    },
    {
      "familia_id": "bebe",
      "venta_esperada": 119.65,
      "cantidad_sugerida": 149
    },
    {
      "familia_id": "bebidas",
      "venta_esperada": 1009.61,
      "cantidad_sugerida": 1363
    },
    "... (12 familias en total)"
  ],
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "familias[5].en_promocion",
        "accion": "advertir",
        "detalle": "en_promocion -2 es negativo; se supuso 0"
      }
    ]
  }
}
```

### Rechazo: tienda inexistente

Solicitud (recortada):
```json
{
  "tienda_id": 42,
  "fecha": "2026-03-01",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ]
}
```
Respuesta **HTTP 422**:
```json
{
  "detail": "la tienda 42 no existe en el catálogo de tiendas"
}
```

### Rechazo: fecha imposible

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-02-30",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ]
}
```
Respuesta **HTTP 422**:
```json
{
  "detail": "fecha '2026-02-30' no es una fecha válida (formato AAAA-MM-DD)"
}
```

### Rechazo: falta la fecha

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ]
}
```
Respuesta **HTTP 422**:
```json
{
  "detail": "falta el campo obligatorio 'fecha'"
}
```

### Rechazo: campos en conflicto

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "familias": [
    {
      "familia_id": "abarrotes",
      "en_promocion": 7
    },
    {
      "familia_id": "bebe",
      "en_promocion": 4
    },
    {
      "familia_id": "bebidas",
      "en_promocion": 0
    },
    "..."
  ],
  "tienda": 6
}
```
Respuesta **HTTP 422**:
```json
{
  "detail": "los campos 'tienda_id' y 'tienda' traen valores distintos para 'tienda_id'"
}
```

### Rechazo: cuerpo que no es JSON

Solicitud: `{"tienda_id": 5, "fecha": `

Respuesta **HTTP 422**:
```json
{
  "detail": "el cuerpo de la solicitud no es un JSON válido"
}
```

## POST /v1/observaciones

### Observación válida (primer envío)

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "ventas": [
    {
      "familia_id": "abarrotes",
      "ventas": 1520
    },
    {
      "familia_id": "bebe",
      "ventas": 108
    },
    {
      "familia_id": "bebidas",
      "ventas": 1225
    },
    {
      "familia_id": "carnes",
      "ventas": 300
    },
    {
      "familia_id": "cuidado_personal",
      "ventas": 372
    },
    {
      "familia_id": "frutas_verduras",
      "ventas": 504
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "registros_guardados": 12,
  "calidad": {
    "estado": "ok",
    "observaciones": []
  }
}
```

### Envío repetido idéntico (idempotente)

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "ventas": [
    {
      "familia_id": "abarrotes",
      "ventas": 1520
    },
    {
      "familia_id": "bebe",
      "ventas": 108
    },
    {
      "familia_id": "bebidas",
      "ventas": 1225
    },
    {
      "familia_id": "carnes",
      "ventas": 300
    },
    {
      "familia_id": "cuidado_personal",
      "ventas": 372
    },
    {
      "familia_id": "frutas_verduras",
      "ventas": 504
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "registros_guardados": 0,
  "calidad": {
    "estado": "ok",
    "observaciones": []
  }
}
```

### Corrección de una familia

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "ventas": [
    {
      "familia_id": "abarrotes",
      "ventas": 1530
    },
    {
      "familia_id": "bebe",
      "ventas": 108
    },
    {
      "familia_id": "bebidas",
      "ventas": 1225
    },
    {
      "familia_id": "carnes",
      "ventas": 300
    },
    {
      "familia_id": "cuidado_personal",
      "ventas": 372
    },
    {
      "familia_id": "frutas_verduras",
      "ventas": 504
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "registros_guardados": 1,
  "calidad": {
    "estado": "ok",
    "observaciones": []
  }
}
```

### Venta negativa

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "ventas": [
    {
      "familia_id": "abarrotes",
      "ventas": 1520
    },
    {
      "familia_id": "bebe",
      "ventas": 108
    },
    {
      "familia_id": "bebidas",
      "ventas": 1225
    },
    {
      "familia_id": "carnes",
      "ventas": 300
    },
    {
      "familia_id": "cuidado_personal",
      "ventas": 372
    },
    {
      "familia_id": "frutas_verduras",
      "ventas": -4
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "registros_guardados": 1,
  "calidad": {
    "estado": "advertencia",
    "observaciones": [
      {
        "campo": "ventas[5].ventas",
        "accion": "advertir",
        "detalle": "ventas -4 es negativo (posible devolución); se descartó el registro"
      }
    ]
  }
}
```

### Números con separador de miles y coma decimal

Solicitud (recortada):
```json
{
  "tienda_id": 5,
  "fecha": "2026-03-01",
  "ventas": [
    {
      "familia_id": "abarrotes",
      "ventas": 1520
    },
    {
      "familia_id": "bebe",
      "ventas": "1,204"
    },
    {
      "familia_id": "bebidas",
      "ventas": "1225,0"
    },
    {
      "familia_id": "carnes",
      "ventas": 300
    },
    {
      "familia_id": "cuidado_personal",
      "ventas": 372
    },
    {
      "familia_id": "frutas_verduras",
      "ventas": 504
    },
    "..."
  ]
}
```
Respuesta **HTTP 200**:
```json
{
  "registros_guardados": 1,
  "calidad": {
    "estado": "corregido",
    "observaciones": [
      {
        "campo": "ventas[1].ventas",
        "accion": "reparar",
        "detalle": "'1,204' se interpretó como 1204"
      },
      {
        "campo": "ventas[2].ventas",
        "accion": "reparar",
        "detalle": "'1225,0' se interpretó como 1225"
      }
    ]
  }
}
```

## GET /modelo

```json
{
  "nombre": "novamercado-ventas",
  "alias": "vigente",
  "version": "1"
}
```

## GET /health

```json
{
  "estado": "ok"
}
```
