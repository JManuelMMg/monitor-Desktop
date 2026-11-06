"""Cálculos de diseño de la PCB v2 (modelo comercial) del nodo «BiogasEmbebido».

Agrega a la v1 las etapas que le faltaban para un producto comercial:
  1. Cargador conmutado CC/CV para la batería AGM de 12 V (CN3767, U2).
  2. Protección contra inversión de la batería (XT60 polarizado + diodo de
     crowbar D1 + fusible F2) y diodo de bloqueo en la entrada del adaptador (D10).
  3. Desconexión por bajo voltaje (LVD) de la carga (TLV1701 + TLV431 + MOSFET P).
y las mejoras menores descritas en hardware/PCB_V2_COMERCIAL.md.

Reutiliza el modelo de consumo de simulacion_energia.py. Sin dependencias externas.

    python hardware/simulacion_pcb_v2.py
    python hardware/simulacion_pcb_v2.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulacion_energia as v1  # noqa: E402

# ------------------------------------------------------------ adaptador y cargador
V_ADAPTER = 19.0          # V, adaptador J3 de 19 V (tipo laptop o industrial), mínimo 1.5 A
V_ADAPTER_MAX = 20.0      # V, tolerancia alta del adaptador
D10_VF = 0.50             # V, MBRS360T3G (bloqueo e inversión de la entrada) a ~1 A
D11_VF = 0.45             # V, MBRS340T3G (diodo de libre circulación del buck) a 1 A

# CN3767 (hoja de datos Consonance, Rev 1.0)
VCS = 0.120               # V, tensión de sensado en corriente constante
F_SW = 300e3              # Hz (240-360 kHz)
F_SW_MIN = 240e3
D_MAX = 0.94
V_OC = 14.8               # V, sobrecarga (14.58-15.02)
V_FLOAT = 13.55           # V, flotación (13.35-13.75)
PRECHARGE = 0.75          # fracción de V_OC
RECHARGE = 0.8395         # fracción de V_OC
TRICKLE = 0.175           # fracción de I_CH
TERMINATION = 0.38        # fracción de I_CH
V_MPPT_REF = 1.205        # V
I_SLEEP_NO_D1 = 52e-6     # A, consumo desde la batería sin el D1 de la figura 1 (VBAT = 12 V)
V_GATE = 6.0              # V, excursión típica de DRV

I_CH = 1.0                # A, corriente de carga elegida (≈0.14 C para 7 Ah; Yuasa NP admite hasta 0.25 C)
L_UH = 68.0               # µH, Bourns SRR1260-680M (Isat 2.1 A, DCR ≤ 110 mΩ)
L_ISAT = 2.1
L_DCR = 0.110
Q1_RDS = 0.020            # Ω, AOD4185 con VGS ≈ -6 V
Q1_QG = 20e-9             # C, carga de compuerta a -6 V
Q1_TRANSITION_S = 100e-9  # s, subida + bajada (40 ns cada una con 2 nF según la hoja de datos, más margen)
R_MPPT_TOP, R_MPPT_BOT = 1.15e6, 100e3
CHARGER_EFF_LIGHT = 0.85  # eficiencia estimada del cargador cuando solo alimenta al nodo (≈0.13 A)
FLOAT_MA_PER_AH = 1.0     # corriente de flotación típica de una AGM

# ------------------------------------------------------------ desconexión por bajo voltaje
V_REF = 1.24              # V, TLV431 (U4)
R_REF = 82e3              # Ω, R26: polarización del TLV431 desde +12V_SW
R_TOP, R_BOT = 845e3, 100e3   # R27 / R28, divisor hacia IN−
R_S, R_F = 10e3, 1.5e6    # R29 / R30, histéresis en IN+ (reconexión < 12.4 V para que arranque con batería sana)
R_GATE_PU, R_GATE_SER = 100e3, 10e3   # R32 (compuerta-fuente de Q2) / R31 (salida → compuerta)
I_COMP = 55e-6            # A, TLV1701 típico
Q2_RDS = 0.020            # Ω, AOD4185

# ------------------------------------------------------------ otras mejoras
D13_VF = 0.30             # V, MBRS340T3G a ≈0.1 A (aislamiento del USB de la DevKitC)
D13_VF_PEAK = 0.37        # V, a 0.45 A (transmisión WiFi)
R_MQ_TOP, R_MQ_BOT = 100e3, 150e3
I_LEAK_TVS = 1e-6         # A, SMBJ15A a su VRWM


def charger() -> dict:
    rcs = VCS / I_CH
    vcc = V_ADAPTER - D10_VF
    vcc_max = V_ADAPTER_MAX - D10_VF
    v_path = V_OC + I_CH * (rcs + L_DCR + Q1_RDS)
    duty = v_path / vcc
    l = L_UH * 1e-6

    def ripple(v_bat, v_in, f):
        return v_bat / (f * l) * (1 - v_bat / v_in)

    # El rizado es máximo con VBAT = VCC/2; la carga normal va de 10.5 V a V_OC.
    v_worst = min(max(vcc_max / 2, 10.5), V_OC)
    di = ripple(V_OC, vcc, F_SW)
    di_max = ripple(v_worst, vcc_max, F_SW_MIN)
    # Regla de la hoja de datos: L > 5 × (VCC − VBAT) µH.
    v_bat_min_rule = vcc_max - L_UH / 5

    v_bat_cc = 13.0                                   # tensión media durante la etapa CC
    d_cc = (v_bat_cc + I_CH * (rcs + L_DCR + Q1_RDS)) / vcc
    p_out = v_bat_cc * I_CH
    losses = {
        "Q1 conducción": I_CH ** 2 * Q1_RDS * d_cc,
        "Q1 conmutación": 0.5 * vcc * I_CH * Q1_TRANSITION_S * F_SW,
        "compuerta (en U2)": Q1_QG * V_GATE * F_SW,
        "D11": D11_VF * I_CH * (1 - d_cc),
        "L1 (DCR)": I_CH ** 2 * L_DCR,
        "R20 (RCS)": I_CH ** 2 * rcs,
    }
    p_in_buck = p_out + sum(losses.values())
    i_in = p_in_buck / vcc
    losses["D10"] = D10_VF * i_in
    p_in = p_out + sum(losses.values())
    return {
        "rcs_ohm": rcs, "p_rcs_w": I_CH ** 2 * rcs,
        "i_trickle_a": TRICKLE * I_CH, "i_termination_a": TERMINATION * I_CH,
        "v_precharge": PRECHARGE * V_OC, "v_recharge": RECHARGE * V_OC,
        "vcc": vcc, "duty": duty, "duty_ok": duty < D_MAX,
        "v_adapter_min": v_path / D_MAX + D10_VF,
        "ripple_a": di, "ripple_max_a": di_max, "i_peak_a": I_CH + di_max / 2, "l_isat_a": L_ISAT,
        "l_rule_min_uh_at_10v5": 5 * (vcc_max - 10.5), "v_bat_min_l_rule": v_bat_min_rule,
        "v_mppt": V_MPPT_REF * (1 + R_MPPT_TOP / R_MPPT_BOT),
        "losses_w": losses, "p_out_w": p_out, "p_in_w": p_in, "eff": p_out / p_in,
        "i_adapter_a": p_in / V_ADAPTER, "p_q1_w": losses["Q1 conducción"] + losses["Q1 conmutación"],
    }


def lvd() -> dict:
    ratio = (R_TOP + R_BOT) / R_BOT
    # Q2 encendido: U3 hunde su salida (≈0 V) y R30 baja un poco IN+.
    in_plus_on = V_REF * R_F / (R_S + R_F)
    v_cut = in_plus_on * ratio
    # Q2 apagado: la salida queda en +12V_SW a través de R32 + R31, en serie con R30.
    r_fb = R_F + R_GATE_PU + R_GATE_SER
    g = 1 / R_S + 1 / r_fb
    v_reconnect = (V_REF / R_S) * ratio / (g - ratio / r_fb)
    v_bus = v1.V_BAT_NOM
    i_q = (I_COMP + (v_bus - V_REF) / R_REF + v_bus / (R_TOP + R_BOT)
           + v_bus / (R_GATE_PU + R_GATE_SER) + V_REF / (R_S + R_F))
    return {"v_cutoff": v_cut, "v_reconnect": v_reconnect, "hysteresis_v": v_reconnect - v_cut,
            "vgs_on": -v_bus * R_GATE_PU / (R_GATE_PU + R_GATE_SER),
            "vgs_on_max": -V_OC * 1.015 * R_GATE_PU / (R_GATE_PU + R_GATE_SER),
            "i_quiescent_a": i_q, "p_quiescent_w": i_q * v_bus,
            "i_ref_at_cut_a": (v_cut - V_REF) / R_REF}


def node_v2() -> dict:
    base = v1.node_budget(v1.SCENARIOS["actual"]["esp_a"], 0)
    lv = lvd()
    i_esp_5v = v1.SCENARIOS["actual"]["esp_a"] + v1.LDO_IQ_A
    p_d13 = D13_VF * i_esp_5v / v1.BUCK_EFF
    p_q2 = base["i_bat_a"] ** 2 * Q2_RDS
    p_total = base["p_total_w"] + lv["p_quiescent_w"] + p_d13 + p_q2
    return {"p_v1_w": base["p_total_w"], "p_lvd_w": lv["p_quiescent_w"], "p_d13_w": p_d13, "p_q2_w": p_q2,
            "p_total_w": p_total, "i_bat_a": p_total / v1.V_BAT_NOM,
            "v_esp_5v_peak": 5.0 - D13_VF_PEAK}


def grid(p_node_w: float, ah: float = 7) -> dict:
    """Con el adaptador conectado, la red alimenta al nodo y la flotación de la batería."""
    p_float = V_FLOAT * FLOAT_MA_PER_AH * ah / 1000
    w = (p_node_w + p_float) / (CHARGER_EFF_LIGHT * v1.ADAPTER_EFF)
    return {"p_float_w": p_float, "grid_w": w, "kwh_year": w * 24 * 365 / 1000}


def standby() -> dict:
    """SW1 apagado y sin adaptador: lo único que queda conectado a la batería."""
    i_chg = I_SLEEP_NO_D1 + (v1.V_BAT_NOM - 0.4) / (R_MPPT_TOP + R_MPPT_BOT)
    i = i_chg + I_LEAK_TVS
    return {"i_a": i, "ah_year": i * 24 * 365}


def recharge(p_node_w: float) -> list[dict]:
    i_load = p_node_w / V_FLOAT
    i_bat = I_CH - i_load          # R20 mide batería + nodo, así que la batería recibe la diferencia
    rows = []
    for name, v, ah, dod in v1.BATTERIES:
        if not name.startswith("AGM"):
            continue                # el CN3767 es solo para plomo-ácido
        ah_needed = ah * dod / 0.85
        hours = ah_needed / i_bat * 1.3   # +30 % por la etapa de sobrecarga con corriente decreciente
        rows.append({"battery": name, "ah": ah_needed, "i_bat_a": i_bat, "hours": hours})
    return rows


def dividers() -> list[dict]:
    def div(v, top, bot):
        return v * bot / (top + bot)
    return [
        {"red": "MQ_ADC (IO34)", "parts": "R1 100k / R2 150k + C20 100 nF", "v_in": 5.0,
         "v_out": div(5.0, R_MQ_TOP, R_MQ_BOT), "ratio": R_MQ_BOT / (R_MQ_TOP + R_MQ_BOT)},
        {"red": "VBAT_SENSE (IO35)", "parts": "R6 100k / R7 22k + C3", "v_in": V_OC * 1.015,
         "v_out": div(V_OC * 1.015, 100e3, 22e3), "ratio": 22 / 122},
    ]


def results() -> dict:
    n = node_v2()
    g = grid(n["p_total_w"])
    pi = v1.raspberry()["p_w"]
    return {"charger": charger(), "lvd": lvd(), "node": n, "grid": g, "standby": standby(),
            "recharge": recharge(n["p_total_w"]), "autonomy": v1.autonomy(n["p_total_w"]),
            "dividers": dividers(),
            "system": [{"nodes": k, "w": k * g["grid_w"] + pi, "kwh_year": (k * g["grid_w"] + pi) * 24 * 365 / 1000}
                       for k in (1, 6, 10)]}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    r = results()
    if parser.parse_args().json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return
    c = r["charger"]
    print("== Cargador CN3767 (U2) ==")
    print(f"I_CH {I_CH:.2f} A → R20 = {c['rcs_ohm']:.3f} Ω ({c['p_rcs_w']:.2f} W) · goteo {c['i_trickle_a']*1000:.0f} mA "
          f"· fin de sobrecarga {c['i_termination_a']*1000:.0f} mA")
    print(f"Sobrecarga {V_OC} V · flotación {V_FLOAT} V · precarga bajo {c['v_precharge']:.2f} V · "
          f"recarga bajo {c['v_recharge']:.2f} V")
    print(f"VCC {c['vcc']:.2f} V · ciclo de trabajo {c['duty']*100:.1f} % (máx. {D_MAX*100:.0f} %) · "
          f"adaptador mínimo {c['v_adapter_min']:.1f} V · umbral MPPT {c['v_mppt']:.2f} V")
    print(f"Rizado en L1 {c['ripple_a']*1000:.0f} mA (peor caso {c['ripple_max_a']*1000:.0f} mA, objetivo ≤ "
          f"{0.3*I_CH*1000:.0f} mA) · pico {c['i_peak_a']:.2f} A (Isat {c['l_isat_a']} A)")
    print(f"Regla L > 5(VCC−VBAT): con 10.5 V pide {c['l_rule_min_uh_at_10v5']:.0f} µH; 68 µH la cumple con "
          f"VBAT ≥ {c['v_bat_min_l_rule']:.1f} V")
    print("Pérdidas a 1 A: " + " · ".join(f"{k} {v:.2f} W" for k, v in c["losses_w"].items()))
    print(f"Eficiencia {c['eff']*100:.1f} % · entrada {c['p_in_w']:.1f} W ({c['i_adapter_a']:.2f} A del adaptador)")
    lv = r["lvd"]
    print("\n== Desconexión por bajo voltaje (U3, U4, Q2) ==")
    print(f"Corta a {lv['v_cutoff']:.2f} V · reconecta a {lv['v_reconnect']:.2f} V · histéresis {lv['hysteresis_v']:.2f} V")
    print(f"VGS de Q2 encendido {lv['vgs_on']:.1f} V (máx. {lv['vgs_on_max']:.1f} V) · consumo propio "
          f"{lv['i_quiescent_a']*1e6:.0f} µA · TLV431 al cortar: {lv['i_ref_at_cut_a']*1e6:.0f} µA")
    n = r["node"]
    print("\n== Nodo v2 ==")
    print(f"v1 {n['p_v1_w']:.3f} W + LVD {n['p_lvd_w']*1000:.1f} mW + D13 {n['p_d13_w']*1000:.1f} mW + "
          f"Q2 {n['p_q2_w']*1000:.2f} mW → {n['p_total_w']:.3f} W ({n['i_bat_a']*1000:.0f} mA) · "
          f"5 V de la DevKitC en picos: {n['v_esp_5v_peak']:.2f} V")
    for a in r["autonomy"][:3]:
        print(f"  {a['battery']:<28} {a['hours']:5.1f} h ({a['days']:.1f} d)")
    print("Recarga con el CN3767:")
    for row in r["recharge"]:
        print(f"  {row['battery']:<28} {row['ah']:4.1f} Ah a {row['i_bat_a']:.2f} A → ≈{row['hours']:4.1f} h")
    s = r["standby"]
    print(f"Apagado (SW1 abierto, sin adaptador): {s['i_a']*1e6:.0f} µA → {s['ah_year']:.2f} Ah/año")
    g = r["grid"]
    print(f"Con adaptador: flotación {g['p_float_w']:.2f} W · desde la red {g['grid_w']:.2f} W ({g['kwh_year']:.0f} kWh/año)")
    print("\n== Divisores ==")
    for d in r["dividers"]:
        print(f"  {d['red']:<18} {d['parts']:<32} {d['v_in']:5.2f} V → {d['v_out']:.2f} V (factor {d['ratio']:.4f})")
    print("\n== Sistema con adaptadores y Raspberry Pi ==")
    for s in r["system"]:
        print(f"  {s['nodes']:>2} nodos: {s['w']:5.1f} W · {s['kwh_year']:5.0f} kWh/año")


if __name__ == "__main__":
    main()
