# Nodo con módulos comerciales: esquemático definitivo

Este documento describe el nodo según el esquemático definitivo `BiogasEmbebido` de Fusion: **una sola placa,
26 piezas y sensores conectados directo**. Manda sobre [`PCB_V2_COMERCIAL.md`](PCB_V2_COMERCIAL.md) y
[`PLACA2_INTERFAZ.md`](PLACA2_INTERFAZ.md). La lista de materiales es [`BOM_v4_modulos.csv`](BOM_v4_modulos.csv) y
los cálculos salen de [`simulacion_placa_definitiva.py`](simulacion_placa_definitiva.py):

```bash
python hardware/simulacion_placa_definitiva.py
```

Las hojas de datos de los módulos genéricos no se han verificado y nada se ha probado en banco.

## 1. Piezas de la lista de compra

| Compra | Cant. | Ref. | Se usa como |
|---|---|---|---|
| MP1584 de 5 V fijo, 3 A | 2 | U$1 + repuesto | 12 V → 5 V para sensores y ESP32 |
| Paquete cargador + zapatas + batería 12 V 7 Ah | 1 | CH1, BAT1 | Batería de respaldo con su propio cargador |
| Módulo de conmutación 12 V 10 A | 1 | UPS1 | Prioriza el adaptador y cambia a batería; no carga |
| Schottky 1N5822 | 20 | D1 | Aísla el pin 5V de la DevKitC. Se usa 1 por nodo |
| Fusible cerámico 3 A, 5×20 mm | 5 | F1, FB1 | Bus de 12 V y cable de la batería |
| Portafusible de PCB Keystone 4527, 5×20 mm | 1 | F1 | Fusible del bus de 12 V |
| Bornera de PCB, 2 pines, 5 mm | 10 | J1 | Entrada de 12 V |
| Interruptor rocker Würth 471001264142 | 1 | S1 | Encendido del nodo, montado en la tapa y cableado a los pads `S1` |

**Faltan por comprar:** el adaptador PS1 de 12 V y 1 A o más, el portafusible en línea FB1 y los arneses con
conector hembra de 2.54 mm para los sensores.

## 2. Conexión

```
PS1 12 V ─────────────► entrada adaptador ┐
                                          ├─ UPS1 ─► J1 ─ F1 3 A ─ S1 ─ +12V ─ U$1 MP1584 5 V ─┬─ +5V_SENS ─ MQ-4, MH-Z19C, AJ-SR04M
BAT1 ── FB1 3 A ──────► entrada batería   ┘                          │                         └─ D1 ─ 5V_ESP ─ U2 DevKitC
  ▲                                                                  └─ R6/R7 ─ IO35              (DHT11 a 3.3 V de U2)
  └── CH1, directo a los bornes
```

## 3. Consumo estimado

| Caso | Riel de 5 V | Entrada | Pin 5V de la DevKitC |
|---|---|---|---|
| Típico con adaptador de 12 V | 282 mA | 136 mA, 1.63 W | 4.69 V |
| Pico con adaptador de 12 V y 4 alarmas | 801 mA | 376 mA, 4.52 W | 4.64 V |
| Pico con batería a 11 V y 4 alarmas | 801 mA | 410 mA, 4.52 W | 4.64 V |

- El MP1584 trabaja al 40 % de sus 2 A nominales y F1 al 14 % en el peor caso.
- Sirve un adaptador de 12 a 13.8 V. Sin corte por bajo voltaje ya no hay un mínimo de 12.37 V.
- **Autonomía típica con 7 Ah: 26 h** hasta 50 % de descarga.

## 4. Limitaciones de este diseño

| Limitación | Qué pasa | Qué hacer |
|---|---|---|
| Sin corte por bajo voltaje | En un apagón largo, el nodo sigue descargando la batería más allá del 50 % y le quita vida. Un solo apagón muy largo puede dañarla | Atiende los apagones de más de 24 h o apaga S1 |
| Sin C1 | Si UPS1 usa relé, el nodo casi seguro se reinicia en cada cambio a batería: con 22 µF supuestos aguanta menos de 1 ms | Es aceptable si el reinicio no afecta: el nodo vuelve a conectarse solo. El MQ-4 tardará en estabilizarse de nuevo |
| Sin protección contra inversión ni TVS | Una batería o adaptador al revés daña el MP1584, y F1 no alcanza a protegerlo | Marca la polaridad en J1 y revisa con multímetro antes de conectar |
| Sin F3 | Un corto en un sensor apaga todo el nodo; F1 no se funde con cortos pequeños | Revisa los arneses antes de energizar |
| Sin F4 ni placa 2 | Los sensores van directo a los conectores de la placa | El DHT11, a 3.3 V, debe llevar el cable lo más corto posible, según el manual V1.3 de Aosong. Mantén cortos los demás: el MQ-4 y el MH-Z19C piden 5.0 ± 0.1 V |
| IO35 mide +12V, no la batería | Con luz lee el voltaje del adaptador; la batería solo se ve durante un apagón | Interpreta así la lectura si el firmware llega a usarla |

La placa 2, el cable W1 y los gabinetes del biodigestor ya no forman parte del nodo. Siguen listados en
[`BOM_v3_modulos.csv`](BOM_v3_modulos.csv) por si regresan, pero esta placa no tiene conector para ellos. La nota
sobre atmósferas explosivas de [`PLACA2_INTERFAZ.md`](PLACA2_INTERFAZ.md) sigue aplicando a cualquier sensor con
electrónica junto al biogás.

## 5. Correcciones pendientes en Fusion

El esquemático ya tiene conectados la entrada (J1-1 → F1 → S1 → `+12V`), el regulador, D1 y todos los pines del
ESP32. `S1` es el interruptor Würth 471001264142, montado en la tapa de la caja, y las piezas tienen los atributos de
[`fusion/atributos_placa1.scr`](fusion/atributos_placa1.scr). `atributos_placa2.scr` ya no aplica.

El ERC marca 6 avisos sin fallas de conexión: 5 de pines de corriente de U2 conectados a sus redes y `EN` sin
conectar, que no necesita conexión externa en esta placa.

Falta:

1. **Portafusible F1.** Ya es el Keystone 4527, con 21.9 mm entre pines. Compara esa medida con tu pieza antes de pedir la PCB.
2. **Placa vinculada.** Los pads `S1` solo reciben los dos cables del interruptor; la PCB no necesita recorte.
3. **Resistencias de perforación.** R1 a R7 y RL1 a RL4 son axiales 0207, con 10.16 mm entre pines. Con la colocación
   anterior, RL1 a RL4 chocan con LED1 a LED4, y R3 y R4 con el conector MQ1: hay que moverlas en la placa.

## 6. Firmware

El firmware 3.1.0 ya usa los pines de este esquemático: DHT11 en `IO23`, LED de alarma en `IO25`, `IO26`, `IO27` e
`IO14`, y `vbus_v` en `IO35`. El backend todavía no guarda ni muestra `vbus_v`.

El cálculo del MQ-4 ya descuenta el divisor R1/R2. **Cada nodo debe recalibrar R0:** el valor anterior se ignora y, hasta
ejecutar `calibrate_mq4`, `ch4_ppm` llega como `null` y la alarma de metano no enciende. La calibración exige los 3 min
de calentamiento y aire limpio. También hay que confirmar que la resistencia de carga del módulo sea de 10 kΩ
(`MQ4_RL_KOHM`), porque muchos traen 1 kΩ.

## 7. Pruebas de aceptación

Hazlas con una fuente limitada en corriente.

1. **U$1.** Antes de conectar sensores, mide entre 4.9 y 5.1 V sin carga y con 0.5 A.
2. **Polaridad.** Comprueba con multímetro J1, el adaptador y la batería antes de cada primera conexión.
3. **Carga.** Con PS1 y CH1 conectados y la batería a menos de 12.6 V, comprueba que su voltaje suba. Sin luz,
   comprueba que CH1 no descargue la batería.
4. **Cambio a batería.** Desconecta PS1 20 veces. El nodo puede reiniciarse, pero debe volver a conectarse al broker
   cada vez.
5. **Regreso del adaptador.** Reconecta PS1 20 veces y comprueba lo mismo.
6. **Consumo del módulo.** Mide lo que UPS1 toma de la batería con S1 abierto: determina cuánto dura guardada.
7. **Mecánica.** Antes de pedir la PCB, compara J1 y el portafusible con una impresión 1:1.

## 8. Otros pendientes

- `COTIZACION_*.docx` y `COTIZACION_Y_SIMULACION_v2.xlsx` **siguen con las piezas anteriores**: faltan los precios
  de las piezas nuevas.
- `simulacion_alimentacion_placas.py` y `simulacion_pcb_v2.py` quedan como referencia del diseño de dos placas.

## 9. Caja

El modelo vigente es el documento `BiogasEmbebido` de Fusion, actualizado para la placa V53; todos los cambios de la caja se
hacen ahí y de ahí se exportan los archivos de impresión. La tabla usa las coordenadas de la PCB, con su cara inferior en z = 0.

| Elemento | Medida o posición |
|---|---|
| Cuerpo | En L, de 127.55 × 82.1 × 51.5 mm; 141.55 × 96.1 mm con orejas. Paredes, piso y tapa de 2.5 mm. 5 orejas con tornillos M3 |
| Compartimento de `UPS1` | Brazo de la L a la izquierda, junto a `J1`, de x = −27 a 14.4 y de y = −42 a 21.75. Marco interior de 32 × 52 mm, de x = −24 a 8 y de y = −34 a 18, con repisa de apoyo de 1.5 mm a 3 mm sobre el piso. Sujeción provisional con cinta o silicón hasta medir los agujeros del módulo |
| Interior | 9 mm bajo la placa; 32.9 mm libres sobre su cara superior hasta el labio de la tapa |
| Placa | 4 postes de Ø7 mm con barreno guía de Ø2.6 mm, en (18.60, −50.65), (18.83, 18.06), (91.12, −50.42) y (91.35, 17.54) |
| Tapa | Labio de encaje y 4 tornillos M3 en las orejas |
| USB del ESP32 | Ventana de 14 × 15 mm en la pared inferior (y−), x = 59.23, z de 4 a 19 |
| Muesca junto a `D1` | Ø3.4 mm y 2.5 mm de profundidad en el poste inferior derecho, centrada en (87.37, −49.65), para la pata del diodo |
| Entradas de 12 V | 2 de Ø12.5 mm en la pared inferior del brazo (y = −43.25), z = 10, en x = −16 y x = −2, para el adaptador y la batería. La salida de `UPS1` va por dentro hasta `J1`, montada con la entrada de cables hacia el módulo (izquierda) |
| Sensores | 4 de Ø12.5 mm en la pared derecha (x+), y = −44, −27, −10 y 7, z = 10 |
| Interruptor `S1` | Recorte de 19.4 × 12.9 mm en la tapa, centrado en (38.75, 5.5), sobre los pads de `S1`; rebaje inferior de 25 × 17 mm que deja un panel de 1 mm |
| LED | 4 de Ø4 mm en la tapa, sobre `LED1` a `LED4` |

La altura supone el ESP32 en zócalo. `UPS1` va dentro de la caja; la batería, `CH1`, `PS1` y el fusible `FB1` van fuera.

**Interruptor:** va a presión en la tapa, con sus terminales hacia adentro, y se une con dos cables (`W9`) a los pads `S1` de la
placa. Los terminales llegan hasta z = 18.4, así que quedan 16.8 mm sobre la placa para los conectores. La PCB no necesita
recorte. El modelo 3D de la PCB aún lo muestra en la placa; es solo visual.
