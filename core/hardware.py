"""
Standard hardware selection: dowel pins (ISO 8734 / DIN 6325), socket head cap screws (ISO 4762),
nuts (ISO 4032) and the matching printed features (counterbores, nut slots).
"""
import math
from typing import Dict, Optional, Tuple

DOWEL_LENGTHS = [4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 35, 40, 45, 50, 55, 60, 70, 80,
                 90, 100, 120]
BOLT_LENGTHS = [6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 90, 100, 110,
                120, 130, 140, 150, 160, 180, 200]
SETSCREW_LENGTHS = [3, 4, 5, 6, 8, 10, 12]
ROD_STEP = 5.0      # DIN 976 threaded rod, cut to length (housings taller than the longest standard screw)


def is_threaded_rod(length: float) -> bool:
    return length > BOLT_LENGTHS[-1] + 1e-6


def pick_dowel(need: float, min_engagement_loss: float, max_protrusion: float = 0.0,
               max_loss: float = -1.0) -> float:
    """
    Pin spanning both carrier plates (`need` = plate to plate). A pin must never reach into the gap to the next
    carrier, which turns at another speed (it would rub on it): at most `max_protrusion` beyond the plates.
    Prefer the longest standard length within [need - min_engagement_loss, need + max_protrusion]; otherwise a
    shorter one that still keeps the pin in the plate (down to need - max_loss, default 1.5 x the preferred loss);
    otherwise `need` itself (a pin cut to length).
    """
    fitting = [L for L in DOWEL_LENGTHS if need - min_engagement_loss <= L <= need + max_protrusion + 1e-6]
    if fitting:
        return float(max(fitting))
    loss = max_loss if max_loss >= 0 else 1.5 * min_engagement_loss
    shorter = [L for L in DOWEL_LENGTHS if need - loss <= L <= need + max_protrusion + 1e-6]
    if shorter:
        return float(max(shorter))
    return round(need - 0.2, 1)


def dowel_is_standard(length: float) -> bool:
    return any(abs(length - L) < 1e-6 for L in DOWEL_LENGTHS)


def tie_rod_choice(z_cover_top: float, tip_lo: float, tip_hi: float,
                   counterbore_max: float, nut_h: float = 0.0,
                   counterbore_min: float = 0.0) -> Tuple[float, float, bool]:
    """
    Tie-rod screw from the cover top into a captive nut in the motor flange.
    The tip must end between tip_lo (not through the flange bottom) and tip_hi (fully through
    the nut + 1 thread). The cover counterbore depth c in [counterbore_min, counterbore_max] absorbs the
    standard length step (counterbore_min > 0: the head must sink below the face, e.g. under a turning
    drum). Returns (length, counterbore depth, threaded rod?).
    When no standard screw fits (taller than the longest one, or the cover cannot absorb the step
    between two long standard lengths): a DIN 976 threaded rod cut to length, with a nut on the
    cover (no counterbore) and one thread protruding above that nut.
    """
    for L in BOLT_LENGTHS:
        c_lo = max(counterbore_min, z_cover_top - L - tip_hi)
        c_hi = min(counterbore_max, z_cover_top - L - tip_lo)
        if c_lo <= c_hi + 1e-9:
            return float(L), round(c_lo, 2), False
    top = z_cover_top + nut_h + 1.5            # bottom tip stays in the nut window, the top end may stick out more
    span = top - (tip_lo + tip_hi) / 2.0
    return float(ROD_STEP * math.ceil(span / ROD_STEP - 1e-9)), 0.0, True


def pick_tie_bolt(z_cover_top: float, tip_lo: float, tip_hi: float,
                  counterbore_max: float, nut_h: float = 0.0) -> Tuple[float, float]:
    """(length, counterbore depth) of tie_rod_choice."""
    L, c, _rod = tie_rod_choice(z_cover_top, tip_lo, tip_hi, counterbore_max, nut_h)
    return L, c


def pick_setscrew(wall: float) -> float:
    ok = [L for L in SETSCREW_LENGTHS if L <= wall + 1.0]
    return float(max(ok)) if ok else float(SETSCREW_LENGTHS[0])


def pick_motor_screw(through: float, thread_depth: float = 4.0) -> float:
    ok = [L for L in BOLT_LENGTHS if L <= through + thread_depth]
    return float(max(ok)) if ok else float(BOLT_LENGTHS[0])


# Spring index plungers with rest position and lock nut (Ganter GN 617.1-...-AK or equivalent): pin d1, thread M
# (d2), thread length l1, pin protrusion l2 beyond the thread end, thin nut ISO 8675 (m, across flats s), lock nut
# height m_lock, knob diameter / height above the thread. Nominal catalogue values — check them against the supplier.
INDEX_PLUNGERS = {
    5.0: {"d1": 5.0, "thread": "M10x1", "d2": 10.0, "l1": 15.0, "l2": 6.0, "m": 5.0, "s": 16.0, "m_lock": 5.0,
          "knob_d": 21.0, "knob_h": 22.0},
    6.0: {"d1": 6.0, "thread": "M12x1.5", "d2": 12.0, "l1": 18.0, "l2": 8.0, "m": 6.0, "s": 18.0, "m_lock": 6.0,
          "knob_d": 25.0, "knob_h": 26.0},
    8.0: {"d1": 8.0, "thread": "M16x1.5", "d2": 16.0, "l1": 22.0, "l2": 10.0, "m": 8.0, "s": 24.0, "m_lock": 8.0,
          "knob_d": 31.0, "knob_h": 32.0},
    10.0: {"d1": 10.0, "thread": "M20x1.5", "d2": 20.0, "l1": 25.0, "l2": 12.0, "m": 10.0, "s": 30.0, "m_lock": 10.0,
           "knob_d": 35.0, "knob_h": 38.0},
}


def plunger_code(pl: Dict) -> str:
    return f"GN 617.1-{pl['d1']:g}-{pl['thread']}-AK"
