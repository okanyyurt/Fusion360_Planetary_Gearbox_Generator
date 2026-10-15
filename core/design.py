"""
Automatic sizing of a (multi-stage) planetary gearbox with a common ring gear.

Search space: standard modules (ISO 54 series I + II) x ring tooth counts x stage tooth sets.
Hard constraints for every stage:
    * coaxiality Zr = Zs + 2 Zp, equal spacing (Zs + Zr) % N == 0
    * adjacent planet tip clearance >= max(0.5 m, 0.8 mm)
    * involute interference removed by tip topping, remaining contact ratio >= 1.2 (spur) / 1.05 (herringbone)
    * planet bearing fits radially (rim under the tooth root >= max(1.5 mm, h_tooth)) and axially
    * carrier pin bosses fit inside the ring bore and around the sun
    * motor shaft (incl. flat / keyway) fits in the stage-1 sun with a sufficient rim
Strength (engineering.stage_margin): bending, contact, bearing life & static, pin, sun core torsion.

Modes:
    AUTO     smallest housing that satisfies all constraints and strength targets
    MAX_OD   within the given outer diameter, the strongest design (largest safety margin)
    MANUAL   fixed module, best ratio match (constraints reported as issues)
"""
import bisect
import math
import time
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Tuple

from core.bearing_catalog import BEARING_CATALOG, get_bearing_info, inner_race_diameter, real_bearings
from core.engineering import (ARM_FLAT, arm_key_height, required_key_dia, required_nut_hub_dia)
from core.engineering import (LOAD_RESERVE, MFG_ERROR, LoadCase, StageDesign, analyze, required_shaft_dia,
                              stage_factors, stage_margin, torsion_allowable)
from core.gear_geometry import (EXT_CLEARANCE, RING_CLEARANCE, SHIFT_LIMITS, StageGeometry, clamp_addendum,
                                 stage_geometry, undercut_shift)
from core.layout import AxialLayout, axial_layout, output_protrusion, ring_layout
from core.layout import drum_arm_height as _drum_arm_height
from core.materials import get_material
from core.motor_catalog import get_motor_info

STANDARD_MODULES = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.125, 1.25, 1.375, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0,
                    3.5, 4.0, 4.5, 5.0, 6.0]                            # ISO 54 series I + II
MIN_MODULE = {"FDM_3D": 0.8, "SLA_RESIN": 0.5, "CNC_METAL": 0.5, "CUSTOM": 0.5}
DOWEL_DIAMETERS = {3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0}  # ISO 8734 / DIN 6325
TIE_RODS = {
    "M3": {"d": 3.0, "hole": 3.4, "head_d": 5.5, "head_h": 3.0, "nut_s": 5.5, "nut_m": 2.4},
    "M4": {"d": 4.0, "hole": 4.5, "head_d": 7.0, "head_h": 4.0, "nut_s": 7.0, "nut_m": 3.2},
    "M5": {"d": 5.0, "hole": 5.5, "head_d": 8.5, "head_h": 5.0, "nut_s": 8.0, "nut_m": 4.0},
    "M6": {"d": 6.0, "hole": 6.6, "head_d": 10.0, "head_h": 6.0, "nut_s": 10.0, "nut_m": 5.2},
    "M8": {"d": 8.0, "hole": 9.0, "head_d": 13.0, "head_h": 8.0, "nut_s": 13.0, "nut_m": 6.8},
}


def auto_tie_rod(wall_r: float) -> str:
    """Tie-rod size by housing radius (more clamping force and stiffness for large housings)."""
    for size, lim in (("M3", 36.0), ("M4", 60.0), ("M5", 90.0), ("M6", 130.0)):
        if wall_r < lim:
            return size
    return "M8"
CLEARANCE = 0.6         # axial running clearance (= printed bearing spacer thickness)
WEB_MIN = 1.2           # web between two planet bearings
BOSS_WALL = 1.5         # carrier material around a pin


PLANET_CHOICES = (6, 5, 4, 3)    # automatic: most planets that fit (lowest load per planet incl. load sharing)


def _planets_param(v) -> int:
    """0 = automatic per stage; otherwise a fixed planet count (2..8)."""
    if v in (None, "") or str(v).strip().upper() in ("AUTO", "0"):
        return 0
    try:
        return max(2, min(8, int(float(v))))
    except (TypeError, ValueError):
        return 0


def max_planets(stage_ratio: float) -> int:
    """Planets that fit around the sun at this stage ratio (planet tips need clearance)."""
    if stage_ratio <= 2.3:
        return 6
    s = min(0.999, 1.08 * (stage_ratio - 2.0) / stage_ratio)      # ≈ (Zp + tips) / (Zs + Zp)
    return max(2, min(6, int(math.pi / math.asin(s))))


def _f(p: Dict, key: str, default: float) -> float:
    try:
        v = p.get(key, default)
        return float(default if v in (None, "") else v)
    except (TypeError, ValueError):
        return float(default)


def z_min(pressure_angle: float) -> int:
    return 18 if pressure_angle < 17 else (10 if pressure_angle > 22 else 12)


def rim_min(module: float, addendum: float = 1.0) -> float:
    """Rim under the tooth root of a gear with a bore/pocket (AGMA backup ratio ~1: one tooth height)."""
    return max(1.5, (2.0 * addendum + EXT_CLEARANCE) * module)


def housing_dims(z_ring: int, module: float, wall_t: float = 3.0, tie_rod: str = "AUTO",
                 motor_code: str = "NEMA17", addendum: float = 1.0) -> Dict:
    """Housing wall, tie-rod size/positions and outer envelope (Fusion layout, parametric wall)."""
    root_r = module * z_ring / 2.0 + (addendum + RING_CLEARANCE) * module
    wall_r = root_r + wall_t
    size = tie_rod if tie_rod in TIE_RODS else auto_tie_rod(wall_r)
    tr = TIE_RODS[size]
    bolt_r = root_r + tr["hole"] / 2.0 + wall_t
    lug_r = tr["hole"] / 2.0 + max(3.0, wall_t)
    if "NEMA17" in motor_code.upper() and (bolt_r + 3.0) <= 21.5:
        h = 31.0 / 2.0
        positions = [(hx, hy) for hx in (-h, h) for hy in (-h, h)]
    else:
        positions = [(bolt_r * math.cos(math.pi / 4 + i * math.pi / 2), bolt_r * math.sin(math.pi / 4 + i * math.pi / 2))
                     for i in range(4)]
    return {"root_r": root_r, "wall_r": wall_r, "bolt_r": bolt_r, "lug_r": lug_r, "tie_rod": size,
            "tie": tr, "positions": positions, "body_d": 2 * wall_r, "envelope_d": 2 * (bolt_r + lug_r)}


def shaft_extent(dia: float, kind: str) -> float:
    """Largest radius of a bore cut for a shaft of the given type (keyway reaches further)."""
    if (kind or "").upper() == "KEYWAY":
        from_t2 = {8: 1.0, 10: 1.4, 12: 1.8, 17: 2.3, 22: 2.8, 30: 3.3, 38: 3.3, 44: 3.3, 50: 3.8}
        t2 = next((v for lim, v in sorted(from_t2.items()) if dia <= lim), 3.8)
        if dia < 6:
            t2 = max(0.6, round(dia * 0.15, 1))
        return dia / 2.0 + t2
    return dia / 2.0


@dataclass
class Params:
    target_ratio: float
    stages: int
    num_planets: int
    mode: str
    module: float
    max_od: float
    ratio_tol: float
    bearing: str
    layout: str
    pin_steel: bool
    cage: bool
    motor_code: str
    motor_shaft_dia: float
    motor_shaft_type: str
    face_width: float
    helix: float
    herringbone: bool
    pressure_angle: float
    backlash: float
    bearing_tol: float
    pin_dia_custom: float
    wall_t: float
    tie_rod: str
    plate_t: float
    output_shaft_dia: float
    output_type: str
    strength_required: bool
    out_hub: str
    arm_shape: str
    arm_length: float
    arm_width: float
    arm_thickness: float
    arm_load: float
    mfg: str
    load: LoadCase
    output_shaft_len: float = 20.0
    make_housing: bool = True
    od_limit: float = 0.0           # AUTO mode: outer diameter cap (0 = none)
    footprint_limit: float = 0.0    # housing/flange footprint on the print bed (0 = none)
    hub_fastener: str = "NUT"       # output flange / arm screws: captive M3 nuts or heat-set inserts
    max_length: float = 0.0         # overall length cap incl. output member (0 = none)
    bed: Tuple[float, float, float] = (256.0, 256.0, 256.0)   # print bed X, Y, Z
    addendum: float = 1.0           # tooth depth coefficient h_a* (1.0 standard, 0.8 stub, 1.2 long)
    load_force: float = 0.0         # application load: force at the lever / rope, N (0 = none)
    load_radius: float = 0.0        # lever arm of that force (arm length, drum / pulley radius), mm
    load_torque: float = 0.0        # application load given directly as output torque, Nm
    load_value: float = 0.0         # as entered (for the messages)
    load_unit: str = "KG"           # KG (weight / kgf), N or NM
    arrangement: str = "CARRIER"    # CARRIER: ring fixed, carrier out | RING: last carrier fixed, ring (drum)
                                    # out | SPEED_UP: carrier driven, sun out (generator, turbine, crank)
    rope_dia: float = 4.0           # winch drum: rope / cord diameter, mm
    drive_torque: float = 0.0       # SPEED_UP: torque on the input member (crank, rotor), Nm
    drive_speed: float = 0.0        # SPEED_UP: speed of the input member, rpm
    shift_mode: str = "AUTO"        # profile shift: AUTO (balanced per stage), NONE (x = 0), CUSTOM (shift_x)
    shift_x: float = 0.0            # CUSTOM: sun shift of every stage (planet / ring: -x)
    mount: bool = False             # mounting bracket under the motor flange (any arrangement with a housing)
    mount_type: str = ""            # SIDE (L, axis parallel to the surface), BASE (legs, axis normal), PANEL
    declutch: bool = False          # arm output: free arm on a collar, coupled by one removable release pin
    plate_t_asked: float = 0.0      # carrier plate thickness of the form (plate_t may be thicker: dowel_plate_t)

    @property
    def ring_out(self) -> bool:
        return self.arrangement == "RING"

    @property
    def reverse(self) -> bool:
        return self.arrangement == "SPEED_UP"

    def hd(self, z_ring: int, module: float) -> Dict:
        return housing_dims(z_ring, module, self.wall_t, self.tie_rod, self.motor_code, self.addendum)

    def base_shift(self) -> float:
        """
        Profile shift the search starts from: the user's x (CUSTOM) or 0. All stages share the ring gear, whose
        tooth spaces fit the planets (x_ring = x_planet = -x_sun), so one x holds for the whole gearbox; AUTO
        optimises it per candidate (_best_shift).
        """
        return self.shift_x if self.shift_mode == "CUSTOM" else 0.0

    def geo(self, zs: int, zp: int, zr: int, module: float, shift: Optional[float] = None) -> StageGeometry:
        x = self.base_shift() if shift is None else shift
        return stage_geometry(zs, zp, zr, module, self.pressure_angle, self.backlash, addendum=self.addendum,
                              shift=x)

    @property
    def output_steel(self) -> bool:
        return self.output_type == "SHAFT_STEEL"

    @staticmethod
    def from_payload(p: Dict) -> "Params":
        motor = get_motor_info(str(p.get("motor_preset", "NEMA17")))
        load = LoadCase(
            motor_torque=_f(p, "motor_torque", motor.get("torque_nm", 0.4)),
            motor_speed=_f(p, "motor_speed", motor.get("speed_rpm", 300)),
            application_factor=_f(p, "app_factor", 1.25),
            target_sf=_f(p, "target_sf", 1.5),
            target_sh=_f(p, "target_sh", 1.0),
            target_life_h=_f(p, "target_life", 2000.0),
            gear_material=str(p.get("gear_material", "PLA")),
            struct_material=str(p.get("struct_material", p.get("gear_material", "PLA"))),
            expert=bool(p.get("expert_mode", False)),
            ambient_c=min(80.0, max(-30.0, _f(p, "ambient_temp", 23.0))),
            duty=min(1.0, max(0.01, _f(p, "duty_pct", 100.0) / 100.0)),
            lube="DRY" if str(p.get("lubrication", "GREASE")).upper() == "DRY" else "GREASE",
            hold_h=max(0.0, _f(p, "hold_hours", 0.0)),
            housing=bool(p.get("generate_housing", True)) or str(p.get("arrangement") or "").upper() not in ("", "CARRIER"),
        )
        herring = bool(p.get("is_herringbone", False))
        arrangement, out_type = normalize_output(p.get("arrangement"), p.get("output_type", "FLANGE"))
        target_ratio = max(1.5, _f(p, "target_ratio", 25.0))
        drive_t = drive_n = 0.0
        if arrangement == "SPEED_UP":
            # the drive turns the output member: the search works with the equivalent sun load (refined per
            # candidate with its exact ratio, _with_flow)
            drive_t = max(0.01, _f(p, "drive_torque", 5.0))
            drive_n = max(0.1, _f(p, "drive_speed", 60.0))
            load.motor_torque, load.motor_speed = drive_t / target_ratio, drive_n * target_ratio
        app = (app_load_from_payload(p, out_type, max(10.0, _f(p, "arm_length", 100.0)))
               if arrangement != "SPEED_UP" else app_load_from_payload({}, out_type, 0.0))
        return Params(
            target_ratio=target_ratio,
            stages=stage_count(p),
            num_planets=_planets_param(p.get("num_planets", 0)),
            mode=str(p.get("sizing_mode", "AUTO")).upper(),
            module=_f(p, "module", 1.0),
            max_od=_f(p, "max_od", 80.0),
            ratio_tol=max(0.2, _f(p, "ratio_tol", 3.0)) / 100.0,
            bearing=str(p.get("bearing_type", "AUTO")),
            layout=str(p.get("bearing_layout", "AUTO")).upper(),
            pin_steel=str(p.get("pin_type", "STEEL")).upper() == "STEEL",
            cage=str(p.get("carrier_type", "CAGE")).upper() != "SINGLE",
            motor_code=str(p.get("motor_preset", "NEMA17")),
            motor_shaft_dia=_f(p, "motor_shaft_dia", motor.get("default_shaft_dia", 5.0)),
            motor_shaft_type=str(p.get("motor_shaft_type", motor.get("default_shaft_type", "ROUND"))),
            face_width=max(3.0, _f(p, "face_width", 12.0)),
            helix=_f(p, "helix_angle", 20.0) if herring else 0.0,
            herringbone=herring,
            pressure_angle=_f(p, "pressure_angle", 20.0),
            backlash=_f(p, "backlash", 0.2),
            bearing_tol=_f(p, "bearing_tolerance", 0.08),
            pin_dia_custom=_f(p, "pin_dia", 5.0),
            wall_t=max(1.5, _f(p, "wall_thickness", 3.0)),
            tie_rod=str(p.get("tie_rod", "AUTO")).upper(),
            plate_t=dowel_plate_t(max(2.0, _f(p, "carrier_thick", 4.0)), max(3.0, _f(p, "face_width", 12.0)),
                                  str(p.get("carrier_type", "CAGE")).upper() != "SINGLE",
                                  str(p.get("pin_type", "STEEL")).upper() == "STEEL"),
            plate_t_asked=max(2.0, _f(p, "carrier_thick", 4.0)),
            output_shaft_dia=_f(p, "output_shaft_dia", 8.0),
            output_type=out_type,
            strength_required=bool(p.get("strength_required", True)),
            out_hub=str(p.get("out_hub", "AUTO")).upper().replace("ZZ", "ZZ"),
            arm_shape=str(p.get("arm_shape", "FLAT")).upper(),
            arm_length=max(10.0, _f(p, "arm_length", 100.0)),
            arm_width=max(4.0, _f(p, "arm_width", 30.0)),
            arm_thickness=max(2.0, _f(p, "arm_thickness", 8.0)),
            arm_load=max(0.0, _f(p, "arm_load", 0.0)),
            mfg=str(p.get("mfg_preset", "FDM_3D")),
            load=load,
            output_shaft_len=_f(p, "output_shaft_len", 20.0),
            make_housing=bool(p.get("generate_housing", True)) or arrangement == "RING",
            od_limit=max(0.0, _f(p, "od_limit", 0.0)),
            footprint_limit=max(0.0, _f(p, "footprint_limit", 0.0)),
            hub_fastener="INSERT" if str(p.get("hub_fastener", "NUT")).upper() == "INSERT" else "NUT",
            max_length=max(0.0, _f(p, "max_length", 0.0)),
            bed=(max(50.0, _f(p, "bed_x", 256.0)), max(50.0, _f(p, "bed_y", 256.0)), max(30.0, _f(p, "bed_z", 256.0))),
            addendum=clamp_addendum(p.get("addendum_coef", 1.0) if p.get("addendum_coef") not in (None, "") else 1.0),
            arrangement=arrangement,
            rope_dia=min(20.0, max(1.0, _f(p, "rope_dia", 4.0))),
            drive_torque=drive_t,
            drive_speed=drive_n,
            **_shift_param(p.get("profile_shift", "AUTO")),
            declutch=bool(p.get("declutch", False)) and (arrangement, normalize_output(
                arrangement, str(p.get("output_type", "FLANGE")).upper())[1]) in DECLUTCH_OUTPUTS,
            mount=_mount_type(p) != "" and (bool(p.get("generate_housing", True)) or arrangement != "CARRIER"),
            mount_type=_mount_type(p),
            **app,
        )


MAX_STAGES = 5
DOWEL_PLATE_MAX = 3.0   # mm the cage plates may grow so the steel pins are a standard length


def dowel_plate_t(plate_t: float, face_width: float, cage: bool, pin_steel: bool) -> float:
    """
    Cage carrier with steel dowels: the pin spans bottom plate + gaps + face width + top plate. A standard length
    that fits that span (hardware.pick_dowel: at most 0.3 mm into the gap to the next carrier, at most 40 % of a
    plate short) is bought ready; otherwise the pins would have to be cut. The plates are thickened (<= 3 mm, both
    plates in proportion) until a standard length fits: stronger plates, no grinding of hardened pins.
    """
    if not (cage and pin_steel):
        return plate_t
    from core.hardware import DOWEL_LENGTHS
    from core.layout import bottom_plate_thickness
    for k in range(int(DOWEL_PLATE_MAX / 0.05) + 1):
        t = round(plate_t + 0.05 * k, 2)
        tb = bottom_plate_thickness(t)
        need = tb + 2.0 * CLEARANCE + face_width + t
        if any(need - 0.4 * min(t, tb) - 1e-6 <= L <= need + (CLEARANCE - 0.3) + 1e-6 for L in DOWEL_LENGTHS):
            return t
    return plate_t
SHIFT_CUSTOM_LIMITS = (-0.5, 0.8)
SHIFT_GRID = (-0.3, -0.15, 0.15, 0.3, 0.45)   # common profile shifts tried for a candidate (AUTO)
SHIFT_TRIES = 4                                # near-miss combinations of a housing size optimised per pair
SHIFT_TRY_MIN = 0.6                            # ... from this margin up (a shift gains ~5-15 %)
UNDERCUT_SLACK = 0.3                           # shift allowed beyond the rack undercut limit (printed teeth)


def _shift_param(v) -> Dict:
    """`profile_shift` of a payload: AUTO (default), NONE / 0 or a number (the sun's x of every stage)."""
    if v is None or str(v).strip().upper() in ("", "AUTO"):
        return {"shift_mode": "AUTO", "shift_x": 0.0}
    if str(v).strip().upper() in ("NONE", "OFF"):
        return {"shift_mode": "NONE", "shift_x": 0.0}
    try:
        x = float(v)
    except (TypeError, ValueError):
        return {"shift_mode": "AUTO", "shift_x": 0.0}
    x = min(SHIFT_CUSTOM_LIMITS[1], max(SHIFT_CUSTOM_LIMITS[0], x))
    return {"shift_mode": "CUSTOM" if abs(x) > 1e-9 else "NONE", "shift_x": round(x, 3)}



def auto_stage_count(p: Dict) -> bool:
    """`stages_count` AUTO (or 0): design() picks the stage count from the ratio, the load and the space."""
    v = p.get("stages_count")
    return (isinstance(v, str) and v.strip().upper() in ("AUTO", "0")) or (isinstance(v, (int, float)) and v == 0)


def stage_count(p: Dict) -> int:
    """Stage count of a payload: an explicit tooth set fixes it, otherwise `stages_count` (1..MAX_STAGES)."""
    if isinstance(p.get("stages"), list) and p["stages"]:
        return max(1, min(MAX_STAGES, len(p["stages"])))
    if auto_stage_count(p):
        return 2                      # placeholder of an automatic count (design() tries each count)
    return max(1, min(MAX_STAGES, int(_f(p, "stages_count", 2))))


ARRANGEMENTS = ("CARRIER", "RING", "SPEED_UP", "WOLFROM", "CYCLOID")
SPECIAL_ARRANGEMENTS = ("WOLFROM", "CYCLOID")      # own engines: core.wolfrom, core.cycloid
CARRIER_OUTPUTS = ("FLANGE", "SHAFT_PRINTED", "SHAFT_STEEL", "ARM")
DRUM_OUTPUTS = ("DRUM_FLANGE", "DRUM_ARM", "DRUM_WINCH")


def normalize_output(arrangement, output_type) -> Tuple[str, str]:
    """
    Arrangement + output member of a payload, made consistent: a rotating housing (RING) takes a drum
    output (flange face, bolted arm, winch drum); the carrier outputs belong to the other arrangements.
    """
    arr = str(arrangement or "CARRIER").upper()
    arr = arr if arr in ARRANGEMENTS else "CARRIER"
    out = str(output_type or "").upper()
    if arr == "RING":
        if out not in DRUM_OUTPUTS:
            out = {"ARM": "DRUM_ARM"}.get(out, "DRUM_FLANGE")
    elif arr == "WOLFROM":                      # the output ring turns: a flange face or an arm on its lid
        if out not in ("DRUM_FLANGE", "DRUM_ARM"):
            out = {"ARM": "DRUM_ARM"}.get(out, "DRUM_FLANGE")
    elif arr == "CYCLOID":                      # output disc through the cover bearing: flange or arm
        if out not in ("FLANGE", "ARM"):
            out = {"DRUM_ARM": "ARM"}.get(out, "FLANGE")
    elif out not in CARRIER_OUTPUTS:
        out = {"DRUM_ARM": "ARM", "DRUM_WINCH": "SHAFT_PRINTED"}.get(out, "FLANGE")
    return arr, out


G_STD = 9.80665          # kg (weight) -> N


def app_load_from_payload(p: Dict, output_type: str, arm_length: float) -> Dict:
    """
    Optional application load of the form / solver: `load_value` in `load_unit` (KG: a weight or a force
    given in kg, N: force, NM: output torque) acting at `load_radius` mm (0 with an arm output: the arm
    length). The older `arm_load` (N at the arm tip) is still accepted.
    """
    value = max(0.0, _f(p, "load_value", 0.0))
    unit = str(p.get("load_unit") or "KG").upper().replace(" ", "")
    unit = {"NM": "NM", "N.M": "NM", "N·M": "NM", "N-M": "NM", "N": "N", "NEWTON": "N", "KG": "KG",
            "KGF": "KG"}.get(unit, "KG")
    radius = max(0.0, _f(p, "load_radius", 0.0))
    if value <= 0 and _f(p, "arm_load", 0.0) > 0:            # legacy: tip force of the arm output, N
        value, unit = _f(p, "arm_load", 0.0), "N"
    if radius <= 0 and output_type in ("ARM", "DRUM_ARM"):
        radius = arm_length
    force = torque = 0.0
    if value > 0:
        if unit == "NM":
            torque = value
        else:
            force = value * G_STD if unit == "KG" else value
            torque = force * radius / 1000.0 if radius > 0 else 0.0
    return {"load_force": force, "load_radius": radius, "load_torque": torque, "load_value": value,
            "load_unit": unit}


def output_member(p: Params, hd: Dict, out_torque_ka: float) -> Dict:
    """
    Output support: a bearing in the top cover carries the last carrier.
      FLANGE        printed hub through a thin-section bearing, threaded-insert holes on its face;
                    hub diameter chosen from the torsion requirement
      SHAFT_PRINTED printed D-shaft (user diameter) on a hub sized to the bearing bore
      SHAFT_STEEL   steel D-shaft (purchased) pressed into the carrier hub
    """
    max_seat_r = hd["root_r"] - 0.5           # seat stays inside the ring bore projection
    steel = p.output_type == "SHAFT_STEEL"
    allow = 150.0 if steel else torsion_allowable(get_material(p.load.struct_material))
    d_req = required_shaft_dia(out_torque_ka, allow, p.load.target_sf)
    if p.output_type == "ARM":       # kol, göbeğe çift-D düzlükle oturur: ezilme de göbek çapını belirler
        d_req = max(d_req, required_key_dia(out_torque_ka, get_material(p.load.struct_material)["sigma_S"],
                                            p.load.target_sf))
    if p.output_type in ("FLANGE", "ARM") and p.hub_fastener == "NUT":   # somun yuvaları kesiti azaltır
        d_req = max(d_req, required_nut_hub_dia(out_torque_ka, allow, p.load.target_sf))

    def fits(b: Dict) -> bool:
        return (b["d_outer"] + p.bearing_tol) / 2.0 <= max_seat_r

    bearings = [(c, BEARING_CATALOG[c]) for c in real_bearings()]
    # smallest catalog hub that is strong enough (for the warning / suggestion) and the housing it needs
    strong_any = sorted((b["d_inner"], b["d_outer"], c) for c, b in bearings if b["d_inner"] >= max(d_req, 10.0))
    suggest = strong_any[0][2] if strong_any else None
    extra = {"suggest": suggest, "suggest_fits": bool(suggest) and fits(BEARING_CATALOG[suggest]),
             "suggest_od": (round(BEARING_CATALOG[suggest]["d_outer"] + p.bearing_tol + 1.0
                                  + hd["envelope_d"] - 2.0 * hd["root_r"], 0) if suggest else 0.0)}
    if p.output_type in ("FLANGE", "ARM"):
        if p.out_hub in BEARING_CATALOG and p.out_hub != "CUSTOM_PIN":
            code = p.out_hub                                       # kullanıcının seçtiği göbek / rulman
            strong = BEARING_CATALOG[code]["d_inner"] >= d_req - 1e-6
        else:
            ok = sorted((b["d_outer"], -b["C_kN"], c) for c, b in bearings
                        if fits(b) and b["d_inner"] >= max(d_req, 10.0))
            strong = bool(ok)
            if ok:
                code = ok[0][2]
            else:
                fit_any = sorted((-b["d_inner"], -b["C_kN"], c) for c, b in bearings if fits(b) and b["d_inner"] >= 8.0)
                code = fit_any[0][2] if fit_any else "608ZZ"
        hub = BEARING_CATALOG[code]["d_inner"]
        options = [{"code": c, "d": b["d_inner"], "D": b["d_outer"], "B": b["width"], "fits": fits(b),
                    "strong": b["d_inner"] >= d_req - 1e-6}
                   for c, b in sorted(bearings, key=lambda cb: (cb[1]["d_inner"], cb[1]["d_outer"]))
                   if b["d_inner"] >= 8.0]
        return {"type": p.output_type, "bearing": code, "hub_d": hub, "shaft_d": hub, "check_d": hub, "steel": False,
                "required_d": d_req, "strong": strong, "seat_fits": fits(BEARING_CATALOG[code]),
                "hub_options": options, **extra}
    shaft = p.output_shaft_dia
    ok = sorted((abs(b["d_inner"] - shaft), b["d_outer"], -b["C_kN"], c) for c, b in bearings
                if fits(b) and b["d_inner"] >= shaft - 1e-6)
    code = ok[0][3] if ok else "608ZZ"
    return {"type": p.output_type, "bearing": code, "hub_d": BEARING_CATALOG[code]["d_inner"], "shaft_d": shaft,
            "check_d": shaft, "steel": steel, "required_d": d_req, "strong": shaft >= d_req - 1e-6,
            "seat_fits": bool(ok), **extra}


# ─── Rotating housing: carrier of the last stage fixed, its ring is the output drum ─────────────

LID_ROOF = 3.0            # drum lid material above the bearing pocket
JOIN_NUT_BACK = 3.4       # M3 side nut pocket reaches this far inside the screw axis (parts.NUT_SLOT_BACK)
M3_HOLE_R, M3_HEAD_R, M3_HEAD_DEPTH = 1.7, 3.1, 3.4
INSERT_HOLE_R = 2.0       # M3 heat-set insert hole Ø4.0
NECK_INSET = 0.3          # neck between a carrier plate and the next sun: root radius - 0.3 (assembly)
DRUM_BORE_AUTO_MAX = 50.0  # automatic drum bearing: common sizes only (6810ZZ / 6010 class and below)


def drum_dims(p: Params, hd: Dict) -> Dict:
    """
    Radii of the turning drum: the ring gear of the last stage with a closed lid on top. A herringbone
    drum is split at the V apex; its halves are screwed together through the wall (M3 + side nuts), so
    the wall holds a screw hole and a nut pocket outside the tooth roots. A winch drum has two rims.
    """
    root = hd["root_r"]
    wall = max(p.wall_t, 3.0)
    join_r = 0.0
    if p.herringbone:
        join_r = root + 1.0 + JOIN_NUT_BACK
        wall = max(wall, join_r + M3_HOLE_R + 1.2 - root)
    drum_r = root + wall
    rim = max(6.0, 2.5 * p.rope_dia) if p.output_type == "DRUM_WINCH" else 0.0
    return {"drum_r": drum_r, "join_r": join_r, "rim": rim, "od": 2.0 * (drum_r + rim)}


def _bolt_in_out(p: Params) -> Tuple[float, float]:
    """Radial extent of a lid screw seat inside / outside its axis: side nut pocket or insert hole."""
    return (JOIN_NUT_BACK, M3_HOLE_R) if p.hub_fastener == "NUT" else (INSERT_HOLE_R, INSERT_HOLE_R)


def drum_screw_circles(p: Params, dd: Dict) -> Dict:
    """
    Lid screws (the user's part / the output arm: DRUM_FLANGE, DRUM_ARM) on the outer edge of the lid, and
    the joint screws of a herringbone drum. Both on the same circle they alternate (half a pitch apart).
    """
    r_bc = n_bc = 0
    if p.output_type in ("DRUM_FLANGE", "DRUM_ARM"):
        r_bc = dd["drum_r"] - 1.2 - _bolt_in_out(p)[1]
    join_r = dd["join_r"]
    r_ref = max(r_bc, join_r)
    if r_ref <= 0:
        return {"bolt_r": 0.0, "bolt_n": 0, "join_r": 0.0, "join_n": 0}
    both = r_bc > 0 and join_r > 0
    # nut pockets 5.8 mm wide plus material between them; alternating circles need twice the room
    n = int(math.pi * r_ref / 8.0) if both else int(2.0 * math.pi * r_ref / 11.0)
    n = max(4, min(8, n - n % 2))
    if r_bc > 0:
        n_bc = n
    return {"bolt_r": float(r_bc), "bolt_n": n_bc, "join_r": float(join_r), "join_n": n if join_r > 0 else 0}


def drum_pocket_limit(p: Params, geo: StageGeometry, dd: Dict) -> float:
    """Largest bearing pocket radius in the lid: inside the ring teeth and clear of the lid screws."""
    lim = geo.tip_ring - 0.8
    if p.output_type in ("DRUM_FLANGE", "DRUM_ARM"):
        inner, outer = _bolt_in_out(p)
        lim = min(lim, dd["drum_r"] - 1.2 - outer - 1.2 - inner)
    if p.herringbone:
        lim = min(lim, dd["join_r"] - M3_HEAD_R - 1.2)
    return lim


def drum_bearing_options(p: Params, geo: StageGeometry, pin_hole: float, dd: Dict) -> List[str]:
    """
    The drum turns on one ball bearing in its lid, seated on a stub of the fixed carrier's top plate.
    The stub (and the inner-race shoulder) stays inside the pin circle, the pocket inside the ring teeth
    and the lid screws. Best first: the largest bore (a thick stub and a wide bearing hold the drum stiff
    against tilting), then the thinnest (a thinner lid), then the static capacity C0. Automatic choice stays
    within common sizes (bore <= 50 mm); larger ones only when the user picks them.
    """
    stub_lim = geo.center_distance - pin_hole / 2.0 - 1.0
    pocket_lim = drum_pocket_limit(p, geo, dd)
    fixed = p.out_hub in BEARING_CATALOG and p.out_hub != "CUSTOM_PIN"
    ok = []
    for c in ([p.out_hub] if fixed else real_bearings()):
        b = BEARING_CATALOG[c]
        if b["d_inner"] < 8.0 - 1e-9 or (not fixed and b["d_inner"] > DRUM_BORE_AUTO_MAX):
            continue
        if inner_race_diameter(b) / 2.0 > stub_lim or (b["d_outer"] + p.bearing_tol) / 2.0 > pocket_lim:
            continue
        ok.append(c)
    ok.sort(key=lambda c: (-BEARING_CATALOG[c]["d_inner"], BEARING_CATALOG[c]["width"], -BEARING_CATALOG[c]["C0_kN"]))
    return ok


def drum_lid_t(p: Params, bearing_width: float) -> float:
    t = bearing_width + LID_ROOF
    if p.output_type in ("DRUM_FLANGE", "DRUM_ARM"):     # screw seat: nut roof + nut + room for the tip
        t = max(t, 10.5 if p.hub_fastener == "NUT" else 7.5)
    if p.herringbone:                                    # joint screw heads sink into the lid
        t = max(t, M3_HEAD_DEPTH + 3.0)
    return t


def drum_arm_height(p: Params) -> float:
    return _drum_arm_height(p.arm_shape, p.arm_width, p.arm_thickness)


def drum_arm_hub_r(out: Dict) -> float:
    """Hub disk of an arm bolted onto the drum lid: covers the lid screw circle (heads + 2.5 mm wall)."""
    return max(out.get("bolt_r", 0.0) + M3_HEAD_R + 2.5, out.get("pocket_r", 0.0) + 2.0)


def _pin_hole(p: Params, pin_d: float) -> float:
    return pin_d + (0.1 if not p.pin_steel else 0.0)


def drum_member(p: Params, hd: Dict, geo: StageGeometry, pin_d: float, code: Optional[str]) -> Dict:
    """Output member of a rotating housing: the drum with its lid bearing, screw circles and rims."""
    dd = drum_dims(p, hd)
    fits_codes = drum_bearing_options(Params(**{**p.__dict__, "out_hub": "AUTO"}), geo, _pin_hole(p, pin_d), dd)
    seat_fits = bool(code)
    if not code:
        code = fits_codes[0] if fits_codes else "608ZZ"
    b = BEARING_CATALOG[code]
    circles = drum_screw_circles(p, dd)
    options = [{"code": c, "d": bb["d_inner"], "D": bb["d_outer"], "B": bb["width"], "fits": c in fits_codes,
                "strong": True}
               for c, bb in sorted(((c, BEARING_CATALOG[c]) for c in real_bearings()),
                                   key=lambda cb: (cb[1]["d_inner"], cb[1]["d_outer"])) if bb["d_inner"] >= 8.0]
    return {"type": p.output_type, "drum": True, "bearing": code, "hub_d": b["d_inner"], "shaft_d": 0.0,
            "check_d": 0.0, "steel": False, "required_d": 0.0, "strong": True, "seat_fits": seat_fits,
            "drum_r": dd["drum_r"], "drum_od": dd["od"], "rim": dd["rim"], "rope_d": p.rope_dia,
            "lid_t": drum_lid_t(p, b["width"]), "pocket_r": (b["d_outer"] + p.bearing_tol) / 2.0,
            "load_r": (dd["drum_r"] + p.rope_dia / 2.0) if p.output_type == "DRUM_WINCH" else 0.0,
            "hub_options": options, "suggest": None, "suggest_fits": False, "suggest_od": 0.0, **circles}


DECLUTCH_OUTPUTS = (("CARRIER", "ARM"), ("RING", "DRUM_ARM"), ("WOLFROM", "DRUM_ARM"), ("CYCLOID", "ARM"))


def _mount_type(p: Dict) -> str:
    """Mounting bracket of a payload: mount_type SIDE / BASE / PANEL (old forms: mount_bracket = SIDE)."""
    from core.layout import MOUNT_TYPES
    mt = str(p.get("mount_type") or ("SIDE" if p.get("mount_bracket") else "")).upper()
    return mt if mt in MOUNT_TYPES else ""


def mount_spec(p: Params, hd: Dict) -> Optional[Dict]:
    """Mounting bracket: the tie rods carry the reaction torque into the shelf (engineering.mount_checks)."""
    if not p.mount:
        return None
    from core.layout import mount_shelf_t
    r = sum(math.hypot(x, y) for x, y in hd["positions"]) / len(hd["positions"])
    return {"n": len(hd["positions"]), "r": r, "d": hd["tie"]["d"], "engage": mount_shelf_t(hd["tie"])}


def drum_spec(p: Params, out: Dict) -> Optional[Dict]:
    """Screw circles of the drum for engineering.drum_checks (projected bearing area of the printed holes)."""
    if not out.get("drum"):
        return None
    spec = {}
    if out.get("bolt_n"):
        nut = p.hub_fastener == "NUT"
        spec.update(bolt_n=out["bolt_n"], bolt_r=out["bolt_r"], bolt_d=3.0 if nut else 4.0,
                    bolt_engage=5.2 if nut else 5.7)
    if out.get("join_n"):
        spec.update(join_n=out["join_n"], join_r=out["join_r"], join_d=3.0, join_engage=4.4)
    return spec or None


def _output_torque_ka(p: Params, ratio: float, n_stages: int) -> float:
    """Torque on the output member incl. K_A (speed-up: the drive torque itself, it enters there)."""
    if p.reverse:
        return p.drive_torque * p.load.application_factor
    eta_total = get_material(p.load.gear_material)["eta"] ** n_stages
    return p.load.motor_torque * p.load.application_factor * ratio * eta_total


SPEEDUP_TEXT = {
    "tr": {"main": "Jeneratör {n_g:.0f} rpm'de {t_g:.3f} Nm ({p:.1f} W) alır; giriş {t_in:g} Nm @ {n_in:g} rpm.",
           "cog": "Kalkış: motorun dişli/manyetik takılma torku (~{c:.3f} Nm) girişte ~{c_in:.2f} Nm olarak hissedilir "
                  "— rüzgâr türbininde düşük oran veya takılmasız (coreless / BLDC) jeneratör seçin.",
           "ratio_high": "Yüksek oranlı hız artırıcıda sürtünme girişte {i:.0f} kat büyür: {i:.0f}:1 üstü oranlar "
                         "elle çevirmede ağır gelebilir; 2 kademe ve ≤ 30:1 önerilir.",
           "fast": "Jeneratör devri {n_g:.0f} rpm — bu motor için yüksek ({n_max:.0f} rpm üstü): oranı düşürün."},
    "en": {"main": "The generator gets {t_g:.3f} Nm at {n_g:.0f} rpm ({p:.1f} W); input {t_in:g} Nm @ {n_in:g} rpm.",
           "cog": "Start-up: the motor's detent / cogging torque (~{c:.3f} Nm) is felt as ~{c_in:.2f} Nm at the input — "
                  "for a wind rotor use a lower ratio or a cogging-free (coreless / BLDC) generator.",
           "ratio_high": "In a high-ratio speed-up gearbox the friction grows {i:.0f} times at the input: ratios above "
                         "{i:.0f}:1 can feel heavy by hand; 2 stages and ≤ 30:1 are recommended.",
           "fast": "Generator speed {n_g:.0f} rpm is high for this motor (above {n_max:.0f} rpm): lower the ratio."},
}


def speedup_info(p: Params, eng: Dict, lang: str) -> Dict:
    """Speed-up gearbox (generator, wind rotor, hand crank): what reaches the generator, start-up feel."""
    t = SPEEDUP_TEXT["en" if lang == "en" else "tr"]
    ratio = eng["total_ratio"]
    n_g, t_g = eng["output_speed"], eng["output_torque"]
    power = t_g * n_g * 2.0 * math.pi / 60.0
    motor = get_motor_info(p.motor_code)
    detent = float(motor.get("detent_nm", 0.0))
    eta = eng["efficiency"]
    notes = [t["main"].format(n_g=n_g, t_g=t_g, p=power, t_in=round(p.drive_torque, 3), n_in=round(p.drive_speed, 2))]
    if detent > 0:
        notes.append(t["cog"].format(c=detent, c_in=detent * ratio / max(eta, 0.5)))
    if ratio > 30.0:
        notes.append(t["ratio_high"].format(i=ratio))
    n_max = float(motor.get("max_speed_rpm", 0.0))
    if n_max > 0 and n_g > n_max:
        notes.append(t["fast"].format(n_g=n_g, n_max=n_max))
    return {"generator_speed": round(n_g, 1), "generator_torque": round(t_g, 4), "power_w": round(power, 2),
            "detent_at_input": round(detent * ratio / max(eta, 0.5), 3) if detent > 0 else 0.0,
            "text": " ".join(notes), "summary": notes[0], "notes": notes[1:],
            "status": "low" if len(notes) > 1 else "ok"}


def _with_flow(p: Params, ratio: float, out: Dict) -> Params:
    """
    Per-candidate load case: a speed-up gearbox works with the exact ratio (sun torque = drive torque /
    i, sun speed = drive speed x i); a winch drum without a given lever arm uses its own rope radius.
    """
    q = p
    if p.reverse and ratio > 0:
        q = replace(q, load=replace(q.load, motor_torque=p.drive_torque / ratio, motor_speed=p.drive_speed * ratio))
    if p.output_type == "DRUM_WINCH" and p.load_force > 0 and p.load_radius <= 0 and out.get("load_r"):
        r = out["load_r"]
        q = replace(q, load_radius=r, load_torque=p.load_force * r / 1000.0)
    return q


def declutch_height(p: Params, torque_ka: float, hub_d: float = 0.0) -> float:
    """Height of a declutchable arm (collar, arm, cap, index plunger knob) above the face it is screwed to."""
    from core.engineering import declutch_design, declutch_hub_d
    return declutch_design(declutch_hub_d(hub_d), torque_ka, p.load.struct_material, p.load.target_sf, p.arm_shape,
                           p.arm_width, p.arm_thickness)["lay"]["height"]


def layout_for(p: Params, n_stages: int, out: Dict, hd: Dict, torque_ka: float = 0.0) -> AxialLayout:
    """Axial layout (overall length) of a design; same numbers the CAD assembly uses."""
    if p.ring_out:
        prot = drum_arm_height(p) if p.output_type == "DRUM_ARM" else 0.0
        if p.output_type == "DRUM_ARM" and p.declutch:
            prot = declutch_height(p, torque_ka)
        return ring_layout(n_stages, p.face_width, p.plate_t, CLEARANCE, p.cage, get_motor_info(p.motor_code),
                           hd["tie"], out["lid_t"], prot, mount=p.mount)
    ob = get_bearing_info(out["bearing"])
    arm = ({"shape": p.arm_shape, "width": p.arm_width, "thickness": p.arm_thickness,
            "declutch_height": declutch_height(p, torque_ka, out["hub_d"]) if p.declutch else 0.0}
           if out["type"] == "ARM" else None)
    prot = output_protrusion(out["type"], p.output_shaft_len, out["hub_d"], arm, p.hub_fastener)
    return axial_layout(n_stages, p.face_width, p.plate_t, CLEARANCE, p.cage, ob["width"],
                        get_motor_info(p.motor_code), hd["tie"], prot, p.make_housing, out["type"], mount=p.mount)


def housing_footprint(hd: Dict) -> float:
    """Square footprint of the lugged housing/flange outline on the print bed (lugs sit at 45°)."""
    half = hd["wall_r"]
    for x, y in hd["positions"]:
        half = max(half, abs(x) + hd["lug_r"], abs(y) + hd["lug_r"])
    return 2.0 * half


def bed_fits(p: Params, w: float, d: float, h: float) -> bool:
    """Footprint w x d (either orientation) and height h on the print bed."""
    bx, by, bz = p.bed
    return h <= bz + 1e-6 and ((w <= bx and d <= by) or (w <= by and d <= bx))


def _nut_dia(p: Params, out: Dict) -> float:
    return out["hub_d"] if (out["type"] in ("FLANGE", "ARM") and p.hub_fastener == "NUT") else 0.0


def max_output_hub(p: Params, hd: Dict) -> float:
    """Largest output hub (bearing bore) whose bearing seat fits this housing."""
    lim = hd["root_r"] - 0.5
    best = 0.0
    for c in real_bearings():
        b = BEARING_CATALOG[c]
        if (b["d_outer"] + p.bearing_tol) / 2.0 <= lim:
            best = max(best, b["d_inner"])
    return best


def arm_spec(p: Params, hub_d: float) -> Optional[Dict]:
    if p.output_type == "DRUM_ARM":               # bolted onto the drum lid: no double-D lock
        return {"shape": p.arm_shape, "length": p.arm_length, "width": p.arm_width, "thickness": p.arm_thickness,
                "hub_d": 0.0, "flat": 0.0, "key_h": 0.0, "drum": True, "declutch": p.declutch}
    if p.output_type != "ARM":
        return None
    return {"shape": p.arm_shape, "length": p.arm_length, "width": p.arm_width, "thickness": p.arm_thickness,
            "hub_d": hub_d, "flat": ARM_FLAT * hub_d, "key_h": arm_key_height(hub_d), "declutch": p.declutch}


def app_load_spec(p: Params, out: Dict) -> Optional[Dict]:
    """Application load for engineering.analyze (None: no load given, or a force without its lever arm)."""
    if p.load_torque <= 0:
        return None
    kind = get_motor_info(p.motor_code).get("kind", "custom")
    spec = {"torque": p.load_torque, "force": p.load_force, "reserve": LOAD_RESERVE.get(kind, 1.25)}
    if p.load_force > 0:
        spec["bearing_c0"] = get_bearing_info(out["bearing"])["C0_kN"] * 1000.0
        if out["type"] in ("SHAFT_PRINTED", "SHAFT_STEEL"):
            # the pulley / drum / wheel sits on the protruding shaft: force at its middle
            spec["shaft"] = {"d": out["shaft_d"], "lever": p.output_shaft_len / 2.0 + 2.0, "steel": out["steel"]}
    return spec


LOAD_TEXT = {
    "tr": {
        "ok": "✓ Uygun: {need_txt}; redüktör {have:.1f} Nm veriyor (rezerv ×{res:.2f}, önerilen ≥ ×{target:.2f}).",
        "low": "⚠ Sınırda: {need_txt}; redüktör {have:.1f} Nm veriyor (rezerv ×{res:.2f}, önerilen ≥ ×{target:.2f}) "
               "— {risk}.",
        "fail": "✗ Uygun değil: {need_txt}, redüktör yalnızca {have:.1f} Nm veriyor (×{res:.2f}).",
        "weak": "✗ Uygun değil: {need_txt}; redüktörün sürekli dayanımı {cap:.1f} Nm — dişliler / çıkış bu yükü "
                "taşıyamaz.",
        "side": "{state}: {need_txt}; redüktör {have:.1f} Nm veriyor (rezerv ×{res:.2f}), ancak:",
        "weak_note": "Redüktörün sürekli dayanımı da yetmiyor ({cap:.1f} Nm < {need:.1f} Nm).",
        "bearing": "Çıkış rulmanı {code} bu yan yük için zayıf ({f:.0f} N, s0 = {s:.2f}, hedef {t:g}): daha büyük "
                   "çıkış göbeği / rulmanı seçin.",
        "shaft": "Çıkış mili Ø{d:g} yan yük ve tork altında zayıf (S = {s:.2f}, hedef {t:.2f}): mili kalınlaştırın, "
                 "çelik mil veya flanş çıkışı seçin.",
        "overload": "Not: yük için yeterli, ancak motor tam torkunda ({have:.1f} Nm) redüktör dayanımı ({cap:.1f} Nm) "
                    "aşılır — sıkışma durumu için motor akımını sınırlayın.",
        "incomplete": "Yük kontrolü için kuvvet kolu gerekli: kuvvetin eksene uzaklığını (makara / tambur yarıçapı, "
                      "kol boyu) girin.",
        "fixes": "Seçenekler: {items}.",
        "fix_ratio": "oranı en az {r:.0f}:1 yapın",
        "fix_stages": " ({n} kademe gerekir)",
        "fix_speed_stepper": " — aynı {n_out:.3g} rpm çıkış için motor ~{n_m:.0f} rpm döner",
        "fix_speed_drop": " — çıkış devri ~{n_out:.3g} rpm'e düşer",
        "fix_motor": "en az {t:.2f} Nm torklu motor kullanın",
        "fix_lever": "kuvvet kolunu en fazla {l:.0f} mm yapın",
        "fix_strength": "daha büyük gövdeye izin verin veya daha güçlü malzeme (PA-CF) seçin",
        "risk_stepper": "sürtünme veya rüzgâr artarsa step motor adım kaçırabilir",
        "risk_other": "sürtünme artarsa motor zorlanır, devir düşer",
        "need_force": "{v:g} {u} × {r:.0f} mm → {need:.1f} Nm gerekiyor",
        "need_torque": "{need:.1f} Nm yük torku gerekiyor",
        "state_low": "⚠ Sınırda", "state_fail": "✗ Uygun değil",
        "short_ok": "✓ Uygun ×{res:.2f}", "short_low": "⚠ Sınırda ×{res:.2f}", "short_fail": "✗ Uygun değil ×{res:.2f}",
        "short_low_side": "⚠ Sınırda", "short_fail_side": "✗ Uygun değil", "short_incomplete": "? Kuvvet kolu girin",
    },
    "en": {
        "ok": "✓ Suitable: {need_txt}; the gearbox delivers {have:.1f} Nm (reserve ×{res:.2f}, recommended ≥ "
              "×{target:.2f}).",
        "low": "⚠ Marginal: {need_txt}; the gearbox delivers {have:.1f} Nm (reserve ×{res:.2f}, recommended ≥ "
               "×{target:.2f}) — {risk}.",
        "fail": "✗ Not suitable: {need_txt}, the gearbox delivers only {have:.1f} Nm (×{res:.2f}).",
        "weak": "✗ Not suitable: {need_txt}; the continuous strength of the gearbox is {cap:.1f} Nm — the gears / output "
                "cannot carry this load.",
        "side": "{state}: {need_txt}; the gearbox delivers {have:.1f} Nm (reserve ×{res:.2f}), but:",
        "weak_note": "The continuous strength of the gearbox is not enough either ({cap:.1f} Nm < {need:.1f} Nm).",
        "bearing": "The output bearing {code} is weak for this side load ({f:.0f} N, s0 = {s:.2f}, target {t:g}): "
                   "choose a larger output hub / bearing.",
        "shaft": "The output shaft Ø{d:g} is weak under the side load and torque (S = {s:.2f}, target {t:.2f}): use a "
                 "thicker shaft, a steel shaft or a flange output.",
        "overload": "Note: enough for the load, but at full motor torque ({have:.1f} Nm) the gearbox strength "
                    "({cap:.1f} Nm) is exceeded — limit the motor current in case of a jam.",
        "incomplete": "The load check needs the lever arm: enter the distance of the force from the axis (pulley / drum "
                      "radius, arm length).",
        "fixes": "Options: {items}.",
        "fix_ratio": "raise the ratio to at least {r:.0f}:1",
        "fix_stages": " ({n} stages needed)",
        "fix_speed_stepper": " — for the same {n_out:.3g} rpm output the motor turns ~{n_m:.0f} rpm",
        "fix_speed_drop": " — the output speed drops to ~{n_out:.3g} rpm",
        "fix_motor": "use a motor with at least {t:.2f} Nm",
        "fix_lever": "shorten the lever arm to at most {l:.0f} mm",
        "fix_strength": "allow a larger housing or a stronger material (PA-CF)",
        "risk_stepper": "with more friction or wind the stepper may lose steps",
        "risk_other": "with more friction the motor labours and slows down",
        "need_force": "{v:g} {u} × {r:.0f} mm → {need:.1f} Nm needed",
        "need_torque": "{need:.1f} Nm load torque needed",
        "state_low": "⚠ Marginal", "state_fail": "✗ Not suitable",
        "short_ok": "✓ Suitable ×{res:.2f}", "short_low": "⚠ Marginal ×{res:.2f}", "short_fail": "✗ Not suitable ×{res:.2f}",
        "short_low_side": "⚠ Marginal", "short_fail_side": "✗ Not suitable", "short_incomplete": "? Enter the lever arm",
    },
}

PRACTICAL_STAGE_RATIO = 9.0
FACE_LOAD_WARN = 1.8     # K_Hbeta above this: the face width is poorly used (warning)
TIP_LAND_FDM = 0.4       # mm, tooth tip thickness an FDM nozzle can still print


def load_verdict(p: Params, eng: Dict, out: Dict, ratio: float, n_stages: int, lang: str) -> Optional[Dict]:
    """
    Plain-language answer to "can this gearbox move my load?" from the application-load checks of the
    analysis, with what to change when it cannot (ratio, motor, lever arm, strength).
    """
    if p.load_value <= 0:
        return None
    t = LOAD_TEXT["en" if lang == "en" else "tr"]
    unit_txt = {"KG": "kg", "N": "N", "NM": "Nm"}[p.load_unit]
    if p.load_torque <= 0:
        return {"status": "incomplete", "text": t["incomplete"], "summary": t["incomplete"], "short": t["short_incomplete"],
                "value": p.load_value, "unit": p.load_unit}
    chk = eng.get("app_load_checks") or {}
    drive, cap_c = chk.get("load_drive"), chk.get("load_capacity")
    if not drive or not cap_c:
        return None
    need, have, cap = drive["value"], drive["limit"], cap_c["limit"]
    res, target = drive["safety"], drive["target"]
    need_txt = (t["need_torque"].format(need=need) if p.load_unit == "NM" else
                t["need_force"].format(v=p.load_value, u=unit_txt, r=p.load_radius, need=need))
    kind = get_motor_info(p.motor_code).get("kind", "custom")
    drive_fail, drive_low, weak = res < 1.0 - 1e-9, res < target - 1e-9, cap_c["safety"] < 1.0 - 1e-9
    notes = []
    if drive_fail:
        status, main = "fail", t["fail"].format(need_txt=need_txt, have=have, res=res)
        if weak:
            notes.append(t["weak_note"].format(need=need, cap=cap))
    elif weak:
        status, main = "fail", t["weak"].format(need_txt=need_txt, cap=cap)
    elif drive_low:
        status, main = "low", t["low"].format(need_txt=need_txt, have=have, res=res, target=target,
                                              risk=t["risk_stepper" if kind == "stepper" else "risk_other"])
    else:
        status, main = "ok", t["ok"].format(need_txt=need_txt, have=have, res=res, target=target)
    torque_status = status
    side = []                                   # the side load on the output (bearing, shaft)
    b = chk.get("load_bearing")
    if b and not b["ok"]:
        status = "fail" if b["safety"] < 1.0 else ("low" if status == "ok" else status)
        side.append(t["bearing"].format(code=out["bearing"], f=b["value"], s=b["safety"], t=b["target"]))
    sh = chk.get("load_shaft")
    if sh and not sh["ok"]:
        status = "fail" if sh["safety"] < 1.0 else ("low" if status == "ok" else status)
        side.append(t["shaft"].format(d=out["shaft_d"], s=sh["safety"], t=sh["target"]))
    if side and torque_status == "ok":          # the torque is fine, the side load is not
        main = t["side"].format(state=t["state_" + status], need_txt=need_txt, have=have, res=res)
    notes += side
    if status in ("ok", "low") and cap_c["safety"] >= 1.0 and cap < have - 1e-6:
        notes.append(t["overload"].format(have=have, cap=cap))
    fixes = []
    if drive_low:
        tm = p.load.motor_torque
        eta = get_material(p.load.gear_material)["eta"]
        n_out = eng["output_speed"]
        for k in range(n_stages, MAX_STAGES + 1):
            r_k = need * target / (tm * eta ** k)
            if r_k <= PRACTICAL_STAGE_RATIO ** k:
                txt = t["fix_ratio"].format(r=math.ceil(r_k))
                if k > n_stages:
                    txt += t["fix_stages"].format(n=k)
                n_max = float(get_motor_info(p.motor_code).get("speed_rpm", 300.0))
                if kind == "stepper" and n_out * r_k <= max(n_max, p.load.motor_speed) * 1.05:
                    # the driver can keep the output speed: the motor just turns faster (still in its torque range)
                    txt += t["fix_speed_stepper"].format(n_out=n_out, n_m=n_out * r_k)
                else:
                    txt += t["fix_speed_drop"].format(n_out=n_out * ratio / r_k)
                fixes.append(txt)
                break
        fixes.append(t["fix_motor"].format(t=need * target / (ratio * eta ** n_stages)))
        l_max = have / (p.load_force * target) * 1000.0 if p.load_force > 0 and p.load_radius > 0 else 0.0
        if l_max >= 10.0:                       # a shorter lever only when it is a practical option
            fixes.append(t["fix_lever"].format(l=math.floor(l_max)))
    if weak:
        fixes.append(t["fix_strength"])
    text = " ".join([main] + notes + ([t["fixes"].format(items="; ".join(fixes))] if fixes else []))
    short = t["short_" + status] if torque_status == status else t["short_" + status + "_side"]
    if weak and not drive_fail:
        short = t["short_fail_side"]
    return {"status": status, "text": text, "summary": " ".join([main] + notes), "short": short.format(res=res),
            "need": round(need, 2),
            "have": round(have, 2), "capacity": round(cap, 2), "reserve": round(res, 3), "reserve_target": target,
            "value": p.load_value, "unit": p.load_unit, "radius": p.load_radius, "force": round(p.load_force, 1),
            "fixes": fixes}


def planet_bearing_options(geo: StageGeometry, p: Params) -> List[Dict]:
    """Bearing choices that fit this planet (best first). Empty -> nothing fits."""
    pocket_limit = 2.0 * (geo.root_planet - rim_min(geo.module, geo.addendum))
    if p.bearing == "CUSTOM_PIN":
        d = p.pin_dia_custom
        if 2.0 * geo.root_planet - d < 2.0 * rim_min(geo.module, geo.addendum):
            return []
        return [{"code": "CUSTOM_PIN", "n": 0, "layout": "bushing", "pin": d, "pocket": 0.0}]
    codes = real_bearings() if p.bearing == "AUTO" else [p.bearing]
    out = []
    for code in codes:
        b = BEARING_CATALOG.get(code)
        if not b:
            continue
        if p.pin_steel and b["d_inner"] not in DOWEL_DIAMETERS:
            continue
        pocket = b["d_outer"] + p.bearing_tol
        if pocket > pocket_limit:
            continue
        dual_ok = p.face_width >= 2 * b["width"] + WEB_MIN
        single_ok = p.face_width >= b["width"] + 1.0
        if p.layout == "DUAL":
            if not dual_ok:
                continue
            n = 2
        elif p.layout == "SINGLE":
            if not single_ok:
                continue
            n = 1
        else:
            if not single_ok:
                continue
            n = 2 if dual_ok else 1
        # carrier pin boss must stay inside the ring bore
        if geo.center_distance + b["d_inner"] / 2.0 + BOSS_WALL > geo.tip_ring - 0.8:
            continue
        out.append({"code": code, "n": n, "layout": "dual" if n == 2 else "single", "pin": b["d_inner"],
                    "pocket": pocket, "score": b["C_kN"] * n})
    out.sort(key=lambda o: (-o["score"], BEARING_CATALOG[o["code"]]["d_outer"]))
    return out if p.bearing == "AUTO" else out[:1]


def _collar_r(p: Params) -> float:
    return max(p.motor_shaft_dia + 7.5, 12.0) / 2.0


def _make_option(module: float, z_ring: int, zs: int, p: Params, x: float, cache: Dict) -> Optional[Dict]:
    """One stage option (sun zs in the ring z_ring) at profile shift x; None when it cannot be built."""
    key = ("opt", module, z_ring, zs, round(x, 3))
    if key in cache:
        return cache[key]
    cache[key] = None
    zmin = z_min(p.pressure_angle)
    eps_req = 1.05 if p.herringbone else 1.2
    n_list = [p.num_planets] if p.num_planets >= 2 else list(PLANET_CHOICES)
    if (z_ring - zs) % 2:
        return None
    zp = (z_ring - zs) // 2
    if zp < zmin:
        return None
    geo = None
    n = 0
    for cand in n_list:                 # automatic: the most planets that are equally spaced and clear
        if (zs + z_ring) % cand:
            continue
        if geo is None:
            geo = p.geo(zs, zp, z_ring, module, x)
        if 2.0 * geo.center_distance * math.sin(math.pi / cand) - 2.0 * geo.tip_planet < max(0.5 * module, 0.8):
            continue
        n = cand
        break
    if not n:
        return None
    if geo.eps_sun_planet < eps_req or geo.eps_planet_ring < eps_req:
        return None
    bearings = planet_bearing_options(geo, p)
    fits = bool(bearings)
    if not fits:
        if p.mode != "MANUAL":
            return None
        fallback = get_bearing_info(p.bearing if p.bearing not in ("AUTO",) else "688ZZ")
        bearings = [{"code": p.bearing if p.bearing != "AUTO" else "688ZZ", "n": 1, "layout": "single",
                     "pin": fallback["d_inner"], "pocket": fallback["d_outer"] + p.bearing_tol, "score": 0}]
    bsel = bearings[0]
    # bottom cage plate must hold the pin around the sun (stage 1 also clears the motor collar)
    cage_ok = geo.center_distance - bsel["pin"] / 2.0 - 1.0 >= geo.tip_sun + 0.6
    if p.cage and not cage_ok and p.mode != "MANUAL":
        return None
    sd = StageDesign(geo=geo, num_planets=n, face_width=p.face_width, helix_deg=p.helix,
                     herringbone=p.herringbone, bearing_code=bsel["code"], bearings_per_planet=bsel["n"],
                     pin_dia=bsel["pin"], pin_steel=p.pin_steel, carrier_cage=p.cage, plate_t=p.plate_t,
                     clearance=CLEARANCE, mfg_error=MFG_ERROR.get(p.mfg, 0.02))
    opt = {"zs": zs, "zp": zp, "n": n, "ratio": 1.0 + z_ring / zs, "geo": geo, "bearing": bsel,
           "fits": fits and (cage_ok or not p.cage), "design": sd, "factors": None, "x": round(x, 3)}
    if p.ring_out:
        # as the last (star) stage: the fixed carrier is a cage on the base plate, the drum turns on a
        # bearing seated on its top plate
        dkey = ("drum", module, z_ring)
        if dkey not in cache:
            cache[dkey] = drum_dims(p, p.hd(z_ring, module))
        drums = drum_bearing_options(p, geo, _pin_hole(p, bsel["pin"]), cache[dkey]) if fits and cage_ok else []
        opt.update(ratio_star=z_ring / zs, drum_bearing=drums[0] if drums else None,
                   star_ok=fits and cage_ok and bool(drums))
    cache[key] = opt
    return opt


def stage_options(module: float, z_ring: int, p: Params, cache: Dict, shift: Optional[float] = None) -> List[Dict]:
    x = p.base_shift() if shift is None else shift
    key = (module, z_ring, round(x, 3))
    if key in cache:
        return cache[key]
    zmin = z_min(p.pressure_angle)
    opts = [o for o in (_make_option(module, z_ring, zs, p, x, cache) for zs in range(zmin, z_ring - 2 * zmin + 1))
            if o is not None]
    opts.sort(key=lambda o: o["ratio"])
    cache[key] = opts
    return opts


def _shift_combo(combo: List[Dict], p: Params, cache: Dict, x: float) -> Optional[List[Dict]]:
    out = []
    for o in combo:
        s_ = _make_option(o["geo"].module, o["geo"].z_ring, o["zs"], p, x, cache)
        if s_ is None:
            return None
        out.append(s_)
    return out


def _best_shift(combo: List[Dict], p: Params, hub_max: float, seat: float, cache: Dict, fits0: bool,
                margin0: float) -> Tuple[float, List[Dict], float, bool]:
    """
    Automatic profile shift: ONE x for the whole gearbox — all stages share the ring gear, whose tooth spaces
    fit every planet (x_ring = x_planet = -x_sun). The grid within the undercut limits of every sun and planet
    (plus the smallest sun's own undercut limit) is tried and the strongest kept; between results within 2 % the
    one without sun undercut and then the smallest |x| wins (x = 0 unless a shift really helps).
    """
    pa, ha = p.pressure_angle, p.addendum
    # a printed tooth is not generated by a rack, so it has no real undercut: below the limit the root only gets
    # narrower (the ISO form factor with x accounts for it); up to UNDERCUT_SLACK beyond it is allowed
    lo = max([SHIFT_LIMITS[0]] + [undercut_shift(o["zs"], pa, ha) for o in combo])
    hi = min([SHIFT_LIMITS[1]] + [-undercut_shift(o["zp"], pa, ha) for o in combo])
    xs = {x for x in SHIFT_GRID if lo - UNDERCUT_SLACK - 1e-9 <= x <= hi + UNDERCUT_SLACK + 1e-9}
    if 1e-9 < lo <= hi + 1e-9:
        xs.add(round(lo, 3))
    trials = [(0.0, combo, margin0 if (fits0 or p.mode == "MANUAL") else -1.0, fits0)]
    for x in sorted(xs):
        if abs(x) < 1e-9:
            continue
        cx = _shift_combo(combo, p, cache, x)
        if cx is None:
            continue
        f = _combo_fits(cx, p) and _first_stage_bore_ok(cx[0]["geo"], p, cx[0]["bearing"]["pin"])
        if not f and p.mode != "MANUAL":
            continue
        trials.append((x, cx, _evaluate(cx, p, hub_max, seat), f))
    best = max(t[2] for t in trials)
    if best < 0:
        return trials[0]
    floor = best / 1.02 if best < 1.0 else max(1.0, best / 1.02)     # never trade a feasible design away
    near = [t for t in trials if t[2] >= floor]
    clean = [t for t in near if t[0] >= lo - 1e-9] if lo > 1e-9 else near
    return min(clean or near, key=lambda t: abs(t[0]))


def _first_stage_bore_ok(geo: StageGeometry, p: Params, pin_d: float = 0.0) -> bool:
    extent = shaft_extent(p.motor_shaft_dia, p.motor_shaft_type) + 0.05
    if geo.root_sun - extent < max(1.2, 0.8 * rim_min(geo.module, geo.addendum)):
        return False
    # bottom cage plate (one stage with a rotating housing: the fixed base plate) passes over the motor collar
    if (p.cage or (p.ring_out and p.stages == 1)) and pin_d > 0:
        return geo.center_distance - pin_d / 2.0 - 1.0 >= _collar_r(p) + 0.6
    return True


def _stage_design(opt: Dict, stage_index: int, p: Params, star: bool = False) -> StageDesign:
    """
    StageDesign of an option in its position: stage 1 holds the motor shaft; every later sun is printed
    in one piece with the previous carrier (cage or single plate), the neck under its teeth carries the
    torque. A star stage (rotating housing) has a fixed cage carrier.
    """
    sd = replace(opt["design"], star=star, carrier_cage=p.cage or star)
    if stage_index == 0:
        sd.sun_bore_dia, sd.inter_shaft_dia, sd.neck_dia = p.motor_shaft_dia, 0.0, 0.0
    else:
        sd.sun_bore_dia, sd.inter_shaft_dia = 0.0, 0.0
        sd.neck_dia = 2.0 * (opt["geo"].root_sun - NECK_INSET)
    return sd


def _factors(opt: Dict, stage_index: int, p: Params, star: bool = False) -> Dict:
    key = ("factors_first" if stage_index == 0 else "factors_next") + ("_star" if star else "")
    if opt.get(key) is None:
        opt[key] = stage_factors(_stage_design(opt, stage_index, p, star), p.load)
    return opt[key]


def _stage_ratio(opt: Dict, star: bool) -> float:
    return opt["ratio_star"] if star else opt["ratio"]


def _seat_factor(p: Params, hd: Dict) -> float:
    """
    A user-chosen output hub must have its bearing seat in this housing's cover: below 1 when it does not,
    so the automatic sizing grows the housing (a seat wider than the cover cannot be built).
    """
    if p.output_type in ("FLANGE", "ARM") and p.out_hub in BEARING_CATALOG and p.out_hub != "CUSTOM_PIN":
        need = (BEARING_CATALOG[p.out_hub]["d_outer"] + p.bearing_tol) / 2.0
        lim = hd["root_r"] - 0.5
        if need > lim:
            return (max(lim, 1e-3) / need) ** 3
    return 1.0


def _evaluate(combo: List[Dict], p: Params, hub_max: float = 0.0, seat: float = 1.0) -> float:
    torque = p.load.motor_torque * p.load.application_factor
    speed = p.load.motor_speed
    eta = 1.0 if p.reverse else get_material(p.load.gear_material)["eta"]
    margin = float("inf")
    for k, opt in enumerate(combo):
        star = p.ring_out and k == len(combo) - 1
        margin = min(margin, stage_margin(_factors(opt, k, p, star), torque, speed, p.load))
        torque *= _stage_ratio(opt, star) * eta
        speed /= _stage_ratio(opt, star)
    if p.ring_out:                 # the drum is the output member: no hub through a cover bearing
        return min(margin, seat)
    # Çıkış göbeği otomatikse boyutlandırmaya dahil: gövde, gereken göbeği taşıyan rulman sığana kadar büyür
    if hub_max > 0 and p.output_type in ("FLANGE", "ARM") and p.out_hub == "AUTO":
        sm = get_material(p.load.struct_material)
        d_req = required_shaft_dia(torque, torsion_allowable(sm), p.load.target_sf)
        if p.output_type == "ARM":
            d_req = max(d_req, required_key_dia(torque, sm["sigma_S"], p.load.target_sf))
        if p.hub_fastener == "NUT":
            d_req = max(d_req, required_nut_hub_dia(torque, torsion_allowable(sm), p.load.target_sf))
        margin = min(margin, (hub_max / d_req) ** 3)
    if hub_max > 0 and p.output_type in ("SHAFT_PRINTED", "SHAFT_STEEL") and hub_max < p.output_shaft_dia:
        margin = min(margin, (hub_max / p.output_shaft_dia) ** 3)     # no bearing seat for this shaft yet
    return min(margin, seat)


def _pair_can_carry(opts: List[Dict], p: Params) -> bool:
    """
    Quick strength bound of a housing size: some stage option must survive as the LAST (most
    loaded) stage. Its sun torque is T_motor·K_A·(i_total / i_last)·η^(n-1). Skips the many small
    housings of high-torque designs without evaluating their stage combinations.
    """
    n = p.stages
    eta = 1.0 if p.reverse else get_material(p.load.gear_material)["eta"]
    t_in = p.load.motor_torque * p.load.application_factor
    star = p.ring_out
    for o in opts:
        if star and not o.get("star_ok"):
            continue
        before = max(1.0, p.target_ratio / _stage_ratio(o, star))
        if n == 1:
            before = 1.0
        torque = t_in * before * eta ** (n - 1)
        speed = p.load.motor_speed / before
        if stage_margin(_factors(o, n - 1, p, star), torque, speed, p.load) >= 1.0:
            return True
    return False


def _min_carrying_ring(p: Params, module: float, rings: List[int], cache: Dict) -> float:
    """
    Smallest ring tooth count (of `rings`, ascending) whose stage options pass _pair_can_carry; inf if
    none. At a fixed module the capacity grows with the ring (larger sun and planets -> smaller tooth
    force, larger pins and bearings), so the boundary is found by bisection. Two neighbouring rings are
    tried per probe (the planet assembly condition can rule out a single size); a small safety step
    below the boundary keeps slightly non-monotonic cases.
    """
    def carries(i: int) -> bool:
        for j in (i, i + 1):
            if j < len(rings):
                opts = stage_options(module, rings[j], p, cache)
                if opts and _pair_can_carry(opts, p):
                    return True
        return False

    if not rings or not carries(max(0, len(rings) - 2)):
        return float("inf")
    lo, hi = 0, len(rings) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if carries(mid):
            hi = mid
        else:
            lo = mid + 1
    return rings[max(0, lo - 2)]


def _combos(opts: List[Dict], p: Params, target: float, tol: float):
    """Stage combinations (non-increasing ratio) within the ratio tolerance."""
    ratios = [o["ratio"] for o in opts]
    if p.stages == 1:
        for o in opts:
            if abs(o["ratio"] - target) / target <= tol:
                yield [o]
        return
    if p.stages == 2:
        for o1 in opts:
            need = target / o1["ratio"]
            lo = bisect.bisect_left(ratios, need * (1 - tol))
            hi = bisect.bisect_right(ratios, min(need * (1 + tol), o1["ratio"] + 1e-9))
            for o2 in opts[lo:hi]:
                yield [o1, o2]
        return
    for i, o1 in enumerate(opts):
        for o2 in opts[:i + 1]:
            need = target / (o1["ratio"] * o2["ratio"])
            lo = bisect.bisect_left(ratios, need * (1 - tol))
            hi = bisect.bisect_right(ratios, min(need * (1 + tol), o2["ratio"] + 1e-9))
            for o3 in opts[lo:hi]:
                yield [o1, o2, o3]


def _combos_ring(opts: List[Dict], p: Params, target: float, tol: float):
    """
    Combinations of a rotating housing: the last stage is a star stage (i = Zr / Zs, carrier fixed); the
    stages before it keep the non-increasing order of the plain search.
    """
    stars = sorted((o for o in opts if o.get("star_ok") or p.mode == "MANUAL"), key=lambda o: o["ratio_star"])
    sr = [o["ratio_star"] for o in stars]

    def last(need: float):
        return stars[bisect.bisect_left(sr, need * (1 - tol)):bisect.bisect_right(sr, need * (1 + tol))]

    if p.stages == 1:
        for o in last(target):
            yield [o]
        return
    if p.stages == 2:
        for o1 in opts:
            for o2 in last(target / o1["ratio"]):
                yield [o1, o2]
        return
    for i, o1 in enumerate(opts):
        for o2 in opts[:i + 1]:
            for o3 in last(target / (o1["ratio"] * o2["ratio"])):
                yield [o1, o2, o3]


DEEP_COMBO_CAP = 600      # combinations evaluated per housing size with 4-5 stages


def _combos_deep(opts: List[Dict], p: Params, target: float, tol: float, prune: bool = False):
    """
    Any stage count (used for 4-5): ratios non-increasing from the motor to the output (the most loaded
    stage gets the largest sun and the most planets), with a rotating housing the last stage is a star stage.
    A prefix is cut when the remaining stages can no longer reach the ratio window and, while searching for
    strong designs, when one of its stages is already too weak (it stays the same in every completion).
    Balanced combinations come first; at most DEEP_COMBO_CAP per housing size.
    """
    n = p.stages
    ratios = [o["ratio"] for o in opts]
    if not ratios:
        return
    lo, hi = target * (1.0 - tol), target * (1.0 + tol)
    star = p.ring_out
    stars, sr = [], []
    if star:
        stars = sorted((o for o in opts if o.get("star_ok") or p.mode == "MANUAL"), key=lambda o: o["ratio_star"])
        if not stars:
            return
        sr = [o["ratio_star"] for o in stars]
    s_lo, s_hi = (sr[0], sr[-1]) if star else (1.0, 1.0)
    r_min = ratios[0]
    eta = 1.0 if p.reverse else get_material(p.load.gear_material)["eta"]

    def rec(prefix: List[Dict], prod: float, top: int, torque: float, speed: float):
        k = n - len(prefix)                   # stages still to choose, this one included
        if star and k == 1:
            for o in stars[bisect.bisect_left(sr, lo / prod):bisect.bisect_right(sr, hi / prod)]:
                yield prefix + [o]
            return
        if not star and k == 1:
            a = bisect.bisect_left(ratios, lo / prod)
            b = min(bisect.bisect_right(ratios, hi / prod), top + 1)
            for i in range(a, b):
                yield prefix + [opts[i]]
            return
        plain = k - (1 if star else 0)        # plain stages left: this ratio r, then plain-1 below r (+ the star)
        a = bisect.bisect_left(ratios, (lo / (prod * s_hi)) ** (1.0 / plain))
        b = min(top, bisect.bisect_right(ratios, hi / (prod * r_min ** (plain - 1) * s_lo)) - 1)
        for i in range(a, b + 1):
            o = opts[i]
            if prune and stage_margin(_factors(o, len(prefix), p), torque, speed, p.load) < 1.0:
                continue
            r = o["ratio"]
            yield from rec(prefix + [o], prod * r, i, torque * r * eta, speed / r)

    count = 0
    for combo in rec([], 1.0, len(opts) - 1, p.load.motor_torque * p.load.application_factor, p.load.motor_speed):
        yield combo
        count += 1
        if count >= DEEP_COMBO_CAP:
            return


def _stage_combos(opts: List[Dict], p: Params, target: float, tol: float, prune: bool = False):
    if p.stages > 3:
        return _combos_deep(opts, p, target, tol, prune)
    return (_combos_ring if p.ring_out else _combos)(opts, p, target, tol)


def _combo_ratio(combo: List[Dict], p: Params) -> float:
    ratio = 1.0
    for k, o in enumerate(combo):
        ratio *= _stage_ratio(o, p.ring_out and k == len(combo) - 1)
    return ratio


def _combo_fits(combo: List[Dict], p: Params) -> bool:
    if p.ring_out:
        return all(o["fits"] for o in combo[:-1]) and bool(combo[-1].get("star_ok"))
    return all(o["fits"] for o in combo)


def _pairs(p: Params, modules: List[float]) -> List[Tuple[float, float, int]]:
    zmin = z_min(p.pressure_angle)
    out = []
    cap = p.max_od if p.mode == "MAX_OD" else p.od_limit
    for m in modules:
        for zr in range(3 * zmin, 400):
            hd = p.hd(zr, m)
            od = hd["envelope_d"]
            if p.ring_out:
                od = max(od, drum_dims(p, hd)["od"])
            if cap > 0 and od > cap:
                break
            if p.footprint_limit > 0 and p.make_housing and housing_footprint(hd) > p.footprint_limit:
                break
            if od > 600 or (p.mode == "MANUAL" and zr > 200):
                break
            out.append((od, m, zr))
    out.sort()
    return out


STAGE_RATIO_BOUNDS = (2.0, 15.0)   # geometric limits of one stage (3 planets: tips clear only below ~15:1)


def design(payload: Dict, max_results: int = 10, time_budget: float = 2.5, _prune: bool = True,
           _strongest_first: bool = False, hard_budget: Optional[float] = None, _hard_until: float = 0.0) -> Dict:
    """
    Candidate search. `time_budget` keeps the UI responsive; a search that has found nothing yet goes on
    until `hard_budget` (default max(4 x budget, 10 s)) so a slow machine does not report "no solution".
    `stages_count` AUTO and `ratio_from_load` are resolved by _design_auto (one search per stage count).
    """
    arr = str(payload.get("arrangement") or "").upper()
    if arr in SPECIAL_ARRANGEMENTS:                 # Wolfrom / cycloidal: their own search
        lang = "en" if str(payload.get("lang", "tr")).lower().startswith("en") else "tr"
        p = Params.from_payload(payload)
        if arr == "WOLFROM":
            from core import wolfrom
            return wolfrom.candidates(p, payload, lang, max_results, time_budget)
        from core import cycloid
        return cycloid.candidates(p, payload, lang, max_results, time_budget)
    if auto_stage_count(payload) or ratio_from_load_asked(payload):
        return _design_auto(payload, max_results, time_budget, hard_budget)
    return _design_fixed(payload, max_results, time_budget, _prune, _strongest_first, hard_budget, _hard_until)


def _design_fixed(payload: Dict, max_results: int = 10, time_budget: float = 2.5, _prune: bool = True,
                  _strongest_first: bool = False, hard_budget: Optional[float] = None, _hard_until: float = 0.0,
                  _cache: Optional[Dict] = None, _stage_hint: bool = True) -> Dict:
    """The search for one stage count and one target ratio."""
    t0 = time.time()
    p = Params.from_payload(payload)
    prune = _prune and p.mode == "AUTO" and p.strength_required
    lang = "en" if str(payload.get("lang", "tr")).lower().startswith("en") else "tr"
    tol_max = max(0.15, 4.0 * p.ratio_tol)
    lo_r, hi_r = STAGE_RATIO_BOUNDS[0] ** p.stages, STAGE_RATIO_BOUNDS[1] ** p.stages
    if p.ring_out:                     # the star stage gives one less: i = Zr / Zs
        lo_r = STAGE_RATIO_BOUNDS[0] ** (p.stages - 1) * (STAGE_RATIO_BOUNDS[0] - 1.0)
        hi_r = STAGE_RATIO_BOUNDS[1] ** (p.stages - 1) * (STAGE_RATIO_BOUNDS[1] - 1.0)
    if p.target_ratio * (1.0 + tol_max) < lo_r or p.target_ratio / (1.0 + tol_max) > hi_r:
        return {"candidates": [], "relaxed_tolerance": False, "search_pairs": 0, "pruned_pairs": 0,
                "elapsed": round(time.time() - t0, 3), "mode": p.mode,
                "hint": _ratio_hint(p, lang == "en")}
    hard_until = _hard_until or t0 + (hard_budget if hard_budget is not None else max(4.0 * time_budget, 10.0))
    if p.mode == "MANUAL":
        modules = [p.module]
    else:
        m_min = MIN_MODULE.get(p.mfg, 0.5)
        modules = [m for m in STANDARD_MODULES if m >= m_min - 1e-9]
    pairs = _pairs(p, modules)
    cap = p.max_od if p.mode == "MAX_OD" else p.od_limit
    if (p.mode == "MAX_OD" or _strongest_first) and cap > 0:
        pairs.reverse()          # looking for the strongest design within the diameter: largest housings first
    cache: Dict = _cache if _cache is not None else {}
    auto_shift = p.shift_mode == "AUTO"
    found: List[Tuple] = []
    best_od = None
    visited = pruned = 0
    tol = p.ratio_tol
    relaxed = False
    stats = {"no_opts": 0, "unfit": 0, "bore": 0, "combos": 0, "timeout": False}
    ring_sizes: Dict[float, List[int]] = {}
    for _od, m, zr in pairs:
        ring_sizes.setdefault(m, []).append(zr)
    zr_floor: Dict[float, float] = {}
    for attempt in range(2):
        for od, m, zr in pairs:
            now = time.time()
            if now - t0 > time_budget and (found or now > hard_until):
                stats["timeout"] = True
                break
            if p.mode == "AUTO" and best_od is not None:
                n_feasible = sum(1 for f in found if f[0][0] == 0)
                if (n_feasible >= max_results and od > best_od * 1.15) or od > best_od * 1.6:
                    break
            if prune and pruned >= 120 and best_od is None:
                # high-torque request: instead of rejecting the small housings one by one, find the smallest
                # ring of this module that can carry the load (bisection) and skip everything below it
                if m not in zr_floor:
                    zr_floor[m] = _min_carrying_ring(p, m, sorted(ring_sizes[m]), cache)
                if zr < zr_floor[m]:
                    pruned += 1
                    continue
            visited += 1
            opts = stage_options(m, zr, p, cache)
            if not opts:
                stats["no_opts"] += 1
                continue
            if prune and not _pair_can_carry(opts, p):
                pruned += 1
                continue
            hd_pair = p.hd(zr, m)
            hub_max, seat = max_output_hub(p, hd_pair), _seat_factor(p, hd_pair)
            items = []
            for combo in _stage_combos(opts, p, p.target_ratio, tol, prune):
                stats["combos"] += 1
                ratio = _combo_ratio(combo, p)
                err = abs(ratio - p.target_ratio) / p.target_ratio
                parts_fit = _combo_fits(combo, p)
                fits = parts_fit and _first_stage_bore_ok(combo[0]["geo"], p, combo[0]["bearing"]["pin"])
                if not fits and p.mode != "MANUAL" and not (auto_shift and parts_fit):
                    stats["unfit"] += 1
                    continue
                items.append([combo, ratio, err, _evaluate(combo, p, hub_max, seat), fits])
            if auto_shift and items:
                # near misses of this housing (strength, or a motor bore too tight at x = 0): the best common
                # profile shift may carry them (a positive shift thickens the sun, a negative one the planet)
                tries = sorted((it for it in items if (not it[4] or it[3] < 1.0) and it[3] >= SHIFT_TRY_MIN),
                               key=lambda it: -it[3])[:SHIFT_TRIES]
                for it in tries:
                    _x, it[0], it[3], it[4] = _best_shift(it[0], p, hub_max, seat, cache, it[4], it[3])
            for combo, ratio, err, margin, fits in items:
                if not fits and p.mode != "MANUAL":
                    stats["bore"] += 1
                    continue
                feasible = fits and (margin >= 1.0 or not p.strength_required)
                if feasible and best_od is None:
                    best_od = od
                if p.mode == "AUTO":
                    # feasible: smallest housing first; nothing feasible: the closest (strongest) first
                    key = ((0, round(od, 1), round(err, 4), -margin) if feasible
                           else (1, -round(min(margin, 5.0), 2), round(od, 1), round(err, 4)))
                elif p.mode == "MAX_OD":
                    key = (0 if feasible else 1, -round(min(margin, 5.0), 2), round(err, 4), od)
                else:
                    key = (0 if feasible else 1, round(err, 4), od, -margin)
                found.append((key, od, m, zr, combo, ratio, err, margin, fits))
        if found or relaxed:
            break
        tol, relaxed = max(0.15, tol * 4), True

    if prune and pruned and not any(f[0][0] == 0 for f in found):
        # nothing strong enough: show the closest designs as before (without the strength bound)
        rest = max(1.0, time_budget - (time.time() - t0))
        out = _design_fixed(payload, max_results, rest, _prune=False, _strongest_first=True,
                            _hard_until=max(hard_until, time.time() + rest), _cache=cache, _stage_hint=_stage_hint)
        out["pruned_pairs"] = pruned
        return out
    found.sort(key=lambda f: f[0])
    results, seen = [], set()
    for key, od, m, zr, combo, ratio, err, margin, fits in found:
        sig = (m, zr) + tuple((o["zs"], o["bearing"]["code"]) for o in combo)
        if sig in seen:
            continue
        seen.add(sig)
        if auto_shift and all(abs(o.get("x", 0.0)) < 1e-9 for o in combo):
            hd_c = p.hd(zr, m)
            _x, combo, m_x, fits = _best_shift(combo, p, max_output_hub(p, hd_c), _seat_factor(p, hd_c), cache,
                                               fits, margin)
            margin = m_x if fits or p.mode == "MANUAL" else margin
        results.append(_candidate(p, od, m, zr, combo, ratio, err, margin, fits, lang))
        if len(results) >= max_results:
            break
    # feasibility of the candidate also covers length, output member and arm (checked per candidate)
    results.sort(key=lambda c: 0 if c["feasible"] else 1)
    pinned = _pinned_candidate(p, payload.get("pin_stages"), payload.get("pin_module"), lang)
    if pinned:                                 # an applied proposal: its exact tooth set always comes first
        key = _tooth_signature(pinned)
        results = [pinned] + [c for c in results if _tooth_signature(c) != key][:max_results - 1]
    out = {"candidates": results, "relaxed_tolerance": relaxed, "search_pairs": visited, "pruned_pairs": pruned,
           "elapsed": round(time.time() - t0, 3), "mode": p.mode}
    hint = _planet_hint(p, lang) if (not results or relaxed) else None
    if not hint and not results:
        hint = _failure_hint(p, stats, visited, lang)
    if not hint and results and not results[0]["feasible"]:
        hint = _weak_part_hint(p, results[0], lang)
        if hint:
            out["hint_kind"] = "weak_part"
        elif _stage_hint and "strength" in results[0]["issues"] and p.stages < MAX_STAGES and (cap > 0 or p.max_length > 0):
            # a size limit with too few stages: lower stage ratios (larger suns, more planets) may fit
            hint = MORE_STAGES_HINT[lang].format(n=p.stages, m=p.stages + 1)
    if hint:
        out["hint"] = hint
    return out


MORE_STAGES_HINT = {
    "tr": "Bu boyut sınırında {n} kademenin dayanımı yetmiyor: kademe sayısını Otomatik veya {m} yapın (kademe oranı "
          "düşer, güneş büyür, daha çok planet sığar) ya da sınırı gevşetin.",
    "en": "{n} stages are not strong enough within this size limit: set the stage count to Automatic or {m} (lower stage "
          "ratios: larger suns, more planets) or relax the limit.",
}


# ─── Automatic stage count / ratio from the load ──────────────────────────────────────────

STAGE_COST = 1.1                 # a further stage must save > 10 % of the volume (or add > 10 % strength)
AUTO_STAGE_WINDOW = (2.8, 10.0)  # mean stage ratio of the counts searched first
AUTO_STAGE_LIMITS = (2.3, 13.0)  # mean stage ratio still buildable (searched when the window has no design)
AUTO_TIME_FACTOR = 1.6           # automatic count: total time = budget x this, shared by the counts
WINCH_LEVER_EST = 40.0           # mm, rope radius of a typical drum before the drum is designed
LOAD_RATIO_MIN = 3.0

AUTO_TEXT = {
    "tr": {
        "stages": "Otomatik kademe: {n} kademe seçildi",
        "tried": "denenen: {items}",
        "tried_ok": "{n} kademe Ø{od:.0f}×{L:.0f} mm",
        "tried_weak": "{n} kademe yetersiz (S {s:.2f})",
        "tried_none": "{n} kademe kombinasyon yok",
        "why_more": "daha az kademe bu sınırlarda yükü taşımıyor / sığmıyor",
        "why_size": "hacim, verim ve parça sayısı dengesine göre",
        "why_only": "bu oran için uygulanabilir kademe sayısı",
        "none": "Otomatik kademe: 1–{max} kademenin hiçbiri hedefleri sağlamıyor; en yakın tasarım gösteriliyor",
        "ratio": "Oran yükten: {t:.1f} Nm × {res:g} rezerv ÷ ({tm:g} Nm × verim {eta:.2f}) → en az {i:.1f}:1",
        "ratio_winch": " (tambur halat yarıçapı ~{r:.0f} mm)",
        "ratio_none": "Oran yükten hesaplanamadı: yük girilmedi — oran alanındaki {i:g}:1 kullanıldı",
        "ratio_lever": "Oran yükten hesaplanamadı: kuvvet kolu yok (makara / tambur yarıçapı girin) — {i:g}:1 kullanıldı",
        "ratio_high": "Yük için en az ~{i:.0f}:1 gerekiyor; {n} kademeyle en fazla ~{max:.0f}:1 kurulabilir — daha "
                      "güçlü motor, daha kısa kuvvet kolu veya daha hafif yük gerekir",
        "word": "kademe",
    },
    "en": {
        "stages": "Automatic stages: {n} stages chosen",
        "tried": "tried: {items}",
        "tried_ok": "{n} stages Ø{od:.0f}×{L:.0f} mm",
        "tried_weak": "{n} stages too weak (S {s:.2f})",
        "tried_none": "{n} stages no combination",
        "why_more": "fewer stages cannot carry the load / do not fit these limits",
        "why_size": "by volume, efficiency and part count",
        "why_only": "the practical stage count for this ratio",
        "none": "Automatic stages: none of 1–{max} stages meets the targets; the closest design is shown",
        "ratio": "Ratio from the load: {t:.1f} Nm × {res:g} reserve ÷ ({tm:g} Nm × efficiency {eta:.2f}) → at least {i:.1f}:1",
        "ratio_winch": " (drum rope radius ~{r:.0f} mm)",
        "ratio_none": "Ratio from the load not possible: no load given — the {i:g}:1 of the ratio field was used",
        "ratio_lever": "Ratio from the load not possible: no lever arm (enter the pulley / drum radius) — {i:g}:1 was used",
        "ratio_high": "The load needs at least ~{i:.0f}:1; {n} stages give at most ~{max:.0f}:1 — a stronger motor, a "
                      "shorter lever or a lighter load is needed",
        "word": "stages",
    },
}


def ratio_from_load_asked(payload: Dict) -> bool:
    v = payload.get("ratio_from_load")
    on = v is True or str(v).strip().lower() in ("1", "true", "yes", "on")
    return on and str(payload.get("arrangement") or "CARRIER").upper() != "SPEED_UP"


def load_ratio(p: Params, n: int, lever: float = 0.0) -> float:
    """
    Smallest ratio whose nominal output torque T_m·i·η^n keeps the recommended drive reserve over the load
    torque (the `load_drive` check); `lever` stands in for a missing lever arm (winch drum). 0: no load torque.
    """
    torque = p.load_torque if p.load_torque > 0 else p.load_force * lever / 1000.0
    if torque <= 0 or p.load.motor_torque <= 0:
        return 0.0
    kind = get_motor_info(p.motor_code).get("kind", "custom")
    eta = get_material(p.load.gear_material)["eta"]
    return torque * LOAD_RESERVE.get(kind, 1.25) / (p.load.motor_torque * eta ** n)


def _stage_mean(ratio: float, n: int, ring: bool) -> float:
    """Mean stage ratio r of n stages (a rotating housing's last stage gives r - 1)."""
    if not ring or n < 1:
        return ratio ** (1.0 / max(1, n))
    lo, hi = 1.0, 400.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if mid ** (n - 1) * (mid - 1.0) < ratio:
            lo = mid
        else:
            hi = mid
    return lo


def _stage_tag(c: Dict, n: int, lang: str) -> None:
    word = AUTO_TEXT[lang]["word"]
    if f" · {n} {word} · " not in c["label"]:
        c["label"] = c["label"].replace(" · ", f" · {n} {word} · ", 1)


def _design_auto(payload: Dict, max_results: int, time_budget: float, hard_budget: Optional[float]) -> Dict:
    """
    `stages_count` AUTO: one search per stage count whose mean stage ratio is practical (more stages give
    lower stage ratios: larger suns, more planets, a stronger last stage in the same diameter), the best
    feasible design wins by volume (MAX_OD sizing: by strength) with STAGE_COST per stage; counts outside
    the practical window are searched only when the window has no feasible design (e.g. a tight diameter).
    `ratio_from_load`: the target ratio of each count is the smallest one that moves the load with the
    recommended reserve (η^n: a further stage needs a slightly higher ratio).
    """
    t0 = time.time()
    lang = "en" if str(payload.get("lang", "tr")).lower().startswith("en") else "tr"
    T = AUTO_TEXT[lang]
    auto_n, from_load = auto_stage_count(payload), ratio_from_load_asked(payload)
    base = {k: v for k, v in payload.items() if k not in ("stages", "ratio_from_load")}
    p = Params.from_payload(dict(base, stages_count=1))
    fixed_n = None if auto_n else stage_count(base)
    notes: List[str] = []
    lever = 0.0
    if from_load:
        if p.load_value <= 0:
            notes.append(T["ratio_none"].format(i=p.target_ratio))
            from_load = False
        elif p.load_torque <= 0:
            if p.output_type == "DRUM_WINCH" and p.load_force > 0:
                lever = WINCH_LEVER_EST
            else:
                notes.append(T["ratio_lever"].format(i=p.target_ratio))
                from_load = False

    def target(n: int, lev: float) -> float:
        if not from_load:
            return p.target_ratio
        return max(LOAD_RATIO_MIN, load_ratio(p, n, lev) * (1.0 + p.ratio_tol))

    counts = [fixed_n] if fixed_n else list(range(1, MAX_STAGES + 1))
    if auto_n:
        means = {n: _stage_mean(target(n, lever), n, p.ring_out) for n in counts}
        buildable = [n for n in counts if AUTO_STAGE_LIMITS[0] <= means[n] <= AUTO_STAGE_LIMITS[1]]
        first = [n for n in buildable if AUTO_STAGE_WINDOW[0] <= means[n] <= AUTO_STAGE_WINDOW[1]]
        if not first and buildable:          # e.g. a very low ratio: the count closest to the window
            first = [min(buildable, key=lambda n: min(abs(math.log(means[n] / w)) for w in AUTO_STAGE_WINDOW))]
        rest = sorted((n for n in buildable if n not in first),
                      key=lambda n: min(abs(math.log(means[n] / w)) for w in AUTO_STAGE_WINDOW))
        if not buildable:                    # out of reach of every count: the nearest gives the hint
            first = [min(counts, key=lambda n: abs(math.log(means[n] / math.sqrt(AUTO_STAGE_WINDOW[0] *
                                                                                   AUTO_STAGE_WINDOW[1]))))]
    else:
        first, rest = counts, []
    pin = payload.get("pin_stages")
    if pin and auto_n and len(pin) in counts:           # an applied proposal: its count is searched first
        first = [len(pin)] + [n for n in first if n != len(pin)]
        rest = [n for n in rest if n != len(pin)]
    total = max(time_budget, 0.5) * (AUTO_TIME_FACTOR if auto_n and len(first) > 1 else 1.0)
    hard_total = max(total, hard_budget if hard_budget is not None else max(4.0 * time_budget, 10.0))
    cache: Dict = {}
    runs: List[Tuple[int, float, Dict]] = []
    levers: Dict[int, float] = {}

    def feasible_best(out: Dict) -> Optional[Dict]:
        return next((c for c in out["candidates"] if c["feasible"]), None)

    def run(n: int, budget: float) -> None:
        lev = lever
        for step in range(3):
            sub = dict(base, stages_count=n, target_ratio=round(target(n, lev), 4))
            if pin and len(pin) != n:
                sub.pop("pin_stages", None)
            b = budget if step == 0 else max(0.5, budget / 2.0)
            hard = max(b, min(2.0 * b + 1.0, hard_total - (time.time() - t0)))
            out = _design_fixed(sub, max_results, b, hard_budget=hard, _cache=cache, _stage_hint=not auto_n)
            # winch drum without a lever arm: the rope radius is the drum's, which grows with the housing
            # the ratio asks for -> again with the radius found until it settles
            if not (from_load and lever > 0 and out["candidates"]):
                break
            r_act = (feasible_best(out) or out["candidates"][0])["output"].get("load_r", 0.0)
            if r_act <= 0 or abs(r_act - lev) / lev <= 0.06 or step == 2:
                break
            lev = r_act
        levers[len(runs)] = lev
        runs.append((n, target(n, lev), out))

    for idx, n in enumerate(first):
        left = total - (time.time() - t0)
        run(n, max(0.6, left / (len(first) - idx)))
    if not any(feasible_best(o) for _, _, o in runs):
        for n in rest:                       # nothing in the window: tighter limits may need more stages
            if time.time() - t0 > hard_total:
                break
            run(n, max(0.6, time_budget / 2.0))
            if feasible_best(runs[-1][2]):
                break

    def score(n: int, c: Dict) -> float:
        if p.mode == "MAX_OD" or not c["feasible"]:
            return -c["margin"] / STAGE_COST ** n          # strength (nothing feasible: the closest design)
        return c["outer_diameter"] ** 2 * max(c.get("overall_length") or 1.0, 1.0) * STAGE_COST ** n

    scored = [(score(n, b), k) for k, (n, _, o) in enumerate(runs) if (b := feasible_best(o))]
    if scored:
        pick = min(scored)[1]
    else:                                    # nothing feasible: the strongest design, a further stage only for >10 %
        with_c = [(score(n, o["candidates"][0]), k) for k, (n, _, o) in enumerate(runs) if o["candidates"]]
        pick = min(with_c)[1] if with_c else 0
    n_pick, i_pick, out = runs[pick]
    lever = levers.get(pick, lever)
    out = dict(out)
    cands = list(out["candidates"])
    alts = []
    for k, (n, _, o) in enumerate(runs):
        if k == pick or not o["candidates"]:
            continue
        alts.append((n, feasible_best(o) or o["candidates"][0]))
    alts.sort(key=lambda a: (0 if a[1]["feasible"] else 1, score(*a)))
    alts = alts[:2]
    cands = cands[:max(1, max_results - len(alts))]
    if auto_n:
        for c in cands:
            _stage_tag(c, n_pick, lang)
        for n, c in alts:
            _stage_tag(c, n, lang)
    out["candidates"] = cands + [c for _, c in alts]
    # what was chosen and why, in one line
    parts = []
    if from_load:
        kind = get_motor_info(p.motor_code).get("kind", "custom")
        torque = p.load_torque if p.load_torque > 0 else p.load_force * lever / 1000.0
        eta = get_material(p.load.gear_material)["eta"] ** n_pick
        txt = T["ratio"].format(t=torque, res=LOAD_RESERVE.get(kind, 1.25), tm=p.load.motor_torque, eta=eta,
                                i=load_ratio(p, n_pick, lever))
        if lever > 0 and p.load_torque <= 0:
            txt += T["ratio_winch"].format(r=lever)
        parts.append(txt)
        r_top = AUTO_STAGE_LIMITS[1]
        reach = r_top ** (n_pick - 1) * (r_top - 1.0) if p.ring_out else r_top ** n_pick
        if not scored and load_ratio(p, n_pick, lever) > reach:
            parts.append(T["ratio_high"].format(i=load_ratio(p, n_pick, lever), n=n_pick, max=reach))
    if auto_n:
        tried = []
        for n, _, o in sorted(runs, key=lambda r: r[0]):
            b = feasible_best(o)
            if b:
                tried.append(T["tried_ok"].format(n=n, od=b["outer_diameter"], L=b.get("overall_length") or 0))
            elif o["candidates"]:
                tried.append(T["tried_weak"].format(n=n, s=o["candidates"][0]["margin"]))
            else:
                tried.append(T["tried_none"].format(n=n))
        if scored:
            fewer = any(n < n_pick and not feasible_best(o) for n, _, o in runs)
            why = T["why_more"] if fewer else (T["why_size"] if len(runs) > 1 else T["why_only"])
            txt = T["stages"].format(n=n_pick) + " (" + why
            txt += ("; " + T["tried"].format(items=", ".join(tried)) if len(tried) > 1 else "") + ")"
        else:
            txt = T["none"].format(max=MAX_STAGES) + " (" + T["tried"].format(items=", ".join(tried)) + ")"
        parts.append(txt)
    parts += notes
    out["auto"] = {"stages": n_pick, "auto_stages": auto_n, "from_load": from_load, "ratio": round(i_pick, 3),
                   "min_ratio": round(load_ratio(p, n_pick, lever), 3) if from_load else 0.0,
                   "tried": [{"stages": n, "ratio": round(i, 3), "feasible": bool(feasible_best(o)),
                              "candidates": len(o["candidates"])} for n, i, o in runs],
                   "note": " · ".join(parts)}
    out["elapsed"] = round(time.time() - t0, 3)
    return out


def _tooth_signature(c: Dict) -> Tuple:
    return (c["module"], c["z_ring"]) + tuple((s["z_sun"], s["z_planet"]) for s in c["stages"])


def _pinned_candidate(p: Params, stages_in, module, lang: str) -> Optional[Dict]:
    """
    Candidate for an explicit tooth set (a proposal of the requirement solver / AI applied to the form),
    evaluated exactly like the search evaluates its own combinations. The search alone may not list it
    again (time budget, ranking), so applying a proposal would otherwise silently pick another design.
    """
    if not stages_in:
        return None
    try:
        m = float(module or stages_in[0].get("module"))
        zr = int(stages_in[0]["z_ring"])
        x_in = stages_in[0].get("x_sun")
        opts = stage_options(m, zr, p, {}, None if x_in is None else float(x_in))
        combo = []
        for st in stages_in:
            zs, n = int(st["z_sun"]), int(st.get("num_planets") or 0)
            o = next((o for o in opts if o["zs"] == zs and (not n or o["n"] == n)), None)
            if o is None:
                return None
            combo.append(o)
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    ratio = _combo_ratio(combo, p)
    err = abs(ratio - p.target_ratio) / p.target_ratio
    fits = _combo_fits(combo, p) and _first_stage_bore_ok(combo[0]["geo"], p, combo[0]["bearing"]["pin"])
    hd = p.hd(zr, m)
    margin = _evaluate(combo, p, max_output_hub(p, hd), _seat_factor(p, hd))
    od = max(hd["envelope_d"], drum_dims(p, hd)["od"]) if p.ring_out else hd["envelope_d"]
    return _candidate(p, od, m, zr, combo, ratio, err, margin, fits, lang)


def _weak_part_hint(p: Params, c: Dict, lang: str) -> Optional[str]:
    """
    Every candidate fails on a part the search cannot grow because the user fixed it (output shaft
    diameter, output hub, arm section): say which setting to change instead of a list of red designs.
    """
    en = lang == "en"
    lim = (c["engineering"].get("limiting") or {}).get("check", "")
    out = c["output"]
    if lim == "output_shaft_torsion" and p.output_type in ("SHAFT_PRINTED", "SHAFT_STEEL"):
        return (f"The output shaft Ø{out['shaft_d']:g} is too weak for this torque: at least Ø{out['required_d']:.1f} mm "
                f"is needed (output settings)." if en else
                f"Çıkış mili Ø{out['shaft_d']:g} bu tork için zayıf: en az Ø{out['required_d']:.1f} mm gerekli "
                f"(çıkış ayarlarından mil çapını büyütün).")
    if lim in ("output_shaft_torsion", "hub_nut_layer", "arm_key") and p.out_hub != "AUTO":
        sug = out.get("suggest") or "AUTO"
        return (f"The selected output hub ({out['bearing']}, Ø{out['hub_d']:g}) is too weak: choose {sug} or Automatic."
                if en else
                f"Seçilen çıkış göbeği ({out['bearing']}, Ø{out['hub_d']:g}) zayıf: {sug} veya Otomatik seçin.")
    if lim == "arm_bending":
        s = min(x["safety"] / x["target"] for st in c["engineering"]["stages"] for x in st["checks"]
                if x["name"] == "arm_bending")
        return (f"The arm section is too weak (S={s:.2f}): make the arm wider or thicker." if en else
                f"Kol kesiti zayıf (S={s:.2f}): kol genişliğini veya kalınlığını artırın.")
    return None


def _ratio_hint(p: Params, en: bool) -> str:
    lo, hi = 3.0 ** p.stages, 12.0 ** p.stages
    if p.ring_out:
        lo, hi = 3.0 ** (p.stages - 1) * 2.0, 12.0 ** (p.stages - 1) * 11.0
    return (f"{p.target_ratio:g}:1 cannot be reached with {p.stages} stage(s) (about {lo:.0f}-{hi:.0f}:1 "
            f"possible here): change the number of stages." if en else
            f"{p.target_ratio:g}:1 oranı {p.stages} kademeyle elde edilemiyor (yaklaşık {lo:.0f}-{hi:.0f}:1 "
            f"mümkün): kademe sayısını değiştirin.")


def _failure_hint(p: Params, stats: Dict, visited: int, lang: str) -> str:
    """Why the search found nothing, in terms of the settings the user can change."""
    en = lang == "en"
    if visited and stats["no_opts"] == visited:
        b = BEARING_CATALOG.get(p.bearing)
        if b and p.layout == "DUAL" and p.face_width < 2 * b["width"] + WEB_MIN:
            need = 2 * b["width"] + WEB_MIN
            return (f"Two {p.bearing} bearings per planet need a face width of at least {need:g} mm "
                    f"(now {p.face_width:g} mm): widen the gears or use one bearing per planet." if en else
                    f"Planet başına iki {p.bearing} rulman için diş genişliği en az {need:g} mm olmalı "
                    f"(şu an {p.face_width:g} mm): genişliği artırın veya planet başına tek rulman seçin.")
        if b and p.face_width < b["width"] + 1.0:
            need = b["width"] + 1.0
            return (f"The {p.bearing} bearing needs a face width of at least {need:g} mm (now {p.face_width:g} mm)."
                    if en else
                    f"{p.bearing} rulmanı için diş genişliği en az {need:g} mm olmalı (şu an {p.face_width:g} mm).")
        if p.bearing != "AUTO":
            return (f"The selected planet bearing / pin ({p.bearing}) does not fit any planet within the size limit: "
                    f"set the planet bearing to Automatic or allow a larger diameter." if en else
                    f"Seçilen planet rulmanı / pimi ({p.bearing}) boyut sınırı içindeki hiçbir planete sığmıyor: "
                    f"rulmanı Otomatik yapın veya daha büyük çapa izin verin.")
    cap = p.max_od if p.mode == "MAX_OD" else p.od_limit
    if stats["combos"] == 0 and visited and not cap and not stats["timeout"]:
        return _ratio_hint(p, en)
    if stats["bore"] and stats["bore"] >= stats["unfit"]:
        return (f"The motor shaft (Ø{p.motor_shaft_dia:g} {p.motor_shaft_type}) does not fit the first-stage sun: "
                f"allow a larger diameter or a smaller first-stage ratio (more stages)." if en else
                f"Motor mili (Ø{p.motor_shaft_dia:g} {p.motor_shaft_type}) birinci kademe güneşine sığmıyor: daha "
                f"büyük çapa izin verin veya kademe sayısını artırın (ilk kademe oranı düşer).")
    if cap > 0:
        return (f"Nothing fits within Ø{cap:g} mm for these settings: allow a larger diameter." if en else
                f"Bu ayarlarla Ø{cap:g} mm içinde çözüm yok: daha büyük dış çapa izin verin.")
    if stats["timeout"]:
        return ("No combination was found within the search time: relax the ratio tolerance or the size limits."
                if en else
                "Arama süresi içinde uygun kombinasyon bulunamadı: oran toleransını veya boyut sınırlarını gevşetin.")
    return ("No combination fits these settings: change the ratio tolerance, diameter, bearing or material." if en
            else "Bu ayarlarla uygun kombinasyon yok: oran toleransını, çapı, rulmanı veya malzemeyi değiştirin.")


def _planet_hint(p: Params, lang: str) -> Optional[str]:
    """Explain a failed search caused by a fixed planet count that cannot fit the stage ratio."""
    if p.num_planets < 4:
        return None
    i_s = p.target_ratio ** (1.0 / p.stages)
    n_max = max_planets(i_s)
    if p.num_planets <= n_max:
        return None
    if lang == "en":
        return (f"{p.num_planets} planets do not fit at ~{i_s:.1f}:1 per stage (at most {n_max}): set the planet count "
                f"to Automatic or use more stages.")
    return (f"Kademe başına ~{i_s:.1f}:1 oranda {p.num_planets} planet sığmaz (en fazla {n_max}): planet sayısını "
            f"Otomatik yapın veya kademe sayısını artırın.")


def _candidate(p: Params, od: float, m: float, zr: int, combo: List[Dict], ratio: float, err: float,
               margin: float, fits: bool, lang: str) -> Dict:
    hd = p.hd(zr, m)
    stages, designs = [], []
    for k, o in enumerate(combo):
        g: StageGeometry = o["geo"]
        b = o["bearing"]
        star = p.ring_out and k == len(combo) - 1
        sd = _stage_design(o, k, p, star)
        designs.append(sd)
        stages.append({
            "z_sun": o["zs"], "z_planet": o["zp"], "z_ring": zr, "num_planets": o["n"], "module": m,
            "x_sun": round(g.x_sun, 3),
            "ratio": round(_stage_ratio(o, star), 4), "star": star, "bearing": b["code"],
            "bearing_layout": b["layout"],
            "bearings_per_planet": b["n"], "pin_dia": b["pin"], "pocket_dia": b["pocket"],
            "inter_shaft_dia": 0.0, "center_distance": g.center_distance,
            "eps_sun_planet": round(g.eps_sun_planet, 3), "eps_planet_ring": round(g.eps_planet_ring, 3),
            "tip_topped": g.tip_topped_sun or g.tip_topped_planet, "ring_tip_raised": g.tip_raised_ring,
            "addendum": g.addendum, "tip_land": round(min(g.tip_land_sun, g.tip_land_planet), 3),
            "eff_addendum_sun": round(g.effective_addendum()["sun"], 3),
            "eff_addendum_planet": round(g.effective_addendum()["planet"], 3),
            # legacy keys used by the Fusion add-in / old UI
            "coaxiality_ok": True, "assembly_ok": True, "planet_clearance_ok": True,
        })
    if p.ring_out:
        last = combo[-1]
        out_member = drum_member(p, hd, last["geo"], last["bearing"]["pin"], last.get("drum_bearing"))
        stages[-1]["drum_bearing"] = out_member["bearing"]
    else:
        out_member = output_member(p, hd, _output_torque_ka(p, ratio, len(combo)))
    pe = _with_flow(p, ratio, out_member)
    eng = analyze(designs, pe.load, out_member["check_d"], out_member["steel"], lang,
                  arm_spec(pe, out_member["hub_d"]), p.motor_shaft_dia, _nut_dia(p, out_member),
                  app_load_spec(pe, out_member), drum=drum_spec(p, out_member), reverse=p.reverse,
                  mount=mount_spec(p, hd))
    eng["load"] = load_verdict(pe, eng, out_member, ratio, len(combo), lang)
    eng["speedup"] = speedup_info(pe, eng, lang) if p.reverse else None
    # The search ranks by what a larger housing can fix (gears, automatic output hub); the candidate reports
    # every check of the analysis too (a user-fixed output shaft or hub, the arm section): a design whose
    # printed output shaft twists off must not show up as "OK" with the gear safety.
    gear_margin = margin
    margin = min(margin, eng["margin"])
    issues = []
    if not fits:
        issues.append("fit")
    if margin < 1.0:
        issues.append("strength")
    if not out_member["strong"]:
        issues.append("output")
    if not out_member["seat_fits"]:
        issues.append("output_bearing")
    lay = layout_for(p, len(combo), out_member, hd, _output_torque_ka(p, ratio, len(combo)))
    length_ok = p.max_length <= 0 or lay.overall_length <= p.max_length + 1e-6
    if not length_ok:
        issues.append("length")
    env = housing_footprint(hd) if p.make_housing else hd["body_d"]
    if p.ring_out:
        env = max(env, out_member["drum_od"])
    bed_ok = bed_fits(p, env, env, 0.0)
    if not bed_ok:
        issues.append("bed")
    req_out = math.ceil(out_member["required_d"] * 2) / 2.0
    bearings = sorted({s["bearing"] for s in stages})
    if not p.make_housing:
        od = hd["body_d"]                 # ring gear only: no flange lugs
    planets = "/".join(str(o["n"]) for o in combo)
    tag = ""
    if p.ring_out:
        tag = (" · drum " if lang == "en" else " · tambur ") + out_member["bearing"]
    elif p.reverse:
        tag = " · speed-up" if lang == "en" else " · hız artırıcı"
    label = (f"{ratio:.2f}:1 · m{m:g} · Zr{zr} · {planets} planet · Ø{od:.0f}×{lay.overall_length:.0f} mm · "
             f"{'/'.join(bearings)}{tag} · S {min(margin, 9.99):.2f}")
    return {
        "label": label, "total_ratio": round(ratio, 3), "error_percent": round(err * 100, 2), "module": m,
        "z_ring": zr, "outer_diameter": round(od, 1), "housing_diameter": round(hd["body_d"], 1),
        "overall_length": round(lay.overall_length, 1), "body_length": round(lay.body_length, 1),
        "length_ok": length_ok, "bed_ok": bed_ok, "footprint": round(env, 1),
        "tie_rod": hd["tie_rod"], "feasible": fits and margin >= 1.0 and length_ok and out_member["seat_fits"],
        "margin": round(margin, 3), "gear_margin": round(gear_margin, 3),
        "fits": fits, "issues": issues, "required_output_dia": req_out, "output": out_member, "stages": stages,
        "engineering": eng, "load": eng["load"],
    }


# ─── Resolution of a chosen design (used by the CAD assembly and the report) ──────────────

WARN_TEXT = {
    "tr": {
        "bearing_fit": "Kademe {n}: {code} rulmanı (Ø{od:.1f}) planet dişliye sığmıyor (en fazla Ø{lim:.1f}). Otomatik boyutlandırma veya daha küçük rulman seçin.",
        "bearing_axial": "Kademe {n}: {code} rulmanı ({w:.1f} mm) diş genişliğine sığmıyor.",
        "sun_bore": "Kademe 1: motor mili (Ø{want:.2f}) güneş dişliye sığmıyor; delik Ø{got:.2f} mm'ye düşürüldü. Daha büyük güneş seçin.",
        "collar": "Kademe 1: alt taşıyıcı plakası motor bileziğinin üzerinden geçemiyor; pim çevresi et kalınlığı yetersiz.",
        "contact_ratio": "Kademe {n}: temas oranı düşük (εα={eps:.2f}); kavrama gürültülü olabilir.",
        "depth_topped": "Kademe {n}: diş yüksekliği h*a = {ha:.2f} seçildi, ancak uçlar sivrilme / girişim nedeniyle kırpıldı (etkin: güneş {s:.2f}, planet {p:.2f}): ek yüksekliğin bir kısmı kullanılamıyor — katsayıyı düşürün veya daha çok dişli tasarım seçin.",
        "tip_thin": "Kademe {n}: uzun dişlerin uçları {t:.2f} mm inceliğinde (FDM nozülü ~0.4 mm): uçlar eksik veya zayıf basılabilir — katsayıyı düşürün veya modülü büyütün.",
        "boss": "Kademe {n}: taşıyıcı pim boss'u çember dişliye çok yakın.",
        "strength": "Kademe {n}: {label} emniyeti yetersiz (S={s:.2f} < {t:.2f}).",
        "output_hub": "Çıkış göbeği Ø{have:g} burulmada zayıf: en az Ø{req:.1f} mm gerekli → {sug} (Ø{d:g}) göbeğini seçin{fit}.",
        "output_hub_fit": "",
        "output_hub_grow": "; bu rulman bu gövdeye sığmıyor, gövde dış çapı ~Ø{od:.0f} mm olmalı (boyutlandırmayı Otomatik yapın veya maks. çapı büyütün)",
        "output_hub_none": "Çıkış göbeği Ø{have:g} burulmada zayıf: en az Ø{req:.1f} mm gerekli; katalogdaki en büyük göbek bile yetmiyor — gövde/çıkış malzemesini PA-CF/PC yapın veya oranı/tork yükünü azaltın.",
        "output_shaft": "Çıkış mili Ø{have:g} burulmada zayıf: en az Ø{req:.1f} mm gerekli (mil çapını büyütün, çelik mil veya flanş/kol çıkışı seçin).",
        "output_bearing": "Çıkış rulmanı ({code}) kapağa sığmıyor; daha küçük göbek seçin veya otomatik bırakın.",
        "length": "Toplam boy {L:.0f} mm, izin verilen {max:.0f} mm'yi aşıyor: diş genişliğini azaltın veya kademe sayısını düşürün.",
        "motor_shaft": "Motor mili Ø{d:g} bu tork için ince (S={s:.2f}): en az ~Ø{need:.0f} mm mil gerekir — daha kalın milli motor veya çelik kaplin/göbek kullanın.",
        "bed_part": "{name} ({w:.0f}×{d:.0f}×{h:.0f} mm) baskı tablasına ({bx:.0f}×{by:.0f}×{bz:.0f} mm) sığmıyor.",
        "tie_rod_rod": "Gövde boyuna uyan standart cıvata yok: {size} bağlantı için {L:.0f} mm DIN 976 saplama (boyuna kesilir) + üst somun kullanılır.",
        "arm_flat": "Çıkış kolu kökünde eğilme emniyeti düşük (S={s:.2f}): kalınlığı ≥{t:.1f} mm veya genişliği ≥{w:.0f} mm yapın.",
        "arm_round": "Çıkış kolu (yuvarlak) eğilme emniyeti düşük (S={s:.2f}): çapı ≥{w:.1f} mm yapın.",
        "arm_key": "Kolun göbeğe oturduğu düzlükler ezilmeye zayıf (S={s:.2f}): daha büyük çıkış göbeği/rulmanı seçin.",
        "arm_bed": "Çıkış kolu {L:.0f} mm — baskı tablasından ({b:.0f} mm) büyük, çapraz da sığmıyor; kolu parçalı tasarlayın.",
        "arm_bed_diag": "Çıkış kolu {L:.0f} mm: tablaya ({b:.0f} mm) düz sığmaz, çapraz (45°) yerleştirilince sığar — 3MF'te kendi tablasında çapraz durur.",
        "assembly": "Kademe {n}: eşit açılı montaj şartı (Zs+Zr) % N = 0 sağlanmıyor.",
        "coaxial": "Kademe {n}: eş eksenlilik şartı Zr = Zs + 2·Zp sağlanmıyor.",
        "ring_mismatch": "Kademe {n}: çember diş sayısı (Zr={zr}) ortak gövdeden (Zr={zr0}) farklı; ilk kademenin çemberi kullanıldı.",
        "ring_cage": "Kademe {n}: dönen gövde düzeninde bu kademenin taşıyıcısı sabit tabana pimlenir; pimler güneşin geçtiği deliğe çok yakın — daha küçük pim / rulman veya daha büyük gövde seçin.",
        "drum_bearing": "Tambur rulmanı ({code}) sığmıyor: sabit taşıyıcı göbeği pim dairesinin içinde, rulman yuvası ise kapak vidalarının içinde kalmalı — tambur rulmanını Otomatik bırakın veya daha büyük gövdeye izin verin.",
        "face_load": "Kademe {n}: yük diş genişliği boyunca eşit dağılmıyor (K_Hβ = {k:.2f}, pim eğikliği ~{f:.0f} µm) — geniş dişin bir kısmı yük taşımıyor. Daha dar diş + daha büyük modül, daha kalın pim / kafes taşıyıcı veya balıksırtı diş daha verimli.",
        "plate_dowel": "Taşıyıcı plakaları {a:g} → {b:g} mm kalınlaştırıldı: çelik pimler standart boyda tam oturur (kesmek / taşlamak gerekmez), plakalar da güçlenir.",
        "many_stages": "{n} kademe: toplam verim ~%{eta:.0f} (kademe başına ~%{e1:.0f}), redüktör boyu {L:.0f} mm; her ek kademe sürtünme, boşluk ve parça ekler (çıkış boşluğu esas olarak son kademeden gelir).",
        "self_lock": " {i:.0f}:1 oranda çıkış elle neredeyse çevrilemez (pratikte kendini kilitler); motor sürücüsünü ani duruşlara karşı rampalı ayarlayın.",
    },
    "en": {
        "bearing_fit": "Stage {n}: {code} bearing (Ø{od:.1f}) does not fit the planet (max Ø{lim:.1f}). Use automatic sizing or a smaller bearing.",
        "bearing_axial": "Stage {n}: {code} bearing ({w:.1f} mm) does not fit the face width.",
        "sun_bore": "Stage 1: motor shaft (Ø{want:.2f}) does not fit the sun; bore reduced to Ø{got:.2f} mm. Choose a larger sun.",
        "collar": "Stage 1: bottom carrier plate cannot pass over the motor collar; not enough wall around the pins.",
        "contact_ratio": "Stage {n}: low contact ratio (εα={eps:.2f}); the mesh may be noisy.",
        "depth_topped": "Stage {n}: tooth depth h*a = {ha:.2f} was chosen, but the tips had to be topped against pointed tips / interference (effective: sun {s:.2f}, planet {p:.2f}): part of the extra depth is lost — use a lower coefficient or more teeth.",
        "tip_thin": "Stage {n}: the tips of the long teeth are only {t:.2f} mm thick (FDM nozzle ~0.4 mm): they may print incompletely or weak — lower the coefficient or use a larger module.",
        "boss": "Stage {n}: carrier pin boss is very close to the ring gear.",
        "strength": "Stage {n}: {label} safety too low (S={s:.2f} < {t:.2f}).",
        "output_hub": "Output hub Ø{have:g} weak in torsion: at least Ø{req:.1f} mm required → choose the {sug} (Ø{d:g}) hub{fit}.",
        "output_hub_fit": "",
        "output_hub_grow": "; that bearing does not fit this housing, the outer diameter must be ~Ø{od:.0f} mm (use automatic sizing or raise the max. diameter)",
        "output_hub_none": "Output hub Ø{have:g} weak in torsion: at least Ø{req:.1f} mm required; even the largest catalog hub is not enough — use PA-CF/PC for the structure or reduce the ratio / load.",
        "output_shaft": "Output shaft Ø{have:g} weak in torsion: at least Ø{req:.1f} mm required (larger shaft, steel shaft, or flange/arm output).",
        "output_bearing": "Output bearing ({code}) does not fit the cover; choose a smaller hub or leave it automatic.",
        "length": "Overall length {L:.0f} mm exceeds the allowed {max:.0f} mm: reduce the face width or the number of stages.",
        "motor_shaft": "Motor shaft Ø{d:g} too thin for this torque (S={s:.2f}): needs ~Ø{need:.0f} mm — use a motor with a thicker shaft or a steel coupling/hub.",
        "bed_part": "{name} ({w:.0f}×{d:.0f}×{h:.0f} mm) does not fit the print bed ({bx:.0f}×{by:.0f}×{bz:.0f} mm).",
        "tie_rod_rod": "No standard screw length fits this housing: {size} tie rods are {L:.0f} mm DIN 976 threaded rods (cut to length) with top nuts.",
        "arm_flat": "Output arm root bending safety low (S={s:.2f}): make it ≥{t:.1f} mm thick or ≥{w:.0f} mm wide.",
        "arm_round": "Output arm (round) bending safety low (S={s:.2f}): make the diameter ≥{w:.1f} mm.",
        "arm_key": "Arm-to-hub flats weak in bearing pressure (S={s:.2f}): choose a larger output hub/bearing.",
        "arm_bed": "Output arm is {L:.0f} mm — larger than the print bed ({b:.0f} mm), even diagonally; split it.",
        "arm_bed_diag": "Output arm is {L:.0f} mm: it does not fit the bed ({b:.0f} mm) straight but fits at 45° — the 3MF puts it diagonally on its own plate.",
        "assembly": "Stage {n}: equal-spacing condition (Zs+Zr) % N = 0 is not met.",
        "coaxial": "Stage {n}: coaxiality condition Zr = Zs + 2·Zp is not met.",
        "ring_mismatch": "Stage {n}: ring tooth count (Zr={zr}) differs from the shared housing (Zr={zr0}); first stage ring used.",
        "ring_cage": "Stage {n}: with a rotating housing this carrier is pinned to the fixed base plate; the pins are too close to the hole the sun passes through — use a smaller pin / bearing or a larger housing.",
        "drum_bearing": "The drum bearing ({code}) does not fit: the fixed carrier stub must stay inside the pin circle and the bearing pocket inside the lid screws — leave the drum bearing on Automatic or allow a larger housing.",
        "face_load": "Stage {n}: the load is not uniform across the face width (K_Hβ = {k:.2f}, pin misalignment ~{f:.0f} µm) — part of the wide tooth carries nothing. Narrower teeth with a larger module, thicker pins / a cage carrier or herringbone teeth do better.",
        "plate_dowel": "Carrier plates thickened {a:g} → {b:g} mm: the steel pins are a standard length (no cutting / grinding) and the plates get stronger.",
        "many_stages": "{n} stages: overall efficiency ~{eta:.0f} % (~{e1:.0f} % per stage), gearbox length {L:.0f} mm; every extra stage adds friction, backlash and parts (the output backlash comes mainly from the last stage).",
        "self_lock": " At {i:.0f}:1 the output can hardly be turned by hand (practically self-locking); ramp the motor driver against sudden stops.",
    },
}


def resolve(payload: Dict) -> Dict:
    """
    Turn a payload with explicit stages (from `design()` or the legacy UI) into everything the CAD
    assembly and the report need: per-stage geometry, bearings, pins, output member, housing,
    engineering analysis and human readable warnings.
    """
    p = Params.from_payload(payload)
    lang = "en" if str(payload.get("lang", "tr")).lower().startswith("en") else "tr"
    wt = WARN_TEXT[lang]
    warnings: List[str] = []

    def warn(key, **kw):
        text = wt[key].format(**kw)
        if text not in warnings:
            warnings.append(text)

    stages_in = list(payload.get("stages") or [])
    if not stages_in:
        raise ValueError("no stages")
    module = float(stages_in[0].get("module") or payload.get("module") or 1.0)
    z_ring = int(stages_in[0].get("z_ring", 48))
    hd = p.hd(z_ring, module)
    stages, designs = [], []
    for k, st in enumerate(stages_in):
        n = k + 1
        zs, zp, zr = int(st.get("z_sun", 12)), int(st.get("z_planet", 18)), int(st.get("z_ring", z_ring))
        n_pl = int(st.get("num_planets") or p.num_planets or 3)
        if zr != z_ring:
            warn("ring_mismatch", n=n, zr=zr, zr0=z_ring)
            zr, zp = z_ring, (z_ring - zs) // 2
        if zr != zs + 2 * zp:
            warn("coaxial", n=n)
        if (zs + zr) % n_pl:
            warn("assembly", n=n)
        x_in = stages_in[0].get("x_sun")          # one shift for all stages: they share the ring gear
        geo = p.geo(zs, zp, zr, module, None if x_in is None else float(x_in))
        if geo.eps_sun_planet < 1.1 or geo.eps_planet_ring < 1.1:
            warn("contact_ratio", n=n, eps=min(geo.eps_sun_planet, geo.eps_planet_ring))
        if p.addendum > 1.0 + 1e-6:              # long teeth: say when the extra depth is lost or too thin to print
            eff = geo.effective_addendum()
            if min(eff["sun"], eff["planet"]) < p.addendum - 0.05:
                warn("depth_topped", n=n, ha=p.addendum, s=eff["sun"], p=eff["planet"])
            land = min(geo.tip_land_sun, geo.tip_land_planet)
            if p.mfg == "FDM_3D" and land < TIP_LAND_FDM:
                warn("tip_thin", n=n, t=land)
        code = st.get("bearing") or p.bearing
        layout = st.get("bearing_layout")
        if code == "AUTO" or layout is None:
            opts = planet_bearing_options(geo, Params(**{**p.__dict__, "bearing": code}))
            if opts:
                code, layout, n_bear, pin_d = opts[0]["code"], opts[0]["layout"], opts[0]["n"], opts[0]["pin"]
            else:
                code = code if code not in ("AUTO",) else "688ZZ"
                layout = "bushing" if code == "CUSTOM_PIN" else "single"
                n_bear = 0 if code == "CUSTOM_PIN" else 1
                pin_d = p.pin_dia_custom if code == "CUSTOM_PIN" else get_bearing_info(code)["d_inner"]
        else:
            n_bear = int(st.get("bearings_per_planet", 2 if layout == "dual" else (0 if layout == "bushing" else 1)))
            pin_d = float(st.get("pin_dia") or (p.pin_dia_custom if code == "CUSTOM_PIN"
                                                 else get_bearing_info(code)["d_inner"]))
        b = get_bearing_info(code)
        pocket = b["d_outer"] + p.bearing_tol if n_bear > 0 else 0.0
        lim = 2.0 * (geo.root_planet - rim_min(module, p.addendum))
        if n_bear > 0 and pocket > lim + 1e-6:
            warn("bearing_fit", n=n, code=code, od=b["d_outer"], lim=lim)
        if n_bear > 0 and p.face_width < b["width"] + 1.0:
            warn("bearing_axial", n=n, code=code, w=b["width"])
        if geo.center_distance + pin_d / 2.0 + BOSS_WALL > geo.tip_ring - 0.8:
            warn("boss", n=n)
        star = p.ring_out and k == len(stages_in) - 1
        cage_here = p.cage or star                 # a star stage always has a fixed cage carrier
        if k == 0:
            extent = shaft_extent(p.motor_shaft_dia, p.motor_shaft_type) + 0.05
            if geo.root_sun - extent < max(1.2, 0.8 * rim_min(module, p.addendum)):
                got = min(p.motor_shaft_dia, max(1.0, 2.0 * geo.root_sun - 1.5))
                warn("sun_bore", want=p.motor_shaft_dia, got=got)
            if cage_here and geo.center_distance - pin_d / 2.0 - 1.0 < _collar_r(p) + 0.6:
                warn("collar")
        if star and geo.center_distance - pin_d / 2.0 - 1.0 < geo.tip_sun + 0.6:
            warn("ring_cage", n=n)
        sd = StageDesign(geo=geo, num_planets=n_pl, face_width=p.face_width, helix_deg=p.helix,
                         herringbone=p.herringbone, bearing_code=code, bearings_per_planet=n_bear, pin_dia=pin_d,
                         pin_steel=p.pin_steel, carrier_cage=cage_here, plate_t=p.plate_t, clearance=CLEARANCE,
                         sun_bore_dia=p.motor_shaft_dia if k == 0 else 0.0, inter_shaft_dia=0.0,
                         neck_dia=0.0 if k == 0 else 2.0 * (geo.root_sun - NECK_INSET), star=star,
                         mfg_error=MFG_ERROR.get(p.mfg, 0.02))
        designs.append(sd)
        stages.append({"index": n, "geo": geo, "z_sun": zs, "z_planet": zp, "z_ring": zr, "num_planets": n_pl,
                       "x_sun": geo.x_sun,
                       "ratio": sd.ratio, "star": star, "bearing": code, "bearing_info": b, "layout": layout,
                       "bearings_per_planet": n_bear, "pin_dia": pin_d, "pocket_dia": pocket,
                       "inner_race_d": inner_race_diameter(b) if n_bear > 0 else pin_d,
                       "inter_shaft_dia": 0.0, "drum_bearing": st.get("drum_bearing"), "design": sd})
    ratio = 1.0
    for s_ in stages:
        ratio *= s_["ratio"]
    if p.ring_out:
        last = stages[-1]
        fit = drum_bearing_options(p, last["geo"], _pin_hole(p, last["pin_dia"]), drum_dims(p, hd))
        code = last.get("drum_bearing")
        if code not in fit:      # no / stale choice: the best that fits; a user-fixed bearing that does not fit
            code = None if (p.out_hub in BEARING_CATALOG and p.out_hub != "CUSTOM_PIN") else (fit[0] if fit else None)
        out = drum_member(p, hd, last["geo"], last["pin_dia"], code)
        last["drum_bearing"] = out["bearing"]
        if not out["seat_fits"]:
            warn("drum_bearing", code=p.out_hub if p.out_hub in BEARING_CATALOG else out["bearing"])
    else:
        out = output_member(p, hd, _output_torque_ka(p, ratio, len(stages)))
    pe = _with_flow(p, ratio, out)
    arm = arm_spec(pe, out["hub_d"])
    eng = analyze(designs, pe.load, out["check_d"], out["steel"], lang, arm, p.motor_shaft_dia, _nut_dia(p, out),
                  app_load_spec(pe, out), drum=drum_spec(p, out), reverse=p.reverse,
                  mount=mount_spec(p, hd))
    eng["load"] = load_verdict(pe, eng, out, ratio, len(stages), lang)
    eng["speedup"] = speedup_info(pe, eng, lang) if p.reverse else None
    if eng["speedup"]:
        for note in eng["speedup"]["notes"]:
            if note not in warnings:
                warnings.append(note)
    for s_eng in eng["stages"]:
        gear = [c["safety"] / c["target"] for c in s_eng["checks"] if c["name"].startswith(("bend_", "contact_"))]
        if s_eng.get("k_hbeta", 1.0) >= FACE_LOAD_WARN and gear and min(gear) < 1.5:
            # only where the teeth are loaded: a lightly loaded stage shows a high factor without consequence
            warn("face_load", n=s_eng["index"], k=s_eng["k_hbeta"], f=s_eng["misalignment_um"])
        for c in s_eng["checks"]:
            if c["ok"]:
                continue
            if c["name"] == "arm_bending":
                factor = c["target"] / max(c["safety"], 1e-6)
                if p.arm_shape == "ROUND":
                    warn("arm_round", s=c["safety"], w=p.arm_width * factor ** (1 / 3.0))
                else:
                    warn("arm_flat", s=c["safety"], t=p.arm_thickness * factor, w=p.arm_width * factor ** 0.5)
            elif c["name"] == "arm_key":
                warn("arm_key", s=c["safety"])
            elif c["name"].startswith("load_"):
                continue                               # application load: one plain-language verdict below
            elif c["name"] == "motor_shaft_torsion":
                d_need = p.motor_shaft_dia * (c["target"] / max(c["safety"], 1e-6)) ** (1 / 3.0)
                warn("motor_shaft", d=p.motor_shaft_dia, s=c["safety"], need=d_need)
            elif c["name"] != "output_shaft_torsion":
                warn("strength", n=s_eng["index"], label=c["label"], s=c["safety"], t=c["target"])
    if arm:
        boss_r = (drum_arm_hub_r(out) if out.get("drum") else
                  out["hub_d"] / 2.0 + max(6.0, 0.25 * out["hub_d"]))
        arm_extent = p.arm_length + p.arm_width / 2.0 + boss_r
        arm_w = max(p.arm_width, 2.0 * boss_r)
        bx, by = max(p.bed[0], p.bed[1]), min(p.bed[0], p.bed[1])
        if not (arm_extent <= bx + 1e-6 and arm_w <= by + 1e-6):
            # diagonally the arm is a hub circle and a rounded tip: both circles inside the square of the short
            # side -> axis length L <= sqrt(2) (b - r_hub - r_tip) (the 3MF places such a part at 45 deg)
            if p.arm_length <= math.sqrt(2.0) * (by - boss_r - p.arm_width / 2.0) + 1e-6:
                warn("arm_bed_diag", L=arm_extent, b=by)
            else:
                warn("arm_bed", L=arm_extent, b=max(p.bed[0], p.bed[1]))
    if not out["strong"]:
        if out["type"] in ("FLANGE", "ARM"):
            if out.get("suggest"):
                d_s = get_bearing_info(out["suggest"])["d_inner"]
                fit = wt["output_hub_fit"] if out["suggest_fits"] else wt["output_hub_grow"].format(od=out["suggest_od"])
                warn("output_hub", have=out["hub_d"], req=out["required_d"], sug=out["suggest"], d=d_s, fit=fit)
            else:
                warn("output_hub_none", have=out["hub_d"], req=out["required_d"])
        else:
            warn("output_shaft", have=out["shaft_d"], req=out["required_d"])
    if not out["seat_fits"]:
        warn("output_bearing", code=out["bearing"])
    if eng.get("load") and eng["load"]["status"] != "ok" and eng["load"]["text"] not in warnings:
        warnings.append(eng["load"]["text"])
    lay = layout_for(p, len(stages), out, hd, _output_torque_ka(p, ratio, len(stages)))
    if p.max_length > 0 and lay.overall_length > p.max_length + 1e-6:
        warn("length", L=lay.overall_length, max=p.max_length)
    if p.make_housing and lay.threaded_rod:
        warn("tie_rod_rod", size=hd["tie_rod"], L=lay.bolt_len)
    if p.plate_t_asked and p.plate_t > p.plate_t_asked + 1e-6:
        warn("plate_dowel", a=p.plate_t_asked, b=p.plate_t)
    if len(stages) >= 4:
        e1 = 1.0 if p.reverse else get_material(p.load.gear_material)["eta"]
        text = wt["many_stages"].format(n=len(stages), eta=100.0 * e1 ** len(stages), e1=100.0 * e1,
                                        L=lay.overall_length)
        if ratio >= 500.0 and not p.reverse:
            text += wt["self_lock"].format(i=ratio)
        warnings.append(text)
    return {"params": p, "lang": lang, "module": module, "z_ring": z_ring, "housing": hd, "stages": stages,
            "output": out, "engineering": eng, "total_ratio": ratio, "warnings": warnings, "layout": lay,
            "warn_text": wt}
