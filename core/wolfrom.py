# -*- coding: utf-8 -*-
"""
Wolfrom (3K) planetary with stepped planets: a high ratio in one stage, the output is a turning ring.

    sun Zs (motor) -> stepped planet: Zp1 meshes the sun and the fixed ring Zr1 = Zs + 2 Zp1
                                       Zp2 meshes the output ring Zr2 = Zr1 + (Zp2 - Zp1)
    the carrier is free (no torque); same module everywhere, every centre distance standard:
        Zs + Zp1 = Zr1 - Zp1 = Zr2 - Zp2

    carrier speed      c  = Zs / (Zs + Zr1)                    (per input turn, ring 1 fixed)
    basic ratio        i0 = Zr1 Zp2 / (Zp1 Zr2)                (ring 2 over ring 1, carrier held)
    output (ring 2)    w2 = c (1 - i0)        ->  ratio i = 1 / w2   (sign: direction)
    planet spin        relative to the carrier  -c Zr1 / Zp1

Efficiency (Mueller, basic efficiency eta0 of the ring 1 -> ring 2 train with the carrier held, two internal
meshes ~ the stage efficiency of the material):  eta = (1 - i0) / (1 - i0 / eta0) for i0 > 1,
(1 - i0) / (1 - i0 eta0) for i0 < 1, times the sun stage.  Driven backwards (from the output) the efficiency
eta' = (1 - i0 eta0) / (1 - i0) (i0 > 1) resp. (1 - i0 / eta0) / (1 - i0) (i0 < 1); eta' <= 0 means the gearbox
locks itself: the load cannot turn the motor (the load is held without power), and it must always be driven.

Tooth forces per planet (load sharing K_gamma): output ring F2 = 2000 T_out / (N d_r2), fixed ring
F1 = 2000 (T_out - T_in) / (N d_r1) (its reaction carries almost the whole output torque), sun Fs = 2000 T_in /
(N d_s). The two ring forces form a couple on the planet (two bearings, pin bending between the plates).

Assembly of identical stepped planets: planet k (at theta_k) is turned by an integer number of set-1 teeth so
that set 1 meshes; set 2 then has a phase error against ring 2 (ring 2 may be turned as a whole). The error
must stay below a quarter of the backlash (search, CAD places every planet accordingly).
"""
from __future__ import annotations

import math
import time
from typing import Dict, List, Optional, Tuple

from core.bearing_catalog import BEARING_CATALOG, get_bearing_info, real_bearings
from core.engineering import (LOAD_RESERVE, Check, LoadCase, _z_e, _z_h, application_load_checks, lewis_y,
                              load_sharing, motor_shaft_check, CHECK_LABELS)
from core.gear_geometry import stage_geometry
from core.materials import STEEL_PIN, get_material
from core.motor_catalog import get_motor_info

KHB = 1.2                 # face load factor (stepped planet on a pin pair, see engineering K_Hbeta)
SET_GAP = 2.0             # axial gap between the two tooth sets (ring 1 ends, ring 2 begins)
RING_GAP = 0.6
DIFFS = (1, -1, 2, -2, 3, -3)
RING_WALL = 3.0           # output ring wall around its teeth (bearing seat)

TEXT = {
    "tr": {"bend_sun": "Diş dibi — güneş", "bend_p1": "Diş dibi — planet (alt dişli)", "bend_r1": "Diş dibi — sabit çember",
           "bend_p2": "Diş dibi — planet (üst dişli)", "bend_r2": "Diş dibi — çıkış çemberi",
           "contact_sp": "Yüzey basıncı güneş / planet", "contact_pr1": "Yüzey basıncı planet / sabit çember",
           "contact_pr2": "Yüzey basıncı planet / çıkış çemberi", "bearing_static": "Planet rulmanı statik s0",
           "bearing_life": "Planet rulman ömrü L10h", "pin_bending": "Pim eğilmesi (iki dişli arası kuvvet çifti)",
           "out_bearing": "Çıkış halkası rulmanı (yan yük + moment) s0",
           "out_plain": "Çıkış halkası kaymalı yatağı (yan yük basıncı)",
           "set1": "Güneş — planet (alt) — sabit çember", "set2": "Planet (üst) — çıkış çemberi",
           "lock": "Kendiliğinden kilitlenir: çıkış elle / yükle çevrilemez (yük elektriksiz tutulur); geri sürme verimi {b:.0f} %.",
           "nolock": "Kilitlenmez: yük çıkışı geri çevirebilir (geri sürme verimi {b:.0f} %); fren veya tutma akımı gerekir.",
           "eta": "Wolfrom verimi ~%{e:.0f} (temel oran i0 = {i0:.4f}): motor torkunun ~%{l:.0f}'i sürtünmeye gider; çıkış torku ve oran buna göre hesaplandı.",
           "bend_p1r": "Diş dibi — planet (alt dişli, ters eğilme)",
           "label": "Wolfrom"},
    "en": {"bend_sun": "Root — sun", "bend_p1": "Root — planet (lower gear)", "bend_r1": "Root — fixed ring",
           "bend_p2": "Root — planet (upper gear)", "bend_r2": "Root — output ring",
           "contact_sp": "Contact sun / planet", "contact_pr1": "Contact planet / fixed ring",
           "contact_pr2": "Contact planet / output ring", "bearing_static": "Planet bearing static s0",
           "bearing_life": "Planet bearing life L10h", "pin_bending": "Pin bending (couple of the two gears)",
           "out_bearing": "Output ring bearing (side load + moment) s0",
           "out_plain": "Output ring plain bearing (side load pressure)",
           "set1": "Sun — planet (lower) — fixed ring", "set2": "Planet (upper) — output ring",
           "lock": "Self-locking: the output cannot be turned by hand / the load (the load is held without power); "
                   "back-drive efficiency {b:.0f} %.",
           "nolock": "Not self-locking: the load can back-drive the output (back-drive efficiency {b:.0f} %); "
                     "a brake or holding current is needed.",
           "eta": "Wolfrom efficiency ~{e:.0f} % (basic ratio i0 = {i0:.4f}): ~{l:.0f} % of the motor torque goes into "
                  "friction; the output torque and the ratio account for it.",
           "bend_p1r": "Root — planet (lower gear, reversed bending)",
           "label": "Wolfrom"},
}


DRY_ETA_LOSS = 0.04       # expert mode, dry running: basic mesh efficiency lower (greased material value - 0.04)


def basic_efficiency(load: LoadCase) -> float:
    """Basic efficiency eta0 of the ring 1 -> ring 2 train (material value, greased; dry in expert mode: lower)."""
    eta0 = get_material(load.gear_material)["eta"]
    return eta0 - DRY_ETA_LOSS if (load.expert and load.lube == "DRY") else eta0


def ratio_of(zs: int, zp1: int, zp2: int) -> Tuple[float, float, float, int, int]:
    """(signed ratio input/output, carrier factor c, basic ratio i0, Zr1, Zr2)."""
    zr1 = zs + 2 * zp1
    zr2 = zr1 + (zp2 - zp1)
    c = zs / (zs + zr1)
    i0 = zr1 * zp2 / (zp1 * zr2)
    w2 = c * (1.0 - i0)
    return (1.0 / w2 if abs(w2) > 1e-12 else float("inf")), c, i0, zr1, zr2


def efficiencies(i0: float, eta0: float, eta_sun: float) -> Tuple[float, float]:
    """(forward efficiency motor -> output, back-drive efficiency output -> carrier) of the Wolfrom stage."""
    if i0 > 1.0:
        fwd = (1.0 - i0) / (1.0 - i0 / eta0)
        back = (1.0 - i0 * eta0) / (1.0 - i0)
    else:
        fwd = (1.0 - i0) / (1.0 - i0 * eta0)
        back = (1.0 - i0 / eta0) / (1.0 - i0)
    return max(0.0, fwd) * eta_sun, back


def planet_phases(zs: int, zp1: int, zp2: int, n: int) -> Tuple[List[float], float]:
    """
    Turn of every stepped planet (rad) so that set 1 meshes the sun and ring 1 (ring spaces at 0) and set 2 is as
    close as possible to ring 2 (also with its space at 0); returns (turns, worst set-2 error in rad of the planet).
    """
    zr1 = zs + 2 * zp1
    zr2 = zr1 + (zp2 - zp1)
    p1, p2 = 2 * math.pi / zp1, 2 * math.pi / zp2
    turns, worst = [], 0.0
    for k in range(n):
        th = 2 * math.pi * k / n
        f1 = (th * (1.0 - zr1 / zp1)) % p1
        f2 = (th * (1.0 - zr2 / zp2)) % p2
        best = None
        for j in range(zp1):
            r = f1 + j * p1
            e = (r - f2) % p2
            e = min(e, p2 - e)
            if best is None or e < best[0]:
                best = (e, r)
        turns.append(best[1])
        worst = max(worst, best[0])
    return turns, worst


def _bearing_for(root_r: float, module: float, face_width: float, steel: bool, bearing: str, tol: float) -> Optional[Dict]:
    """Planet bearing (two, one at each end of the stepped planet) that fits the smaller root circle."""
    from core.design import DOWEL_DIAMETERS, rim_min
    lim = 2.0 * (root_r - rim_min(module))
    codes = real_bearings() if bearing == "AUTO" else [bearing]
    best = None
    for code in codes:
        b = BEARING_CATALOG.get(code)
        if not b or (steel and b["d_inner"] not in DOWEL_DIAMETERS):
            continue
        if b["d_outer"] + tol > lim or b["width"] + 1.0 > face_width:
            continue
        if best is None or b["C_kN"] > BEARING_CATALOG[best]["C_kN"]:
            best = code
    if best is None:
        return None
    b = BEARING_CATALOG[best]
    return {"code": best, "pin": b["d_inner"], "pocket": b["d_outer"] + tol, "width": b["width"],
            "C": b["C_kN"] * 1000.0, "C0": b["C0_kN"] * 1000.0}


PLAIN_LEN = 10.0          # printed plain bearing of the output ring (slow output: greased PETG / PLA sleeve)
PLAIN_CLEAR = 0.4
PLAIN_P_ALLOW = 4.0       # MPa, printed plastic on plastic, greased, very slow


def output_support(ring2_root_r: float) -> Dict:
    """
    How the output ring turns in the fixed housing: the smallest thin-section ball bearing whose bore takes the ring
    (teeth root + wall), else a printed plain bearing (the ring runs in the housing sleeve, greased) — the output of
    a Wolfrom turns very slowly, the plain bearing only sees the side load.
    """
    code = output_bearing_for(ring2_root_r)
    if code:
        b = get_bearing_info(code)
        return {"kind": "BEARING", "code": code, "d": b["d_inner"], "D": b["d_outer"], "width": b["width"],
                "C0": b["C0_kN"] * 1000.0}
    d = 2.0 * (ring2_root_r + RING_WALL)
    return {"kind": "PLAIN", "code": "PLAIN", "d": d, "D": d + PLAIN_CLEAR, "width": PLAIN_LEN, "C0": 0.0}


def output_bearing_for(ring2_root_r: float) -> Optional[str]:
    """Thin-section bearing whose bore takes the output ring (teeth root + wall)."""
    need = 2.0 * (ring2_root_r + RING_WALL)
    fits = [c for c in real_bearings() if c.startswith("68") and BEARING_CATALOG[c]["d_inner"] >= need]
    return min(fits, key=lambda c: BEARING_CATALOG[c]["d_inner"]) if fits else None


def _mesh_checks(prefix: str, ft: float, z1: float, z2: float, internal: bool, m: float, b: float, d1: float,
                 gm: Dict, load: LoadCase, rev1: float = 1.0) -> List[Tuple[str, float, float, float]]:
    """(name, value, limit, exponent) of the root of both gears and the contact of one mesh."""
    out = []
    y1 = lewis_y(z1) * 0.79
    y2 = lewis_y(400.0 if internal else z2) * 0.79
    for name, y, f in ((prefix[0], y1, rev1), (prefix[1], y2, 1.0)):
        if name:
            out.append((name, ft * KHB / (b * m * y), gm["sigma_F"] * f, 1.0))
    u = z2 / z1
    ze, zh = _z_e(gm, gm), _z_h(math.radians(20.0), 0.0)
    sig = ze * zh * 0.9 * math.sqrt(ft * KHB / (b * d1) * ((u - 1) if internal else (u + 1)) / u)
    out.append((prefix[2], sig, gm["sigma_H"], 2.0))
    return out


def _expert(c: Dict, load: LoadCase, eta: float) -> Dict:
    """
    Expert terms of a Wolfrom gearbox: its power loss P_in (1 - eta) is large and heats the closed housing (heat
    balance), the sun mesh adds its local tooth temperature (VDI 2736 tooth term); load cycles and wear of the sun.
    """
    from core import expert as X
    g1 = c["geo1"]
    n_in = load.motor_speed
    n_rel = n_in * (1.0 - c["carrier"])
    x = X.stage_terms(load.gear_material, g1, c["face_width"], c["n"], False, load.lube)
    t = X.terms(x, load.motor_torque, n_rel, math.pi * 2.0 * g1.r_sun * n_rel / 60000.0, load)
    p_loss = load.motor_torque * 2.0 * math.pi * n_in / 60.0 * (1.0 - eta)
    d = c["hd"]["body_d"]
    length = 2.0 * c["face_width"] + SET_GAP + 25.0
    area = (math.pi * d * length + 2.0 * math.pi * d * d / 4.0) / 1e6
    rise = t["rise"] + X.housing_rise(p_loss, area, load.duty)
    temp = load.ambient_c + rise
    f_t = X.temp_factor(temp, x["t_max"])
    return {"temp": temp, "rise": rise, "t_max": x["t_max"], "f_t": f_t, "y_nt": t["y_nt"], "z_nt": t["z_nt"],
            "fb": f_t * t["y_nt"], "fc": f_t * t["z_nt"], "wear": t["wear"], "wear_lim": t["wear_lim"],
            "cycles": t["cycles"], "mu": x["mu"], "p_loss": p_loss}


def _expert_summary(ex: Dict) -> Dict:
    return {"temp": round(ex["temp"], 1), "t_max": ex["t_max"], "f_t": round(ex["f_t"], 3), "y_nt": round(ex["y_nt"], 3),
            "z_nt": round(ex["z_nt"], 3), "cycles": ex["cycles"], "mu": ex["mu"], "p_loss_w": round(ex["p_loss"], 2),
            **({"wear_mm": round(ex["wear"], 4), "wear_lim": round(ex["wear_lim"], 3)} if ex.get("wear") is not None
               else {})}


def analyze(c: Dict, load: LoadCase, lang: str, app: Optional[Dict] = None) -> Dict:
    """Engineering of one Wolfrom design (checks, capacity, efficiencies) in the engine's result format."""
    T = TEXT["en" if lang == "en" else "tr"]
    gm, sm = get_material(load.gear_material), get_material(load.struct_material)
    m, n, b = c["module"], c["n"], c["face_width"]
    zs, zp1, zp2, zr1, zr2 = c["zs"], c["zp1"], c["zp2"], c["zr1"], c["zr2"]
    i, eta, back = abs(c["ratio"]), c["eta"], c["eta_back"]
    t_in = load.motor_torque * load.application_factor
    t_out = t_in * i * eta
    kg = load_sharing(n, gm["printed"])
    fs = 2000.0 * t_in / (n * m * zs) * kg
    f1 = 2000.0 * max(t_out - t_in, 0.0) / (n * m * zr1) * kg
    f2 = 2000.0 * t_out / (n * m * zr2) * kg
    raw = []
    raw += _mesh_checks(("bend_sun", "bend_p1", "contact_sp"), fs, zs, zp1, False, m, b, m * zs, gm, load, 1.0)
    raw += _mesh_checks((None, "bend_r1", "contact_pr1"), f1, zp1, zr1, True, m, b, m * zp1, gm, load)
    raw.append(("bend_p1r", f1 * KHB / (b * m * lewis_y(zp1) * 0.79), gm["sigma_F"] * 0.7, 1.0))   # reversed
    raw += _mesh_checks(("bend_p2", "bend_r2", "contact_pr2"), f2, zp2, zr2, True, m, b, m * zp2, gm, load, 0.7)
    sets_span = b + SET_GAP
    brg = c["bearing"]
    p_brg = f2 * (1.0 + 0.5 * sets_span / max(sets_span + 2.0, 1.0))
    raw.append(("bearing_static", brg["C0"] / max(p_brg, 1e-6), 1.0, 1.0))
    n_rel = load.motor_speed * c["carrier"] * zr1 / zp1
    life = (brg["C"] / max(p_brg, 1e-6)) ** 3 * 1e6 / (60.0 * max(n_rel, 1e-6))
    raw.append(("bearing_life", life, load.target_life_h, 3.0))
    pin_allow = STEEL_PIN["sigma_S"] if c["pin_steel"] else sm["sigma_S"]
    m_pin = f2 * sets_span / 2.0
    raw.append(("pin_bending", 32.0 * m_pin / (math.pi * brg["pin"] ** 3), pin_allow, 1.0))
    ex = _expert(c, load, eta) if load.expert else None
    if ex:              # allowables at the tooth temperature and over the load cycles of the target life
        raw = [(nm, v, lim * (ex["fb"] if nm.startswith("bend") else ex["fc"] if nm.startswith("contact") else 1.0), e)
               for nm, v, lim, e in raw]
    checks = []
    targets = {"contact": load.target_sh, "bearing_static": 1.0, "bearing_life": 1.0}
    labels = CHECK_LABELS["en" if lang == "en" else "tr"]
    for name, value, limit, exp in raw:
        tgt = targets.get(name.split("_")[0], targets.get(name, load.target_sf))
        if name == "bearing_static":
            safety = value
        elif name == "bearing_life":
            safety = value / limit
        else:
            safety = limit / max(value, 1e-9)
        checks.append(Check(name, value, limit, safety, tgt, "h" if name == "bearing_life" else
                            ("" if name == "bearing_static" else "MPa"), exp))
    # the output ring bearing: side load of the application (arm / flange) and its moment
    sup = c["support"]
    side = (app or {}).get("force", 0.0)
    p0 = side + 2.0 * side * 15.0 / ((sup["d"] + sup["D"]) / 2.0)      # side load + its moment (arm ~15 mm up)
    if side > 0 and sup["kind"] == "BEARING":
        checks.append(Check("out_bearing", p0, sup["C0"], sup["C0"] / p0, 2.0, "N", 0.0))
    elif side > 0:
        pr = p0 / (sup["d"] * sup["width"])
        checks.append(Check("out_plain", pr, PLAIN_P_ALLOW, PLAIN_P_ALLOW / pr, 1.0, "MPa", 0.0))
    ms = motor_shaft_check(t_in, c["motor_shaft_dia"], load)
    checks.append(ms)
    if ex:
        from core.expert import creep_check, special_checks
        checks += special_checks(ex, load)
        if load.hold_h > 0:          # self-locking Wolfrom: a held load stays on the teeth
            t_nom = t_out / load.application_factor
            hold = (app or {}).get("torque", 0.0) or t_nom
            bends = [ch.value for ch in checks if ch.name.startswith("bend")]
            checks.append(creep_check(max(bends) / load.application_factor, gm["sigma_F"], hold / t_nom, load))
    from core.engineering import arm_checks, mount_check
    mc = mount_check(t_out, c.get("mount"), load)
    if mc:
        checks.append(mc)
    if c.get("arm"):
        checks += arm_checks(t_out, c["arm"], load, key=False)
    scale, limiting = float("inf"), None
    for ch in checks:
        if ch.exponent <= 0:
            continue
        s = ch.torque_scale()
        if s < scale:
            scale, limiting = s, ch
    names = {"bend_sun": T["bend_sun"], "bend_p1": T["bend_p1"], "bend_r1": T["bend_r1"], "bend_p2": T["bend_p2"],
             "bend_r2": T["bend_r2"], "contact_sp": T["contact_sp"], "contact_pr1": T["contact_pr1"],
             "contact_pr2": T["contact_pr2"], "bearing_static": T["bearing_static"], "bearing_life": T["bearing_life"],
             "pin_bending": T["pin_bending"], "bend_p1r": T["bend_p1r"], "out_bearing": T["out_bearing"], "out_plain": T["out_plain"]}

    def cdict(ch):
        return {"name": ch.name, "label": names.get(ch.name, labels.get(ch.name, ch.name)), "value": ch.value,
                "limit": ch.limit, "safety": ch.safety, "target": ch.target, "unit": ch.unit, "ok": ch.ok}
    set1 = [ch for ch in checks if ch.name in ("bend_sun", "contact_sp", "bend_r1", "contact_pr1", "motor_shaft_torsion")
            or ch.name in ("bend_p1", "bend_p1r", "tooth_temp", "wear_sun")]
    set2 = [ch for ch in checks if ch not in set1]
    out_torque = t_out / load.application_factor
    out_speed = load.motor_speed / i
    common = {"star": False, "eps_alpha_sp": c["geo1"].eps_sun_planet, "eps_alpha_pr": c["geo1"].eps_planet_ring,
              "eps_beta": 0.0, "addendum": 1.0, "tip_land": 0.0, "depth_factor": {}}
    stages = [dict(common, index=1, ratio=1.0 / c["carrier"], title=T["set1"], input_torque=load.motor_torque,
                   output_torque=load.motor_torque / c["carrier"], sun_speed=load.motor_speed,
                   carrier_speed=load.motor_speed * c["carrier"], ring_speed=0.0, planet_speed_rel=n_rel,
                   tangential_force=f1, pitch_velocity=math.pi * m * zs * load.motor_speed / 60000.0,
                   checks=[cdict(ch) for ch in set1]),
              dict(common, index=2, ratio=i * c["carrier"], title=T["set2"], input_torque=load.motor_torque / c["carrier"],
                   output_torque=out_torque, sun_speed=load.motor_speed * c["carrier"], carrier_speed=0.0,
                   ring_speed=out_speed, planet_speed_rel=n_rel, tangential_force=f2,
                   pitch_velocity=math.pi * m * zr2 * out_speed / 60000.0,
                   eps_alpha_pr=c["geo2"].eps_planet_ring, checks=[cdict(ch) for ch in set2])]
    eng = {"total_ratio": c["ratio"], "efficiency": eta, "reverse": False, "star": False,
           "input_torque": load.motor_torque, "input_speed": load.motor_speed, "output_torque": out_torque,
           "output_speed": out_speed, "max_output_torque": out_torque * scale, "margin": scale,
           "limiting": ({"stage": 2 if limiting in set2 else 1, "check": limiting.name,
                         "label": names.get(limiting.name, labels.get(limiting.name, limiting.name))}
                        if limiting else None),
           "all_ok": all(ch.ok for ch in checks), "stages": stages,
           "load_case": {"application_factor": load.application_factor, "target_sf": load.target_sf,
                         "target_sh": load.target_sh, "target_life_h": load.target_life_h,
                         "gear_material": load.gear_material, "struct_material": load.struct_material},
           "wolfrom": {"i0": c["i0"], "eta": eta, "eta_back": back, "self_locking": back <= 0.0,
                       "text": (T["lock"] if back <= 0.0 else T["nolock"]).format(b=max(back, 0.0) * 100.0) + " " +
                               T["eta"].format(e=eta * 100.0, i0=c["i0"], l=(1.0 - eta) * 100.0)},
           "app_load_checks": None}
    if ex:
        stages[0]["expert"] = _expert_summary(ex)
    if app and app.get("torque", 0.0) > 0:
        cks = application_load_checks(app, out_torque, out_torque * scale, load)
        stages[-1]["checks"] += [cdict(ch) for ch in cks]
        eng["app_load_checks"] = {ch.name: {"value": ch.value, "limit": ch.limit, "safety": ch.safety,
                                            "target": ch.target, "ok": ch.ok} for ch in cks}
    return eng


def candidates(p, payload: Dict, lang: str, max_results: int = 10, time_budget: float = 2.5) -> Dict:
    """Search of stepped-planet Wolfrom sets for the target ratio; smallest housing first."""
    from core.design import (MIN_MODULE, PLANET_CHOICES, STANDARD_MODULES, app_load_spec, housing_dims, z_min,
                             load_verdict, rim_min)
    t0 = time.time()
    target = p.target_ratio
    zmin = max(12, z_min(p.pressure_angle))
    eta0 = basic_efficiency(p.load)
    eta_sun = math.sqrt(eta0)
    modules = [p.module] if p.mode == "MANUAL" else [m for m in STANDARD_MODULES if m >= MIN_MODULE.get(p.mfg, 0.5)]
    n_list = [p.num_planets] if p.num_planets >= 2 else list(PLANET_CHOICES)
    tol = max(p.ratio_tol, 0.03)
    found = []
    sets = []
    for zs in range(zmin, 60):
        for zp1 in range(zmin, 70):
            for d in DIFFS:
                zp2 = zp1 + d
                if zp2 < zmin:
                    continue
                r, cf, i0, zr1, zr2 = ratio_of(zs, zp1, zp2)
                if abs(abs(r) - target) / target > 4 * tol:
                    continue
                eta, back = efficiencies(i0, eta0, eta_sun)
                if eta <= 0.05:
                    continue
                sets.append((zs, zp1, zp2, zr1, zr2, r, cf, i0, eta, back))
    sets.sort(key=lambda s: s[3])                         # smallest ring first
    load_case = p.load
    app = app_load_spec(p, {"bearing": "6810ZZ", "type": "DRUM"})
    cap = p.max_od if p.mode == "MAX_OD" else p.od_limit
    best_od = None
    for relax in (1, 4):
        for m in modules:
            for zs, zp1, zp2, zr1, zr2, r, cf, i0, eta, back in sets:
                if time.time() - t0 > time_budget and found:
                    break
                err = abs(abs(r) - target) / target
                if err > tol * relax:
                    continue
                n = next((k for k in n_list if (zs + zr1) % k == 0), 0)
                if not n:
                    continue
                g1 = stage_geometry(zs, zp1, zr1, m, p.pressure_angle, p.backlash, addendum=p.addendum)
                g2 = stage_geometry(max(zr2 - 2 * zp2, 6), zp2, zr2, m, p.pressure_angle, p.backlash,
                                    addendum=p.addendum)
                sup = output_support(g2.root_ring)
                ob = sup["code"]
                zr_eq = math.ceil(((sup["D"] / 2.0 + 0.6) - 1.25 * m) * 2.0 / m)
                hd = housing_dims(zr_eq, m, p.wall_t, p.tie_rod, p.motor_code)
                od = hd["envelope_d"]
                if (cap > 0 and od > cap) or (best_od is not None and od > best_od * 1.15):
                    continue
                if min(g1.eps_sun_planet, g1.eps_planet_ring, g2.eps_planet_ring) < (1.9 if p.hcr else 1.1):
                    continue
                tip = max(g1.tip_planet, g2.tip_planet)
                if 2.0 * g1.center_distance * math.sin(math.pi / n) - 2.0 * tip < max(0.5 * m, 0.8):
                    continue
                turns, err_rad = planet_phases(zs, zp1, zp2, n)
                if err_rad * g2.r_planet > 0.25 * p.backlash + 1e-6:
                    continue
                brg = _bearing_for(min(g1.root_planet, g2.root_planet), m, p.face_width, p.pin_steel, p.bearing,
                                   p.bearing_tol)
                if brg is None:
                    continue
                if g1.root_sun - p.motor_shaft_dia / 2.0 < max(1.2, 0.8 * rim_min(m)):
                    continue
                cand = {"zs": zs, "zp1": zp1, "zp2": zp2, "zr1": zr1, "zr2": zr2, "ratio": r, "carrier": cf, "i0": i0,
                        "eta": eta, "eta_back": back, "n": n, "module": m, "face_width": p.face_width, "geo1": g1,
                        "geo2": g2, "bearing": brg, "pin_steel": p.pin_steel, "out_bearing": ob, "hd": hd,
                        "support": sup, "turns": turns, "phase_err_mm": err_rad * g2.r_planet, "motor_shaft_dia": p.motor_shaft_dia,
                        "od": od, "err": err}
                from core.design import mount_spec
                cand["mount"] = mount_spec(p, hd)
                cand["arm"] = _arm(p)
                cand["eng"] = analyze(cand, load_case, lang, dict(app, bearing_c0=sup["C0"] or 1.0) if app else None)
                strong = cand["eng"]["margin"] >= 1.0 or not p.strength_required
                if strong and (best_od is None or od < best_od):
                    best_od = od
                found.append(cand)
        if any(c_["eng"]["margin"] >= 1.0 for c_ in found) or not p.strength_required:
            break
    results = []
    found.sort(key=lambda c_: (0 if c_["eng"]["margin"] >= 1.0 else 1, round(c_["od"], 1), c_["err"],
                               -c_["eng"]["margin"]))
    seen = set()
    for cand in found:
        key = (cand["module"], cand["zs"], cand["zp1"], cand["zp2"])
        if key in seen:
            continue
        seen.add(key)
        results.append(to_candidate(p, cand, lang))
        if len(results) >= max_results:
            break
    return {"candidates": results, "relaxed_tolerance": False, "search_pairs": len(sets), "pruned_pairs": 0,
            "elapsed": round(time.time() - t0, 3), "mode": p.mode,
            **({} if results else {"hint": ("No Wolfrom tooth set reaches this ratio here: try 60–400:1, a larger "
                                            "diameter or another module." if lang == "en" else
                                            "Bu oranda Wolfrom diş seti bulunamadı: 60–400:1 arası bir oran, daha büyük "
                                            "çap veya başka modül deneyin.")})}


def plate_t(p, fw: float) -> float:
    """
    Top cage plate (the bottom one follows it): the steel pins span bottom plate + both tooth sets + top plate, so
    the plates are thickened like a standard cage carrier (core.design.dowel_plate_t, <= 3 mm) until a standard
    ISO 8734 length fits — no pins cut to length.
    """
    from core.design import dowel_plate_t
    return dowel_plate_t(p.plate_t_asked or p.plate_t, 2.0 * fw + SET_GAP, True, p.pin_steel)


def length_of(p, cand: Dict) -> float:
    """Overall length of the CAD layout (wolfrom_cad uses the same numbers)."""
    from core.design import CLEARANCE
    from core.layout import bottom_plate_thickness
    motor = get_motor_info(p.motor_code)
    tie = cand["hd"]["tie"]
    flange_t = max(5.0, float(motor.get("pilot_depth", 0.0)) + 2.5, float(motor.get("screw_head_h", 3.0)) + 2.0,
                   tie["nut_m"] + 2.9)
    fw = cand["face_width"]
    t_top = plate_t(p, fw)
    t_bot = bottom_plate_thickness(t_top)
    z_lid0 = CLEARANCE + t_bot + CLEARANCE + fw + SET_GAP + fw + CLEARANCE + t_top + CLEARANCE
    ob = {"width": cand["support"]["width"]}
    lid_t = 6.0
    arm = 0.0
    if p.output_type == "DRUM_ARM":
        from core.design import declutch_height
        from core.layout import drum_arm_height
        arm = (declutch_height(p, cand["eng"]["output_torque"] * p.load.application_factor) if p.declutch
               else drum_arm_height(p.arm_shape, p.arm_width, p.arm_thickness))
    return flange_t + max(z_lid0, CLEARANCE + t_bot + CLEARANCE + fw + SET_GAP / 2 + ob["width"] + 2.5) + lid_t + arm


def to_candidate(p, cand: Dict, lang: str) -> Dict:
    from core.design import load_verdict
    eng = cand["eng"]
    out = {"type": p.output_type, "bearing": cand["out_bearing"], "hub_d": cand["support"]["d"],
           "shaft_d": 0.0, "drum": True, "strong": True, "seat_fits": True, "required_d": 0.0, "steel": False,
           "check_d": 0.0, "drum_od": cand["od"], "load_r": p.load_radius}
    eng["load"] = load_verdict(p, eng, out, abs(cand["ratio"]), 2, lang)
    length = length_of(p, cand)
    length_ok = p.max_length <= 0 or length <= p.max_length + 1e-6
    feasible = eng["margin"] >= 1.0 and length_ok
    word = "kilitli" if lang != "en" else "self-locking"
    stages = [{"z_sun": cand["zs"], "z_planet": cand["zp1"], "z_ring": cand["zr1"], "num_planets": cand["n"],
               "module": cand["module"], "ratio": round(1.0 / cand["carrier"], 4), "star": False,
               "bearing": cand["bearing"]["code"], "bearing_layout": "dual", "bearings_per_planet": 2,
               "pin_dia": cand["bearing"]["pin"], "pocket_dia": cand["bearing"]["pocket"], "x_sun": 0.0,
               "addendum": 1.0, "wolfrom": {"zp2": cand["zp2"], "zr2": cand["zr2"], "out_bearing": cand["out_bearing"]}}]
    label = (f"{abs(cand['ratio']):.2f}:1 · Wolfrom m{cand['module']:g} · Zs{cand['zs']} Zp{cand['zp1']}/{cand['zp2']} "
             f"Zr{cand['zr1']}/{cand['zr2']} · {cand['n']} planet · Ø{cand['od']:.0f}×{length:.0f} mm · "
             f"{cand['bearing']['code']} · {_support_word(cand['out_bearing'], lang)} · η {cand['eta'] * 100:.0f}%"
             f"{' · ' + word if cand['eta_back'] <= 0 else ''} · S {min(eng['margin'], 9.99):.2f}")
    return {"label": label, "total_ratio": round(abs(cand["ratio"]), 3), "error_percent": round(cand["err"] * 100, 2),
            "module": cand["module"], "z_ring": cand["zr1"], "outer_diameter": round(cand["od"], 1),
            "housing_diameter": round(cand["hd"]["body_d"], 1), "overall_length": round(length, 1),
            "body_length": round(length, 1), "length_ok": length_ok, "bed_ok": True, "footprint": round(cand["od"], 1),
            "tie_rod": cand["hd"]["tie_rod"], "feasible": feasible, "margin": round(eng["margin"], 3),
            "gear_margin": round(eng["margin"], 3), "fits": True,
            "issues": ([] if eng["margin"] >= 1.0 else ["strength"]) + ([] if length_ok else ["length"]),
            "required_output_dia": 0.0, "output": out, "stages": stages, "engineering": eng, "load": eng["load"],
            "arrangement": "WOLFROM", "reversed": cand["ratio"] < 0}


def _arm(p) -> Optional[Dict]:
    """Arm bolted onto the output ring lid (arm root bending, release pin) or None."""
    if p.output_type != "DRUM_ARM":
        return None
    return {"shape": p.arm_shape, "length": p.arm_length, "width": p.arm_width, "thickness": p.arm_thickness,
            "hub_d": 0.0, "drum": True, "declutch": p.declutch}


def _support_word(code: str, lang: str) -> str:
    if code != "PLAIN":
        return code
    return "kaymalı yatak" if lang != "en" else "plain bearing"


def resolve(payload: Dict, p, lang: str) -> Dict:
    """A Wolfrom candidate rebuilt from its payload (stages[0] + its 'wolfrom' entry) for the CAD."""
    st = payload["stages"][0]
    w = st["wolfrom"]
    zs, zp1, zp2 = int(st["z_sun"]), int(st["z_planet"]), int(w["zp2"])
    m = float(st.get("module") or payload.get("module") or 1.0)
    r, cf, i0, zr1, zr2 = ratio_of(zs, zp1, zp2)
    n = int(st["num_planets"])
    eta0 = basic_efficiency(p.load)
    eta, back = efficiencies(i0, eta0, math.sqrt(eta0))
    g1 = stage_geometry(zs, zp1, zr1, m, p.pressure_angle, p.backlash, addendum=p.addendum)
    g2 = stage_geometry(max(zr2 - 2 * zp2, 6), zp2, zr2, m, p.pressure_angle, p.backlash, addendum=p.addendum)
    brg = _bearing_for(min(g1.root_planet, g2.root_planet), m, p.face_width, p.pin_steel,
                       st.get("bearing") or p.bearing, p.bearing_tol) or \
        _bearing_for(min(g1.root_planet, g2.root_planet), m, p.face_width, p.pin_steel, "AUTO", p.bearing_tol)
    sup = output_support(g2.root_ring)
    ob = sup["code"]
    from core.design import housing_dims, app_load_spec
    zr_eq = math.ceil(((sup["D"] / 2.0 + 0.6) - 1.25 * m) * 2.0 / m)
    hd = housing_dims(zr_eq, m, p.wall_t, p.tie_rod, p.motor_code)
    turns, err = planet_phases(zs, zp1, zp2, n)
    cand = {"zs": zs, "zp1": zp1, "zp2": zp2, "zr1": zr1, "zr2": zr2, "ratio": r, "carrier": cf, "i0": i0, "eta": eta,
            "eta_back": back, "n": n, "module": m, "face_width": p.face_width, "geo1": g1, "geo2": g2, "bearing": brg,
            "pin_steel": p.pin_steel, "out_bearing": ob, "hd": hd, "support": sup, "turns": turns,
            "phase_err_mm": err * g2.r_planet,
            "motor_shaft_dia": p.motor_shaft_dia, "od": hd["envelope_d"], "err": 0.0}
    app = app_load_spec(p, {"bearing": "6810ZZ", "type": "DRUM"})
    from core.design import mount_spec
    cand["mount"] = mount_spec(p, hd)
    cand["arm"] = _arm(p)
    cand["eng"] = analyze(cand, p.load, lang, dict(app, bearing_c0=sup["C0"] or 1.0) if app else None)
    return cand
