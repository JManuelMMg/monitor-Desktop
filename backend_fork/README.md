# Backend Raspberry Pi

FastAPI + MQTT (Mosquitto) + Neon. Reemplaza al servidor de `../web` para el sistema multi-nodo.

## Instalación en la Pi
```bash
sudo apt install mosquitto mosquitto-clients python3-venv
sudo mkdir -p /opt/monitor && sudo cp -r backend /opt/monitor/ && cd /opt/monitor/backend
python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env   # completa DATABASE_URL, JWT_SECRET, ADMIN_PASSWORD, MQTT_PASSWORD
sudo cp deploy/mosquitto.conf /etc/mosquitto/conf.d/monitor.conf
sudo cp deploy/acl.example /etc/mosquitto/acl
sudo cp deploy/monitor-api.service /etc/systemd/system/ && sudo systemctl enable --now monitor-api
```
Usuarios MQTT: `sudo mosquitto_passwd -c /etc/mosquitto/passwd backend` y uno por nodo
(usuario = MAC de 12 hex en minúsculas, la misma clave que se pone en el portal del ESP32).
Certificados: CA propia + certificado del servidor con la IP/nombre de la Pi.

## Flujo
1. El nodo publica `monitor/v1/<mac>/meta` → aparece como `pending` en `GET /devices`.
2. Un admin hace `PATCH /devices/<mac>` con `name`, `zone`, `config` → pasa a `active`
   y la config se publica retenida; el nodo la aplica sin reflashear.
3. Telemetría: WebSocket `/ws?token=<access>`; histórico: `/history`; CSV: `/export`.

## API (JWT Bearer; roles viewer < operator < admin)
| Método | Ruta | Rol |
|---|---|---|
| POST | /auth/login, /auth/refresh | — |
| GET | /auth/me, /devices, /devices/{id}, /live, /history, /events, /export | viewer |
| POST | /devices/{id}/cmd | operator |
| PATCH/DELETE | /devices/{id} | admin |
| GET/POST/PATCH/DELETE | /users | admin |
| GET | /health | — |
Documentación interactiva en `/docs`.
