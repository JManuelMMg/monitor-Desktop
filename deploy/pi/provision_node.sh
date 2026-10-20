#!/usr/bin/env bash
# Alta (o rotación de clave) y revocación de nodos por consola.
# Hace lo mismo que el botón «Agregar nodo» del panel.
#
#   sudo ./provision_node.sh A4:CF:12:B3:C4:D5 [--name "Biodigestor 1"] [--zone "Granja norte"]
#   sudo ./provision_node.sh --revoke A4:CF:12:B3:C4:D5
#
# La MAC aparece en el monitor serie al arrancar el nodo ("Nodo a4cf12b3c4d5").
# Para no teclear la WiFi en cada nodo:  sudo WIFI_SSID=... WIFI_PASS=... -E ./provision_node.sh MAC
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "ejecuta con sudo" >&2; exit 1; }

CLI=/opt/monitor/deploy/pi/monitor-cli.sh

if [[ ${1:-} == "--revoke" ]]; then
    exec "$CLI" revoke-node "${2:?Falta la MAC}"
fi

mac=${1:?Uso: provision_node.sh MAC [--name NOMBRE] [--zone ZONA]}
shift
result=$("$CLI" add-node "$mac" "$@")

ssid=${WIFI_SSID:-}
wifi_pass=${WIFI_PASS:-}
[[ -n $ssid ]] || read -rp "SSID de la WiFi del nodo: " ssid
[[ -n $wifi_pass ]] || { read -rsp "Contraseña de la WiFi: " wifi_pass; echo; }

line=$(RESULT="$result" SSID="$ssid" WPASS="$wifi_pass" python3 -c '
import json, os
r = json.loads(os.environ["RESULT"])
print(json.dumps({"cmd": "provision", "wifi_ssid": os.environ["SSID"], "wifi_pass": os.environ["WPASS"],
                  "mqtt_host": r["mqtt_host"] or "IP_DE_LA_PI", "mqtt_port": r["mqtt_port"], "mqtt_tls": True,
                  "mqtt_pass": r["password"]}, ensure_ascii=False))')
node=$(RESULT="$result" python3 -c 'import json, os; print(json.loads(os.environ["RESULT"])["mac"])')

cat <<EOF

Nodo $node registrado y con credencial MQTT activa.
Abre el monitor serie (115200 baudios, fin de línea "Nueva línea") y pega esta línea:

$line

La clave solo se muestra ahora. Si la pierdes, vuelve a ejecutar este script
(o usa «Generar clave nueva» en el panel) para rotarla.
EOF
