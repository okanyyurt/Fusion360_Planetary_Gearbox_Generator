"""
Axial layout of the gearbox: one source for the design engine (overall length limit, candidate
length) and the CAD assembly (part positions).

z = 0 is the top face of the motor flange (bottom of the ring housing). Per stage, bottom up:
    cage carrier:    clearance | bottom plate | clearance | planet (face width) | clearance | top plate
    single carrier:  pin tail  | planet | clearance | carrier plate
The cover with the output bearing closes the housing; the output member protrudes above it.
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from core.engineering import arm_key_height
from core.hardware import tie_rod_choice

PIN_TAIL = 2.5             # single-plate carrier: pin length below the planet (circlip zone)
COLLAR_LEN = 7.0           # first sun: set-screw collar on the motor shaft, below the gear
ARM_GAP = 1.0              # gap between the output arm and the cover
ARM_SCREW_HEAD_DEPTH = 3.4  # counterbore of the M3 arm screws
FLANGE_PROTRUSION = 5.0    # output flange hub above the cover (heat-set inserts)
FLANGE_PROTRUSION_NUT = 7.0  # with side-loaded M3 nut pockets: 1 mm above the cover + pocket + 2.5 mm roof


def bottom_plate_thickness(plate_t: float) -> float:
    return max(2.5, round(0.75 * plate_t * 2.0) / 2.0)


def arm_boss_height(key_h: float, shape: str = "FLAT", width: float = 0.0, thickness: float = 0.0) -> float:
    """Arm hub height: pocket for the double-D lock + screw counterbore + >= 3 mm floor; never below the bar."""
    tb = key_h + 0.4 + ARM_SCREW_HEAD_DEPTH + 3.0
    if shape == "ROUND":
        return max(tb, 0.96 * width)          # rod centre at 0.46·d, flat on the bed
    return max(tb, thickness)


@dataclass
class AxialLayout:
    z_planets: List[float]
    carrier_tops: List[float]
    housing_len: float
    cover_t: float
    flange_t: float
    nut_z: float
    z_cover_top: float
    bolt_len: float
    counterbore: float
    output_protrusion: float
    overall_length: float          # motor flange bottom -> top of the output member
    body_length: float             # motor flange bottom -> cover top
    extra: Dict = field(default_factory=dict)
    arm_gap: float = ARM_GAP       # cover top -> underside of the output arm (clears the tie-rod heads / nuts)
    threaded_rod: bool = False     # tie rods are cut DIN 976 rods with top nuts (no standard screw fits)
    fastener_top: float = 0.0      # highest stationary fastener (bolt head, rod end) above the cover
    flange_nut_z: float = 0.0      # nut slots of the motor flange (the nuts sit lower when a bracket is mounted)
    mount_t: float = 0.0           # mounting bracket shelf under the motor flange (0 = none)


def mount_shelf_t(tie: Dict) -> float:
    """Bracket shelf under the motor flange: hex nut pocket open from below (nut + 3 mm) and 2 mm above the nut."""
    return max(8.0, tie["nut_m"] + 5.0)


MOUNT_TYPES = ("SIDE", "BASE", "PANEL")


def mount_window(flange_t: float, tie: Dict, mount: bool) -> Tuple[float, float, float, float]:
    """
    (nut z, lowest tie-rod tip, highest tip, bracket shelf thickness). Without a bracket the nuts sit in the side
    slots of the motor flange; with one the tie rods run on through the shelf into nuts in pockets open from below
    (3 mm under the nut), so the reaction torque goes straight into the bracket. Same for every arrangement.
    """
    nut_z = -flange_t + 1.8
    if not mount:
        return nut_z, -flange_t + 0.6, nut_z - 0.6, 0.0
    mt = mount_shelf_t(tie)
    z0 = -flange_t - mt
    return z0 + 3.0 - 0.15, z0 + 0.3, z0 + 3.0 - 0.7, mt


DECLUTCH_GAP = 0.3         # running gaps of the free arm on the collar (shoulder, cap)
DECLUTCH_CAP = 2.5         # cap washer on the collar, clamped by the hub screws, keeps the arm on
DECLUTCH_HEAD = 3.0        # M3 screw heads on the cap


def declutch_layout(shape: str, width: float, thickness: float, plunger: Dict) -> Dict:
    """
    Heights of a declutchable arm above its base (= the face it is screwed to): collar shoulder [0, t_s] with the
    blind hole of the index plunger pin, free arm ring [z_arm, z_arm + h_a] around the collar neck, cap washer
    [z_sp, z_cap] on the neck, screw heads above. The index plunger's thread ends flush with the arm underside (thin
    nut in a pocket there), its lock nut sits on the arm (local_top: counterbored where the arm is thicker), its knob
    sticks out above — raised by the pin stroke in the rest position.
    """
    bar = 0.96 * width if shape == "ROUND" else thickness
    h_a = max(bar, 12.0, plunger["m"] + 3.5)             # thin nut pocket + >= 3 mm of clamped arm
    t_s = max(12.0, plunger["l2"] + 3.0)
    z_arm = t_s + DECLUTCH_GAP
    z_sp = z_arm + h_a + DECLUTCH_GAP
    z_cap = z_sp + DECLUTCH_CAP
    knob_top = z_arm + plunger["l1"] + plunger["knob_h"] + plunger["l2"]
    return {"t_s": t_s, "h_a": h_a, "z_arm": z_arm, "z_sp": z_sp, "z_cap": z_cap,
            "local_top": min(h_a, plunger["l1"] - plunger["m_lock"]), "height": max(z_cap + DECLUTCH_HEAD, knob_top)}


def output_protrusion(output_type: str, shaft_len: float = 20.0, hub_d: float = 0.0, arm: Dict = None,
                      fastener: str = "NUT") -> float:
    if output_type == "FLANGE":
        return FLANGE_PROTRUSION if fastener == "INSERT" else FLANGE_PROTRUSION_NUT
    if output_type == "ARM":
        arm = arm or {}
        if arm.get("declutch_height"):
            return ARM_GAP + arm["declutch_height"]
        return ARM_GAP + arm_boss_height(arm_key_height(hub_d), arm.get("shape", "FLAT"),
                                         arm.get("width", 0.0), arm.get("thickness", 0.0))
    if output_type == "SHAFT_STEEL":
        return shaft_len
    return shaft_len


DRUM_GAP = 0.5             # turning drum above the fixed base plate
DRUM_ARM_FLOOR = 3.0       # arm hub below the screw head counterbores


def drum_arm_height(shape: str, width: float, thickness: float) -> float:
    """Hub of an arm bolted onto the drum lid: screw head counterbore + floor; never below the bar."""
    tb = ARM_SCREW_HEAD_DEPTH + DRUM_ARM_FLOOR
    if shape == "ROUND":
        return max(tb, 0.96 * width)
    return max(tb, thickness)


def ring_layout(n_stages: int, face_width: float, plate_t: float, clearance: float, cage: bool, motor: Dict,
                tie: Dict, lid_t: float, protrusion: float, mount: bool = False) -> AxialLayout:
    """
    Rotating housing (ring output). Bottom up: motor flange | fixed ring housing of stages 1..n-1 (the
    usual stacking) | fixed base plate = bottom of the last, fixed carrier (pins pressed in, tie rods
    clamp it to the flange with their heads sunk, the drum turns right above them) | last stage planets |
    fixed top plate with the drum bearing stub | drum lid (bearing pocket, output face).
    The drum (ring gear of the last stage + lid) reaches from just above the base plate to the lid top.
    """
    clr, fw, t_top = clearance, face_width, plate_t
    t_bot = bottom_plate_thickness(plate_t)
    z_planets = []
    z = (clr + t_bot + clr) if cage else (clr + PIN_TAIL)
    for _ in range(n_stages - 1):
        z_planets.append(z)
        zt = z + fw + clr + t_top
        z = zt + ((2 * clr + t_bot) if cage else (clr + PIN_TAIL))
    carrier_tops = [zk + fw + clr + t_top for zk in z_planets]
    housing_len = carrier_tops[-1] + clr if z_planets else 0.0
    head_h = float(motor.get("screw_head_h", 3.0))
    flange_t = max(5.0, float(motor.get("pilot_depth", 0.0)) + 2.5, head_h + 2.0, tie["nut_m"] + 2.9)
    nut_z, tip_lo, tip_hi, mount_t = mount_window(flange_t, tie, mount)
    # the base plate grows until a standard screw sinks its head fully (the standard length steps are
    # absorbed by the counterbore depth between head height and base thickness - 2 mm)
    c_min = tie["head_h"] + 0.3
    base_t = max(6.0, c_min + 2.0)
    bolt_len, counterbore, rod = tie_rod_choice(housing_len + base_t, tip_lo, tip_hi, base_t - 2.0,
                                                tie["nut_m"], c_min)
    while rod and base_t < 24.0:
        base_t += 0.5
        bolt_len, counterbore, rod = tie_rod_choice(housing_len + base_t, tip_lo, tip_hi, base_t - 2.0,
                                                    tie["nut_m"], c_min)
    if rod:   # taller than any standard screw: a rod cut to length, its top nut sunk in a socket pocket
        base_t = max(base_t, tie["nut_m"] + 1.8 + 2.0)
        counterbore = round(tie["nut_m"] + 1.8, 2)
        bolt_len = math.floor(((housing_len + base_t - 0.5) - (tip_lo + tip_hi) / 2.0) * 2.0) / 2.0
    z_base1 = housing_len + base_t
    z_pn = z_base1 + clr
    z_planets.append(z_pn)
    z_tp1 = z_pn + fw + clr + t_top
    carrier_tops.append(z_tp1)
    z_lu = z_tp1 + clr
    z_lt = z_lu + lid_t
    return AxialLayout(z_planets=z_planets, carrier_tops=carrier_tops, housing_len=housing_len, cover_t=base_t,
                       flange_t=flange_t, nut_z=nut_z, z_cover_top=z_base1, bolt_len=bolt_len,
                       counterbore=counterbore, output_protrusion=protrusion,
                       overall_length=z_lt + protrusion + flange_t, body_length=z_lt + flange_t,
                       extra={"ring": True, "base_t": base_t, "z_base0": housing_len, "z_base1": z_base1,
                              "z_lid0": z_lu, "z_lid1": z_lt, "drum_z0": z_base1 + DRUM_GAP,
                              "z_shoulder": z_tp1 + clr},
                       threaded_rod=rod, fastener_top=0.0, flange_nut_z=-flange_t + 1.8, mount_t=mount_t)


def axial_layout(n_stages: int, face_width: float, plate_t: float, clearance: float, cage: bool,
                 out_bearing_width: float, motor: Dict, tie: Dict, protrusion: float,
                 with_housing: bool = True, output_type: str = "", mount: bool = False) -> AxialLayout:
    clr, fw, t_top = clearance, face_width, plate_t
    t_bot = bottom_plate_thickness(plate_t)
    z_planets = []
    z = (clr + t_bot + clr) if cage else (clr + PIN_TAIL)
    for _ in range(n_stages):
        z_planets.append(z)
        zt = z + fw + clr + t_top
        z = zt + ((2 * clr + t_bot) if cage else (clr + PIN_TAIL))
    carrier_tops = [zk + fw + clr + t_top for zk in z_planets]
    housing_len = carrier_tops[-1] + clr
    cover_t = max(6.0, out_bearing_width + 1.5)
    head_h = float(motor.get("screw_head_h", 3.0))
    flange_t = max(5.0, float(motor.get("pilot_depth", 0.0)) + 2.5, head_h + 2.0, tie["nut_m"] + 2.9)
    flange_nut_z = -flange_t + 1.8
    z_cover_top = housing_len + cover_t
    nut_z, tip_lo, tip_hi, mount_t = mount_window(flange_t, tie, mount and with_housing)
    bolt_len, counterbore, rod = tie_rod_choice(z_cover_top, tip_lo, tip_hi, cover_t - 2.0, tie["nut_m"])
    # without the housing nothing covers the sun's motor collar: it is the lowest point
    base = flange_t if with_housing else max(0.0, COLLAR_LEN - z_planets[0])
    # The rotating output must pass over the stationary tie-rod ends: a bolt head that the counterbore cannot
    # sink, or the top nut + rod end of a long housing. Arm and flange face keep 1 mm above them.
    above = 0.0
    if with_housing:                          # rod: its bottom end sits mid nut window (as the assembly places it)
        above = ((tip_lo + tip_hi) / 2.0 + bolt_len - z_cover_top) if rod else max(0.0, tie["head_h"] - counterbore)
    arm_gap = ARM_GAP
    if output_type == "ARM":
        arm_gap = max(ARM_GAP, round(above + 1.0, 2))
        protrusion += arm_gap - ARM_GAP
    elif output_type == "FLANGE":
        protrusion = max(protrusion, round(above + 1.0, 2))
    return AxialLayout(z_planets=z_planets, carrier_tops=carrier_tops, housing_len=housing_len, cover_t=cover_t,
                       flange_t=flange_t, nut_z=nut_z, z_cover_top=z_cover_top, bolt_len=bolt_len,
                       counterbore=counterbore, output_protrusion=protrusion,
                       overall_length=z_cover_top + protrusion + base, body_length=z_cover_top + base,
                       arm_gap=arm_gap, fastener_top=above, threaded_rod=rod, flange_nut_z=flange_nut_z,
                       mount_t=mount_t)
