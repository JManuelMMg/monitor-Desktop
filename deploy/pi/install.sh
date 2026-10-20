#!/usr/bin/env bash
# Instalación en Raspberry Pi OS (Bookworm, 64 bits) — sin Node.js ni NPM.
#
#   git clone / copia del proyecto en la Pi, luego:
#   sudo LAN_IP=192.168.1.50 ./deploy/pi/install.sh
#
# Usa una IP fija para la Pi (reserva DHCP en el router): los ESP32 se
# conectan a esa IP y el certificado TLS la incluye.
# Se puede volver a ejecutar para actualizar el código: conserva claves,
# certificados, contraseñas y /etc/monitor/monitor.env.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "ejecuta con sudo" >&2; exit 1; }

REPO_DIR=$(cd "$(dirname "$0")/../.." && pwd)
LAN_IP=${LAN_IP:-$(hostname -I | awk '{print $1}')}
APP_DIR=/opt/monitor
ETC_DIR=/etc/monitor
DATA_DIR=/var/lib/monitor
MQTT_DIR=/var/lib/monitor-mqtt
ENV_FILE=$ETC_DIR/monitor.env

echo "==> Proyecto: $REPO_DIR   IP LAN de la Pi: $LAN_IP"
read -rp "¿Es correcta la IP? (s/N) " ok
[[ $ok == "s" ]] || { echo "Ejecuta de nuevo con LAN_IP=..."; exit 1; }

echo "==> Paquetes del sistema (apt)"
apt-get update
apt-get install -y --no-install-recommends \
    mosquitto mosquitto-clients python3-venv python3-pip openssl ufw wireguard-tools qrencode rsync

echo "==> Usuario de servicio y directorios"
id monitor >/dev/null 2>&1 || useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin monitor
install -d -m 755 -o root -g root "$APP_DIR"
install -d -m 750 -o root -g monitor "$ETC_DIR"
install -d -m 750 -o monitor -g monitor "$DATA_DIR"
# Credenciales MQTT: las escribe el backend (usuario monitor) y las lee
# Mosquitto (grupo mosquitto). setgid: los archivos heredan el grupo.
install -d -m 2750 -o monitor -g mosquitto "$MQTT_DIR"

echo "==> Código del backend"
rsync -a --delete --exclude '.venv' --exclude '__pycache__' --exclude 'tests' --exclude '.env' \
    "$REPO_DIR/backend/" "$APP_DIR/backend/"
rsync -a --delete "$REPO_DIR/deploy/" "$APP_DIR/deploy/"
chmod +x "$APP_DIR"/deploy/pi/*.sh
chown -R root:root "$APP_DIR/backend" "$APP_DIR/deploy"

echo "==> Entorno virtual de Python (solo pip)"
[[ -x $APP_DIR/venv/bin/python ]] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install --no-cache-dir -r "$APP_DIR/backend/requirements.txt"

echo "==> Certificados TLS"
"$APP_DIR/deploy/pi/pki.sh" init "$LAN_IP"

echo "==> Mosquitto"
install -m 644 "$APP_DIR/deploy/mosquitto/monitor.conf" /etc/mosquitto/conf.d/monitor.conf
install -m 640 -o root -g mosquitto "$APP_DIR/deploy/mosquitto/acl" /etc/mosquitto/acl

if [[ ! -f $ENV_FILE ]]; then
    mqtt_pass=$(openssl rand -hex 24)

    echo "Pega la cadena de conexión de Neon (postgresql://...?sslmode=require)."
    read -rsp "DATABASE_URL: " database_url; echo
    [[ $database_url == postgres* ]] || { echo "Cadena inválida" >&2; exit 1; }

    umask 027
    cat > "$ENV_FILE" <<EOF
DATABASE_URL=$database_url
JWT_SECRET=$(openssl rand -hex 32)
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_USERNAME=backend
MQTT_PASSWORD=$mqtt_pass
SPOOL_DIR=$DATA_DIR
PERSIST_INTERVAL_S=10
DB_FLUSH_INTERVAL_S=15
RETENTION_DAYS=180
COOKIE_SECURE=true
MQTT_PASSWD_FILE=$MQTT_DIR/passwd
MQTT_PUBLIC_HOST=$LAN_IP
MQTT_PUBLIC_PORT=8883
PUBLIC_URLS=https://$LAN_IP:8443,https://10.8.0.1:8443
EOF
    chown root:monitor "$ENV_FILE"
    chmod 640 "$ENV_FILE"
    echo "Configuración creada en $ENV_FILE"
else
    echo "Se conserva $ENV_FILE"
    # Actualizaciones desde versiones anteriores: añade lo que falte.
    grep -q '^MQTT_PASSWD_FILE=' "$ENV_FILE" || echo "MQTT_PASSWD_FILE=$MQTT_DIR/passwd" >> "$ENV_FILE"
    grep -q '^MQTT_PUBLIC_HOST=' "$ENV_FILE" || echo "MQTT_PUBLIC_HOST=$LAN_IP" >> "$ENV_FILE"
    grep -q '^MQTT_PUBLIC_PORT=' "$ENV_FILE" || echo "MQTT_PUBLIC_PORT=8883" >> "$ENV_FILE"
    grep -q '^PUBLIC_URLS=' "$ENV_FILE" || echo "PUBLIC_URLS=https://$LAN_IP:8443,https://10.8.0.1:8443" >> "$ENV_FILE"
fi

echo "==> Base de datos y credenciales MQTT"
"$APP_DIR/deploy/pi/monitor-cli.sh" init-db
# Genera el password_file (usuario backend + nodos registrados) antes de
# arrancar Mosquitto, que no inicia si el archivo no existe.
"$APP_DIR/deploy/pi/monitor-cli.sh" mqtt-sync

systemctl enable mosquitto
systemctl restart mosquitto

echo "==> Servicios"
install -m 644 "$APP_DIR/deploy/systemd/monitor-backend.service" /etc/systemd/system/monitor-backend.service
install -m 644 "$APP_DIR/deploy/systemd/mosquitto-monitor-reload.path" /etc/systemd/system/mosquitto-monitor-reload.path
install -m 644 "$APP_DIR/deploy/systemd/mosquitto-monitor-reload.service" /etc/systemd/system/mosquitto-monitor-reload.service
systemctl daemon-reload
systemctl enable --now mosquitto-monitor-reload.path
systemctl enable monitor-backend
systemctl restart monitor-backend

echo "==> Cortafuegos"
"$APP_DIR/deploy/pi/firewall.sh"

cat <<EOF

Instalación completa.

Siguientes pasos:
  1. Crear el primer administrador:
       sudo $APP_DIR/deploy/pi/monitor-cli.sh create-admin
  2. Firmware: genera la cabecera de la CA y compila una vez:
       sudo $APP_DIR/deploy/pi/pki.sh export-firmware-header > ca_cert.h
  3. Por cada ESP32:   en el panel, botón «Agregar nodo» (o provision_node.sh <MAC> por consola)
  4. Acceso remoto:    sudo $APP_DIR/deploy/pi/wireguard.sh init
                       sudo $APP_DIR/deploy/pi/wireguard.sh add <equipo> <tu-ddns>
  5. Panel: https://$LAN_IP:8443  (importa $ETC_DIR/tls/ca.crt en cada equipo)
     Desde ahí se puede instalar como app (Conexión › Usar como aplicación).
     Huella de la CA: $("$APP_DIR/deploy/pi/pki.sh" fingerprint)
EOF
