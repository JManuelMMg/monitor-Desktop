# Placa 2 «BiogasInterfaz»: interfaz de sensores en el biodigestor

> **Fuera del diseño definitivo:** el nodo actual conecta los sensores directo a una sola placa, sin esta interfaz.
> Lo vigente está en [`MODULOS_ALIMENTACION.md`](MODULOS_ALIMENTACION.md) y [`BOM_v4_modulos.csv`](BOM_v4_modulos.csv).

La placa 2 va dentro del biodigestor, en el espacio destinado a proteger los sensores. Recibe los cuatro
sensores, los alimenta y acondiciona sus señales, y las manda a la unidad central (placa 1) por un solo
cable apantallado. El firmware del ESP32 no cambia: cada señal llega a la placa 1 por la misma red que
antes.

```
 ┌──────────── Biodigestor: espacio protegido ────────────┐
 │  MQ-4   MH-Z19C   AJ-SR04M   DHT11                     │
 │    │       │         │         │   arneses JST XH (W2-W5, 30 cm)
 │  ┌─┴───────┴─────────┴─────────┴──┐                    │
 │  │ PLACA 2  (caja IP67, G2)       │ 12 V → 5 V local   │
 │  │ buffer, buffers TTL, ESD, TVS  │                    │
 │  └───────────────┬────────────────┘                    │
 └──────────────────┼─────────────────────────────────────┘
                    │ W1: 6 pares trenzados 0.34 mm², apantallado, PUR, hasta 20 m
                    │     prensaestopas IP68 M16 en ambos extremos
 ┌──────────────────┴─────────────────────────────────────┐
 │ PLACA 1: unidad central (gabinete IP65, G1)            │
 │ J4A/J4B ← F4 (PTC 60 V) ← +12V_LOAD (después del LVD)  │
 └────────────────────────────────────────────────────────┘
```

Archivos:

| Archivo | Contenido |
|---|---|
| [`placa2/BiogasInterfaz.sch`](placa2/BiogasInterfaz.sch) | Esquemático (EAGLE 9), 31 piezas y 20 redes |
| [`placa2/BiogasInterfaz.brd`](placa2/BiogasInterfaz.brd) | PCB de 70 × 55 mm con las piezas colocadas, sin rutear |
| [`placa2/netlist.json`](placa2/netlist.json) | Lista de redes para revisar o comparar |
| [`biogas_v2.lbr`](biogas_v2.lbr) | Biblioteca con todas las huellas de las dos placas |
| [`BOM_v2.csv`](BOM_v2.csv) | Lista definitiva de materiales del sistema completo |
| [`fusion/atributos_placa1.scr`](fusion/atributos_placa1.scr), [`fusion/atributos_placa2.scr`](fusion/atributos_placa2.scr) | Cargan fabricante y número de parte en cada pieza de Fusion |

---

## 1. Antes de instalar: los sensores dentro del gas

Las hojas de datos de los sensores actuales marcan límites que el interior de un biodigestor no cumple.
El biogás tiene 50-70 % de CH₄, 30-45 % de CO₂, humedad saturada y H₂S.

| Sensor | Límite en su hoja de datos | Qué pasa dentro del biodigestor |
|---|---|---|
| MQ-4 | Trabaja con 21 % de O₂ (mínimo 2 %), humedad < 95 %, rango de fuga de gas en aire | Sin oxígeno, la lectura no significa nada. Además su calentador es una superficie caliente dentro de un gas inflamable |
| MH-Z19C | 400-5000 ppm de CO₂, 0-95 % HR sin condensación | Se satura: el biogás tiene 300 000-450 000 ppm |
| DHT11 | Humedad sin condensación | La condensación lo daña en poco tiempo |
| AJ-SR04M | Transductor sellado | Sirve para el nivel; limpia el transductor si se forma espuma o condensado |

Recomendaciones:

- **Para medir la composición del biogás**, usa sensores NDIR de 0-100 % en volumen para CH₄ y CO₂
  (módulos analizadores de biogás). Hazles llegar una muestra de gas por una línea con trampa de
  condensado y filtro de H₂S, en lugar de meterlos en el gas del digestor.
- **El MQ-4 sirve para detectar fugas** en el aire alrededor del biodigestor y de la tubería. Ese es su
  uso según la hoja de datos.
- **Para temperatura dentro del digestor**, una sonda sellada de acero inoxidable aguanta mejor que el
  DHT11.
- **Atmósfera explosiva:** la mezcla de biogás con aire es explosiva entre 5 y 15 % de CH₄. Poner
  electrónica dentro del volumen del gas exige, en un producto comercial, certificación para atmósferas
  explosivas (equipo intrínsecamente seguro o encapsulado). Esta placa limita la energía (PTC de 0.5 A,
  sin relés ni contactos que hagan chispa, barniz conformal), pero no está certificada.

La placa 2 y el cable sirven igual con otros sensores: si cambias alguno, solo cambia el arnés y, si el
protocolo es distinto, el firmware.

---

## 2. Circuito de la placa 2

### 2.1 Alimentación

Por el cable llegan 12 V (no 5 V) porque la caída en 20 m de cable dejaría al calentador del MQ-4 fuera
de su 5.0 ± 0.1 V. Los 5 V se generan en la placa 2.

| Ref. | Pieza | Conexión | Por qué |
|---|---|---|---|
| D1 | MBRS340T3G | J1A-1/2 (+12V_IN) → V12 | Protege contra un cable con los polos invertidos |
| D2 | SMBJ18A | V12 a GND | Recorta transitorios del cable largo. VRWM 18 V, por encima de los 14.8 V de la carga |
| C1, C2 | 47 µF/35 V + 100 nF | V12 a GND | Entrada del regulador |
| U1 | Traco TSR 1-2450 | 1 +Vin = V12 · 2 GND · 3 +Vout = +5V | 6.5-36 V de entrada, 5 V 1 A, 94 % de eficiencia. No requiere bobina ni diodo externos |
| C3 | 10 µF/16 V | +5V a GND | Salida del regulador |

Consumo con los cuatro sensores: ≈ 0.33 A a 5 V en el pico (MQ-4 150 mA, MH-Z19C 125 mA). Del lado
de 12 V son ≈ 0.15 A, así que F4 (0.5 A) en la placa 1 no se dispara.

### 2.2 MQ-4 (analógico)

J2-2 (AO del módulo) → R1 1 kΩ + C4 100 nF (filtro) → U3 TLV9001 como seguidor → R2 100 Ω → MQ_AN.

El seguidor entrega la misma tensión con impedancia baja, para que el cable no capte ruido. En la placa 1
llega a R1/R2 (100 kΩ/150 kΩ), igual que antes.

### 2.3 MH-Z19C (UART a 9600 baud, nivel 3.3 V)

- CO2_RX (del ESP32, IO17) → R3 100 Ω → J3-3 (Rx del sensor).
- J3-2 (Tx del sensor) → R4 100 Ω → CO2_TX (al ESP32, IO16).

Las resistencias en serie amortiguan los reflejos del cable y limitan la corriente de una descarga.

### 2.4 AJ-SR04M (TRIG y ECHO)

- SR_TRIG (3.3 V del ESP32) → U4 SN74AHCT1G125 → R5 100 Ω → J4-2. U4 tiene entradas TTL (reconoce
  2.0 V como alto), así que el pulso llega al sensor regenerado a 5 V. R6 100 kΩ mantiene TRIG en bajo si
  el cable se desconecta.
- J4-3 (ECHO, 5 V) → U5 SN74AHCT1G125 → R7 100 Ω → SR_ECHO. El buffer, y no el sensor, es el que maneja
  el cable. En la placa 1, R3/R4 bajan la señal a 3.24 V para IO18.

### 2.5 DHT11 (bus de un hilo)

El DHT11 se alimenta con 5 V en la placa 2 y R9 (5.1 kΩ a 5 V) es su pull-up. Así lo pide su hoja de
datos para cables de hasta 20 m; con 3.3 V el cable no puede pasar de 1 m. R8 100 Ω queda en serie.

En la placa 1, Q3 (BSS138) traduce el nivel entre DHT_LINE (5 V, lado del cable) y DHT_DATA (3.3 V,
IO4, con R5 a +3V3). Es un adaptador bidireccional de colector abierto, así que el protocolo no cambia.

### 2.6 Protección ESD

U6 y U7 (TPD4E1U06) protegen las seis líneas del cable, junto a J1. El lado de la placa 1 ya tiene sus
propios U5/U6.

| Chip | Pin 1 (D1+) | Pin 3 (D2+) | Pin 4 (D2−) | Pin 6 (D1−) |
|---|---|---|---|---|
| U6 | MQ_AN | CO2_RX | CO2_TX | SR_TRIG |
| U7 | SR_ECHO | DHT_LINE | libre | libre |

---

## 3. Cable W1: unidad central ↔ placa 2

**Especificación:** 6 pares trenzados de 0.34 mm² (AWG 22), con pantalla trenzada de cobre estañado y
cubierta de PUR negra (resiste UV, hidrólisis, aceites y microorganismos). Longitud de diseño: hasta
20 m, que es el límite del DHT11. A 20 m, con 2 conductores de ida y 4 de retorno, la caída en los
12 V es de ≈ 0.1 V.

| Polo | Placa 1 | Placa 2 | Señal | Par | Sentido |
|---|---|---|---|---|---|
| 1 | J4A-1 | J1A-1 | +12V | 1 | Central → sensores |
| 2 | J4A-2 | J1A-2 | +12V | 2 | Central → sensores |
| 3 | J4A-3 | J1A-3 | GND | 1 | — |
| 4 | J4A-4 | J1A-4 | GND | 2 | — |
| 5 | J4A-5 | J1A-5 | GND (retorno analógico) | 3 | — |
| 6 | J4A-6 | J1A-6 | MQ_AN (en la placa 1: MQ_A0_RAW) | 3 | Sensores → central |
| 7 | J4B-1 | J1B-1 | CO2_RX (IO17 → Rx del sensor) | 4 | Central → sensores |
| 8 | J4B-2 | J1B-2 | CO2_TX (Tx del sensor → IO16) | 4 | Sensores → central |
| 9 | J4B-3 | J1B-3 | SR_TRIG | 5 | Central → sensores |
| 10 | J4B-4 | J1B-4 | SR_ECHO (en la placa 1: SR_ECHO_RAW) | 5 | Sensores → central |
| 11 | J4B-5 | J1B-5 | DHT_LINE | 6 | Bidireccional |
| 12 | J4B-6 | J1B-6 | GND | 6 | — |
| Pantalla | J4B-6 (junto con el polo 12) | Sin conectar: se corta y se aísla | — | — | — |

Reglas:

- La pantalla se conecta **solo en la unidad central**, para que no circule corriente por ella.
- Usa punteras en todos los conductores y anota en el cable el número de polo.
- En ambos extremos, la cubierta entra al gabinete por un prensaestopa IP68 M16. Sella la boca de la
  cubierta con termorretráctil con adhesivo.
- En el tramo exterior, pasa el cable por tubo flexible hermético (licuatite) y deja una gota de goteo
  antes de cada gabinete.

---

## 4. Arneses W2-W5: placa 2 ↔ sensores

Son de 30 cm, con cable UL1007 24 AWG y carcasas JST XH. El pin 1 siempre es +5 V.

| Arnés | Conector | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| W2 | J2 (MQ-4) | VCC | AO | sin conectar (DO) | GND |
| W3 | J3 (MH-Z19C) | Vin | Tx | Rx | GND |
| W4 | J4 (AJ-SR04M) | 5V | Trig | Echo | GND |
| W5 | J5 (DHT11) | VCC | DATA | GND | — |

---

## 5. Cambios en la placa 1 para el cable

| Ref. | Pieza | Conexión |
|---|---|---|
| J4A, J4B | Phoenix MKDS 1/ 6-3,5 (1751280) ×2 | Polos 1-12 del cable (tabla de la sección 3) |
| F4 | Bourns MF-R050 (PTC radial 0.5 A, 60 V) | +12V_LOAD → +12V_CBL. Va después del LVD, así que la placa 2 también se apaga cuando la batería está baja |
| Q3 | BSS138 | G a +3V3 · S a DHT_DATA · D a DHT_LINE |
| U5 | (ya existía) | Su pin 6 pasa de DHT_DATA a DHT_LINE, del lado del cable |

Los conectores locales MQ1, CO2, SR1 y DHT1 se quedan para pruebas en banco. **No conectes sensores en
ellos y en la placa 2 al mismo tiempo.**

---

## 6. Gabinetes y sellado

| Elemento | Unidad central (G1) | Placa 2 (G2) |
|---|---|---|
| Gabinete | IP65, ≈ 250 × 200 × 100 mm, con la batería de 7 Ah dentro | IP67 de policarbonato, ≈ 120 × 80 × 55 mm |
| Entrada del cable W1 | Prensaestopa IP68 M16 | Prensaestopa IP68 M16 |
| Otras entradas | Adaptador de 19 V e interruptor de panel | 4 prensaestopas M12 para los arneses y el cable del transductor |
| Respiradero | — | Membrana ePTFE M12: iguala la presión sin dejar entrar agua |
| Humedad | — | Bolsa de gel de sílice; cámbiala en cada mantenimiento |
| Recubrimiento | Opcional | Barniz conformal acrílico en la placa 2 y en los módulos de los sensores, sin tapar las ventanas de gas |
| Material | — | Prensaestopas de latón niquelado o acero inoxidable 316; el latón sin niquelar se corroe con el H₂S |

---

## 7. Sincronización con las hojas de datos

Cada valor del esquemático se comparó con la hoja de datos del fabricante.

| Pieza | Dato usado en el diseño | Hoja de datos | Estado |
|---|---|---|---|
| CN3767 | Pines 1-10, VCS 120 mV, 14.8/13.55 V, SSOP-10 de paso 1.0 mm | Consonance, rev. 1.0 | Coincide |
| AOD4185 | −40 V, 20 mΩ a −4.5 V, Qg 18.6 nC, ±20 V en la compuerta, TO-252 G-D-S | AOS, rev. 4.2 | Coincide |
| SRR1260-680M | 68 µH ±20 %, DCR 110 mΩ, Isat 2.1 A, Irms 2.1 A | Bourns | Coincide |
| TLV1701 | 1 IN+, 2 V−, 3 IN−, 4 OUT, 5 V+; salida de colector abierto hasta 36 V | TI SBOS589D | Coincide; el orden de pines **no** es el habitual de los comparadores |
| TLV431 | DBZ: 1 REF, 2 cátodo, 3 ánodo; 1.24 V | TI SLVS139Z | Coincide |
| TPD4E1U06 | 1 D1+, 2 GND, 3 D2+, 4 D2−, 5 NC, 6 D1−; 5.5 V | TI SLVSBQ9E | Coincide |
| SMBJ15A / 18A / 20A | VRWM 15/18/20 V; VC 24.4/29.2/32.4 V | Bourns | Coincide. Con 33 V de máximo en U2, el SMBJ20A deja 0.6 V de margen al pico de corriente nominal |
| BZT52C15 | 15 V (13.8-15.6), SOD-123 | Diodes Inc. | Coincide |
| MF-MSMF075-2 | 0.75 A / 1.5 A, 13.2 V máx. | Bourns | Coincide; va en el riel de 5 V |
| MF-R050 | 0.5 A / 1.0 A, 60 V máx., paso 5.1 mm | Bourns | Coincide; es el que admite los 14.8 V del cable |
| TSR 1-2450 | 6.5-36 V → 5 V 1 A; 1 +Vin, 2 GND, 3 +Vout | Traco | Coincide |
| TLV9001 | DBV: 1 OUT, 2 V−, 3 IN+, 4 IN−, 5 V+; 1.8-5.5 V | TI | Coincide; usar **TLV9001IDBVR**, no la variante «U» |
| SN74AHCT1G125 | 1 OE, 2 A, 3 GND, 4 Y, 5 VCC; entradas TTL | TI SCLS378P | Coincide |
| BSS138 | SOT-23: 1 G, 2 S, 3 D; VGS(th) 0.5-1.5 V | Diodes Inc. | Coincide |
| MQ-4 | Calentador 5.0 ± 0.1 V, 33 Ω; RL recomendada 20 kΩ (10-47 kΩ) | Hanwei | Revisa la RL de tu módulo: muchos traen 1 kΩ o 10 kΩ |
| MH-Z19C | 5.0 ± 0.1 V, UART de 3.3 V (tolera 5 V), pico de 125 mA | Winsen | Coincide |
| DHT11 | 3.3-5.5 V; 5.1 kΩ de pull-up hasta 20 m | Aosong | Coincide con la placa 2 |
| MBRS340T3G / MBRS360T3G | 3 A, 40/60 V, SMC | onsemi (bloqueó la descarga) | Familia confirmada en su biblioteca EAGLE; verifica la hoja al comprar |
| SB560 | 5 A, 60 V, DO-201AD | — | Se descargó la de la serie SB3xx; verifica la hoja al comprar |

---

## 8. Lista de materiales

La lista completa, con referencia, cantidad, fabricante, número de parte, encapsulado y si se verificó
contra la hoja de datos, está en [`BOM_v2.csv`](BOM_v2.csv).

| Grupo | Renglones | Piezas |
|---|---|---|
| Placa 1 (unidad central) | 49 | 75 |
| Placa 2 (interfaz de sensores) | 16 | 31 |
| Sensores | 4 | 4 |
| Cableado (W1-W7) | 9 | Por longitud |
| Mecánica y protección | 12 | — |

Los renglones sin número de parte (electrolíticos, gabinetes, prensaestopas, cable) llevan la
especificación completa; elige el código exacto con tu proveedor según disponibilidad.

---

## 9. Pruebas de la placa 2 y del cable

1. **Continuidad del cable:** cada polo de J4 con su polo de J1, ningún polo en corto con otro ni con la
   pantalla.
2. **Alimentación:** 12 V en J1A-1/2; en +5V, entre 4.9 y 5.1 V con los cuatro sensores conectados.
3. **Cable invertido:** con +12 V en el polo 3, la placa 2 no enciende y nada se calienta.
4. **MQ-4:** la tensión en MQ_AN (J1A-6) es igual a la de AO del módulo, ± 10 mV.
5. **UART:** el firmware lee el MH-Z19C igual que conectado directo.
6. **Ultrasónico:** con osciloscopio en J4B-3/J4B-4 de la placa 1, TRIG de 10 µs y ECHO proporcional a
   la distancia, con flancos limpios.
7. **DHT11:** 20 lecturas seguidas sin error de suma de verificación con el cable a su longitud final.
