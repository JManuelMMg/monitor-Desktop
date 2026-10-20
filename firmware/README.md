# Firmware del nodo ESP32

Es un único firmware para todos los nodos. Cada nodo se identifica por su MAC.
El nombre y la zona se asignan en el panel, sin recompilar.

## Conexiones

| Sensor | Pin ESP32 |
|---|---|
| DHT11 (datos) | 23 |
| MQ-4 (A0) | 34 |
| AJ-SR04M TRIG / ECHO | 5 / 18 |
| MH-Z19C TX → RX2 / RX ← TX2 | 16 / 17 |
| LED de estado | 2 |

## Compilar

**Antes de compilar**: reemplaza `esp32_node/ca_cert.h` por el que genera la
Pi (`sudo /opt/monitor/deploy/pi/pki.sh export-firmware-header > ca_cert.h`).
Con el archivo de ejemplo, el nodo se niega a conectarse.

### Opción A: Arduino IDE

1. Abre `esp32_node/esp32_node.ino`.
2. Instala estas bibliotecas desde el *Gestor de bibliotecas*:
   - **PubSubClient** (Nick O'Leary) 2.8
   - **ArduinoJson** (Benoît Blanchon) 7.x
   - **DHT sensor library** y **Adafruit Unified Sensor**
3. Elige la placa *ESP32 Dev Module* y sube el sketch.

Verificado con el core esp32 3.3.12: compila con 79 % de flash y 15 % de RAM.

### Opción B: PlatformIO

Las bibliotecas se descargan solas desde `platformio.ini`.

```bash
cd firmware
pio run -t upload && pio device monitor
```

## Aprovisionar (por USB, una vez por nodo)

1. Al arrancar, el monitor serie (115200) muestra la MAC, por ejemplo
   `Nodo a4cf12b3c4d5`.
2. En el panel, **Agregar nodo**: escribe la MAC, nombre y zona; el asistente
   genera la clave MQTT y la línea de aprovisionamiento.
3. Pega esa línea en el monitor serie. Tiene esta forma:
   ```json
   {"cmd":"provision","wifi_ssid":"MiRed","wifi_pass":"…","mqtt_host":"192.168.1.50","mqtt_port":8883,"mqtt_tls":true,"mqtt_pass":"…"}
   ```

## Comandos por USB

Estos funcionan aunque no haya red:

| Comando | Efecto |
|---|---|
| `{"cmd":"status"}` | estado de red y MQTT (las contraseñas no se muestran) |
| `{"cmd":"provision", …}` | guarda WiFi y MQTT en NVS y reinicia (solo por USB) |
| `{"cmd":"factory_reset"}` | borra la NVS completa (solo por USB) |
| `{"cmd":"calibrate_mq4"}` | calibra R0 en aire limpio (20 s, sin bloquear) |
| `{"cmd":"calibrate_co2_zero"}` | cero del MH-Z19C (requiere 20 min en aire exterior) |
| `{"cmd":"identify","args":{"seconds":10}}` | hace parpadear el LED |
| `{"cmd":"reboot"}` | reinicia |

## LED

| Estado | Significado |
|---|---|
| Fijo | MQTT conectado |
| 1 Hz | WiFi sí, MQTT no |
| Destello corto cada 2 s | sin WiFi |
| Parpadeo rápido | comando *identify* |

## Notas sobre los sensores

- **MQ-4**: tarda 3 min en calentar. Hasta entonces y sin R0, `ch4_ppm` llega
  como `null`. Si lo alimentas a 5 V, su salida debe pasar por un divisor
  antes del GPIO34, que admite como máximo unos 3,1 V.
- **MH-Z19C**: la autocalibración ABC viene apagada, porque en un biodigestor
  el CO₂ nunca baja a 400 ppm. Se puede activar por configuración.
- **Ultrasonido**: lleva un filtro de media móvil de 10 muestras. El offset,
  la escala y las alturas de reactor vacío y lleno se ajustan desde el panel.
