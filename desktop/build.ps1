# Genera dist\MonitorMultiNodo.exe (un solo archivo, sin consola).
# Uso (PowerShell, desde esta carpeta):  .\build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

$data = @("--add-data", "setup.html;.")
# Si copias aqui el ca.crt de la Pi se incluye para las comprobaciones de conexion.
if (Test-Path "ca.crt") { $data += @("--add-data", "ca.crt;.") }

.\.venv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --windowed `
    --name MonitorMultiNodo @data monitor_desktop.py

Write-Host "Listo: $PSScriptRoot\dist\MonitorMultiNodo.exe"
