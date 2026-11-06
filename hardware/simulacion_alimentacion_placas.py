"""Simulación de la alimentación de las dos placas del nodo v2 y de cada sensor.

Placa 1 (unidad central): adaptador PS1 o batería de 12 V a través del módulo de conmutación UPS1
(la batería tiene su propio cargador, que UPS1 no maneja), corte por bajo voltaje, reductor MP1584 de 5 V fijo, D13 y el regulador de 3.3 V de la DevKitC.
Pendiente: la placa 2 todavía se modela con el TSR 1-2450, aunque la BOM usa el Mini560, y la
recarga con la corriente de 1 A del CN3767. Falta la hoja de datos real de ambos reemplazos.
Placa 2 (interfaz de sensores): recibe los 12 V de la placa 1 por F4 y el cable W1, y genera
sus propios 5 V con el TSR 1-2450 para el MQ-4, el MH-Z19C, el AJ-SR04M y el DHT11.

El cálculo resuelve, para cada escenario, la tensión que llega a cada sensor y la corriente que
sale de la batería, considerando las caídas en el fusible, el MOSFET del LVD, el PTC, el cable,
los diodos y la eficiencia de cada convertidor. Reutiliza los modelos de simulacion_energia.py
(consumos) y simulacion_pcb_v2.py (cargador y LVD). Sin dependencias externas.

    python hardware/simulacion_alimentacion_placas.py
    python hardware/simulacion_alimentacion_placas.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulacion_pcb_v2 as v2  # noqa: E402

# ------------------------------------------------------------ cable W1 y protecciones
RHO_CU = 0.0175           # Ω·mm²/m a 20 °C
CABLE_MM2 = 0.34          # mm², 6 pares trenzados AWG 22
CABLE_M = 20.0            # m, longitud de diseño (límite del DHT11)
N_IDA, N_RET = 2, 4       # conductores de +12 V (polos 1-2) y de GND (polos 3, 4, 5 y 12)
F2_R = 0.025              # Ω, fusible cerámico 5×20 de 3 A (estimado)
V_PS1 = 13.8              # V, adaptador en la entrada de UPS1; debe superar la reconexión del LVD (12.37 V)
C1_F = 470e-6             # F, C1 en +12V_LOAD: lo único que sostiene el bus durante el cambio de UPS1
LVD_TAU_S = 845e3 * 100e3 / (845e3 + 100e3) * 100e-9   # s, R27 ∥ R28 con C18
V_BUCK_MIN = 7.0          # V, entrada mínima anunciada para el MP1584 de 5 V (a confirmar)
F4_R = 0.85               # Ω, PTC MF-R050 (Rmin 0.50 Ω, R1max 1.17 Ω)
HARNESS_R = 0.084 * 0.3 * 2   # Ω, arnés JST de 30 cm en 24 AWG (ida y vuelta)

# ------------------------------------------------------------ convertidores
TSR_VOUT, TSR_TOL = 5.0, 0.02   # TSR 1-2450: ±2 % de ajuste de salida
TSR_VIN_MIN = 6.5
BUCK_VOUT = 5.00          # MP1584EN ajustado antes de montar
LDO_VOUT, LDO_IQ, LDO_DROPOUT = 3.3, 0.005, 1.1   # AMS1117-3.3 de la DevKitC (dropout a 0.8 A)


def tsr_eff(i_out: float) -> float:
    """Eficiencia del TSR 1-2450 a 12 V de entrada (curva de la hoja de datos, aproximada)."""
    return max(0.70, 0.93 - 0.012 / max(i_out, 0.01))


def buck_eff(i_out: float) -> float:
    """MP1584EN de 12 a 5 V: ≈80 % a 0.1 A y ≈88 % a 0.5 A."""
    return max(0.65, 0.90 - 0.010 / max(i_out, 0.01))


def schottky_vf(i: float) -> float:
    """1N5822 (D13 y D1 de la placa 2): aproximación ajustada a 0.525 V máx. a 3 A, 25 °C. Medir en el prototipo."""
    return 0.28 + 0.13 * min(i, 3.0) ** 0.6


@dataclass
class Sensor:
    ref: str
    name: str
    typ_a: float
    peak_a: float
    v_min: float
    v_max: float
    source: str


SENSORS = [
    Sensor("MQ-4", "Metano (calefactor 33 Ω + LM393 + LED del módulo)", 0.157, 0.170, 4.90, 5.10,
           "Calefactor 33 Ω ±5 % a 5.0 ± 0.1 V (hoja de datos Winsen MQ-4); módulo ≈7 mA"),
    Sensor("MH-Z19C", "CO₂ NDIR", 0.040, 0.125, 4.90, 5.10,
           "Hoja de datos Winsen MH-Z19C: media < 40 mA, pico 125 mA, 5.0 ± 0.1 V"),
    Sensor("AJ-SR04M", "Nivel ultrasónico", 0.008, 0.030, 3.0, 5.5,
           "Reposo ≈5-8 mA, midiendo < 30 mA, 3.0-5.5 V"),
    Sensor("DHT11", "Temperatura y humedad (+ pull-up R9 de 5.1 kΩ)", 0.0004, 0.0035, 3.3, 5.5,
           "Hoja de datos Aosong: 0.5-2.5 mA midiendo, 0.1-0.15 mA en reposo; pull-up 1 mA al transmitir"),
]
PLACA2_LOGIC = [  # cargas propias de la placa 2 en el riel de 5 V
    ("U3 TLV9001 (seguidor del MQ-4)", 0.00006, 0.00006),
    ("U4, U5 SN74AHCT1G125 (buffers del ultrasónico)", 0.00002, 0.0014),
    ("U6, U7 TPD4E1U06 (ESD, fuga)", 0.000001, 0.000001),
]

ESP_3V3 = {"actual": 0.070, "pico": 0.450}     # ESP32-WROOM-32E: media con ahorro WiFi / transmisión
DEVKIT_LED = 0.002
ALARM_LED = (3.3 - 2.0) / 330                  # por LED encendido
DHT_PULLUP_3V3 = 3.3 / 10e3 * 0.02             # R5 de 10 kΩ, línea en bajo ≈2 % del tiempo
VBAT_DIVIDER = 122e3                           # R6 + R7 sobre +12V


def cable_r() -> dict:
    r1 = RHO_CU * CABLE_M / CABLE_MM2
    return {"r_conductor": r1, "r_ida": r1 / N_IDA, "r_retorno": r1 / N_RET, "r_total": r1 / N_IDA + r1 / N_RET}


def placa2(v_12v_load: float, peak: bool) -> dict:
    """Riel de 5 V de la placa 2 y la corriente que pide a los 12 V de la placa 1."""
    sens = [(s, s.peak_a if peak else s.typ_a) for s in SENSORS]
    logic = sum(p if peak else t for _, t, p in PLACA2_LOGIC)
    i5 = sum(a for _, a in sens) + logic
    p5 = i5 * TSR_VOUT
    eff = tsr_eff(i5)
    rc = cable_r()["r_total"]
    i_in = 0.1
    for _ in range(30):     # la tensión de entrada depende de la corriente que pasa por el cable
        v_in = v_12v_load - i_in * (F4_R + rc) - schottky_vf(i_in)
        i_in = p5 / eff / v_in
    v_sensor = [(s, a, TSR_VOUT - a * HARNESS_R) for s, a in sens]
    return {
        "i_5v_a": i5, "p_5v_w": p5, "tsr_eff": eff, "v_tsr_in": v_in, "i_12v_a": i_in,
        "p_in_w": i_in * v_12v_load, "p_cable_w": i_in ** 2 * rc, "p_f4_w": i_in ** 2 * F4_R,
        "p_d1_w": i_in * schottky_vf(i_in), "p_tsr_loss_w": p5 / eff - p5,
        "sensores": [{"ref": s.ref, "nombre": s.name, "i_a": a, "p_w": a * TSR_VOUT,
                      "v_nom": v, "v_min": (TSR_VOUT * (1 - TSR_TOL)) - a * HARNESS_R,
                      "v_max": TSR_VOUT * (1 + TSR_TOL), "rango": f"{s.v_min:.2f}-{s.v_max:.2f} V",
                      "ok": s.v_min <= (TSR_VOUT * (1 - TSR_TOL)) - a * HARNESS_R and TSR_VOUT * (1 + TSR_TOL) <= s.v_max,
                      "fuente": s.source} for s, a, v in v_sensor],
        "margen_tsr_v": v_in - TSR_VIN_MIN,
    }


def placa1(v_bat: float, peak: bool, leds_on: int = 0) -> dict:
    """Riel de 3.3 V, 5 V y 12 V de la placa 1, incluida la carga de la placa 2."""
    lv = v2.lvd()
    i3 = (ESP_3V3["pico"] if peak else ESP_3V3["actual"]) + DEVKIT_LED + ALARM_LED * leds_on + DHT_PULLUP_3V3
    i_ldo_in = i3 + LDO_IQ
    vf13 = schottky_vf(i_ldo_in)
    v_esp5 = BUCK_VOUT - vf13
    p_buck_out = i_ldo_in * BUCK_VOUT
    eff = buck_eff(i_ldo_in)
    i_bat = 0.15
    for _ in range(30):
        v_load = v_bat - i_bat * (F2_R + v2.Q2_RDS)
        p2 = placa2(v_load, peak)
        i_buck_in = p_buck_out / eff / v_load
        i_bat = i_buck_in + p2["i_12v_a"] + lv["i_quiescent_a"] + v_load / VBAT_DIVIDER
    return {
        "v_bat": v_bat, "v_12v_load": v_load, "i_3v3_a": i3, "i_5v_a": i_ldo_in, "v_esp_5v": v_esp5,
        "v_ldo_margen": v_esp5 - (LDO_VOUT + LDO_DROPOUT), "buck_eff": eff,
        "p_3v3_w": i3 * LDO_VOUT, "p_ldo_loss_w": i_ldo_in * v_esp5 - i3 * LDO_VOUT,
        "p_d13_w": i_ldo_in * vf13, "p_buck_loss_w": p_buck_out / eff - p_buck_out,
        "p_lvd_w": lv["p_quiescent_w"], "p_divisor_w": v_load ** 2 / VBAT_DIVIDER,
        "p_f2_q2_w": i_bat ** 2 * (F2_R + v2.Q2_RDS),
        "i_bat_a": i_bat, "p_bat_w": i_bat * v_bat, "placa2": p2,
    }


def escenarios() -> list[dict]:
    lv = v2.lvd()
    defs = [
        ("Típico con batería nominal", v2.v1.V_BAT_NOM, False, 0),
        ("Pico (WiFi transmitiendo, MH-Z19C midiendo) con batería nominal", v2.v1.V_BAT_NOM, True, 0),
        ("Pico con las 4 alarmas, batería en el corte del LVD", lv["v_cutoff"], True, 4),
        (f"Típico con el adaptador PS1 de {V_PS1} V", V_PS1, False, 0),
        (f"Pico con el adaptador PS1 de {V_PS1} V", V_PS1, True, 0),
    ]
    return [dict(nombre=n, **placa1(v, pk, leds)) for n, v, pk, leds in defs]


def protecciones(peak: dict) -> list[dict]:
    p2 = peak["placa2"]
    return [
        {"pieza": "F2 fusible cerámico 3 A (bus 12 V)", "corriente_a": peak["i_bat_a"], "limite_a": 3.0},
        {"pieza": "UPS1 módulo de conmutación", "corriente_a": peak["i_bat_a"], "limite_a": 10.0},
        {"pieza": "F4 PTC MF-R050 (cable a la placa 2)", "corriente_a": p2["i_12v_a"], "limite_a": 0.50},
        {"pieza": "Q2 AOD4185 (LVD)", "corriente_a": peak["i_bat_a"], "limite_a": 40.0},
        {"pieza": "BUCK1 MP1584EN (5 V placa 1)", "corriente_a": peak["i_5v_a"], "limite_a": 3.0},
        {"pieza": "D13 1N5822", "corriente_a": peak["i_5v_a"], "limite_a": 3.0},
        {"pieza": "TSR 1-2450 (5 V placa 2)", "corriente_a": p2["i_5v_a"], "limite_a": 1.0},
        {"pieza": "D1 1N5822 (placa 2)", "corriente_a": p2["i_12v_a"], "limite_a": 3.0},
        {"pieza": "Cable W1, conductor 0.34 mm²", "corriente_a": p2["i_12v_a"] / N_IDA, "limite_a": 3.0},
    ]


def cambio_ups(v0: float, p_w: float, c_f: float = C1_F) -> dict:
    """Tiempo que aguanta C1, a potencia constante y sin entrada, durante el cambio de UPS1."""
    v_corte = v2.lvd()["v_cutoff"]
    v, filtro, t, dt = v0, v0, 0.0, 1e-5
    t_lvd = t_buck = None
    while t < 1.0 and (t_lvd is None or t_buck is None):
        v = max(v * v - 2 * p_w * dt / c_f, 0.0) ** 0.5
        filtro += (v - filtro) * dt / LVD_TAU_S
        t += dt
        if t_lvd is None and filtro < v_corte:
            t_lvd = t
        if t_buck is None and v < V_BUCK_MIN:
            t_buck = t
    return {"v0": v0, "p_w": p_w, "c_uf": c_f * 1e6, "ms_lvd": t_lvd * 1e3, "ms_buck": t_buck * 1e3}


def bateria(p_w: float) -> list[dict]:
    return [{"bateria": n, "wh_util": v * ah * dod, "horas": v * ah * dod / p_w}
            for n, v, ah, dod in v2.v1.BATTERIES if n.startswith("AGM")]


def results() -> dict:
    esc = escenarios()
    tip = esc[0]
    g = v2.grid(tip["p_bat_w"])
    pi = v2.v1.raspberry()["p_w"]
    return {
        "cable": cable_r(), "lvd": v2.lvd(), "escenarios": esc, "protecciones": protecciones(esc[2]),
        "cambio_ups": [cambio_ups(V_PS1, p, c) for p in (tip["p_bat_w"], esc[2]["p_bat_w"]) for c in (C1_F, 2200e-6)],
        "autonomia": bateria(tip["p_bat_w"]), "recarga": v2.recharge(tip["p_bat_w"]), "red": g,
        "sistema": [{"nodos": k, "w": k * g["grid_w"] + pi, "kwh_ano": (k * g["grid_w"] + pi) * 8.76}
                    for k in (1, 6, 10)],
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    r = results()
    if ap.parse_args().json:
        print(json.dumps(r, ensure_ascii=False, indent=1, default=lambda o: o.__dict__))
        return
    c = r["cable"]
    print(f"Cable W1 de {CABLE_M:.0f} m: {c['r_conductor']:.3f} Ω por conductor · ida {c['r_ida']:.3f} Ω "
          f"+ retorno {c['r_retorno']:.3f} Ω = {c['r_total']:.3f} Ω")
    for e in r["escenarios"]:
        p2 = e["placa2"]
        print(f"\n== {e['nombre']} (batería {e['v_bat']:.2f} V) ==")
        print(f"Placa 2: entrada {p2['v_tsr_in']:.2f} V (margen {p2['margen_tsr_v']:.2f} V sobre 6.5 V) · "
              f"{p2['i_12v_a']*1000:.0f} mA a 12 V · riel de 5 V {p2['i_5v_a']*1000:.0f} mA "
              f"({p2['p_5v_w']:.2f} W, eficiencia del TSR {p2['tsr_eff']*100:.0f} %)")
        for s in p2["sensores"]:
            print(f"   {s['ref']:9} {s['i_a']*1000:6.1f} mA  {s['p_w']:.3f} W  llega {s['v_min']:.2f}-{s['v_max']:.2f} V "
                  f"(admite {s['rango']}) {'OK' if s['ok'] else 'REVISAR'}")
        print(f"Placa 1: 3.3 V {e['i_3v3_a']*1000:.0f} mA · 5 V {e['i_5v_a']*1000:.0f} mA · pin 5V de la DevKitC "
              f"{e['v_esp_5v']:.2f} V (margen del LDO {e['v_ldo_margen']:+.2f} V) · buck {e['buck_eff']*100:.0f} %")
        print(f"Batería: {e['i_bat_a']*1000:.0f} mA · {e['p_bat_w']:.2f} W")
    print("\n== Protecciones en el peor caso ==")
    for p in r["protecciones"]:
        print(f"   {p['pieza']:38} {p['corriente_a']*1000:7.0f} mA de {p['limite_a']:.2f} A "
              f"({p['corriente_a']/p['limite_a']*100:.0f} %)")
    print("\n== Cambio de adaptador a batería en UPS1 (estimado, sin datos del módulo) ==")
    for u in r["cambio_ups"]:
        print(f"   {u['p_w']:.2f} W, C1 {u['c_uf']:4.0f} µF: dispara el LVD a {u['ms_lvd']:5.1f} ms · "
              f"bus bajo {V_BUCK_MIN:.0f} V a {u['ms_buck']:5.1f} ms")
    print("\n== Autonomía y recarga (consumo típico) ==")
    for a in r["autonomia"]:
        print(f"   {a['bateria']:28} {a['horas']:5.1f} h")
    for x in r["recarga"]:
        print(f"   recarga {x['battery']:20} ≈ {x['hours']:.1f} h a {x['i_bat_a']:.2f} A netos")
    print(f"\nCon adaptador: {r['red']['grid_w']:.2f} W de la red por nodo")
    for s in r["sistema"]:
        print(f"   {s['nodos']:2} nodos + Raspberry Pi: {s['w']:.1f} W · {s['kwh_ano']:.0f} kWh/año")


if __name__ == "__main__":
    main()
