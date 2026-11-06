#!/usr/bin/env bash
# Cortafuegos (ufw). Desde internet solo queda abierto WireGuard (UDP 51820),
# que no responde a paquetes sin una clave válida.
#
#   sudo LAN_CIDR=192.168.1.0/24 ./firewall.sh
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "ejecuta con sudo" >&2; exit 1; }

if [[ -z ${LAN_CIDR:-} ]]; then
    iface_cidr=$(ip -o -f inet addr show scope global | awk '{print $4; exit}')
    LAN_CIDR=$(python3 -c 'import ipaddress,sys; print(ipaddress.ip_interface(sys.argv[1]).network)' "$iface_cidr")
fi
WG_CIDR=${WG_CIDR:-10.8.0.0/24}
WG_PORT=${WG_PORT:-51820}

echo "Red local: $LAN_CIDR   VPN: $WG_CIDR"
ufw default deny incoming
ufw default allow outgoing

# SSH, panel/API y MQTT-TLS solo desde la LAN.
ufw allow from "$LAN_CIDR" to any port 22 proto tcp comment 'SSH LAN'
ufw allow from "$LAN_CIDR" to any port 8443 proto tcp comment 'Panel HTTPS LAN'
ufw allow from "$LAN_CIDR" to any port 8883 proto tcp comment 'MQTT TLS nodos'

# Clientes VPN: panel y SSH (no MQTT: los ESP32 están en casa).
ufw allow from "$WG_CIDR" to any port 8443 proto tcp comment 'Panel HTTPS VPN'
ufw allow from "$WG_CIDR" to any port 22 proto tcp comment 'SSH VPN'

ufw allow "$WG_PORT"/udp comment 'WireGuard'

# Tailscale Funnel: el panel público (https://<nombre>.ts.net) llega por la
# interfaz tailscale0. Los nodos de ingreso de Funnel entregan las conexiones a
# la peerapi de tailscaled (puerto alto variable) y tailscaled las pasa a
# localhost:8443. A tailscale0 solo llega tráfico autenticado por Tailscale y ya
# filtrado por las ACL del tailnet, así que se permite completo (lo que
# recomienda Tailscale con ufw).
ufw allow in on tailscale0 comment 'Tailscale'

ufw --force enable
ufw status verbose
