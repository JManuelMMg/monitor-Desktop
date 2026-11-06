# Revisión de la placa BiogasEmbebido, versión V51

Revisión de archivos: tablero V51 y esquemático V29 de Fusion, comparados con el firmware 3.1.0. No se ejecutó el DRC de
Fusion y nada se ha medido en banco. Los anchos de pista y la caída de voltaje suponen cobre de 1 oz.

**Dictamen: las conexiones están correctas, pero la placa no está lista para pedirse.**

## Lo que quedó correcto

- Las 24 redes con pads coinciden entre esquemático y tablero, sin redes abiertas, con 225 pistas en la cara superior y sin vías.
- Los pines del ESP32 coinciden con `firmware/esp32_node/config.h`.
- No se usan IO0, IO2, IO12 ni IO15. IO34 e IO35 están en ADC1, que sigue disponible con Wi-Fi.
- Divisores: el MQ-4 da 3.0 V a 5 V, el eco da 3.2 V y el bus de 13.8 V da 2.5 V en IO35.
- Alimentación calculada: 136 mA a 12 V en uso típico y 376 mA a 12 V en el peor caso.

## Hallazgos

| Gravedad | Hallazgo | Evidencia | Acción |
|---|---|---|---|
| Mayor | El MP1584 quedó pegado frente a la antena del ESP32 | `U$1` ocupa de y = 3.4 a 20.4; la huella de `U2` termina en y = 3.4. En V50 estaba en (90.5, 16) | Alejarlo de la antena y dejar libre la zona de la antena |
| Mayor | La caja ya no coincide con la placa | `J1` pasó de (38.25, 11.25) a (22.75, 3.75); la entrada de 12 V sigue en x = 38.25 | Mover la perforación después de fijar la colocación |
| Mayor | Hay un riesgo de seguridad si el MQ-4 recibe biogás sin diluir | Elemento caliente a unos 300 °C y metano; falta el sistema de dilución | Definir la toma de muestra antes de energizar junto al biogás |
| Menor | La ruta de +5 V es muy larga | 155 mm hasta D1 y 198 mm hasta el MQ-4: unos 40 mV típicos y más de 100 mV en picos | Reducir la ruta o ensanchar a 1 mm o más |
| Menor | No hay plano de GND | 0 polígonos; GND mide 248 mm en pistas | Evaluar un plano en la cara inferior, sin cobre bajo la antena |
| Menor | Holguras justas junto a los pines del ESP32 | Mínimo aproximado de 0.16 mm junto a `J3_11` | Correr el DRC y separar donde se pueda para soldar a mano |
| Menor | La entrada del ADC no tiene capacitor | R1 y R2 dan 60 kΩ en IO34, con 31 mm de pista | Evaluar 100 nF junto a IO34 |
| Menor | IO34 puede salir de la zona más exacta del ADC | A 11 dB, la zona recomendada llega a unos 2.45 V y el divisor llega a 3.0 V | Revisar el rango real con gas |
| Información | Queda una red vacía `N$1` | Sin pads ni pistas | Se puede eliminar |

## Dudas que se resuelven midiendo

- DHT11 a 3.3 V: el informe cita de 3.5 a 5.5 V.
- Disparo del AJ-SR04M con 3.3 V desde IO5.
- Resistencia de carga del módulo MQ-4 (`MQ4_RL_KOHM` supone 10 kΩ).
- Medidas físicas contra una impresión 1:1: MP1584 (pads a 19.0 × 13.07 mm), `J1` a 5.08 mm, `F1` a 21.9 mm.
- Orden de pines de cada arnés contra su módulo.
- Pruebas de `MODULOS_ALIMENTACION.md`, sección 7.

## Cambios en la versión V53

- `D1` pasó de (75.75, −49.00) a (77.42, −49.65) y los agujeros cambiaron a (18.60, −50.65), (18.83, 18.06),
  (91.12, −50.42) y (91.35, 17.54). `U$1` sigue en (71.75, 20.41), así que el hallazgo de la antena continúa.
- Las redes siguen completas y coinciden con el esquemático. La holgura mínima calculada bajó a 0.156 mm junto a `J2_17` y `J3_17`.
- El pad `D1.A` quedó a 3.82 mm del centro del agujero (91.12, −50.42) y una pista de +5 V a 3.0 mm: la cabeza de un
  tornillo M3 puede tocarlos.
- La caja se corrigió en `caja/Caja_base_V53.stl`: tres postes nuevos y entrada de 12 V en la pared izquierda.
- Decisión del autor: `U$1` se queda en su lugar. Riesgo aceptado: hay que probar la señal de Wi-Fi al armar el nodo.

Limitaciones ya aceptadas en el diseño: sin protección contra inversión, sin TVS, sin corte por bajo voltaje y reinicio
posible al conmutar a batería.
