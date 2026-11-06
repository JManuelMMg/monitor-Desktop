#pragma once

// Certificado de la CA local que firmó el certificado TLS de Mosquitto en la
// Raspberry Pi (192.168.137.139). Es público (no es secreto) y es el mismo para
// todos los nodos. Huella SHA1: 1A6D7E5C5E5330657CDF94BA099BD379E92DF2E2
// Vence el 2 de noviembre de 2036. Si se crea una CA nueva, regenera este archivo con:
//
//   sudo /opt/monitor/deploy/pi/pki.sh export-firmware-header > ca_cert.h

#define CA_CERT_CONFIGURED 1

static const char CA_CERT[] PROGMEM = R"PEM(
-----BEGIN CERTIFICATE-----
MIIBtTCCAVqgAwIBAgIUOckg0hLxvpw5V8BbxrH/FiOx+XQwCgYIKoZIzj0EAwIw
JjEkMCIGA1UEAwwbTW9uaXRvciBNdWx0aS1Ob2RvIENBIGxvY2FsMB4XDTI2MTEw
NTE5MDgyOFoXDTM2MTEwMjE5MDgyOFowJjEkMCIGA1UEAwwbTW9uaXRvciBNdWx0
aS1Ob2RvIENBIGxvY2FsMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEN+L6nhwJ
EqMOecEtR9EdEToNCr8/h/hexO70WvGd2WDrDymWg90ffjMro893BT3DR5GaHObT
XV+yZd/SWbjlp6NmMGQwHQYDVR0OBBYEFBcLATR7wE6Y5JqQP9spxBYNVfFVMB8G
A1UdIwQYMBaAFBcLATR7wE6Y5JqQP9spxBYNVfFVMBIGA1UdEwEB/wQIMAYBAf8C
AQAwDgYDVR0PAQH/BAQDAgEGMAoGCCqGSM49BAMCA0kAMEYCIQDlLbjw27Glo4Rw
ErFLyyFi9zrPO7EQnvf58YLiBjg9NQIhALSyHdNoy1Y4jvFTcVXodvq9Qnu4PFx3
SjXnBam5G8rn
-----END CERTIFICATE-----
)PEM";
