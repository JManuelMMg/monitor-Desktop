# PCB v2 del nodo «BiogasEmbebido»: modelo comercial

> **Documento histórico:** el diseño definitivo es más simple y no incluye el cargador, el corte por bajo voltaje
> ni varias protecciones de aquí. Lo vigente está en [`MODULOS_ALIMENTACION.md`](MODULOS_ALIMENTACION.md) y
> [`BOM_v4_modulos.csv`](BOM_v4_modulos.csv).

Este documento describe lo que se agrega a la PCB v1 (esquemático de Fusion «BiogasEmbebido») para que el
nodo sea un producto que se pueda instalar y dejar trabajando sin supervisión. Incluye el circuito de cada
etapa, sus valores calculados, las conexiones pin a pin para dibujarlas en Fusion, la lista de materiales
que cambia y las pruebas de aceptación.

Los cálculos salen de [`simulacion_pcb_v2.py`](simulacion_pcb_v2.py), que reutiliza el modelo de consumo de
[`simulacion_energia.py`](simulacion_energia.py):

```bash
python hardware/simulacion_pcb_v2.py
```

## Estado en Fusion

Los cambios ya están aplicados en el diseño «BiogasEmbebido» abierto en Fusion, **sin guardar**. Si te
convencen, guarda el esquemático y la PCB; si no, ciérralos sin guardar y quedan como estaban.

- **Biblioteca:** [`biogas_v2.lbr`](biogas_v2.lbr) (ya incrustada en el diseño). Las huellas salen de las
  bibliotecas estándar de EAGLE (`ref-packages`, `diode`, `bourns-inductor`). La del CN3767 (SSOP-10 de
  paso 1.0 mm) se dibujó con las medidas de la página 12 de su hoja de datos. La asignación de pines del
  TLV1701, TLV431 y TPD4E1U06 se verificó en las hojas de datos de TI.
- **Esquemático:** la hoja 2 tiene las 38 piezas nuevas con todas sus conexiones. En la hoja 1 se
  reconectaron D1, D2, R6, C1, BUCK1, el pin 5V de U1, el 5 V de MQ1, CO2 y SR1, y se agregaron IO32 e
  IO33. R1/R2 pasan a 100 kΩ/150 kΩ y J3 dice «ADAPTADOR 19V». La revisión eléctrica (ERC) no marca
  errores.
- **PCB:** el contorno creció 45 mm hacia abajo (de 74 × 63 mm a 74 × 108.5 mm). La franja nueva lleva el
  cargador (izquierda) y el corte por bajo voltaje (derecha). U5 y U6 quedaron junto a los conectores de
  los sensores y C20 junto a R2. Los dos barrenos de montaje inferiores pasaron a las esquinas nuevas.
- **Falta rutear.** Se borraron las pistas de BAT_P, BAT_F, +12V, ADP_P y +5V porque esas redes
  cambiaron. Quedan 93 líneas de aire, incluidas todas las de la franja nueva. Rutea el cargador a mano
  siguiendo la sección 5; el autoruteador no respeta esas reglas.
- **Aperturas que se conservaron:** J2 sigue con la bornera de 5.08 mm y los sensores con sus tiras de
  pines de 2.54 mm. El XT60 y los JST XH de la sección 6 son opcionales y necesitan su propia huella.

- **Cable a la placa 2:** se agregaron J4A/J4B (bornera de 12 polos para el cable de sensores), F4 (PTC
  de 60 V que alimenta el cable) y Q3 (adaptador de nivel del DHT11). El pin 6 de U5 pasó al lado del
  cable. La placa de sensores, el cableado y la lista definitiva de materiales están en
  [`PLACA2_INTERFAZ.md`](PLACA2_INTERFAZ.md) y [`BOM_v2.csv`](BOM_v2.csv).

Las referencias nuevas empiezan en R20, C10, D10, U2, Q1, L1 y F3 para no chocar con la v1. Los nombres de
red son los mismos del esquemático: BAT_P es J2+ antes del fusible, BAT_F es después del fusible, +12V es
después de SW1 y ADP_P es J3+.

---

## 1. Qué le faltaba a la v1

| Problema en la v1 | Riesgo | Solución en la v2 |
|---|---|---|
| El adaptador de 13.8 V carga la batería por D1 (SB560), sin control | La batería queda al ≈90 %, sin límite de corriente; con la batería descargada el adaptador entrega lo que pueda | Cargador conmutado CC/CV **CN3767** (U2): 1 A, 14.8 V de sobrecarga y 13.55 V de flotación |
| Batería conectada al revés | Se dañan el buck, el TVS y el ESP32 | Conector polarizado **XT60** (J2), diodo de *crowbar* D1 y fusible F2 |
| Adaptador conectado al revés | Se dañan U2 y los capacitores | Diodo de bloqueo **D10** en serie con J3 |
| La batería se descarga hasta 0 V si se va la luz | Sulfatación: una AGM descargada a fondo pierde capacidad en pocos ciclos | Desconexión por bajo voltaje (**LVD**): U3 TLV1701 + U4 TLV431 + Q2 AOD4185 |
| USB de la DevKitC y +5 V de la placa en paralelo | Al programar con la placa encendida, una fuente alimenta a la otra | Diodo **D13** entre +5V y el pin 5V de la DevKitC |
| Corto en el cable de un sensor | Se cae todo el riel de 5 V y se reinicia el nodo | Fusible rearmable **F3** (PTC) en el riel de sensores |
| Descargas electrostáticas en cables largos | Se dañan los GPIO del ESP32 | Protección ESD **U5, U6** (TPD4E1U06) junto a los conectores |
| Divisor del MQ-4 de 10 kΩ/15 kΩ | Carga la resistencia de salida del módulo y altera la lectura | Divisor de 100 kΩ/150 kΩ con 100 nF (misma relación 0.6) |
| Conectores sin polarizar | Un sensor conectado al revés se quema | Conectores JST XH con traba |
| R6/R7 conectados directo a la batería | 103 µA de consumo aun con el nodo apagado | R6/R7 pasan a +12V (después de SW1) |

---

## 2. Arquitectura de alimentación

```
                    ┌────────────── Cargador U2 CN3767 ──────────────┐
J3 19 V ──D10──► VIN_CHG ──Q1──► SW_CHG ──L1──► CS_P ──R20──► BAT_F
                 │  D14 TVS        │ D11 a GND                     │
                 │  C10 C11 C12                                    │
                                                                   │
J2 XT60 ──F2 3 A────────────────────────────────────────────────► BAT_F
                                                   D1 crowbar, D2 TVS
BAT_F ──SW1──► +12V ──Q2 (LVD: U3, U4)──► +12V_LOAD ──C1── BUCK1 ──► +5V
                 │ R6/R7 → IO35                                       │
                                                         ┌────────────┴────────────┐
                                                     D13 ▼                      F3 ▼
                                               5V_ESP (U1 DevKitC)       +5V_SENS (sensores)
```

- El cargador queda **antes de SW1**: la batería se carga aunque el nodo esté apagado.
- El LVD queda **solo en la rama de carga**: si corta, el cargador sigue funcionando y la batería se
  recupera sola cuando vuelve la luz.
- R20 mide la corriente que va a la batería **más** la del nodo. Con el nodo encendido, la batería recibe
  ≈0.88 A de los 1.0 A programados.

---

## 3. Etapas

### 3.1 Cargador CC/CV (U2, CN3767)

**Valores calculados** (adaptador de 19 V, batería AGM de 12 V y 7 Ah)

| Parámetro | Valor | Cómo sale |
|---|---|---|
| Corriente de carga | 1.0 A (≈0.14 C) | R20 = 0.120 V / 1.0 A = **0.120 Ω**, disipa 0.12 W |
| Sobrecarga / flotación | 14.8 V / 13.55 V | Fijos en el CN3767 (para plomo-ácido de 12 V) |
| Precarga (goteo) | 175 mA si la batería está bajo 11.10 V | 17.5 % de la corriente programada |
| Pasa a flotación | cuando la corriente baja a 380 mA | 38 % de la corriente programada |
| Vuelve a cargar | si la batería baja de 12.42 V | 83.95 % de 14.8 V |
| Ciclo de trabajo | 81.4 % (máx. 94 %) | Adaptador mínimo para cargar a 14.8 V: **16.5 V** |
| Umbral de entrada (MPPT) | 15.06 V | 1.205 × (1 + 1.15 MΩ / 100 kΩ); si el adaptador se cae bajo este voltaje, U2 reduce la corriente |
| Rizado en L1 | 145 mA (peor caso 297 mA) | Objetivo de la hoja de datos: ≤ 0.3 × 1 A = 300 mA |
| Pico en L1 | 1.15 A | SRR1260-680M satura a 2.1 A |
| Regla L > 5(VCC − VBAT) µH | 68 µH la cumple con VBAT ≥ 5.9 V | Una batería bajo 6 V ya no se recupera, y el LVD impide llegar ahí |
| Eficiencia a 1 A | 92.5 % (14.1 W de entrada, 0.74 A del adaptador) | Pérdidas: conmutación de Q1 0.28 W, D10 0.37 W, D11 0.13 W, R20 0.12 W, L1 0.11 W |

**Adaptador:** 19 V y al menos 1.5 A (los de laptop sirven). El de 13.8 V de la v1 **ya no sirve**: no
alcanza los 16.5 V que necesita el cargador.

**Conexiones de U2 (CN3767, SSOP-10)**

| Pin | Nombre | Red | Conexión |
|---|---|---|---|
| 1 | VG | VG_CHG | C13 100 nF/50 V entre VG y **VIN_CHG** (no a GND) |
| 2 | GND | AGND | Tierra analógica; mucho cobre alrededor (disipa calor) |
| 3 | CHRG | CHG_STAT | U1 IO32 y R24 10 kΩ a +3V3. Drenador abierto: **bajo = cargando** |
| 4 | DONE | CHG_DONE | U1 IO33 y R25 10 kΩ a +3V3. Drenador abierto: **bajo = carga completa (flotación)** |
| 5 | COM | COMP_CHG | R21 120 Ω en serie con C16 220 nF hacia el pin 2 |
| 6 | MPPT | MPPT_CHG | R22 1.15 MΩ 1 % desde VIN_CHG y R23 100 kΩ 1 % a AGND, pegados al pin |
| 7 | BAT | BAT_F | Conexión Kelvin al lado de la batería de R20 |
| 8 | CSP | CS_P | Conexión Kelvin al lado de la bobina de R20 |
| 9 | VCC | VIN_CHG | Directo, con C12 100 nF junto al pin |
| 10 | DRV | DRV_CHG | Compuerta de Q1 |

Si CHRG y DONE están los dos en alto, no hay adaptador (U2 en reposo).

**Etapa de potencia**

| Ref. | Pieza | Conexión |
|---|---|---|
| D10 | Schottky MBRS360T3G (60 V, 3 A, SMC) | Ánodo a J3+, cátodo a VIN_CHG. Bloquea el adaptador invertido y el retorno hacia J3 |
| D14 | TVS SMBJ20A | Cátodo a VIN_CHG, ánodo a GND. Recorta picos al conectar el adaptador (U2 aguanta 33 V) |
| C10 | 100 µF/35 V electrolítico de baja ESR, rizado ≥ 0.6 A | VIN_CHG a PGND |
| C11 | 10 µF/50 V X7R (1210) | VIN_CHG a PGND, junto a la fuente de Q1 |
| C12 | 100 nF/50 V X7R (0603) | VIN_CHG a AGND, junto al pin 9 |
| Q1 | AOD4185 (P-MOSFET, −40 V) | S a VIN_CHG, G a DRV_CHG, D a SW_CHG |
| D11 | Schottky MBRS340T3G (40 V, 3 A) | Cátodo a SW_CHG, ánodo a PGND |
| L1 | Bourns SRR1260-680M (68 µH) | SW_CHG a CS_P |
| R20 | 0.120 Ω 1 %, ≥ 0.5 W (2010) | CS_P a BAT_F |
| C14 | 10 µF/35 V electrolítico | BAT_F a PGND, junto a R20 |
| C15 | 4.7 µF/50 V X7R (1210) | BAT_F a PGND |

> El D1 de la figura 1 de la hoja de datos (en serie con el drenador de Q1) se omite, como permite la
> propia hoja de datos (pág. 9). Sin él, U2 toma unos 52 µA de la batería cuando no hay adaptador.
> Con el divisor MPPT de 1.25 MΩ y la fuga del TVS, la placa apagada consume en total **63 µA
> (0.55 Ah al año)**, menos que la autodescarga de la propia AGM.

> **Limitación:** el CN3767 no compensa la temperatura. Si el gabinete pasa de 35 °C seguido, el voltaje
> de sobrecarga queda un poco alto. Ubica la batería a la sombra y ventilada.

### 3.2 Entrada de batería y protección contra inversión

| Ref. | Pieza | Conexión |
|---|---|---|
| J2 | Amass XT60PW-M (macho, para PCB) | BAT+ a BAT_P, BAT− a GND. Solo entra en un sentido |
| F2 | Fusible de 3 A rápido, 5×20 mm (el de la v1) | BAT_P a BAT_F |
| D1 | SB560 (**el mismo de la v1, con otra conexión**) | Cátodo a BAT_F, ánodo a GND: *crowbar* |
| D2 | SMBJ15A (se conserva) | Cátodo a BAT_F, ánodo a GND |

Si alguien arma un cable al revés, D1 conduce, la corriente sube a cientos de amperes y F2 se funde en
milisegundos, antes de que llegue voltaje negativo al resto de la placa. Se cambia F2 y listo.

¿Por qué no un MOSFET de protección (más eficiente)? Porque el cargador alimenta BAT_F desde el lado de la
placa. Con la batería al revés y el adaptador conectado, la compuerta quedaría polarizada y el MOSFET
conduciría, así que el cargador alimentaría a la batería invertida. El *crowbar* con fusible no tiene ese
problema.

### 3.3 Desconexión por bajo voltaje (U3, U4, Q2)

**Funcionamiento:** U3 compara una fracción del voltaje del bus (IN−) con 1.24 V de U4 (IN+). Con la
batería sana, IN− > IN+, la salida de U3 se va a bajo y enciende a Q2. Cuando la batería baja del umbral,
la salida queda abierta, R32 apaga a Q2 y R30 sube IN+, lo que crea la histéresis.

| Parámetro | Valor |
|---|---|
| Corta la carga | **11.64 V** |
| Reconecta | **12.37 V** (histéresis de 0.73 V) |
| VGS de Q2 encendido | −11.5 V a 12.6 V (−13.7 V en la sobrecarga; límite del AOD4185: ±20 V) |
| Consumo propio | 322 µA (0.2 % del consumo del nodo) |
| Corriente de U4 al cortar | 127 µA (el TLV431 necesita al menos 100 µA) |

La reconexión se fijó bajo 12.4 V a propósito: una AGM en reposo con más del 60 % de carga siempre
arranca el nodo al cerrar SW1. Si al encender la batería está entre 11.6 y 12.4 V, el nodo puede
quedarse apagado hasta conectar el adaptador. Esto es intencional.

**Conexiones** (pines verificados en las hojas de datos de TI; ojo, el TLV1701 en SOT-23-5 no usa el orden
habitual de los comparadores)

| Ref. | Pieza | Conexión |
|---|---|---|
| U3 | TLV1701 (SOT-23-5, DBV) | 1 IN+ a LVD_INP · 2 V− a GND · 3 IN− a LVD_DIV · 4 OUT a LVD_OUT · 5 V+ a +12V |
| C17 | 100 nF/50 V | +12V a GND, junto a V+ de U3 |
| U4 | TLV431 (SOT-23-3, DBZ) | 1 REF y 2 cátodo juntos a VREF_LVD · 3 ánodo a GND |
| R26 | 82 kΩ | +12V a VREF_LVD (polariza a U4) |
| R27 | 845 kΩ 1 % | +12V a LVD_DIV |
| R28 | 100 kΩ 1 % | LVD_DIV a GND |
| C18 | 100 nF | LVD_DIV a GND (filtro de 9 ms contra los picos del WiFi) |
| R29 | 10 kΩ 1 % | VREF_LVD a LVD_INP |
| R30 | 1.5 MΩ 1 % | LVD_OUT a LVD_INP (histéresis) |
| R31 | 10 kΩ | LVD_OUT a Q2_G |
| R32 | 100 kΩ | Q2_G a +12V (apaga a Q2 si U3 no lo jala) |
| D15 | Zener BZT52C15 (15 V) | Cátodo a +12V, ánodo a Q2_G (protege la compuerta) |
| Q2 | AOD4185 | S a +12V · D a +12V_LOAD · G a Q2_G |

### 3.4 Carga, 5 V y medición de batería

| Ref. | Pieza | Cambio |
|---|---|---|
| SW1 | Interruptor (v1) | Ahora va de BAT_F a +12V |
| C1 | 470 µF/25 V (v1) | Ahora en +12V_LOAD, a la entrada de BUCK1 |
| BUCK1 | Reductor a 5 V (v1) | Entrada en +12V_LOAD. Ajústalo a **5.0 V**: el MQ-4 y el MH-Z19C piden 5.0 ± 0.1 V. Para producción conviene un módulo regulador encapsulado de 5 V y 2 A con entrada de hasta 36 V (por ejemplo, la serie TSR 2 de Traco) en lugar del módulo genérico |
| D13 | Schottky MBRS340T3G | Ánodo a +5V, cátodo a 5V_ESP (pin 5V de la DevKitC). En los picos del WiFi deja 4.63 V, suficiente para el regulador de la DevKitC |
| F3 | PTC Bourns MF-MSMF075-2 (0.75 A) | +5V a +5V_SENS. Los sensores toman ≈0.33 A en el pico |
| C21 | 10 µF/16 V X7R | +5V_SENS a GND, junto a los conectores |
| R6/R7, C3 | Divisor de 100 kΩ/22 kΩ (v1) | El extremo superior pasa de BAT_P (antes del fusible) a **+12V**. Máximo en IO35: 2.71 V con 15.0 V |

### 3.5 Señales de sensores, ESD y conectores

**Divisor del MQ-4:** R1 pasa a 100 kΩ y R2 a 150 kΩ (5.0 V → 3.0 V). Se agrega C20 de 100 nF de MQ_ADC
a GND, junto a IO34. Como la relación sigue en 0.6, el firmware no cambia.

**ESD:** U5 y U6 (TPD4E1U06) van a menos de 5 mm de los conectores, en el lado del cable (antes de los
divisores), con su pin GND a un via directo al plano.

| Chip | Pin 1 (D1+) | Pin 3 (D2+) | Pin 4 (D2−) | Pin 6 (D1−) |
|---|---|---|---|---|
| U5 | MQ_A0_RAW | SR_TRIG | SR_ECHO_RAW (antes de R3/R4) | DHT_DATA |
| U6 | CO2_TX | CO2_RX | sin conectar | sin conectar |

En los dos, el pin 2 va a GND y el pin 5 (NC) queda libre.

**Conectores** (JST XH de 2.5 mm con traba). El pin 1 siempre es alimentación y el último siempre es GND,
para que todos los cables se armen igual:

| Ref. | Pieza | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| MQ1 | B4B-XH-A(LF)(SN) | +5V_SENS | MQ_A0_RAW | sin conectar (DO) | GND |
| SR1 | B4B-XH-A(LF)(SN) | +5V_SENS | SR_TRIG | SR_ECHO_RAW | GND |
| CO2 | B4B-XH-A(LF)(SN) | +5V_SENS | CO2_TX (IO17 → RX del sensor) | CO2_RX (IO16 ← TX del sensor) | GND |
| DHT1 | B3B-XH-A(LF)(SN) | VCC del DHT (igual que en la v1) | DHT_DATA | GND | — |

---

## 4. Lista de redes nuevas o modificadas

| Red | Conecta |
|---|---|
| ADP_P | J3+, ánodo de D10 |
| VIN_CHG | Cátodo de D10, cátodo de D14, C10, C11, C12, C13, U2-9 (VCC), fuente de Q1, R22 |
| VG_CHG | U2-1 (VG), C13 |
| DRV_CHG | U2-10 (DRV), compuerta de Q1 |
| SW_CHG | Drenador de Q1, cátodo de D11, L1 |
| CS_P | L1, R20 (lado de la bobina), U2-8 (CSP) |
| BAT_P | J2 BAT+, F2 |
| BAT_F | F2, R20 (lado de la batería), U2-7 (BAT), C14, C15, cátodo de D1, cátodo de D2, SW1 |
| COMP_CHG | U2-5 (COM), R21 |
| COMP_RC | R21, C16 |
| MPPT_CHG | U2-6 (MPPT), R22, R23 |
| CHG_STAT | U2-3 (CHRG), R24, U1 IO32 |
| CHG_DONE | U2-4 (DONE), R25, U1 IO33 |
| +12V | SW1, fuente de Q2, R32, cátodo de D15, U3 V+, C17, R26, R27, R6 |
| VREF_LVD | Cátodo y REF de U4, R26, R29 |
| LVD_DIV | U3 IN−, R27, R28, C18 |
| LVD_INP | U3 IN+, R29, R30 |
| LVD_OUT | U3 OUT, R30, R31 |
| Q2_G | Compuerta de Q2, R31, R32, ánodo de D15 |
| +12V_LOAD | Drenador de Q2, C1, entrada de BUCK1 |
| +5V | Salida de BUCK1, ánodo de D13, F3 |
| 5V_ESP | Cátodo de D13, pin 5V de U1 |
| +5V_SENS | F3, C21, pin 1 de MQ1, SR1 y CO2 |
| MQ_A0_RAW | MQ1-2, U5 canal 1, R1 |
| MQ_ADC | R1, R2, C20, U1 IO34 |
| AGND / PGND | Se unen en un solo punto junto al pin 2 de U2 y de ahí van al plano GND |

---

## 5. Reglas de trazado

Del cargador (hoja de datos del CN3767, sección *PCB Layout Considerations*):

1. El lazo C11 → Q1 → D11 lo más corto posible. El positivo de C11 va pegado a la fuente de Q1.
2. C16 (COM) regresa directo al pin 2 de U2, no al plano general.
3. Las tierras de C10, C11, C14, C15 y D11 se juntan en el mismo cobre (PGND) antes de ir al plano.
4. AGND (U2-2, C16, R23, C12) y PGND llegan al plano GND por caminos separados.
5. Mucho cobre alrededor del pin 2 de U2 y en los pads de Q1 y D11: es su disipador.
6. R20 justo a la salida de L1. Las pistas de CSP y BAT salen de los extremos de R20 (Kelvin), juntas
   como par, en la misma capa y sin compartir corriente de carga.
7. El nodo SW_CHG debe ser pequeño y estar lejos de LVD_DIV, LVD_INP, MPPT_CHG y de las señales de los
   sensores, que son de alta impedancia.

Generales:

- F2, D1 y D2 junto a J2. D10 y D14 junto a J3.
- Pistas de batería y del cargador (BAT_P, BAT_F, VIN_CHG, SW_CHG, CS_P) de al menos 1.5 mm en cobre de
  1 oz. Para +12V_LOAD y +5V basta con 0.8 mm.
- Puntos de prueba: VIN_CHG, BAT_F, +12V, +12V_LOAD, +5V, 5V_ESP, +3V3, CHG_STAT, CHG_DONE y GND.
- En la serigrafía: polaridad de J2 y J3, «19 V ⎓», valor de F2 y versión de la placa.
- Tres marcas fiduciales y barrenos M3 en las esquinas para el gabinete.

---

## 6. Lista de materiales: cambios respecto a la v1

La lista definitiva del sistema completo (placa 1, placa 2, sensores, cableado y mecánica) está en
[`BOM_v2.csv`](BOM_v2.csv). Esta sección solo resume lo que cambia en la placa 1.

**Se agregan**

| Ref. | Cant. | Pieza | Huella en Fusion |
|---|---|---|---|
| U2 | 1 | CN3767 (SSOP-10) | SSOP-10 paso 1.0 mm (dibujada de la hoja de datos) |
| Q1, Q2 | 2 | AOD4185 (TO-252) | DPAK (TO-252) |
| U3 | 1 | TLV1701 (SOT-23-5) | SOT23-5L |
| U4 | 1 | TLV431 | SOT23 |
| L1 | 1 | Bourns SRR1260-680M | SRR1260 |
| U5, U6 | 2 | TPD4E1U06 | SC70-6L |
| D10 | 1 | MBRS360T3G (también sirve MBRS340T3G, con menos margen ante un adaptador invertido) | SMC |
| D11, D13 | 2 | MBRS340T3G | SMC |
| D14 | 1 | SMBJ20A | SMB |
| D15 | 1 | BZT52C15 (SOD-123) | SOD123 |
| F3 | 1 | Bourns MF-MSMF075-2 (1812) | 1812 |
| R20 | 1 | 0.120 Ω 1 % ≥ 0.5 W (2010) | 2010 |
| R21 | 1 | 120 Ω | 0805 |
| R22 | 1 | 1.15 MΩ 1 % | 0805 |
| R23, R28 | 2 | 100 kΩ 1 % | 0805 |
| R24, R25, R29, R31 | 4 | 10 kΩ (R29 al 1 %) | 0805 |
| R26 | 1 | 82 kΩ | 0805 |
| R27 | 1 | 845 kΩ 1 % | 0805 |
| R30 | 1 | 1.5 MΩ 1 % | 0805 |
| R32 | 1 | 100 kΩ | 0805 |
| C10 | 1 | 100 µF/35 V electrolítico, baja ESR | Radial 8 mm, paso 3.5 mm |
| C11 | 1 | 10 µF/50 V X7R (1210) | 1210 |
| C12, C13, C17, C18, C20 | 5 | 100 nF/50 V X7R | 0805 |
| C14 | 1 | 10 µF/35 V electrolítico | Radial 5 mm, paso 2 mm |
| C15 | 1 | 4.7 µF/50 V X7R (1210) | 1210 |
| C16 | 1 | 220 nF/50 V X7R | 0805 |
| C21 | 1 | 10 µF/16 V X7R | 0805 |

**Cambian**

| Ref. | v1 | v2 |
|---|---|---|
| J2 | Bornera de 5.08 mm | Amass XT60PW-M (opcional; en Fusion sigue la bornera) |
| J3 | Bornera para 13.8 V | La misma bornera, ahora para 19 V (o bornera enchufable con traba) |
| D1 | SB560 de J3 a la batería | El mismo SB560 como *crowbar* (cátodo a BAT_F, ánodo a GND) |
| R1 / R2 | 10 kΩ / 15 kΩ | 100 kΩ / 150 kΩ |
| R6 | Desde BAT_P | Desde +12V |
| MQ1, SR1, CO2 | Tira de pines de 2.54 mm | JST B4B-XH-A(LF)(SN) (opcional; en Fusion sigue la tira de pines) |
| DHT1 | Tira de pines de 2.54 mm | JST B3B-XH-A(LF)(SN) (opcional; en Fusion sigue la tira de pines) |
| Adaptador | 13.8 V | 19 V, ≥ 1.5 A |

**Se quita:** la conexión directa J3 → D1 → batería.

---

## 7. Resultados de la simulación

| Concepto | v1 | v2 |
|---|---|---|
| Consumo del nodo (desde la batería) | 1.662 W (132 mA) | 1.693 W (134 mA) |
| Autonomía con AGM de 7 / 12 / 18 Ah (50 % de descarga) | 25.3 h / 43.3 h / 65.0 h | 24.8 h / 42.5 h / 63.8 h |
| Recarga desde 50 % (7 / 12 / 18 Ah) | ≈3.3 h / 5.6 h / 8.5 h, sin límite de corriente y solo hasta ≈90 % | ≈6.1 h / 10.5 h / 15.7 h a 1 A, completa y con flotación |
| Consumo con la placa apagada (sin adaptador) | 103 µA (divisor R6/R7) | 63 µA |
| Desde la red por nodo, con adaptador | 1.96 W | 2.48 W (22 kWh al año) |
| Sistema de 6 nodos + Raspberry Pi | 15.7 W (138 kWh al año) | 18.9 W (165 kWh al año) |

El consumo desde la red sube porque ahora la energía pasa por el cargador (≈85 % de eficiencia con la
carga ligera del nodo) y la batería se mantiene en flotación.

---

## 8. Pruebas de aceptación en banco

Hazlas con una fuente de laboratorio con límite de corriente antes de conectar una batería real.

1. **Inversión de batería.** Fuente de 12 V limitada a 2 A, conectada al revés en J2 con F2 puesto. Debe
   conducir D1 y la fuente debe entrar en límite (con 2 A, F2 no alcanza a fundirse). En +12V no debe
   haber más de −1 V.
2. **Adaptador invertido.** 19 V al revés en J3: VIN_CHG queda en 0 V (o en el voltaje de la batería
   menos un diodo, si hay batería).
3. **LVD.** Fuente en J2, sin adaptador. Baja el voltaje de 12.6 V: Q2 debe abrir cerca de 11.6 V. Súbelo:
   debe cerrar cerca de 12.4 V.
4. **Cargador.** Batería AGM descargada a unos 12.0 V y amperímetro en serie con J2. Al conectar el
   adaptador: ≈0.88 A hacia la batería con el nodo encendido, CHRG en bajo y luego 14.8 V. Al terminar,
   la corriente cae, DONE pasa a bajo y el voltaje queda en 13.55 V.
5. **USB.** Con SW1 apagado, conecta el USB de la DevKitC: +5V y +5V_SENS deben quedar en 0 V, porque
   D13 bloquea el retorno. Con SW1 encendido y el USB conectado, el nodo debe funcionar normal.
6. **Corto en un sensor.** Pon en corto +5V_SENS con GND: F3 se abre y el ESP32 sigue conectado al
   broker. Al quitar el corto, F3 se rearma.

---

## 9. Cambios en el firmware

En `firmware/esp32_node/config.h`:

- Entradas nuevas: `PIN_CHG_STAT 32` y `PIN_CHG_DONE 33`, activas en bajo. Estados que se publican:
  «cargando» (CHRG bajo), «cargada» (DONE bajo) o «sin adaptador» (las dos en alto).
- Medición de batería en IO35 con factor 122/22. Se publica una alarma de batería baja a 11.9 V, antes
  de que el LVD corte a 11.6 V.
- Revisa que los demás pines del firmware coincidan con la PCB (DHT11, LED de alarma).

---

## 10. Fuera del alcance de la PCB

- **Atmósferas explosivas.** El biogás contiene metano. Si el nodo va dentro de una zona clasificada
  cerca del digestor, el gabinete y la instalación deben cumplir la norma para atmósferas explosivas que
  aplique. La PCB no lo resuelve.
- **Gabinete IP65**, con prensaestopas para los cables de los sensores y la batería fuera del gabinete
  electrónico.
- **Rango de los sensores.** El MH-Z19C mide hasta 5 % de CO₂, y el biogás tiene entre 30 y 45 %. Para
  medir el gas del digestor (no el ambiente) hace falta un sensor NDIR de rango alto.
- **Certificación de compatibilidad electromagnética**, si el producto se va a vender.
