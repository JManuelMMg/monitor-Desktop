# Guía paso a paso: Raspberry Pi, broker MQTT, panel web y app de escritorio

Esta guía explica cómo dejar funcionando todo el sistema desde cero. Sigue el
orden de las partes: cada una depende de la anterior.

> **Convenciones de la guía**
> - `192.168.1.50` es la IP de ejemplo de la Raspberry Pi. Cámbiala por la tuya.
> - `usuario` es el usuario que creas en la Raspberry Pi. Cámbialo por el tuyo.
> - Los bloques `bash` se escriben **en la Raspberry Pi** (por SSH).
> - Los bloques `powershell` se escriben **en tu PC con Windows**.
> - ✅ marca cómo comprobar que un paso salió bien.

---

## Índice

1. [Cómo funciona el sistema](#1-cómo-funciona-el-sistema)
2. [Lo que necesitas](#2-lo-que-necesitas)
3. [Parte A. Preparar la Raspberry Pi](#parte-a-preparar-la-raspberry-pi)
4. [Parte B. Instalar el servidor (broker + backend + panel)](#parte-b-instalar-el-servidor)
5. [Parte C. El broker MQTT funcionando a la perfección](#parte-c-el-broker-mqtt-funcionando-a-la-perfección)
6. [Parte D. El panel web](#parte-d-el-panel-web)
7. [Parte E. La app de escritorio (Windows)](#parte-e-la-app-de-escritorio-windows)
8. [Parte F. Conectar los ESP32](#parte-f-conectar-los-esp32)
9. [Parte G. Entrar desde fuera de casa (VPN)](#parte-g-entrar-desde-fuera-de-casa-vpn)
10. [Parte H. Probar en tu PC sin Raspberry Pi](#parte-h-probar-en-tu-pc-sin-raspberry-pi)
11. [Mantenimiento](#mantenimiento)
12. [Solución de problemas](#solución-de-problemas)

---

## 1. Cómo funciona el sistema

```
  ESP32 (sensores)                  Raspberry Pi 4B                         Tus equipos
 ┌──────────────┐  MQTT con TLS   ┌──────────────────────────────┐  HTTPS   ┌──────────────────┐
 │ MQ-4, CO₂,   │ ──────────────► │ Mosquitto (broker)  :8883    │ ◄──────► │ Navegador (web)  │
 │ DHT11, nivel │   puerto 8883   │        │ (local :1883)       │  :8443   │ App de escritorio│
 └──────────────┘                 │        ▼                     │          │ Celular (PWA)    │
       (6 o más)                  │ Backend FastAPI + panel web  │          └──────────────────┘
                                  │        │                     │
                                  └────────┼─────────────────────┘
                                           ▼  (internet)
                                    Neon (PostgreSQL)
                                    guarda el histórico
```

- **Broker (Mosquitto)**: es el «cartero». Los ESP32 le entregan sus lecturas
  y él se las pasa al backend. También lleva los comandos del panel a los
  nodos.
- **Backend (FastAPI)**: recibe las lecturas, las guarda en Neon, maneja
  usuarios y sirve el panel web.
- **Panel web**: lo que ves en el navegador. La **app de escritorio** muestra
  ese mismo panel dentro de una ventana de Windows.
- **Neon**: la base de datos en la nube. Si se cae internet, el panel sigue
  mostrando datos en vivo y las lecturas se suben a Neon cuando vuelve la
  conexión.

---

## 2. Lo que necesitas

**Hardware**
- Raspberry Pi 4B con fuente oficial y microSD de 16 GB o más (clase A1).
- Cable de red (recomendado) o WiFi para la Pi.
- PC con Windows 10 u 11.
- Los ESP32 con sus sensores.

**Cuentas y datos**
- La **cadena de conexión de Neon**. Está en el panel de Neon, en *Connect*.
  Tiene esta forma:
  `postgresql://usuario:clave@ep-xxxx.neon.tech/neondb?sslmode=require`
- El nombre y la contraseña de tu red WiFi (para los ESP32).

**Software en tu PC**
- [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
- Python 3.11 o superior (solo para la app de escritorio y las pruebas).
- Arduino IDE o PlatformIO (para el firmware de los ESP32).

---

## Parte A. Preparar la Raspberry Pi

### A1. Grabar el sistema operativo

1. Abre **Raspberry Pi Imager**.
2. Elige *Raspberry Pi 4* → **Raspberry Pi OS Lite (64-bit)** (Bookworm) →
   tu microSD.
3. En **Editar ajustes** (el engrane):
   - Nombre de equipo: `monitor` (así podrás usar `monitor.local`).
   - Usuario y contraseña: los que quieras (en esta guía, `usuario`).
   - WiFi: solo si no usarás cable.
   - Pestaña *Servicios*: activa **SSH** con contraseña.
4. Graba, pon la microSD en la Pi y enciéndela.

### A2. Darle una IP fija

Los ESP32 se conectan a la Pi por su IP, así que **no debe cambiar**.

1. Entra a la configuración de tu router (normalmente `192.168.1.1`).
2. Busca *DHCP* → *Reserva de direcciones* (o *IP estática por MAC*).
3. Reserva una IP para la Pi, por ejemplo `192.168.1.50`.
4. Reinicia la Pi.

✅ Desde tu PC:

```powershell
ping 192.168.1.50
```

Debe responder.

### A3. Entrar por SSH

```powershell
ssh usuario@192.168.1.50
```

La primera vez escribe `yes` y luego tu contraseña. A partir de aquí, los
bloques `bash` se escriben en esta ventana.

### A4. Actualizar el sistema

```bash
sudo apt update && sudo apt full-upgrade -y && sudo reboot
```

Vuelve a entrar por SSH después del reinicio.

### A5. Copiar el proyecto a la Pi

**Opción 1 (recomendada): desde GitHub**

```bash
sudo apt install -y git
git clone https://github.com/JManuelMMg/monitor-Desktop.git ~/monitor
```

Si el repositorio es privado, GitHub te pedirá usuario y un *token* personal
en lugar de la contraseña.

**Opción 2: copiar desde tu PC**

```powershell
scp -r "C:\Users\jmedi\Documents\proyectos\monitor Desktop\backend" "C:\Users\jmedi\Documents\proyectos\monitor Desktop\deploy" "C:\Users\jmedi\Documents\proyectos\monitor Desktop\firmware" usuario@192.168.1.50:~/monitor/
```

Antes, crea la carpeta en la Pi con `mkdir -p ~/monitor`. Solo hacen falta
`backend`, `deploy` y `firmware`. No copies las carpetas `.venv` ni `venv`
de Windows: no sirven en la Pi.

---

## Parte B. Instalar el servidor

Un solo script instala y configura el broker, el backend, los certificados y
el cortafuegos.

### B1. Ejecutar el instalador

```bash
cd ~/monitor
sudo LAN_IP=192.168.1.50 ./deploy/pi/install.sh
```

El script te hará dos preguntas:

1. `¿Es correcta la IP? (s/N)` → escribe `s` si es la IP fija de la Pi.
2. `DATABASE_URL:` → pega la cadena de conexión de Neon. **No se ve al
   escribirla**; es normal. Pulsa Enter.

Tarda varios minutos. Esto es lo que hace:

| Paso | Qué hace |
|---|---|
| Paquetes | Instala Mosquitto, Python, el cortafuegos (ufw) y WireGuard. |
| Usuario `monitor` | Crea un usuario de sistema sin acceso a consola para correr el backend. |
| Código | Copia el backend a `/opt/monitor` y crea su entorno de Python. |
| Certificados | Crea una autoridad certificadora (CA) propia y el certificado TLS de la Pi. |
| Mosquitto | Lo configura con TLS en el puerto 8883 y permisos por nodo. |
| Configuración | Guarda la URL de Neon y genera las claves secretas en `/etc/monitor/monitor.env`. |
| Base de datos | Crea las tablas en Neon (esquema `monitor`). |
| Servicios | Activa el backend para que arranque solo al encender la Pi. |
| Cortafuegos | Deja abiertos solo los puertos necesarios, y solo para tu red local. |

Al final muestra **la huella de la CA**. Anótala: la vas a comparar al
instalar el certificado en Windows.

> El instalador se puede volver a ejecutar sin miedo: conserva claves,
> certificados, usuarios y configuración. Así se actualiza el sistema (ver
> [Mantenimiento](#mantenimiento)).

### B2. Crear el primer administrador

```bash
sudo /opt/monitor/deploy/pi/monitor-cli.sh create-admin
```

Escribe un nombre de usuario y una contraseña de **al menos 10 caracteres**
(dos veces). Los demás usuarios se crean después desde el panel.

### B3. Comprobar que todo arrancó

```bash
systemctl is-active mosquitto monitor-backend mosquitto-monitor-reload.path
curl -sk https://localhost:8443/healthz
```

✅ Debe salir `active` tres veces y luego:

```json
{"ok":true,"service":"monitor-multinodo","mqtt":true,"db":true}
```

- `"mqtt":true` → el backend está conectado al broker.
- `"db":true` → el backend puede escribir en Neon.

Si alguno sale en `false`, ve a [Solución de problemas](#solución-de-problemas).

---

## Parte C. El broker MQTT funcionando a la perfección

El instalador ya dejó Mosquitto configurado. En esta parte entiendes cómo
quedó y verificas punto por punto que funcione bien.

### C1. Cómo quedó configurado

El archivo es `/etc/mosquitto/conf.d/monitor.conf` (copia de
`deploy/mosquitto/monitor.conf`).

| Línea | Para qué sirve |
|---|---|
| `allow_anonymous false` | Nadie entra sin usuario y contraseña. |
| `password_file /var/lib/monitor-mqtt/passwd` | Lista de usuarios. **La escribe el backend**; no la edites a mano. |
| `acl_file /etc/mosquitto/acl` | Qué tópicos puede leer o escribir cada usuario. |
| `use_username_as_clientid true` | Cada nodo usa su MAC como identidad; nadie puede hacerse pasar por otro. |
| `listener 1883 127.0.0.1` | Puerto sin cifrar **solo dentro de la Pi**, para el backend. |
| `listener 8883` + `certfile`/`keyfile` | Puerto con TLS para los ESP32 en la red local. |
| `tls_version tlsv1.2` | Versión de TLS que entiende el ESP32. |
| `max_packet_size 8192` | Rechaza mensajes demasiado grandes. |
| `persistent_client_expiration 7d` | Olvida las sesiones de nodos que lleven 7 días sin conectarse. |

**Usuarios del broker**

- `backend`: el propio servidor. Su clave está en `/etc/monitor/monitor.env`
  (`MQTT_PASSWORD`). Puede leer y escribir todo `monitor/v1/#`.
- Un usuario por nodo, cuyo nombre es la **MAC** del ESP32 (12 caracteres,
  por ejemplo `a4cf12b3c4d5`). Se crea con *Agregar nodo* en el panel.

**Permisos de cada nodo** (`/etc/mosquitto/acl`): un nodo solo puede usar los
tópicos que llevan su propia MAC.

| Tópico | El nodo… | Contenido |
|---|---|---|
| `monitor/v1/nodes/<mac>/status` | escribe | en línea / desconectado |
| `monitor/v1/nodes/<mac>/telemetry` | escribe | lecturas de los sensores |
| `monitor/v1/nodes/<mac>/event` | escribe | alarmas y avisos |
| `monitor/v1/nodes/<mac>/cmd` | lee | comandos que manda el panel |
| `monitor/v1/nodes/<mac>/cmd/ack` | escribe | respuesta a cada comando |
| `monitor/v1/nodes/<mac>/config/set` | lee | configuración que manda el panel |
| `monitor/v1/nodes/<mac>/config/state` | escribe | configuración que aplicó el nodo |

**Recarga automática.** Cuando agregas, rotas o revocas un nodo, el backend
reescribe el archivo de claves y la unidad `mosquitto-monitor-reload.path`
recarga Mosquitto en ese momento. No hay que reiniciar nada a mano.

### C2. Lista de verificación

Haz estas pruebas una vez después de instalar. Si todas pasan, el broker está
bien.

**1. Mosquitto está corriendo**

```bash
systemctl status mosquitto --no-pager
```

✅ `Active: active (running)`.

**2. Escucha en los puertos correctos**

```bash
sudo ss -tlnp | grep mosquitto
```

✅ Debe aparecer `127.0.0.1:1883` y `0.0.0.0:8883` (y `[::]:8883`). El 1883
**nunca** debe aparecer como `0.0.0.0:1883`.

**3. Rechaza a quien no tiene usuario**

```bash
mosquitto_sub -h 127.0.0.1 -t '#' -C 1 -W 3
```

✅ `Connection error: Connection Refused: not authorised.`

**4. El usuario `backend` entra y ve los mensajes**

Guarda la clave en una variable (solo vive en esta sesión de SSH):

```bash
MQTT_PASS=$(sudo grep '^MQTT_PASSWORD=' /etc/monitor/monitor.env | cut -d= -f2)
mosquitto_sub -h 127.0.0.1 -u backend -P "$MQTT_PASS" -t 'monitor/v1/#' -v
```

Déjalo abierto. En **otra** ventana de SSH, publica un mensaje de prueba:

```bash
MQTT_PASS=$(sudo grep '^MQTT_PASSWORD=' /etc/monitor/monitor.env | cut -d= -f2)
mosquitto_pub -h 127.0.0.1 -u backend -P "$MQTT_PASS" -t 'monitor/v1/prueba' -m 'hola'
```

✅ En la primera ventana aparece `monitor/v1/prueba hola`. Cuando haya nodos
conectados, ahí mismo verás sus lecturas. Sal con `Ctrl+C`.

**5. El certificado TLS es válido para la IP de la Pi**

```bash
sudo openssl s_client -connect 192.168.1.50:8883 -CAfile /etc/monitor/tls/ca.crt \
    -verify_ip 192.168.1.50 </dev/null 2>/dev/null | grep "Verify return code"
```

✅ `Verify return code: 0 (ok)`. Si sale otro código, la IP del certificado no
coincide (ver «Cambió la IP de la Pi» en [Solución de problemas](#solución-de-problemas)).

**6. TLS + usuario funcionan juntos** (es exactamente lo que hace un ESP32)

```bash
sudo mosquitto_sub -h 192.168.1.50 -p 8883 --cafile /etc/monitor/tls/ca.crt \
    -u backend -P "$MQTT_PASS" -t 'monitor/v1/#' -v -W 5
```

✅ No muestra errores (se cierra solo a los 5 s si no hay mensajes).

**7. El archivo de claves existe y tiene los permisos correctos**

```bash
sudo ls -l /var/lib/monitor-mqtt/passwd
sudo wc -l /var/lib/monitor-mqtt/passwd
```

✅ `-rw-r----- 1 monitor mosquitto …`. El número de líneas es 1 (el backend)
más una por cada nodo activo.

**8. La recarga automática está activa**

```bash
systemctl is-active mosquitto-monitor-reload.path
```

✅ `active`.

**9. El cortafuegos deja pasar a los ESP32**

```bash
sudo ufw status
```

✅ Aparece `8883/tcp  ALLOW  192.168.1.0/24` (tu red local).

### C3. Ver lo que pasa en el broker

| Para… | Comando |
|---|---|
| Ver el log de Mosquitto en vivo | `sudo tail -f /var/log/mosquitto/mosquitto.log` |
| Ver todos los mensajes | `mosquitto_sub -h 127.0.0.1 -u backend -P "$MQTT_PASS" -t 'monitor/v1/#' -v` |
| Ver solo quién se conecta o desconecta | `mosquitto_sub -h 127.0.0.1 -u backend -P "$MQTT_PASS" -t 'monitor/v1/nodes/+/status' -v` |
| Ver un solo nodo | `mosquitto_sub -h 127.0.0.1 -u backend -P "$MQTT_PASS" -t 'monitor/v1/nodes/a4cf12b3c4d5/#' -v` |
| Reiniciar el broker | `sudo systemctl restart mosquitto` |
| Recargar claves y ACL sin cortar conexiones | `sudo systemctl reload mosquitto` |
| Regenerar el archivo de claves desde la base de datos | `sudo /opt/monitor/deploy/pi/monitor-cli.sh mqtt-sync` |

En el log, una conexión correcta de un nodo se ve así:

```
New client connected from 192.168.1.61:52344 as a4cf12b3c4d5 (p2, c1, k30, u'a4cf12b3c4d5').
```

### C4. Reglas para que siga funcionando bien

- **No edites** `/var/lib/monitor-mqtt/passwd` a mano ni uses
  `mosquitto_passwd`: el backend lo reescribe desde la base de datos y tus
  cambios se perderían. Usa el panel o `provision_node.sh`.
- **No abras el puerto 1883** al exterior ni cambies `listener 1883 127.0.0.1`.
- **No borres** `/etc/monitor/tls/ca.key`: si la pierdes, tendrías que
  recompilar el firmware de todos los ESP32.
- Si cambias algo en `deploy/mosquitto/`, vuelve a ejecutar `install.sh` para
  que se copie a `/etc/mosquitto/`.

---

## Parte D. El panel web

### D1. Instalar el certificado de la Pi en cada equipo

La Pi usa un certificado propio. Sin este paso, el navegador mostrará «La
conexión no es privada». Se hace **una sola vez por equipo**.

**1. Saca el certificado a tu carpeta de usuario en la Pi** (la carpeta
original solo la puede leer root):

```bash
sudo cp /etc/monitor/tls/ca.crt ~/ca.crt && sudo chown "$USER" ~/ca.crt
sudo /opt/monitor/deploy/pi/pki.sh fingerprint
```

Anota la huella que imprime el segundo comando.

**2. Cópialo a tu PC**

```powershell
cd "C:\Users\jmedi\Documents\proyectos\monitor Desktop\desktop"
scp usuario@192.168.1.50:~/ca.crt .
```

**3. Instálalo según el equipo**

- **Windows** (sirve para Edge, Chrome y la app de escritorio):

  ```powershell
  powershell -ExecutionPolicy Bypass -File .\instalar_ca.ps1 -Ruta .\ca.crt
  ```

  Compara la huella que muestra con la que anotaste; si coinciden, escribe
  `s`. No necesita permisos de administrador.
- **Firefox**: usa su propio almacén. En `about:preferences#privacy` →
  *Certificados* → *Ver certificados* → *Autoridades* → *Importar* →
  `ca.crt` → marca «Confiar en esta CA para identificar sitios web».
- **Android**: copia `ca.crt` al teléfono → *Ajustes* → *Seguridad* →
  *Cifrado y credenciales* → *Instalar un certificado* → *Certificado de CA*.
- **iPhone / iPad**: envíate el archivo (correo o AirDrop) y ábrelo →
  *Ajustes* → *Perfil descargado* → *Instalar*. Después ve a *Ajustes* →
  *General* → *Información* → *Ajustes de confianza de certificados* y activa
  la confianza para «Monitor Multi-Nodo CA local».

### D2. Entrar al panel

1. Abre `https://192.168.1.50:8443` (o `https://monitor.local:8443` si
   nombraste la Pi `monitor`).
2. Inicia sesión con el administrador que creaste en B2.

✅ Ves el **Panel general** con la guía de primeros pasos.

### D3. Qué hay en cada sección

| Sección | Para qué sirve |
|---|---|
| **Panel general** | Tarjetas en vivo de cada nodo, alarmas y botón *Agregar nodo*. Al tocar un nodo ves sus gráficas, histórico, comandos y configuración. |
| **Administración** | Usuarios, alta y retiro de nodos y estado del sistema. Solo para administradores. |
| **Conexión** | Direcciones del servidor (red local y VPN), cambio automático entre ellas e instalación como app. |
| **Mi cuenta** | Cambiar tu contraseña. |

### D4. Usuarios y roles

En **Administración** → crear usuario:

| Rol | Qué puede hacer |
|---|---|
| **Solo lectura** | Ver el panel y el histórico, y exportar CSV. |
| **Operador** | Lo anterior, más renombrar y ubicar nodos, ajustar umbrales y configuración, y enviar comandos (calibrar, reiniciar…). |
| **Administrador** | Lo anterior, más gestionar usuarios y dar de alta, deshabilitar o eliminar nodos y sus credenciales. |

Al cambiar el rol o la contraseña de alguien, sus sesiones abiertas se
cierran solas. Siempre queda al menos un administrador activo.

### D5. Instalar el panel como aplicación (PWA)

Sirve en PC y en celular, y tiene las mismas funciones que la app de
escritorio. Ve a **Conexión** → *Usar como aplicación* → **Instalar ahora**,
o bien:

- **Windows (Edge o Chrome)**: menú `⋯` → *Aplicaciones* → *Instalar este
  sitio como aplicación*.
- **Android (Chrome)**: menú `⋮` → *Instalar aplicación* o *Añadir a pantalla
  de inicio*.
- **iPhone / iPad (Safari)**: botón *Compartir* → *Añadir a pantalla de
  inicio*.

### D6. Direcciones del servidor (red local y VPN)

La página **Conexión** muestra las direcciones por las que se llega a la Pi.
Si la actual deja de responder, el panel cambia solo a otra que sí conteste.
Las direcciones salen de la línea `PUBLIC_URLS` de `/etc/monitor/monitor.env`:

```
PUBLIC_URLS=https://192.168.1.50:8443,https://10.8.0.1:8443
```

Si agregas otra (por ejemplo Tailscale), edita el archivo y reinicia:

```bash
sudo nano /etc/monitor/monitor.env
sudo systemctl restart monitor-backend
```

---

## Parte E. La app de escritorio (Windows)

Es una ventana de Windows que muestra el panel de la Pi. Usa WebView2, el
motor de Edge que ya trae Windows 10 y 11, y recuerda tu sesión. Cambia sola
entre la red local y la VPN.

> **Antes de abrirla**, instala el certificado de la Pi en Windows
> ([paso D1](#d1-instalar-el-certificado-de-la-pi-en-cada-equipo)).

### E1. Opción 1: ejecutarla desde el código

```powershell
cd "C:\Users\jmedi\Documents\proyectos\monitor Desktop\desktop"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pywebview==6.2.1
.\.venv\Scripts\python.exe monitor_desktop.py
```

La próxima vez basta con el último comando.

### E2. Opción 2: generar el `.exe` (para instalar en otras PCs)

```powershell
cd "C:\Users\jmedi\Documents\proyectos\monitor Desktop\desktop"
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

✅ Se crea `desktop\dist\MonitorMultiNodo.exe`. Es un solo archivo: cópialo a
cualquier PC con Windows 10/11 y ábrelo (en cada PC instala antes el
certificado, paso D1).

Si junto a `monitor_desktop.py` pones el archivo `ca.crt` antes de compilar,
el `.exe` lo incluye para comprobar la conexión. Aun así, conviene instalarlo
en Windows para que la ventana no muestre advertencias.

### E3. Primer uso

1. Abre la app.
2. Si encuentra la Pi, verás directamente la pantalla de inicio de sesión.
3. Si no la encuentra, aparece una pantalla para escribir los servidores,
   **uno por línea**, empezando por la red local:

   ```
   https://192.168.1.50:8443
   https://10.8.0.1:8443
   ```

4. Guarda e inicia sesión.

Fuera de casa, **activa primero la VPN de WireGuard** y luego abre la app.

### E4. Dónde guarda sus datos

| Qué | Dónde |
|---|---|
| Lista de servidores | `%APPDATA%\MonitorMultiNodo\config.json` |
| Sesión (para no iniciar sesión cada vez) | `%APPDATA%\MonitorMultiNodo\webview` |

Para empezar de cero, cierra la app y borra la carpeta
`%APPDATA%\MonitorMultiNodo`.

---

## Parte F. Conectar los ESP32

Resumen; el detalle está en `firmware/README.md`.

### F1. Preparar el firmware (una vez para todos los nodos)

En la Pi, genera el archivo con el certificado:

```bash
sudo /opt/monitor/deploy/pi/pki.sh export-firmware-header > ~/ca_cert.h
```

Cópialo a tu PC y reemplaza `firmware/esp32_node/ca_cert.h`:

```powershell
cd "C:\Users\jmedi\Documents\proyectos\monitor Desktop"
scp usuario@192.168.1.50:~/ca_cert.h firmware\esp32_node\ca_cert.h
```

Compila y sube el firmware con Arduino IDE (placa *ESP32 Dev Module*) o con
PlatformIO (`pio run -t upload`). Es **el mismo firmware para todos** los
nodos.

### F2. Dar de alta cada nodo

1. Conecta el ESP32 por USB y abre el **monitor serie a 115200** con fin de
   línea «Nueva línea». Al arrancar muestra su MAC, por ejemplo
   `Nodo a4cf12b3c4d5`.
2. En el panel: **Agregar nodo** → escribe la MAC, un nombre y una zona.
3. Escribe el nombre y la contraseña de la WiFi. La contraseña de la WiFi no
   sale de tu navegador.
4. El asistente te da una línea que empieza con `{"cmd":"provision"…`.
   **Cópiala y pégala en el monitor serie**.
5. El nodo se reinicia y se conecta. El asistente te avisa cuando aparece en
   línea.

✅ El LED del ESP32 queda **fijo** y el nodo aparece «En línea» en el panel.

| LED | Significa |
|---|---|
| Fijo | Conectado al broker |
| Parpadeo de 1 Hz | Tiene WiFi pero no llega al broker |
| Destello corto cada 2 s | No tiene WiFi |

La clave MQTT de cada nodo **solo se muestra una vez**. Si la pierdes: nodo →
*Administración* → **Generar clave nueva** y vuelve a pegar la línea.

---

## Parte G. Entrar desde fuera de casa (VPN)

Con WireGuard ves el panel desde cualquier lugar sin exponer la Pi a
internet.

1. **En la Pi:**

   ```bash
   sudo /opt/monitor/deploy/pi/wireguard.sh init
   ```

2. **En el router:** redirige el puerto **UDP 51820** a `192.168.1.50`.
3. **Dirección pública:** si tu IP de internet cambia, crea un nombre gratuito
   en [DuckDNS](https://www.duckdns.org) (por ejemplo `micasa.duckdns.org`).
4. **Por cada equipo** (laptop, celular):

   ```bash
   sudo /opt/monitor/deploy/pi/wireguard.sh add laptop micasa.duckdns.org
   ```

   - **Celular**: escanea el QR que aparece con la app *WireGuard*.
   - **Windows**: instala la app oficial de WireGuard e importa el archivo
     `/etc/wireguard/clients/laptop.conf`. Para copiarlo, sácalo primero a tu
     carpeta: `sudo cp /etc/wireguard/clients/laptop.conf ~/ && sudo chown "$USER" ~/laptop.conf`.
5. Activa el túnel y abre `https://192.168.1.50:8443`: es la misma dirección
   que en casa.

Para quitar un equipo: `sudo /opt/monitor/deploy/pi/wireguard.sh remove laptop`.

> Si tu proveedor de internet usa **CGNAT** (la IP de internet del router
> empieza con `100.64` a `100.127`, o es privada), el reenvío de puertos no
> funciona. Usa Tailscale; los pasos están en `docs/CONECTIVIDAD.md`.

---

## Parte H. Probar en tu PC sin Raspberry Pi

Sirve para revisar el panel y la app de escritorio antes de tener la Pi lista.
Usa **datos simulados** (6 nodos) y **no toca Neon**.

```powershell
cd "C:\Users\jmedi\Documents\proyectos\monitor Desktop\backend"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe tests\demo_server.py
```

Abre `http://127.0.0.1:8765` con el usuario `demo` y la contraseña
`demo-demo-demo`.

Para probar la **app de escritorio** contra este servidor, deja la demo
corriendo y, en la pantalla de servidores de la app, escribe:

```
http://127.0.0.1:8765
```

Para correr las pruebas automáticas del backend:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

---

## Mantenimiento

### Actualizar el sistema después de cambiar el código

```bash
cd ~/monitor
git pull
sudo LAN_IP=192.168.1.50 ./deploy/pi/install.sh
```

Responde `s` a la pregunta de la IP. Como `/etc/monitor/monitor.env` ya
existe, **no vuelve a pedir la URL de Neon** y conserva todo.

### Tareas frecuentes

| Tarea | Comando (en la Pi) |
|---|---|
| Ver el log del backend en vivo | `journalctl -u monitor-backend -f` |
| Ver el log del broker | `sudo tail -f /var/log/mosquitto/mosquitto.log` |
| Estado general | `curl -sk https://localhost:8443/healthz` |
| Reiniciar el backend | `sudo systemctl restart monitor-backend` |
| Lista de usuarios | `sudo /opt/monitor/deploy/pi/monitor-cli.sh list-users` |
| Restablecer una contraseña | `sudo /opt/monitor/deploy/pi/monitor-cli.sh reset-password NOMBRE` |
| Dar de alta un nodo por consola | `sudo /opt/monitor/deploy/pi/provision_node.sh a4cf12b3c4d5 --name "Biodigestor 1" --zone "Granja norte"` |
| Revocar un nodo por consola | `sudo /opt/monitor/deploy/pi/provision_node.sh --revoke a4cf12b3c4d5` |
| Renovar el certificado (cada ~2 años) | `sudo /opt/monitor/deploy/pi/pki.sh renew-server 192.168.1.50` |
| Equipos de la VPN | `sudo /opt/monitor/deploy/pi/wireguard.sh list` |

### Respaldo

Guarda una copia de estas carpetas fuera de la Pi (por ejemplo en una USB):

```bash
sudo tar czf ~/respaldo-monitor.tgz /etc/monitor /etc/wireguard
```

- `/etc/monitor` contiene la URL de Neon, las claves y **la CA**. Sin la CA
  habría que recompilar el firmware de todos los nodos.
- `/etc/wireguard` contiene las claves de la VPN.

Este archivo es **secreto**: no lo subas a GitHub ni lo compartas.

### Ahorrar en Neon (plan gratuito)

La Pi escribe en Neon cada 15 s, lo que mantiene la base despierta. Para que
Neon pueda suspenderse, sube el intervalo:

```bash
sudo nano /etc/monitor/monitor.env      # cambia DB_FLUSH_INTERVAL_S=15 por 600
sudo systemctl restart monitor-backend
```

Los datos esperan en la Pi hasta el siguiente envío.

---

## Solución de problemas

### Broker (Mosquitto)

| Síntoma | Causa probable | Solución |
|---|---|---|
| Mosquitto no arranca; en el log aparece `Unable to open pwfile` | Falta el archivo de claves | `sudo /opt/monitor/deploy/pi/monitor-cli.sh mqtt-sync` y luego `sudo systemctl restart mosquitto` |
| `Address already in use` en el log | Hay otro Mosquitto u otro programa en el 1883/8883 | `sudo ss -tlnp \| grep -E '1883\|8883'` y detén el otro programa |
| `/healthz` muestra `"mqtt":false` | El backend no entra al broker | `sudo /opt/monitor/deploy/pi/monitor-cli.sh mqtt-sync`, `sudo systemctl restart mosquitto monitor-backend` y revisa `journalctl -u monitor-backend -n 50` |
| Agregué un nodo pero el broker no lo deja entrar | No se recargó Mosquitto | `systemctl is-active mosquitto-monitor-reload.path`; si no está activo: `sudo systemctl enable --now mosquitto-monitor-reload.path` y `sudo systemctl reload mosquitto` |
| En el log: `not authorised` para una MAC | Clave equivocada o nodo revocado | Panel → nodo → *Generar clave nueva* y vuelve a pegar la línea de aprovisionamiento |
| Error de permisos al leer `passwd` | Permisos alterados | `sudo chown monitor:mosquitto /var/lib/monitor-mqtt/passwd && sudo chmod 640 /var/lib/monitor-mqtt/passwd` |

### ESP32

| Síntoma | Causa probable | Solución |
|---|---|---|
| LED con destello cada 2 s | No conecta a la WiFi | Revisa nombre y contraseña de la WiFi (debe ser de 2.4 GHz) y vuelve a aprovisionar |
| LED a 1 Hz | Tiene WiFi pero no llega al broker | Comprueba que `mqtt_host` sea la IP de la Pi, que el puerto 8883 esté permitido (`sudo ufw status`) y que el firmware tenga el `ca_cert.h` de **esta** Pi |
| El nodo nunca se conecta tras reinstalar la Pi | Se creó una CA nueva | Vuelve a generar `ca_cert.h` (paso F1), recompila y sube el firmware |
| Escribe `{"cmd":"status"}` en el monitor serie | — | Muestra el estado de red y MQTT del nodo |

### Panel web y app de escritorio

| Síntoma | Causa probable | Solución |
|---|---|---|
| «La conexión no es privada» | Falta instalar la CA en ese equipo | Paso D1 |
| La página no carga desde la PC | Cortafuegos o IP equivocada | `curl -sk https://localhost:8443/healthz` en la Pi; si responde, revisa que la PC esté en la misma red y que `sudo ufw status` permita el 8443 |
| `"db":false` en `/healthz` | La Pi no llega a Neon | Revisa internet en la Pi y la `DATABASE_URL` en `/etc/monitor/monitor.env`. Mientras tanto, las lecturas se guardan en la Pi y se suben al volver |
| La app de escritorio muestra la pantalla de servidores | No encontró ninguna dirección | Revisa la IP, que la Pi esté encendida y que la CA esté instalada en Windows |
| PowerShell dice que la ejecución de scripts está deshabilitada | Política de Windows | Usa `powershell -ExecutionPolicy Bypass -File .\script.ps1` como en esta guía |
| Olvidé la contraseña del administrador | — | `sudo /opt/monitor/deploy/pi/monitor-cli.sh reset-password NOMBRE` |

### Cambió la IP de la Pi

Si la IP de la Pi cambia (por ejemplo, otro router), haz esto con la IP nueva:

```bash
sudo /opt/monitor/deploy/pi/pki.sh renew-server 192.168.1.80
sudo nano /etc/monitor/monitor.env   # cambia MQTT_PUBLIC_HOST y PUBLIC_URLS a la IP nueva
sudo systemctl restart monitor-backend
```

La CA no cambia, así que **no hay que recompilar el firmware**. Pero cada
ESP32 tiene guardada la IP vieja: vuelve a aprovisionarlos (panel → nodo →
*Generar clave nueva*) y actualiza la lista de servidores de la app de
escritorio.

Si además cambió la red (por ejemplo, de `192.168.1.x` a `192.168.0.x`),
vuelve a aplicar el cortafuegos para que permita la red nueva:

```bash
sudo /opt/monitor/deploy/pi/firewall.sh
```

---

## Documentos relacionados

| Documento | Contenido |
|---|---|
| `docs/ARQUITECTURA.md` | Tópicos MQTT, API y seguridad en detalle |
| `docs/DESPLIEGUE_PI.md` | Referencia técnica de la instalación |
| `docs/CONECTIVIDAD.md` | Red local, VPN, Tailscale y certificados |
| `firmware/README.md` | Conexiones de los sensores, compilación y comandos por USB |
| `desktop/README.md` | Detalles de la app de escritorio |
| `docs/INTEGRACION_ML.md` | Cómo conectar el modelo de aprendizaje automático |
