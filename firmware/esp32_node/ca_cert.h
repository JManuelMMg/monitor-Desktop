#pragma once

// Certificado de la CA local que firmó el certificado TLS de Mosquitto en la
// Raspberry Pi. Es público (no es secreto) y es el mismo para todos los
// nodos. Genéralo en la Pi con:
//
//   sudo /opt/monitor/deploy/pi/pki.sh export-firmware-header > ca_cert.h
//
// y reemplaza este archivo. Mientras CA_CERT_CONFIGURED sea 0 el nodo se
// niega a conectarse por TLS (nunca usa setInsecure()).

#define CA_CERT_CONFIGURED 0

static const char CA_CERT[] PROGMEM = R"PEM(
-----BEGIN CERTIFICATE-----
REEMPLAZAR_CON_EL_CONTENIDO_DE_ca.crt
-----END CERTIFICATE-----
)PEM";
