# Integración del modelo de ML (desarrollo independiente)

El panel principal tiene un espacio vacío reservado, `#ml-panel` en
`backend/app/templates/dashboard.html`, para las interfaces del modelo. Este
documento recoge recomendaciones para que el equipo de ML trabaje por su
cuenta y conecte su modelo al sistema sin tocar el backend de monitoreo.

## 1. Principio: el ML es un servicio aparte

- **Separación**: otro repositorio (o carpeta), su propio `venv` y su propio
  servicio systemd. Nunca dentro del proceso del backend: un fallo, una fuga
  de memoria o una actualización de librerías del modelo no debe tumbar el
  monitoreo en vivo ni Mosquitto.
- **Contratos estables**: el ML se comunica con el sistema por datos (tablas
  y tópicos con un esquema fijo), no importando código del backend.
- **El panel funciona sin ML**: si el modelo no responde, el espacio muestra
  "sin datos del modelo" y todo lo demás sigue igual.

## 2. Datos para entrenar

Los datos están en Neon, esquema `monitor`:

| Tabla | Uso |
|---|---|
| `monitor.sensor_readings` | serie temporal: `mac, ts (UTC), temp_c, hum_pct, ch4_ppm, co2_ppm, dist_cm, level_pct, rssi, uptime_s` |
| `monitor.devices` | metadatos del nodo: `name`, `zone`, `config` (offsets, alturas del reactor) |
| `monitor.command_log` | calibraciones y reinicios con fecha: puntos de cambio en la serie |

**Acceso de solo lectura.** Crea un rol para el ML; nunca uses el dueño de la
base:

```sql
CREATE ROLE ml_reader LOGIN PASSWORD '…';
GRANT USAGE ON SCHEMA monitor TO ml_reader;
GRANT SELECT ON monitor.sensor_readings, monitor.devices, monitor.command_log TO ml_reader;
-- sin acceso a monitor.users
```

**Experimentos sobre una rama de Neon.** Neon permite crear una *branch* de
la base en segundos: es una copia instantánea, sin carga sobre producción y
con un punto en el tiempo reproducible. Anota el nombre de la rama con cada
entrenamiento.

**Particularidades de estos datos:**

- **Muestreo**: se guarda 1 lectura cada `PERSIST_INTERVAL_S` (10 s por
  defecto) por nodo. Hay huecos cuando el nodo se desconecta. Remuestrea a una
  rejilla fija (por ejemplo 1 min con `date_bin`) antes de calcular
  características.
- **`NULL` = sensor sin lectura válida.** El firmware no repite el último valor
  bueno. Por ejemplo, `ch4_ppm` es `NULL` durante los 3 min de calentamiento
  del MQ-4 y mientras no está calibrado. No imputes a ciegas: el `NULL`
  también es información.
- **Cambios de escala por calibración**: un `calibrate_mq4` cambia R0 y, con
  él, la escala del CH₄. Usa las fechas de `command_log` como cortes y no
  mezcles tramos sin normalizar.
- **Offsets**: las lecturas ya llevan aplicados los offsets de
  `devices.config` (temperatura, humedad, ultrasonido).
- **Nodos deshabilitados**: no guardan lecturas en ese periodo.
- **Volumen**: unas 50 000 filas/día con 6 nodos y crece lineal con los nodos.
- **Mejora sugerida**: guardar también `mq_rs_kohm` (la resistencia cruda del
  MQ-4, que ya llega por MQTT). No depende de la calibración y es mejor
  entrada para un modelo que el ppm derivado. Es una columna más en
  `sensor_readings` y una línea en `persistence.py`.

**Validación sin fugas:**

- Divide por **tiempo** (entrenar con el pasado, validar con el futuro), nunca
  al azar.
- Si el modelo debe servir para nodos nuevos, valida también dejando fuera
  **nodos completos**.
- La zona y el tamaño del reactor (`reactor_empty_cm`) son buenas variables de
  contexto.

## 3. Cómo entregar resultados al sistema

Hay dos opciones. Empieza por la A.

### A. Por lotes, escribiendo en Neon (recomendada para empezar)

El servicio de ML lee la base cada N minutos, predice y escribe en su propia
tabla. El backend solo lee esa tabla.

```sql
CREATE TABLE monitor.ml_predictions (
    id BIGSERIAL PRIMARY KEY,
    model VARCHAR(64) NOT NULL,          -- p. ej. "ch4_forecast"
    version VARCHAR(32) NOT NULL,        -- versión del artefacto
    mac CHAR(12) REFERENCES monitor.devices(mac) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,             -- momento de la predicción (UTC)
    target_ts TIMESTAMPTZ,               -- momento predicho (si es pronóstico)
    kind VARCHAR(16) NOT NULL,           -- 'forecast' | 'anomaly' | 'class'
    value REAL,                          -- valor principal
    score REAL,                          -- confianza / puntuación de anomalía 0..1
    label VARCHAR(64),                   -- p. ej. 'acidificación', 'sensor CO₂ defectuoso'
    detail JSONB                         -- intervalos, contribución de variables, etc.
);
CREATE INDEX ON monitor.ml_predictions (mac, ts DESC);
GRANT INSERT, SELECT ON monitor.ml_predictions TO ml_writer;  -- rol aparte del lector
```

### B. En tiempo real por MQTT (para detección de anomalías al instante)

1. El servicio se suscribe a la telemetría con un usuario MQTT propio de solo
   lectura y publica en su propio espacio de tópicos. En `deploy/mosquitto/acl`:
   ```
   user ml
   topic read monitor/v1/nodes/+/telemetry
   topic write monitor/v1/ml/#
   ```
2. Publica las predicciones en `monitor/v1/ml/<modelo>/<mac>/prediction`, con
   el mismo JSON que la tabla de la opción A.
3. El backend reenvía esos mensajes por WebSocket al panel. Cambio pequeño en
   `mqtt_bridge.py`: suscribirse a `monitor/v1/ml/#`.

**Contrato del mensaje**: el mismo en A y B. Versiónalo como los tópicos
(`v1`) para cambiarlo sin romper el panel.

```json
{"model": "ch4_forecast", "version": "2026.11.03", "mac": "a4cf12b3c4d5",
 "ts": "2026-11-03T14:00:00Z", "target_ts": "2026-11-03T20:00:00Z",
 "kind": "forecast", "value": 5320, "score": 0.82, "label": null,
 "detail": {"p10": 4900, "p90": 5700}}
```

**En el panel**, cuando el modelo esté listo:

1. Un endpoint `GET /api/ml/summary` (rol viewer) que lea `ml_predictions`.
2. Un script `static/js/ml.js` que dibuje dentro de `#ml-panel`. Reutiliza
   `LineChart` y `App.sparkline`, que ya existen.

## 4. Dónde corre el modelo

- **Entrenamiento**: en tu PC o en la nube, con las librerías que quieras.
- **Inferencia en la Pi 4 (ARM64, 4–8 GB)**:
  - Usa modelos ligeros: scikit-learn, LightGBM o XGBoost, o exporta a
    **ONNX** y ejecútalo con `onnxruntime`, que tiene ruedas aarch64 por pip.
  - Evita TensorFlow o PyTorch completos en la Pi: pesan mucho y compiten por
    CPU con el backend.
- **Servicio systemd propio** con límites, para que nunca deje sin recursos a
  Mosquitto ni al backend:
  ```ini
  [Service]
  User=ml
  MemoryMax=1G
  CPUQuota=150%
  Nice=10
  ```
- **Sin Node ni NPM** también aquí: `venv` + `pip` con versiones exactas, como
  el backend.

## 5. Versionado y seguimiento

- Registra cada modelo entrenado:
  - nombre y versión;
  - rango de fechas de datos y rama de Neon;
  - métricas de validación;
  - hash del artefacto.

  Puede ser una tabla `monitor.ml_models` o un `model_card.json` junto al
  artefacto.
- Cada predicción guarda `model` + `version`, para comparar versiones en
  paralelo.
- **Deriva**: compara cada semana la distribución de las entradas por nodo con
  la de entrenamiento. Una calibración, un sensor nuevo o un cambio de
  estación la mueven.
- **Alarma de modelo caído**: si no hay predicciones recientes, el espacio del
  panel lo debe decir. No muestres datos viejos como si fueran actuales.

## 6. Ideas de modelos útiles para biodigestores

| Objetivo | Entradas | Tipo |
|---|---|---|
| Pronóstico de producción de CH₄ (horas/días) | CH₄, temperatura, nivel, historial | regresión de series temporales |
| Detección de acidificación o inhibición | relación **CO₂/CH₄** creciente, caída de CH₄ con temperatura estable | anomalía / clasificación |
| Falla de sensor frente a falla de proceso | sensor que se congela, saltos imposibles, un sensor que diverge de los demás del mismo nodo | anomalía por sensor |
| Llenado / vaciado del reactor | `level_pct`, `dist_cm` | pronóstico simple, alerta de desborde |
| Comparación entre nodos de la misma zona | todos los nodos de una zona | detección del nodo atípico |

## 7. Lista de verificación para conectar el modelo

- [ ] Rol `ml_reader` creado; entrenamiento sobre una rama de Neon.
- [ ] Contrato de predicción acordado (JSON de la sección 3).
- [ ] Tabla `monitor.ml_predictions` (opción A) o usuario MQTT `ml` + ACL (opción B).
- [ ] Servicio systemd del ML con límites de memoria y CPU.
- [ ] Endpoint `GET /api/ml/summary` y `static/js/ml.js` que dibuje en `#ml-panel`.
- [ ] Estado "modelo sin datos recientes" visible en el panel.
