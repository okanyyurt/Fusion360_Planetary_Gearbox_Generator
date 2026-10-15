"""
Engineering checks for a planetary gearbox (units: N, mm, MPa, Nm, rpm).

Method (simplified ISO 6336 / AGMA 2001 / VDI 2736 approach, suitable for design screening):

Loads per stage k (sun input, ring fixed, carrier output; a "star" stage: carrier fixed, ring output,
i = Zr/Zs, the planets turn on fixed axes, n_rel = n_sun — same tooth and planet bearing forces)
    T_k        = T_motor * K_A * prod(i_j * eta_j, j < k)          sun torque incl. application factor
    speed-up (reverse power flow, input at the carrier): T_k = T_in * K_A / prod(i_j, j >= k), no
                 efficiency credit on the way down (conservative for every tooth, pin and bearing)
    F_t        = 2000 * T_k / (d_sun * N) * K_gamma                tangential force per planet mesh [N]
    K_gamma    = load sharing factor (N=3: 1.15 machined / 1.25 printed, rises with N)
    v          = pi * d_sun * (n_sun - n_carrier) / 60000          pitch line velocity [m/s]
    K_v        = (A + v) / A, A = 6.1 (machined) or 3.05 (printed)  (Barth)

Face load factor (simplified ISO 6336-1 method C): the load is not uniform across the face width
    F_beta_x   = misalignment across b (per helix of a herringbone) [um]: pin tilt from the relative hole
                 position error of the carrier plates (FDM 0.02 / resin 0.015 / CNC 0.005 mm) + pin deflection
                 under load (cage: the torque-free plate winds up, guided pins; single plate: cantilever pin)
    F_beta_y   = F_beta_x * running-in factor (plastics 0.35: creep / wear conform the flanks, metals 0.85)
    c_gamma    = 20 N/(mm um) * E / 210000                          mesh stiffness of the material pair
    w_m        = F_t * K_v / b                                      mean line load [N/mm]
    K_Hbeta    = 1 + c_gamma F_beta_y / (2 w_m)    (<= 2, contact over the whole width)
               = sqrt(2 c_gamma F_beta_y / w_m)    (> 2, only part of the width carries)
    K_Fbeta    = K_Hbeta ^ N_F,  N_F = (b/h)^2 / (1 + b/h + (b/h)^2)
    -> a wider gear carries less than in proportion; the factor is load dependent, the capacity is found
       by solving for the torque at which the smallest safety meets its target

Tooth root bending (Lewis form factor + ISO 6336-3 load-sharing factors)
    sigma_F    = F_t * K_v * K_Fbeta * Y_eps * Y_beta / (b * m_n * Y(z_v))   m_n = m*cos(beta), z_v = z / cos^3(beta)
    Y          = Lewis form factor (Shigley table, 20 deg full depth), scaled for 14.5 / 25 deg and for the
                 tooth depth h_a* (ratio of the ISO 6336-3 form x stress factors Y_F·Y_S, load at the actual
                 tip, against the same tooth with standard depth; 1.0 for h_a* = 1)
    Y_eps      = 0.25 + 0.75 / eps_alpha_n,  eps_alpha_n = eps_alpha / cos^2(beta_b)
    Y_beta     = 1 - min(eps_beta, 1) * beta[deg] / 120   (>= 0.75)
    planet     : idler gear, reversed bending -> allowable * 0.7
    S_F        = sigma_F,lim / sigma_F

Contact (Hertz, ISO 6336-2 form)
    sigma_H    = Z_E Z_H Z_eps Z_beta sqrt(F_t K_v K_Hbeta / (b d_1) * (u +/- 1) / u)
    S_H        = sigma_H,lim / sigma_H

Planet bearings
    F_r        = 2 F_t per planet (sun and ring forces add), shared by the bearings of a planet
    L10h       = (C / P)^3 * 1e6 / (60 * n_planet,rel),   s0 = C0 / P

Pins, sun core and shafts
    pin bending: single plate (cantilever) M = F_r * lever, cage (two plates) M = F_r * span / 4
    torsion    : tau = 16 T d_o / (pi (d_o^4 - d_i^4)),  allowable 0.5 * sigma_S
                 printed parts loaded across layers (vertical axis): allowable * 0.6

Every check scales with the transmitted torque T as  safety ~ T^-exponent, so the maximum
continuous output torque is  T_out * min((S / S_target)^(1/exponent)).
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.bearing_catalog import get_bearing_info
from core.gear_geometry import StageGeometry, depth_strength_factors, overlap_ratio
from core.materials import STEEL_PIN, get_material

# Lewis form factor Y (20 deg, full depth) — Shigley, Mechanical Engineering Design, Table 14-2
_LEWIS = [(12, 0.245), (13, 0.261), (14, 0.277), (15, 0.290), (16, 0.296), (17, 0.303), (18, 0.309),
          (19, 0.314), (20, 0.322), (21, 0.328), (22, 0.331), (24, 0.337), (26, 0.346), (28, 0.353),
          (30, 0.359), (34, 0.371), (38, 0.384), (43, 0.397), (50, 0.409), (60, 0.422), (75, 0.435),
          (100, 0.447), (150, 0.460), (300, 0.472), (400, 0.480), (10000, 0.485)]
_PA_SCALE = {14.5: 0.83, 20.0: 1.0, 25.0: 1.12}
PRINTED_TORSION_FACTOR = 0.6
PLANET_REVERSE_BENDING = 0.7
MESH_STIFFNESS_STEEL = 20.0     # c_gamma of a steel pair, N/(mm um) (ISO 6336-1)
KHB_MAX = 8.0                   # beyond this the mesh is essentially one corner (reported, not extrapolated)
# relative pin hole position error between the carrier plates, mm (plates printed together: the scale error of the
# printer is common to both and does not tilt the pins, only the random part does)
MFG_ERROR = {"FDM_3D": 0.02, "SLA_RESIN": 0.015, "CNC_METAL": 0.005, "CUSTOM": 0.02}

CHECK_LABELS = {
    "tr": {"bend_sun": "Diş dibi eğilme — güneş", "bend_planet": "Diş dibi eğilme — planet",
           "bend_ring": "Diş dibi eğilme — çember", "contact_sun_planet": "Yüzey basıncı güneş/planet",
           "contact_planet_ring": "Yüzey basıncı planet/çember", "bearing_life": "Planet rulman ömrü L10h",
           "bearing_static": "Rulman statik emniyet s0", "bushing_pressure": "Burç yüzey basıncı",
           "pin_bending": "Pim eğilme", "sun_core_torsion": "Güneş çekirdeği burulma",
           "shaft_torsion": "Kademe arası mil burulma", "output_shaft_torsion": "Çıkış (mil/flanş göbeği) burulma",
           "arm_bending": "Kol kökü eğilme", "arm_key": "Kol–göbek düzlük kilidi (ezilme)",
           "motor_shaft_torsion": "Motor mili burulma (çelik)",
           "hub_nut_layer": "Çıkış göbeği somun yuvası katmanı burulma",
           "load_drive": "Uygulama yükü — motor + oran yeterliliği (rezerv)",
           "load_capacity": "Uygulama yükü — redüktör dayanımı",
           "load_bearing": "Uygulama yükü — çıkış rulmanı yan yük (s0)",
           "load_shaft": "Uygulama yükü — çıkış mili eğilme + burulma",
           "drum_bolts": "Tambur flanş vidaları (delik ezilmesi)",
           "drum_join": "Tambur yarıları birleşim vidaları (delik ezilmesi)",
           "mount_rods": "Montaj braketi — bağlantı cıvataları raf deliklerinde (ezilme)",
           "tooth_temp": "Diş sıcaklığı (VDI 2736, diş dibi)", "wear_sun": "Aşınma derinliği — güneş (VDI 2736)",
           "creep": "Durarak yük tutma — sünme (diş dibi)",
           "declutch_hole": "Boşa alma pimi — delik ezilmesi (bilezik / kol)",
           "declutch_shear": "Boşa alma pimi — kesme"},
    "en": {"bend_sun": "Tooth root bending — sun", "bend_planet": "Tooth root bending — planet",
           "bend_ring": "Tooth root bending — ring", "contact_sun_planet": "Contact stress sun/planet",
           "contact_planet_ring": "Contact stress planet/ring", "bearing_life": "Planet bearing life L10h",
           "bearing_static": "Bearing static safety s0", "bushing_pressure": "Bushing surface pressure",
           "pin_bending": "Pin bending", "sun_core_torsion": "Sun core torsion",
           "shaft_torsion": "Inter-stage shaft torsion", "output_shaft_torsion": "Output (shaft/flange hub) torsion",
           "arm_bending": "Arm root bending", "arm_key": "Arm–hub flat lock (bearing pressure)",
           "motor_shaft_torsion": "Motor shaft torsion (steel)",
           "hub_nut_layer": "Output hub nut-pocket layer torsion",
           "load_drive": "Application load — motor + ratio (reserve)",
           "load_capacity": "Application load — gearbox strength",
           "load_bearing": "Application load — output bearing side load (s0)",
           "load_shaft": "Application load — output shaft bending + torsion",
           "drum_bolts": "Drum flange screws (hole bearing pressure)",
           "drum_join": "Drum half joint screws (hole bearing pressure)",
           "mount_rods": "Mounting bracket — tie rods in the shelf holes (bearing pressure)",
           "tooth_temp": "Tooth temperature (VDI 2736, root)", "wear_sun": "Wear depth — sun (VDI 2736)",
           "creep": "Holding a load at rest — creep (root)",
           "declutch_hole": "Release pin — hole bearing pressure (collar / arm)",
           "declutch_shear": "Release pin — shear"},
}


def lewis_y(z: float, pressure_angle: float = 20.0) -> float:
    scale = _PA_SCALE.get(round(pressure_angle, 1), 1.0)
    if z <= _LEWIS[0][0]:
        (z0, y0), (z1, y1) = _LEWIS[0], _LEWIS[1]
        return max(0.18, y0 + (z - z0) * (y1 - y0) / (z1 - z0)) * scale
    for (z0, y0), (z1, y1) in zip(_LEWIS, _LEWIS[1:]):
        if z <= z1:
            return (y0 + (z - z0) * (y1 - y0) / (z1 - z0)) * scale
    return _LEWIS[-1][1] * scale


def load_sharing(n_planets: int, printed: bool) -> float:
    base = {3: 1.15, 4: 1.25, 5: 1.35, 6: 1.44}.get(n_planets, 1.5)
    return base + (0.10 if printed else 0.0)


def torsion_allowable(material: Dict, across_layers: bool = True) -> float:
    return 0.5 * material["sigma_S"] * (PRINTED_TORSION_FACTOR if material["printed"] and across_layers else 1.0)


@dataclass
class LoadCase:
    motor_torque: float = 0.4          # Nm, continuous
    motor_speed: float = 300.0         # rpm
    application_factor: float = 1.25   # K_A
    target_sf: float = 1.5             # bending / structural safety
    target_sh: float = 1.0             # contact safety
    target_life_h: float = 2000.0      # planet bearing L10h
    gear_material: str = "PLA"
    struct_material: str = "PLA"
    # expert mode (core.expert): operating temperature, load-cycle life, wear, creep
    expert: bool = False
    ambient_c: float = 23.0            # ambient temperature
    duty: float = 1.0                  # relative duty ED (share of the time running)
    lube: str = "GREASE"               # GREASE / DRY
    hold_h: float = 0.0                # hours a load is held at rest (creep), 0 = none
    housing: bool = True               # closed printed housing (heat through its wall)


@dataclass
class StageDesign:
    geo: StageGeometry
    num_planets: int
    face_width: float
    helix_deg: float
    herringbone: bool
    bearing_code: str
    bearings_per_planet: int           # 0 = plain pin bushing
    pin_dia: float
    pin_steel: bool
    carrier_cage: bool                 # True: pins supported by two plates
    plate_t: float = 3.5
    clearance: float = 0.5
    sun_bore_dia: float = 0.0          # bore inside the sun core (motor shaft / inter-stage shaft)
    inter_shaft_dia: float = 0.0       # printed D-shaft driving this sun (legacy), 0 = none
    neck_dia: float = 0.0              # sun printed in one piece with the previous carrier: neck diameter
    star: bool = False                 # carrier fixed, ring output (rotating housing): i = Zr / Zs
    mfg_error: float = 0.02            # relative pin hole position error of the carrier, mm (face load factor)

    @property
    def ratio(self) -> float:
        if self.star:
            return self.geo.z_ring / self.geo.z_sun
        return 1.0 + self.geo.z_ring / self.geo.z_sun

    @property
    def rel_speed(self) -> float:
        """Sun speed relative to the carrier, per sun rpm (planet bearing and pitch-line speeds)."""
        return 1.0 if self.star else 1.0 - 1.0 / self.ratio


@dataclass
class Check:
    name: str
    value: float
    limit: float
    safety: float
    target: float
    unit: str
    exponent: float = 1.0

    @property
    def ok(self) -> bool:
        return self.safety >= self.target - 1e-9

    def torque_scale(self) -> float:
        return 0.0 if self.safety <= 0 else (self.safety / self.target) ** (1.0 / self.exponent)


def _z_e(m1: Dict, m2: Dict) -> float:
    return math.sqrt(1.0 / (math.pi * ((1 - m1["nu"] ** 2) / m1["E"] + (1 - m2["nu"] ** 2) / m2["E"])))


def _z_h(alpha: float, beta: float) -> float:
    beta_b = math.atan(math.tan(beta) * math.cos(alpha))
    return math.sqrt(2.0 * math.cos(beta_b) / (math.cos(alpha) ** 2 * math.sin(alpha)))


def _z_eps(eps_a: float, eps_b: float) -> float:
    if eps_b >= 1.0:
        return math.sqrt(1.0 / max(eps_a, 1e-6))
    return math.sqrt(max(0.05, (4.0 - eps_a) / 3.0 * (1.0 - eps_b) + eps_b / max(eps_a, 1e-6)))


def stage_factors(st: StageDesign, load: LoadCase) -> Dict:
    """Torque/speed-independent capacities of one stage (per 1 Nm sun torque)."""
    gm, sm = get_material(load.gear_material), get_material(load.struct_material)
    g = st.geo
    alpha = math.radians(g.pressure_angle)
    beta = math.radians(st.helix_deg) if st.herringbone else 0.0
    d_s, d_p = 2 * g.r_sun, 2 * g.r_planet
    b = st.face_width
    m_n = g.module * math.cos(beta)
    cb3 = math.cos(beta) ** 3
    ftc = 2000.0 / (d_s * st.num_planets) * load_sharing(st.num_planets, gm["printed"])
    eps_b = overlap_ratio(b, st.helix_deg, g.module, st.herringbone) if st.herringbone else 0.0
    f = {"ftc": ftc, "ratio": st.ratio, "rel": st.rel_speed, "zs_zp": g.z_sun / g.z_planet,
         "v_per_rpm": math.pi * d_s / 60000.0, "kv_a": 3.05 if gm["printed"] else 6.1, "eps_beta": eps_b,
         "bend": {}, "contact": {}}
    beta_b = math.atan(math.tan(beta) * math.cos(alpha))
    y_beta = max(0.75, 1.0 - min(eps_b, 1.0) * math.degrees(beta) / 120.0)
    depth = depth_strength_factors(g)            # tooth depth h_a*: stub > 1 (stronger root), long < 1
    f["depth"] = depth
    for name, z, factor, eps_a, key in (("bend_sun", g.z_sun, 1.0, g.eps_sun_planet, "sun"),
                                        ("bend_planet", g.z_planet, PLANET_REVERSE_BENDING, g.eps_sun_planet,
                                         "planet"),
                                        ("bend_ring", 10000, 1.0, g.eps_planet_ring, "ring")):
        allow = gm["sigma_F"] * factor
        y_eps = 0.25 + 0.75 / max(eps_a / math.cos(beta_b) ** 2, 1.0)
        y_form = lewis_y(z / cb3, g.pressure_angle) * depth[key]
        f["bend"][name] = (allow, b * m_n * y_form / (ftc * y_eps * y_beta))
    ze, zh, zb = _z_e(gm, gm), _z_h(alpha, beta), math.sqrt(math.cos(beta))
    u_sp, u_pr = g.z_planet / g.z_sun, g.z_ring / g.z_planet
    f["contact"]["contact_sun_planet"] = (gm["sigma_H"], ze * zh * _z_eps(g.eps_sun_planet, eps_b) * zb *
                                          math.sqrt(ftc / (b * d_s) * (u_sp + 1) / u_sp))
    f["contact"]["contact_planet_ring"] = (gm["sigma_H"], ze * zh * _z_eps(g.eps_planet_ring, eps_b) * zb *
                                           math.sqrt(ftc / (b * d_p) * (u_pr - 1) / u_pr))
    f["fr_per_nm"] = 2.0 * ftc
    if st.bearings_per_planet > 0:
        info = get_bearing_info(st.bearing_code)
        f["bearing"] = (info["C_kN"] * 1000.0, info["C0_kN"] * 1000.0, st.bearings_per_planet)
    else:
        f["bushing"] = (0.25 * gm["sigma_H"], st.pin_dia * b)
    if st.carrier_cage:
        lever = (b + 2 * st.clearance + st.plate_t) / 4.0
    elif st.bearings_per_planet == 1:
        lever = st.clearance + get_bearing_info(st.bearing_code)["width"] / 2.0
    else:
        lever = st.clearance + b / 2.0
    pin_allow = STEEL_PIN["sigma_S"] if st.pin_steel else sm["sigma_S"]
    f["pin"] = (pin_allow, 2.0 * ftc * lever * 32.0 / (math.pi * st.pin_dia ** 3))      # sigma per Nm
    f["khb"] = _face_load_data(st, gm, sm, b, lever, ftc)
    d_o, d_i = 2 * g.root_sun, min(st.sun_bore_dia, 2 * g.root_sun - 0.5)
    if st.neck_dia > 0:                          # one piece with the carrier: the neck below the teeth
        d_o = min(d_o, st.neck_dia)
    f["core"] = (torsion_allowable(gm), 16000.0 * d_o / (math.pi * (d_o ** 4 - max(d_i, 0.0) ** 4)))
    if st.inter_shaft_dia > 0:
        f["shaft"] = (torsion_allowable(sm), 16000.0 / (math.pi * st.inter_shaft_dia ** 3))
    if load.expert:
        from core import expert
        f["expert"] = expert.stage_terms(load.gear_material, g, b, st.num_planets, load.housing, load.lube)
    return f


def _expert_terms(f: Dict, torque: float, sun_speed: float, load: LoadCase) -> Optional[Dict]:
    """Expert terms of a stage at sun torque `torque` (incl. K_A; the heat comes from the nominal torque)."""
    if "expert" not in f:
        return None
    from core import expert
    n_rel = sun_speed * f["rel"]
    return expert.terms(f["expert"], torque / load.application_factor, n_rel, f["v_per_rpm"] * n_rel, load)


def _face_load_data(st: StageDesign, gm: Dict, sm: Dict, b: float, lever: float, ftc: float) -> Dict:
    """Torque-independent part of the face load factor of one stage (see the module docstring)."""
    g = st.geo
    b_eff = b / 2.0 if st.herringbone else b              # each helix of a herringbone is its own face
    e_pin = STEEL_PIN["E"] if st.pin_steel else sm["E"]
    i_pin = math.pi * st.pin_dia ** 4 / 64.0
    # tilt from the hole errors: two independent plates (x sqrt 2), only the component along the line of action
    # counts (x 1/sqrt 2); the radial component changes the backlash, not the load distribution
    if st.carrier_cage:
        span = b + 2.0 * st.clearance + st.plate_t
        tilt_mfg = st.mfg_error / span
        tilt_per_n = span ** 2 / (8.0 * e_pin * i_pin)                   # guided pin, torque-free plate
    else:
        seat = max(st.plate_t, 1.0)
        tilt_mfg = 0.4 * st.mfg_error / seat                             # hole axis is built along the axis
        tilt_per_n = lever ** 2 / (2.0 * e_pin * i_pin) * (1.5 if sm["printed"] else 1.0)   # + seat compliance
    h = (g.addendum + 1.25) * g.module
    r = b_eff / h
    plastic = gm["E"] < 20000.0
    # running-in: ISO 6336-1 gives y_beta = 320 / sigma_Hlim x F_beta_x (soft materials conform more; extrapolated
    # to plastics it would be complete). Plastics conform by creep and wear, but printed flanks only partly:
    # ~65 % of the misalignment is taken as run in (F_beta_y = 0.35 F_beta_x); metals 15 %.
    return {"c": MESH_STIFFNESS_STEEL * min(1.0, gm["E"] / 210000.0), "run_in": 0.35 if plastic else 0.85,
            "mfg_um": tilt_mfg * b_eff * 1000.0, "def_um_per_nm": tilt_per_n * b_eff * 1000.0 * 2.0 * ftc,
            "w_per_nm": ftc / b, "nf": r * r / (1.0 + r + r * r)}


def face_load_factor(f: Dict, torque: float, kv: float) -> Tuple[float, float, float]:
    """K_Hbeta, K_Fbeta and the effective misalignment F_beta_y [um] at sun torque `torque` (incl. K_A)."""
    k = f["khb"]
    w = k["w_per_nm"] * torque * kv
    f_by = k["run_in"] * (k["mfg_um"] + k["def_um_per_nm"] * torque)
    if w <= 0.0:
        return 1.0, 1.0, f_by
    x = k["c"] * f_by / (2.0 * w)
    khb = min(KHB_MAX, 1.0 + x if x <= 1.0 else 2.0 * math.sqrt(x))
    return khb, khb ** k["nf"], f_by


def stage_checks(f: Dict, torque: float, sun_speed: float, load: LoadCase) -> List[Check]:
    """All checks of one stage at sun torque `torque` (incl. K_A) and sun speed [rpm]."""
    n_rel = sun_speed * f["rel"]
    kv = (f["kv_a"] + f["v_per_rpm"] * n_rel) / f["kv_a"]
    khb, kfb, _ = face_load_factor(f, torque, kv)
    ex = _expert_terms(f, torque, sun_speed, load)
    fb, fc = (ex["f_t"] * ex["y_nt"], ex["f_t"] * ex["z_nt"]) if ex else (1.0, 1.0)
    out = []
    for name, (allow, cap) in f["bend"].items():
        sigma = torque * kv * kfb / cap
        out.append(Check(name, sigma, allow * fb, allow * fb / sigma, load.target_sf, "MPa", 1.0))
    for name, (lim, coef) in f["contact"].items():
        sigma = coef * math.sqrt(torque * kv * khb)
        out.append(Check(name, sigma, lim * fc, lim * fc / sigma, load.target_sh, "MPa", 2.0))
    if ex:
        from core.expert import margins
        m_temp, m_wear = margins(ex, load)
        out.append(Check("tooth_temp", ex["temp"], ex["t_max"], m_temp, 1.0, "°C", 1.0))
        out.append(Check("wear_sun", ex["wear"], ex["wear_lim"], m_wear, 1.0, "mm", 1.0))
    p_total = f["fr_per_nm"] * torque
    if "bearing" in f:
        c_dyn, c_stat, nb = f["bearing"]
        p = p_total / nb
        n_p = max(n_rel * f["zs_zp"], 1e-6)
        life = (c_dyn / p) ** 3 * 1e6 / (60.0 * n_p)
        out.append(Check("bearing_life", life, load.target_life_h, life / load.target_life_h, 1.0, "h", 3.0))
        out.append(Check("bearing_static", c_stat / p, 1.0, c_stat / p, 1.0, "", 1.0))
    else:
        p_allow, area = f["bushing"]
        pressure = p_total / area
        out.append(Check("bushing_pressure", pressure, p_allow, p_allow / pressure, 1.0, "MPa", 1.0))
    allow, coef = f["pin"]
    out.append(Check("pin_bending", coef * torque, allow, allow / (coef * torque), load.target_sf, "MPa", 1.0))
    allow, coef = f["core"]
    out.append(Check("sun_core_torsion", coef * torque, allow, allow / (coef * torque), load.target_sf, "MPa", 1.0))
    if "shaft" in f:
        allow, coef = f["shaft"]
        out.append(Check("shaft_torsion", coef * torque, allow, allow / (coef * torque), load.target_sf, "MPa", 1.0))
    return out


def stage_margin(f: Dict, torque: float, sun_speed: float, load: LoadCase) -> float:
    """Fast path for design search: min over checks of (S/S_target)^(1/exponent); >= 1 means OK."""
    n_rel = sun_speed * f["rel"]
    kv = (f["kv_a"] + f["v_per_rpm"] * n_rel) / f["kv_a"]
    khb, kfb, _ = face_load_factor(f, torque, kv)
    tk = torque * kv
    ex = _expert_terms(f, torque, sun_speed, load)
    fb, fc = (ex["f_t"] * ex["y_nt"], ex["f_t"] * ex["z_nt"]) if ex else (1.0, 1.0)
    margin = min(cap / (tk * kfb) / load.target_sf * allow * fb for allow, cap in f["bend"].values())
    for lim, coef in f["contact"].values():
        margin = min(margin, (lim * fc / (coef * math.sqrt(tk * khb)) / load.target_sh) ** 2)
    if ex:
        from core.expert import margins
        margin = min(margin, *margins(ex, load))
    p_total = f["fr_per_nm"] * torque
    if "bearing" in f:
        c_dyn, c_stat, nb = f["bearing"]
        p = p_total / nb
        life = (c_dyn / p) ** 3 * 1e6 / (60.0 * max(n_rel * f["zs_zp"], 1e-6))
        margin = min(margin, (life / load.target_life_h) ** (1.0 / 3.0), c_stat / p)
    else:
        p_allow, area = f["bushing"]
        margin = min(margin, p_allow * area / p_total)
    for key in ("pin", "core", "shaft"):
        if key in f:
            allow, coef = f[key]
            margin = min(margin, allow / (coef * torque) / load.target_sf)
    return margin


def output_shaft_check(torque_ka: float, dia: float, steel: bool, load: LoadCase) -> Check:
    """Torsion of the output member (printed hub/flange or shaft, or steel shaft)."""
    sm = get_material(load.struct_material)
    allow = 0.5 * 300.0 if steel else torsion_allowable(sm)
    tau = 16000.0 * torque_ka / (math.pi * dia ** 3)
    return Check("output_shaft_torsion", tau, allow, allow / tau, load.target_sf, "MPa", 1.0)


ARM_FLAT = 0.15        # double-D flat depth / hub diameter (arm-to-hub form lock)


def arm_key_height(hub_d: float) -> float:
    """Height of the double-D lock on the output hub (mm)."""
    return min(12.0, max(6.0, 0.3 * hub_d))


def arm_key_pressure(torque: float, hub_d: float) -> float:
    """Peak contact pressure on the two flats (MPa) for torque [Nm]."""
    r = hub_d / 2.0
    c = math.sqrt(max(1e-6, r * r - (r - ARM_FLAT * hub_d) ** 2))
    return 3.0 * torque * 1000.0 / (2.0 * c * c * arm_key_height(hub_d))


def required_key_dia(torque_ka: float, allow: float, target: float) -> float:
    lo, hi = 2.0, 200.0
    for _ in range(50):
        mid = (lo + hi) / 2.0
        if allow / arm_key_pressure(torque_ka, mid) >= target:
            hi = mid
        else:
            lo = mid
    return hi


def arm_section_modulus(shape: str, width: float, thickness: float) -> float:
    """Bending in the plane of rotation: flat bar t x w -> t·w²/6, round (D) rod d -> pi·d³/32."""
    if shape == "ROUND":
        return math.pi * width ** 3 / 32.0
    return thickness * width ** 2 / 6.0


DECLUTCH_SPIGOT_MIN = 9.0     # drum arms: smallest collar neck radius
DECLUTCH_R_PREF = 40.0        # index plunger: the smallest size whose pin stays within this radius
DECLUTCH_R_MAX = 45.0         # pin radius beyond the collar bore at most (arm hub size)
DECLUTCH_ENGAGE_LOSS = 0.8    # pin tip chamfer + running gap: lost from the pin protrusion


def declutch_hub_d(hub_d: float, screw_r: float = 0.0) -> float:
    """
    Hub diameter that sets the collar neck (r_s = hub_d / 2 + 4). A carrier arm uses its double-D hub; an arm bolted
    onto a drum lid / cycloid hub has no key: its screws run through the neck, which takes them with 3.5 mm to spare.
    """
    if hub_d > 0:
        return hub_d
    return 2.0 * (max(DECLUTCH_SPIGOT_MIN, screw_r + 3.5) - 4.0)


def _plunger_need(torque_ka: float, pl: Dict, local_top: float, sigma: float, target: float) -> float:
    """Pin radius at which the printed holes (collar: pin d1, arm: thread body d2) meet the target."""
    area = min(pl["d1"] * (pl["l2"] - DECLUTCH_ENGAGE_LOSS), pl["d2"] * local_top)
    return torque_ka * 1000.0 * target / (sigma * area)


def declutch_design(hub_d: float, torque_ka: float, struct_material: str, target: float, shape: str = "FLAT",
                    width: float = 0.0, thickness: float = 0.0) -> Dict:
    """
    Declutchable arm with a spring index plunger (GN 617.1, rest position, lock nut). The collar (screwed to the
    output) carries the torque to the free arm through the plunger pin at radius r_c: F = T / r_c, borne by the
    printed collar hole (pin d1 over its protrusion) and the arm hole (thread body d2 over the clamped arm). The
    plunger size follows the torque only (the smallest one whose pin radius stays within DECLUTCH_R_PREF), so the
    engine and the CAD agree on it; r_c then grows until the hole pressure meets the target. Pull the knob and turn
    it a quarter: the pin stays up, the arm turns freely; turn it back: the spring snaps the pin in as soon as the
    holes line up. A pull solenoid can replace the knob later (same axis, same spring).
    """
    from core.hardware import INDEX_PLUNGERS
    from core.layout import declutch_layout
    sm = get_material(struct_material)
    sizes = [INDEX_PLUNGERS[k] for k in sorted(INDEX_PLUNGERS)]
    pl = sizes[-1]
    for cand in sizes:
        lay = declutch_layout(shape, width, thickness, cand)
        if _plunger_need(torque_ka, cand, lay["local_top"], sm["sigma_S"], target) <= DECLUTCH_R_PREF:
            pl = cand
            break
    lay = declutch_layout(shape, width, thickness, pl)
    r_s = hub_d / 2.0 + 4.0
    bore_r = r_s + 0.3
    clear = max(pl["s"] / math.sqrt(3.0), pl["knob_d"] / 2.0, pl["d2"] / 2.0)
    r0 = bore_r + 2.0 + clear
    need = _plunger_need(torque_ka, pl, lay["local_top"], sm["sigma_S"], target)
    r_c = math.ceil(min(max(r0, need), bore_r + DECLUTCH_R_MAX) * 10.0 - 1e-9) / 10.0
    return {"pin_d": pl["d1"], "plunger": pl, "r_c": r_c, "r_s": r_s, "bore_r": bore_r, "boss_r": r_c + clear + 3.5,
            "shoulder_r": r_c + pl["d1"] / 2.0 + 4.0, "clear": clear, "lay": lay}


def declutch_checks(torque_ka: float, geo: Dict, load: LoadCase) -> List[Check]:
    sm = get_material(load.struct_material)
    pl = geo["plunger"]
    f = torque_ka * 1000.0 / geo["r_c"]
    p = max(f / (pl["d1"] * (pl["l2"] - DECLUTCH_ENGAGE_LOSS)), f / (pl["d2"] * geo["lay"]["local_top"]))
    tau = f / (math.pi * pl["d1"] ** 2 / 4.0)
    tau_allow = 0.58 * STEEL_PIN["sigma_S"]
    return [Check("declutch_hole", p, sm["sigma_S"], sm["sigma_S"] / p, load.target_sf, "MPa", 1.0),
            Check("declutch_shear", tau, tau_allow, tau_allow / tau, load.target_sf, "MPa", 1.0)]


def arm_checks(torque_ka: float, arm: Dict, load: LoadCase, key: bool = True) -> List[Check]:
    """
    Output arm (lever). The worst case moment at the arm root equals the transmitted torque (the
    load at the tip balances the gearbox). Torque goes from the hub to the arm through a double-D
    form lock (the M3 screws only hold it axially): each flat carries a triangular pressure over its
    half chord c and height h -> T = 2/3 · p_max · c² · h. The tip load itself: application_load_checks.
    An arm bolted onto a rotating drum (`key=False`) has no double-D lock: its screws are drum_checks.
    """
    sm = get_material(load.struct_material)
    out = []
    w = arm_section_modulus(arm["shape"], arm["width"], arm["thickness"])
    sigma = torque_ka * 1000.0 / w
    out.append(Check("arm_bending", sigma, sm["sigma_S"], sm["sigma_S"] / sigma, load.target_sf, "MPa", 1.0))
    if key:
        p_max = arm_key_pressure(torque_ka, arm["hub_d"])
        out.append(Check("arm_key", p_max, sm["sigma_S"], sm["sigma_S"] / p_max, load.target_sf, "MPa", 1.0))
    if arm.get("declutch"):
        geo = declutch_design(declutch_hub_d(arm["hub_d"], arm.get("screw_r", 0.0)), torque_ka,
                              load.struct_material, load.target_sf, arm["shape"], arm["width"], arm["thickness"])
        out += declutch_checks(torque_ka, geo, load)
    return out


def mount_check(torque_ka: float, mount: Optional[Dict], load: LoadCase) -> Optional[Check]:
    """The housing's reaction torque (= output torque) reaches the bracket through the tie rods."""
    if not mount:
        return None
    return _screw_bearing_check("mount_rods", torque_ka, mount["n"], mount["r"], mount["d"], mount["engage"], 1.0,
                                load)


LOAD_RESERVE = {"stepper": 1.5, "dc": 1.25, "custom": 1.25}   # recommended drive torque / load torque
BEARING_S0_TARGET = 2.0       # static safety of the output bearing under the side load (printed seat, shocks)


def application_load_checks(app: Dict, have: float, capacity: float, load: LoadCase) -> List[Check]:
    """
    Optional application load (what the gearbox has to move): torque T = F·r at the output.
      load_drive    nominal output torque (motor x ratio x efficiency) / T   >= reserve (stepper 1.5: the pull-out
                    torque falls with speed, a stepper that is short of torque loses steps)
      load_capacity continuous torque capacity of the gearbox (all strength targets incl. K_A) / T  >= 1
      load_bearing  the force F also pushes the output sideways: static safety C0 / F of the cover bearing
      load_shaft    shaft outputs: bending by F at mid-length of the protruding shaft + torsion by T
                    (von Mises, K_A applied, printed shafts loaded across the layers x 0.6)
    All are pass/fail (exponent 0): they do not change the motor-based capacity of the gearbox.
    """
    need = app["torque"]
    out = [Check("load_drive", need, have, have / need, app.get("reserve", 1.5), "Nm", 0.0),
           Check("load_capacity", need, capacity, capacity / need, 1.0, "Nm", 0.0)]
    force = app.get("force", 0.0)
    if force > 0 and app.get("bearing_c0", 0.0) > 0:
        c0 = app["bearing_c0"]
        out.append(Check("load_bearing", force, c0, c0 / force, BEARING_S0_TARGET, "N", 0.0))
    shaft = app.get("shaft")
    if force > 0 and shaft and shaft.get("d", 0.0) > 0:
        d = shaft["d"]
        ka = load.application_factor
        sigma_b = 32.0 * force * ka * shaft["lever"] / (math.pi * d ** 3)
        tau = 16000.0 * need * ka / (math.pi * d ** 3)
        sv = math.sqrt(sigma_b ** 2 + 3.0 * tau ** 2)
        if shaft.get("steel"):
            allow = 300.0
        else:
            sm = get_material(load.struct_material)
            allow = sm["sigma_S"] * (PRINTED_TORSION_FACTOR if sm["printed"] else 1.0)
        out.append(Check("load_shaft", sv, allow, allow / sv, load.target_sf, "MPa", 0.0))
    return out


def _screw_bearing_check(name: str, torque_ka: float, n: int, r: float, d: float, engage: float, share: float,
                         load: LoadCase) -> Optional[Check]:
    """
    Screws on a circle that carry a torque in shear: the printed hole wall takes the screw force over the
    projected area d x engagement (no credit for clamping friction): p = share·T / (n·r) / (d·L).
    """
    if n <= 0 or r <= 0 or d <= 0 or engage <= 0:
        return None
    sm = get_material(load.struct_material)
    p = share * torque_ka * 1000.0 / (n * r) / (d * engage)
    return Check(name, p, sm["sigma_S"], sm["sigma_S"] / p, load.target_sf, "MPa", 1.0)


def drum_checks(torque_ka: float, drum: Dict, load: LoadCase) -> List[Check]:
    """
    Rotating housing (ring output): the output torque leaves the drum through the screws of its face
    (the user's part / the output arm) and, on a herringbone drum, half of it crosses the joint of the two
    drum halves through the joint screws (each helix half carries half of the tooth forces).
    """
    out = []
    c = _screw_bearing_check("drum_bolts", torque_ka, drum.get("bolt_n", 0), drum.get("bolt_r", 0.0),
                             drum.get("bolt_d", 3.0), drum.get("bolt_engage", 0.0), 1.0, load)
    if c:
        out.append(c)
    c = _screw_bearing_check("drum_join", torque_ka, drum.get("join_n", 0), drum.get("join_r", 0.0),
                             drum.get("join_d", 3.0), drum.get("join_engage", 0.0), 0.5, load)
    if c:
        out.append(c)
    return out


def required_shaft_dia(torque_ka: float, allow: float, target: float) -> float:
    return (16000.0 * torque_ka * target / (math.pi * allow)) ** (1.0 / 3.0)


M3_NUT_S, M3_NUT_M = 5.5, 2.4             # ISO 4032 M3 hex nut (output hub pockets)
NUT_SLOT_W = M3_NUT_S + 0.3
NUT_SLOT_BACK = M3_NUT_S / math.sqrt(3.0) + 0.2   # pocket reaches this far behind the screw axis


def hub_nut_layout(hub_d: float) -> Tuple[int, float]:
    """(number of M3 nuts, pitch radius) of the output hub: 4 only on large hubs, so the side pockets
    do not cut away too much of the hub section; 2 opposite; 1 central on small hubs."""
    if hub_d >= 40.0:
        return 4, 0.31 * hub_d
    if hub_d >= 14.0:
        return 2, 0.3 * hub_d
    return 1, 0.0


def nut_layer_polar_moment(hub_d: float) -> float:
    """Polar moment (mm^4) of the hub section at the nut pockets: full disk minus the radial slots."""
    R = hub_d / 2.0
    j = math.pi * hub_d ** 4 / 32.0
    n, pcd = hub_nut_layout(hub_d)
    r_i = max(0.0, pcd - NUT_SLOT_BACK)
    if n == 1:            # central nut: the slot runs from behind the axis to the outside
        slot = NUT_SLOT_W * (R ** 3 + NUT_SLOT_BACK ** 3) / 3.0
    else:
        slot = NUT_SLOT_W * (R - r_i) * (r_i * r_i + r_i * R + R * R) / 3.0
    return max(j - n * slot, 0.05 * j)


def hub_nut_layer_check(torque_ka: float, hub_d: float, load: LoadCase) -> Check:
    allow = torsion_allowable(get_material(load.struct_material))
    tau = torque_ka * 1000.0 * (hub_d / 2.0) / nut_layer_polar_moment(hub_d)
    return Check("hub_nut_layer", tau, allow, allow / tau, load.target_sf, "MPa", 1.0)


def required_nut_hub_dia(torque_ka: float, allow: float, target: float) -> float:
    """
    Smallest hub from which every larger hub passes the nut-layer check. Not simply the first passing
    size: at Ø40 the layout switches from 2 to 4 pockets and the section gets weaker, so a Ø39 hub may
    pass while the next catalog hub (Ø40) fails.
    """
    req = None
    for d in [x * 0.5 for x in range(16, 241)]:            # 8 .. 120 mm
        tau = torque_ka * 1000.0 * (d / 2.0) / nut_layer_polar_moment(d)
        if allow / tau >= target:
            req = d if req is None else req
        else:
            req = None
    return req if req is not None else 120.0


MOTOR_SHAFT_TAU = 100.0    # MPa, allowable torsion of a steel motor shaft (flat / keyway notch included)


def motor_shaft_check(torque_ka: float, dia: float, load: LoadCase) -> Check:
    """Steel motor shaft carrying the input torque: tau = 16 T / (pi d^3)."""
    tau = 16.0 * torque_ka * 1000.0 / (math.pi * dia ** 3)
    # exponent 0: reported pass/fail; a motor property, so it does not lower the gearbox capacity
    return Check("motor_shaft_torsion", tau, MOTOR_SHAFT_TAU, MOTOR_SHAFT_TAU / tau, load.target_sf, "MPa", 0.0)


GEAR_CHECKS = ("bend_sun", "bend_planet", "bend_ring", "contact_sun_planet", "contact_planet_ring")


def _capacity_scale(loads: List[Tuple[Dict, float, float]], checks: List[Check], load: LoadCase, s0: float) -> float:
    """
    Torque scale at which the smallest safety meets its target. The face load factor falls with the load, so
    the gear checks are evaluated again at the scaled torque (stage_margin); every other check follows its
    power law exactly (torque_scale).
    """
    stage_names = set(GEAR_CHECKS) | {"bearing_life", "bearing_static", "bushing_pressure", "pin_bending",
                                      "sun_core_torsion", "shaft_torsion", "tooth_temp", "wear_sun"}
    other = min((c.torque_scale() for c in checks if c.exponent > 0 and c.name not in stage_names),
                default=float("inf"))

    def ok(s: float) -> bool:
        return other >= s and all(stage_margin(f, t * s, n, load) >= 1.0 for f, t, n in loads)

    lo, hi = s0, s0
    if ok(s0):
        while ok(hi) and hi < 1e5:
            lo, hi = hi, hi * 2.0
    else:
        while not ok(lo) and lo > 1e-6:
            lo, hi = lo / 2.0, lo
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if ok(mid):
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-5 * hi:
            break
    return lo


def analyze(stages: List[StageDesign], load: LoadCase, output_shaft_dia: float = 0.0,
            output_shaft_steel: bool = False, lang: str = "tr", arm: Optional[Dict] = None,
            motor_shaft_dia: float = 0.0, hub_nut_dia: float = 0.0, app_load: Optional[Dict] = None,
            drum: Optional[Dict] = None, reverse: bool = False, mount: Optional[Dict] = None) -> Dict:
    """
    Full stage-by-stage analysis. Returns a JSON-serializable dict. `app_load` (optional): what the gearbox
    has to move, {"torque": Nm, "force": N, "reserve", "bearing_c0": N, "shaft": {"d", "lever", "steel"}}.
    `drum`: screw circles of a rotating-housing output (drum_checks). `reverse`: speed-up gearbox, the load
    case holds the equivalent sun torque / speed (input torque / ratio, input speed x ratio); torques are
    carried up without efficiency credit and the generator (sun) side is reported as the output.
    """
    eta = get_material(load.gear_material)["eta"]
    eta_prop = 1.0 if reverse else eta
    labels = CHECK_LABELS["en" if lang == "en" else "tr"]
    torque = load.motor_torque * load.application_factor
    speed = load.motor_speed
    stage_out, all_checks, loads = [], [], []
    for k, st in enumerate(stages):
        f = stage_factors(st, load)
        checks = stage_checks(f, torque, speed, load)
        loads.append((f, torque, speed))
        n_rel0 = speed * f["rel"]
        khb, kfb, f_by = face_load_factor(f, torque, (f["kv_a"] + f["v_per_rpm"] * n_rel0) / f["kv_a"])
        if k == 0 and motor_shaft_dia > 0:
            checks.append(motor_shaft_check(torque, motor_shaft_dia, load))
        n_c = speed / st.ratio                    # carrier speed (ring speed of a star stage)
        n_rel = speed * st.rel_speed
        stage_out.append({
            "index": k + 1, "ratio": st.ratio, "star": st.star, "input_torque": torque / load.application_factor,
            "output_torque": torque * st.ratio * eta_prop / load.application_factor, "sun_speed": speed,
            "carrier_speed": 0.0 if st.star else n_c, "ring_speed": n_c if st.star else 0.0,
            "planet_speed_rel": n_rel * st.geo.z_sun / st.geo.z_planet,
            "tangential_force": f["ftc"] * torque, "pitch_velocity": f["v_per_rpm"] * n_rel,
            "eps_alpha_sp": st.geo.eps_sun_planet, "eps_alpha_pr": st.geo.eps_planet_ring,
            "eps_beta": f["eps_beta"], "addendum": st.geo.addendum,
            "tip_land": min(st.geo.tip_land_sun, st.geo.tip_land_planet),
            "depth_factor": {k: round(v, 4) for k, v in f["depth"].items()},
            "k_hbeta": round(khb, 3), "k_fbeta": round(kfb, 3), "misalignment_um": round(f_by, 1),
            "checks": checks})
        ex = _expert_terms(f, torque, speed, load)
        if ex:
            stage_out[-1]["expert"] = {"temp": round(ex["temp"], 1), "t_max": ex["t_max"], "f_t": round(ex["f_t"], 3),
                                       "y_nt": round(ex["y_nt"], 3), "z_nt": round(ex["z_nt"], 3),
                                       "cycles": ex["cycles"], "wear_mm": round(ex["wear"], 4),
                                       "wear_lim": round(ex["wear_lim"], 3), "mu": ex["mu"]}
        all_checks += [(k + 1, c) for c in checks]
        torque *= st.ratio * eta_prop
        speed = n_c
    if output_shaft_dia > 0:
        c = output_shaft_check(torque, output_shaft_dia, output_shaft_steel, load)
        stage_out[-1]["checks"].append(c)
        all_checks.append((len(stages), c))
    if hub_nut_dia > 0:
        c = hub_nut_layer_check(torque, hub_nut_dia, load)
        stage_out[-1]["checks"].append(c)
        all_checks.append((len(stages), c))
    if arm:
        for c in arm_checks(torque, arm, load, key=not drum):
            stage_out[-1]["checks"].append(c)
            all_checks.append((len(stages), c))
    if drum:
        for c in drum_checks(torque, drum, load):
            stage_out[-1]["checks"].append(c)
            all_checks.append((len(stages), c))
    if mount:
        # the housing's reaction torque (output torque) reaches the bracket through the tie rods
        c = _screw_bearing_check("mount_rods", torque, mount["n"], mount["r"], mount["d"], mount["engage"], 1.0, load)
        if c:
            stage_out[-1]["checks"].append(c)
            all_checks.append((len(stages), c))
    if load.expert and load.hold_h > 0:
        # creep: the load held at rest (application load, else the nominal output torque) for hold_h hours
        from core.expert import creep_factor
        t_nom = torque / load.application_factor
        r_h = ((app_load or {}).get("torque", 0.0) or t_nom) / max(t_nom, 1e-9)
        allow = get_material(load.gear_material)["sigma_F"] * creep_factor(load.hold_h)
        for k, so in enumerate(stage_out):
            bends = [c for c in so["checks"] if isinstance(c, Check) and c.name.startswith("bend_")]
            if bends:
                s_hold = max(c.value for c in bends) / load.application_factor * r_h
                c = Check("creep", s_hold, allow, allow / max(s_hold, 1e-9), 1.0, "MPa", 0.0)
                so["checks"].append(c)
                all_checks.append((k + 1, c))
    out_torque = torque / load.application_factor
    scale, limiting = float("inf"), None
    for idx, c in all_checks:
        if c.exponent <= 0:          # pass/fail only (e.g. the motor shaft), not a torque limit
            continue
        s = c.torque_scale()
        if s < scale:
            scale, limiting = s, (idx, c)
    if loads and scale < float("inf"):
        scale = _capacity_scale(loads, [c for _, c in all_checks], load, scale)
    app_out = None
    if app_load and app_load.get("torque", 0.0) > 0 and not reverse:
        capacity = out_torque * scale
        cks = application_load_checks(app_load, out_torque, capacity, load)
        stage_out[-1]["checks"] += cks
        all_checks += [(len(stages), c) for c in cks]
        app_out = {c.name: {"value": c.value, "limit": c.limit, "safety": c.safety, "target": c.target, "ok": c.ok}
                   for c in cks}
    for s in stage_out:
        s["checks"] = [{"name": c.name, "label": labels.get(c.name, c.name), "value": c.value, "limit": c.limit,
                        "safety": c.safety, "target": c.target, "unit": c.unit, "ok": c.ok} for c in s["checks"]]
    total_ratio = 1.0
    for st in stages:
        total_ratio *= st.ratio
    flow = {"input_torque": load.motor_torque, "input_speed": load.motor_speed, "output_torque": out_torque,
            "output_speed": speed, "max_output_torque": out_torque * scale}
    if reverse:
        # speed-up: the drive (crank / rotor) turns the output member, the generator sits on the first sun
        gen_torque = load.motor_torque * eta ** len(stages)
        flow = {"input_torque": out_torque, "input_speed": speed, "output_torque": gen_torque,
                "output_speed": load.motor_speed, "max_output_torque": gen_torque * scale,
                "max_input_torque": out_torque * scale}
    return {
        "total_ratio": total_ratio,
        "efficiency": eta ** len(stages),
        "reverse": reverse,
        "star": bool(stages and stages[-1].star),
        **flow,
        "margin": scale,
        "limiting": ({"stage": limiting[0], "check": limiting[1].name,
                      "label": labels.get(limiting[1].name, limiting[1].name)} if limiting else None),
        "all_ok": all(c.ok for _, c in all_checks),
        "min_sf_bending": min((c.safety for _, c in all_checks if c.name.startswith("bend")), default=0.0),
        "min_sf_contact": min((c.safety for _, c in all_checks if c.name.startswith("contact")), default=0.0),
        "min_bearing_life": min((c.value for _, c in all_checks if c.name == "bearing_life"), default=None),
        "load_case": {"application_factor": load.application_factor, "target_sf": load.target_sf,
                      "target_sh": load.target_sh, "target_life_h": load.target_life_h,
                      "gear_material": load.gear_material, "struct_material": load.struct_material},
        "stages": stage_out,
        "app_load_checks": app_out,
    }
