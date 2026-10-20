#!/usr/bin/env bash
# Ejecuta la consola de administración del backend como usuario "monitor".
#   sudo ./monitor-cli.sh create-admin | reset-password USUARIO | list-users | init-db
# El archivo de entorno lo lee Python (no se hace "source": la URL de Neon
# puede contener '&' y otros caracteres especiales).
set -euo pipefail
cd /opt/monitor/backend
exec sudo -u monitor MONITOR_ENV_FILE=/etc/monitor/monitor.env /opt/monitor/venv/bin/python -m app.cli "$@"
