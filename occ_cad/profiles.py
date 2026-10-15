# -*- coding: utf-8 -*-
"""
2B profiller: evolvent dişli konturları, mil/göbek kesitleri, kulaklı gövde konturu, segman.

Diş geometrisi Fusion eklentisiyle aynı kaynaktan (core.tooth_profile) gelir; tek fark,
Fusion'da tek diş çizilip "circular pattern" ile çoğaltılırken burada tüm dişlerin
tek bir kapalı tel olarak kurulmasıdır (OCCT'de 10-30 kat hızlı ve boolean gerektirmez).
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from core.tooth_profile import ToothProfileGenerator

from .kernel import (GeometryError, arc_edge, circle_wire, line_edge, make_wire, pnt, polar,
                     spline_edge)

FLANK_POINTS = 16


def _inv(base_r: float, r: float) -> float:
    """Evolvent fonksiyonu: taban dairesinden r yarıçapına kadar kutupsal açı artışı."""
    if r <= base_r:
        return 0.0
    a = math.acos(base_r / r)
    return math.tan(a) - a


def _flank_top(base_r: float, rot: float, r_start: float, r_end: float, min_half: float) -> float:
    """
    Kanat (negatif tarafta) açı = rot + inv(r). Karşı kanatla kesişmemesi için açı -min_half'ı
    geçtiği yarıçapta kanat kırpılır (sivri diş / sivri boşluk koruması).
    """
    if rot + _inv(base_r, r_end) <= -min_half:
        return r_end
    lo, hi = r_start, r_end
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if rot + _inv(base_r, mid) <= -min_half:
            lo = mid
        else:
            hi = mid
    return lo


def _flank_polar(base_r: float, rot: float, r_start: float, r_end: float, n: int) -> List[Tuple[float, float]]:
    """(yarıçap, açı) listesi; taban dairesine yakın bölgede noktalar sıklaştırılır."""
    pts = []
    near_base = (r_start - base_r) < 0.02 * max(r_end - r_start, 1e-6)
    for i in range(n):
        s = i / (n - 1)
        if near_base:
            s = s ** 1.6
        r = r_start + (r_end - r_start) * s
        pts.append((r, rot + _inv(base_r, r)))
    return pts


def _arc_mid(a0: float, a1: float) -> float:
    """a0'dan a1'e saat yönünün tersine giden yayın orta açısı."""
    return a0 + ((a1 - a0) % (2.0 * math.pi)) / 2.0


def _flank_xy(rb: float, rot: float, r: float) -> Tuple[float, float]:
    ang = rot + _inv(rb, r) if r > rb else rot
    return r * math.cos(ang), r * math.sin(ang)


def _flank_normal(rb: float, rot: float, r: float, toward_negative: bool) -> Tuple[float, float]:
    """Kanadın birim normali; toward_negative=True ise açının azaldığı tarafa bakar."""
    if r <= rb + 1e-9:
        nx, ny = math.sin(rot), -math.cos(rot)
    else:
        h = max(1e-5, 1e-4 * r)
        x1, y1 = _flank_xy(rb, rot, max(rb + 1e-9, r - h))
        x2, y2 = _flank_xy(rb, rot, r + h)
        tx, ty = x2 - x1, y2 - y1
        ln = math.hypot(tx, ty)
        nx, ny = ty / ln, -tx / ln
        px, py = _flank_xy(rb, rot, r)
        th = math.atan2(py, px)
        if nx * -math.sin(th) + ny * math.cos(th) > 0:     # açısal bileşen pozitif -> çevir
            nx, ny = -nx, -ny
    return (nx, ny) if toward_negative else (-nx, -ny)


def _solve_fillet(rb: float, rot: float, r_lo: float, r_hi: float, rho_target: float, root_r: float,
                  external: bool, q_limit: float):
    """
    Kanada ve kök dairesine teğet yay. Dış dişlide yay boşlukta, kök dairesine dıştan teğet;
    iç dişlide (çember) boşluk tarafında, kök dairesine içten teğettir.
    q_limit: Q noktasının açısı için sınır (dış: Q > q_limit, iç: Q < q_limit).
    """
    def at(r):
        px, py = _flank_xy(rb, rot, r)
        nx, ny = _flank_normal(rb, rot, r, toward_negative=external)
        pn = px * nx + py * ny
        p2 = px * px + py * py
        if external:
            den = 2.0 * (root_r - pn)
            rho = (p2 - root_r ** 2) / den if den > 1e-12 else 0.0
        else:
            den = 2.0 * (pn + root_r)
            rho = (root_r ** 2 - p2) / den if den > 1e-12 else 0.0
        cx, cy = px + rho * nx, py + rho * ny
        cl = math.hypot(cx, cy)
        qx, qy = cx * root_r / cl, cy * root_r / cl
        return rho, (px, py), (cx, cy), (qx, qy)

    def q_ok(r):
        _, _, _, (qx, qy) = at(r)
        a = math.atan2(qy, qx)
        return a > q_limit if external else a < q_limit

    if r_hi - r_lo < 1e-4:
        return None
    # dış: rho r ile artar; iç: rho r ile azalır
    near, far = (r_lo, r_hi) if external else (r_hi, r_lo)
    if at(far)[0] <= rho_target:
        r_t = far
    else:
        a, b = near, far
        for _ in range(60):
            mid = 0.5 * (a + b)
            if at(mid)[0] < rho_target:
                a = mid
            else:
                b = mid
        r_t = 0.5 * (a + b)
    if not q_ok(r_t):
        a, b = near, r_t
        if not q_ok(near):
            return None
        for _ in range(60):
            mid = 0.5 * (a + b)
            if q_ok(mid):
                a = mid
            else:
                b = mid
        r_t = a
    rho, p, c, q = at(r_t)
    if rho < 0.02:
        return None
    vx, vy = (p[0] - c[0]) + (q[0] - c[0]), (p[1] - c[1]) + (q[1] - c[1])
    vl = math.hypot(vx, vy)
    mid = (c[0] + rho * vx / vl, c[1] + rho * vy / vl)
    return {"r_t": r_t, "rho": rho, "P": p, "Q": q, "M": mid}


def _tooth_flank(rb: float, rot: float, r_root_side: float, r_tip_side: float, n_points: int, fillet):
    """
    Negatif taraftaki kanadın parçaları (yerel koordinat), kökten uca doğru:
    [('arc', Q, M, P)] [('line', A, B)] ('spline', [...]) -> (parçalar, başlangıç, bitiş)
    """
    segs = []
    if fillet is not None:
        segs.append(("arc", fillet["Q"], fillet["M"], fillet["P"]))
        r0 = fillet["r_t"]
        first = fillet["Q"]
    else:
        r0 = r_root_side
        first = None
    if r0 < rb - 1e-9:                                  # taban dairesi altında radyal kanat
        a = fillet["P"] if fillet is not None else (r0 * math.cos(rot), r0 * math.sin(rot))
        b = (rb * math.cos(rot), rb * math.sin(rot))
        segs.append(("line", a, b))
        first = first or a
        r0 = rb
    pts = []
    near_base = (r0 - rb) < 0.02 * max(r_tip_side - r0, 1e-6)
    for i in range(n_points):
        s = i / (n_points - 1)
        if near_base:
            s = s ** 1.6
        pts.append(_flank_xy(rb, rot, r0 + (r_tip_side - r0) * s))
    if fillet is not None and abs(r0 - fillet["r_t"]) < 1e-9:
        pts[0] = fillet["P"]
    segs.append(("spline", pts))
    first = first or pts[0]
    return segs, first, pts[-1]


def _emit(segs, a: float, mirror: bool, reverse: bool):
    """Yerel parçaları döndürüp (ve aynalayıp) OCC kenarlarına çevirir."""
    c, s = math.cos(a), math.sin(a)

    def tp(xy):
        x, y = xy[0], (-xy[1] if mirror else xy[1])
        return pnt(x * c - y * s, x * s + y * c)

    order = list(reversed(segs)) if reverse else segs
    edges = []
    for seg in order:
        if seg[0] in ("arc", "arc_out"):
            q, m, p = seg[1], seg[2], seg[3]          # parça yönü: q -> p
            edges.append(arc_edge(tp(p), tp(m), tp(q)) if reverse else arc_edge(tp(q), tp(m), tp(p)))
        elif seg[0] == "line":
            a_, b_ = seg[1], seg[2]
            edges.append(line_edge(tp(b_), tp(a_)) if reverse else line_edge(tp(a_), tp(b_)))
        else:
            pts = [tp(p) for p in seg[1]]
            edges.append(spline_edge(list(reversed(pts)) if reverse else pts))
    return edges


def _ring_of_teeth(z: int, phase: float, segs, first, top, r_top_arc: float, r_root_arc: float):
    """Diş/boşluk kanatlarından kapalı tel: kanat1 -> uç yayı -> kanat2 -> kök yayı -> sonraki."""
    pitch_ang = 2.0 * math.pi / z
    edges = []
    first_pt = None
    prev_end = None
    for k in range(z):
        a = phase + k * pitch_ang
        c, s = math.cos(a), math.sin(a)
        rot_pt = lambda xy, mir=False: pnt(xy[0] * c - (-xy[1] if mir else xy[1]) * s,
                                           xy[0] * s + (-xy[1] if mir else xy[1]) * c)
        start, end = rot_pt(first), rot_pt(first, True)
        tooth = _emit(segs, a, mirror=False, reverse=False)
        tooth.append(arc_edge(rot_pt(top), polar(r_top_arc, a), rot_pt(top, True)))
        tooth += _emit(segs, a, mirror=True, reverse=True)
        if prev_end is None:
            first_pt = start
        else:
            a0 = math.atan2(prev_end.Y(), prev_end.X())
            a1 = math.atan2(start.Y(), start.X())
            edges.append(arc_edge(prev_end, polar(r_root_arc, _arc_mid(a0, a1)), start))
        edges.extend(tooth)
        prev_end = end
    a0 = math.atan2(prev_end.Y(), prev_end.X())
    a1 = math.atan2(first_pt.Y(), first_pt.X())
    edges.append(arc_edge(prev_end, polar(r_root_arc, _arc_mid(a0, a1)), first_pt))
    return make_wire(edges)


FILLET_FACTOR = 0.35   # kök radyüsü hedefi = 0.35 m (ISO kremayer uç radyüsü 0.38 m)


def external_gear(z: int, module: float, pressure_angle: float = 20.0, backlash: float = 0.05,
                  phase: float = 0.0, n_points: int = FLANK_POINTS, tip_r: Optional[float] = None,
                  form_r: Optional[float] = None, fillet: bool = True, addendum: float = 1.0, shift: float = 0.0):
    """
    Dış dişli (güneş / planet) tam konturu. Diş 0, `phase` açısında merkezlenir.
    shift : profil kaydırma katsayısı x (uç ve kök +x·m, diş kalınlığı m (π/2 + 2x·tanα))
    tip_r : girişimi önlemek için kırpılmış uç yarıçapı (core.gear_geometry)
    form_r: eşleşen dişin temas ettiği en alt yarıçap; kök radyüsü bunun altında kalır
    addendum: diş yüksekliği katsayısı h_a* (diş başı h_a*·m, diş dibi (h_a* + 0.157)·m)
    Döndürür: (tel, bilgi sözlüğü [mm])
    """
    z = int(z)
    g = ToothProfileGenerator.get_external_tooth_features(z, module, pressure_angle, backlash, addendum=addendum,
                                                          shift=shift)
    rb, rr = g['base_r_cm'] * 10.0, g['root_r_cm'] * 10.0
    ro, rp = g['outside_r_cm'] * 10.0, g['pitch_r_cm'] * 10.0
    if tip_r is not None:
        ro = min(ro, tip_r)
    p0 = g['spline1_pts'][0]
    rot = math.atan2(p0[1], p0[0])                       # taban dairesindeki kanat başlangıç açısı
    pitch_ang = 2.0 * math.pi / z
    r_top = _flank_top(rb, rot, max(rb, rr), ro, 0.02 * pitch_ang)
    fil = None
    if fillet:
        f_r = rb if form_r is None else form_r
        r_hi = min(f_r - 0.02 * module, r_top - 0.05 * module)
        fil = _solve_fillet(rb, rot, rr + 1e-4, r_hi, FILLET_FACTOR * module, rr, True,
                            -pitch_ang / 2.0 + 0.04 * pitch_ang)
    segs, first, top = _tooth_flank(rb, rot, rr, r_top, n_points, fil)
    wire = _ring_of_teeth(z, phase, segs, first, top, r_top, rr)
    info = {'pitch_r': rp, 'root_r': rr, 'base_r': rb, 'outside_r': ro, 'tip_r_effective': r_top,
            'pointed': r_top < ro - 1e-6, 'fillet_r': fil["rho"] if fil else 0.0}
    return wire, info


def internal_gear(z: int, module: float, pressure_angle: float = 20.0, backlash: float = 0.05,
                  phase: float = 0.0, n_points: int = FLANK_POINTS, tip_r: Optional[float] = None,
                  form_r: Optional[float] = None, fillet: bool = True, addendum: float = 1.0, shift: float = 0.0):
    """
    İç dişli (çember) boşluk konturu: gövdeden çıkarılacak bölgenin sınırı.
    shift : çemberin profil kaydırması (planetinkiyle aynı; boşluk planet dişine uyar)
    Diş boşluğu 0, `phase` açısında merkezlenir (Fusion eklentisiyle aynı yerleşim).
    tip_r : girişimi önlemek için yükseltilmiş iç uç yarıçapı
    form_r: planet ucunun çember üzerinde temas ettiği en büyük yarıçap (radyüs bunun dışında)
    addendum: diş yüksekliği katsayısı h_a* (iç uç r - h_a*·m, boşluk dibi r + (h_a* + 0.25)·m)
    Döndürür: (tel, bilgi sözlüğü [mm])
    """
    z = int(z)
    g = ToothProfileGenerator.get_internal_tooth_space_features(z, module, pressure_angle, backlash,
                                                                addendum=addendum, shift=shift)
    rb = g['base_r_cm'] * 10.0
    rt = g['tip_r_cm'] * 10.0                             # iç diş uç dairesi (gövde deliği)
    rr = g['root_r_cm'] * 10.0                            # boşluk dibi
    rp = g['pitch_r_cm'] * 10.0
    p0 = g['spline1_pts'][0]
    rot = math.atan2(p0[1], p0[0]) - _inv(rb, max(rb, rt))
    if tip_r is not None:
        rt = max(rt, tip_r)
    pitch_ang = 2.0 * math.pi / z
    r_inv0 = max(rb, rt)
    r_top = _flank_top(rb, rot, r_inv0, rr, 0.02 * pitch_ang)
    fil = None
    if fillet and r_top >= rr - 1e-6:
        f_r = (rr - 0.5 * module) if form_r is None else form_r
        half_space_root = -(rot + _inv(rb, rr))
        fil = _solve_fillet(rb, rot, max(f_r + 0.02 * module, r_inv0 + 0.05 * module), rr - 1e-4,
                            FILLET_FACTOR * module, rr, False, -0.12 * half_space_root)
    # boşluk kanadı: iç uç (rt) -> dış kök (rr); _tooth_flank kökten uca kurar, burada ters yönde
    segs, first, top = _space_flank(rb, rot, rt, r_inv0, r_top, n_points, fil)
    wire = _ring_of_teeth(z, phase, segs, first, top, r_top if fil is None else rr, rt)
    info = {'pitch_r': rp, 'tip_r': rt, 'root_r': rr, 'base_r': rb, 'fillet_r': fil["rho"] if fil else 0.0}
    return wire, info


def _space_flank(rb: float, rot: float, rt: float, r_inv0: float, r_top: float, n_points: int, fillet):
    """İç dişli boşluk kanadı (negatif taraf): iç uç dairesinden dış köke doğru parçalar."""
    segs = []
    first = (rt * math.cos(rot), rt * math.sin(rot))
    if rt < rb - 1e-9:
        b = (rb * math.cos(rot), rb * math.sin(rot))
        segs.append(("line", first, b))
    r_end = fillet["r_t"] if fillet is not None else r_top
    pts = []
    near_base = (r_inv0 - rb) < 0.02 * max(r_end - r_inv0, 1e-6)
    for i in range(n_points):
        s = i / (n_points - 1)
        if near_base:
            s = s ** 1.6
        pts.append(_flank_xy(rb, rot, r_inv0 + (r_end - r_inv0) * s))
    if fillet is not None:
        pts[-1] = fillet["P"]
    segs.append(("spline", pts))
    if rt >= rb - 1e-9:
        first = pts[0]
    top = pts[-1]
    if fillet is not None:
        segs.append(("arc_out", fillet["P"], fillet["M"], fillet["Q"]))
        top = fillet["Q"]
    return segs, first, top


# ─── Mil / göbek kesitleri ───────────────────────────────────────────────────

# DIN 6885 A tipi kama: (mil çapı üst sınırı, kama genişliği b, göbek kanal derinliği t2)
DIN6885 = [(8, 2.0, 1.0), (10, 3.0, 1.4), (12, 4.0, 1.8), (17, 5.0, 2.3), (22, 6.0, 2.8),
           (30, 8.0, 3.3), (38, 10.0, 3.3), (44, 12.0, 3.3), (50, 14.0, 3.8)]


def keyway_dims(shaft_dia: float) -> Tuple[float, float]:
    for limit, b, t2 in DIN6885:
        if shaft_dia <= limit:
            if shaft_dia < 6.0:
                return max(1.0, round(shaft_dia * 0.3, 1)), max(0.6, round(shaft_dia * 0.15, 1))
            return b, t2
    return DIN6885[-1][1], DIN6885[-1][2]


def shaft_section(dia: float, kind: str = "ROUND", flat_depth: float = 0.5, tolerance: float = 0.0,
                  cx: float = 0.0, cy: float = 0.0):
    """
    Mil kesiti veya göbek deliği (Fusion: GearBuilder.add_shaft_bore).
    ROUND, D_CUT (düzlük +Y tarafında), DOUBLE_D, KEYWAY (DIN 6885 kanal +Y yönünde).
    `tolerance` yarıçapa eklenir, düzlük derinliği değişmez (Fusion ile aynı).
    """
    r = dia / 2.0 + tolerance
    kind = (kind or "ROUND").upper()
    if kind == "D_CUT" and 0.0 < flat_depth < r:
        y = r - flat_depth
        x = math.sqrt(max(1e-9, r * r - y * y))
        p1, p2 = pnt(cx - x, cy + y), pnt(cx + x, cy + y)
        return make_wire([line_edge(p1, p2), arc_edge(p2, pnt(cx, cy - r), p1)])
    if kind == "DOUBLE_D" and 0.0 < flat_depth < r:
        y = r - flat_depth
        x = math.sqrt(max(1e-9, r * r - y * y))
        a, b = pnt(cx - x, cy + y), pnt(cx + x, cy + y)
        c, d = pnt(cx + x, cy - y), pnt(cx - x, cy - y)
        return make_wire([line_edge(a, b), arc_edge(b, pnt(cx + r, cy), c),
                          line_edge(c, d), arc_edge(d, pnt(cx - r, cy), a)])
    if kind == "KEYWAY":
        b, t2 = keyway_dims(dia)
        hb = b / 2.0 + tolerance
        if hb < r * 0.9:
            y_int = math.sqrt(r * r - hb * hb)
            top = cy + dia / 2.0 + t2 + tolerance
            p_r, p_l = pnt(cx + hb, cy + y_int), pnt(cx - hb, cy + y_int)
            t_r, t_l = pnt(cx + hb, top), pnt(cx - hb, top)
            return make_wire([arc_edge(p_l, pnt(cx, cy - r), p_r), line_edge(p_r, t_r),
                              line_edge(t_r, t_l), line_edge(t_l, p_l)])
    return circle_wire(r, cx, cy)


# ─── Gövde konturu ───────────────────────────────────────────────────────────

def lugged_outline(wall_r: float, lug_centers: Sequence[Tuple[float, float]], lug_r: float):
    """
    Silindirik gövde + cıvata kulakları (Fusion: add_lugs_and_holes_to_body) dış konturu.
    Kulak daireleri ile ana daire analitik olarak kesiştirilir; boolean gerekmez.
    Kulak ana daireyle kesişmiyorsa None döner (çağıran boolean yoluna düşer).
    """
    lugs = []
    for x, y in lug_centers:
        d = math.hypot(x, y)
        if d + lug_r <= wall_r + 1e-6:
            continue                                    # tamamen gövde içinde
        if d - lug_r >= wall_r - 1e-6:
            return None                                 # gövdeden kopuk kulak
        cos_delta = (wall_r ** 2 + d ** 2 - lug_r ** 2) / (2.0 * wall_r * d)
        delta = math.acos(max(-1.0, min(1.0, cos_delta)))
        lugs.append((math.atan2(y, x) % (2 * math.pi), delta, d))
    if not lugs:
        return circle_wire(wall_r)
    lugs.sort()
    for i, (th, de, _) in enumerate(lugs):
        th2, de2, _ = lugs[(i + 1) % len(lugs)]
        if i == len(lugs) - 1:
            th2 += 2.0 * math.pi
        if (th2 - de2) - (th + de) <= 1e-6:
            return None                                 # kulaklar üst üste biniyor
    edges = []
    for i, (th, de, d) in enumerate(lugs):
        a = polar(wall_r, th - de)
        b = polar(wall_r, th + de)
        edges.append(arc_edge(a, polar(d + lug_r, th), b))
        th2, de2, _ = lugs[(i + 1) % len(lugs)]
        c = polar(wall_r, th2 - de2)
        edges.append(arc_edge(b, polar(wall_r, _arc_mid(th + de, th2 - de2)), c))
    return make_wire(edges)


def rounded_square(size: float, corner_r: float):
    """Motor flanşı için köşeleri yuvarlatılmış kare (NEMA flanş formu)."""
    h = size / 2.0
    c = min(corner_r, h * 0.45)
    pts = []
    edges = []
    corners = [(h, h, 0.0), (-h, h, 0.5 * math.pi), (-h, -h, math.pi), (h, -h, 1.5 * math.pi)]
    for x, y, a in corners:
        ccx, ccy = x - math.copysign(c, x), y - math.copysign(c, y)
        p_start = polar(c, a, ccx, ccy)
        p_mid = polar(c, a + math.pi / 4.0, ccx, ccy)
        p_end = polar(c, a + math.pi / 2.0, ccx, ccy)
        pts.append((p_start, p_mid, p_end))
    for i, (p_start, p_mid, p_end) in enumerate(pts):
        edges.append(arc_edge(p_start, p_mid, p_end))
        nxt = pts[(i + 1) % 4][0]
        edges.append(line_edge(p_end, nxt))
    return make_wire(edges)


# ─── Segman ──────────────────────────────────────────────────────────────────

def snap_circlip(d_inner: float, d_outer: float, half_open_deg: float = 35.0):
    """
    3D baskılık C-segman (Fusion: CirclipBuilder.build_3d_circlip_body). Ağız +X yönünde.
    Döndürür: (dış tel, [pense deliği telleri])
    """
    r_in, r_out = d_inner / 2.0, d_outer / 2.0
    if r_out <= r_in:
        raise GeometryError("Segman dış çapı iç çapından büyük olmalı.")
    h = math.radians(half_open_deg)
    o_s, o_e = polar(r_out, h), polar(r_out, -h)
    i_s, i_e = polar(r_in, h), polar(r_in, -h)
    outline = make_wire([
        arc_edge(o_s, pnt(-r_out, 0.0), o_e),
        line_edge(o_e, i_e),
        arc_edge(i_e, pnt(-r_in, 0.0), i_s),
        line_edge(i_s, o_s),
    ])
    holes = []
    hole_r = 0.4
    if (r_out - r_in) > 2.0 * hole_r + 0.4:
        ear_r = (r_in + r_out) / 2.0
        # Delik ağız kenarından en az 0.25 mm içeride kalsın (küçük segmanlarda kenarı kesmesin)
        ang0 = max(h + 0.15, h + (hole_r + 0.25) / ear_r)
        for sign in (1.0, -1.0):
            ang = sign * ang0
            holes.append(circle_wire(hole_r, ear_r * math.cos(ang), ear_r * math.sin(ang)))
    return outline, holes
