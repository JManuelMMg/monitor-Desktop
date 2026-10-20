# Arquitectura — Monitor multi-nodo (ESP32 + Raspberry Pi + Windows)

Sin Node.js ni NPM en ninguna capa. Firmware en C++ (Arduino/PlatformIO),
broker Eclipse Mosquitto (paquete apt), backend en Python/FastAPI con `venv` y
`pip`, interfaz en plantillas Jinja2 con JavaScript propio (sin CDN), y app de
escritorio Windows en Python (pywebview + WebView2).

```
  ESP32 (6+)                      Raspberry Pi 4B                         Clientes
 ┌──────────────┐  MQTT/TLS   ┌────────────────────────────────┐
 │ DHT11 MQ-4   │  :8883      │ Mosquitto                      │
 │ MH-Z19C      ├────────────►│  :8883 TLS (LAN)  :1883 local  │
 │ AJ-SR04M     │  user=MAC   │        │                       │  HTTPS :8443   ┌──────────────┐
 └──────────────┘             │        ▼ paho-mqtt             │◄──────────────►│ App Windows  │
        ▲  config/cmd         │ FastAPI (uvicorn, 1 worker)    │   (LAN)        │ (pywebview)  │
        └─────────────────────┤  • estado en vivo (memoria)    │                └──────────────┘
                              │  • WebSocket /ws               │  WireGuard     ┌──────────────┐
                              │  • JWT + roles                 │◄──── UDP ─────►│ Laptop/móvil │
                              │  • escritura por lotes + spool │  51820         │ fuera de casa│
                              └───────────────┬────────────────┘                └──────────────┘
                                              │ TLS (saliente)
                                              ▼
                                       Neon (PostgreSQL)
```

## 1. Identidad por MAC

- Cada nodo lee su MAC WiFi STA (`esp_read_mac`) y la usa en minúsculas sin
  separadores: `a4cf12b3c4d5`.
- Esa cadena es **a la vez** el `clientId`, el **usuario MQTT** y parte de los
  tópicos. Mosquitto fuerza `clientId = usuario` (`use_username_as_clientid`)
  y la ACL con `%u` impide que un nodo publique bajo otra MAC.
- **Registro automático**: el primer mensaje de una MAC con credenciales válidas
  crea la fila en `devices` con el nombre `Nodo XXXX`. Desde el panel se le
  asigna nombre y zona.

## 2. Tópicos MQTT

Raíz: `monitor/v1/nodes/<mac>/…`. La versión `v1` permite cambiar el contrato
sin romper nodos antiguos.

| Tópico | Sentido | QoS | Retenido | Contenido |
|---|---|---|---|---|
| `<mac>/status` | nodo → Pi | 1 | sí | `{"state":"online","fw","ip","rssi","reset_reason","sensors":[…]}`. Como LWT lleva `{"state":"offline"}`. |
| `<mac>/telemetry` | nodo → Pi | 0 | no | `temp_c, hum_pct, ch4_ppm, co2_ppm, dist_cm, level_pct` (null si el sensor falla), banderas `*_ok`, `seq, up, rssi, heap` |
| `<mac>/event` | nodo → Pi | 0 | no | `{"type":"mq4_calibration","id","ok","r0_kohm"}` … |
| `<mac>/cmd` | Pi → nodo | 1 | no | `{"id":"<uuid>","cmd":"identify","args":{"seconds":15}}` |
| `<mac>/cmd/ack` | nodo → Pi | 0 | no | `{"id","cmd","ok","msg"}` |
| `<mac>/config/set` | Pi → nodo | 1 | **sí** | configuración deseada con `rev` |
| `<mac>/config/state` | nodo → Pi | 0 | sí | configuración aplicada (`rev`), o `error` si la rechazó |

Decisiones clave:

- **La zona no va en el tópico.** Mover un nodo de la cocina al patio es un
  `UPDATE` en la base: el broker, la ACL y el firmware no cambian.
- `config/set` es **retenido**: un nodo apagado recibe la última configuración
  al reconectar. El backend compara `rev` deseada contra `rev` reportada y el
  panel muestra *pendiente / aplicada / rechazada*.
- Comandos con `id` (UUID). QoS 1 puede entregar dos veces, así que el nodo
  ignora los `id` repetidos. Cada comando queda en `command_log` con quién lo
  envió y qué respondió el nodo.
- Comandos permitidos por MQTT: `ping`, `reboot`, `identify`, `calibrate_mq4`,
  `clear_mq4`, `calibrate_co2_zero`. `provision` y `factory_reset` **solo
  funcionan por USB**.

## 3. Firmware (`firmware/esp32_node`)

- Un binario único para todos los nodos. WiFi, host MQTT y clave se guardan en
  NVS con `{"cmd":"provision",…}` por el puerto serie.
- **Reconexión**:
  - WiFi con autoreconexión y reintento cada 15 s.
  - MQTT con backoff exponencial de 2 a 60 s más jitter, para que 6+ nodos no
    reintenten a la vez.
  - LWT retenido y watchdog de 30 s.
- **TLS obligatorio por defecto**. Valida contra la CA local (`ca_cert.h`) y
  nunca usa `setInsecure()`.
- **Calibración del MQ-4 no bloqueante**: 100 muestras en 20 s, intercaladas
  con el loop, así la sesión MQTT no se corta.
- **Lecturas inválidas → `null`**. No se repite el último valor bueno, porque
  eso ocultaría una falla del sensor.

## 4. Backend (`backend/app`)

| Módulo | Función |
|---|---|
| `mqtt_bridge.py` | cliente paho en su propio hilo, valida tópico, tamaño y JSON, y despacha |
| `state.py` | estado en vivo por nodo: conexión `online/stale/offline`, alarmas y normalización de telemetría |
| `persistence.py` | submuestreo (`PERSIST_INTERVAL_S`), lotes a Neon (`DB_FLUSH_INTERVAL_S`) y **spool JSONL** cuando no hay internet |
| `hub.py` | difusión WebSocket segura entre hilos |
| `db.py` | pool psycopg2 con reintento ante conexiones cerradas por Neon |
| `security.py` / `deps.py` | scrypt (stdlib), JWT HS256, roles, bloqueo por intentos y CSRF |
| `routers/` | `auth`, `users`, `devices`, `live` (WebSocket) y `pages` (HTML) |

**Tablas** (se crean solas, en el esquema PostgreSQL `monitor`, configurable con `DB_SCHEMA`): `users`, `devices`, `sensor_readings` (con índice
único `(mac, ts)`, así reenviar el spool no duplica filas) y `command_log`. La
tabla `readings` del sistema anterior **no se toca**.

### API

Todas las rutas aceptan `Authorization: Bearer <jwt>` o la cookie de sesión.

| Método | Ruta | Rol mínimo |
|---|---|---|
| POST | `/api/auth/login`, `/api/auth/logout` | — |
| GET | `/api/auth/me` · POST `/api/auth/password` | viewer |
| GET | `/api/devices`, `/api/devices/{mac}`, `/api/zones` | viewer |
| GET | `/api/devices/{mac}/history?hours=&points=` · `/export.csv` · `/commands` | viewer |
| PATCH | `/api/devices/{mac}` (nombre, zona, descripción, umbrales) | operator |
| PATCH | `/api/devices/{mac}` con `enabled` | admin |
| PUT | `/api/devices/{mac}/config` | operator |
| POST | `/api/devices/{mac}/commands` | operator |
| DELETE | `/api/devices/{mac}` | admin |
| POST | `/api/devices` (alta de nodo + credencial) | admin |
| POST/DELETE | `/api/devices/{mac}/credentials` (rotar / revocar) | admin |
| GET/POST/PATCH/DELETE | `/api/users…` | admin |
| WS | `/ws` (cookie, o primer mensaje `{"type":"auth","token":…}`) | viewer |
| GET | `/healthz` | — |

### Roles

- **viewer**: ve todo.
- **operator**: además renombra y reubica nodos, cambia umbrales y
  configuración, y envía comandos.
- **admin**: además gestiona usuarios y habilita, deshabilita o elimina nodos.

Al cambiar la contraseña, el rol o el estado de un usuario sube su
`token_version` y sus tokens anteriores dejan de valer. Siempre queda al menos
un admin activo.

## 5. Seguridad, resumen

- **Cortafuegos**: desde internet solo está abierto WireGuard (UDP 51820). El
  panel (8443) y MQTT-TLS (8883) solo se aceptan desde la LAN y la VPN.
  MQTT sin TLS (1883) escucha solo en `127.0.0.1`.
- **Credenciales MQTT por nodo**, generadas desde el panel (*Agregar nodo*).
  En la base solo queda el hash PBKDF2-SHA512 (formato `$7$` de Mosquitto); el
  backend regenera el `password_file` y systemd recarga Mosquitto. Se pueden
  rotar o revocar desde el panel.
- **Sesiones web**:
  - Cookie `HttpOnly` + `SameSite=Strict` + `Secure`.
  - Cabecera `X-CSRF` obligatoria en métodos que modifican.
  - CSP `default-src 'self'` sin scripts inline.
  - Swagger desactivado en producción.
- **Contraseñas**: scrypt (N=2¹⁵) y bloqueo de 15 min tras 5 fallos por IP y
  usuario.
- **Servicio en la Pi**: systemd con `ProtectSystem=strict`, sin
  capacidades, como usuario `monitor`.
- **Dependencias**: 7 paquetes Python directos con versiones exactas. Cero
  paquetes de Node.

## 6. Escalabilidad

- **Más nodos**: aprovisionar y listo. No hay nada que recompilar ni
  reconfigurar en el backend.
- **Sensores nuevos**: se añade el campo al firmware (`publishTelemetry`), a
  `TELEMETRY_RANGES` en `state.py` y a la columna en `sensor_readings`.
- **Carga**: con 6 nodos cada 5 s y guardado cada 10 s son unas 50 000
  filas/día. La retención (`RETENTION_DAYS`) purga cada 24 h y el histórico se
  agrega con `date_bin` para no mandar miles de puntos al navegador.
- **Más de unos cientos de nodos**: habría que mover el estado en vivo a un
  proceso dedicado y usar varias réplicas de la API. La separación
  bridge/estado/API ya lo permite.
