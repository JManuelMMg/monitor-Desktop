"""Alimentación del esquemático definitivo: una sola placa, sin corte por bajo voltaje ni C1.

Cadena: UPS1 → J1 → F1 → S1 → +12V → MP1584 de 5 V → sensores, y → D1 → regulador de la DevKitC.
Los consumos y modelos vienen de simulacion_alimentacion_placas.py. Sin dependencias externas.

    python hardware/simulacion_placa_definitiva.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulacion_alimentacion_placas as sim  # noqa: E402

V_5V = 5.0
BUCK_LIMITE_A = 2.0       # A, nominal anunciado sin disipador; el máximo de 3 A pide disipador
CAP_ENTRADA_F = 22e-6     # F, capacitancia supuesta del módulo MP1584; medir o consultar el módulo
BATERIA_WH = 12.0 * 7     # Wh, batería de 12 V y 7 Ah
DESCARGA_SEGURA = 0.5     # profundidad de descarga recomendada para una AGM
LED_A = sim.ALARM_LED


def nodo(v_in: float, pico: bool, leds: int = 0) -> dict:
    i_sensores = sum((s.peak_a if pico else s.typ_a) for s in sim.SENSORS if s.ref != "DHT11")
    dht = next(s for s in sim.SENSORS if s.ref == "DHT11")
    i_3v3 = ((sim.ESP_3V3["pico"] if pico else sim.ESP_3V3["actual"]) + sim.DEVKIT_LED
             + LED_A * leds + (dht.peak_a if pico else dht.typ_a))
    i_ldo = i_3v3 + sim.LDO_IQ
    i_5v = i_sensores + i_ldo
    p_salida = i_5v * V_5V
    eficiencia = sim.buck_eff(i_5v)
    p_in = p_salida / eficiencia + v_in ** 2 / sim.VBAT_DIVIDER
    return {"v_in": v_in, "i_5v": i_5v, "eficiencia": eficiencia, "p_in": p_in, "i_in": p_in / v_in,
            "v_esp": V_5V - sim.schottky_vf(i_ldo), "v_ldo_margen": V_5V - sim.schottky_vf(i_ldo) - (sim.LDO_VOUT + sim.LDO_DROPOUT)}


def respaldo_ms(v0: float, p_w: float) -> float:
    """Tiempo que aguanta la capacitancia de entrada hasta bajar al mínimo del MP1584."""
    return CAP_ENTRADA_F * (v0 ** 2 - sim.V_BUCK_MIN ** 2) / (2 * p_w) * 1e3


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    casos = [("Típico, adaptador de 12 V", 12.0, False, 0), ("Pico, adaptador de 12 V", 12.0, True, 4),
             ("Pico, adaptador de 13.8 V", 13.8, True, 4), ("Típico, batería a 12.6 V", 12.6, False, 0),
             ("Pico, batería a 11 V", 11.0, True, 4)]
    for nombre, v, pico, leds in casos:
        n = nodo(v, pico, leds)
        print(f"{nombre:28} 5 V {n['i_5v']*1000:4.0f} mA ({n['i_5v']/BUCK_LIMITE_A*100:2.0f} % de {BUCK_LIMITE_A:.0f} A) · "
              f"entrada {n['i_in']*1000:4.0f} mA, {n['p_in']:.2f} W · F1 {n['i_in']/3*100:2.0f} % · "
              f"pin 5V {n['v_esp']:.2f} V · margen LDO {n['v_ldo_margen']:+.2f} V")
    tipico = nodo(12.6, False)
    print(f"\nAutonomía típica con 7 Ah: {BATERIA_WH * DESCARGA_SEGURA / tipico['p_in']:.0f} h hasta 50 % de descarga. "
          "Sin corte, el nodo sigue descargando la batería después de eso.")
    print(f"Respaldo durante el cambio de UPS1 con {CAP_ENTRADA_F*1e6:.0f} µF (supuestos): "
          f"{respaldo_ms(12.0, tipico['p_in']):.1f} ms típico · {respaldo_ms(12.0, nodo(12.0, True, 4)['p_in']):.1f} ms pico")
    print(f"Máximo en IO35 con 14.8 V: {14.8 * 22 / 122:.2f} V (R6 100 kΩ / R7 22 kΩ)")


if __name__ == "__main__":
    main()
