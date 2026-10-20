# Despliegue en la Raspberry Pi 4B

Probado para Raspberry Pi OS Bookworm de 64 bits. No se instala Node.js ni
nada de NPM. Todo viene de `apt` (sistema) o de `pip` dentro de un `venv`.

## 0. Preparación

1. **IP fija para la Pi.** Haz una reserva DHCP en el router, por ejemplo
   `192.168.1.50`. Los ESP32 se conectan a esa IP y el certificado TLS la
   incluye.
2. **Copia el proyecto a la Pi**, con `git clone` o con
   `scp -r "monitor Desktop" pi@192.168.1.50:~/monitor`.
3. **Ten a mano la cadena de conexión de Neon**:
   `postgresql://usuario:clave@ep-xxx.neon.tech/db?sslmode=require`.

## 1. Instalación

```bash
cd ~/monitor
sudo LAN_IP=192.168.1.50 ./deploy/pi/install.sh
```

El script hace esto:

- Instala `mosquitto`, `wireguard-tools`, `ufw`, `python3-venv` y `qrencode`.
- Crea el usuario de servicio `monitor` y las carpetas `/opt/monitor`
  (código y venv), `/etc/monitor` (secretos) y `/var/lib/monitor` (spool).
- Instala las dependencias de `backend/requirements.txt` con pip, en
  versiones exactas.
- Crea una CA local y un certificado ECDSA para `192.168.1.50`, `10.8.0.1` y
  `monitor.local`.
- Configura Mosquitto: TLS en 8883, solo localhost en 1883 y ACL por MAC. El
  archivo de claves lo genera el backend (usuario `backend` con clave aleatoria +
  un usuario por nodo).
- Te pide la `DATABASE_URL` y genera `JWT_SECRET`. Lo guarda en
  `/etc/monitor/monitor.env` con permisos `root:monitor 640`.
- Crea las tablas en Neon y activa `monitor-backend.service`.
- Activa el cortafuegos (ver `docs/CONECTIVIDAD.md`).

Volver a ejecutarlo actualiza el código y conserva las claves y la
configuración.

## 2. Primer administrador

```bash
sudo /opt/monitor/deploy/pi/monitor-cli.sh create-admin
```

Los demás usuarios se crean desde el panel, en *Administración*.

## 3. Firmware (una sola vez para todos los nodos)

```bash
sudo /opt/monitor/deploy/pi/pki.sh export-firmware-header > ca_cert.h
```

Copia ese archivo sobre `firmware/esp32_node/ca_cert.h` y compila. Los pasos
están en `firmware/README.md`.

## 4. Alta de cada ESP32 (más nodos)

Desde el panel, con un usuario administrador:

1. Flashea el firmware y abre el monitor serie a 115200. Verás `Nodo a4cf12b3c4d5 …`.
2. Pulsa **Agregar nodo**, escribe esa MAC, un nombre y una zona.
3. El asistente genera la clave MQTT del nodo y arma la línea `{"cmd":"provision",…}`
   con el WiFi que escribas (la clave del WiFi no sale de tu navegador).
4. Pega la línea en el monitor serie. El asistente te avisa cuando el nodo se conecta.

El backend guarda solo el hash de cada clave y regenera el archivo de claves de
Mosquitto (`/var/lib/monitor-mqtt/passwd`); la unidad `mosquitto-monitor-reload.path`
recarga Mosquitto al instante. No hay límite fijo de nodos.

Por consola hace lo mismo: `sudo /opt/monitor/deploy/pi/provision_node.sh a4cf12b3c4d5 --name "Biodigestor 1" --zone "Granja norte"`.

- **Clave perdida**: Nodo › Administración › *Generar clave nueva* (la anterior deja de valer).
- **Retirar un nodo**: *Revocar* (conserva el histórico) o *Eliminar* (borra todo y su credencial).

## 5. Acceso desde fuera de casa

Ver `docs/CONECTIVIDAD.md`.

```bash
sudo /opt/monitor/deploy/pi/wireguard.sh init
sudo /opt/monitor/deploy/pi/wireguard.sh add laptop micasa.duckdns.org
```

## 6. Operación

| Tarea | Comando |
|---|---|
| Logs del backend | `journalctl -u monitor-backend -f` |
| Logs de Mosquitto | `sudo tail -f /var/log/mosquitto/mosquitto.log` |
| Ver tráfico MQTT | `mosquitto_sub -h 127.0.0.1 -u backend -P "$(sudo grep MQTT_PASSWORD /etc/monitor/monitor.env \| cut -d= -f2)" -t 'monitor/v1/#' -v` |
| Estado | `curl -sk https://localhost:8443/healthz` |
| Reiniciar | `sudo systemctl restart monitor-backend` |
| Renovar certificado (cada ~2 años) | `sudo /opt/monitor/deploy/pi/pki.sh renew-server 192.168.1.50` |
| Restablecer contraseña | `sudo /opt/monitor/deploy/pi/monitor-cli.sh reset-password usuario` |

Sin internet, el panel sigue mostrando datos en vivo, porque el MQTT es local.
Las lecturas se acumulan en `/var/lib/monitor/spool.jsonl` (máximo
`SPOOL_MAX_MB`) y se suben a Neon al volver la conexión.

## Instalación con verificación de hashes (opcional, recomendado)

En un equipo de confianza con la misma arquitectura (aarch64, Python 3.11):

```bash
python3 -m venv /tmp/lock && /tmp/lock/bin/pip install pip-tools
/tmp/lock/bin/pip-compile --generate-hashes -o requirements.lock backend/requirements.in
```

Después cambia en `install.sh` `-r requirements.txt` por
`--require-hashes -r requirements.lock`.

## Coste en Neon

La Pi escribe un lote cada `DB_FLUSH_INTERVAL_S`, 15 s por defecto. Escribir
de forma constante mantiene despierto el cómputo de Neon. Si usas el plan
gratuito y quieres que se suspenda, sube `DB_FLUSH_INTERVAL_S` a 600 o más en
`/etc/monitor/monitor.env`. Los datos esperan en memoria hasta el siguiente
lote; si la Pi se apaga de golpe, se pierden como mucho los de ese intervalo.
