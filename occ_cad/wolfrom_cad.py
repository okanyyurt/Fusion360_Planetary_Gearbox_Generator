# -*- coding: utf-8 -*-
"""
Wolfrom redüktörünün CAD'i (core.wolfrom): motor flanşı, sabit çember + çıkış yatağı gövdesi, motor güneşi,
kademeli planetler (alt dişli Zp1 güneş ve sabit çemberle, üst dişli Zp2 çıkış çemberiyle kavrar), serbest kafes
taşıyıcı (iki plaka + çelik pimler + planet başına iki rulman), kapaklı çıkış çemberi (rulmanda veya baskılı kaymalı
yatakta döner), çıkış flanşı burç delikleri veya kapağa vidalı kol, bağlantı cıvataları.

Eksenel yerleşim (z = 0 motor flanşının üstü), core.wolfrom.length_of ile aynı:
    alt plaka [clr, clr + t_bot], alt dişli [z1, z1 + fw], aralık SET_GAP, üst dişli [z2, z2 + fw],
    üst plaka [z2 + fw + clr, + t_top], kapak [z_lid0, + LID_T]
Sabit çemberin dişleri alt dişliyi, çıkış çemberinin dişleri üst dişliyi ve üst plakayı örter; çıkış yatağı
iki çemberin birleşim yükseltisinde, gövdenin üst kovanındadır.
"""
from __future__ import annotations

import math
import time
from typing import Callable, Dict, List, Optional

from core import design as D
from core import wolfrom as W
from core.bearing_catalog import get_bearing_info, inner_race_diameter
from core.materials import get_material
from core.hardware import dowel_is_standard, pick_dowel, tie_rod_choice
from core.layout import mount_window, COLLAR_LEN, bottom_plate_thickness, drum_arm_height
from core.motor_catalog import get_motor_info

from . import kernel as K
from . import parts as B
from . import profiles as P
from .assembly import COLORS, BuildCancelled, BuildResult, Part, bracket_part, drum_declutch_parts, _flip_x

LID_T = 6.0
INSERT_R, INSERT_DEPTH = 2.0, 6.0

NAMES = {
    "tr": {"flange": "Motor Flanşı", "housing": "Sabit Çember + Yatak Gövdesi", "sun": "Güneş Dişli",
           "planet": "Kademeli Planet", "bearing": "Planet Rulmanı", "spacer": "Rulman Ara Halkası",
           "bottom": "Taşıyıcı Alt Plaka", "top": "Taşıyıcı Üst Plaka", "pin": "Pim", "ring2": "Çıkış Çemberi (kapaklı)",
           "out_bearing": "Çıkış Çemberi Rulmanı", "arm": "Çıkış Kolu", "screw": "Kol Vidası M3", "bolt": "Bağlantı Cıvatası",
           "rod": "Bağlantı Saplaması", "nut": "Somun", "g_housing": "Gövde", "g_stage": "Wolfrom Kademesi",
           "g_fast": "Bağlantı Elemanları", "pin_cut": "standart boydan kısaltılır",
           "progress": "Wolfrom redüktörü kuruluyor..."},
    "en": {"flange": "Motor Flange", "housing": "Fixed Ring + Bearing Housing", "sun": "Sun Gear",
           "planet": "Stepped Planet", "bearing": "Planet Bearing", "spacer": "Bearing Spacer",
           "bottom": "Carrier Bottom Plate", "top": "Carrier Top Plate", "pin": "Pin", "ring2": "Output Ring (lidded)",
           "out_bearing": "Output Ring Bearing", "arm": "Output Arm", "screw": "Arm Screw M3", "bolt": "Tie Bolt",
           "rod": "Tie Rod", "nut": "Nut", "g_housing": "Housing", "g_stage": "Wolfrom Stage", "g_fast": "Fasteners",
           "pin_cut": "cut down from a standard length", "progress": "Building the Wolfrom gearbox..."},
}


def generate(config: Dict, progress: Optional[Callable[[str, int], None]] = None,
             cancelled: Optional[Callable[[], bool]] = None) -> BuildResult:
    t_start = time.time()
    lang = "en" if str(config.get("lang", "tr")).lower().startswith("en") else "tr"
    nm = NAMES[lang]

    def report(pct: int):
        if cancelled and cancelled():
            raise BuildCancelled()
        if progress:
            progress(nm["progress"], pct)

    report(5)
    p = D.Params.from_payload(config)
    c = W.resolve(config, p, lang)
    g1, g2, m, n = c["geo1"], c["geo2"], c["module"], c["n"]
    hd, tie, sup, brg = c["hd"], c["hd"]["tie"], c["support"], c["bearing"]
    motor = get_motor_info(p.motor_code)
    pa, bl, fw, clr = p.pressure_angle, p.backlash, p.face_width, D.CLEARANCE
    t_top = W.plate_t(p, fw)
    t_bot = bottom_plate_thickness(t_top)
    z1 = clr + t_bot + clr
    z2 = z1 + fw + W.SET_GAP
    zt0 = z2 + fw + clr
    zt1 = zt0 + t_top
    zr1_top = z1 + fw + (W.SET_GAP - W.RING_GAP) / 2.0
    zb0 = zr1_top + 0.3                                    # output support seat (bearing / plain)
    z_sleeve = zb0 + sup["width"] + 1.0
    z_lid0 = max(zt1 + clr, z_sleeve + 0.6)
    z_lid1 = z_lid0 + LID_T
    head_h = float(motor.get("screw_head_h", 3.0))
    flange_t = max(5.0, float(motor.get("pilot_depth", 0.0)) + 2.5, head_h + 2.0, tie["nut_m"] + 2.9)
    flange_nut_z = -flange_t + 1.8
    nut_z, tip_lo, tip_hi, mount_t = mount_window(flange_t, tie, p.mount)
    bolt_len, counterbore, rod = tie_rod_choice(z_sleeve, tip_lo, tip_hi, min(8.0, z_sleeve - 2.0),
                                                tie["nut_m"])
    parts: List[Part] = []
    g_h, g_s, g_f = nm["g_housing"], nm["g_stage"], nm["g_fast"]

    # motor flange
    report(15)
    collar_r = D._collar_r(p)
    flange = B.build_motor_flange(hd, flange_t, max(7.0, collar_r + 1.0), motor, tie, flange_nut_z, False)
    parts.append(Part("motor_flange", "Motor_Mount_Flange", nm["flange"], "housing", g_h, flange, COLORS["flange"],
                      explode=[(0.0, 0.0, -2.5)]))

    # fixed ring + sleeve of the output support
    report(25)
    outline_body = B._lugged_plate(hd, True, 0.0, z_sleeve)
    ring1_wire, _ = P.internal_gear(g1.z_ring, m, pa, bl, 0.0, tip_r=g1.tip_ring, form_r=g1.form_ring, addendum=g1.addendum)
    cuts = [K.extrude(K.planar_face(ring1_wire), -1.0, zr1_top)]
    rs_in = (sup["d"] + sup["D"]) / 4.0 + 0.5 if sup["kind"] == "BEARING" else sup["d"] / 2.0 - 1.5
    cuts.append(K.cylinder(rs_in, zr1_top - 0.01, zb0 + 0.01))
    cuts.append(K.cylinder(sup["D"] / 2.0 + (p.bearing_tol / 2.0 if sup["kind"] == "BEARING" else 0.0),
                           zb0, z_sleeve + 1.0))
    for x, y in hd["positions"]:
        cuts.append(K.cylinder(tie["hole"] / 2.0, -1.0, z_sleeve + 1.0, x, y))
        if counterbore > 0.05:
            cuts.append(K.cylinder(tie["head_d"] / 2.0 + 0.3, z_sleeve - counterbore, z_sleeve + 1.0, x, y))
    housing = K.cut(outline_body, cuts, "Wolfrom gövdesi")
    parts.append(Part("ring_housing", "Fixed_Ring_Housing", nm["housing"], "housing", g_h, housing, COLORS["housing"]))

    # sun
    report(35)
    sun_phase = math.pi / g1.z_sun if g1.z_planet % 2 == 0 else 0.0
    flat = float(motor.get("default_d_flat_depth", 0.5))
    sun, _ = B.build_motor_sun(g1, fw, z1, pa, bl, 0.0, sun_phase, p.motor_shaft_dia, p.motor_shaft_type, flat,
                               collar_r, COLLAR_LEN)
    parts.append(Part("sun_s1", "Sun_Gear", nm["sun"], "stage1", g_s, sun, COLORS["sun"], explode=[(0.0, 0.0, 3.0)]))

    # stepped planet (identical parts, every one turned by its own phase)
    report(45)
    gear1, _ = B.external_gear_solid(g1.z_planet, m, pa, bl, fw, z1, 0.0, -1.0, 0.0, g1.tip_planet, g1.form_planet,
                                     g1.addendum)
    gear2, _ = B.external_gear_solid(g2.z_planet, m, pa, bl, fw, z2, 0.0, -1.0, 0.0, g2.tip_planet, g2.form_planet,
                                     g2.addendum)
    neck_r = min(g1.root_planet, g2.root_planet) - 0.2
    planet = K.fuse(gear1, [gear2, K.cylinder(neck_r, z1 + fw - 0.01, z2 + 0.01)], "kademeli planet")
    bi = get_bearing_info(brg["code"])
    race_d = inner_race_diameter(bi)
    pocket = brg["pocket"]
    planet = K.cut(planet, [K.cylinder(race_d / 2.0 + 0.3, z1 - 1.0, z2 + fw + 1.0),
                            K.cylinder(pocket / 2.0, z1 - 1.0, z1 + bi["width"]),
                            K.cylinder(pocket / 2.0, z2 + fw - bi["width"], z2 + fw + 1.0)], "planet rulman yuvaları")
    cd = g1.center_distance
    centers = [(cd * math.cos(2 * math.pi * k / n), cd * math.sin(2 * math.pi * k / n)) for k in range(n)]
    turns = c["turns"]
    parts.append(Part("planet_s1", "Stepped_Planet", f"{nm['planet']} Z{g1.z_planet}/{g2.z_planet}", "stage1", g_s,
                      planet, COLORS["planet"],
                      placements=[K.trsf_place(x, y, 0.0, turns[k]) for k, (x, y) in enumerate(centers)],
                      explode=[(math.cos(2 * math.pi * k / n) * 1.6, math.sin(2 * math.pi * k / n) * 1.6, 3.0)
                               for k in range(n)], gear=True))
    bearing = B.build_bearing(bi["d_inner"], bi["d_outer"], bi["width"])
    bpl, spl = [], []
    for x, y in centers:
        bpl += [K.trsf_translate(x, y, z1), K.trsf_translate(x, y, z2 + fw - bi["width"])]
        spl += [K.trsf_translate(x, y, z1 - clr), K.trsf_translate(x, y, z2 + fw)]
    parts.append(Part("bearing_s1", f"Bearing_{brg['code']}", f"{brg['code']} {nm['bearing']}", "stage1", g_s, bearing,
                      COLORS["bearing"], placements=bpl, printable=False,
                      spec=f"{brg['code']} ({bi['d_inner']:g}x{bi['d_outer']:g}x{bi['width']:g})"))
    spacer = B.build_spacer(brg["pin"] + 0.3, race_d - 0.3, clr)
    parts.append(Part("spacer_s1", "Spacer", nm["spacer"], "stage1", g_s, spacer, COLORS["spacer"], placements=spl))

    # free cage carrier
    report(60)
    pin_hole = brg["pin"] + (0.1 if not p.pin_steel else 0.0) + float(config.get("pin_tolerance") or 0.0)
    r_out = min(cd + pin_hole / 2.0 + 2.5, min(g1.tip_ring, g2.tip_ring) - 0.8)
    bottom = B.build_cage_bottom_plate(cd, n, pin_hole, clr, t_bot, max(g1.tip_sun, collar_r) + 0.6, r_out)
    parts.append(Part("carrier_bottom_s1", "Carrier_Bottom", nm["bottom"], "stage1", g_s, bottom, COLORS["carrier"]))
    top = B.build_cage_top_plate(cd, n, pin_hole, zt0, t_top, r_out, cd - pin_hole / 2.0 - 2.0)
    parts.append(Part("carrier_top_s1", "Carrier_Top", nm["top"], "stage1", g_s, top, COLORS["carrier"]))
    need = zt1 - clr
    pin_len = pick_dowel(need, 0.4 * min(t_top, t_bot), max(0.0, clr - 0.3), 0.6 * min(t_top, t_bot)) \
        if p.pin_steel else need - 0.4
    cut_note = (" — " + nm["pin_cut"]) if p.pin_steel and not dowel_is_standard(pin_len) else ""
    parts.append(Part("pin_s1", "Pin", f"{nm['pin']} Ø{brg['pin']:g}×{pin_len:g}", "stage1", g_s,
                      B.build_pin(brg["pin"], pin_len, flat=not p.pin_steel),
                      COLORS["pin"] if p.pin_steel else COLORS["carrier"],
                      placements=[K.trsf_translate(x, y, clr) for x, y in centers], printable=not p.pin_steel,
                      spec=f"ISO 8734 / DIN 6325 Ø{brg['pin']:g} m6 × {pin_len:g} mm{cut_note}" if p.pin_steel else ""))

    # output ring with its lid
    report(72)
    zr2_0 = zb0 if sup["kind"] == "PLAIN" else zr1_top + W.RING_GAP
    r_seat = sup["d"] / 2.0 - (0.05 if sup["kind"] == "BEARING" else 0.0)
    r_up = r_seat + 1.5 if sup["kind"] == "BEARING" else r_seat
    lid_r = hd["wall_r"] if z_lid0 >= z_sleeve + 0.5 else r_up
    ring2 = K.fuse(K.cylinder(r_seat, zr2_0, zb0 + sup["width"] + 0.01),
                   [K.cylinder(r_up, zb0 + sup["width"], z_lid0 + 0.01),
                    K.cylinder(lid_r, z_lid0, z_lid1)], "çıkış çemberi")
    ring2_wire, _ = P.internal_gear(g2.z_ring, m, pa, bl, 0.0, tip_r=g2.tip_ring, form_r=g2.form_ring, addendum=g2.addendum)
    rcuts = [K.extrude(K.planar_face(ring2_wire), zr2_0 - 1.0, z_lid0)]
    bolt_r = max(g2.tip_ring + 3.0, r_up - 6.0) if lid_r > r_up else r_up - 5.0
    pts = [(bolt_r * math.cos(math.pi / 6 + k * math.pi / 3), bolt_r * math.sin(math.pi / 6 + k * math.pi / 3))
           for k in range(6)]
    for x, y in pts:
        rcuts.append(K.cylinder(INSERT_R, z_lid1 - INSERT_DEPTH, z_lid1 + 1.0, x, y))
    ring2 = K.cut(ring2, rcuts, "çıkış çemberi dişleri")
    parts.append(Part("drum", "Output_Ring", nm["ring2"], "output", g_s, ring2, COLORS["housing"],
                      print_trsf=_flip_x(), explode=[(0.0, 0.0, 9.0)], gear=True))
    if sup["kind"] == "BEARING":
        ob = get_bearing_info(sup["code"])
        parts.append(Part("drum_bearing", f"Bearing_{sup['code']}", f"{sup['code']} {nm['out_bearing']}", "output", g_s,
                          B.build_bearing(ob["d_inner"], ob["d_outer"], ob["width"]), COLORS["bearing"],
                          placements=[K.trsf_translate(0, 0, zb0)], printable=False,
                          spec=f"{sup['code']} ({ob['d_inner']:g}x{ob['d_outer']:g}x{ob['width']:g})"))
    if p.output_type == "DRUM_ARM" and p.declutch:
        parts += drum_declutch_parts(p, z_lid1 + 0.4, pts, "INSERT",
                                     c["eng"]["output_torque"] * p.load.application_factor, lang, "output", g_s, 9.0)
    elif p.output_type == "DRUM_ARM":
        arm, arm_h = B.build_drum_arm(p.arm_shape, p.arm_length, p.arm_width, p.arm_thickness, bolt_r + 6.0, pts)
        parts.append(Part("output_arm", "Output_Arm", f"{nm['arm']} {p.arm_length:g} mm", "output", g_s, arm,
                          COLORS["carrier"], placements=[K.trsf_translate(0, 0, z_lid1 + 0.4)],
                          explode=[(0.0, 0.0, 12.0)]))
        parts.append(Part("arm_screw", "Screw_M3_Arm", nm["screw"], "output", g_s,
                          B.build_socket_bolt({"d": 3.0, "head_d": 5.5, "head_h": 3.0}, 10.0), COLORS["bolt"],
                          placements=[K.trsf_translate(x, y, z_lid1 + 0.4 + arm_h - B.M3_HEAD_DEPTH) for x, y in pts],
                          printable=False, spec="ISO 4762 M3 × 10 mm + M3 ısıl burç"))

    # tie bolts / rods with nuts in the motor flange
    report(85)
    if not rod:
        parts.append(Part("tie_rod_bolt", f"Bolt_{hd['tie_rod']}x{bolt_len:g}", f"{hd['tie_rod']}×{bolt_len:g} {nm['bolt']}",
                          "fasteners", g_f, B.build_socket_bolt(tie, bolt_len), COLORS["bolt"],
                          placements=[K.trsf_translate(x, y, z_sleeve - counterbore) for x, y in hd["positions"]],
                          printable=False, spec=f"ISO 4762 {hd['tie_rod']} × {bolt_len:g} mm"))
    else:
        tip = (tip_lo + tip_hi) / 2.0
        parts.append(Part("tie_rod_bolt", f"Rod_{hd['tie_rod']}x{bolt_len:g}", f"{hd['tie_rod']}×{bolt_len:g} {nm['rod']}",
                          "fasteners", g_f, K.cylinder(tie["d"] / 2.0, 0.0, bolt_len), COLORS["bolt"],
                          placements=[K.trsf_translate(x, y, tip) for x, y in hd["positions"]], printable=False,
                          spec=f"DIN 976 {hd['tie_rod']} × {bolt_len:g} mm"))
    parts.append(Part("tie_rod_nut", f"Nut_{hd['tie_rod']}", f"{hd['tie_rod']} {nm['nut']}", "fasteners", g_f,
                      B.build_hex_nut(tie), COLORS["bolt"],
                      placements=[K.trsf_place(x, y, nut_z + 0.15, math.atan2(y, x) + math.pi / 6)
                                  for x, y in hd["positions"]], printable=False, spec=f"ISO 4032 {hd['tie_rod']}"))

    mount_warning = ""
    mount_notes: List[str] = []
    if mount_t > 0:
        bpart = bracket_part(hd, motor, tie, flange_t, mount_t, p.mount_type, lang, g_h, parts, mount_notes)
        if isinstance(bpart, str):
            mount_warning = bpart
        else:
            parts.append(bpart)

    # kinematics: sun 1, carrier c, planets orbit c + spin, output ring c (1 - i0)
    cf = c["carrier"]
    rel = -cf * g1.z_ring / g1.z_planet
    bodies = {"ground": {"type": "ground"}, "input": {"type": "axis", "factor": 1.0},
              "carrier1": {"type": "axis", "factor": cf, "stage": 1},
              "drum": {"type": "axis", "factor": cf * (1.0 - c["i0"]), "stage": 1}}
    for k, (x, y) in enumerate(centers):
        bodies[f"planet1_{k}"] = {"type": "planet", "orbit": cf, "spin": rel, "carrier": "carrier1",
                                  "center": [x, y], "stage": 1}
    for part in parts:
        q = part.quantity
        if part.key == "sun_s1":
            part.bodies = ["input"]
        elif part.key == "planet_s1":
            part.bodies = [f"planet1_{k}" for k in range(q)]
        elif part.key == "bearing_s1":
            part.bodies = [f"planet1_{k // 2}" for k in range(q)]
        elif part.key.startswith(("spacer_s1", "pin_s1", "carrier")):
            part.bodies = ["carrier1"] * q
        elif part.key in ("drum", "output_arm", "arm_screw", "declutch_collar", "declutch_cap", "declutch_pin",
                          "declutch_nut"):
            part.bodies = ["drum"] * q
        else:
            part.bodies = ["ground"] * q
    kin = {"bodies": bodies, "input": "input", "output": "drum", "total_ratio": abs(c["ratio"])}

    eng = c["eng"]
    out_member = {"type": p.output_type, "bearing": sup["code"], "drum": True}
    eng["load"] = D.load_verdict(p, eng, out_member, abs(c["ratio"]), 2, lang)
    warnings = [eng["wolfrom"]["text"]]
    if sup["kind"] == "PLAIN":
        warnings.append("Çıkış çemberi baskılı kaymalı yatakta döner (bu çapta ince kesitli rulman yok): yüzeyleri "
                        "greslenmeli; çıkış çok yavaş döndüğü için uygundur." if lang != "en" else
                        "The output ring runs in a printed plain bearing (no thin-section bearing this large): grease "
                        "it; the output turns very slowly, which suits it.")
    if mount_warning:
        warnings.append(mount_warning)
    warnings += mount_notes
    if eng["margin"] < 1.0:
        warnings.append(("Dayanım hedefi sağlanmıyor (S = {s:.2f}, sınırlayan: {l})." if lang != "en" else
                         "Strength target not met (S = {s:.2f}, limited by: {l}).").format(
            s=eng["margin"], l=(eng["limiting"] or {}).get("label", "-")))
    if eng.get("load") and eng["load"]["status"] != "ok":
        warnings.append(eng["load"]["text"])
    gm, sm = get_material(p.load.gear_material), get_material(p.load.struct_material)
    mass = sum(K.volume(pt.shape) * pt.quantity * (gm["rho"] if pt.gear or pt.key.startswith(("sun", "planet"))
                                                   else sm["rho"]) / 1000.0 for pt in parts if pt.printable)
    length = z_lid1 + flange_t + ((D.declutch_height(p, c["eng"]["output_torque"] * p.load.application_factor)
                                    if p.declutch
                                   else drum_arm_height(p.arm_shape, p.arm_width, p.arm_thickness)) + 0.4
                                  if p.output_type == "DRUM_ARM" else 0.0)
    summary = {"total_ratio": round(abs(c["ratio"]), 3), "stages": 1, "herringbone": False, "module": m,
               "z_ring": g1.z_ring, "housing_diameter": round(hd["body_d"], 1),
               "outer_diameter": round(hd["envelope_d"], 1), "overall_length": round(length, 1),
               "body_length": round(z_lid1 + flange_t, 1), "part_count": sum(pt.quantity for pt in parts),
               "unique_parts": len(parts), "printed_mass_g": round(mass, 0), "output_torque": round(eng["output_torque"], 2),
               "max_output_torque": round(eng["max_output_torque"], 2), "output_speed": round(eng["output_speed"], 3),
               "efficiency": round(eng["efficiency"], 3), "carrier": "cage", "output_type": p.output_type,
               "arrangement": "WOLFROM", "drum_bearing": sup["code"], "drum_diameter": round(2 * lid_r, 1),
               "tie_rod": f"{hd['tie_rod']}x{bolt_len:g}", "counterbore": counterbore, "addendum": 1.0,
               "wolfrom": {"zs": c["zs"], "zp1": c["zp1"], "zp2": c["zp2"], "zr1": c["zr1"], "zr2": c["zr2"],
                           "self_locking": eng["wolfrom"]["self_locking"], "eta_back": eng["wolfrom"]["eta_back"]}}
    stages_d = [{"index": 1, "z_sun": c["zs"], "z_planet": c["zp1"], "z_ring": c["zr1"], "geometry": g1.to_dict(),
                 "bearing": brg["code"], "layout": "dual", "pin_dia": brg["pin"], "num_planets": n},
                {"index": 2, "z_sun": "—", "z_planet": c["zp2"], "z_ring": c["zr2"],
                 "geometry": g2.to_dict(), "bearing": brg["code"], "layout": "dual", "pin_dia": brg["pin"],
                 "num_planets": n}]
    design = {"params": {"gear_material": p.load.gear_material, "struct_material": p.load.struct_material,
                         "motor": p.motor_code, "cage": True, "addendum": 1.0, "backlash": bl,
                         "bearing_tol": p.bearing_tol},
              "hardware": {"bolt_len": bolt_len, "flange_t": flange_t, "hub_fastener": "INSERT",
                           "insert_holes": True, "insert_count": len(pts)},
              "stages": stages_d, "kind": "WOLFROM"}
    report(100)
    return BuildResult(parts=parts, warnings=warnings, summary=summary, elapsed=time.time() - t_start,
                       product_name=f"Wolfrom_Gearbox_{('%g' % round(abs(c['ratio']), 1)).replace('.', '_')}x",
                       engineering=eng, design=design, kinematics=kin)
