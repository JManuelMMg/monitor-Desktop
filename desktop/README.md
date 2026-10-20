# App de escritorio Windows

> **Alternativa sin instalar nada**: el panel web también se instala como app
> (Conexión › *Usar como aplicación* en Edge/Chrome) y tiene las mismas
> funciones: ventana propia, cambio LAN ↔ VPN y pantalla sin conexión. Ver
> `docs/CONECTIVIDAD.md`.

Es una ventana nativa de Windows: usa WebView2, el motor de Edge que ya viene
con Windows 10 y 11, a través de **pywebview** (Python). No usa Electron, Node
ni NPM. Muestra el mismo panel que sirve la Raspberry Pi, con sesión
persistente y cambio automático entre la red local y la VPN.

## Ejecutar desde el código

```powershell
cd desktop
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pywebview==6.2.1
.\.venv\Scripts\python.exe monitor_desktop.py
```

## Generar el .exe

```powershell
.\build.ps1        # crea dist\MonitorMultiNodo.exe
```

## Primer uso en cada PC

1. Copia la CA de la Pi. `/etc/monitor` solo lo lee root, así que primero
   sácala a tu carpeta en la Pi y después cópiala:
   ```bash
   # En la Pi
   sudo cp /etc/monitor/tls/ca.crt ~/ca.crt && sudo chown "$USER" ~/ca.crt
   ```
   ```powershell
   # En Windows
   scp usuario@192.168.1.50:~/ca.crt .
   ```
2. Impórtala: `.\instalar_ca.ps1 -Ruta .\ca.crt`. No necesita administrador.
   Compara la huella que muestra con la de la Pi.
3. Abre la app. Si no encuentra la Pi, aparece una pantalla para escribir los
   servidores, uno por línea, empezando por la red local:
   ```
   https://192.168.1.50:8443
   https://10.8.0.1:8443
   ```
4. Fuera de casa, activa el túnel WireGuard antes de abrir la app.

La configuración queda en `%APPDATA%\MonitorMultiNodo\config.json` y la sesión
del navegador interno en `%APPDATA%\MonitorMultiNodo\webview`.
