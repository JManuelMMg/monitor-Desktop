# Monitor multi-nodo — ESP32 + Raspberry Pi + Windows

Sistema de monitoreo para 6 o más nodos ESP32. Cada nodo lleva un DHT11, un
MQ-4, un MH-Z19C y un AJ-SR04M. Una Raspberry Pi 4B hace de broker y servidor
local, Neon (PostgreSQL) guarda el histórico y una app de escritorio Windows
muestra el panel. No usa Node.js ni NPM en ninguna parte.

| Carpeta | Contenido |
|---|---|
| `firmware/` | Firmware C++ (Arduino IDE o PlatformIO). Usa la MAC como identidad, MQTT con TLS, reconexión automática y configuración remota. |
| `backend/` | FastAPI para la Pi: puente MQTT, usuarios con JWT y roles, API, WebSocket y panel web Jinja2. |
| `desktop/` | App Windows (pywebview + WebView2) que cambia sola entre la red local y la VPN. Opcional: el panel web también se instala como app (PWA) con las mismas funciones. |
| `deploy/` | Mosquitto (configuración y ACL), systemd, cortafuegos, PKI, WireGuard y scripts de instalación y aprovisionamiento. |
| `docs/` | `ARQUITECTURA.md` (tópicos, API, seguridad), `DESPLIEGUE_PI.md`, `CONECTIVIDAD.md`, `INTEGRACION_ML.md` (cómo conectar el modelo de ML). |

**Por dónde empezar:** [`docs/GUIA_PASO_A_PASO.md`](docs/GUIA_PASO_A_PASO.md)
explica, paso a paso y desde cero, cómo preparar la Raspberry Pi, dejar el
broker MQTT funcionando, usar el panel web y la app de escritorio, y conectar
los ESP32. Para el detalle técnico están `docs/ARQUITECTURA.md` y
`docs/DESPLIEGUE_PI.md`.

## Legado

Lo siguiente es del sistema anterior y ya no lo usa el sistema nuevo:

- `web/`: servidor HTTP de un solo nodo.
- `arduino/mgas/`: firmware HTTP.
- `test_esp32_sim.py`, `run_server.bat` y las guías `ARDUINO_SETUP.md`,
  `COMANDOS_EJECUCION.md`, `GUIA_CALIBRACION_PRECISION.md` e
  `implementation_plan.md`.
- `backend_fork/` y `arduino/nodo_mqtt/`: un diseño alternativo de otra
  sesión, que no está completo (ver `backend_fork/NOTA.md`).
