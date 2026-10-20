# Conectividad híbrida (local y remota)

## Principio

**No se expone ningún servicio web ni MQTT a internet.** Fuera de casa se
entra por una VPN WireGuard que termina en la Pi. Para quien no tiene la clave
del túnel, el puerto UDP 51820 no responde: es indistinguible de un puerto
cerrado.

| Desde | Llega a | Cómo |
|---|---|---|
| ESP32 (en casa) | `IP_LAN:8883` | MQTT con TLS y usuario por MAC |
| PC Windows en casa | `https://IP_LAN:8443` | HTTPS directo por la LAN |
| PC o móvil fuera de casa | `https://IP_LAN:8443` (o `https://10.8.0.1:8443`) | dentro del túnel WireGuard |
| Internet (sin VPN) | nada | solo UDP 51820, que exige la clave del túnel |
| Pi → Neon | `*.neon.tech:5432` | conexión saliente TLS (`sslmode=require`) |

## Una sola dirección dentro y fuera de casa

El túnel WireGuard de cada cliente enruta **dos** direcciones de la Pi:
`10.8.0.1` y su IP de la LAN (por ejemplo `192.168.1.50`), lo genera
`wireguard.sh add`. Por eso `https://192.168.1.50:8443` funciona igual:

- **En casa**, sin VPN: directo por la WiFi.
- **Fuera**, con la VPN activa: por el túnel.

Así la app instalada, los marcadores y la sesión son los mismos en todas
partes. Si dentro de casa dejas la VPN encendida, el tráfico da la vuelta por
tu router. Funciona si el router admite *NAT loopback* (la mayoría); si no,
apaga la VPN en casa.

## Panel web como app (equivalente a la app de escritorio)

Todo lo que hace la app de escritorio también está en la web:

| App de escritorio (pywebview) | Web |
|---|---|
| Ventana propia con icono | **Instalable** (PWA): Conexión › *Usar como aplicación*, o el menú del navegador. Funciona en Windows, Android e iOS. |
| Lista de servidores LAN → VPN | **Conexión** › *Direcciones del servidor*. Salen de `PUBLIC_URLS` en `/etc/monitor/monitor.env`. |
| Cambio automático si un servidor cae | Igual. Si el tiempo real se corta más de 12 s y la dirección actual no responde, prueba las demás y salta a la primera que conteste. Se puede desactivar. |
| Pantalla cuando no hay servidor | Página **sin conexión**, que sirve el *service worker*. Reintenta cada 6 s y propone las otras direcciones. |
| Sesión persistente | Cookie de sesión (12 h), por dirección. |

La app de escritorio sigue disponible (`desktop/`), pero ya no es
imprescindible.

La configuración de la app de escritorio vive en
`%APPDATA%\MonitorMultiNodo\config.json`:

```json
{ "servers": ["https://192.168.1.50:8443", "https://10.8.0.1:8443"] }
```

## WireGuard

1. **En la Pi:** `sudo /opt/monitor/deploy/pi/wireguard.sh init`
2. **En el router:** redirige **UDP 51820** a la IP de la Pi.
3. **Dirección pública:**
   - Si tu IP pública cambia, usa un DDNS (DuckDNS, No-IP; muchos routers lo
     traen integrado).
   - Si tu proveedor te pone detrás de **CGNAT** (la IP WAN del router es del
     rango `100.64.0.0/10` o privada), el reenvío de puertos no funcionará.
     Mira la alternativa más abajo.
4. **Por cada equipo:**
   `sudo /opt/monitor/deploy/pi/wireguard.sh add <nombre> <tu-ddns>`
   - En Windows, importa el `.conf` generado en la app oficial de WireGuard.
   - En el móvil, escanea el QR con la app WireGuard.
5. **Para revocar un equipo:**
   `sudo /opt/monitor/deploy/pi/wireguard.sh remove <nombre>`

Los clientes usan *split tunnel* (`AllowedIPs = 10.8.0.1/32`): solo el tráfico
hacia la Pi pasa por el túnel, no toda tu navegación. Desde la VPN solo se
alcanzan los puertos 8443 (panel) y 22 (SSH) de la Pi.

## Alternativa si hay CGNAT: Tailscale

Tailscale usa WireGuard por debajo y atraviesa CGNAT sin abrir puertos. Es un
binario en Go (sin Node):

```bash
curl -fsSL https://pkgs.tailscale.com/stable/raspbian/bookworm.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
# (sigue la guía oficial para añadir el repositorio apt)
sudo apt install tailscale && sudo tailscale up
```

- Añade la IP `100.x.y.z` de la Pi a la lista de servidores de la app de
  escritorio.
- Regenera el certificado con esa IP:
  `sudo WG_IP=100.x.y.z /opt/monitor/deploy/pi/pki.sh renew-server IP_LAN`.
- En `firewall.sh` permite el puerto 8443 desde `100.64.0.0/10`.
- Ojo: depende del servidor de coordinación de Tailscale. WireGuard puro no
  depende de terceros.

## Certificados en los clientes

La CA local (`/etc/monitor/tls/ca.crt`) se importa una vez en cada equipo:

- **Windows**: `desktop\instalar_ca.ps1 -Ruta .\ca.crt`. Va al almacén del
  usuario y no necesita administrador. Compara la huella con
  `sudo /opt/monitor/deploy/pi/pki.sh fingerprint`.
- **Android / iOS**: instala el `.crt` como certificado de CA de usuario si
  vas a usar el navegador del móvil.

El certificado de la CA es público. La clave de la CA (`ca.key`) no sale
nunca de la Pi.
