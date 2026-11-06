# Bitácora de configuración de la Raspberry Pi

Registro de lo que se hizo en la Raspberry Pi que funciona como broker MQTT y servidor del monitor. Es aparte de la
documentación del proyecto (`docs/DESPLIEGUE_PI.md`): aquí queda qué se ejecutó, cuándo, con qué resultado y qué
quedó pendiente.

## Datos del equipo

| Dato | Valor |
|---|---|
| Acceso | `ssh ialab` (alias de la PC) o `ssh -i ~/.ssh/id_ialab_pi ialab@192.168.120.74`. Solo con llave desde el 2026-11-06 |
| Red | `EDIFICIO EE`, `192.168.120.0/24`, puerta de enlace `192.168.120.1`. Antes: `192.168.137.0/24`, la red de «Conexión compartida» de Windows |
| Huella SSH de la Raspberry | `SHA256:F/u/cSIt1lfdZEZBvMgl3jLyP7n7eqUl5DNYuuATHic` (ED25519) |
| Llave SSH de la PC | `~/.ssh/id_ialab_pi` (ed25519, sin frase de paso, solo para esta Raspberry) |

## Configuración que hay que aplicar

Sale de `deploy/pi/install.sh`, `deploy/mosquitto/` y `deploy/systemd/`.

| Elemento | Configuración |
|---|---|
| Paquetes | `mosquitto`, `mosquitto-clients`, `python3-venv`, `python3-pip`, `openssl`, `ufw`, `wireguard-tools`, `qrencode`, `rsync` |
| Mosquitto, puerto 1883 | Solo `127.0.0.1`, sin TLS, para el backend |
| Mosquitto, puerto 8883 | TLS 1.2 para los ESP32, limitado a la red local por el cortafuegos |
| Autenticación | Sin acceso anónimo; usuario `backend` y un usuario por nodo, igual a su MAC |
| Permisos | ACL en `/etc/mosquitto/acl`: cada nodo solo usa `monitor/v1/nodes/<MAC>/...` |
| Contraseñas MQTT | `/var/lib/monitor-mqtt/passwd`, generado por el backend a partir de la base de datos |
| Certificados | CA local y certificado del servidor ECDSA P-256 para la IP de la Raspberry, `10.8.0.1` y `monitor.local` |
| Backend | FastAPI en `/opt/monitor`, servicio `monitor-backend` en el puerto 8443 con TLS |
| Secretos | `/etc/monitor/monitor.env`: `DATABASE_URL` de Neon, `JWT_SECRET` y clave MQTT del backend |
| Cortafuegos | `ufw`: SSH, 8443 y 8883 solo desde la red local; WireGuard en UDP 51820 |

### IP de la Raspberry

El certificado TLS y los ESP32 usan la IP de la Raspberry, así que no debe cambiar. La red `192.168.137.x` la reparte
Windows con «Conexión compartida», que no permite reservar una IP. Por eso hay que fijarla en la Raspberry:
`192.168.137.139`, con puerta de enlace y DNS `192.168.137.1`.

Desde el cambio a `EDIFICIO EE` la IP es `192.168.120.74` y la entrega el DHCP del edificio (ver «Cambio a la red
EDIFICIO EE»).

## Registro

### 2026-11-05

1. **Revisión del repositorio.** Se leyeron `deploy/pi/install.sh`, `pki.sh`, `firewall.sh`, `monitor-cli.sh`,
   `deploy/mosquitto/monitor.conf`, `deploy/mosquitto/acl` y las unidades de `deploy/systemd/`.
2. **Conectividad.** La Raspberry responde al ping desde la PC.
3. **SSH.** El servidor solo acepta llave pública o contraseña, y la PC no tenía llave para este equipo. Se creó
   `~/.ssh/id_ialab_pi`. El primer intento de instalarla desde PowerShell dejó la llave con saltos de línea de Windows y
   la Raspberry la rechazó. Se instaló de nuevo con un script que quita los `\r`, y desde entonces entra sin contraseña.
4. **Estado inicial de la Raspberry.**

   | Dato | Valor |
   |---|---|
   | Nombre | `IALab` |
   | Sistema | Debian GNU/Linux 13 (trixie), aarch64. El instalador se escribió para Bookworm |
   | Python | 3.13.5 |
   | Memoria y disco | 3.7 GiB de RAM; 22 GB libres de 29 GB |
   | Red | `wlan0`, Wi-Fi del punto de acceso de la PC (conexión `netplan-wlan0-DESKTOP-OERS02P 2827`), IP por DHCP, con internet |
   | Hora | `America/Mexico_City`, sincronizada |
   | Servicios | Solo SSH (22) y rpcbind (111). Sin Mosquitto, backend ni cortafuegos |
   | `sudo` | Pide contraseña: los pasos de instalación los ejecuta el usuario en una terminal |

5. **Copia del proyecto.** Se copiaron `backend/` y `deploy/` del commit `8d7d4e8` a `/home/ialab/monitor`, sin `.venv`,
   cachés ni `.env`, y se quitaron los `\r` de los scripts.
6. **Prueba de dependencias.** En un entorno virtual temporal se instalaron las versiones exactas de
   `backend/requirements.txt` con Python 3.13: todas instalaron y `app.main` cargó sin errores. El entorno se borró.
7. **Script de configuración.** Se dejó `/home/ialab/monitor/configurar_pi.sh`, que fija la IP `192.168.137.139/24` con
   puerta de enlace y DNS `192.168.137.1` (sin reiniciar la conexión) y ejecuta `deploy/pi/install.sh` guardando la
   salida en `/home/ialab/monitor/install.log`. La `DATABASE_URL` se escribe sin eco y no queda en el registro.
8. **Ejecución, 13:05.** El usuario lanzó `configurar_pi.sh` con su contraseña de `sudo`.
   - **IP fija:** quedó en modo `manual` con `192.168.137.139/24`, puerta de enlace y DNS `192.168.137.1`. La conexión no
     se cortó y la Raspberry siguió con internet.
   - **Paquetes:** se instalaron `mosquitto` y `mosquitto-clients` 2.0.21, `ufw` 0.36.2, `wireguard-tools`, `qrencode`
     e `iptables`. Mosquitto quedó habilitado al arranque.
   - **Backend:** se crearon el usuario `monitor` y las carpetas, y se copió el código a `/opt/monitor`. La instalación
     de dependencias con pip va lenta por la red: cada paquete tarda minutos en descargarse.
   - **Certificados:** se creó la CA local y el certificado del servidor para `192.168.137.139`, `10.8.0.1` y
     `monitor.local`, válido 825 días. Huella SHA1 de la CA: `1A6D7E5C5E5330657CDF94BA099BD379E92DF2E2`.
   - **Mosquitto:** se instalaron `monitor.conf` y la ACL. El servicio quedó activo con su configuración.
   - **Falla en la base de datos:** al crear las tablas, psycopg2 rechazó la cadena con
     `invalid dsn: extra key/value separator "=" in URI query parameter: "channel_binding"`. La causa probable es que la
     cadena se pegó dos veces sin verse. La instalación se detuvo ahí: faltan las credenciales MQTT, el servicio del
     backend y el cortafuegos.
9. **Corrección.** Se dejó `/home/ialab/monitor/corregir_db.sh`, que muestra cuántos `://` y `?` tiene la cadena
   guardada sin revelarla, pide la cadena una sola vez, valida su forma, la reemplaza en `/etc/monitor/monitor.env` con
   permisos `root:monitor 640` y vuelve a ejecutar el instalador, que conserva certificados y claves.

10. **Segunda ejecución, 13:15.** Con la cadena corregida, el instalador conservó la CA, volvió a emitir el certificado
    del servidor, creó el esquema en Neon («Esquema listo») y generó `/var/lib/monitor-mqtt/passwd`. Después Mosquitto
    no arrancó: `systemctl` lo reinició cinco veces y lo dejó en `failed`. El registro solo muestra la carga de
    `monitor.conf` y la salida con error; el detalle está en `/var/log/mosquitto/mosquitto.log`, que solo lee `root`.
    La instalación se detuvo antes de instalar el servicio del backend y el cortafuegos.
11. **Diagnóstico.** Se dejó `/home/ialab/monitor/diag_mosquitto.sh`, que guarda en `diag_mosquitto.txt` el final del
    registro, los permisos de certificados y del archivo de claves (solo los nombres de usuario, no los hashes) y una
    prueba de Mosquitto en primer plano durante 5 s.

12. **Causa.** El registro mostró `Opening ipv4 listen socket on port 1883` dos veces y luego
    `Error: Address already in use`. `use_username_as_clientid` estaba en la sección global de `monitor.conf`, antes de
    cualquier `listener`; en Mosquitto 2.0 una opción de listener ahí crea un listener por defecto en `0.0.0.0:1883`,
    que choca con el de `127.0.0.1:1883`. Se comprobó sin `root`, en puertos libres: con la opción en la sección global
    se abre un `1883` extra, y con la opción después de un `listener`, no.
    También avisó que `passwd` y `acl` no pertenecen a `mosquitto` (por ahora solo es advertencia).
13. **Corrección en el repositorio.**
    - `deploy/mosquitto/monitor.conf`: `use_username_as_clientid true` pasó al final, después de `listener 8883`.
    - `deploy/pi/install.sh`: la ACL se instala con dueño `mosquitto:mosquitto`.
    - `passwd` sigue con dueño `monitor`, porque lo escribe el backend; la advertencia de Mosquitto queda pendiente.
    Se copiaron ambos archivos a la Raspberry y se volvió a ejecutar el instalador.

14. **Tercera ejecución, 13:24.** El instalador terminó: Mosquitto arrancó, se instalaron y activaron
    `monitor-backend` y `mosquitto-monitor-reload.path`, y se aplicó el cortafuegos.

## Estado final y pruebas

| Prueba | Resultado |
|---|---|
| Servicios | `mosquitto`, `monitor-backend` y `mosquitto-monitor-reload.path` activos y habilitados al arranque |
| Puertos | `127.0.0.1:1883` (solo local), `0.0.0.0:8883` y `[::]:8883` (TLS), `0.0.0.0:8443` (panel) |
| Backend | Conectado a Mosquitto y a Neon; esquema listo; 0 nodos registrados; archivo de claves con 1 usuario (`backend`) |
| `/healthz` desde la PC | `{"ok":true,"service":"monitor-multinodo","mqtt":true,"db":true}` |
| Puerto 1883 desde la PC | Cerrado, como se esperaba |
| Certificado en 8883 | `CN=monitor.local`, emitido por la CA local; la huella de la CA coincide con la registrada |
| TLS | Negocia TLS 1.3 y acepta TLS 1.2 forzado, la versión que usa el ESP32 |
| MQTT anónimo, 1883 y 8883 | `Connection Refused: not authorised` |
| MQTT con usuario inventado en 8883 | `Connection Refused: not authorised` |
| Cortafuegos | `ufw` activo: SSH, 8443 y 8883 solo desde `192.168.137.0/24`; 8443 y SSH desde la VPN `10.8.0.0/24`; WireGuard en UDP 51820 |

La prueba de 8883 usó la CA pública que el propio servidor envía en la cadena TLS.

## Pendientes

1. **Contraseña de Neon:** la cadena se escribió en el chat. Hay que cambiar la contraseña de `neondb_owner` en Neon
   y luego ejecutar `sudo bash ~/monitor/corregir_db.sh` con la cadena nueva.
2. **Primer administrador:** `sudo /opt/monitor/deploy/pi/monitor-cli.sh create-admin`. Lo ejecuta el usuario,
   porque pide una contraseña.
3. **Firmware:** `firmware/esp32_node/ca_cert.h` ya tiene la CA nueva y `CA_CERT_CONFIGURED 1`. Se obtuvo de la cadena
   TLS del puerto 8883 y se verificó que su huella coincide con la registrada, que el certificado del servidor valida
   contra ella y que la verificación por IP `192.168.137.139` da `0 (ok)` con TLS 1.2. Falta compilar y cargar el
   firmware en cada ESP32: en esta PC no hay compilador de Arduino instalado.
4. **Nodos:** dar de alta cada ESP32 en el panel, `https://192.168.137.139:8443`, importando antes la CA en la PC.
5. **Advertencia de Mosquitto:** `/var/lib/monitor-mqtt/passwd` pertenece a `monitor` y no a `mosquitto`. Hoy solo
   genera un aviso, pero versiones futuras de Mosquitto rechazarán el archivo.
6. **IP:** la Raspberry depende de la «Conexión compartida» de la PC. Si cambia la red, hay que ajustar la IP fija y
   emitir un certificado nuevo con `pki.sh renew-server <IP>`.
7. **Acceso remoto (opcional):** WireGuard está instalado, pero no configurado.

## Primer nodo en marcha (2026-11-05)

1. **Código.** La rama `main` de `JManuelMMg/monitor-Desktop` tiene el mismo `backend/` y `deploy/` que se instaló.
   Los cambios de `monitor.conf`, `install.sh` y `ca_cert.h` siguen sin commit.
2. **Firmware.** Se compiló `firmware/esp32_node` con la CA nueva (core esp32 3.3.12, PubSubClient y ArduinoJson): 79 %
   de flash y 15 % de RAM. La primera carga por COM3 falló con `Wrong boot mode detected`; con el botón BOOT presionado
   se cargó y verificó.
3. **Arranque.** El nodo reportó la MAC `b0cbd8c82130` y el firmware 3.1.0. DHT11 y MH-Z19C leyeron (21.8 °C, 49 %,
   unos 550 ppm de CO₂), el MQ-4 en calentamiento y sin calibrar, y el AJ-SR04M sin respuesta (`us_ok: false`).
4. **Administrador y alta.** Con `~/monitor/alta_nodo.sh`, el usuario creó el administrador del panel y registró el
   nodo como «Biodigestor 1», zona «Laboratorio». Las contraseñas las escribió él en la terminal.
5. **Aprovisionamiento.** La línea de aprovisionamiento se envió por COM3 con `enviar_serial.py`, que la lee del
   portapapeles sin mostrarla y oculta las contraseñas en la respuesta. Hubo tres tropiezos:
   - Pegada en una entrada oculta, la línea llegó incompleta y se rechazó.
   - COM3 estaba ocupado por otro programa (`Acceso denegado`) hasta que se cerró.
   - El nombre de la red se escribió como `mDESKTOP-OERS02P 2827`; con la confirmación del usuario se envió como
     `DESKTOP-OERS02P 2827`, sin tocar las contraseñas.
6. **Resultado.** El nodo respondió `Aprovisionado`, se reinició y reportó `WiFi conectado, IP 192.168.137.225` y
   `MQTT conectado a 192.168.137.139:8883`. El backend registró `Nodo nuevo detectado: B0:CB:D8:C8:21:30`. Después
   avisó una vez `Conexión a la base perdida, reintentando` (Neon cierra conexiones inactivas) y `/healthz` siguió en
   `ok` con base de datos y MQTT conectados.

### Pendientes del nodo

- Revisar el cableado del AJ-SR04M, que no responde.
- Calibrar el MQ-4 en aire limpio tras su calentamiento (`calibrate_mq4` desde el panel).
- Comprobar en el panel que las lecturas se guardan en el histórico.
- Fijar la IP del ESP32 o reservarla; hoy la recibe por DHCP.

## Cambio a la red EDIFICIO EE (2026-11-05)

La red del hotspot de la PC (`DESKTOP-OERS02P 2827`) se cambió por la red del edificio, `EDIFICIO EE`.

| Dato | Valor |
|---|---|
| Raspberry | `192.168.120.74/24` por DHCP, perfil de NetworkManager `EDIFICIO EE`, puerta de enlace `192.168.120.1` |
| PC | `192.168.120.187`, conectada a la banda de 5 GHz |
| Bandas | 2.4 GHz en el canal 11 (2462 MHz) y 5 GHz (5240 MHz). El ESP32 usa la de 2.4 GHz |
| Seguridad de la WiFi | Abierta, sin contraseña ni cifrado. Los datos del nodo siguen cifrados por MQTT con TLS, y el panel por HTTPS |

1. **Acceso bloqueado.** La Raspberry respondía al ping, pero SSH, 8443 y 8883 estaban filtrados, porque `ufw` solo
   admitía la red `192.168.137.0/24`. Desde la consola de la Raspberry se abrió SSH a la red nueva:
   `sudo ufw allow from 192.168.120.0/24 to any port 22 proto tcp`.
2. **Huella SSH.** `known_hosts` tenía otra huella para `192.168.120.74`, que pertenecía a otro equipo que usó antes
   esa IP. La huella que envió la Raspberry coincidía con la que ya se conocía de `192.168.137.139`, así que se borró
   la entrada vieja (`ssh-keygen -R 192.168.120.74`).
3. **`~/monitor/cambiar_red.sh`** (con `sudo`):
   - En `/etc/monitor/monitor.env` puso `MQTT_PUBLIC_HOST=192.168.120.74` y
     `PUBLIC_URLS=https://192.168.120.74:8443,https://10.8.0.1:8443`.
   - Ejecutó `firewall.sh` con `LAN_CIDR=192.168.120.0/24` y borró las reglas de `192.168.137.x`.
   - Ejecutó `pki.sh renew-server 192.168.120.74`. El certificado nuevo cubre IALab.local, monitor.local, localhost,
     127.0.0.1, 192.168.120.74 y 10.8.0.1, y vale 825 días. **La CA es la misma**, por lo que `ca_cert.h` del firmware
     y `desktop/ca_raspberry.crt` no cambian.
   - Al reiniciar los servicios, el backend tardó unos 90 s en detenerse; `systemd` lo cerró al vencer el tiempo de
     espera. Justo después `/healthz` dio `db:false`, y a los pocos segundos `db:true`.
4. **Pruebas desde la PC**:

| Prueba | Resultado |
|---|---|
| `https://192.168.120.74:8443/healthz`, validando con la CA | `{"ok":true,...,"mqtt":true,"db":true}` |
| `https://192.168.120.74:8443/` | Redirige a `/login` |
| `openssl s_client` a `192.168.120.74:8883` con `-verify_ip` | TLS 1.3, `Verify return code: 0 (ok)` |
| Puerto 1883 desde la PC | Cerrado |

5. **Nodo.** El firmware acepta un `provision` parcial y solo cambia los campos que recibe. Por eso se le enviaron
   solo la red y la IP del broker (`cambiar_red_nodo.py` por COM3), sin generar una clave MQTT nueva:
   `{"cmd":"provision","wifi_ssid":"EDIFICIO EE","wifi_pass":"","mqtt_host":"192.168.120.74","mqtt_port":8883,"mqtt_tls":true}`.
   El nodo respondió `Aprovisionado`, se reinició y reportó `WiFi conectado, IP 192.168.120.142` y
   `MQTT conectado a 192.168.120.74:8883`. En la Raspberry, `ss` mostró la sesión TLS establecida desde
   `192.168.120.142`. Al abrir el puerto serie el ESP32 se reinicia, y volvió a conectarse solo. `/healthz` siguió con
   MQTT y base de datos conectados.

### Pendientes de la red nueva

- La IP `192.168.120.74` llega por DHCP y el edificio podría cambiarla. Lo ideal es pedir al administrador de la red
  una reserva para la MAC de la Raspberry, `88:a2:9e:80:a7:99`. Si la IP cambia, hay que volver a ejecutar
  `cambiar_red.sh` con la IP nueva y reaprovisionar los nodos.
- Para entrar al panel desde Windows sin aviso de certificado hay que importar la CA (`desktop\instalar_ca.ps1`).
- El perfil viejo `netplan-wlan0-DESKTOP-OERS02P 2827` sigue guardado en la Raspberry, por si se vuelve al hotspot.

## Mantenimiento y seguridad (2026-11-06)

**Auditoría previa**, sin cambios:
- Hardware: 30 °C, sin bajones de voltaje (`throttled=0x0`), 20 GB libres de 29 GB, 3.3 GB de RAM libre.
- Hora: zona `America/Mexico_City`, con NTP sincronizado.
- Tras un reinicio, `mosquitto` y `monitor-backend` arrancaron solos y la IP siguió siendo `192.168.120.74`.

| Hallazgo | Riesgo |
|---|---|
| 120 paquetes sin actualizar y sin actualizaciones automáticas | Fallas de seguridad conocidas sin corregir |
| SSH acepta contraseña en una WiFi abierta y no hay protección contra intentos repetidos | Ataques para adivinar la contraseña desde la red del edificio |
| Ahorro de energía del WiFi encendido | Cortes y latencia en un equipo que debe estar siempre disponible |
| Perfiles `EDIFICIO EE` y `EDIFICIO EE - WIFI` con la misma prioridad | La Raspberry podría cambiar de red y de IP |
| El backend tardaba 90 s en detenerse | Reinicios lentos del servicio |
| Sin respaldo de la CA ni de `monitor.env` | Si se pierde la CA, hay que regenerarla y volver a grabar el firmware de todos los nodos |
| `rpcbind` activo (NFS) | Servicio que no se usa |

**`~/monitor/ajustes_pi.sh`** (con `sudo`; la salida queda en `~/monitor/ajustes.log`):
1. `apt-get full-upgrade` de 120 paquetes, entre ellos el kernel 6.18.60. Instaló además `unattended-upgrades` y
   `fail2ban`.
2. Actualizaciones de seguridad automáticas diarias, **sin reinicio automático**: `/etc/apt/apt.conf.d/20auto-upgrades`
   y `52monitor-unattended`.
3. SSH (`/etc/ssh/sshd_config.d/10-monitor.conf`): solo con llave, sin contraseña y sin entrar como root. Se validó con
   `sshd -t` antes de aplicarlo. La consola local con teclado sigue aceptando contraseña.
4. `fail2ban` para `sshd` (`/etc/fail2ban/jail.local`): 5 intentos fallidos en 10 minutos bloquean esa IP 1 hora.
5. WiFi: `wifi.powersave = 2` en `/etc/NetworkManager/conf.d/20-wifi-powersave.conf`. El perfil `EDIFICIO EE` quedó
   con prioridad 10, por encima de los demás perfiles.
6. Backend: `TimeoutStopSec=15` en `/etc/systemd/system/monitor-backend.service.d/10-stop.conf`.
7. Respaldo semanal: `/usr/local/sbin/monitor-backup.sh` con el temporizador `monitor-backup.timer`, cada domingo a las
   03:00.
   - Guarda `/etc/monitor` (CA, certificado y `monitor.env`), `/etc/mosquitto` y `/var/lib/monitor-mqtt` en
     `/var/backups/monitor/`, con permisos 600 y solo legible por root.
   - Conserva los 8 respaldos más recientes. El primero fue `monitor-20261106-1006.tar.gz`.
   - **Contiene la clave privada de la CA y la `DATABASE_URL`**: si se copia fuera de la Raspberry, debe guardarse en
     un lugar seguro.
8. Diario del sistema persistente, con un tope de 200 MB (`/etc/systemd/journald.conf.d/10-monitor.conf`).
9. Se desactivó `rpcbind`.

En la PC se agregó el alias `ssh ialab` a `~/.ssh/config`, apuntando a `192.168.120.74` con la llave `id_ialab_pi`.

**Comprobaciones:**

| Prueba | Resultado |
|---|---|
| `mosquitto`, `monitor-backend`, `fail2ban`, `monitor-backup.timer` | `active` |
| `rpcbind` | `inactive` |
| Paquetes pendientes | 0 |
| SSH con contraseña desde la PC | `Permission denied (publickey)`: rechazado |
| SSH con llave (`ssh ialab`) | Entra |
| Ahorro de energía de `wlan0` | `off` |
| `TimeoutStopUSec` del backend | `15s` |
| `/healthz` | MQTT y base de datos conectados |

**Reinicio.** El kernel 6.18.60 quedó instalado, pero el 6.18.50 siguió corriendo hasta reiniciar: Raspberry Pi OS no
crea `/var/run/reboot-required`, por eso el script indicó que no hacía falta reiniciar. Después del reinicio:
- Kernel `6.18.60+rpt-rpi-v8`, IP `192.168.120.74` y ahorro de energía del WiFi en `off`.
- `mosquitto`, `monitor-backend` y `fail2ban` activos, sin unidades fallidas.
- `/healthz` dio `db:false` durante unos segundos, mientras se conectaba a Neon, y luego `db:true`.

**Nodo.** Al terminar no había ninguna sesión en el puerto 8883 y el ESP32 no estaba en la red. La IP
`192.168.120.142` ya la tenía otro equipo, por lo que el ESP32 probablemente se quedó sin alimentación al
desconectarlo de la PC. Al darle corriente otra vez se conectó solo con la configuración guardada:
- Recibió por DHCP la IP `192.168.120.144`, que en la tabla ARP corresponde a la MAC `b0:cb:d8:c8:21:30`.
- Abrió la sesión TLS con `192.168.120.74:8883`.
- En 12 s, los bytes recibidos por la Raspberry en esa sesión pasaron de 2267 a 2994: llegan lecturas.

La IP del nodo cambia con cada conexión. No afecta, porque el nodo es el que se conecta al broker.

## Panel en vivo y acceso público con Tailscale Funnel (2026-11-06)

### Lecturas y gráficas congeladas

Síntoma: en la web y en la app de escritorio, en distintos dispositivos, las lecturas y las gráficas dejaban de
actualizarse. Había tres causas en el código:

| Causa | Archivo | Corrección |
|---|---|---|
| Si un envío por WebSocket tardaba más de 2 s, el servidor quitaba al cliente de la lista pero **no cerraba la conexión**. El navegador seguía mostrando «En vivo» sin recibir nada hasta recargar. En la WiFi del edificio pasaba seguido | `backend/app/hub.py` | Cola y tarea de envío por cliente. Si un cliente se atrasa (cola llena) o falla un envío, se cierra su conexión (códigos 1013 y 1011) y el navegador reconecta. Latido `tick` cada 15 s |
| El navegador no detectaba conexiones muertas | `backend/app/static/js/common.js` | Si pasan 40 s sin mensajes, reconecta. Al volver a la pestaña, desbloquear el celular o recuperar la red, revisa la conexión de inmediato |
| Las gráficas solo se recargaban de la base cada 60 s, y la base va hasta ~85 s atrasada (guarda cada 10 s y envía a Neon cada 15 s) | `backend/app/static/js/node.js` | Cada lectura en vivo entra a la gráfica, con un redibujo cada 2 s como máximo. Con 1 h aparece un punto nuevo cada ~9 s; con 24 h se mueve el último punto. Al reconectar se recarga el histórico, y la resincronización con la base pasó a 5 minutos |
| **El alto de las gráficas crecía en cada redibujo**: `chart.js` leía el atributo `height` del canvas, que él mismo reescribe multiplicado por la densidad de la pantalla. Llegó a 26 millones de px y la gráfica se veía en blanco, sobre todo en celulares (densidad 2–3) | `backend/app/static/js/chart.js` | El alto se lee una sola vez y se guarda en `data-css-height` |

Además:
- Los archivos de `/static/` se sirven con `Cache-Control: no-cache` y el service worker pasó a `monitor-v2`, para
  que cada dispositivo reciba el JavaScript nuevo sin borrar la caché a mano.
- Pruebas nuevas en `backend/tests/test_hub.py`: entrega a varios clientes, cierre del cliente que falla, cierre del
  cliente lento y latido. Pasan las 34 pruebas del backend.
- Se comprobó en el servidor de demostración (`tests/demo_server.py`): la gráfica se redibuja cada 2 s con la
  lectura nueva, el latido llega cada 15 s y el alto se queda en 200 px tras varios redibujos.

### Acceso sin instalar certificados: Tailscale Funnel

Objetivo: abrir el panel desde cualquier dispositivo y lugar sin importar la CA local. Se eligió Tailscale Funnel,
gratuito, que publica el panel con un certificado de Let's Encrypt.

| Dato | Valor |
|---|---|
| Dirección pública | **https://ialab-monitor.taile0627f.ts.net** |
| Equipo en Tailscale | `ialab-monitor`, `100.111.7.116`, cuenta `JManuelMMg` |
| Proxy | `tailscale funnel --bg https+insecure://localhost:8443`: Tailscale termina TLS y reenvía al backend local |
| Certificado | Let's Encrypt (YE2), vence 2027-02-04; Tailscale lo renueva solo |

`~/monitor/publicar_tailscale.sh` (con `sudo`):
1. Instaló el backend nuevo en `/opt/monitor` (rsync, igual que `install.sh`) y la unidad systemd con
   `--proxy-headers --forwarded-allow-ips 127.0.0.1`. Así el backend ve la IP real del visitante, y el bloqueo por
   intentos fallidos de inicio de sesión funciona por visitante y no por el túnel.
2. Instaló Tailscale desde `pkgs.tailscale.com` (Debian trixie) y ejecutó `tailscale up --hostname=ialab-monitor`. El
   usuario inició sesión y aprobó el equipo.
3. Activó Funnel y puso en `PUBLIC_URLS` la dirección pública, la LAN y la VPN.

El WebSocket (`routers/live.py`) acepta como origen el propio `Host` o cualquier dirección de `PUBLIC_URLS`.

**Problema y solución:**
- La dirección pública cortaba la conexión en el saludo TLS, tanto desde el edificio como desde internet.
- Se agregaron las reglas `ufw allow in on tailscale0 to any port 443 proto tcp` y `ufw allow in on tailscale0`, que
  ahora están en `deploy/pi/firewall.sh`.
- No era eso: la cadena `ts-input` de Tailscale ya acepta `tailscale0` antes que `ufw`.
- En los registros, el filtro de Tailscale había descartado las primeras conexiones de los nodos de ingreso a la
  peerapi mientras se emitía el certificado, y después no volvió a llegar nada.
- Lo resolvió `~/monitor/funnel_diag.sh`: guarda el diagnóstico, da a `ialab` permiso de operador de Tailscale
  (`tailscale set --operator=ialab`), reinicia `tailscaled` y vuelve a activar Funnel.

**Comprobaciones desde la PC (sin la CA local):**

| Prueba | Resultado |
|---|---|
| `/healthz` | `{"ok":true,...,"mqtt":true,"db":true}` |
| `/login`, `/static/js/chart.js`, `/manifest.webmanifest`, `/sw.js` | 200, ~0.6 s |
| WebSocket `/ws` con origen `https://ialab-monitor.taile0627f.ts.net` | 101, aceptado |
| WebSocket con origen ajeno | 403, rechazado |
| IP que registra el backend | `177.244.41.210`, la IP pública real del visitante, no `127.0.0.1` |
| Navegador integrado de Claude, sin la CA | Abre el login sin aviso de certificado |

La app de escritorio (`%APPDATA%\MonitorMultiNodo\config.json` y los valores por defecto de
`desktop/monitor_desktop.py`) intenta primero la dirección pública, luego `https://192.168.120.74:8443` y luego la
VPN.

**Seguridad.** El panel queda en internet y solo lo protege el inicio de sesión: 5 intentos fallidos en 15 minutos
bloquean 15 minutos la combinación de IP y usuario. Conviene usar contraseñas largas. Para quitar el acceso público:
`sudo tailscale funnel --https=443 off`. Los nodos ESP32 no pasan por Tailscale: siguen en `192.168.120.74:8883` con
la CA local.

## Intervalo de 2 s y tema claro (2026-11-06)

**Frecuencia de lecturas.** En el firmware no hay esperas que retrasen el ciclo: el peor caso suma ~0.4 s (CO₂ 150 ms,
ultrasónico 30 ms, DHT11 ~250 ms). El nodo publicaba cada 5 s porque ese era su intervalo configurado.
- El valor por defecto pasó a **2000 ms**, el mínimo que admite el DHT11: `backend/app/state.py` (`DEFAULT_CONFIG`),
  `firmware/esp32_node/settings.h` y `settings.cpp`.
- Para el nodo actual se cambia desde el panel, en Nodo → Ajustes → Intervalo de lectura = 2000. El nodo lo aplica
  por MQTT, sin regrabar el firmware.
- El histórico sigue guardando una lectura cada 10 s (`PERSIST_INTERVAL_S`). La gráfica en vivo muestra todas.

**Tema claro.**
- `static/css/app.css`: ~25 colores fijos pasaron a variables (`--sidebar-bg`, `--card-bg`, `--modal-bg`,
  `--toast-bg`, `--on-accent`, `--warn-text`, etc.). `:root[data-theme="light"]` redefine la paleta, con acentos más
  oscuros para que el texto sea legible sobre blanco.
- `static/js/theme.js`: se carga en `<head>` antes del CSS (la CSP no permite scripts en línea) y aplica el tema
  guardado sin parpadeo. Lo guarda por navegador (`localStorage.theme`), actualiza `color-scheme` y `theme-color`,
  sincroniza pestañas y emite `themechange`. Por defecto queda el oscuro.
- Botón de luna o sol (`data-theme-toggle`) en la barra lateral junto a «En vivo», en la barra del celular y flotante
  en el inicio de sesión. Íconos `i-sun` e `i-moon` en `_icons.html`.
- Las gráficas (`node.js`, `chart.js`) y los minigráficos (`nodecard.js`, `dashboard.js`) se redibujan con los
  colores del tema al cambiarlo.
- El service worker pasó a `monitor-v3` y guarda `theme.js` en caché.
- **App de escritorio:**
  - `desktop/setup.html` usa variables, tiene su propio botón y lee el tema de `config.json`.
  - `Bridge.set_theme()` lo guarda; el panel lo llama al cambiar de tema dentro de la app.
  - La ventana abre con el fondo del tema.
  - Los atributos del puente pasaron a ser privados (`_config`, `_window`): pywebview recorría la ventana expuesta
    y llenaba la consola de errores «maximum recursion depth».

**Despliegue.** Se creó `~/monitor/actualizar_backend.sh` (con `sudo`). Copia `backend/` y `deploy/` a
`/opt/monitor`, reinstala la unidad systemd si cambió, reinicia el backend y espera a que `/healthz` tenga la base de
datos conectada.

**Comprobado** en la dirección pública:
- `/healthz` responde con MQTT y base de datos conectados.
- `theme.js` se sirve y `/login` tiene el botón.
- `app.css` llega con `Cache-Control: no-cache`.
- El cambio a tema claro funciona (fondo `#f3f6f9`).
- El nodo sigue conectado al broker.
- Pasan las 34 pruebas del backend.

## Logo e íconos nuevos (2026-11-06)

Origen: `Assets/img/WrR1h.gif`, una ilustración IoT animada (nube, WiFi, nodos, gráfica y tanque) de 800×800 px,
20 cuadros de 70 ms y 1.5 MB. Los recursos se generaron con Pillow:

| Archivo | Contenido | Tamaño |
|---|---|---|
| `static/img/logo.webp` | Ilustración completa animada, sin márgenes, 132 px (se muestra a 44 px) | 58 KB |
| `static/img/logo-lg.webp` | Igual, 320 px, para el inicio de sesión | 192 KB |
| `static/img/logo.png` | Primer cuadro, fijo, para «reducir movimiento» | 15 KB |
| `static/favicon.png` | Recorte de la nube, 64 px, esquinas redondeadas (sustituye a `favicon.svg`) | 6 KB |
| `static/icons/icon-192.png`, `icon-512.png`, `apple-touch-icon.png` | Recorte de la nube | 25–122 KB |
| `static/icons/maskable-512.png` | Nube al 80 % sobre negro (zona segura de Android) | 88 KB |
| `desktop/icon.ico` | Nube, 16–256 px; `build.ps1` la usa con `--icon` | 84 KB |

- El recorte de la nube se usa en los íconos chicos porque la ilustración completa no se distingue a 16–64 px.
- Nuevo macro `logo()` en `_macros.html`: un `<picture>` que da el cuadro fijo cuando el sistema pide reducir
  movimiento.
- Se usa en la barra lateral, en la marca del inicio de sesión y, en grande, sobre el título del inicio de sesión
  (`.auth-hero`, cuyo tamaño se adapta a la altura y que se oculta en pantallas angostas).
- La página Conexión usa el logo animado.
- El service worker pasó a `monitor-v4` y guarda en caché el favicon y el logo.

**Desplegado** con `actualizar_backend.sh` y comprobado en la dirección pública:
- `/healthz` responde con MQTT y base de datos conectados.
- `logo.webp`, `logo-lg.webp`, `favicon.png`, `icon-192.png` y el manifiesto responden 200 con el tipo correcto.
- `/login` referencia el logo nuevo.

> **Aviso:** en la terminal de la PC donde se ejecutó la actualización quedó visible texto escrito tras el aviso de
> `sudo`. Si era la contraseña de `ialab`, conviene cambiarla con `passwd` en la Raspberry. SSH ya solo acepta la
> llave, pero la contraseña sigue sirviendo para `sudo` y para la consola local.

## Archivos en la Raspberry

| Archivo | Uso |
|---|---|
| `/home/ialab/monitor/` | Copia de `backend/` y `deploy/` usada por el instalador |
| `/home/ialab/monitor/configurar_pi.sh` | IP fija e instalación |
| `/home/ialab/monitor/corregir_db.sh` | Cambiar la `DATABASE_URL` y volver a ejecutar el instalador |
| `/home/ialab/monitor/cambiar_red.sh` | Cambio a la red EDIFICIO EE: `monitor.env`, cortafuegos y certificado |
| `/home/ialab/monitor/ajustes_pi.sh` | Actualización, SSH con llave, fail2ban, WiFi, respaldos y diario del sistema |
| `/usr/local/sbin/monitor-backup.sh` | Respaldo semanal en `/var/backups/monitor` |
| `/home/ialab/monitor/publicar_tailscale.sh` | Backend nuevo, Tailscale y Funnel |
| `/home/ialab/monitor/funnel_diag.sh` | Diagnóstico de Funnel y reinicio de `tailscaled` |
| `/home/ialab/monitor/actualizar_backend.sh` | Instala el backend copiado en `~/monitor` y reinicia el servicio |
| `/home/ialab/monitor/diag_mosquitto.sh` | Diagnóstico de Mosquitto sin contraseñas |
| `/home/ialab/monitor/install.log` | Salida de las instalaciones |

> **Seguridad:** la cadena de Neon con su contraseña se escribió en el chat de esta sesión. Conviene cambiar la
> contraseña del rol `neondb_owner` en Neon y actualizar `/etc/monitor/monitor.env` con `corregir_db.sh`.
