#!/usr/bin/env bash
# CA local y certificado TLS del servidor (Mosquitto :8883 y backend :8443).
#
#   sudo ./pki.sh init <IP_LAN_PI>       crea CA (si no existe) + certificado del servidor
#   sudo ./pki.sh renew-server <IP_LAN_PI>
#   sudo ./pki.sh export-firmware-header  imprime ca_cert.h para el firmware
#   sudo ./pki.sh fingerprint             huella de la CA (para verificar en Windows)
#
# Claves ECDSA P-256 (soportadas por mbedTLS en el ESP32 y por WebView2).
set -euo pipefail

PKI_DIR=${PKI_DIR:-/etc/monitor/tls}
WG_IP=${WG_IP:-10.8.0.1}
MOSQ_CERTS=/etc/mosquitto/certs

die() { echo "Error: $*" >&2; exit 1; }

make_ca() {
    if [[ -f "$PKI_DIR/ca.key" ]]; then
        echo "CA existente conservada: $PKI_DIR/ca.crt"
        return
    fi
    openssl ecparam -name prime256v1 -genkey -noout -out "$PKI_DIR/ca.key"
    openssl req -x509 -new -key "$PKI_DIR/ca.key" -sha256 -days 3650 \
        -subj "/CN=Monitor Multi-Nodo CA local" \
        -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
        -addext "keyUsage=critical,keyCertSign,cRLSign" \
        -out "$PKI_DIR/ca.crt"
    chmod 600 "$PKI_DIR/ca.key"
    echo "CA creada (válida 10 años)."
}

make_server() {
    local lan_ip=$1
    [[ $lan_ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "IP LAN inválida: $lan_ip"
    local ext
    ext=$(mktemp)
    cat > "$ext" <<EOF
basicConstraints=CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=serverAuth
subjectAltName=DNS:$(hostname).local,DNS:monitor.local,DNS:localhost,IP:127.0.0.1,IP:${lan_ip},IP:${WG_IP}
EOF
    openssl ecparam -name prime256v1 -genkey -noout -out "$PKI_DIR/server.key"
    openssl req -new -key "$PKI_DIR/server.key" -subj "/CN=monitor.local" -out "$PKI_DIR/server.csr"
    openssl x509 -req -in "$PKI_DIR/server.csr" -CA "$PKI_DIR/ca.crt" -CAkey "$PKI_DIR/ca.key" \
        -CAcreateserial -days 825 -sha256 -extfile "$ext" -out "$PKI_DIR/server.crt"
    rm -f "$ext" "$PKI_DIR/server.csr"

    # Backend (usuario monitor) y Mosquitto (usuario mosquitto) leen la clave.
    chown root:monitor "$PKI_DIR/server.key" "$PKI_DIR/server.crt" "$PKI_DIR/ca.crt" 2>/dev/null || true
    chmod 640 "$PKI_DIR/server.key"
    chmod 644 "$PKI_DIR/server.crt" "$PKI_DIR/ca.crt"
    install -d -m 750 -o mosquitto -g mosquitto "$MOSQ_CERTS"
    install -m 600 -o mosquitto -g mosquitto "$PKI_DIR/server.key" "$MOSQ_CERTS/server.key"
    install -m 644 -o mosquitto -g mosquitto "$PKI_DIR/server.crt" "$MOSQ_CERTS/server.crt"
    install -m 644 -o mosquitto -g mosquitto "$PKI_DIR/ca.crt" "$MOSQ_CERTS/ca.crt"
    echo "Certificado de servidor emitido para: $lan_ip, $WG_IP, monitor.local (825 días)."
}

fingerprint() {
    openssl x509 -in "$PKI_DIR/ca.crt" -noout -fingerprint -sha1 | sed 's/^.*=//; s/://g'
}

case ${1:-} in
    init)
        [[ $EUID -eq 0 ]] || die "ejecuta con sudo"
        install -d -m 750 -o root -g monitor "$PKI_DIR" 2>/dev/null || install -d -m 750 "$PKI_DIR"
        make_ca
        make_server "${2:?Uso: pki.sh init <IP_LAN_PI>}"
        echo "Huella SHA1 de la CA (compárala al importarla en Windows): $(fingerprint)"
        ;;
    renew-server)
        [[ $EUID -eq 0 ]] || die "ejecuta con sudo"
        make_server "${2:?Uso: pki.sh renew-server <IP_LAN_PI>}"
        systemctl restart mosquitto monitor-backend
        ;;
    export-firmware-header)
        echo "#pragma once"
        echo "// Generado por deploy/pi/pki.sh — CA pública de la Raspberry Pi."
        echo "#define CA_CERT_CONFIGURED 1"
        echo 'static const char CA_CERT[] PROGMEM = R"PEM('
        cat "$PKI_DIR/ca.crt"
        echo ')PEM";'
        ;;
    fingerprint)
        fingerprint
        ;;
    *)
        sed -n '2,8p' "$0"
        exit 1
        ;;
esac
