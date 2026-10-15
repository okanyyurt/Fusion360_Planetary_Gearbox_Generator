"""
Planetary stage involute geometry: radii, interference-free tip limits, active-profile (form)
radii and transverse contact ratios. All lengths in mm.

Conventions (same as core/tooth_profile.py), h_a* = addendum (tooth depth) coefficient, 1.0 = standard:
  external gears: addendum h_a* m, dedendum (h_a* + 0.157) m
  internal ring : tip (inner) radius r - h_a* m, root radius r + (h_a* + 0.25) m
  backlash      : total circumferential backlash of one mesh, shared equally by both gears
The bottom clearance (0.157 m / 0.25 m) stays the same for every h_a*: stub teeth (h_a* < 1) are shorter
on both sides of the pitch circle, long teeth (h_a* > 1) taller.

Involute interference (ISO 21771 terminology):
  * sun <-> planet (external pair): a tip may not contact the mating flank below its base
    circle. With line-of-action segment T1T2 = a*sin(alpha):
        sqrt(ra_planet^2 - rb_planet^2) <= a*sin(alpha)   (else planet tip digs into sun root)
        sqrt(ra_sun^2    - rb_sun^2)    <= a*sin(alpha)
  * planet <-> ring (internal pair): the ring tip must stay outside the planet's interference
    point:   sqrt(ra_ring^2 - rb_ring^2) >= a*sin(alpha)
Violations are removed by topping the external tips / raising the ring tip (addendum
correction), which keeps the coaxial tooth counts unchanged.

Profile shift (V-zero / height correction, ISO 21771): the sun gets +x, the planet and the ring -x.
Every center distance stays standard (x_sun + x_planet = 0, x_ring - x_planet = 0), so the tooth counts,
planet phasing and kinematics do not change; only the tooth thicknesses and the tip / root circles move:
  external gear: tip r + (h_a* + x) m, root r - (h_a* + 0.157 - x) m, thickness m (pi/2 + 2 x tan alpha)
  internal ring: tip r - (h_a* - x) m, root r + (h_a* + 0.25 + x) m, space width m (pi/2 + 2 x tan alpha)
(x_ring = x_planet: the ring space fits the shifted planet tooth.) A positive sun shift removes the undercut of a
small sun and thickens its root; the planet (and the ring tooth space) gets thinner by the same amount.
"""
import math
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Dict

EXT_CLEARANCE = 0.157           # bottom clearance / module (external gears)
RING_CLEARANCE = 0.25           # bottom clearance / module (ring gear tooth spaces)
EXT_DEDENDUM = 1.0 + EXT_CLEARANCE
RING_DEDENDUM = 1.0 + RING_CLEARANCE
ADDENDUM_RANGE = (0.75, 1.3)    # tooth depth coefficient h_a*: 0.8 stub ... 1.0 standard ... 1.2-1.3 long (HCR)


def clamp_addendum(v) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 1.0
    if v != v:                  # NaN
        return 1.0
    return round(min(ADDENDUM_RANGE[1], max(ADDENDUM_RANGE[0], v)), 3)


def inv(alpha: float) -> float:
    return math.tan(alpha) - alpha


def _tooth_thickness_at(r: float, r_pitch: float, rb: float, s_pitch: float, alpha: float) -> float:
    """Circular tooth thickness of an external gear at radius r (involute function)."""
    if r <= rb:
        r = rb
    ar = math.acos(rb / r)
    return 2.0 * r * (s_pitch / (2.0 * r_pitch) + inv(alpha) - inv(ar))


def _radius_for_thickness(target: float, r_lo: float, r_hi: float, r_pitch: float, rb: float,
                          s_pitch: float, alpha: float) -> float:
    if _tooth_thickness_at(r_hi, r_pitch, rb, s_pitch, alpha) >= target:
        return r_hi
    lo, hi = r_lo, r_hi
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if _tooth_thickness_at(mid, r_pitch, rb, s_pitch, alpha) >= target:
            lo = mid
        else:
            hi = mid
    return lo


@dataclass
class StageGeometry:
    module: float
    pressure_angle: float          # degrees
    z_sun: int
    z_planet: int
    z_ring: int
    backlash: float
    center_distance: float
    r_sun: float
    r_planet: float
    r_ring: float
    rb_sun: float
    rb_planet: float
    rb_ring: float
    root_sun: float
    root_planet: float
    root_ring: float               # outer root of the ring tooth spaces
    tip_sun: float                 # possibly topped
    tip_planet: float              # possibly topped
    tip_ring: float                # inner tip radius, possibly raised
    form_sun: float                # lowest radius of active involute contact
    form_planet: float
    form_ring: float               # highest radius of active contact on the ring
    eps_sun_planet: float          # transverse contact ratio
    eps_planet_ring: float
    tip_topped_sun: bool
    tip_topped_planet: bool
    tip_raised_ring: bool
    interference_free: bool
    addendum: float = 1.0          # nominal tooth depth coefficient h_a*
    tip_land_sun: float = 0.0      # circular tooth thickness at the (final) tip, mm
    tip_land_planet: float = 0.0
    x_sun: float = 0.0             # profile shift coefficients (V-zero: planet and ring = -x_sun)
    x_planet: float = 0.0
    x_ring: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)

    def effective_addendum(self) -> Dict[str, float]:
        """Addendum / module left after tip topping (sun, planet) and ring tip raising."""
        m = self.module
        return {"sun": (self.tip_sun - self.r_sun) / m, "planet": (self.tip_planet - self.r_planet) / m,
                "ring": (self.r_ring - self.tip_ring) / m}


@lru_cache(maxsize=20000)
def stage_geometry(z_sun: int, z_planet: int, z_ring: int, module: float, pressure_angle: float = 20.0,
                   backlash: float = 0.2, min_tip_land: float = -1.0, addendum: float = 1.0,
                   shift: float = 0.0) -> StageGeometry:
    """
    Geometry of one planetary stage. `min_tip_land` (mm) limits pointed tips for printing;
    negative -> automatic: max(0.25 m, 0.2 mm). `addendum` = tooth depth coefficient h_a*.
    `shift` = profile shift coefficient of the sun; the planet and the ring get -shift (module docstring).
    """
    ha = clamp_addendum(addendum)
    xs = round(float(shift), 4)
    xp = xr = -xs
    m = float(module)
    a_rad = math.radians(pressure_angle)
    rs, rp, rr = m * z_sun / 2.0, m * z_planet / 2.0, m * z_ring / 2.0
    rbs, rbp, rbr = rs * math.cos(a_rad), rp * math.cos(a_rad), rr * math.cos(a_rad)
    a = rs + rp
    a_ring = rr - rp
    las = a * math.sin(a_rad)                  # T1T2 of the external pair
    lar = a_ring * math.sin(a_rad)             # T1T2 of the internal pair
    delta = 0.02 * m                           # safety margin on interference limits
    land = min_tip_land if min_tip_land >= 0 else max(0.25 * m, 0.2)
    tan_a = math.tan(a_rad)
    s_pitch_s = m * (math.pi / 2.0 + 2.0 * xs * tan_a) - backlash / 2.0   # tooth thickness at the pitch circle
    s_pitch_p = m * (math.pi / 2.0 + 2.0 * xp * tan_a) - backlash / 2.0

    root_ring = rr + (ha + RING_CLEARANCE + xr) * m
    tip_s0, tip_p0, tip_r0 = rs + (ha + xs) * m, rp + (ha + xp) * m, rr - (ha - xr) * m

    tip_s = min(tip_s0, math.sqrt(rbs ** 2 + las ** 2) - delta)
    tip_p = min(tip_p0, math.sqrt(rbp ** 2 + las ** 2) - delta)
    tip_s = _radius_for_thickness(land, min(rs, tip_s), tip_s, rs, rbs, s_pitch_s, a_rad)
    tip_p = _radius_for_thickness(land, min(rp, tip_p), tip_p, rp, rbp, s_pitch_p, a_rad)
    tip_r = max(tip_r0, math.sqrt(rbr ** 2 + lar ** 2) + delta)

    def leg(r_tip: float, rb: float) -> float:
        return math.sqrt(max(0.0, r_tip ** 2 - rb ** 2))

    form_s = math.sqrt(rbs ** 2 + max(0.0, las - leg(tip_p, rbp)) ** 2)
    form_p_sun = math.sqrt(rbp ** 2 + max(0.0, las - leg(tip_s, rbs)) ** 2)
    form_p_ring = math.sqrt(rbp ** 2 + max(0.0, leg(tip_r, rbr) - lar) ** 2)
    form_p = min(form_p_sun, form_p_ring)
    form_r = math.sqrt(rbr ** 2 + (lar + leg(tip_p, rbp)) ** 2)

    pb = math.pi * m * math.cos(a_rad)
    eps_sp = (leg(tip_s, rbs) + leg(tip_p, rbp) - las) / pb
    eps_pr = (leg(tip_p, rbp) - leg(tip_r, rbr) + lar) / pb

    ok = (leg(tip_p, rbp) <= las + 1e-9 and leg(tip_s, rbs) <= las + 1e-9 and leg(tip_r, rbr) >= lar - 1e-9)
    hf = (ha + EXT_CLEARANCE) * m
    return StageGeometry(
        module=m, pressure_angle=pressure_angle, z_sun=z_sun, z_planet=z_planet, z_ring=z_ring,
        backlash=backlash, center_distance=a, r_sun=rs, r_planet=rp, r_ring=rr,
        rb_sun=rbs, rb_planet=rbp, rb_ring=rbr,
        root_sun=rs - hf + xs * m, root_planet=rp - hf + xp * m, root_ring=root_ring,
        tip_sun=tip_s, tip_planet=tip_p, tip_ring=tip_r,
        form_sun=form_s, form_planet=form_p, form_ring=form_r,
        eps_sun_planet=eps_sp, eps_planet_ring=eps_pr,
        tip_topped_sun=tip_s < tip_s0 - 1e-6, tip_topped_planet=tip_p < tip_p0 - 1e-6,
        tip_raised_ring=tip_r > tip_r0 + 1e-6, interference_free=ok, addendum=ha,
        tip_land_sun=_tooth_thickness_at(tip_s, rs, rbs, s_pitch_s, a_rad),
        tip_land_planet=_tooth_thickness_at(tip_p, rp, rbp, s_pitch_p, a_rad), x_sun=xs, x_planet=xp, x_ring=xr)


# ─── Tooth root form factor (ISO 6336-3, method B) ───────────────────────────

def _inv(a: float) -> float:
    return math.tan(a) - a


@lru_cache(maxsize=8192)
def iso_form_stress_factor(z: float, pressure_angle: float, ha_eff: float, hf: float, clearance: float,
                           x: float = 0.0) -> float:
    """
    Y_F · Y_S of a spur tooth with the load at the tip (ISO 6336-3 method B, gear generated by a rack with
    profile shift x). Lengths in modules: ha_eff = tip height above the pitch circle (incl. the shift),
    hf = dedendum of the basic rack (tool addendum), clearance = bottom clearance (sets the root fillet radius
    of the tool, rho = c / (1 - sin alpha)). Used as a ratio against the standard tooth: bending stress scales
    with Y_F · Y_S.
    """
    an = math.radians(pressure_angle)
    rho = min(0.38, clearance / (1.0 - math.sin(an)))
    zn = max(float(z), 6.0)
    e = math.pi / 4.0 - hf * math.tan(an) - (1.0 - math.sin(an)) * rho / math.cos(an)
    g = rho - hf + x
    h = 2.0 / zn * (math.pi / 2.0 - e) - math.pi / 3.0
    th = math.pi / 6.0
    for _ in range(60):
        th = 2.0 * g / zn * math.tan(th) - h
    s_fn = zn * math.sin(math.pi / 3.0 - th) + math.sqrt(3.0) * (g / math.cos(th) - rho)
    rho_f = rho + 2.0 * g * g / (math.cos(th) * (zn * math.cos(th) ** 2 - 2.0 * g))
    db = zn * math.cos(an)
    da = max(zn + 2.0 * ha_eff, db * 1.0001)
    a_en = math.acos(db / da)
    g_e = 0.5 * math.pi / zn + _inv(an) - _inv(a_en)
    a_fen = a_en - g_e
    h_fe = 0.5 * ((math.cos(g_e) - math.sin(g_e) * math.tan(a_fen)) * da - zn * math.cos(math.pi / 3.0 - th)
                  - g / math.cos(th) + rho)
    y_f = 6.0 * h_fe * math.cos(a_fen) / (s_fn ** 2 * math.cos(an))
    l_ = s_fn / h_fe
    q_s = s_fn / (2.0 * rho_f)
    y_s = (1.2 + 0.13 * l_) * q_s ** (1.0 / (1.21 + 2.3 / l_))
    return y_f * y_s


RING_FORM_Z = 400.0     # ring teeth: rack-like form factor (internal teeth are at least as strong)


def depth_strength_factors(geo: StageGeometry) -> Dict[str, float]:
    """
    Tooth root strength of this geometry relative to the same tooth counts with standard depth (h_a* = 1.0)
    and no profile shift, from the ISO form/stress factors with the load at the actual (topped) tip.
    > 1: stronger root (stub teeth, positive shift), < 1: weaker (long teeth, negative shift). Exactly 1.0
    for h_a* = 1 and x = 0. The ring tooth is a rack-like tooth whose thickness grows with -x_ring.
    """
    if abs(geo.addendum - 1.0) < 1e-9 and abs(geo.x_sun) < 1e-9:
        return {"sun": 1.0, "planet": 1.0, "ring": 1.0}
    ref = stage_geometry(geo.z_sun, geo.z_planet, geo.z_ring, geo.module, geo.pressure_angle, geo.backlash,
                         addendum=1.0)
    eff, eff_ref = geo.effective_addendum(), ref.effective_addendum()
    pa, ha = geo.pressure_angle, geo.addendum
    out = {}
    for key, z, c, x in (("sun", geo.z_sun, EXT_CLEARANCE, geo.x_sun),
                         ("planet", geo.z_planet, EXT_CLEARANCE, geo.x_planet),
                         ("ring", RING_FORM_Z, RING_CLEARANCE, -geo.x_ring)):
        f_ref = iso_form_stress_factor(z, pa, round(eff_ref[key], 4), 1.0 + c, c)
        f_new = iso_form_stress_factor(z, pa, round(eff[key], 4), ha + c, c, round(x, 4))
        out[key] = f_ref / f_new
    return out


SHIFT_LIMITS = (-0.3, 0.6)      # automatic profile shift of the sun (planet / ring: the negative)


def undercut_shift(z: float, pressure_angle: float, addendum: float = 1.0) -> float:
    """Smallest profile shift of a rack-generated external gear without undercut: x = h_a* - z sin^2(alpha) / 2."""
    return addendum - z * math.sin(math.radians(pressure_angle)) ** 2 / 2.0


def overlap_ratio(face_width: float, helix_deg: float, module: float, herringbone: bool) -> float:
    """Face (overlap) contact ratio eps_beta; for herringbone per helix half."""
    if helix_deg <= 0.0:
        return 0.0
    b = face_width / 2.0 if herringbone else face_width
    return b * math.sin(math.radians(helix_deg)) / (math.pi * module)
