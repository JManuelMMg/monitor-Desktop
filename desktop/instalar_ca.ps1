# Importa la CA local de la Raspberry Pi en el almacen "Raiz de confianza"
# del USUARIO actual (no requiere administrador). Asi WebView2 acepta el
# certificado HTTPS de la Pi sin advertencias.
#
# Uso:  .\instalar_ca.ps1 -Ruta .\ca.crt
# Copia ca.crt desde la Pi. /etc/monitor solo lo lee root, asi que primero
# en la Pi:      sudo cp /etc/monitor/tls/ca.crt ~/ca.crt && sudo chown $USER ~/ca.crt
# y en Windows:  scp usuario@IP_PI:~/ca.crt .
param([Parameter(Mandatory = $true)][string]$Ruta)
$ErrorActionPreference = "Stop"

$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 (Resolve-Path $Ruta).Path
Write-Host "Certificado: $($cert.Subject)"
Write-Host "Huella SHA1: $($cert.Thumbprint)"
Write-Host "Compara la huella con la que mostro pki.sh en la Pi antes de continuar."
$respuesta = Read-Host "Importar? (s/N)"
if ($respuesta -ne "s") { Write-Host "Cancelado."; exit 1 }

Import-Certificate -FilePath (Resolve-Path $Ruta).Path -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
Write-Host "CA importada en CurrentUser\Root."
