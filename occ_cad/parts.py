# -*- coding: utf-8 -*-
"""
Parça üreticileri (Fusion eklentisindeki cad/*_builder.py modüllerinin OpenCascade karşılıkları,
baskıya ve montaja yönelik mühendislik düzeltmeleriyle).

Her fonksiyon tek bir katı (TopoDS_Shape) döndürür; ölçüler mm'dir. Tekrar eden parçalar
(planet, rulman, pim, cıvata...) orijinde kurulur ve montajda konumlandırılır (instance).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from core.engineering import hub_nut_layout
from core.layout import ARM_GAP, ARM_SCREW_HEAD_DEPTH, arm_boss_height, drum_arm_height
from core.tooth_profile import ToothProfileGenerator

from . import kernel as K
from . import profiles as P

BORE_TOL = 0.05      # Fusion: add_shaft_bore tolerance_offset_mm
SPIGOT_H = 1.2       # merkezleme omuzu yüksekliği


def herringbone_twist(face_width: float, pitch_r: float, helix_deg: float) -> float:
    """Yarım diş genişliğindeki dönme açısı (rad) — Fusion ile aynı formül."""
    return ToothProfileGenerator.calculate_herringbone_twist_angle(face_width, pitch_r, helix_deg)


def _gear_body(wire, z0: float, face_width: float, twist_mid: float):
    """Düz dişli: extrude. Balıksırtı: alt yarı +twist, üst yarı geri dönüş (V)."""
    if abs(twist_mid) > 1e-9:
        return K.twisted_solid(wire, [z0, z0 + face_width / 2.0, z0 + face_width], [0.0, twist_mid, 0.0])
    return K.extrude(K.planar_face(wire), z0, z0 + face_width)


def annulus(r_in: float, r_out: float, z0: float, z1: float, cx: float = 0.0, cy: float = 0.0):
    outer = K.cylinder(r_out, z0, z1, cx, cy)
    if r_in <= 0:
        return outer
    return K.cut(outer, [K.cylinder(r_in, z0 - 1.0, z1 + 1.0, cx, cy)], "halka")


def _polar_xy(r: float, ang: float) -> Tuple[float, float]:
    return r * math.cos(ang), r * math.sin(ang)


# ─── Dişliler ────────────────────────────────────────────────────────────────

def external_gear_solid(z: int, module: float, pressure_angle: float, backlash: float, face_width: float,
                        z0: float, helix_deg: float, twist_sign: float, phase: float = 0.0,
                        tip_r: Optional[float] = None, form_r: Optional[float] = None, addendum: float = 1.0,
                        shift: float = 0.0):
    wire, info = P.external_gear(z, module, pressure_angle, backlash, phase, tip_r=tip_r, form_r=form_r,
                                 addendum=addendum, shift=shift)
    twist = herringbone_twist(face_width, info['pitch_r'], helix_deg) * twist_sign if helix_deg > 0 else 0.0
    return _gear_body(wire, z0, face_width, twist), info


COLLAR_NECK = 0.6          # = running clearance of the planets above the sun collar


def build_motor_sun(geo, face_width: float, z0: float, pressure_angle: float, backlash: float, helix_deg: float,
                    phase: float, bore_dia: float, bore_kind: str, flat_depth: float, collar_r: float,
                    collar_len: float) -> Tuple[object, Dict]:
    """
    1. kademe güneşi: motor mili deliği, altta sıkma bileziği, radyal M3 setskur ve alttan
    takılan M3 kare somun (DIN 562) yuvası.
    """
    body, info = external_gear_solid(geo.z_sun, geo.module, pressure_angle, backlash, face_width, z0, helix_deg,
                                     +1.0, phase, geo.tip_sun, geo.form_sun, geo.addendum, geo.x_sun)
    safe_bore = min(bore_dia, max(1.0, 2.0 * geo.root_sun - 1.5))
    info.update(bore=safe_bore, bore_reduced=safe_bore < bore_dia - 1e-6)
    body = K.fuse(body, [K.cylinder(collar_r, z0 - collar_len, z0)], "güneş bileziği")
    z_screw = z0 - collar_len / 2.0
    tools = [K.cylinder_along(1.6, (0.0, 0.0, z_screw), (0.0, 1.0, 0.0), collar_r + 1.0)]
    nut_y = (safe_bore / 2.0 + collar_r) / 2.0
    slot = K.polygon_wire([(-2.95, nut_y - 1.05), (2.95, nut_y - 1.05), (2.95, nut_y + 1.05), (-2.95, nut_y + 1.05)])
    tools.append(K.extrude(K.planar_face(slot), z0 - collar_len - 1.0, z_screw + 2.95))
    bore = P.shaft_section(safe_bore, bore_kind, flat_depth, BORE_TOL)
    tools.append(K.extrude(K.planar_face(bore), z0 - collar_len - 1.0, z0 + face_width + 1.0))
    # small sun: the collar reaches under the planet teeth -> neck its top (running clearance below the planets)
    neck_r = geo.center_distance - geo.tip_planet - 0.3
    if collar_r > neck_r:
        tools.append(K.cut(K.cylinder(collar_r + 1.0, z0 - COLLAR_NECK, z0),
                           [K.cylinder(max(neck_r, safe_bore / 2.0 + 1.2), z0 - COLLAR_NECK - 1.0, z0 + 1.0)],
                           "bilezik boynu"))
    return K.cut(body, tools, "güneş dişli deliği"), info


def build_planet(geo, face_width: float, z0: float, pressure_angle: float, backlash: float, helix_deg: float,
                 layout: str, pocket_d: float, bearing_w: float, inner_race_d: float, pin_d: float,
                 bushing_clearance: float) -> Tuple[object, Dict]:
    """
    Planet dişli (orijinde). Rulmanlar yüzeyle aynı hizada: 'dual' iki rulman (alt + üst, ortada
    gövde), 'single' tek rulman (üstte), 'bushing' rulmansız düz yatak.
    """
    body, info = external_gear_solid(geo.z_planet, geo.module, pressure_angle, backlash, face_width, z0,
                                     helix_deg, -1.0, 0.0, geo.tip_planet, geo.form_planet, geo.addendum,
                                     geo.x_planet)
    z1 = z0 + face_width
    if layout == "bushing":
        tools = [K.cylinder(pin_d / 2.0 + bushing_clearance, z0 - 1.0, z1 + 1.0)]
    else:
        web_r = inner_race_d / 2.0 + 0.3          # gövde yalnızca dış bileziğe değer
        tools = [K.cylinder(web_r, z0 - 1.0, z1 + 1.0),
                 K.cylinder(pocket_d / 2.0, z1 - bearing_w, z1 + 1.0)]
        if layout == "dual":
            tools.append(K.cylinder(pocket_d / 2.0, z0 - 1.0, z0 + bearing_w))
    return K.cut(body, tools, "planet yuvaları"), info


# ─── Çember dişli gövdesi ────────────────────────────────────────────────────

def _lugged_plate(hd: Dict, lugs: bool, z0: float, z1: float, holes: Sequence = ()):
    """Kulaklı plaka/boru: analitik kontur ile tek extrude (kulaklar arası boolean yok)."""
    lug_pos = hd["positions"] if lugs else []
    outline = P.lugged_outline(hd["wall_r"], lug_pos, hd["lug_r"])
    if outline is not None:
        return K.extrude(K.planar_face(outline, holes), z0, z1)
    base = K.extrude(K.planar_face(K.circle_wire(hd["wall_r"])), z0, z1)
    body = K.fuse(base, [K.cylinder(hd["lug_r"], z0, z1, x, y) for x, y in lug_pos], "gövde kulakları", unify=True)
    return K.cut(body, [K.extrude(K.planar_face(h), z0 - 1.0, z1 + 1.0) for h in holes], "gövde delikleri")


def spigot_radii(hd: Dict) -> Tuple[float, float]:
    r_a = hd["root_r"] + 0.6
    r_b = r_a + max(0.8, min(1.6, hd["wall_r"] - r_a - 1.0))
    return r_a, r_b


def spigot_male(hd: Dict, z_top: float):
    """Üst yüzde merkezleme omuzu (parçanın içine 0.5 mm gömülü -> çakışık yüz yok)."""
    r_a, r_b = spigot_radii(hd)
    return annulus(r_a, r_b, z_top - 0.5, z_top + SPIGOT_H)


def spigot_female(hd: Dict, z_bottom: float):
    r_a, r_b = spigot_radii(hd)
    return annulus(r_a - 0.15, r_b + 0.15, z_bottom - 1.0, z_bottom + SPIGOT_H + 0.2)


def _ring_holes(hd: Dict, lugs: bool, z: float, hole_d: float):
    return [K.circle_wire(hole_d / 2.0, x, y, z) for x, y in hd["positions"]] if lugs else []


def _cap_faces(outline, gear_wire, bolt_holes, z: float, hd: Dict, spigot: Optional[str]):
    """
    Gövde bölümünün alt/üst kapak yüzleri. Merkezleme omuzu ('male', üst yüzden yukarı) veya
    yuvası ('female', alt yüzden içeri) doğrudan yüz olarak kurulur (boolean yok).
    """
    if spigot is None:
        return [K.planar_face(outline, [gear_wire] + bolt_holes)]
    r_a, r_b = spigot_radii(hd)
    h = SPIGOT_H
    if spigot == "female":
        r_a, r_b, h = r_a - 0.15, r_b + 0.15, SPIGOT_H + 0.2
    c_out, c_in = K.circle_wire(r_b, 0, 0, z), K.circle_wire(r_a, 0, 0, z)
    faces = [K.planar_face(outline, [c_out] + bolt_holes), K.planar_face(c_in, [gear_wire])]
    faces += K.faces(K.prism(c_out, h)) + K.faces(K.prism(c_in, h))
    faces.append(K.planar_face(K.circle_wire(r_b, 0, 0, z + h), [K.circle_wire(r_a, 0, 0, z + h)]))
    return faces


def build_ring_section(geo, pressure_angle: float, backlash: float, zs: Sequence[float], angles: Sequence[float],
                       hd: Dict, lugs: bool, hole_d: float, male_top: bool, female_bottom: bool):
    """
    Çember dişli gövdesi (düz dişlide tek parça, balıksırtında V tepe düzlemleri arasındaki bölüm).
    İç diş yüzeyi loft/extrude, dış yüzeyler extrude ile; kapaklar ve merkezleme omuzları düzlemsel
    yüzlerle kurulur ve hepsi dikilerek katı yapılır — boolean işlem yoktur.
    """
    inner, info = P.internal_gear(geo.z_ring, geo.module, pressure_angle, backlash, 0.0,
                                  tip_r=geo.tip_ring, form_r=geo.form_ring, addendum=geo.addendum,
                                  shift=geo.x_ring)
    z_lo, z_hi = zs[0], zs[-1]
    outline = P.lugged_outline(hd["wall_r"], hd["positions"] if lugs else [], hd["lug_r"])
    male = "male" if (lugs and male_top) else None
    female = "female" if (lugs and female_bottom) else None
    if outline is not None:
        try:
            side, first, last = K.twisted_faces(inner, zs, angles)
            h = z_hi - z_lo
            out_lo, out_hi = K.place_wire(outline, z_lo), K.place_wire(outline, z_hi)
            holes_lo, holes_hi = _ring_holes(hd, lugs, z_lo, hole_d), _ring_holes(hd, lugs, z_hi, hole_d)
            face_list = side + K.faces(K.prism(out_lo, h))
            for hw in holes_lo:
                face_list += K.faces(K.prism(hw, h))
            face_list += _cap_faces(out_lo, first, holes_lo, z_lo, hd, female)
            face_list += _cap_faces(out_hi, last, holes_hi, z_hi, hd, male)
            solid = K.sew_solid(face_list)
            if K.is_valid(solid) and K.volume(solid) > 0.0:
                return solid, info
        except K.GeometryError:
            pass
    # yedek yol: boolean
    plate = _lugged_plate(hd, lugs, z_lo, z_hi, _ring_holes(hd, lugs, 0.0, hole_d))
    body = K.cut(plate, [K.twisted_solid(inner, zs, angles)], "çember dişli")
    if male:
        body = K.fuse(body, [spigot_male(hd, z_hi)], "merkezleme omuzu")
    if female:
        body = K.cut(body, [spigot_female(hd, z_lo)], "merkezleme yuvası")
    return body, info


def build_ring_spur(geo, pressure_angle: float, backlash: float, z0: float, z1: float, hd: Dict, lugs: bool,
                    hole_d: float, male_top: bool, female_bottom: bool):
    """Düz dişli çember gövdesi: tek parça (aynı dikiş yolu, dönme açısı sıfır)."""
    return build_ring_section(geo, pressure_angle, backlash, [z0, z1], [0.0, 0.0], hd, lugs, hole_d,
                              male_top, female_bottom)


# ─── Planet taşıyıcı ─────────────────────────────────────────────────────────

LIGHTENING_WALL = 3.0     # en az et: delik ile dış kenar / göbek / pim deliği arasında (baskıda ~7 çevre)


def _lightening_holes(cd: float, n: int, r_in: float, r_out: float, pin_hole_r: float, z0: float, z1: float):
    """
    Pimler arasına hafifletme delikleri (yer varsa); her yönde en az LIGHTENING_WALL et kalır. Komşu
    delikler arasındaki kol (torku pimden göbeğe taşır) en az 1.5 x et: çok planetli büyük plakalarda
    delikler birleşip göbeği plakadan ayırmasın.
    """
    wall = max(LIGHTENING_WALL, 0.12 * (r_out - r_in))
    rc = (r_in + r_out) / 2.0
    # deliğin merkezi pimler arasındaki açıortayda: komşu pim deliğine olan mesafe
    pin_dist = math.hypot(rc * math.cos(math.pi / n) - cd, rc * math.sin(math.pi / n))
    r_l = min((r_out - r_in) / 2.0 - wall, pin_dist - pin_hole_r - wall,
              rc * math.sin(math.pi / n) - 0.75 * wall)
    if r_l < 2.5:
        return []
    return [K.cylinder(r_l, z0 - 1.0, z1 + 1.0, *_polar_xy(rc, math.pi / n + 2 * math.pi * i / n)) for i in range(n)]


def build_cage_bottom_plate(cd: float, n: int, pin_hole_d: float, z0: float, t: float, r_in: float, r_out: float):
    """Kafes taşıyıcının alt plakası: güneşin geçtiği delikli halka + pim delikleri."""
    body = annulus(r_in, r_out, z0, z0 + t)
    tools = [K.cylinder(pin_hole_d / 2.0, z0 - 1.0, z0 + t + 1.0, *_polar_xy(cd, 2 * math.pi * i / n)) for i in range(n)]
    tools += _lightening_holes(cd, n, r_in, r_out, pin_hole_d / 2.0, z0, z0 + t)
    return K.cut(body, tools, "alt taşıyıcı plaka")


def build_cage_top_plate(cd: float, n: int, pin_hole_d: float, z0: float, t: float, r_out: float, hub_r: float,
                         extras: Sequence = (), cuts: Sequence = ()):
    """
    Kafes taşıyıcının üst plakası (tam disk + pim delikleri). `extras`: plakaya gömülü bir sonraki
    kademe güneşi veya çıkış göbeği; `cuts`: çıkış flanşı burç delikleri, çelik mil yuvası.
    """
    body = K.cylinder(r_out, z0, z0 + t)
    if extras:
        body = K.fuse(body, list(extras), "taşıyıcı göbeği")
    tools = [K.cylinder(pin_hole_d / 2.0, z0 - 1.0, z0 + t + 1.0, *_polar_xy(cd, 2 * math.pi * i / n)) for i in range(n)]
    tools += _lightening_holes(cd, n, hub_r, r_out, pin_hole_d / 2.0, z0, z0 + t)
    tools += list(cuts)
    return K.cut(body, tools, "üst taşıyıcı plaka")


def build_single_carrier(cd: float, n: int, pin_d: float, z_planet: float, face_width: float, clearance: float,
                         plate_t: float, pin_tail: float, hub_r: float, boss_r: float, step_r: float,
                         groove: Optional[Tuple[float, float]], extras: Sequence = (), cuts: Sequence = ()):
    """
    Klasik tek plaka: tam disk (kol + göbek birleşimlerinde çentik / sivri iç köşe yok), pimler
    arasında yuvarlak hafifletme delikleri, aşağı sarkan baskı pimleri, rulman iç bileziğine basan
    basamak, DIN 471 / 6799 segman kanalları.
    """
    pin_r = pin_d / 2.0
    zp = z_planet + face_width + clearance
    zt = zp + plate_t
    zmid = zp + plate_t / 2.0
    r_plate = cd + boss_r                     # boss_r çember diş uçlarından açıklığı zaten sağlar
    base = K.cylinder(r_plate, zp, zt)
    tools = list(extras)
    for i in range(n):
        px, py = _polar_xy(cd, 2.0 * math.pi * i / n)
        tools.append(K.cylinder(pin_r, z_planet - pin_tail, zmid, px, py))
        tools.append(K.cylinder(step_r, zp - clearance, zmid, px, py))
    body = K.fuse(base, tools, "taşıyıcı", unify=True)
    cut_tools = list(cuts) + _lightening_holes(cd, n, hub_r, r_plate, max(pin_r, step_r), zp, zt)
    if groove is not None:
        d2, width = groove
        g_top = z_planet - 0.3
        for i in range(n):
            px, py = _polar_xy(cd, 2.0 * math.pi * i / n)
            cut_tools.append(annulus(d2 / 2.0, pin_r + 1.0, g_top - width, g_top, px, py))
    return K.cut(body, cut_tools, "segman kanalları")


ARM_POCKET_TOL = 0.15  # kol cebindeki çift-D boşluğu (yarıçapa)
INSERT_R, INSERT_DEPTH = 2.0, 5.7      # M3 ısıl burç deliği Ø4.0 x 5.7
M3_CLEAR_R, M3_HEAD_R = 1.7, 3.1
M3_HEAD_DEPTH = ARM_SCREW_HEAD_DEPTH


M3_NUT_S, M3_NUT_M = 5.5, 2.4          # ISO 4032 M3 altıgen somun
M3_NUT = {"d": 3.0, "nut_s": M3_NUT_S, "nut_m": M3_NUT_M}
NUT_ROOF_FLANGE, NUT_ROOF_ARM = 2.5, 2.0   # somun yuvası ile göbek yüzü arasındaki et
NUT_TIP_ROOM = 4.0                     # vida ucu için somunun altında kalan delik
NUT_SPREAD = math.radians(25.0)        # 4 somunda yuvaların ±X ekseninden açısı


def hub_screw_points(hub_d: float, fastener: str = "NUT") -> List[Tuple[float, float]]:
    """
    Çıkış göbeğine (flanş yüzü / kol kilidi) giren M3 vidaların konumu.
    Isıl burç: göbek ≥20 mm ise 4 adet, değilse merkezde 1 adet. Tutsak somun: yan yuvalar göbek
    kesitini fazla zayıflatmasın diye ≥40 mm'de 4, 14–40 mm'de 2 (çapraz), daha küçükte 1 adet
    (core.engineering.hub_nut_layout; somun katmanı burulma kontrolü aynı yerleşimi kullanır).
    """
    if fastener == "INSERT":
        if hub_d >= 20.0:
            return [_polar_xy(0.31 * hub_d, math.pi / 4 + i * math.pi / 2) for i in range(4)]
        return [(0.0, 0.0)]
    # nut pockets open towards ±X: through the round sides of the double-D key, far from the corners
    # where its flats (±Y) meet the circle (a pocket crossing that corner upsets the boolean cut)
    n, r = hub_nut_layout(hub_d)
    if n == 4:
        return [_polar_xy(r, a) for a in (NUT_SPREAD, -NUT_SPREAD, math.pi + NUT_SPREAD, math.pi - NUT_SPREAD)]
    if n == 2:
        return [_polar_xy(r, 0.0), _polar_xy(r, math.pi)]
    return [(0.0, 0.0)]


def arm_screw_points(hub_d: float, fastener: str = "NUT") -> List[Tuple[float, float]]:
    return hub_screw_points(hub_d, fastener)


def _hub_face(kind: str, z_cover_top: float, protrusion: float, key_h: float,
              arm_gap: float = ARM_GAP) -> Tuple[float, float]:
    """Vidaların girdiği göbek yüzünün kotu ve somun yuvası üstünde kalan et: (z_top, roof)."""
    if kind == "FLANGE":
        return z_cover_top + protrusion, NUT_ROOF_FLANGE
    return z_cover_top + arm_gap + key_h, NUT_ROOF_ARM


def _nut_pocket_z(z_top: float, roof: float) -> float:
    """Somun yuvasının taban kotu (yuva yüksekliği somun + 0.3 mm)."""
    return z_top - roof - (M3_NUT_M + 0.3)


def hub_nut_seats(kind: str, hub_d: float, z_cover_top: float, protrusion: float = 5.0, key_h: float = 6.0,
                  fastener: str = "NUT", arm_gap: float = ARM_GAP) -> List[Tuple[float, float, float, float]]:
    """
    Çıkış göbeği yuvalarındaki tutsak M3 somunlar: [(x, y, somun alt kotu, dönüş açısı)].
    Somun yuvada ortalanır (alt/üst 0.15 mm boşluk); düz yüzleri yuva duvarlarına paralel
    (yuva açısı + 30°, gövde somunlarıyla aynı kural).
    """
    if fastener != "NUT" or kind not in ("FLANGE", "ARM"):
        return []
    z_top, roof = _hub_face(kind, z_cover_top, protrusion, key_h, arm_gap)
    z = _nut_pocket_z(z_top, roof) + 0.15
    return [(x, y, z, math.atan2(y, x) + math.pi / 6.0) for x, y in hub_screw_points(hub_d, fastener)]


def _hub_fastener_cuts(points, z_top: float, roof: float, hub_r: float, fastener: str) -> List:
    """Isıl burç delikleri veya yandan takılan somun yuvaları + vida delikleri."""
    cuts = []
    for x, y in points:
        if fastener == "INSERT":
            cuts.append(K.cylinder(INSERT_R, z_top - INSERT_DEPTH, z_top + 1.0, x, y))
            continue
        z_nut = _nut_pocket_z(z_top, roof)
        cuts.append(K.cylinder(M3_CLEAR_R, z_nut - NUT_TIP_ROOM, z_top + 1.0, x, y))
        cuts.append(_nut_slot(x, y, M3_NUT_S, M3_NUT_M, z_nut, hub_r + 1.0))
    return cuts


def output_hub(kind: str, hub_d: float, shaft_d: float, z_from: float, z_cover_top: float, shoulder_r: float,
               z_shoulder_top: float, shaft_len: float, protrusion: float = 5.0, key_h: float = 6.0,
               key_flat: float = 0.0, fastener: str = "NUT", arm_gap: float = ARM_GAP):
    """
    Son taşıyıcının çıkışı: çıkış rulmanından geçen yuvarlak göbek + rulman iç bileziğine basan omuz.
      FLANGE        göbek kapaktan `protrusion` kadar çıkar; yüzünde M3 vida delikleri ve yandan takılan
                    tutsak somun yuvaları (veya ısıl burç delikleri)
      SHAFT_PRINTED göbeğin üstünde basılı D-mil (shaft_len)
      SHAFT_STEEL   göbekte çelik D-mil için yuva (mil ayrıca satın alınır)
      ARM           göbeğin ucu çift-D kilit (key_h yüksekliğinde); kol üstüne oturur, M3 vidalarla tutulur
    Döndürür: (eklenecek katılar, kesilecek katılar, üst kot)
    """
    r_h = hub_d / 2.0
    extras = [K.cylinder(shoulder_r, z_from, z_shoulder_top)]
    cuts = []
    if kind == "FLANGE":
        z_top, roof = _hub_face(kind, z_cover_top, protrusion, key_h)
        hub = K.cylinder(r_h, z_from, z_top)
        hub_cuts = []
        if fastener == "INSERT" and hub_d < 14.0:
            hub_cuts.append(K.cylinder(1.25, z_top - 6.0, z_top + 1.0))                # M3 kılavuz (Ø2.5)
        else:
            pts = hub_screw_points(hub_d, fastener)
            hub_cuts += _hub_fastener_cuts(pts, z_top, roof, r_h, fastener)
            if len(pts) > 1:
                hub_cuts.append(K.cylinder(max(1.5, 0.12 * hub_d), z_top - 2.0, z_top + 1.0))   # merkezleme
        extras.append(K.cut(hub, hub_cuts, "çıkış flanşı somun yuvaları"))   # göbek tek başına kesilir
        return extras, cuts, z_top
    if kind == "ARM":
        z_key = z_cover_top + arm_gap
        z_top, roof = _hub_face(kind, z_cover_top, protrusion, key_h, arm_gap)
        key = K.extrude(K.planar_face(P.shaft_section(hub_d, "DOUBLE_D", key_flat, 0.0)), z_key, z_top)
        hub = K.fuse(K.cylinder(r_h, z_from, z_key), [key], "kol göbeği")
        hub = K.cut(hub, _hub_fastener_cuts(hub_screw_points(hub_d, fastener), z_top, roof, r_h, fastener),
                    "kol göbeği somun yuvaları")
        extras.append(hub)
        return extras, cuts, z_top
    if kind == "SHAFT_STEEL":
        z_top = z_cover_top + 0.5
        extras.append(K.cylinder(r_h, z_from, z_top))
        bore = P.shaft_section(shaft_d, "D_CUT", 0.06 * shaft_d, 0.02)
        cuts.append(K.extrude(K.planar_face(bore), z_from - 0.5, z_top + 1.0))
        return extras, cuts, z_top
    extras.append(K.cylinder(r_h, z_from, z_cover_top + 0.5))
    shaft = P.shaft_section(shaft_d, "D_CUT", 0.06 * shaft_d, 0.0)
    z_top = z_cover_top + shaft_len
    extras.append(K.extrude(K.planar_face(shaft), z_cover_top, z_top))
    return extras, cuts, z_top


def build_output_arm(shape: str, length: float, width: float, thickness: float, hub_d: float, key_h: float,
                     key_flat: float, fastener: str = "NUT") -> Tuple[object, float]:
    """
    Çıkış kolu (alt yüzü z=0, +X yönünde uzanır; basım yönüyle aynı). Göbek, çıkış milinin çift-D
    kilidine oturan cep ve M3 havşalı delikler taşır. FLAT: t x w yassı kol, yuvarlak uç + delik.
    ROUND: Ø w çubuk, tablaya oturan düzlüğü var (destek gerektirmez), uçta dikey delik.
    Döndürür: (katı, göbek yüksekliği)
    """
    boss_r = hub_d / 2.0 + max(6.0, 0.25 * hub_d)
    tb = arm_boss_height(key_h, shape, width, thickness)        # core.layout: tasarım motoruyla aynı yükseklik
    tools = []
    if shape == "ROUND":
        d = width
        zc = 0.46 * d
        L = max(length, boss_r + 0.6 * d)
        rod = K.cylinder_along(d / 2.0, (0.0, 0.0, zc), (1.0, 0.0, 0.0), L + 0.6 * d)
        rod = K.cut(rod, [K.extrude(K.planar_face(K.polygon_wire(
            [(-1.0, -d), (L + d, -d), (L + d, d), (-1.0, d)])), -d, 0.0)], "kol düzlüğü")
        tools.append(rod)
        hole_r = min(4.25, max(1.7, 0.175 * d))
    else:
        w, t = width, thickness
        L = max(length, boss_r + 0.6 * w)
        tools.append(K.extrude(K.planar_face(K.polygon_wire([(0.0, -w / 2.0), (L, -w / 2.0), (L, w / 2.0),
                                                            (0.0, w / 2.0)])), 0.0, t))
        tools.append(K.cylinder(w / 2.0, 0.0, t, L, 0.0))
        hole_r = min(4.25, max(1.7, 0.175 * w))
    body = K.fuse(K.cylinder(boss_r, 0.0, tb), tools, "çıkış kolu", unify=True)
    pocket = K.extrude(K.planar_face(P.shaft_section(hub_d, "DOUBLE_D", key_flat - ARM_POCKET_TOL,
                                                     ARM_POCKET_TOL)), -1.0, key_h + 0.4)
    cuts = [pocket, K.cylinder(hole_r, -1.0, tb + 1.0, L, 0.0)]
    for x, y in hub_screw_points(hub_d, fastener):
        cuts.append(K.cylinder(M3_CLEAR_R, -1.0, tb + 1.0, x, y))
        cuts.append(K.cylinder(M3_HEAD_R, tb - M3_HEAD_DEPTH, tb + 1.0, x, y))
    return K.cut(body, cuts, "kol cebi ve delikleri"), tb


def _arm_bar(shape: str, length: float, width: float, thickness: float, boss_r: float, h: float):
    """Kol çubuğu (+X), göbeği hariç: (araçlar, uç deliği yarıçapı, uç x)."""
    if shape == "ROUND":
        d = width
        zc = 0.46 * d
        L = max(length, boss_r + 0.6 * d)
        rod = K.cylinder_along(d / 2.0, (0.0, 0.0, zc), (1.0, 0.0, 0.0), L + 0.6 * d)
        rod = K.cut(rod, [K.extrude(K.planar_face(K.polygon_wire(
            [(-1.0, -d), (L + d, -d), (L + d, d), (-1.0, d)])), -d, 0.0)], "kol düzlüğü")
        return [rod], min(4.25, max(1.7, 0.175 * d)), L
    w, t = width, thickness
    L = max(length, boss_r + 0.6 * w)
    tools = [K.extrude(K.planar_face(K.polygon_wire([(0.0, -w / 2.0), (L, -w / 2.0), (L, w / 2.0),
                                                     (0.0, w / 2.0)])), 0.0, t),
             K.cylinder(w / 2.0, 0.0, t, L, 0.0)]
    return tools, min(4.25, max(1.7, 0.175 * w)), L


PIN_SLIP = 0.15       # index plunger pin: running fit in the collar hole (on the diameter)


def _hex(x: float, y: float, s: float, z0: float, z1: float):
    r = s / math.sqrt(3.0)
    return K.extrude(K.planar_face(K.polygon_wire([(x + r * math.cos(k * math.pi / 3), y + r * math.sin(k * math.pi / 3))
                                                   for k in range(6)])), z0, z1)


def build_declutch_arm(shape: str, length: float, width: float, thickness: float, geo: Dict, h_a: float):
    """
    Boşa alınabilen kol (alt yüzü z=0): bileziğin boynunda serbest dönen göbek halkası (delik bore_r) + kol. Göbekte
    r_c'de yaylı indeks pimi (GN 617.1): gövde deliği boydan boya, altta ince somun cebi, üstte kilit somunu (kol daha
    kalınsa havşa). Topuz çekilip çeyrek tur çevrilince pim yukarıda kalır, kol bilezik üzerinde serbest döner.
    """
    pl, lay = geo["plunger"], geo["lay"]
    tools, hole_r, L = _arm_bar(shape, length, width, thickness, geo["boss_r"], h_a)
    body = K.fuse(K.cylinder(geo["boss_r"], 0.0, h_a), tools, "boşa alma kolu", unify=True)
    x = -geo["r_c"]
    cuts = [K.cylinder(geo["bore_r"], -1.0, h_a + 1.0), K.cylinder(hole_r, -1.0, h_a + 1.0, L, 0.0),
            K.cylinder(pl["d2"] / 2.0 + 0.25, -1.0, h_a + 1.0, x, 0.0),
            _hex(x, 0.0, pl["s"] + 0.3, -1.0, pl["m"] + 0.2)]
    if h_a > lay["local_top"] + 0.01:
        cuts.append(K.cylinder(geo["clear"] + 1.0, lay["local_top"], h_a + 1.0, x, 0.0))
    return K.cut(body, cuts, "boşa alma kolu delikleri")


def build_index_plunger(pl: Dict, local_top: float):
    """GN 617.1 yaylı indeks pimi (z=0 diş sonu = kolun alt yüzü): pim ucu aşağıda, gövde, kilit somunu, topuz."""
    body = K.fuse(K.cylinder(pl["d1"] / 2.0, -pl["l2"], 0.01),
                  [K.cylinder(pl["d2"] / 2.0, 0.0, pl["l1"]),
                   _hex(0.0, 0.0, pl["s"], local_top, local_top + pl["m_lock"]),
                   K.cylinder(pl["knob_d"] / 2.0, pl["l1"] - 0.01, pl["l1"] + pl["knob_h"])], "indeks pimi")
    return body


def build_plunger_nut(pl: Dict):
    return K.cut(_hex(0.0, 0.0, pl["s"], 0.0, pl["m"]), [K.cylinder(pl["d2"] / 2.0, -1.0, pl["m"] + 1.0)], "ince somun")


def build_declutch_collar(hub_d: float, key_h: float, key_flat: float, fastener: str, geo: Dict, lay: Dict):
    """
    Tahrik bileziği (alt yüzü z=0): çift-D kilide oturan omuz + boyun (kol bunun üzerinde döner); omuzda indeks
    piminin kör deliği, göbek vidaları boydan boya (başlar kapak pulunun üstünde).
    """
    body = K.fuse(K.cylinder(geo["shoulder_r"], 0.0, lay["t_s"]), [K.cylinder(geo["r_s"], lay["t_s"] - 0.01, lay["z_sp"])],
                  "tahrik bileziği")
    pocket = K.extrude(K.planar_face(P.shaft_section(hub_d, "DOUBLE_D", key_flat - ARM_POCKET_TOL,
                                                     ARM_POCKET_TOL)), -1.0, key_h + 0.4)
    pl = geo["plunger"]
    cuts = [pocket, K.cylinder((pl["d1"] + PIN_SLIP) / 2.0, lay["t_s"] - pl["l2"] - 1.0, lay["t_s"] + 1.0,
                               -geo["r_c"], 0.0)]
    cuts += [K.cylinder(M3_CLEAR_R, -1.0, lay["z_sp"] + 1.0, x, y) for x, y in hub_screw_points(hub_d, fastener)]
    return K.cut(body, cuts, "tahrik bileziği delikleri")


def build_declutch_cap(hub_d: float, fastener: str, geo: Dict, t: float, pts: Optional[Sequence] = None):
    """Kapak pulu (alt yüzü z=0): kolu bileziğin üzerinde tutar, göbek (veya tambur kapağı) vidalarıyla sıkılır."""
    body = K.cylinder(geo["bore_r"] + 1.5, 0.0, t)
    pts = pts if pts is not None else hub_screw_points(hub_d, fastener)
    return K.cut(body, [K.cylinder(M3_CLEAR_R, -1.0, t + 1.0, x, y) for x, y in pts], "kapak pulu delikleri")


def build_drum_declutch_collar(geo: Dict, lay: Dict, screw_pts: Sequence[Tuple[float, float]], disc_r: float):
    """
    Tambur / göbek yüzüne vidalanan tahrik halkası (alt yüzü z=0): disk (boşa alma piminin kör deliği) + boyun (kol
    bunun üzerinde döner). Yüzün vidaları boynun içinden boydan boya geçer; başları kapak pulunun üstünde, pulu da
    sıkar. Pim ekseni dönme eksenine paralel: ileride pimin yerine kola bir solenoid takılabilir.
    """
    body = K.fuse(K.cylinder(disc_r, 0.0, lay["t_s"]), [K.cylinder(geo["r_s"], lay["t_s"] - 0.01, lay["z_sp"])],
                  "tahrik halkası")
    pl = geo["plunger"]
    cuts = [K.cylinder((pl["d1"] + PIN_SLIP) / 2.0, lay["t_s"] - pl["l2"] - 1.0, lay["t_s"] + 1.0, -geo["r_c"], 0.0)]
    cuts += [K.cylinder(M3_CLEAR_R, -1.0, lay["z_sp"] + 1.0, x, y) for x, y in screw_pts]
    return K.cut(body, cuts, "tahrik halkası delikleri")


# ─── Dönen gövde (çember çıkışı): sabit taban, tambur, tambur kolu ───────────

RIM_T = 3.0           # vinç tamburu kenar kalınlığı
JOIN_NUT_FLOOR = 1.2  # balıksırtı tambur birleşim somunu: yuvanın altında kalan et


def build_ring_base(hd: Dict, z0: float, t: float, hole_r: float, pin_centers: Sequence[Tuple[float, float]],
                    pin_hole_d: float, tie: Dict, counterbore: float, female_spigot: bool, nut_pocket: bool = False):
    """
    Dönen gövdenin sabit taban plakası (son kademenin sabit taşıyıcısının alt plakası): sabit çember gövdeyi
    (veya tek kademede motor flanşını) kapatır, pimler buna preslenir. Bağlantı cıvatalarının başları yüzeyin
    altına gömülür — tambur hemen üstünde döner. Ortadaki delikten güneş (ve 1. kademede motor bileziği) geçer.
    """
    z1 = z0 + t
    holes = [K.circle_wire(hole_r)] + [K.circle_wire(tie["hole"] / 2.0, x, y) for x, y in hd["positions"]]
    body = _lugged_plate(hd, True, z0, z1, holes)
    tools = [K.cylinder(pin_hole_d / 2.0, z0 - 1.0, z1 + 1.0, x, y) for x, y in pin_centers]
    if counterbore > 0.05:
        # bolt head counterbore, or a socket-wrench pocket around the top nut of a threaded rod
        r_cb = (tie["nut_s"] * 2.0 / math.sqrt(3.0) + 3.0) / 2.0 if nut_pocket else tie["head_d"] / 2.0 + 0.3
        for x, y in hd["positions"]:
            tools.append(K.cylinder(r_cb, z1 - counterbore, z1 + 1.0, x, y))
    if female_spigot:
        tools.append(spigot_female(hd, z0))
    return K.cut(body, tools, "taban plakası")


def build_drum_tube(geo, pressure_angle: float, backlash: float, zs: Sequence[float], angles: Sequence[float],
                    drum_r: float):
    """Tamburun dişli borusu: içte çember dişleri (düz / balıksırtı bölümü), dışta Ø2·drum_r silindir."""
    hd_d = {"wall_r": drum_r, "positions": [], "lug_r": 1.0, "root_r": geo.root_ring}
    solid, _ = build_ring_section(geo, pressure_angle, backlash, zs, angles, hd_d, False, 0.0, False, False)
    return solid


def build_drum_part(geo, pressure_angle: float, backlash: float, zs: Sequence[float], angles: Sequence[float],
                    drum_r: float, lid: Optional[Tuple[float, float]] = None, pocket_r: float = 0.0,
                    pocket_depth: float = 0.0, extras: Sequence = (), cuts: Sequence = ()):
    """
    Tambur (veya balıksırtında tamburun bir yarısı): dişli boru + isteğe bağlı kapak (lid = (alt, üst) kotu),
    kapağın altında tambur rulmanı yuvası; `extras` (vinç kenarları) eklenir, `cuts` (vida delikleri, somun
    yuvaları, halat deliği) kesilir.
    """
    body = build_drum_tube(geo, pressure_angle, backlash, zs, angles, drum_r)
    adds = list(extras)
    if lid is not None:
        adds.insert(0, K.cylinder(drum_r, lid[0], lid[1]))
    if adds:
        body = K.fuse(body, adds, "tambur kapağı")
    tools = list(cuts)
    if lid is not None and pocket_r > 0:
        tools.append(K.cylinder(pocket_r, lid[0] - 1.0, lid[0] + pocket_depth))
    return K.cut(body, tools, "tambur") if tools else body


def winch_rims(drum_r: float, rim: float, z_bottom: float, z_top: float, chamfer: bool):
    """
    Vinç tamburu kenarları (halka): altta ve üstte drum_r + rim yarıçaplı. `chamfer`: alt kenarın üst yüzü
    45° koni — tambur kapağı tablada basılırken bu kenar desteksiz çıkar.
    """
    lo = annulus(drum_r - 1.0, drum_r + rim, z_bottom, z_bottom + RIM_T)
    if chamfer:
        cone = K.cone(drum_r + rim, drum_r - 0.5, z_bottom + RIM_T, z_bottom + RIM_T + rim + 0.5)
        lo = K.fuse(lo, [K.cut(cone, [K.cylinder(drum_r - 1.0, z_bottom, z_bottom + RIM_T + rim + 2.0)],
                                "kenar pahı")], "alt kenar", unify=True)
    hi = annulus(drum_r - 1.0, drum_r + rim, z_top - RIM_T, z_top)
    return [lo, hi]


def rope_hole(drum_r: float, rope_d: float, z_top: float):
    """Halat bağlama deliği: üst kenarda, tambur yüzeyine teğet, eksene paralel."""
    r = rope_d / 2.0 + 0.3
    return K.cylinder(r, z_top - RIM_T - 1.0, z_top + 1.0, drum_r + r, 0.0)


def lid_screw_cuts(points: Sequence[Tuple[float, float]], z_top: float, reach_r: float, fastener: str) -> List:
    """Tambur kapağındaki vida yuvaları (çıkış flanşıyla aynı): yandan takılan somun veya ısıl burç."""
    return _hub_fastener_cuts(points, z_top, NUT_ROOF_FLANGE, reach_r, fastener)


def lid_nut_seats(points: Sequence[Tuple[float, float]], z_top: float) -> List[Tuple[float, float, float, float]]:
    z = _nut_pocket_z(z_top, NUT_ROOF_FLANGE) + 0.15
    return [(x, y, z, math.atan2(y, x) + math.pi / 6.0) for x, y in points]


def join_screw_fit(z_lid_top: float, z_drum_bottom: float, lid_t: float,
                   lengths: Sequence[float] = (8, 10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60)) -> Tuple[float, float, float]:
    """
    Balıksırtı tamburun iki yarısını birleştiren M3 vida: kapaktan girer (baş havşası c derinliğinde),
    alt yarının tabanına yakın yandan takılan somuna geçer. Uç, somunu geçip tambur tabanından taşmaz;
    standart boy farkını havşa derinliği karşılar. Döndürür: (boy, havşa derinliği, somun yuvası taban kotu)
    """
    z_nb = z_drum_bottom + JOIN_NUT_FLOOR
    tip_lo, tip_hi = z_drum_bottom + 0.3, z_nb + 0.15 + M3_NUT_M - 0.6   # through the nut, not out of the drum
    c_lo, c_hi = M3_HEAD_DEPTH, max(M3_HEAD_DEPTH, lid_t - 2.0)
    best = None
    for L in lengths:
        lo = max(c_lo, z_lid_top - L - tip_hi)
        hi = min(c_hi, z_lid_top - L - tip_lo)
        if lo <= hi + 1e-9:
            return float(L), round(lo, 2), z_nb
        if best is None or abs((z_lid_top - L - tip_lo) - c_hi) < abs((z_lid_top - best - tip_lo) - c_hi):
            best = L
    c = min(c_hi, max(c_lo, z_lid_top - best - tip_lo))
    return float(best), round(c, 2), z_nb


def join_cuts_upper(points: Sequence[Tuple[float, float]], z_apex: float, z_lid_top: float, c: float) -> List:
    tools = []
    for x, y in points:
        tools.append(K.cylinder(M3_CLEAR_R, z_apex - 1.0, z_lid_top + 1.0, x, y))
        tools.append(K.cylinder(M3_HEAD_R, z_lid_top - c, z_lid_top + 1.0, x, y))
    return tools


def join_cuts_lower(points: Sequence[Tuple[float, float]], z_bottom: float, z_apex: float, z_nb: float,
                    reach_r: float) -> List:
    tools = []
    for x, y in points:
        tools.append(K.cylinder(1.6, z_bottom - 1.0, z_apex + 1.0, x, y))      # Ø3.2: aligns the two halves
        tools.append(_nut_slot(x, y, M3_NUT_S, M3_NUT_M, z_nb, reach_r))
    return tools


def build_drum_arm(shape: str, length: float, width: float, thickness: float, hub_r: float,
                   screw_pts: Sequence[Tuple[float, float]]) -> Tuple[object, float]:
    """
    Tambur kapağına vidalanan çıkış kolu (alt yüzü z=0, +X yönünde): kapak vida dairesini örten göbek diski +
    yassı / yuvarlak kol; vidalar göbekte havşalı. Torku vida dairesi taşır (büyük yarıçapta, ezilme kontrollü).
    Döndürür: (katı, göbek yüksekliği)
    """
    tb = drum_arm_height(shape, width, thickness)
    tools = []
    if shape == "ROUND":
        d = width
        zc = 0.46 * d
        L = max(length, hub_r + 0.6 * d)
        rod = K.cylinder_along(d / 2.0, (0.0, 0.0, zc), (1.0, 0.0, 0.0), L + 0.6 * d)
        rod = K.cut(rod, [K.extrude(K.planar_face(K.polygon_wire(
            [(-1.0, -d), (L + d, -d), (L + d, d), (-1.0, d)])), -d, 0.0)], "kol düzlüğü")
        tools.append(rod)
        hole_r = min(4.25, max(1.7, 0.175 * d))
    else:
        w, t = width, thickness
        L = max(length, hub_r + 0.6 * w)
        tools.append(K.extrude(K.planar_face(K.polygon_wire([(0.0, -w / 2.0), (L, -w / 2.0), (L, w / 2.0),
                                                            (0.0, w / 2.0)])), 0.0, t))
        tools.append(K.cylinder(w / 2.0, 0.0, t, L, 0.0))
        hole_r = min(4.25, max(1.7, 0.175 * w))
    body = K.fuse(K.cylinder(hub_r, 0.0, tb), tools, "tambur kolu", unify=True)
    cuts = [K.cylinder(hole_r, -1.0, tb + 1.0, L, 0.0)]
    for x, y in screw_pts:
        cuts.append(K.cylinder(M3_CLEAR_R, -1.0, tb + 1.0, x, y))
        cuts.append(K.cylinder(M3_HEAD_R, tb - M3_HEAD_DEPTH, tb + 1.0, x, y))
    return K.cut(body, cuts, "tambur kolu delikleri"), tb


# ─── Motor flanşı, kapak ─────────────────────────────────────────────────────

def _nut_slot(x: float, y: float, s: float, m: float, z_bottom: float, lug_r: float):
    """Kulak içinde yandan (dışarıdan) takılan altıgen somun yuvası."""
    ang = math.atan2(y, x)
    w = s / 2.0 + 0.15
    back = s / math.sqrt(3.0) + 0.2          # altıgenin köşesi yuvanın iç ucuna değmesin
    length = lug_r + s
    slot = K.polygon_wire([(-back, -w), (length, -w), (length, w), (-back, w)])
    solid = K.extrude(K.planar_face(slot), z_bottom, z_bottom + m + 0.3)
    return K.transform(solid, K.trsf_place(x, y, 0.0, ang))


def build_motor_flange(hd: Dict, thickness: float, center_hole_r: float, motor: Dict, tie: Dict,
                       nut_z_bottom: float, male_spigot: bool):
    """
    Motor montaj flanşı — z: [-t, 0]. Kulaklı gövde konturu ∪ motor flanş karesi; motor vidaları
    için üstten havşa (başlar dişli boşluğuna taşmaz), pilot çıkıntısı için alttan havşa,
    bağlantı cıvataları için yandan takılan somun yuvaları.
    """
    z0, z1 = -thickness, 0.0
    body = _lugged_plate(hd, True, z0, z1)
    size = float(motor.get("flange_size", 0.0))
    extras = []
    if size / 2.0 * math.sqrt(2.0) > hd["wall_r"] + 0.5:
        extras.append(K.extrude(K.planar_face(P.rounded_square(size, 4.0)), z0, z1))
    if male_spigot:
        extras.append(spigot_male(hd, z1))
    if extras:
        body = K.fuse(body, extras, "motor flanşı", unify=True)
    tools = [K.cylinder(center_hole_r, z0 - 1.0, z1 + 2.0)]
    for x, y in hd["positions"]:
        tools.append(K.cylinder(tie["hole"] / 2.0, z0 - 1.0, z1 + 2.0, x, y))
        tools.append(_nut_slot(x, y, tie["nut_s"], tie["nut_m"], nut_z_bottom, hd["lug_r"]))
    pcd_r = float(motor.get("bolt_pitch_circle", 0.0)) / 2.0
    hole_r = float(motor.get("bolt_hole_dia", 3.4)) / 2.0
    head_r = float(motor.get("screw_head_dia", 5.5)) / 2.0 + 0.3
    head_h = float(motor.get("screw_head_h", 3.0)) + 0.3
    for i in range(4):
        x, y = _polar_xy(pcd_r, math.pi / 4.0 + i * math.pi / 2.0)
        tools.append(K.cylinder(hole_r, z0 - 1.0, z1 + 2.0, x, y))
        tools.append(K.cylinder(head_r, z1 - head_h, z1 + 2.0, x, y))
    pilot_r = float(motor.get("pilot_diameter", 0.0)) / 2.0 + 0.2
    pilot_depth = float(motor.get("pilot_depth", 0.0)) + 0.3
    if pilot_r > center_hole_r and pilot_depth < thickness - 1.0:
        tools.append(K.cylinder(pilot_r, z0 - 1.0, z0 + pilot_depth))
    return K.cut(body, tools, "flanş delikleri")


def build_top_cover(hd: Dict, z0: float, thickness: float, seat_d: float, seat_depth: float, hub_hole_r: float,
                    tie: Dict, counterbore: float, female_spigot: bool):
    """Üst kapak: çıkış rulmanı yuvası (alttan), göbek deliği, cıvata delikleri (+ baş havşası)."""
    z1 = z0 + thickness
    holes = [K.circle_wire(hub_hole_r)] + [K.circle_wire(tie["hole"] / 2.0, x, y) for x, y in hd["positions"]]
    body = _lugged_plate(hd, True, z0, z1, holes)
    tools = [K.cylinder(seat_d / 2.0, z0 - 1.0, z0 + seat_depth)]
    if counterbore > 0.05:
        for x, y in hd["positions"]:
            tools.append(K.cylinder(tie["head_d"] / 2.0 + 0.3, z1 - counterbore, z1 + 1.0, x, y))
    if female_spigot:
        tools.append(spigot_female(hd, z0))
    return K.cut(body, tools, "kapak yuvaları")


# ─── Satın alınan / küçük parçalar ───────────────────────────────────────────

def build_bearing(d: float, D: float, B: float):
    """Sızdırmaz bilyalı rulman (sadeleştirilmiş): iç/dış bilezik + iki yüzde kapak çukuru."""
    body = annulus(d / 2.0, D / 2.0, 0.0, B)
    w = (D - d) / 2.0
    r1, r2 = d / 2.0 + 0.3 * w, D / 2.0 - 0.22 * w
    depth = min(0.25, B * 0.06)
    return K.cut(body, [annulus(r1, r2, -1.0, depth), annulus(r1, r2, B - depth, B + 1.0)], "rulman kapakları")


def build_pin(d: float, length: float, flat: bool = False):
    """Çelik silindirik pim (ISO 8734) veya yatay basılacak D-düzlüklü baskı pimi."""
    if flat:
        return K.extrude(K.planar_face(P.shaft_section(d, "D_CUT", 0.08 * d, 0.0)), 0.0, length)
    return K.cylinder(d / 2.0, 0.0, length)


def build_spacer(d_in: float, d_out: float, t: float):
    return annulus(d_in / 2.0, d_out / 2.0, 0.0, t)


def build_socket_bolt(tie: Dict, length: float):
    """ISO 4762 imbus cıvata (orijinde: baş alt yüzü z=0, gövde -z yönünde)."""
    shank = K.cylinder(tie["d"] / 2.0, -length, 0.1)
    head = K.cylinder(tie["head_d"] / 2.0, 0.0, tie["head_h"])
    sock = K.extrude(K.planar_face(K.polygon_wire([_polar_xy(tie["d"] * 0.46, i * math.pi / 3) for i in range(6)])),
                     tie["head_h"] * 0.4, tie["head_h"] + 1.0)
    return K.cut(K.fuse(shank, [head], "cıvata", unify=True), [sock], "imbus")


def build_hex_nut(tie: Dict):
    r = tie["nut_s"] / math.sqrt(3.0)
    body = K.extrude(K.planar_face(K.polygon_wire([_polar_xy(r, i * math.pi / 3 + math.pi / 6) for i in range(6)])),
                     0.0, tie["nut_m"])
    return K.cut(body, [K.cylinder(tie["d"] / 2.0, -1.0, tie["nut_m"] + 1.0)], "somun")


def build_steel_shaft(d: float, length: float):
    return K.extrude(K.planar_face(P.shaft_section(d, "D_CUT", 0.06 * d, 0.0)), 0.0, length)


def build_snap_circlip(d1: float, d2: float, thickness: float, z_top: float):
    """3D baskılık C-segman (orijinde, ağız +X): z [z_top - s, z_top]."""
    outline, holes = P.snap_circlip(d2, d1 + 2.4)
    return K.extrude(K.planar_face(outline, holes), z_top - thickness, z_top)


# ─── Montaj braketi ──────────────────────────────────────────────────────────

MOUNT_BACK_T = 6.0      # back plate (screwed to the wall / post / floor)
MOUNT_GUSSET_T = 5.0
MOUNT_SCREW_D = 5.5     # wall screws M5 / Ø5 wood screw


def mount_bracket_half(hd: Dict, motor: Dict, tie: Dict) -> float:
    """Half width of the bracket shelf: around the tie rods (with their lugs) and the motor body."""
    reach = max(max(abs(x), abs(y)) for x, y in hd["positions"]) + hd["lug_r"]
    return max(reach, float(motor.get("flange_size", 42.0)) / 2.0 + 6.0)


def mount_bracket_fits(hd: Dict, motor: Dict, tie: Dict) -> bool:
    """The tie rods must pass beside the motor body (small housings bolt through the motor's own holes)."""
    face = float(motor.get("flange_size", 42.0)) / 2.0 + 0.75
    return all(max(abs(x), abs(y)) - tie["hole"] / 2.0 - 1.5 >= face for x, y in hd["positions"])


def _shelf_cuts(hd: Dict, motor: Dict, tie: Dict, z0: float, z_top: float) -> List:
    """Motor opening + tie-rod holes + hex nut pockets open from below (as the nuts are placed)."""
    m = float(motor.get("flange_size", 42.0)) / 2.0 + 0.75
    cuts = [K.extrude(K.planar_face(K.polygon_wire([(-m, -m), (m, -m), (m, m), (-m, m)])), z0 - 1.0, z_top + 1.0)]
    nut_r = (tie["nut_s"] + 0.3) / math.sqrt(3.0)
    for x, y in hd["positions"]:
        cuts.append(K.cylinder(tie["hole"] / 2.0, z0 - 1.0, z_top + 1.0, x, y))
        hexw = K.polygon_wire([(x + nut_r * math.cos(math.atan2(y, x) + k * math.pi / 3),
                                y + nut_r * math.sin(math.atan2(y, x) + k * math.pi / 3)) for k in range(6)])
        cuts.append(K.extrude(K.planar_face(hexw), z0 - 1.0, z0 + 3.0 + tie["nut_m"]))
    return cuts


MOUNT_FOOT_T = 6.0      # base stand: foot plate
MOUNT_LEG = 8.0         # base stand: leg section (square)


def build_mount_panel(hd: Dict, motor: Dict, tie: Dict, z_top: float, shelf_t: float) -> Tuple[object, Dict]:
    """
    Panel / plate mount: the shelf grows into a square plate with four counterbored screw holes outside the housing
    lugs; it is screwed onto a panel (table top, wall, machine frame) whose hole the motor passes through.
    """
    h = mount_bracket_half(hd, motor, tie) + 13.0
    z0 = z_top - shelf_t
    body = K.extrude(K.planar_face(K.polygon_wire([(-h, -h), (h, -h), (h, h), (-h, h)])), z0, z_top)
    cuts = _shelf_cuts(hd, motor, tie, z0, z_top)
    s = h - 7.0
    for x in (-s, s):
        for y in (-s, s):
            cuts.append(K.cylinder(MOUNT_SCREW_D / 2.0, z0 - 1.0, z_top + 1.0, x, y))
            cuts.append(K.cylinder(5.2, z_top - 3.5, z_top + 1.0, x, y))
    return K.cut(body, cuts, "panel braketi"), {"half": h, "screw_pitch": 2.0 * s, "z0": z0}


def build_mount_base(hd: Dict, motor: Dict, tie: Dict, z_top: float, shelf_t: float) -> Tuple[object, Dict]:
    """
    Base stand: the shelf under the motor flange on four legs beside the motor body down to a foot frame with four
    screw tabs (motor rear and cable stay free). Stands on a floor / table (axis vertical) or hangs on a wall (axis
    horizontal, output away from the wall). Printed shelf-down.
    """
    m = float(motor.get("flange_size", 42.0)) / 2.0 + 0.75
    h = max(mount_bracket_half(hd, motor, tie), m + 2.0 + MOUNT_LEG)
    z0 = z_top - shelf_t
    zf = z0 - float(motor.get("body_length", 40.0)) - 8.0          # foot underside: motor body + connector room
    shelf = K.extrude(K.planar_face(K.polygon_wire([(-h, -h), (h, -h), (h, h), (-h, h)])), z0, z_top)
    legs = []
    c = h - MOUNT_LEG / 2.0
    for x, y in ((c, 0.0), (-c, 0.0), (0.0, c), (0.0, -c)):
        legs.append(K.extrude(K.planar_face(K.polygon_wire([(x - MOUNT_LEG / 2, y - MOUNT_LEG / 2),
                                                            (x + MOUNT_LEG / 2, y - MOUNT_LEG / 2),
                                                            (x + MOUNT_LEG / 2, y + MOUNT_LEG / 2),
                                                            (x - MOUNT_LEG / 2, y + MOUNT_LEG / 2)])), zf, z0 + 0.01))
    hf = h + 14.0
    foot = K.extrude(K.planar_face(K.polygon_wire([(-hf, -hf), (hf, -hf), (hf, hf), (-hf, hf)])), zf, zf + MOUNT_FOOT_T)
    body = K.fuse(shelf, legs + [foot], "taban braketi")
    cuts = _shelf_cuts(hd, motor, tie, z0, z_top)
    cuts.append(K.extrude(K.planar_face(K.polygon_wire([(-m, -m), (m, -m), (m, m), (-m, m)])), zf - 1.0,
                          zf + MOUNT_FOOT_T + 1.0))
    s = hf - 7.0
    for x in (-s, s):
        for y in (-s, s):
            cuts.append(K.cylinder(MOUNT_SCREW_D / 2.0, zf - 1.0, zf + MOUNT_FOOT_T + 1.0, x, y))
            cuts.append(K.cylinder(5.2, zf + MOUNT_FOOT_T - 3.0, zf + MOUNT_FOOT_T + 1.0, x, y))
    return K.cut(body, cuts, "taban braketi delikleri"), {"half": hf, "screw_pitch": 2.0 * s, "z_foot": zf}


MOUNT_WALL_GAP = 2.0    # side mount: the widest part of the gearbox stays this far from the wall


def build_mount_bracket(hd: Dict, motor: Dict, tie: Dict, z_top: float, shelf_t: float, r_env: float = 0.0,
                        z_up: float = 0.0) -> Tuple[object, Dict]:
    """
    Side mount (L): a shelf under the motor flange with the tie-rod holes, hex nut pockets open from below and a
    square opening for the motor, and a back plate parallel to the axis that stands MOUNT_WALL_GAP outside the widest
    part of the gearbox (`r_env`: housing lugs, cover, a turning drum) — the gearbox body never touches the wall. The
    back plate reaches from below the motor up along the housing (`z_up`), so the wall screws sit far apart (small
    pull-out force from the tipping moment); the four screws lie beside the housing / motor silhouette, where a
    screwdriver reaches them from the front. Two gussets under the shelf. Printed shelf-down.
    """
    h = mount_bracket_half(hd, motor, tie)
    m = float(motor.get("flange_size", 42.0)) / 2.0 + 0.75
    off = max(h, r_env + MOUNT_WALL_GAP)                    # axis -> inner face of the back plate
    z0 = z_top - shelf_t
    body_len = float(motor.get("body_length", 40.0))
    zb = z_top - (body_len + shelf_t + 6.0)                  # back plate bottom: below the motor body
    zt = max(z_top, z_up)                                    # back plate top: along the housing
    sx = max(h, m, r_env) + 6.0                              # wall screws beside the silhouette
    w = sx + 6.0                                             # back plate half width
    shelf = K.extrude(K.planar_face(K.polygon_wire([(-h, -off), (h, -off), (h, h), (-h, h)])), z0, z_top)
    back = K.extrude(K.planar_face(K.polygon_wire([(-w, -off - MOUNT_BACK_T), (w, -off - MOUNT_BACK_T), (w, -off),
                                                   (-w, -off)])), zb, zt)
    g_len, g_h = off + 0.6 * h, (z0 - zb) - 2.0
    gussets = []
    for x0 in (-h, h - MOUNT_GUSSET_T):
        tri = K.polygon_wire([(-off, z0), (-off, z0 - g_h), (-off + g_len, z0)])
        g = K.prism(K.planar_face(tri), MOUNT_GUSSET_T)    # triangle in the XY plane, extruded along +Z
        # map (x, y, z) -> (x0 + z, x, y): the triangle (y, z) lies in the YZ plane, thickness along X
        g = K.transform(g, K.trsf_rotate_axis((0, 0, 0), (1, 1, 1), 2.0 * math.pi / 3.0))
        gussets.append(K.translate(g, x0, 0.0, 0.0))
    body = K.fuse(shelf, [back] + gussets, "montaj braketi")
    cuts = _shelf_cuts(hd, motor, tie, z0, z_top)
    cuts[0] = K.extrude(K.planar_face(K.polygon_wire([(-m, -m), (m, -m), (m, m), (-m, m)])), zb - 1.0, z_top + 1.0)
    zs = (zt - 10.0, zb + 10.0)
    for x in (-sx, sx):
        for z in zs:
            cuts.append(K.cylinder_along(MOUNT_SCREW_D / 2.0, (x, -off - MOUNT_BACK_T - 1.0, z), (0.0, 1.0, 0.0),
                                         MOUNT_BACK_T + 2.0))
            cuts.append(K.cylinder_along(5.2, (x, -off - 3.0, z), (0.0, 1.0, 0.0), 4.0))   # head counterbore
    shape = K.cut(body, cuts, "montaj braketi delikleri")
    return shape, {"half": h, "offset": off, "screw_dx": 2.0 * sx, "screw_dz": zs[0] - zs[1], "z0": z0}
