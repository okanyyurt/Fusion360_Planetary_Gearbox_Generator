# -*- coding: utf-8 -*-
"""
Cycloidal drive: a high ratio in one compact stage, no gear teeth, very stiff and with almost no backlash.

    N steel ring pins (dowels, half sunk into the housing bore) on the pin circle R, radius rp
    two cycloid discs with N - 1 lobes on an eccentric input hub (eccentricity e, 180 deg apart: balanced)
    output: n_o steel output pins in the output plate run in holes of the discs (hole radius = pin radius + e)

    ratio  i = (N - 1) : 1, the output turns against the input
    disc   centre orbits with the input, the disc itself turns -1 / (N - 1)

Disc profile (Lehmann; disc centred, its eccentric offset along +x at input angle 0, pin k at angle 2 pi k / N):
    psi(t) = atan2(sin((1 - N) t), R / (e N) - cos((1 - N) t))
    x(t) =  R cos t - rp' cos(t + psi) - e cos(N t)
    y(t) = -R sin t + rp' sin(t + psi) + e sin(N t)          rp' = rp + backlash / 2 (running clearance)
Valid (no undercut) when every convex part of the base epitrochoid (rp = 0) is curved wider than rp'; the
shortening factor K1 = e N / R between 0.5 and 0.8 is the usual range.

Loads (Sensinger / Blanche & Yang, simplified): two discs share the torque (0.55 each with printed errors).
    largest ring pin force   F_max = 4 T_d / (K1 N R)          T_d = 0.55 T_out
    Hertz contact pin / disc (line contact over the disc thickness, the pin radius governs)
    output pin force         F_o = 4 T_d / (n_o R_o)             (about half of the pins carry, sinusoidally)
    output pin bending       both discs on the cantilever from the output plate
    disc hole bearing pressure  F_o / (d_o t)
    eccentric bearing        F_b = 1.4 T_d / ((N - 1) e eta)     (tangential + radial share of the input)
Efficiency of sliding (not rolling) pins on printed discs ~ 0.80 of the material's mesh efficiency.
"""
from __future__ import annotations

import math
import time
from typing import Dict, List, Optional, Tuple

from core.bearing_catalog import BEARING_CATALOG, get_bearing_info, real_bearings
from core.engineering import Check, LoadCase, application_load_checks, motor_shaft_check, CHECK_LABELS
from core.materials import STEEL_PIN, get_material

PIN_DIAMETERS = (4.0, 5.0, 6.0, 8.0, 10.0)        # ring pins: ISO 8734 dowels
OUT_PIN_DIAMETERS = (3.0, 4.0, 5.0, 6.0, 8.0, 10.0)
OUT_PIN_COUNTS = (8, 6, 4)
K1_CHOICES = (0.65, 0.75, 0.55)
HOLE_CLEAR = 0.25         # output pin hole: pin radius + e + this
DISC_SHARE = 0.55         # torque share of one disc (two discs, printed errors)
CAM_WALL = 1.2            # eccentric cam wall around the motor shaft bore
MIN_E = 0.6               # smaller eccentricities vanish in the printing tolerance
COVER_LIP = 2.0
HUB_INSERT_R = 3.2        # inserts at hub radius - this
N_RANGE = (7, 61)         # ring pins: ratio 6 ... 60

TEXT = {
    "tr": {"contact": "Yüzey basıncı halka pimi / disk", "out_pin": "Çıkış pimi eğilmesi",
           "hole": "Disk deliği ezilmesi (çıkış pimi)", "seat": "Halka pimi yuvası ezilmesi (gövde)",
           "bearing_static": "Eksantrik rulmanı statik s0", "bearing_life": "Eksantrik rulman ömrü L10h",
           "disc": "Sikloid diskler (2 adet, 180°)", "label": "Sikloidal",
           "note": "Sikloidal redüktör: dişsiz, çok rijit ve boşluğu çok az; çıkış girişin tersine döner. Verim ~%{e:.0f} "
                   "(kayan pimler — gresleyin). Geri sürülebilir: yük çıkışı çevirebilir, tutma için fren / tutma akımı "
                   "gerekir.",
           "hint": "Bu oranda sikloidal tasarım bulunamadı: 6–60:1 arası bir oran, daha büyük çap deneyin."},
    "en": {"contact": "Contact ring pin / disc", "out_pin": "Output pin bending",
           "hole": "Disc hole bearing pressure (output pin)", "seat": "Ring pin seat pressure (housing)",
           "bearing_static": "Eccentric bearing static s0", "bearing_life": "Eccentric bearing life L10h",
           "disc": "Cycloid discs (2, 180°)", "label": "Cycloidal",
           "note": "Cycloidal drive: no teeth, very stiff and almost free of backlash; the output turns against the input. "
                   "Efficiency ~{e:.0f} % (sliding pins — grease them). Back-drivable: the load can turn the output, "
                   "use a brake / holding current to hold it.",
           "hint": "No cycloidal design reaches this ratio here: try 6–60:1 or a larger diameter."},
}


# ---------------------------------------------------------------------------------------------------- geometry
def profile_points(n_pins: int, R: float, rp: float, e: float, samples: int = 0) -> List[Tuple[float, float]]:
    """Closed disc profile (disc centred at the origin), counter-clockwise, without the repeated end point."""
    n = n_pins
    samples = samples or max(240, 24 * (n - 1))
    pts = []
    for k in range(samples):
        t = 2.0 * math.pi * k / samples
        psi = math.atan2(math.sin((1 - n) * t), R / (e * n) - math.cos((1 - n) * t))
        x = R * math.cos(t) - rp * math.cos(t + psi) - e * math.cos(n * t)
        y = -R * math.sin(t) + rp * math.sin(t + psi) + e * math.sin(n * t)
        pts.append((x, y))
    pts.reverse()                                   # t runs clockwise
    return pts


def min_convex_radius(n_pins: int, R: float, e: float, samples: int = 2000) -> float:
    """Smallest radius of curvature of the convex parts of the base epitrochoid (rp = 0)."""
    n = n_pins
    best = float("inf")
    for k in range(samples):
        t = 2.0 * math.pi * k / samples
        xd = -R * math.sin(t) + e * n * math.sin(n * t)
        yd = -R * math.cos(t) + e * n * math.cos(n * t)
        xdd = -R * math.cos(t) + e * n * n * math.cos(n * t)
        ydd = R * math.sin(t) - e * n * n * math.sin(n * t)
        v = math.hypot(xd, yd)
        if v < 1e-9:
            return 0.0
        kappa = (xd * ydd - yd * xdd) / v ** 3      # clockwise curve: convex parts are negative
        if kappa < 0:
            best = min(best, -1.0 / kappa)
    return best


def disc_radii(n_pins: int, R: float, rp: float, e: float) -> Tuple[float, float]:
    pts = profile_points(n_pins, R, rp, e, 6 * (n_pins - 1) * 8)
    rs = [math.hypot(x, y) for x, y in pts]
    return min(rs), max(rs)


def disc_bearing(need_id: float, max_od: float, max_w: float) -> List[str]:
    """Eccentric bearings whose bore takes the cam, smallest outside first."""
    out = [c for c in real_bearings() if BEARING_CATALOG[c]["d_inner"] >= need_id
           and BEARING_CATALOG[c]["d_outer"] <= max_od and BEARING_CATALOG[c]["width"] <= max_w]
    out.sort(key=lambda c: (BEARING_CATALOG[c]["d_outer"], -BEARING_CATALOG[c]["C_kN"]))
    return out


def output_bearing(side_force: float, max_od: float) -> Optional[str]:
    """Cover bearing of the output hub: a thin-section bearing with a bore >= 20 mm (4 inserts in the hub)."""
    fits = [c for c in real_bearings() if c.startswith("68") and BEARING_CATALOG[c]["d_inner"] >= 20.0
            and BEARING_CATALOG[c]["d_outer"] <= max_od]
    fits.sort(key=lambda c: BEARING_CATALOG[c]["d_inner"])
    for c in fits:
        if BEARING_CATALOG[c]["C0_kN"] * 1000.0 >= 2.0 * side_force:
            return c
    return fits[-1] if fits else None


OUT_PLATE_MAX = 5.0       # mm the output plate may grow so the output pins are a standard length


def output_plate_t(t0: float, base: float, clr: float) -> float:
    """
    Output plate thickness. The steel output pins are pressed into it (their top 1 mm below its face) and reach
    down through both discs: at least to 1 mm above the bottom of disc A, at most to 0.3 mm above the floor. That
    window is only clr + 0.7 mm long, so the plate grows (<= OUT_PLATE_MAX) until a standard ISO 8734 length fits
    it — no pins cut to length. `base` = floor top -> plate bottom.
    """
    from core.hardware import DOWEL_LENGTHS
    for k in range(int(OUT_PLATE_MAX / 0.05) + 1):
        t_o = round(t0 + 0.05 * k, 2)
        hi = base + t_o - 1.3                  # pin bottom 0.3 above the floor
        lo = base - clr + t_o - 2.0            # pin bottom 1 mm above the bottom of disc A
        if any(lo - 1e-6 <= L <= hi + 1e-6 for L in DOWEL_LENGTHS):
            return t_o
    return t0


def layout(p, cand: Dict) -> Dict:
    """Axial layout (z = 0 at the motor flange top), shared by the engine (length) and the CAD."""
    from core.design import CLEARANCE as clr
    from core.design import declutch_height
    from core.layout import bottom_plate_thickness, drum_arm_height, FLANGE_PROTRUSION
    from core.motor_catalog import get_motor_info
    motor = get_motor_info(p.motor_code)
    tie = cand["hd"]["tie"]
    flange_t = max(5.0, float(motor.get("pilot_depth", 0.0)) + 2.5, float(motor.get("screw_head_h", 3.0)) + 2.0,
                   tie["nut_m"] + 2.9)
    t = cand["disc_t"]
    zd1 = clr + bottom_plate_thickness(p.plate_t) + clr       # same height as a first sun: the collar clears the motor
    zd2 = zd1 + t + clr
    zo0 = zd2 + t + clr
    t_o = output_plate_t(max(p.plate_t_asked or p.plate_t, 5.0), zo0 - (zd1 - clr), clr)
    zo1 = zo0 + t_o
    z_hs = zo1 + clr
    ob = get_bearing_info(cand["out_bearing"])
    z_cv1 = z_hs + ob["width"] + COVER_LIP
    z_hub1 = z_cv1 + FLANGE_PROTRUSION
    arm = 0.0
    if p.output_type == "ARM":
        t_ka = p.load.motor_torque * p.load.application_factor * cand["ratio"] * cand["eta"]
        arm = 0.4 + (declutch_height(p, t_ka) if p.declutch
                     else drum_arm_height(p.arm_shape, p.arm_width, p.arm_thickness))
    return {"flange_t": flange_t, "zd1": zd1, "zd2": zd2, "zo0": zo0, "zo1": zo1, "t_o": t_o, "z_hs": z_hs,
            "z_cv1": z_cv1, "z_hub1": z_hub1, "floor": zd1 - clr, "length": flange_t + z_hub1 + arm,
            "body_length": flange_t + z_cv1}


# ------------------------------------------------------------------------------------------------- engineering
def _expert(c: Dict, load: LoadCase) -> Dict:
    """
    Expert terms of a cycloidal drive: the power loss P_in (1 - eta) of the sliding pins heats the closed housing
    (heat balance), the pin / lobe contacts run 1.5 x hotter than the housing rise; a disc lobe is loaded about
    once per input turn. Wear of the sliding pin contact is not estimated (keep it greased).
    """
    from core import expert as X
    gm = get_material(load.gear_material)
    p_loss = load.motor_torque * 2.0 * math.pi * load.motor_speed / 60.0 * (1.0 - c["eta"])
    d = c["hd"]["body_d"]
    length = c["layout"]["body_length"]
    area = (math.pi * d * length + 2.0 * math.pi * d * d / 4.0) / 1e6
    rise = 1.5 * X.housing_rise(p_loss, area, load.duty)
    t_max = float(gm.get("t_max", 60))
    temp = load.ambient_c + rise
    f_t = X.temp_factor(temp, t_max)
    cycles = 60.0 * load.target_life_h * load.motor_speed
    y_nt, z_nt = X.cycle_factors(cycles)
    lube_mu = X.MU_GREASED if load.lube != "DRY" else X.MU_DRY.get(str(load.gear_material).upper(), 0.28)
    return {"temp": temp, "rise": rise, "t_max": t_max, "f_t": f_t, "y_nt": y_nt, "z_nt": z_nt, "cycles": cycles,
            "mu": lube_mu, "p_loss": p_loss, "wear": None}


def _expert_summary(ex: Dict) -> Dict:
    return {"temp": round(ex["temp"], 1), "t_max": ex["t_max"], "f_t": round(ex["f_t"], 3), "y_nt": round(ex["y_nt"], 3),
            "z_nt": round(ex["z_nt"], 3), "cycles": ex["cycles"], "mu": ex["mu"], "p_loss_w": round(ex["p_loss"], 2),
            **({"wear_mm": round(ex["wear"], 4), "wear_lim": round(ex["wear_lim"], 3)} if ex.get("wear") is not None
               else {})}


def analyze(c: Dict, load: LoadCase, lang: str, app: Optional[Dict] = None) -> Dict:
    T = TEXT["en" if lang == "en" else "tr"]
    gm, sm = get_material(load.gear_material), get_material(load.struct_material)
    n, R, rp, e, t = c["n_pins"], c["R"], c["rp"], c["e"], c["disc_t"]
    i = n - 1
    eta = c["eta"]
    t_in = load.motor_torque * load.application_factor
    t_out = t_in * i * eta
    td = DISC_SHARE * t_out * 1000.0                              # N mm per disc
    k1 = e * n / R
    f_max = 4.0 * td / (k1 * n * R)
    e_star = 1.0 / ((1 - gm["nu"] ** 2) / gm["E"] + (1 - 0.3 ** 2) / STEEL_PIN["E"])
    sig_h = math.sqrt(f_max * e_star / (math.pi * t * rp))
    raw = [("contact", sig_h, gm["sigma_H"], 2.0)]
    no, ro, do = c["n_out"], c["R_out"], c["d_out"]
    f_o = 4.0 * td / (no * ro)
    lay = c["layout"]
    lever = (lay["zo0"] - (lay["zd2"] + t / 2.0)) + (lay["zo0"] - (lay["zd1"] + t / 2.0))
    raw.append(("out_pin", 32.0 * f_o * lever / (math.pi * do ** 3), STEEL_PIN["sigma_S"], 1.0))
    raw.append(("hole", f_o / (do * t), gm["sigma_S"], 1.0))
    raw.append(("seat", f_max / (2.0 * rp * (2.0 * t + 0.6)), sm["sigma_S"], 1.0))
    brg = c["bearing"]
    f_b = 1.4 * td / (i * e * eta)
    raw.append(("bearing_static", brg["C0"] / max(f_b, 1e-6), 1.0, 1.0))
    n_rel = load.motor_speed * n / i
    life = (brg["C"] / max(f_b, 1e-6)) ** 3 * 1e6 / (60.0 * max(n_rel, 1e-6))
    raw.append(("bearing_life", life, load.target_life_h, 3.0))
    ex = _expert(c, load) if load.expert else None
    if ex:              # allowables at the contact temperature and over the load cycles of the target life
        mult = {"contact": ex["f_t"] * ex["z_nt"], "hole": ex["f_t"], "seat": ex["f_t"]}
        raw = [(nm, v, lim * mult.get(nm, 1.0), e) for nm, v, lim, e in raw]
    checks = []
    for name, value, limit, exp in raw:
        if name == "bearing_static":
            safety, tgt, unit = value, 1.0, ""
        elif name == "bearing_life":
            safety, tgt, unit = value / limit, 1.0, "h"
        else:
            safety, tgt, unit = limit / max(value, 1e-9), (load.target_sh if name == "contact" else load.target_sf), "MPa"
        checks.append(Check(name, value, limit, safety, tgt, unit, exp))
    checks.append(motor_shaft_check(t_in, c["motor_shaft_dia"], load))
    if ex:
        from core.expert import creep_check, special_checks
        checks += special_checks(ex, load)
        if load.hold_h > 0:
            t_nom = t_out / load.application_factor
            hold = (app or {}).get("torque", 0.0) or t_nom
            hole = next(ch.value for ch in checks if ch.name == "hole")
            checks.append(creep_check(hole / load.application_factor, gm["sigma_S"], hold / t_nom, load))
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
    labels = CHECK_LABELS["en" if lang == "en" else "tr"]

    def label(name):
        return T.get(name) if name in T else labels.get(name, name)

    def cdict(ch):
        return {"name": ch.name, "label": label(ch.name), "value": ch.value, "limit": ch.limit, "safety": ch.safety,
                "target": ch.target, "unit": ch.unit, "ok": ch.ok}
    out_torque = t_out / load.application_factor
    out_speed = load.motor_speed / i
    stage = {"index": 1, "ratio": float(i), "title": T["disc"], "star": False, "input_torque": load.motor_torque,
             "output_torque": out_torque, "sun_speed": load.motor_speed, "carrier_speed": out_speed, "ring_speed": 0.0,
             "planet_speed_rel": n_rel, "tangential_force": f_max,
             "pitch_velocity": 2 * math.pi * e * load.motor_speed / 60000.0, "eps_alpha_sp": 0.0, "eps_alpha_pr": 0.0,
             "eps_beta": 0.0, "addendum": 1.0, "tip_land": 0.0, "depth_factor": {}, "checks": [cdict(ch) for ch in checks]}
    eng = {"total_ratio": float(i), "efficiency": eta, "reverse": False, "star": False,
           "input_torque": load.motor_torque, "input_speed": load.motor_speed, "output_torque": out_torque,
           "output_speed": out_speed, "max_output_torque": out_torque * scale, "margin": scale,
           "limiting": ({"stage": 1, "check": limiting.name, "label": label(limiting.name)} if limiting else None),
           "all_ok": all(ch.ok for ch in checks), "stages": [stage],
           "load_case": {"application_factor": load.application_factor, "target_sf": load.target_sf,
                         "target_sh": load.target_sh, "target_life_h": load.target_life_h,
                         "gear_material": load.gear_material, "struct_material": load.struct_material},
           "cycloid": {"k1": k1, "f_max": f_max, "eta": eta, "text": T["note"].format(e=eta * 100.0)},
           "app_load_checks": None}
    if ex:
        stage["expert"] = _expert_summary(ex)
    if app and app.get("torque", 0.0) > 0:
        cks = application_load_checks(app, out_torque, out_torque * scale, load)
        stage["checks"] += [cdict(ch) for ch in cks]
        eng["app_load_checks"] = {ch.name: {"value": ch.value, "limit": ch.limit, "safety": ch.safety,
                                            "target": ch.target, "ok": ch.ok} for ch in cks}
    return eng


# ------------------------------------------------------------------------------------------------------ search
def _efficiency(load: LoadCase) -> float:
    """Sliding ring pins on printed discs: 0.85 of the mesh efficiency greased; dry (expert mode) 0.70."""
    dry = load.expert and load.lube == "DRY"
    return (0.70 if dry else 0.85) * get_material(load.gear_material)["eta"]


def build(p, n_pins: int, R: float, rp: float, k1: float, lang: str, out_d_pref: float = 0.0) -> Optional[Dict]:
    """One complete design (geometry, bearings, output pins, housing) or None when it does not fit."""
    from core.design import DOWEL_DIAMETERS, app_load_spec, housing_dims, shaft_extent
    n = n_pins
    e = round(k1 * R / n / 0.05) * 0.05
    if e < MIN_E:
        return None
    rpc = rp + p.backlash / 2.0
    if 2.0 * R * math.sin(math.pi / n) - 2.0 * rp < 1.2:          # neighbouring pins
        return None
    if min_convex_radius(n, R, e) < rpc + 0.3:                    # undercut / pointed lobes
        return None
    r_min, r_max = disc_radii(n, R, rpc, e)
    if r_max + e > R - 0.4:                                       # lobe tips must clear the bore between the pins
        return None
    t = max(6.0, min(float(p.face_width), 20.0))
    need_id = 2.0 * (shaft_extent(p.motor_shaft_dia, p.motor_shaft_type) + e + CAM_WALL)
    best = None
    for code in disc_bearing(need_id, 2.0 * (r_min - 4.0), t)[:3]:
        b = get_bearing_info(code)
        r_in = b["d_outer"] / 2.0 + p.bearing_tol / 2.0 + 1.6
        for no in OUT_PIN_COUNTS:
            for do in OUT_PIN_DIAMETERS:
                if do not in DOWEL_DIAMETERS:
                    continue
                h = do / 2.0 + e + HOLE_CLEAR
                ro = r_in + h
                if ro + h > r_min - 1.8:
                    continue
                if 2.0 * ro * math.sin(math.pi / no) - 2.0 * h < 1.6:
                    continue
                score = no * do ** 3 * ro
                if best is None or score > best[0]:
                    best = (score, code, no, do, ro)
        if best:
            break
    if best is None:
        return None
    _, code, no, do, ro = best
    b = get_bearing_info(code)
    zr_eq = math.ceil(2.0 * (R + rp + 0.4 - 1.25))
    hd = housing_dims(zr_eq, 1.0, p.wall_t, p.tie_rod, p.motor_code)
    app0 = app_load_spec(p, {"bearing": "6804ZZ", "type": p.output_type, "shaft_d": 0.0, "steel": False})
    ob = output_bearing(app0["force"] if app0 else 0.0, 2.0 * (hd["wall_r"] - 3.0))
    if ob is None:
        return None
    cand = {"n_pins": n, "ratio": float(n - 1), "R": R, "rp": rp, "rpc": rpc, "e": e, "k1": e * n / R, "disc_t": t,
            "r_min": r_min, "r_max": r_max, "bearing": {"code": code, "d": b["d_inner"], "D": b["d_outer"],
                                                         "width": b["width"], "C": b["C_kN"] * 1000.0,
                                                         "C0": b["C0_kN"] * 1000.0},
            "n_out": no, "d_out": do, "R_out": ro, "hole_r": do / 2.0 + e + HOLE_CLEAR, "hd": hd, "out_bearing": ob,
            "od": hd["envelope_d"], "eta": _efficiency(p.load), "motor_shaft_dia": p.motor_shaft_dia}
    cand["layout"] = layout(p, cand)
    from core.design import mount_spec
    cand["mount"] = mount_spec(p, hd)
    cand["arm"] = ({"shape": p.arm_shape, "length": p.arm_length, "width": p.arm_width, "thickness": p.arm_thickness,
                    "hub_d": 0.0, "drum": True, "declutch": p.declutch} if p.output_type == "ARM" else None)
    app = app_load_spec(p, {"bearing": ob, "type": p.output_type, "shaft_d": 0.0, "steel": False})
    cand["eng"] = analyze(cand, p.load, lang, app)
    return cand


def candidates(p, payload: Dict, lang: str, max_results: int = 10, time_budget: float = 2.5) -> Dict:
    t0 = time.time()
    T = TEXT["en" if lang == "en" else "tr"]
    target = p.target_ratio
    tol = max(p.ratio_tol, 0.02)
    ns = sorted({n for n in range(N_RANGE[0], N_RANGE[1] + 1) if abs((n - 1) - target) / target <= max(tol, 0.5 / target)},
                key=lambda n: abs((n - 1) - target))
    cap = p.max_od if p.mode == "MAX_OD" else p.od_limit
    found = []
    best_od = None
    for n in ns[:2]:
        for R in [15.0 + 2.5 * k for k in range(40)]:
            if time.time() - t0 > time_budget and found:
                break
            for rp_d in PIN_DIAMETERS:
                for k1 in K1_CHOICES:
                    cand = build(p, n, R, rp_d / 2.0, k1, lang)
                    if cand is None:
                        continue
                    if (cap > 0 and cand["od"] > cap) or (best_od is not None and cand["od"] > best_od * 1.25):
                        continue
                    cand["err"] = abs(cand["ratio"] - target) / target
                    found.append(cand)
                    if (cand["eng"]["margin"] >= 1.0 or not p.strength_required) and \
                            (best_od is None or cand["od"] < best_od):
                        best_od = cand["od"]
            if best_od is not None and 2.0 * R > best_od * 1.25:
                break
    found.sort(key=lambda c: (0 if c["eng"]["margin"] >= 1.0 else 1, c["err"], round(c["od"], 0), -c["eng"]["margin"]))
    results, seen = [], set()
    for cand in found:
        key = (cand["n_pins"], cand["R"], cand["rp"])
        if key in seen:
            continue
        seen.add(key)
        results.append(to_candidate(p, cand, lang))
        if len(results) >= max_results:
            break
    return {"candidates": results, "relaxed_tolerance": False, "search_pairs": len(found), "pruned_pairs": 0,
            "elapsed": round(time.time() - t0, 3), "mode": p.mode, **({} if results else {"hint": T["hint"]})}


def to_candidate(p, cand: Dict, lang: str) -> Dict:
    from core.design import load_verdict
    eng = cand["eng"]
    ob = get_bearing_info(cand["out_bearing"])
    out = {"type": p.output_type, "bearing": cand["out_bearing"], "hub_d": ob["d_inner"], "shaft_d": 0.0,
           "drum": False, "strong": True, "seat_fits": True, "required_d": 0.0, "steel": False, "check_d": 0.0,
           "load_r": p.load_radius}
    eng["load"] = load_verdict(p, eng, out, cand["ratio"], 1, lang)
    length = cand["layout"]["length"]
    length_ok = p.max_length <= 0 or length <= p.max_length + 1e-6
    feasible = eng["margin"] >= 1.0 and length_ok
    pins = "pim" if lang != "en" else "pins"
    stages = [{"z_sun": 0, "z_planet": cand["n_pins"] - 1, "z_ring": cand["n_pins"], "num_planets": 2, "module": 1.0,
               "ratio": cand["ratio"], "star": False, "bearing": cand["bearing"]["code"], "bearing_layout": "single",
               "bearings_per_planet": 1, "pin_dia": cand["d_out"], "pocket_dia": cand["bearing"]["D"], "x_sun": 0.0,
               "addendum": 1.0,
               "cycloid": {"n_pins": cand["n_pins"], "R": cand["R"], "rp": cand["rp"], "e": cand["e"],
                           "disc_t": cand["disc_t"], "n_out": cand["n_out"], "d_out": cand["d_out"],
                           "R_out": cand["R_out"], "bearing": cand["bearing"]["code"],
                           "out_bearing": cand["out_bearing"]}}]
    label = (f"{cand['ratio']:.0f}:1 · {TEXT['en' if lang == 'en' else 'tr']['label']} · {cand['n_pins']} {pins} "
             f"Ø{2 * cand['rp']:g} @ R{cand['R']:g} · e {cand['e']:.2f} · Ø{cand['od']:.0f}×{length:.0f} mm · "
             f"{cand['bearing']['code']} · {cand['n_out']}×Ø{cand['d_out']:g} · S {min(eng['margin'], 9.99):.2f}")
    return {"label": label, "total_ratio": cand["ratio"], "error_percent": round(cand["err"] * 100, 2), "module": 1.0,
            "z_ring": cand["n_pins"], "outer_diameter": round(cand["od"], 1),
            "housing_diameter": round(cand["hd"]["body_d"], 1), "overall_length": round(length, 1),
            "body_length": round(cand["layout"]["body_length"], 1), "length_ok": length_ok, "bed_ok": True,
            "footprint": round(cand["od"], 1), "tie_rod": cand["hd"]["tie_rod"], "feasible": feasible,
            "margin": round(eng["margin"], 3), "gear_margin": round(eng["margin"], 3), "fits": True,
            "issues": ([] if eng["margin"] >= 1.0 else ["strength"]) + ([] if length_ok else ["length"]),
            "required_output_dia": 0.0, "output": out, "stages": stages, "engineering": eng, "load": eng["load"],
            "arrangement": "CYCLOID", "reversed": True}


def resolve(payload: Dict, p, lang: str) -> Dict:
    """The design of a payload (stages[0]['cycloid']) rebuilt for the CAD."""
    cy = payload["stages"][0]["cycloid"]
    n, R, rp = int(cy["n_pins"]), float(cy["R"]), float(cy["rp"])
    k1 = float(cy["e"]) * n / R
    cand = build(p, n, R, rp, k1, lang)
    if cand is None:
        raise ValueError("cycloid design does not fit any more")
    cand["err"] = 0.0
    return cand
