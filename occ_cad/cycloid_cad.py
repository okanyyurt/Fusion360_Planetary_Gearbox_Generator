# -*- coding: utf-8 -*-
"""
Sikloidal redüktörün CAD'i (core.cycloid): motor flanşı, halka pimli gövde (pimler deliğin içine yarı gömülü,
altta zemin), motor miline eksantrik göbek (iki kam 180°), iki sikloid disk (her biri bir rulmanla kamda),
çıkış plakası + göbek (çelik çıkış pimleri disk deliklerinden geçer), çıkış rulmanlı kapak, flanş burçları
veya kol, bağlantı cıvataları.

Eksenel yerleşim core.cycloid.layout ile aynı (z = 0 motor flanşının üstü):
    zemin [0, zd1 - clr], disk A [zd1, + t], disk B [zd2, + t], çıkış plakası [zo0, zo1], kapak [z_hs, z_cv1],
    göbek ucu z_hub1
Disk B, disk A'nın yarım lob döndürülmüş hâlidir (ters kamda, aynı halka pimleriyle kavrar); çıkış pimi
delikleri iki diskte de aynı açılardadır.
"""
from __future__ import annotations

import math
import time
from typing import Callable, Dict, List, Optional

from core import cycloid as C
from core import design as D
from core.bearing_catalog import get_bearing_info
from core.hardware import dowel_is_standard, pick_dowel, tie_rod_choice
from core.layout import mount_window, COLLAR_LEN
from core.materials import get_material
from core.motor_catalog import get_motor_info

from . import kernel as K
from . import parts as B
from . import profiles as P
from .assembly import COLORS, BuildCancelled, BuildResult, Part, bracket_part, drum_declutch_parts

INSERT_R, INSERT_DEPTH = 2.0, 6.0

NAMES = {
    "tr": {"flange": "Motor Flanşı", "housing": "Halka Pimli Gövde", "hub": "Eksantrik Göbek",
           "disc_a": "Sikloid Disk A", "disc_b": "Sikloid Disk B (yarım lob döndürülmüş)", "disc_brg": "Disk Rulmanı",
           "ring_pin": "Halka Pimi", "out_pin": "Çıkış Pimi", "output": "Çıkış Plakası + Göbek", "cover": "Kapak",
           "out_brg": "Çıkış Rulmanı", "arm": "Çıkış Kolu", "screw": "Kol Vidası M3", "bolt": "Bağlantı Cıvatası",
           "rod": "Bağlantı Saplaması", "nut": "Somun", "g_housing": "Gövde", "g_stage": "Sikloid Kademe",
           "g_fast": "Bağlantı Elemanları", "pin_cut": "standart boydan kısaltılır",
           "progress": "Sikloidal redüktör kuruluyor..."},
    "en": {"flange": "Motor Flange", "housing": "Ring Pin Housing", "hub": "Eccentric Hub", "disc_a": "Cycloid Disc A",
           "disc_b": "Cycloid Disc B (turned by half a lobe)", "disc_brg": "Disc Bearing", "ring_pin": "Ring Pin",
           "out_pin": "Output Pin", "output": "Output Plate + Hub", "cover": "Cover", "out_brg": "Output Bearing",
           "arm": "Output Arm", "screw": "Arm Screw M3", "bolt": "Tie Bolt", "rod": "Tie Rod", "nut": "Nut",
           "g_housing": "Housing", "g_stage": "Cycloid Stage", "g_fast": "Fasteners",
           "pin_cut": "cut down from a standard length", "progress": "Building the cycloidal gearbox..."},
}


def _disc(c: Dict, t: float, turn: float, pocket_r: float, lip_r: float, bw: float):
    """Sikloid disk (merkez orijinde, z [0, t]); profil `turn` kadar döndürülmüş, çıkış delikleri sabit açılarda."""
    pts = C.profile_points(c["n_pins"], c["R"], c["rpc"], c["e"])
    ct, st = math.cos(turn), math.sin(turn)
    pts = [(x * ct - y * st, x * st + y * ct) for x, y in pts]
    edge = K.spline_edge([K.pnt(x, y) for x, y in pts + pts[:1]])
    face = K.planar_face(K.make_wire([edge]))
    body = K.extrude(face, 0.0, t)
    cuts = [K.cylinder(pocket_r, -1.0, bw), K.cylinder(lip_r, bw - 0.01, t + 1.0)]
    for j in range(c["n_out"]):
        a = 2 * math.pi * j / c["n_out"]
        cuts.append(K.cylinder(c["hole_r"], -1.0, t + 1.0, c["R_out"] * math.cos(a), c["R_out"] * math.sin(a)))
    return K.cut(body, cuts, "sikloid disk")


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
    c = C.resolve(config, p, lang)
    lay = c["layout"]
    hd, tie = c["hd"], c["hd"]["tie"]
    motor = get_motor_info(p.motor_code)
    clr = D.CLEARANCE
    n, R, rp, e, t = c["n_pins"], c["R"], c["rp"], c["e"], c["disc_t"]
    zd1, zd2, zo0, zo1, z_hs, z_cv1, z_hub1 = (lay[k] for k in ("zd1", "zd2", "zo0", "zo1", "z_hs", "z_cv1", "z_hub1"))
    floor = lay["floor"]
    flange_t = lay["flange_t"]
    flange_nut_z = -flange_t + 1.8
    nut_z, tip_lo, tip_hi, mount_t = mount_window(flange_t, tie, p.mount)
    t_cv = z_cv1 - z_hs
    bolt_len, counterbore, rod = tie_rod_choice(z_cv1, tip_lo, tip_hi, min(8.0, t_cv - 2.0), tie["nut_m"])
    parts: List[Part] = []
    g_h, g_s, g_f = nm["g_housing"], nm["g_stage"], nm["g_fast"]
    collar_r = D._collar_r(p)

    report(12)
    flange = B.build_motor_flange(hd, flange_t, max(7.0, collar_r + 1.0), motor, tie, flange_nut_z, False)
    parts.append(Part("motor_flange", "Motor_Mount_Flange", nm["flange"], "housing", g_h, flange, COLORS["flange"],
                      explode=[(0.0, 0.0, -2.5)]))

    # housing: floor, bore R with the ring pins half sunk into its wall
    report(22)
    pin_pos = [(R * math.cos(2 * math.pi * k / n), R * math.sin(2 * math.pi * k / n)) for k in range(n)]
    cuts = [K.cylinder(R, floor, z_hs + 1.0),
            K.cylinder(max(collar_r, c["bearing"]["d"] / 2.0 + e) + 0.6, -1.0, floor + 0.5)]
    cuts += [K.cylinder(rp, floor - 2.0, z_hs + 1.0, x, y) for x, y in pin_pos]
    cuts += [K.cylinder(tie["hole"] / 2.0, -1.0, z_hs + 1.0, x, y) for x, y in hd["positions"]]
    housing = K.cut(B._lugged_plate(hd, True, 0.0, z_hs), cuts, "halka pimli gövde")
    parts.append(Part("ring_housing", "Ring_Pin_Housing", nm["housing"], "housing", g_h, housing, COLORS["housing"]))
    need = z_hs - (floor - 2.0)
    cover_min = (zd2 + t + 1.0) - (floor - 2.0)
    pin_len = pick_dowel(need, need - cover_min, 0.0, need - cover_min)
    cut_note = "" if dowel_is_standard(pin_len) else " — " + nm["pin_cut"]
    parts.append(Part("ring_pin", "Ring_Pin", f"{nm['ring_pin']} Ø{2 * rp:g}×{pin_len:g}", "stage1", g_s,
                      B.build_pin(2 * rp, pin_len), COLORS["pin"],
                      placements=[K.trsf_translate(x, y, floor - 2.0) for x, y in pin_pos], printable=False,
                      spec=f"ISO 8734 / DIN 6325 Ø{2 * rp:g} m6 × {pin_len:g} mm{cut_note}"))

    # eccentric hub on the motor shaft: collar (set screw + square nut), two cams 180 deg apart
    report(35)
    bi = c["bearing"]
    r_cam = bi["d"] / 2.0
    z_split = zd1 + t + clr / 2.0
    hub = K.fuse(K.cylinder(collar_r, zd1 - COLLAR_LEN, zd1 - clr),
                 [K.cylinder(r_cam, zd1 - clr - 0.01, z_split + 0.01, e, 0.0),
                  K.cylinder(r_cam, z_split - 0.01, zd2 + t, -e, 0.0)], "eksantrik göbek")
    safe_bore = p.motor_shaft_dia
    z_screw = zd1 - clr - (COLLAR_LEN - clr) / 2.0
    tools = [K.cylinder_along(1.6, (0.0, 0.0, z_screw), (0.0, 1.0, 0.0), collar_r + 1.0)]
    nut_y = (safe_bore / 2.0 + collar_r) / 2.0
    slot = K.polygon_wire([(-2.95, nut_y - 1.05), (2.95, nut_y - 1.05), (2.95, nut_y + 1.05), (-2.95, nut_y + 1.05)])
    tools.append(K.extrude(K.planar_face(slot), zd1 - COLLAR_LEN - 1.0, z_screw + 2.95))
    flat = float(motor.get("default_d_flat_depth", 0.5))
    bore = P.shaft_section(safe_bore, p.motor_shaft_type, flat, B.BORE_TOL)
    tools.append(K.extrude(K.planar_face(bore), zd1 - COLLAR_LEN - 1.0, zd2 + t + 1.0))
    hub = K.cut(hub, tools, "eksantrik göbek deliği")
    parts.append(Part("sun_s1", "Eccentric_Hub", nm["hub"], "stage1", g_s, hub, COLORS["sun"], explode=[(0, 0, 2.0)],
                      gear=True))

    # cycloid discs and their bearings
    report(50)
    pocket_r = bi["D"] / 2.0 + p.bearing_tol / 2.0
    lip_r = max(r_cam + 0.6, (bi["d"] + bi["D"]) / 4.0 + 0.3)
    disc_a = _disc(c, t, 0.0, pocket_r, lip_r, bi["width"])
    disc_b = _disc(c, t, math.pi / (n - 1), pocket_r, lip_r, bi["width"])
    parts.append(Part("disc_a", "Cycloid_Disc_A", nm["disc_a"], "stage1", g_s, disc_a, COLORS["planet"],
                      placements=[K.trsf_translate(e, 0.0, zd1)], explode=[(0, 0, 4.0)], gear=True))
    parts.append(Part("disc_b", "Cycloid_Disc_B", nm["disc_b"], "stage1", g_s, disc_b, COLORS["planet"],
                      placements=[K.trsf_translate(-e, 0.0, zd2)], explode=[(0, 0, 6.0)], gear=True))
    parts.append(Part("disc_bearing", f"Bearing_{bi['code']}", f"{bi['code']} {nm['disc_brg']}", "stage1", g_s,
                      B.build_bearing(bi["d"], bi["D"], bi["width"]), COLORS["bearing"],
                      placements=[K.trsf_translate(e, 0.0, zd1), K.trsf_translate(-e, 0.0, zd2)], printable=False,
                      spec=f"{bi['code']} ({bi['d']:g}x{bi['D']:g}x{bi['width']:g})"))

    # output plate + hub, steel output pins pressed into blind holes from below
    report(62)
    ob = get_bearing_info(c["out_bearing"])
    r_pl = R - rp - 0.8
    r_h = ob["d_inner"] / 2.0 - 0.05
    out_pts = [(c["R_out"] * math.cos(2 * math.pi * j / c["n_out"]), c["R_out"] * math.sin(2 * math.pi * j / c["n_out"]))
               for j in range(c["n_out"])]
    r_ins = ob["d_inner"] / 2.0 - C.HUB_INSERT_R
    ins_pts = [(r_ins * math.cos(math.pi / 4 + k * math.pi / 2), r_ins * math.sin(math.pi / 4 + k * math.pi / 2))
               for k in range(4)]
    pin_hole = c["d_out"] + float(config.get("pin_tolerance") or 0.0)
    out_body = K.fuse(K.cylinder(r_pl, zo0, zo1), [K.cylinder(r_h, zo1 - 0.01, z_hub1)], "çıkış plakası")
    ocuts = [K.cylinder(pin_hole / 2.0, zo0 - 1.0, zo1 - 1.0, x, y) for x, y in out_pts]
    ocuts += [K.cylinder(INSERT_R, z_hub1 - INSERT_DEPTH, z_hub1 + 1.0, x, y) for x, y in ins_pts]
    out_body = K.cut(out_body, ocuts, "çıkış plakası delikleri")
    parts.append(Part("carrier_top_s1", "Output_Plate_Hub", nm["output"], "output", g_s, out_body, COLORS["carrier"],
                      print_trsf=K.trsf_rotate_axis((0, 0, 0), (1, 0, 0), math.pi), explode=[(0, 0, 9.0)]))
    top = zo1 - 1.0
    need_o = top - (floor + 0.3)
    min_o = top - (zd1 + 1.0)
    out_len = pick_dowel(need_o, need_o - min_o, 0.0, need_o - min_o)
    cut_o = "" if dowel_is_standard(out_len) else " — " + nm["pin_cut"]
    parts.append(Part("pin_s1", "Output_Pin", f"{nm['out_pin']} Ø{c['d_out']:g}×{out_len:g}", "output", g_s,
                      B.build_pin(c["d_out"], out_len), COLORS["pin"],
                      placements=[K.trsf_translate(x, y, top - out_len) for x, y in out_pts], printable=False,
                      spec=f"ISO 8734 / DIN 6325 Ø{c['d_out']:g} m6 × {out_len:g} mm{cut_o}"))

    # cover with the output bearing (pressed in from below), tie bolt counterbores
    report(74)
    lip = max(r_h + 0.6, (ob["d_inner"] + ob["d_outer"]) / 4.0)
    ccuts = [K.cylinder(ob["d_outer"] / 2.0 + p.bearing_tol / 2.0, z_hs - 1.0, z_hs + ob["width"]),
             K.cylinder(lip, z_hs + ob["width"] - 0.01, z_cv1 + 1.0)]
    for x, y in hd["positions"]:
        ccuts.append(K.cylinder(tie["hole"] / 2.0, z_hs - 1.0, z_cv1 + 1.0, x, y))
        if counterbore > 0.05:
            ccuts.append(K.cylinder(tie["head_d"] / 2.0 + 0.3, z_cv1 - counterbore, z_cv1 + 1.0, x, y))
    cover = K.cut(B._lugged_plate(hd, True, z_hs, z_cv1), ccuts, "kapak")
    parts.append(Part("cover", "Cover", nm["cover"], "housing", g_h, cover, COLORS["housing"],
                      print_trsf=K.trsf_rotate_axis((0, 0, 0), (1, 0, 0), math.pi), explode=[(0, 0, 12.0)]))
    parts.append(Part("out_bearing", f"Bearing_{c['out_bearing']}", f"{c['out_bearing']} {nm['out_brg']}", "output",
                      g_s, B.build_bearing(ob["d_inner"], ob["d_outer"], ob["width"]), COLORS["bearing"],
                      placements=[K.trsf_translate(0, 0, z_hs)], printable=False,
                      spec=f"{c['out_bearing']} ({ob['d_inner']:g}x{ob['d_outer']:g}x{ob['width']:g})"))
    if p.output_type == "ARM" and p.declutch:
        parts += drum_declutch_parts(p, z_hub1 + 0.4, ins_pts, "INSERT",
                                     c["eng"]["output_torque"] * p.load.application_factor, lang, "output", g_s, 12.0)
    elif p.output_type == "ARM":
        arm, arm_h = B.build_drum_arm(p.arm_shape, p.arm_length, p.arm_width, p.arm_thickness,
                                      max(r_ins + 5.0, r_h), ins_pts)
        parts.append(Part("output_arm", "Output_Arm", f"{nm['arm']} {p.arm_length:g} mm", "output", g_s, arm,
                          COLORS["carrier"], placements=[K.trsf_translate(0, 0, z_hub1 + 0.4)],
                          explode=[(0.0, 0.0, 15.0)]))
        parts.append(Part("arm_screw", "Screw_M3_Arm", nm["screw"], "output", g_s,
                          B.build_socket_bolt({"d": 3.0, "head_d": 5.5, "head_h": 3.0}, 10.0), COLORS["bolt"],
                          placements=[K.trsf_translate(x, y, z_hub1 + 0.4 + arm_h - B.M3_HEAD_DEPTH) for x, y in ins_pts],
                          printable=False, spec="ISO 4762 M3 × 10 mm + M3 ısıl burç"))

    report(85)
    if not rod:
        parts.append(Part("tie_rod_bolt", f"Bolt_{hd['tie_rod']}x{bolt_len:g}", f"{hd['tie_rod']}×{bolt_len:g} {nm['bolt']}",
                          "fasteners", g_f, B.build_socket_bolt(tie, bolt_len), COLORS["bolt"],
                          placements=[K.trsf_translate(x, y, z_cv1 - counterbore) for x, y in hd["positions"]],
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

    # kinematics: hub 1, discs orbit with the input and turn -1/(N-1), output -1/(N-1)
    w_out = -1.0 / (n - 1)
    spin = w_out - 1.0
    bodies = {"ground": {"type": "ground"}, "input": {"type": "axis", "factor": 1.0},
              "disc_a": {"type": "planet", "orbit": 1.0, "spin": spin, "center": [e, 0.0], "stage": 1},
              "disc_b": {"type": "planet", "orbit": 1.0, "spin": spin, "center": [-e, 0.0], "stage": 1},
              "output": {"type": "axis", "factor": w_out, "stage": 1}}
    for part in parts:
        q = part.quantity
        if part.key == "sun_s1":
            part.bodies = ["input"]
        elif part.key == "disc_a":
            part.bodies = ["disc_a"]
        elif part.key == "disc_b":
            part.bodies = ["disc_b"]
        elif part.key == "disc_bearing":
            part.bodies = ["disc_a", "disc_b"]
        elif part.key in ("carrier_top_s1", "pin_s1", "output_arm", "arm_screw", "declutch_collar", "declutch_cap",
                          "declutch_pin", "declutch_nut"):
            part.bodies = ["output"] * q
        else:
            part.bodies = ["ground"] * q
    kin = {"bodies": bodies, "input": "input", "output": "output", "total_ratio": float(n - 1)}

    eng = c["eng"]
    out_member = {"type": p.output_type, "bearing": c["out_bearing"], "hub_d": ob["d_inner"], "shaft_d": 0.0,
                  "drum": False, "steel": False}
    eng["load"] = D.load_verdict(p, eng, out_member, float(n - 1), 1, lang)
    warnings = [eng["cycloid"]["text"]]
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
    mass = sum(K.volume(pt.shape) * pt.quantity * (gm["rho"] if pt.gear else sm["rho"]) / 1000.0
               for pt in parts if pt.printable)
    summary = {"total_ratio": float(n - 1), "stages": 1, "herringbone": False, "module": 1.0, "z_ring": n,
               "housing_diameter": round(hd["body_d"], 1), "outer_diameter": round(hd["envelope_d"], 1),
               "overall_length": round(lay["length"], 1), "body_length": round(lay["body_length"], 1),
               "part_count": sum(pt.quantity for pt in parts), "unique_parts": len(parts),
               "printed_mass_g": round(mass, 0), "output_torque": round(eng["output_torque"], 2),
               "max_output_torque": round(eng["max_output_torque"], 2), "output_speed": round(eng["output_speed"], 3),
               "efficiency": round(eng["efficiency"], 3), "carrier": "cycloid", "output_type": p.output_type,
               "arrangement": "CYCLOID", "tie_rod": f"{hd['tie_rod']}x{bolt_len:g}", "counterbore": counterbore,
               "addendum": 1.0, "out_hub": c["out_bearing"],
               "cycloid": {"n_pins": n, "pin_d": 2 * rp, "R": R, "e": e, "lobes": n - 1, "n_out": c["n_out"],
                           "d_out": c["d_out"]}}
    stage_d = {"index": 1, "z_sun": 0, "z_planet": n - 1, "z_ring": n, "bearing": bi["code"], "layout": "single",
               "pin_dia": c["d_out"], "num_planets": 2,
               "cycloid": {"n_pins": n, "rp": rp, "R": R, "e": e, "disc_t": t, "n_out": c["n_out"], "d_out": c["d_out"],
                           "R_out": c["R_out"], "bearing": bi["code"]}}
    design = {"params": {"gear_material": p.load.gear_material, "struct_material": p.load.struct_material,
                         "motor": p.motor_code, "cage": True, "addendum": 1.0, "backlash": p.backlash,
                         "bearing_tol": p.bearing_tol},
              "hardware": {"bolt_len": bolt_len, "flange_t": flange_t, "hub_fastener": "INSERT",
                           "insert_holes": True, "insert_count": len(ins_pts)},
              "stages": [stage_d], "kind": "CYCLOID"}
    report(100)
    return BuildResult(parts=parts, warnings=warnings, summary=summary, elapsed=time.time() - t_start,
                       product_name=f"Cycloidal_Gearbox_{n - 1}x", engineering=eng, design=design, kinematics=kin)
