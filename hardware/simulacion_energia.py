"""Simulación de consumo y presupuesto energético del nodo «BiogasEmbebido».

Fuente del circuito: esquemático de Fusion (documento BiogasEmbebido, 30 partes,
24 redes) SIN panel solar: el nodo funciona con su batería de 12 V (J2) y el
adaptador de 13,8 V (J3, por D1) la recarga. Corrientes: valores típicos y
máximos de las hojas de datos; cámbialos aquí cuando midas el prototipo real
con un multímetro o un medidor USB.

    python hardware/simulacion_energia.py            # tablas en consola
    python hardware/simulacion_energia.py --json     # resultados en JSON

Sin dependencias externas.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

# ----------------------------------------------------------------- supuestos
V_BAT_NOM = 12.6          # V, tensión media de batería en descarga
V_5V = 5.0                # salida del BUCK1
V_3V3 = 3.3               # LDO AMS1117 de la placa ESP32-DevKitC
BUCK_EFF = 0.85           # eficiencia típica de un módulo buck 12→5 V a 0,2-0,8 A
LDO_IQ_A = 0.005          # A: corriente de reposo del AMS1117
DIVIDER_R = 122_000       # R6 + R7, medición de batería (siempre conectada)
V_ADAPTER = 13.8          # V, adaptador J3
D1_DROP = 0.45            # V, Schottky SB560 a ~1 A
ADAPTER_EFF = 0.85        # eficiencia de un adaptador de red 13,8 V típico
ADAPTER_MAX_A = 2.0       # A, corriente máxima del adaptador (ajústalo al tuyo)
HOURS = 24


@dataclass
class Load:
    ref: str
    name: str
    rail: str           # "5V" o "3V3"
    typ_a: float        # corriente media en servicio continuo
    peak_a: float       # pico (arranque, transmisión WiFi, calentamiento…)
    source: str         # de dónde sale el dato


LOADS = [
    Load("U1", "ESP32-WROOM-32E (DevKitC) con WiFi + MQTT/TLS", "3V3", 0.070, 0.450,
         "Hoja de datos ESP32-WROOM-32E: TX 802.11b ≈240 mA, RX ≈100 mA, modem-sleep 20-30 mA; "
         "media estimada con el ahorro de energía WiFi por defecto de Arduino y publicación cada 5 s"),
    Load("U1-LED", "LED de encendido de la DevKitC", "3V3", 0.002, 0.002, "LED rojo de placa, ≈2 mA"),
    Load("DHT1", "DHT11 + pull-up R5 10k", "3V3", 0.0004, 0.0025,
         "Hoja de datos DHT11: 0,3-2,5 mA midiendo, 0,1-0,15 mA en reposo"),
    Load("LED1-4", "4 LEDs de alerta (RL 330 Ω)", "3V3", 0.0, 0.016,
         "(3,3 V − 2,0 V)/330 Ω ≈ 4 mA c/u; normalmente apagados, pico con las 4 alarmas"),
    Load("MQ1", "MQ-4 (calefactor 33 Ω + comparador + LED del módulo)", "5V", 0.157, 0.170,
         "Hoja de datos MQ-4: calefactor 33 Ω ±5 % a 5 V → 150 mA, ≤750 mW; módulo +≈7 mA"),
    Load("CO2", "MH-Z19C (NDIR)", "5V", 0.040, 0.125,
         "Hoja de datos Winsen MH-Z19C: media <40 mA, pico 125 mA"),
    Load("SR1", "AJ-SR04M (ultrasonido)", "5V", 0.008, 0.030,
         "Hoja de datos AJ-SR04M: reposo ≈5 mA, trabajando <30 mA (1 medida/intervalo)"),
]

# Baterías de 12 V habituales: (nombre, tensión nominal, Ah, profundidad de descarga útil)
BATTERIES = [
    ("AGM plomo-ácido 12 V 7 Ah", 12.0, 7, 0.5),
    ("AGM plomo-ácido 12 V 12 Ah", 12.0, 12, 0.5),
    ("AGM plomo-ácido 12 V 18 Ah", 12.0, 18, 0.5),
    ("LiFePO4 12,8 V 6 Ah", 12.8, 6, 0.8),
    ("LiFePO4 12,8 V 12 Ah", 12.8, 12, 0.8),
    ("LiFePO4 12,8 V 20 Ah", 12.8, 20, 0.8),
]

# Raspberry Pi 4B central (red eléctrica, fuente oficial 5 V 3 A).
PI_W_TYP = 3.4
PI_W_PEAK = 6.4
PI_PSU_EFF = 0.85

SCENARIOS = {
    "actual": {"label": "Firmware actual (WiFi con ahorro por defecto)", "esp_a": 0.070, "leds_on": 0},
    "sin_ahorro": {"label": "WiFi sin ahorro (peor caso continuo)", "esp_a": 0.130, "leds_on": 0},
    "optimizado": {"label": "Optimizado (modem-sleep y LEDs apagados)", "esp_a": 0.040, "leds_on": 0},
    "alarma": {"label": "Las 4 alarmas encendidas", "esp_a": 0.070, "leds_on": 4},
}


def node_budget(esp_a: float, leds_on: int) -> dict:
    """Corrientes por riel y potencia tomada de la batería (entrada 12 V)."""
    i_3v3 = 0.0
    i_5v_direct = 0.0
    for load in LOADS:
        a = load.typ_a
        if load.ref == "U1":
            a = esp_a
        if load.ref == "LED1-4":
            a = 0.004 * leds_on
        if load.rail == "3V3":
            i_3v3 += a
        else:
            i_5v_direct += a
    i_ldo_in = i_3v3 + LDO_IQ_A          # el LDO es lineal: entra lo mismo que sale + reposo
    i_5v = i_5v_direct + i_ldo_in
    p_5v = i_5v * V_5V
    p_3v3 = i_3v3 * V_3V3
    p_in_buck = p_5v / BUCK_EFF
    p_divider = V_BAT_NOM ** 2 / DIVIDER_R
    p_total = p_in_buck + p_divider
    return {
        "i_3v3_a": i_3v3, "i_5v_a": i_5v, "p_5v_w": p_5v, "p_3v3_w": p_3v3,
        "p_ldo_loss_w": i_ldo_in * V_5V - p_3v3, "p_buck_loss_w": p_in_buck - p_5v,
        "p_divider_w": p_divider, "p_total_w": p_total, "i_bat_a": p_total / V_BAT_NOM,
        "wh_day": p_total * HOURS, "ah_day": p_total / V_BAT_NOM * HOURS,
        "kwh_year": p_total * HOURS * 365 / 1000,
        # Con el adaptador conectado siempre, la energía sale de la red:
        "grid_w": p_total / ADAPTER_EFF,
        "grid_kwh_year": p_total / ADAPTER_EFF * HOURS * 365 / 1000,
    }


def node_peak() -> dict:
    i_3v3 = sum(l.peak_a for l in LOADS if l.rail == "3V3")
    i_5v = sum(l.peak_a for l in LOADS if l.rail == "5V") + i_3v3 + LDO_IQ_A
    p_in = i_5v * V_5V / BUCK_EFF
    return {"i_3v3_a": i_3v3, "i_5v_a": i_5v, "p_in_w": p_in, "i_12v_a": p_in / 11.5}


def autonomy(p_w: float) -> list[dict]:
    """Horas que aguanta cada batería sin adaptador."""
    out = []
    for name, v, ah, dod in BATTERIES:
        wh_usable = v * ah * dod
        hours = wh_usable / p_w
        out.append({"battery": name, "wh_usable": wh_usable, "hours": hours, "days": hours / 24})
    return out


def charging(p_w: float) -> dict:
    """Recarga por J3 (13,8 V) a través de D1 directamente sobre la batería."""
    v_bat_float = V_ADAPTER - D1_DROP
    i_load = p_w / v_bat_float
    i_charge = max(0.0, ADAPTER_MAX_A - i_load)
    rows = []
    for name, v, ah, dod in BATTERIES:
        lead = name.startswith("AGM")
        eff = 0.85 if lead else 0.95            # eficiencia de carga (Ah)
        ah_needed = ah * dod / eff
        # La corriente cae al acercarse a 13,35 V: se estima 1,5× el tiempo a corriente máxima.
        hours = ah_needed / i_charge * 1.5 if i_charge else float("inf")
        rows.append({"battery": name, "ah_to_recharge": ah_needed, "hours": hours})
    return {
        "v_at_battery": v_bat_float,
        "i_load_a": i_load,
        "i_charge_a": i_charge,
        "note_agm": "13,35 V queda por debajo de la flotación de una AGM (13,5-13,8 V): carga al ≈90 %.",
        "note_lfp": "13,35 V es ≈95 % de carga en LiFePO4; sin limitación de corriente ni corte de carga.",
        "rows": rows,
    }


def dividers() -> list[dict]:
    def div(v_in, r_top, r_bot):
        return v_in * r_bot / (r_top + r_bot)
    return [
        {"red": "MQ_ADC (IO34)", "parts": "R1 10k / R2 15k", "v_in_max": 5.0, "v_out": div(5.0, 10e3, 15e3),
         "ok": div(5.0, 10e3, 15e3) <= 3.3},
        {"red": "SR_ECHO (IO18)", "parts": "R3 1.8k / R4 3.3k", "v_in_max": 5.0, "v_out": div(5.0, 1.8e3, 3.3e3),
         "ok": div(5.0, 1.8e3, 3.3e3) <= 3.3},
        {"red": "VBAT_SENSE (IO35)", "parts": "R6 100k / R7 22k + C3", "v_in_max": V_ADAPTER - D1_DROP,
         "v_out": div(V_ADAPTER - D1_DROP, 100e3, 22e3), "ok": div(V_ADAPTER - D1_DROP, 100e3, 22e3) <= 3.3},
    ]


def raspberry() -> dict:
    p = PI_W_TYP / PI_PSU_EFF
    return {"p_w": p, "wh_day": p * 24, "kwh_year": p * 24 * 365 / 1000}


def system(nodes: int, scenario: str = "actual") -> dict:
    s = SCENARIOS[scenario]
    node = node_budget(s["esp_a"], s["leds_on"])
    pi = raspberry()
    grid = node["grid_w"] * nodes + pi["p_w"]
    return {"nodes": nodes, "grid_w": grid, "grid_kwh_month": grid * 24 * 30 / 1000,
            "grid_kwh_year": grid * 24 * 365 / 1000}


def results() -> dict:
    scen = {k: {"label": v["label"], **node_budget(v["esp_a"], v["leds_on"])} for k, v in SCENARIOS.items()}
    return {
        "loads": [asdict(l) for l in LOADS],
        "scenarios": scen,
        "peak": node_peak(),
        "autonomy": {k: autonomy(scen[k]["p_total_w"]) for k in ("actual", "optimizado")},
        "charging": charging(scen["actual"]["p_total_w"]),
        "dividers": dividers(),
        "raspberry": raspberry(),
        "system": {n: system(n) for n in (1, 6, 10, 20)},
        "assumptions": {"V_BAT_NOM": V_BAT_NOM, "BUCK_EFF": BUCK_EFF, "LDO_IQ_A": LDO_IQ_A,
                        "V_ADAPTER": V_ADAPTER, "D1_DROP": D1_DROP, "ADAPTER_EFF": ADAPTER_EFF,
                        "ADAPTER_MAX_A": ADAPTER_MAX_A, "PI_W_TYP": PI_W_TYP, "PI_PSU_EFF": PI_PSU_EFF},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    r = results()
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return
    print("== Nodo: consumo continuo desde la batería (12,6 V) ==")
    for s in r["scenarios"].values():
        print(f"{s['label']:<48} {s['p_total_w']:5.2f} W  {s['i_bat_a']*1000:4.0f} mA  "
              f"{s['wh_day']:5.1f} Wh/día  {s['ah_day']:4.2f} Ah/día  red: {s['grid_kwh_year']:4.1f} kWh/año")
    p = r["peak"]
    print(f"\nPico simultáneo: 5 V {p['i_5v_a']*1000:.0f} mA, 3,3 V {p['i_3v3_a']*1000:.0f} mA, "
          f"entrada {p['p_in_w']:.2f} W ({p['i_12v_a']*1000:.0f} mA a 11,5 V)")
    print("\n== Autonomía sin adaptador (firmware actual / optimizado) ==")
    for a, o in zip(r["autonomy"]["actual"], r["autonomy"]["optimizado"]):
        print(f"{a['battery']:<30} {a['wh_usable']:5.0f} Wh útiles  {a['hours']:5.1f} h ({a['days']:.1f} d)  /  {o['hours']:5.1f} h")
    c = r["charging"]
    print(f"\n== Recarga con el adaptador 13,8 V ({ADAPTER_MAX_A:.0f} A) por D1 ==")
    print(f"Tensión en batería {c['v_at_battery']:.2f} V · nodo {c['i_load_a']*1000:.0f} mA · queda para cargar {c['i_charge_a']:.2f} A")
    for row in c["rows"]:
        print(f"{row['battery']:<30} {row['ah_to_recharge']:4.1f} Ah → ≈{row['hours']:4.1f} h")
    print(c["note_agm"]); print(c["note_lfp"])
    print("\n== Divisores hacia el ESP32 ==")
    for d in r["dividers"]:
        print(f"{d['red']:<18} {d['parts']:<22} {d['v_in_max']:5.2f} V → {d['v_out']:.2f} V  {'OK' if d['ok'] else 'EXCEDE'}")
    pi = r["raspberry"]
    print(f"\n== Raspberry Pi 4B == {pi['p_w']:.1f} W · {pi['wh_day']:.0f} Wh/día · {pi['kwh_year']:.1f} kWh/año")
    print("\n== Sistema 24/7 con adaptadores conectados (energía de la red) ==")
    for n, s in r["system"].items():
        print(f"{n:>3} nodos: {s['grid_w']:6.1f} W · {s['grid_kwh_month']:6.1f} kWh/mes · {s['grid_kwh_year']:6.0f} kWh/año")


if __name__ == "__main__":
    main()
