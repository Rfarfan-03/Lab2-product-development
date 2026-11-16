# Decisiones técnicas y de producto

Este documento explica las decisiones principales del producto, las alternativas consideradas y por
qué se eligió cada una. Las cuatro decisiones que pide el enunciado están en las secciones 1 a 4.

---

## 1. Política ante problemas en los datos de entrada

### Principios

El servicio no debe detenerse por datos defectuosos, pero tampoco debe inventar datos. Las reglas
son **generales** (por tipo de problema, no por ejemplo del catálogo) porque en operación llegarán
problemas que no están en el catálogo.

| Acción | Cuándo | Efecto |
|---|---|---|
| **Reparar** | La corrección es inequívoca: solo hay una interpretación posible | Se corrige y se informa (`accion: reparar`) |
| **Advertir** | Se puede responder, pero con un supuesto | Se responde y se informa el supuesto (`accion: advertir`) |
| **Rechazar** | Sin el dato no se sabe a quién o para cuándo pronosticar | 422 con `detail` que explica el motivo |

**Regla de alcance.** Un problema en la solicitud completa (cuerpo, tienda, fecha, lista de familias)
que no se puede interpretar provoca un rechazo. Un problema en **un elemento** de la lista no rechaza
toda la solicitud: se descarta o se completa ese elemento con advertencia. Así, un solo error de
escritura no deja a una tienda sin el pronóstico de sus demás familias.

Toda solicitud queda registrada (tabla `solicitudes`, también las rechazadas, con el cuerpo tal como
llegó), y cada acción queda en `correcciones`.

### Reglas generales (`novamercado/limpieza/`)

**Nombres de campo** (`comunes.mapear_campos`). Cada clave se reduce a una forma compacta: sin
mayúsculas ni acentos, sin separadores, sin `camelCase`, sin las palabras `id`, `en`, `de` y con
singular y plural equivalentes. Si esa forma corresponde a un único campo del contrato, se repara
(`tienda`, `TiendaId`, `id_tienda` → `tienda_id`; `promocion` → `en_promocion`).

- Una clave que no corresponde a ningún campo se ignora con advertencia: no se sabe qué quería decir
  la tienda.
- Dos claves para el mismo campo con valores distintos son una contradicción, así que se rechaza la
  solicitud (o se descarta el elemento, si ocurre dentro de la lista).

**Números** (`normalizacion.interpretar_numero`). Se aceptan enteros, decimales y texto. El separador
de miles y la coma decimal se distinguen por posición:
- Si aparecen los dos separadores, el último es el decimal.
- Si hay uno solo seguido de exactamente 3 dígitos, es de miles (`"1,234"` → 1234).
- En cualquier otro caso, es decimal (`"812,0"` → 812).

Como son cantidades en unidades, un valor decimal entero (`2.0`) se repara, y uno no entero (`2.6`)
se redondea con advertencia.

**Fechas** (`normalizacion.interpretar_fecha`). Se reparan `AAAA/MM/DD`, `AAAAMMDD`, ISO con hora y
`DD/MM/AAAA` o `MM/DD/AAAA` cuando solo hay una lectura posible (uno de los números es mayor que 12).

- Si ambas lecturas son válidas (`05/11/2025`), se supone día/mes, el orden que se usa en Guatemala,
  y se advierte.
- Una fecha que no existe en el calendario se rechaza. También una anterior a la apertura de la
  tienda.
- **No se usa el reloj del sistema**: el servicio opera con fechas simuladas.

**Identificador de tienda** (`comunes.interpretar_tienda`). Se repara si llega como texto numérico,
con un prefijo de letras (`T05`, `Tienda 5`) o con el nombre de la tienda. Si no se puede interpretar
o la tienda no existe, se rechaza.

**Familia** (`comunes.interpretar_familia`). Se compara contra el id y el nombre del catálogo, sin
mayúsculas, acentos, separadores ni conectores (`LÁCTEOS`, `Frutas y Verduras`). Una coincidencia
exacta se repara. Una coincidencia aproximada única con similitud ≥ 0.85 (error de escritura como
`abarotes`) se acepta con advertencia, porque es un supuesto. Por debajo de ese umbral la familia se
considera desconocida: se descarta el elemento con advertencia y la familia queda como faltante (ver
E05). Por ejemplo, `carnez` tiene similitud 0.83 con `carnes`, así que se descarta y `carnes` se
pronostica con `en_promocion = 0`. El umbral es alto a propósito: se prefiere no adivinar.

### Política por tipo de problema

| Problema | Ejemplo | Política | Alternativa descartada y por qué |
|---|---|---|---|
| E01 Tienda como texto o con prefijo | `"T05"`, `"5"` | Reparar | Rechazar: el valor es inequívoco |
| Tienda inexistente o ininterpretable | `42`, `"abc"` | Rechazar | Adivinar la tienda: sería inventar |
| E02 Familia escrita de otra forma | `"LÁCTEOS"` | Reparar | — |
| Familia con error de escritura (similitud ≥ 0.85) | `"abarotes"` | Advertir | Reparar: no es inequívoco |
| Familia desconocida (incluye similitud < 0.85) | `"juguetes"`, `"carnez"` | Descartar el elemento y advertir | Rechazar toda la solicitud: castiga a las demás familias |
| E03 Promoción como texto o decimal | `"3"`, `2.0` | Reparar | — |
| Promoción no numérica, negativa o ausente | `"muchas"`, `-2` | Suponer 0 y advertir | Rechazar: la promoción ajusta el pronóstico, pero sin ella todavía se puede pronosticar |
| Promoción mayor al máximo histórico | `500` | Usar el valor y advertir | Recortarla: modificaría el dato de la tienda |
| E04 Fecha en otro formato | `"17/11/2025"` | Reparar | — |
| Fecha ambigua | `"05/11/2025"` | Suponer día/mes y advertir | Rechazar: la convención local resuelve casi todos los casos |
| Fecha imposible o faltante | `"2025-02-30"` | Rechazar | No hay para cuándo pronosticar |
| Fecha posterior a la cobertura de `feriados.csv` | `2027-03-01` | Suponer día no feriado y advertir | Rechazar: el modelo puede pronosticar sin feriados |
| E05 Faltan familias | 10 de 12 | Pronosticar las faltantes con `en_promocion = 0` y advertir | Responder solo las pedidas (ver abajo) |
| E06 Familia repetida, valores distintos | `abarrotes` ×2 | Usar el último valor y advertir | Rechazar: el resto de la solicitud es válido |
| Familia repetida, mismo valor | `abarrotes` ×2 | Reparar (se ignora la repetición) | — |
| E07 Campo con otro nombre | `"tienda"` | Reparar | — |
| Campo desconocido | `"comentario"` | Ignorar y advertir | Ignorar sin avisar: la tienda debe saber que no se usó |
| Campos en conflicto | `tienda` y `tienda_id` distintos | Rechazar | Elegir uno: sería adivinar |
| Cuerpo que no es objeto JSON | `[]`, JSON inválido | Rechazar | — |
| Lista de familias vacía o ausente | `[]` | Rechazar | No hay nada que pronosticar |
| E08 Ventas negativas | `-4` | Descartar el registro y advertir | Guardar 0 o el valor absoluto: inventaría la venta real |
| E09 Envío repetido | misma observación | Idempotente: `registros_guardados = 0` | Duplicar filas: sesga el reentrenamiento |
| Observación corregida | mismo día, otro valor | Se actualiza; cuenta como modificado | Ignorar: la última versión es la corrección de la tienda |
| E10 Separador de miles o coma decimal | `"1,234"`, `"812,0"` | Reparar | — |
| Ventas no numéricas o ausentes | `"n/a"` | Descartar el registro y advertir | Suponer un valor: inventaría la verdad |
| Ventas no enteras | `10.4` | Redondear y advertir | — |

**¿Por qué completar las familias faltantes (E05) y no responder solo las pedidas?** El catálogo dice
"faltan familias **que la tienda vende**": la tienda necesita preparar el inventario de todas. Un
pronóstico sin promoción es un supuesto razonable (0 es el valor más frecuente en el histórico), y se
informa. Las familias que vende cada tienda se obtienen del histórico.

**¿Por qué las observaciones descartan en lugar de suponer?** Las observaciones son la verdad con la
que se reentrena. Un valor inventado contaminaría el modelo, mientras que un registro faltante solo
reduce un poco los datos de entrenamiento.

---

## 2. Información que usa el modelo al predecir

Todas las features se construyen con `novamercado/modelo/features.construir_features`, **la misma
función** al entrenar y al predecir, así que no hay diferencias entre ambos caminos.

| Grupo | Features | Origen |
|---|---|---|
| Identidad | `tienda_id`, `familia_id`, `tipo_tienda` | Solicitud + `tiendas.csv` |
| Calendario | día de la semana, día del mes, mes, día del año | Fecha de la solicitud |
| Feriados | feriado, medio día, fecha comercial, fecha de pago, víspera de feriado, día después de feriado | `feriados.csv` (nacionales y los de la **ciudad de la tienda**) |
| Promoción | `en_promocion` del día | Solicitud |
| Historia | lags de 1, 2, 3, 7, 14 y 28 días; media de 7 y 28 días; desviación de 7 días; media del mismo día de la semana en las 4 semanas previas; días desde el último dato | Histórico + observaciones registradas |

Reglas:
- Para pronosticar la fecha `d` **solo se usan ventas de fechas anteriores a `d`**. Si existe una
  observación de `d` o posterior, se ignora. Hay una prueba que lo verifica
  (`test_prediccion_no_usa_observaciones_del_mismo_dia_ni_posteriores`).
- Cuando una observación y el histórico tienen la misma tienda, familia y fecha, prevalece la
  observación.
- Si faltan observaciones (por ejemplo, la tienda no reportó un día), los lags quedan nulos y LightGBM
  los trata como faltantes. `dias_desde_ultima_venta` le indica al modelo cuánta información reciente
  tiene. Las medias móviles usan los datos disponibles en su ventana.
- La promoción del día se conoce por la solicitud. Al reentrenar con observaciones (que no traen
  promoción) se usa la promoción informada en la última solicitud de pronóstico de esa tienda, fecha
  y familia.
- No se usa ninguna variable del futuro ni el reloj del sistema.

**Alternativas.**
- Se probó escalar el objetivo por la media de 28 días para que el modelo fuera relativo al nivel de
  cada serie. El costo de validación empeoró de 90 966 a 137 863, porque se vuelve inestable cuando la
  media es muy pequeña.
- No se usaron features de tendencia de largo plazo: el histórico no muestra tendencia (medias
  trimestrales estables, con un pico en Q4 que ya capturan mes y día del año). Los lags recientes
  permiten adaptarse a cambios de nivel de la demanda.

---

## 3. Elección de la cantidad sugerida

Con el costo del enunciado, para cada familia:

```
costo = c_faltante · max(real − q, 0) + c_sobrante · max(q − real, 0)
```

la cantidad `q` que minimiza el costo esperado es el **cuantil τ = c_faltante / (c_faltante + c_sobrante)**
de la distribución de la demanda (solución clásica del *newsvendor*). Esa pérdida es exactamente la
pérdida pinball del cuantil τ multiplicada por (c_faltante + c_sobrante). Por eso:

- **LightGBM** entrena una regresión cuantílica (objetivo `quantile`, `alpha = τ`) por cada τ
  distinto, y la usa para las familias con ese τ. Optimiza directamente la métrica de negocio y
  captura que la incertidumbre cambia según la tienda, el día y la promoción.
- **Baseline**: `venta_esperada × factor`, donde el factor de cada familia es el cuantil τ del
  cociente real/esperada observado en entrenamiento.

| Familia | c_faltante | c_sobrante | τ |
|---|---|---|---|
| licores | 2.0 | 0.1 | 0.95 |
| limpieza, cuidado_personal | 1.0 | 0.1 | 0.91 |
| bebe | 1.5 | 0.2 | 0.88 |
| abarrotes, bebidas, mascotas | 1.0 | 0.2 | 0.83 |
| snacks | 1.0 | 0.3 | 0.77 |
| lacteos | 1.0 | 1.2 | 0.45 |
| carnes | 1.5 | 2.0 | 0.43 |
| frutas_verduras | 1.0 | 2.0 | 0.33 |
| panaderia | 1.0 | 2.5 | 0.29 |

Así la sugerencia queda por encima de la venta esperada en las familias donde faltar cuesta más
(licores) y por debajo en las perecederas donde sobrar cuesta más (panadería). Hay una prueba que lo
verifica (`test_cantidad_sugerida_sigue_los_costos`). La cantidad se redondea a un entero no negativo.

**Resultados en validación** (últimos 28 días del histórico):

| Alternativa | Costo |
|---|---|
| Sugerir la venta esperada del baseline (sin considerar costos) | 143 795 |
| Baseline con cuantil por familia | 105 869 |
| **LightGBM con regresión cuantílica por τ** | **90 966** |

**Alternativas descartadas.**
- Sugerir la venta esperada: ignora la asimetría de costos. Con el mismo baseline cuesta 36 % más que
  usar el cuantil (143 795 contra 105 869).
- Venta esperada más un margen fijo de seguridad: un solo margen no puede ser óptimo para familias con
  τ entre 0.29 y 0.95.
- Cuantiles empíricos de los residuos aplicados al pronóstico puntual: suponen la misma dispersión en
  todas las tiendas y días; la regresión cuantílica la modela.

---

## 4. Criterio de reemplazo del modelo

**Criterio** (`novamercado/modelo/criterio.py`): el modelo nuevo reemplaza al vigente **solo si su
costo de negocio en la ventana de validación es estrictamente menor** que el del vigente evaluado en la
misma ventana. Si no hay vigente, el primero se promueve.

Funcionamiento en cada entrenamiento (`novamercado/modelo/entrenamiento.py`):

1. La ventana de validación son los **últimos 28 días** de datos disponibles (histórico más
   observaciones): 4 semanas completas, así que todos los días de la semana pesan igual.
2. Se entrenan el baseline y LightGBM con los datos anteriores a la ventana. El de menor costo es el
   candidato y se registra como versión nueva, con su linaje en tags: datos, ventana y costo.
3. El vigente (alias `vigente`) se carga desde MLflow y se evalúa en la misma ventana.
4. Si se cumple el criterio se mueve el alias; si no, el alias queda igual. El resultado y el motivo
   se registran en MLflow y en la tabla `reentrenamientos`, por ejemplo: "Costo en validación 88 693 vs
   88 886 del vigente".

**El modelo registrado no se reentrena con la ventana de validación.** Esto mantiene la comparación
justa: en el siguiente reentrenamiento la ventana se mueve hacia adelante, sobre días que el vigente
tampoco vio. Si el vigente se hubiera reentrenado con todos los datos, sería evaluado sobre días que ya
conoce, parecería mejor de lo que es y bloquearía modelos nuevos que sí mejoran. El costo es que el
modelo no aprende de los últimos 28 días. Se compensa porque, al predecir, los lags y las medias usan
las observaciones más recientes.

**Por qué el costo y no el MAE o el RMSE.** El costo es lo que evalúa el negocio y lo que se evalúa en
el laboratorio. Las métricas técnicas (MAE, RMSE, WAPE, sesgo) se registran en MLflow para
diagnóstico.

**Por qué "estrictamente menor" y sin margen.** Es el criterio más simple y explícito. Con la misma
información y el mismo modelo el resultado es determinista (semilla fija), así que reentrenar sin datos
nuevos no promueve nada. Un margen mínimo, por ejemplo de 1 %, frenaría cambios útiles cuando la
demanda cambia de forma gradual.

**Garantías.**
- Un reentrenamiento que falla (excepción, MLflow caído, tiempo agotado) nunca mueve el alias, porque
  el alias es lo último que se toca.
- `max_active_runs=1` evita que dos reentrenamientos compitan por el alias.

---

## 5. Otras decisiones técnicas

**Modelos.** El baseline es la media del mismo día de la semana en las 4 semanas previas: es simple y
captura la estacionalidad semanal. El modelo de ML es LightGBM, que maneja features categóricas y
valores faltantes, entrena en segundos (unos 45 s el ciclo completo) y soporta regresión cuantílica.
Hiperparámetros: `learning_rate` 0.03, 31 hojas, `min_data_in_leaf` 100, `feature_fraction` 0.8 y
800 rondas, elegidos entre tres configuraciones por costo de validación.

**Registro en MLflow.** Cada entrenamiento es un run padre con dos runs anidados (baseline y
LightGBM), con parámetros, métricas y el modelo como pyfunc. El mejor se registra en el Model Registry
como `novamercado-ventas`, y el vigente se identifica con el alias `vigente`. MLflow usa SQLite y
artefactos en un volumen, servidos por el propio servidor (`--serve-artifacts`).

**Reentrenamiento con Airflow.**
- `POST /admin/reentrenar` crea la fila en `reentrenamientos` y dispara el DAG por la REST API de
  Airflow, con un `dag_run_id` propio que es el `id` devuelto.
- El DAG escribe el resultado en la base del producto. Si falla, un callback registra el motivo.
- `GET /admin/reentrenar/{id}` lee esa fila y, mientras esté en curso, consulta a Airflow para detectar
  fallas que no alcanzaron a registrarse.
- Si MLflow no responde, la versión informada en un fallo es la última versión vigente registrada.

**Uso del modelo nuevo sin reinicio.** Un hilo de la API revisa el alias cada 30 s y carga la versión
nueva si cambió. En la evidencia, el modelo promovido se usa unos 20 s después de terminar el
reentrenamiento (el requisito es ≤ 2 min). Se descartó que el DAG notifique a la API: acoplaría Airflow
con la API y fallaría si la API está caída en ese momento.

**Resiliencia ante MLflow caído.** La API predice con el modelo en memoria, y su cliente de MLflow no
reintenta, para no bloquearse. `GET /health` revisa en vivo, con timeouts de 3 s, la base de datos,
MLflow (`/health`), Airflow (webserver y scheduler) y el modelo cargado. La caída se refleja en
segundos y el estado vuelve a `ok` en cuanto MLflow responde. Se descartó guardar el modelo en disco
local: el requisito es seguir respondiendo con el modelo **cargado**.

**Persistencia.** PostgreSQL propia del producto (`db`), separada de la de Airflow (`airflow-db`),
con volúmenes nombrados.
- `observaciones` tiene clave (tienda, fecha, familia) y solo se insertan o actualizan los registros
  nuevos o con ventas distintas. `registros_guardados` cuenta exactamente esos, y reenviar lo mismo
  devuelve 0.
- El histórico se carga una sola vez en `historico_ventas`, para que el DAG y la API lean todo desde
  la base de datos.

**Arranque desde cero.** El servicio `bootstrap` (misma imagen que la API) carga el histórico y
entrena y registra el primer modelo solo si no hay alias vigente; después termina. La API arranca en
paralelo y responde 503 en `/health` hasta tener modelo. La API y el bootstrap se coordinan con un
advisory lock de PostgreSQL al crear tablas. Se eligió un servicio aparte en lugar de entrenar dentro
de la API para no bloquear su arranque ni mezclar responsabilidades.

**Versiones.** Todas las imágenes y dependencias tienen versión fija. pandas, numpy, LightGBM y
mlflow-skinny son las mismas en la API y en Airflow, porque el modelo se entrena en un lado y se
carga en el otro.

---

## 6. Limitaciones conocidas

- La validación usa 28 días. Si la demanda cambia de forma brusca, el modelo puede tardar hasta un
  reentrenamiento en reflejar el cambio en su estructura, aunque los lags lo reflejan desde el día
  siguiente.
- Si la API se reinicia mientras MLflow está caído, no puede cargar el modelo hasta que MLflow vuelva
  (`/health` responde 503 en ese lapso).
- El hilo que recarga el modelo asume una sola instancia de la API (un worker de uvicorn), que es la
  configuración del Compose.
