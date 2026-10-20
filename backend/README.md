# Backend (Raspberry Pi)

Hecho con FastAPI, paho-mqtt (contra Mosquitto) y Neon (PostgreSQL). Tiene 7
dependencias directas, ninguna de Node. La arquitectura completa está en
`../docs/ARQUITECTURA.md` y la instalación en `../docs/DESPLIEGUE_PI.md`.

## Desarrollo en Windows

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q           # 30 pruebas, sin base ni broker
.\.venv\Scripts\python.exe tests\demo_server.py   # panel con 6 nodos simulados
```

El servidor demo queda en http://127.0.0.1:8765 (usuario `demo`, contraseña
`demo-demo-demo`). Usa una base en memoria y no toca Neon.

Para correrlo contra Neon y un Mosquitto real:

```powershell
copy .env.example .env    # completa DATABASE_URL, JWT_SECRET, MQTT_PASSWORD
.\.venv\Scripts\python.exe -m app.cli create-admin
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```
