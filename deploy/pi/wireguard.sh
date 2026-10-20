#!/usr/bin/env bash
# VPN WireGuard para entrar al panel desde fuera de casa.
#
#   sudo ./wireguard.sh init
#   sudo ./wireguard.sh add <nombre> <host_publico>   p. ej. add laptop-ana micasa.duckdns.org
#   sudo ./wireguard.sh remove <nombre>
#   sudo ./wireguard.sh list
#
# Los clientes solo enrutan por el túnel la IP de la Pi en la VPN (10.8.0.1)
# y su IP en la LAN (split tunnel): ven la Pi y nada más de la red de casa.
# Así la MISMA dirección (https://IP_LAN:8443) sirve dentro y fuera de casa,
# y la app instalada conserva su sesión. En el router hay que redirigir UDP 51820
# a la IP de la Pi. Si tu proveedor usa CGNAT (sin IP pública), mira la
# alternativa en docs/CONECTIVIDAD.md.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "ejecuta con sudo" >&2; exit 1; }

WG_DIR=/etc/wireguard
CONF=$WG_DIR/wg0.conf
CLIENTS=$WG_DIR/clients
SERVER_IP=10.8.0.1
# IP de la Pi en la LAN (la escribe install.sh en monitor.env).
LAN_IP=${LAN_IP:-$(grep -oP '^MQTT_PUBLIC_HOST=\K.*' /etc/monitor/monitor.env 2>/dev/null || true)}
PORT=${WG_PORT:-51820}
umask 077

die() { echo "Error: $*" >&2; exit 1; }

case ${1:-} in
    init)
        [[ -f $CONF ]] && die "$CONF ya existe"
        mkdir -p "$CLIENTS"
        wg genkey | tee "$WG_DIR/server.key" | wg pubkey > "$WG_DIR/server.pub"
        cat > "$CONF" <<EOF
[Interface]
Address = ${SERVER_IP}/24
ListenPort = ${PORT}
PrivateKey = $(cat "$WG_DIR/server.key")
EOF
        systemctl enable --now wg-quick@wg0
        echo "WireGuard activo en UDP $PORT. Clave pública del servidor: $(cat "$WG_DIR/server.pub")"
        ;;
    add)
        name=${2:?Uso: wireguard.sh add <nombre> <host_publico>}
        endpoint=${3:?Falta el host público (IP o DDNS)}
        [[ $name =~ ^[A-Za-z0-9_-]{1,32}$ ]] || die "nombre inválido"
        [[ -f $CLIENTS/$name.conf ]] && die "ya existe un cliente '$name'"
        last=$(grep -oE 'AllowedIPs = 10\.8\.0\.[0-9]+' "$CONF" | awk -F. '{print $4}' | sort -n | tail -1)
        octet=$(( ${last:-1} + 1 ))
        (( octet < 255 )) || die "sin direcciones libres"
        client_key=$(wg genkey)
        client_pub=$(printf '%s' "$client_key" | wg pubkey)
        psk=$(wg genpsk)
        cat >> "$CONF" <<EOF

[Peer]
# $name
PublicKey = $client_pub
PresharedKey = $psk
AllowedIPs = 10.8.0.${octet}/32
EOF
        cat > "$CLIENTS/$name.conf" <<EOF
[Interface]
PrivateKey = $client_key
Address = 10.8.0.${octet}/32

[Peer]
PublicKey = $(cat "$WG_DIR/server.pub")
PresharedKey = $psk
Endpoint = ${endpoint}:${PORT}
AllowedIPs = ${SERVER_IP}/32${LAN_IP:+, ${LAN_IP}/32}
PersistentKeepalive = 25
EOF
        wg syncconf wg0 <(wg-quick strip wg0)
        echo "Cliente '$name' = 10.8.0.${octet}. Configuración: $CLIENTS/$name.conf"
        if command -v qrencode >/dev/null; then
            echo "QR para la app WireGuard del teléfono:"
            qrencode -t ansiutf8 < "$CLIENTS/$name.conf"
        fi
        echo "En Windows: importa el .conf en la app oficial de WireGuard."
        ;;
    remove)
        name=${2:?Uso: wireguard.sh remove <nombre>}
        python3 - "$CONF" "$name" <<'PY'
import re, sys
path, name = sys.argv[1], sys.argv[2]
text = open(path).read()
blocks = re.split(r"\n(?=\[Peer\])", text)
kept = [b for b in blocks if not b.startswith("[Peer]") or f"# {name}\n" not in b]
if len(kept) == len(blocks):
    sys.exit(f"cliente '{name}' no encontrado")
open(path, "w").write("\n".join(kept).rstrip() + "\n")
PY
        rm -f "$CLIENTS/$name.conf"
        wg syncconf wg0 <(wg-quick strip wg0)
        echo "Cliente '$name' eliminado."
        ;;
    list)
        grep -A3 '^\[Peer\]' "$CONF" | grep -E '^# |AllowedIPs' | paste - - || true
        wg show wg0 latest-handshakes || true
        ;;
    *)
        sed -n '2,12p' "$0"
        exit 1
        ;;
esac
