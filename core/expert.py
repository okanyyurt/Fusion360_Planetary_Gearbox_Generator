# -*- coding: utf-8 -*-
"""
Expert mode: operating temperature, load-cycle life, wear and creep of plastic gears (the planetary arrangements).

Tooth temperature (structure of VDI 2736-2, root temperature; constants for plastic / plastic, approximate):
    theta = theta_0 + P mu 136 (u + 1) / (z1 + 5 u) [k2 17100 / (b z1 (v m)^0.75) + 6.3 R_lambda / A_G] ED^0.64
        P      power through the sun / planet meshes [kW] (nominal torque x relative speed)
        mu     tooth friction: greased plastic 0.07, dry by material (0.22 ... 0.30)
        k2     2.4 (plastic / plastic)
        v, m   pitch line velocity relative to the carrier [m/s], module [mm]; b face width, z1 sun teeth
        R/A    heat transfer resistance of the closed printed housing 0.172 K m^2/W over its surface of the stage
               (open gearbox, no housing: 0)
        ED     relative duty (share of the time the gearbox runs)
    The strength falls with the temperature: allowables x f_T, f_T = 1 at 23 C down to 0.5 at the material's limit
    (t_max); above t_max the temperature check fails.
Load-cycle life (material values taken at 10^6 cycles; plastic S-N slopes, approximate):
    N = 60 h n_rel N_planets (the sun tooth sees most cycles), root Y_NT = (10^6 / N)^(1/10) in [0.6, 1.3],
    flank Z_NT = (10^6 / N)^(1/15) in [0.7, 1.2]
Wear (VDI 2736-2): W = T_sun 2 pi N_rev k_w / (b z1 l_fl), l_fl = 2.25 m, allowed 0.15 m; k_w by material
(dry, approximate), greased x 0.2.
Creep under a sustained load (holding a load at rest for t hours): the root stress at the holding torque against
sigma_F c(t), c(t) = 0.55 - 0.07 log10(t) (>= 0.2).
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from core.materials import get_material

MU_GREASED = 0.07
MU_DRY = {"PLA": 0.30, "PETG": 0.30, "ABS": 0.30, "PA12": 0.25, "PACF": 0.22, "PC": 0.30, "RESIN": 0.30,
          "POM": 0.25}
KW_DRY = {"PLA": 6e-6, "PETG": 6e-6, "ABS": 8e-6, "PA12": 3e-6, "PACF": 3e-6, "PC": 8e-6, "RESIN": 1e-5,
          "POM": 2e-6}                                   # mm^3 / (N m)
K2_PLASTIC = 2.4
R_LAMBDA_PRINTED = 0.172                                 # K m^2 / W, closed plastic housing
WEAR_LIMIT = 0.15                                        # x module
T_ROOM = 23.0


def stage_terms(gear_material: str, geo, b: float, n_planets: int, housing: bool, lube: str) -> Dict:
    """Torque / speed independent part of the expert terms of one stage (stored in the stage factors)."""
    gm = get_material(gear_material)
    code = str(gear_material).upper()
    u = geo.z_planet / geo.z_sun
    d_ring = 2.0 * geo.root_ring + 6.0                   # housing around the ring teeth (wall)
    length = b + 12.0                                    # this stage's share of the housing length
    area = (math.pi * d_ring * length + 0.5 * math.pi * d_ring ** 2 / 4.0) / 1e6
    dry = str(lube).upper() == "DRY"
    metal = not gm["printed"] and gm["E"] > 20000.0
    mu = (MU_DRY.get(code, 0.28) if dry else MU_GREASED) if not metal else 0.06
    kw = KW_DRY.get(code, 6e-6) * (1.0 if dry else 0.2) * (0.05 if metal else 1.0)
    return {"geo": 136.0 * (u + 1.0) / (geo.z_sun + 5.0 * u), "b": b, "z1": geo.z_sun, "m": geo.module,
            "ra": (R_LAMBDA_PRINTED / area) if housing else 0.0, "mu": mu, "kw": kw, "n_pl": n_planets,
            "t_max": float(gm.get("t_max", 60)), "l_fl": 2.25 * geo.module}


def temp_factor(temp: float, t_max: float) -> float:
    """Allowable stress factor at the tooth temperature: 1 at 23 C down to 0.5 at the material limit."""
    span = max(t_max - T_ROOM, 1.0)
    return min(1.0, max(0.3, 1.0 - 0.5 * (temp - T_ROOM) / span))


def cycle_factors(cycles: float) -> Tuple[float, float]:
    """(root Y_NT, flank Z_NT) for the load cycles of the target life (material values at 10^6 cycles)."""
    cycles = max(cycles, 1.0)
    return min(1.3, max(0.6, (1e6 / cycles) ** 0.1)), min(1.2, max(0.7, (1e6 / cycles) ** (1.0 / 15.0)))


def housing_rise(p_loss_w: float, area_m2: float, duty: float) -> float:
    """Heat balance of a closed printed housing: the power loss leaves through its wall (alpha = 1 / 0.172)."""
    return p_loss_w * R_LAMBDA_PRINTED / max(area_m2, 1e-4) * max(duty, 0.01) ** 0.64


def terms(x: Dict, torque_nom: float, n_rel: float, v: float, load) -> Dict:
    """Temperature, strength factors and wear of one stage at the nominal sun torque [Nm] and relative speed."""
    p_kw = torque_nom * 2.0 * math.pi * n_rel / 60.0 / 1000.0
    vm = max(v * x["m"], 1e-4) ** 0.75
    rise = p_kw * x["mu"] * x["geo"] * (K2_PLASTIC * 17100.0 / (x["b"] * x["z1"] * vm) + 6.3 * x["ra"]) \
        * max(load.duty, 0.01) ** 0.64
    temp = load.ambient_c + rise
    f_t = temp_factor(temp, x["t_max"])
    n_rev = 60.0 * load.target_life_h * max(n_rel, 1e-6)
    cycles = n_rev * x["n_pl"]
    y_nt, z_nt = cycle_factors(cycles)
    wear = torque_nom * 2.0 * math.pi * n_rev * x["kw"] / (x["b"] * x["z1"] * x["l_fl"])
    return {"temp": temp, "rise": rise, "f_t": f_t, "y_nt": y_nt, "z_nt": z_nt, "wear": wear,
            "wear_lim": WEAR_LIMIT * x["m"], "cycles": cycles, "mu": x["mu"], "t_max": x["t_max"]}


def margins(t: Dict, load) -> Tuple[float, float]:
    """(temperature margin, wear margin): >= 1 is OK (both linear in the torque)."""
    m_temp = (t["t_max"] - load.ambient_c) / max(t["rise"], 1e-9) if t["t_max"] > load.ambient_c else 0.0
    return m_temp, t["wear_lim"] / max(t["wear"], 1e-12)


def creep_factor(hours: float) -> float:
    return max(0.2, 0.55 - 0.07 * math.log10(max(hours, 1.0)))


def special_checks(ex: Dict, load) -> List:
    """Temperature and (when known) wear checks of the Wolfrom / cycloidal expert terms (linear in the torque)."""
    from core.engineering import Check
    out = [Check("tooth_temp", ex["temp"], ex["t_max"],
                 (ex["t_max"] - load.ambient_c) / max(ex["rise"], 1e-9) if ex["t_max"] > load.ambient_c else 0.0,
                 1.0, "°C", 1.0)]
    if ex.get("wear") is not None:
        out.append(Check("wear_sun", ex["wear"], ex["wear_lim"], ex["wear_lim"] / max(ex["wear"], 1e-12), 1.0,
                         "mm", 1.0))
    return out


def creep_check(stress_nominal: float, allow_static: float, ratio_hold: float, load):
    """Creep of a load held at rest: the nominal stress scaled to the holding torque against allow x c(t)."""
    from core.engineering import Check
    s = stress_nominal * ratio_hold
    allow = allow_static * creep_factor(load.hold_h)
    return Check("creep", s, allow, allow / max(s, 1e-9), 1.0, "MPa", 0.0)
