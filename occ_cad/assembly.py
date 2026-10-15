# -*- coding: utf-8 -*-
"""
Planet redüktör montaj yöneticisi (Fusion: cad/assembly_manager.py karşılığı).

Tasarım verisi core.design.resolve() ile çözülür (geometri, rulmanlar, çıkış elemanı, mühendislik
hesapları); bu modül yalnızca katıları kurar ve konumlandırır. Fusion sürümüne göre başlıca farklar:

  * Diş profili: kavrama başına toplam backlash, girişimsiz uç yarıçapları, kök radyüsü.
  * Planetler güneş ve çembere göre fazlanır; balıksırtı yönleri güneş (+), planet/çember (-).
    Balıksırtı çember V tepe düzlemlerinden bölünür (takılabilirlik).
  * Kafes taşıyıcı (varsayılan): iki düz plaka + çelik pim; bir sonraki kademenin güneşi üst
    plakaya gömülüdür. Plakalar ve dişliler desteksiz basılır. Klasik tek plaka da seçilebilir.
  * Rulmanlar yüzey hizasında (tek / çift), iç bilezikler basılı ara halkalarla sıkıştırılır.
  * Çıkış: kapaktaki rulmanla taşınan flanş göbeği veya mil.
  * Dönen gövde (çember çıkışı): son kademenin taşıyıcısı sabit tabana pimlenir, çemberi kapaklı bir
    tambur olur ve sabit taşıyıcının üst plakasındaki göbeğe oturan rulmanla döner (flanş, kol, vinç).
  * Kademe arası: bir sonraki güneş her iki taşıyıcı tipinde de taşıyıcıyla tek parça basılır (D-mil yok).
  * Gövde: merkezleme omuzları, havşalı motor vidaları, yandan takılan somun yuvaları; bağlantı
    cıvatası standart boydadır, kapak havşası boy farkını karşılar.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from core import design as D
from core.bearing_catalog import get_bearing_info, inner_race_diameter
from core.circlip_catalog import get_circlip_info
from core.engineering import ARM_FLAT, arm_key_height
from core.hardware import DOWEL_LENGTHS, dowel_is_standard, pick_dowel, pick_motor_screw, pick_setscrew
from core.layout import DECLUTCH_CAP, COLLAR_LEN, PIN_TAIL
from core.materials import get_material
from core.motor_catalog import get_motor_info

from . import kernel as K
from . import parts as B
from . import profiles as Pr


COLORS = {
    "flange": "#b9c3cd", "housing": "#7f8c99", "sun": "#d8a945", "planet": "#a7b4c2", "carrier": "#c7d0d9",
    "circlip": "#e8743b", "cover": "#b9c3cd", "bolt": "#3f4752", "bearing": "#d9dee4", "pin": "#5f6b78",
    "spacer": "#3fb27f", "shaft": "#6f7c89",
}

MESSAGES = {
    "tr": {"start": "⚙️ 1/5: Tasarım çözülüyor ve montaj ağacı kuruluyor...",
           "flange": "🔧 2/5: Motor flanşı üretiliyor...",
           "housing": "🛡️ 3/5: Çember dişli gövdesi oluşturuluyor...",
           "stage": "⚡ 4/5: Kademe {n}: dişliler, taşıyıcı ve rulmanlar...",
           "cover": "🎯 5/5: Kapak, çıkış rulmanı ve bağlantı elemanları...",
           "done": "✅ Redüktör başarıyla oluşturuldu!"},
    "en": {"start": "⚙️ 1/5: Resolving the design and assembly tree...",
           "flange": "🔧 2/5: Generating the motor flange...",
           "housing": "🛡️ 3/5: Building the ring gear housing...",
           "stage": "⚡ 4/5: Stage {n}: gears, carrier and bearings...",
           "cover": "🎯 5/5: Cover, output bearing and fasteners...",
           "done": "✅ Gearbox generated successfully!"},
}

NAMES = {
    "tr": {"bracket": "Montaj Braketi (L)", "pin_cut": "standart boydan kısaltılır (taşlama / kesme)",
           "mount_small": "Montaj braketi bu küçük gövdeye uygun değil: bağlantı cıvataları motorun kendi deliklerinden geçiyor (motor gövdesi rafın altından geçemez).",
           "flange": "Motor Flanşı", "housing": "Çember Dişli Gövdesi", "housing_sec": "Çember Gövde Bölümü {i}",
           "ring": "Çember Dişli", "sun": "Güneş Dişli", "planet": "Planet Dişli", "carrier": "Planet Taşıyıcı",
           "carrier_top": "Üst Taşıyıcı Plaka", "carrier_top_sun": "Üst Taşıyıcı + K{n} Güneşi",
           "carrier_top_out": "Üst Taşıyıcı + Çıkış", "carrier_bottom": "Alt Taşıyıcı Plaka",
           "circlip": "Segman", "cover": "Üst Kapak", "bolt": "Bağlantı Cıvatası", "nut": "Somun",
           "rod": "Saplama (DIN 976)", "nut_top": "Üst Somun",
           "bearing": "Rulman", "out_bearing": "Çıkış Rulmanı", "pin": "Pim", "spacer": "Rulman Ara Halkası",
           "steel_shaft": "Çelik Çıkış Mili", "g_housing": "Gövde", "g_stage": "Kademe {n}",
           "arm_flat": "Çıkış Kolu (yassı)", "arm_round": "Çıkış Kolu (yuvarlak)", "arm_screw": "Kol Vidası",
           "hub_nut": "Somun (çıkış göbeği yuvası)",
           "carrier_sun": "Taşıyıcı + K{n} Güneşi", "ring_base": "Sabit Taban Plakası (taşıyıcı tabanı)",
           "carrier_fixed": "Sabit Üst Plaka + Tambur Göbeği", "drum": "Dönen Gövde (Tambur)",
           "drum_lo": "Tambur Alt Yarısı", "drum_hi": "Tambur Üst Yarısı + Kapak", "drum_bearing": "Tambur Rulmanı",
           "drum_nut": "Somun (tambur kapağı yuvası)", "join_screw": "Tambur Birleşim Vidası",
           "join_nut": "Somun (tambur birleşimi)", "drum_arm_flat": "Tambur Kolu (yassı)",
           "drum_arm_round": "Tambur Kolu (yuvarlak)",
           "g_fasteners": "Bağlantı Elemanları", "stage_tag": "K{n}"},
    "en": {"bracket": "Mounting Bracket (L)", "pin_cut": "cut down from a standard length (grind / cut)",
           "mount_small": "The mounting bracket does not suit this small housing: the tie rods go through the motor's own holes (the motor body cannot pass the shelf).",
           "flange": "Motor Flange", "housing": "Ring Gear Housing", "housing_sec": "Ring Housing Section {i}",
           "ring": "Ring Gear", "sun": "Sun Gear", "planet": "Planet Gear", "carrier": "Planet Carrier",
           "carrier_top": "Top Carrier Plate", "carrier_top_sun": "Top Carrier + S{n} Sun",
           "carrier_top_out": "Top Carrier + Output", "carrier_bottom": "Bottom Carrier Plate",
           "circlip": "Circlip", "cover": "Top Cover", "bolt": "Tie Rod Bolt", "nut": "Nut",
           "rod": "Threaded Rod (DIN 976)", "nut_top": "Top Nut",
           "bearing": "Bearing", "out_bearing": "Output Bearing", "pin": "Pin", "spacer": "Bearing Spacer",
           "steel_shaft": "Steel Output Shaft", "g_housing": "Housing", "g_stage": "Stage {n}",
           "arm_flat": "Output Arm (flat)", "arm_round": "Output Arm (round)", "arm_screw": "Arm Screw",
           "hub_nut": "Nut (output hub pocket)",
           "carrier_sun": "Carrier + S{n} Sun", "ring_base": "Fixed Base Plate (carrier base)",
           "carrier_fixed": "Fixed Top Plate + Drum Stub", "drum": "Rotating Housing (Drum)",
           "drum_lo": "Drum Lower Half", "drum_hi": "Drum Upper Half + Lid", "drum_bearing": "Drum Bearing",
           "drum_nut": "Nut (drum lid pocket)", "join_screw": "Drum Joint Screw", "join_nut": "Nut (drum joint)",
           "drum_arm_flat": "Drum Arm (flat)", "drum_arm_round": "Drum Arm (round)",
           "g_fasteners": "Fasteners", "stage_tag": "S{n}"},
}


@dataclass
class Part:
    key: str                     # benzersiz prototip anahtarı (STEP/STL dosya adı)
    name: str                    # ASCII CAD adı (STEP ürün adı)
    label: str                   # arayüzde gösterilen ad
    group: str                   # grup anahtarı: housing / stage1 / fasteners
    group_label: str
    shape: object                # TopoDS_Shape (prototip)
    color: str
    placements: List[object] = field(default_factory=list)   # gp_Trsf listesi (boşsa tek, kimlik)
    explode: List[Tuple[float, float, float]] = field(default_factory=list)
    printable: bool = True       # True: basılacak (STL), False: satın alınan parça
    print_trsf: object = None    # STL için baskı yönü (gp_Trsf)
    spec: str = ""               # satın alınan parça tanımı (BOM)
    note: str = ""               # baskı notu
    bodies: List[str] = field(default_factory=list)   # her instance'ın bağlı olduğu rijit gövde (kinematik)
    gear: bool = False           # dişli taşıyan parça (dişli malzemesiyle basılır): ör. güneşli taşıyıcı

    @property
    def quantity(self) -> int:
        return max(1, len(self.placements))


@dataclass
class BuildResult:
    parts: List[Part]
    warnings: List[str]
    summary: Dict
    elapsed: float
    product_name: str
    engineering: Dict = field(default_factory=dict)
    bom: List[Dict] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    design: Dict = field(default_factory=dict)
    kinematics: Dict = field(default_factory=dict)


class BuildCancelled(Exception):
    pass


def planet_phases(z_sun: int, z_planet: int, z_ring: int, num_planets: int) -> Tuple[float, List[float]]:
    """
    Çember dişli boşluğu 0° iken güneş ve planetlerin kavrama fazları (rad).
    Planet i (konum açısı θ): φ = θ·(1 − Zr/Zp)  (mod 2π/Zp);  güneş: Zp çiftse yarım adım.
    """
    sun_phase = math.pi / z_sun if z_planet % 2 == 0 else 0.0
    step = 2.0 * math.pi / z_planet
    return sun_phase, [((2.0 * math.pi * i / num_planets) * (1.0 - z_ring / z_planet)) % step
                       for i in range(num_planets)]


BRACKET_NAMES = {
    "tr": {"SIDE": "Montaj Braketi (L, yan montaj)", "BASE": "Montaj Braketi (ayaklı taban)",
           "PANEL": "Montaj Braketi (panel plakası)"},
    "en": {"SIDE": "Mounting Bracket (L, side mount)", "BASE": "Mounting Bracket (base stand)",
           "PANEL": "Mounting Bracket (panel plate)"},
}


SWING_KEYS = ("output_arm", "arm_screw", "declutch_pin", "declutch_nut")      # members that sweep beyond the housing


def _envelope(parts: List[Part]) -> Tuple[float, float, float]:
    """(widest radius of the gearbox body, top of it, reach of an output arm) from the placed parts."""
    r_env, z_up, reach = 0.0, 0.0, 0.0
    for pt in parts:
        for i in range(pt.quantity):
            x0, y0, z0, x1, y1, z1 = K.bounding_box(K.transform(pt.shape, pt.placements[i]) if pt.placements
                                                    else pt.shape)
            r = max(abs(x0), abs(x1), abs(y0), abs(y1))
            if pt.key in SWING_KEYS:
                reach = max(reach, max(math.hypot(x, y) for x in (x0, x1) for y in (y0, y1)))
            elif z1 > 0.0:
                r_env, z_up = max(r_env, r), max(z_up, z1)
    return r_env, z_up, reach


SWING_TEXT = {
    "tr": "Yan montaj: kol (erişim {L:.0f} mm) duvara / direğe çarpmadan yalnızca ~{a:.0f}° döner — duvar −Y tarafında, "
          "kolun serbest bölgesi +Y tarafı. Kolun sürdüğü mekanizma bu açının içinde kalmalı; tam tur gerekiyorsa ayaklı taban seçin.",
    "en": "Side mount: the arm (reach {L:.0f} mm) turns only ~{a:.0f}° before it hits the wall / post — the wall is on "
          "the −Y side, the arm is free on the +Y side. The driven mechanism must stay within this angle; for a full turn "
          "use the base stand.",
}


def bracket_part(hd: Dict, motor: Dict, tie: Dict, flange_t: float, mount_t: float, kind: str, lang: str,
                 group_label: str, parts: Optional[List[Part]] = None, warnings: Optional[List[str]] = None):
    """
    The mounting bracket under the motor flange (any arrangement), or the warning why it does not fit. A side mount
    keeps its back plate outside the widest part of the gearbox and reaches up along the housing; an output arm
    that sweeps past the wall gets its free swing angle as a warning.
    """
    if not B.mount_bracket_fits(hd, motor, tie):
        return NAMES[lang]["mount_small"]
    kind = kind or "SIDE"
    r_env, z_up, reach = _envelope(parts or [])
    if kind == "SIDE":
        shape, info = B.build_mount_bracket(hd, motor, tie, -flange_t, mount_t, r_env, z_up - 2.0)
        if reach > info["offset"] and warnings is not None:
            a = 180.0 + 2.0 * math.degrees(math.asin(min(1.0, info["offset"] / reach)))
            warnings.append(SWING_TEXT[lang].format(L=reach, a=a))
    else:
        build = {"BASE": B.build_mount_base, "PANEL": B.build_mount_panel}[kind]
        shape, _ = build(hd, motor, tie, -flange_t, mount_t)
    if kind == "SIDE":       # back plate flat on the bed (it reaches above and below the shelf)
        trsf, note = (K.trsf_rotate_axis((0, 0, 0), (1, 0, 0), math.pi / 2.0),
                      "Sırt plakası tablada (desteksiz); %40 gyroid, 4 duvar")
    else:
        trsf, note = _flip_x(), "Raf yüzü tablada; %40 gyroid, 4 duvar"
    return Part("mount_bracket", "Mounting_Bracket", BRACKET_NAMES[lang][kind], "housing", group_label, shape,
                COLORS["flange"], explode=[(0.0, -0.6, -4.0)], print_trsf=trsf, note=note)


def _flip_x():
    return K.trsf_rotate_axis((0, 0, 0), (1, 0, 0), math.pi)


def _f(cfg: Dict, key: str, default: float) -> float:
    try:
        v = cfg.get(key, default)
        return float(default if v in (None, "") else v)
    except (TypeError, ValueError):
        return float(default)


def generate(config: Dict, progress: Optional[Callable[[str, int], None]] = None,
             cancelled: Optional[Callable[[], bool]] = None) -> BuildResult:
    t_start = time.time()
    lang = "en" if str(config.get("lang", "tr")).lower().startswith("en") else "tr"
    msg, names = MESSAGES[lang], NAMES[lang]

    def report(key: str, pct: int, **kw):
        if cancelled and cancelled():
            raise BuildCancelled()
        if progress:
            progress(msg[key].format(**kw), pct)

    if str(config.get("arrangement") or "").upper() == "WOLFROM":
        from .wolfrom_cad import generate as wolfrom_generate
        return wolfrom_generate(config, progress, cancelled)
    if str(config.get("arrangement") or "").upper() == "CYCLOID":
        from .cycloid_cad import generate as cycloid_generate
        return cycloid_generate(config, progress, cancelled)
    if not config.get("stages"):
        raise K.GeometryError("Dişli kombinasyonu seçilmedi." if lang == "tr" else "No gear combination selected.")
    report("start", 8)
    R = D.resolve(config)
    p: D.Params = R["params"]
    hd, out, stages = R["housing"], R["output"], R["stages"]
    tie = hd["tie"]
    motor = get_motor_info(p.motor_code)
    pa, bl, fw = p.pressure_angle, p.backlash, p.face_width
    helix = p.helix if p.herringbone else 0.0
    clr = D.CLEARANCE
    t_top = p.plate_t
    t_bot = max(2.5, round(0.75 * t_top * 2.0) / 2.0)
    pin_tol = _f(config, "pin_tolerance", 0.0)
    make_housing = p.make_housing
    ring = p.ring_out                       # rotating housing: last carrier fixed, its ring is the output drum
    if ring and not out.get("seat_fits", True):
        raise K.GeometryError(
            f"Tambur rulmanı ({p.out_hub}) bu tasarıma sığmıyor: sabit taşıyıcının göbeği pim dairesinin içinde "
            f"kalmalı. Tambur rulmanını Otomatik bırakın veya daha büyük gövdeye izin verin." if lang == "tr" else
            f"The drum bearing ({p.out_hub}) does not fit this design: the fixed carrier stub must stay inside the "
            f"pin circle. Leave the drum bearing on Automatic or allow a larger housing.")
    if make_housing and not ring and not out.get("seat_fits", True):
        # a bearing seat wider than the cover would give an invalid cover with the bearing sticking out
        ob_ = get_bearing_info(out["bearing"])
        raise K.GeometryError(
            f"Çıkış rulmanı {out['bearing']} (Ø{ob_['d_outer']:g}) bu gövdenin kapağına sığmıyor (gövde Ø{hd['body_d']:.0f}): "
            f"daha küçük çıkış göbeği / mil seçin veya Otomatik bırakın ya da daha büyük gövdeye izin verin."
            if lang == "tr" else
            f"The output bearing {out['bearing']} (Ø{ob_['d_outer']:g}) does not fit this housing's cover "
            f"(housing Ø{hd['body_d']:.0f}): choose a smaller output hub / shaft, leave it Automatic or allow a "
            f"larger housing.")
    circlip_type = str(config.get("circlip_type", "DIN_471"))
    make_circlips = (not p.cage) and bool(config.get("generate_circlips", True)) and circlip_type != "NONE"
    collar_r = D._collar_r(p)
    n_st = len(stages)
    n_fixed = n_st - 1 if ring else n_st     # stages whose ring is the fixed housing
    parts: List[Part] = []
    g_housing, g_fast = names["g_housing"], names["g_fasteners"]

    # ── Eksenel yerleşim (core.layout: tasarım motoruyla ortak) ───────────────
    ob = get_bearing_info(out["bearing"])
    out_len = _f(config, "output_shaft_len", 20.0)
    lay = R["layout"]
    z_planets, carrier_tops, housing_len = lay.z_planets, lay.carrier_tops, lay.housing_len
    cover_t, flange_t, nut_z, z_cover_top = lay.cover_t, lay.flange_t, lay.nut_z, lay.z_cover_top
    bolt_len, counterbore = lay.bolt_len, lay.counterbore
    head_h = float(motor.get("screw_head_h", 3.0))
    tie_rod_kind = "rod" if lay.threaded_rod else "bolt"

    # merkezleme omuzu motor vidası havşalarıyla çakışıyorsa flanş-gövde arasında kullanılmaz
    r_a, r_b = B.spigot_radii(hd)
    pcd_r = float(motor.get("bolt_pitch_circle", 0.0)) / 2.0
    head_r = float(motor.get("screw_head_dia", 5.5)) / 2.0 + 0.3
    flange_spigot = make_housing and not (pcd_r + head_r >= r_a - 0.3 and pcd_r - head_r <= r_b + 0.3)

    # ── 1) Motor flanşı ──────────────────────────────────────────────────────
    if make_housing:
        report("flange", 18)
        flange = B.build_motor_flange(hd, flange_t, max(7.0, collar_r + 1.0), motor, tie, lay.flange_nut_z or nut_z,
                                      flange_spigot)
        parts.append(Part("motor_flange", "Motor_Mount_Flange", names["flange"], "housing", g_housing, flange,
                          COLORS["flange"], explode=[(0.0, 0.0, -2.5)]))

    # ── 2) Çember dişli gövdesi ──────────────────────────────────────────────
    report("housing", 30)
    geo0 = stages[0]["geo"]
    if n_fixed and p.herringbone:
        tw = B.herringbone_twist(fw, geo0.r_ring, helix)
        apexes = [zk + fw / 2.0 for zk in z_planets[:n_fixed]]
        bounds = [0.0] + apexes + [housing_len]
        hole_d = tie["d"] + 0.1                      # bölümler arası açısal hizalama için sıkı delik
        for i in range(len(bounds) - 1):
            z_lo, z_hi = bounds[i], bounds[i + 1]
            pts = [(z_lo, -tw if i > 0 else 0.0)]
            if i > 0:
                pts.append((z_planets[i - 1] + fw, 0.0))
            if i < n_fixed:
                pts.append((z_planets[i], 0.0))
            pts.append((z_hi, -tw if i < n_fixed else 0.0))
            clean = [pts[0]]
            for zz, aa in pts[1:]:
                if zz - clean[-1][0] > 1e-6:
                    clean.append((zz, aa))
            section, _ = B.build_ring_section(geo0, pa, bl, [c[0] for c in clean], [c[1] for c in clean], hd,
                                              make_housing, hole_d, male_top=True,
                                              female_bottom=(i > 0) or flange_spigot)
            parts.append(Part(f"ring_housing_s{i + 1}", f"Ring_Gear_Housing_S{i + 1}",
                              names["housing_sec"].format(i=i + 1), "housing", g_housing, section, COLORS["housing"],
                              explode=[(0.0, 0.0, float(2 * i))]))
    elif n_fixed:
        ring_body, _ = B.build_ring_spur(geo0, pa, bl, 0.0, housing_len, hd, make_housing, tie["hole"],
                                         male_top=True, female_bottom=flange_spigot)
        parts.append(Part("ring_housing", "Ring_Gear_Housing", names["housing"] if make_housing else names["ring"],
                          "housing", g_housing, ring_body, COLORS["housing"], explode=[(0.0, 0.0, 0.0)]))

    # ── 3) Kademeler ─────────────────────────────────────────────────────────
    sun_phases = [planet_phases(s["z_sun"], s["z_planet"], s["z_ring"], s["num_planets"])[0] for s in stages]
    for idx, st in enumerate(stages):
        n = idx + 1
        report("stage", 40 + int(45 * idx / n_st), n=n)
        geo = st["geo"]
        tag = names["stage_tag"].format(n=n)
        g_key, g_label = f"stage{n}", names["g_stage"].format(n=n)
        z0 = z_planets[idx]
        zp, zt = z0 + fw + clr, carrier_tops[idx]
        cd = geo.center_distance
        n_pl = st["num_planets"]
        _, phases = planet_phases(st["z_sun"], st["z_planet"], st["z_ring"], n_pl)
        level = 2.0 * idx + 1.0
        pin_d = st["pin_dia"]
        layout = st["layout"]
        info_b = st["bearing_info"]
        pin_hole = pin_d + pin_tol + (0.1 if not p.pin_steel else 0.0)
        centers = [(cd * math.cos(2 * math.pi * i / n_pl), cd * math.sin(2 * math.pi * i / n_pl)) for i in range(n_pl)]

        # Güneş
        if idx == 0:
            flat = float(motor.get("default_d_flat_depth", 0.5))
            sun, sun_info = B.build_motor_sun(geo, fw, z0, pa, bl, helix, sun_phases[0], p.motor_shaft_dia,
                                              p.motor_shaft_type, flat, collar_r, COLLAR_LEN)
            parts.append(Part("sun_s1", "Sun_Gear_Stg1", f"{names['sun']} ({tag})", g_key, g_label, sun,
                              COLORS["sun"], explode=[(0.0, 0.0, level + 0.6)]))
        # later suns are printed in one piece with the previous carrier (cage or single plate): the torque
        # passes through a full section instead of a D-flat, which strips in plastic
        star = ring and idx == n_st - 1

        # Planetler
        bushing_clear = max(0.2, 2.0 * p.bearing_tol)
        planet, _ = B.build_planet(geo, fw, z0, pa, bl, helix, layout, st["pocket_dia"], info_b["width"],
                                   st["inner_race_d"], pin_d, bushing_clear)
        placements = [K.trsf_place(x, y, 0.0, phases[i]) for i, (x, y) in enumerate(centers)]
        radial = [(math.cos(2 * math.pi * i / n_pl), math.sin(2 * math.pi * i / n_pl)) for i in range(n_pl)]
        parts.append(Part(f"planet_s{n}", f"Planet_Gear_Stg{n}", f"{names['planet']} ({tag})", g_key, g_label,
                          planet, COLORS["planet"], placements=placements,
                          explode=[(ux * 0.7, uy * 0.7, level + 0.3) for ux, uy in radial]))

        # Rulmanlar (yüzey hizasında) ve ara halkalar
        if st["bearings_per_planet"] > 0:
            brg = B.build_bearing(info_b["d_inner"], info_b["d_outer"], info_b["width"])
            zs_b = [z0 + fw - info_b["width"]] + ([z0] if layout == "dual" else [])
            bpl, bex = [], []
            for zb in zs_b:
                for (x, y), (ux, uy) in zip(centers, radial):
                    bpl.append(K.trsf_translate(x, y, zb))
                    bex.append((ux * 1.25, uy * 1.25, level + (0.9 if zb > z0 else -0.2)))
            parts.append(Part(f"bearing_s{n}", f"Bearing_{st['bearing']}_Stg{n}", f"{st['bearing']} {names['bearing']} ({tag})",
                              g_key, g_label, brg, COLORS["bearing"], placements=bpl, explode=bex, printable=False,
                              spec=f"{st['bearing']} ({info_b['d_inner']:g}x{info_b['d_outer']:g}x{info_b['width']:g})"))
            if p.cage or star:
                spacer = B.build_spacer(pin_d + 0.3, st["inner_race_d"] - 0.3, clr)
                spl, sex = [], []
                zs_s = [z0 + fw] + ([z0 - clr] if layout == "dual" else [])
                for zsp in zs_s:
                    for (x, y), (ux, uy) in zip(centers, radial):
                        spl.append(K.trsf_translate(x, y, zsp))
                        sex.append((ux * 1.25, uy * 1.25, level + (1.35 if zsp > z0 else -0.5)))
                parts.append(Part(f"spacer_s{n}", f"Bearing_Spacer_Stg{n}", f"{names['spacer']} ({tag})", g_key,
                                  g_label, spacer, COLORS["spacer"], placements=spl, explode=sex,
                                  note=f"{clr:.1f} mm — 0.2 mm katmanla 3 katman"))

        # Taşıyıcı
        r_out = min(cd + pin_hole / 2.0 + 2.5, geo.tip_ring - 0.8)
        is_last = idx == n_st - 1
        if star:
            drum_parts = _build_star_stage(p, out, lay, hd, tie, geo, st, centers, radial, pin_hole, pin_d, idx, n,
                                           tag, g_key, g_label, level, collar_r, flange_spigot, n_fixed, names,
                                           pa, bl, helix, r_out, R["engineering"])
            parts += drum_parts
            continue
        if is_last:
            shoulder_r = inner_race_diameter(ob) / 2.0 - 0.2
            extras, cuts, out_top = B.output_hub(out["type"], out["hub_d"], out["shaft_d"], zt - t_top / 2.0,
                                                 z_cover_top, shoulder_r, housing_len, out_len,
                                                 key_h=arm_key_height(out["hub_d"]), key_flat=ARM_FLAT * out["hub_d"],
                                                 protrusion=lay.output_protrusion, fastener=p.hub_fastener,
                                                 arm_gap=lay.arm_gap)
            hub_r = max(shoulder_r, out["hub_d"] / 2.0) + 1.0
        else:
            nxt = stages[idx + 1]["geo"]
            neck_r = nxt.root_sun - D.NECK_INSET
            gear_next, _ = B.external_gear_solid(nxt.z_sun, nxt.module, pa, bl, fw, z_planets[idx + 1], helix,
                                                 +1.0, sun_phases[idx + 1], nxt.tip_sun, nxt.form_sun,
                                                 nxt.addendum, nxt.x_sun)
            extras = [K.cylinder(neck_r, zt - t_top / 2.0, z_planets[idx + 1] + 1.0), gear_next]
            hub_r = neck_r + 1.0
            cuts = []
        if p.cage:
            bottom = B.build_cage_bottom_plate(cd, n_pl, pin_hole, z0 - clr - t_bot, t_bot,
                                               max(geo.tip_sun, collar_r if idx == 0 else 0.0) + 0.6, r_out)
            parts.append(Part(f"carrier_bottom_s{n}", f"Carrier_Bottom_Stg{n}", f"{names['carrier_bottom']} ({tag})",
                              g_key, g_label, bottom, COLORS["carrier"], explode=[(0.0, 0.0, level - 0.6)]))
            top = B.build_cage_top_plate(cd, n_pl, pin_hole, zp, t_top, r_out, hub_r, extras, cuts)
            label = (names["carrier_top_out"] if is_last else names["carrier_top_sun"].format(n=n + 1)) + f" ({tag})"
            parts.append(Part(f"carrier_top_s{n}", f"Carrier_Top_Stg{n}", label, g_key, g_label, top,
                              COLORS["carrier"], explode=[(0.0, 0.0, level + 1.8)], gear=not is_last))
            # pimler
            need = t_bot + clr + fw + clr + t_top
            # never into the gap to the next carrier (it turns at another speed): at most clr - 0.3 beyond the plates
            pin_len = (pick_dowel(need, 0.4 * min(t_top, t_bot), max(0.0, clr - 0.3), 0.6 * min(t_top, t_bot))
                       if p.pin_steel else need - 0.4)
            cut_note = (" — " + names["pin_cut"]) if p.pin_steel and not dowel_is_standard(pin_len) else ""
            pin = B.build_pin(pin_d, pin_len, flat=not p.pin_steel)
            ppl = [K.trsf_translate(x, y, z0 - clr - t_bot) for x, y in centers]
            ppr = None if p.pin_steel else K.trsf_rotate_axis((0, 0, 0), (1, 0, 0), -math.pi / 2.0)
            parts.append(Part(f"pin_s{n}", f"Pin_Stg{n}", f"{names['pin']} Ø{pin_d:g}×{pin_len:g} ({tag})", g_key,
                              g_label, pin, COLORS["pin"] if p.pin_steel else COLORS["carrier"], placements=ppl,
                              explode=[(ux * 1.25, uy * 1.25, level + 2.4) for ux, uy in radial],
                              printable=not p.pin_steel, print_trsf=ppr,
                              spec=(f"ISO 8734 / DIN 6325 Ø{pin_d:g} m6 × {pin_len:g} mm{cut_note}" if p.pin_steel
                                    else ""),
                              note="" if p.pin_steel else "Düzlük alta gelecek şekilde yatay basın"))
        else:
            pin_r = pin_d / 2.0
            boss_r = min(pin_r + 2.5, geo.tip_ring - cd - 0.6)
            groove = None
            if circlip_type != "NONE":
                ci = get_circlip_info(circlip_type, pin_d)
                groove = (float(ci["d2"]), float(ci["m"]))
            carrier = B.build_single_carrier(cd, n_pl, pin_d, z0, fw, clr, t_top, PIN_TAIL, hub_r, boss_r,
                                             st["inner_race_d"] / 2.0 - 0.2 if st["bearings_per_planet"] else pin_r + 0.8,
                                             groove, extras, cuts)
            c_label = names["carrier"] if is_last else names["carrier_sun"].format(n=n + 1)
            parts.append(Part(f"carrier_s{n}", f"Carrier_Stg{n}", f"{c_label} ({tag})", g_key, g_label,
                              carrier, COLORS["carrier"], explode=[(0.0, 0.0, level + 1.8)],
                              note="Tek plaka: iki yüzde de çıkıntı var, destekle basın", gear=not is_last))
            if make_circlips:
                ci = get_circlip_info(circlip_type, pin_d)
                clip = B.build_snap_circlip(float(ci["d1"]), float(ci["d2"]), float(ci["s"]), z0 - 0.3)
                parts.append(Part(f"circlip_s{n}", f"Circlip_Stg{n}", f"{names['circlip']} ({tag})", g_key, g_label,
                                  clip, COLORS["circlip"],
                                  placements=[K.trsf_place(x, y, 0.0, 2 * math.pi * i / n_pl) for i, (x, y) in enumerate(centers)],
                                  explode=[(ux * 0.7, uy * 0.7, level - 0.3) for ux, uy in radial]))

        if is_last and out["type"] == "ARM" and p.declutch:
            parts += _declutch_parts(p, out, R, z_cover_top + lay.arm_gap, g_key, g_label, level, names)
        elif is_last and out["type"] == "ARM":
            key_h = arm_key_height(out["hub_d"])
            arm, arm_h = B.build_output_arm(p.arm_shape, p.arm_length, p.arm_width, p.arm_thickness, out["hub_d"],
                                            key_h, ARM_FLAT * out["hub_d"], p.hub_fastener)
            z_arm = z_cover_top + lay.arm_gap
            round_arm = p.arm_shape == "ROUND"
            size = (f"Ø{p.arm_width:g} × {p.arm_length:g} mm" if round_arm
                    else f"{p.arm_width:g} × {p.arm_length:g} × {p.arm_thickness:g} mm")
            parts.append(Part("output_arm", "Output_Arm", f"{names['arm_round' if round_arm else 'arm_flat']} {size}",
                              g_key, g_label, arm, COLORS["carrier"], placements=[K.trsf_translate(0, 0, z_arm)],
                              explode=[(0.0, 0.0, level + 4.5)],
                              note="Göbek alta gelecek şekilde, düz yüzü tablada basın; %40+ dolgu, 4+ duvar"))
            pts = B.hub_screw_points(out["hub_d"], p.hub_fastener)
            floor = (arm_h - B.M3_HEAD_DEPTH) - (key_h + 0.4)          # kol tabanı: havşa altından cebe
            if p.hub_fastener == "INSERT":
                avail = floor + 0.4 + B.INSERT_DEPTH - 0.7
                scr_len = max([L for L in (6, 8, 10, 12, 16, 20) if L <= avail] or [6])
            else:                                                       # somunu tamamen geçip 1 diş taşsın
                need = floor + 0.4 + B.NUT_ROOF_ARM + B.M3_NUT_M + 0.5
                scr_len = min([L for L in (6, 8, 10, 12, 16, 20, 25) if L >= need] or [25])
            m3 = {"d": 3.0, "head_d": 5.5, "head_h": 3.0}
            parts.append(Part("arm_screw", f"Screw_M3x{scr_len}_Arm", f"M3×{scr_len} {names['arm_screw']}",
                              g_key, g_label, B.build_socket_bolt(m3, scr_len), COLORS["bolt"],
                              placements=[K.trsf_translate(x, y, z_arm + arm_h - B.M3_HEAD_DEPTH) for x, y in pts],
                              explode=[(0.0, 0.0, level + 6.0)] * len(pts), printable=False,
                              spec=f"ISO 4762 M3 × {scr_len} mm"))
            out_top = z_arm + arm_h

        if is_last and p.hub_fastener == "NUT" and out["type"] in ("FLANGE", "ARM"):
            # yan yuvalara itilen tutsak somunlar (vidalar flanşa/kola üstten girer)
            seats = B.hub_nut_seats(out["type"], out["hub_d"], z_cover_top, lay.output_protrusion,
                                    arm_key_height(out["hub_d"]), p.hub_fastener, lay.arm_gap)
            parts.append(Part("hub_nut", "Nut_M3_Output_Hub", f"M3 {names['hub_nut']}", g_key, g_label,
                              B.build_hex_nut(B.M3_NUT), COLORS["bolt"],
                              placements=[K.trsf_place(x, y, z, a) for x, y, z, a in seats],
                              explode=[(math.cos(a - math.pi / 6.0) * 1.2, math.sin(a - math.pi / 6.0) * 1.2,
                                        level + 1.8) for _x, _y, _z, a in seats],
                              printable=False, spec="ISO 4032 M3"))

        if is_last and out["type"] == "SHAFT_STEEL":
            sh_len = (z_cover_top + out_len) - (zt - t_top / 2.0 - 0.5)
            shaft = B.build_steel_shaft(out["shaft_d"], sh_len)
            parts.append(Part("steel_shaft", "Steel_Output_Shaft", names["steel_shaft"], g_key, g_label, shaft,
                              COLORS["shaft"], placements=[K.trsf_translate(0, 0, zt - t_top / 2.0 - 0.5)],
                              explode=[(0.0, 0.0, level + 4.0)], printable=False,
                              spec=f"Çelik D-mil Ø{out['shaft_d']:g} h6 × {sh_len:.0f} mm"))

    # ── 4) Kapak, çıkış rulmanı, cıvatalar ───────────────────────────────────
    top_level = 2.0 * n_st + 1.5
    if make_housing:
        report("cover", 90)
        if not ring:
            cover = B.build_top_cover(hd, housing_len, cover_t, ob["d_outer"] + p.bearing_tol, ob["width"],
                                      out["hub_d"] / 2.0 + 0.6, tie, counterbore, True)
            parts.append(Part("top_cover", "Top_Bearing_Cover", names["cover"], "housing", g_housing, cover,
                              COLORS["cover"], explode=[(0.0, 0.0, top_level)], print_trsf=_flip_x(),
                              note="Ters çevrilmiş basılır (rulman yuvası yukarı)"))
            obrg = B.build_bearing(ob["d_inner"], ob["d_outer"], ob["width"])
            parts.append(Part("output_bearing", f"Bearing_{out['bearing']}_Output",
                              f"{out['bearing']} {names['out_bearing']}", "housing", g_housing, obrg, COLORS["bearing"],
                              placements=[K.trsf_translate(0, 0, housing_len)], explode=[(0.0, 0.0, top_level - 0.6)],
                              printable=False,
                              spec=f"{out['bearing']} ({ob['d_inner']:g}x{ob['d_outer']:g}x{ob['width']:g})"))
        if tie_rod_kind == "bolt":
            bolt = B.build_socket_bolt(tie, bolt_len)
            parts.append(Part("tie_rod_bolt", f"Bolt_{hd['tie_rod']}x{bolt_len:g}", f"{hd['tie_rod']}×{bolt_len:g} {names['bolt']}",
                              "fasteners", g_fast, bolt, COLORS["bolt"],
                              placements=[K.trsf_translate(x, y, z_cover_top - counterbore) for x, y in hd["positions"]],
                              explode=[(0.0, 0.0, top_level + 2.0)] * len(hd["positions"]), printable=False,
                              spec=f"ISO 4762 {hd['tie_rod']} × {bolt_len:g} mm"))
        else:
            # gövde en uzun standart cıvatadan uzun: kesilmiş saplama, altta tutsak somun, üstte kapak somunu
            tip = ((-flange_t + 0.6) + (nut_z - 0.6)) / 2.0
            if lay.mount_t > 0:                          # the nuts sit in the bracket shelf
                z0m = -flange_t - lay.mount_t
                tip = ((z0m + 0.3) + (z0m + 2.3)) / 2.0
            rod = K.cylinder(tie["d"] / 2.0, 0.0, bolt_len)
            parts.append(Part("tie_rod_bolt", f"Rod_{hd['tie_rod']}x{bolt_len:g}", f"{hd['tie_rod']}×{bolt_len:g} {names['rod']}",
                              "fasteners", g_fast, rod, COLORS["bolt"],
                              placements=[K.trsf_translate(x, y, tip) for x, y in hd["positions"]],
                              explode=[(0.0, 0.0, top_level + 2.0)] * len(hd["positions"]), printable=False,
                              spec=f"DIN 976 {hd['tie_rod']} × {bolt_len:g} mm"))
            z_top_nut = z_cover_top - counterbore if ring else z_cover_top   # ring: sunk under the drum
            parts.append(Part("tie_rod_top_nut", f"Nut_{hd['tie_rod']}_Top", f"{hd['tie_rod']} {names['nut_top']}",
                              "fasteners", g_fast, B.build_hex_nut(tie), COLORS["bolt"],
                              placements=[K.trsf_place(x, y, z_top_nut, math.atan2(y, x) + math.pi / 6)
                                          for x, y in hd["positions"]],
                              explode=[(0.0, 0.0, top_level + 2.6)] * len(hd["positions"]), printable=False,
                              spec=f"ISO 4032 {hd['tie_rod']}"))
        nut = B.build_hex_nut(tie)
        parts.append(Part("tie_rod_nut", f"Nut_{hd['tie_rod']}", f"{hd['tie_rod']} {names['nut']}", "fasteners", g_fast,
                          nut, COLORS["bolt"],
                          placements=[K.trsf_place(x, y, nut_z + 0.15, math.atan2(y, x) + math.pi / 6)
                                      for x, y in hd["positions"]],
                          explode=[(math.cos(math.atan2(y, x)) * 1.2, math.sin(math.atan2(y, x)) * 1.2, -2.5)
                                   for x, y in hd["positions"]],
                          printable=False, spec=f"ISO 4032 {hd['tie_rod']}"))

    if lay.mount_t > 0:
        part = bracket_part(hd, motor, tie, flange_t, lay.mount_t, p.mount_type, lang, g_housing, parts,
                            R["warnings"])
        if isinstance(part, str):
            R["warnings"].append(part)
        else:
            parts.append(part)
    report("done", 100)
    eng = R["engineering"]
    gm = get_material(p.load.gear_material)
    sm = get_material(p.load.struct_material)
    printed_mass = 0.0
    for part in parts:
        if part.printable:
            rho = gm["rho"] if (part.gear or part.key.startswith(("sun", "planet", "ring", "drum")))                 else sm["rho"]
            printed_mass += K.volume(part.shape) * part.quantity * rho / 1000.0
    # baskı tablası: her basılacak parçanın baskı yönündeki ölçüleri
    warnings = list(R["warnings"])
    for part in parts:
        if not part.printable or part.key == "output_arm":       # kol için ayrı uyarı (resolve: arm_bed)
            continue
        shp = K.transform(part.shape, part.print_trsf) if part.print_trsf is not None else part.shape
        x0, y0, z0, x1, y1, z1 = K.bounding_box(shp)
        if not D.bed_fits(p, x1 - x0, y1 - y0, z1 - z0):
            text = R["warn_text"]["bed_part"].format(name=part.label, w=x1 - x0, d=y1 - y0, h=z1 - z0,
                                                     bx=p.bed[0], by=p.bed[1], bz=p.bed[2])
            if text not in warnings:
                warnings.append(text)
    summary = {
        "total_ratio": round(R["total_ratio"], 3),
        "stages": n_st,
        "herringbone": p.herringbone,
        "module": R["module"],
        "z_ring": R["z_ring"],
        "housing_diameter": round(hd["body_d"], 1),
        "outer_diameter": round(max(hd["envelope_d"] if make_housing else hd["body_d"],
                                    out.get("drum_od", 0.0)), 1),
        "overall_length": round(lay.overall_length, 1),
        "body_length": round(lay.body_length, 1),
        "part_count": sum(pt.quantity for pt in parts),
        "unique_parts": len(parts),
        "printed_mass_g": round(printed_mass, 0),
        "output_torque": round(eng["output_torque"], 2),
        "max_output_torque": round(eng["max_output_torque"], 2),
        "output_speed": round(eng["output_speed"], 2),
        "efficiency": round(eng["efficiency"], 3),
        "carrier": "cage" if p.cage else "single",
        "output_type": out["type"],
        "arrangement": p.arrangement,
        "drum_bearing": out["bearing"] if ring else "",
        "drum_diameter": round(out.get("drum_od", 0.0), 1),
        "tie_rod": f"{hd['tie_rod']}x{bolt_len:g}",
        "counterbore": counterbore,
        "addendum": p.addendum,
    }
    product = f"Planetary_Gearbox_{('%g' % round(R['total_ratio'], 2)).replace('.', '_')}x"
    hardware = {"bolt_len": bolt_len, "flange_t": flange_t, "motor_screw": pick_motor_screw(flange_t - head_h - 0.3),
                "setscrew": pick_setscrew(collar_r - p.motor_shaft_dia / 2.0), "cover_t": cover_t,
                "hub_fastener": p.hub_fastener if out["type"] in ("FLANGE", "ARM") else "",
                "hub_screw_count": (len(B.hub_screw_points(out["hub_d"], p.hub_fastener))
                                    if out["type"] in ("FLANGE", "ARM") else 0),
                "insert_holes": p.hub_fastener == "INSERT" and ((out["type"] == "FLANGE" and out["hub_d"] >= 14.0)
                                                                or out["type"] == "ARM"),
                "insert_count": len(B.hub_screw_points(out["hub_d"], p.hub_fastener)) if out["type"] == "ARM" else 4}
    if ring:                       # the drum lid screws (the user's part / the arm) replace the hub screws
        n_b = int(out.get("bolt_n", 0))
        hardware.update(hub_fastener=p.hub_fastener if n_b else "", hub_screw_count=n_b,
                        insert_holes=p.hub_fastener == "INSERT" and n_b > 0, insert_count=n_b,
                        drum_bearing=out["bearing"], join_screws=int(out.get("join_n", 0)))
    design_info = {"stages": [{k: v for k, v in s.items() if k not in ("geo", "design", "bearing_info")} | {
                       "geometry": s["geo"].to_dict()} for s in stages],
                   "output": out, "housing": {k: v for k, v in hd.items() if k != "positions"},
                   "hardware": hardware, "params": {"motor": p.motor_code, "motor_shaft": p.motor_shaft_dia,
                                                     "gear_material": p.load.gear_material,
                                                     "struct_material": p.load.struct_material,
                                                     "pin_steel": p.pin_steel, "cage": p.cage,
                                                     "face_width": fw, "helix": helix, "pressure_angle": pa,
                                                     "backlash": bl, "bearing_tol": p.bearing_tol,
                                                     "addendum": p.addendum}}
    kin = assign_kinematics(parts, stages, ring)
    return BuildResult(parts=parts, warnings=warnings, summary=summary, elapsed=time.time() - t_start,
                       product_name=product, engineering=eng, design=design_info, kinematics=kin)



def _plunger_parts(geo: Dict, z_arm: float, g_key: str, g_label: str, level: float, lang: str) -> List[Part]:
    """The index plunger and its thin nut under the arm (both go with the arm)."""
    from core.hardware import plunger_code
    pl = geo["plunger"]
    en = lang == "en"
    code = plunger_code(pl)
    return [Part("declutch_pin", "Index_Plunger", ("Index plunger " if en else "İndeks pimi ") + code, g_key, g_label,
                 B.build_index_plunger(pl, geo["lay"]["local_top"]), COLORS["pin"],
                 placements=[K.trsf_translate(-geo["r_c"], 0.0, z_arm)], explode=[(0.0, 0.0, level + 8.0)],
                 printable=False,
                 spec=(f"{code} (Ganter, spring index plunger with rest position and lock nut) or equivalent — pin "
                       f"Ø{pl['d1']:g}; later a pull solenoid" if en else
                       f"{code} (Ganter, dinlenme konumlu yaylı indeks pimi, kilit somunlu) veya muadili — pim "
                       f"Ø{pl['d1']:g}; ileride çekme solenoidi")),
            Part("declutch_nut", "Index_Plunger_Nut", ("Thin nut " if en else "İnce somun ") + pl["thread"], g_key,
                 g_label, B.build_plunger_nut(pl), COLORS["bolt"],
                 placements=[K.trsf_translate(-geo["r_c"], 0.0, z_arm)], explode=[(0.0, 0.0, level + 4.0)],
                 printable=False, spec=f"ISO 8675 {pl['thread']}")]


def _declutch_parts(p, out: Dict, R: Dict, z0: float, g_key: str, g_label: str, level: float, names: Dict) -> List[Part]:
    """Boşa alınabilen kol: tahrik bileziği + serbest kol + kapak pulu + yaylı indeks pimi + göbek vidaları."""
    from core.engineering import declutch_design
    eng = R["engineering"]
    torque_ka = eng["output_torque"] * p.load.application_factor
    geo = declutch_design(out["hub_d"], torque_ka, p.load.struct_material, p.load.target_sf, p.arm_shape,
                          p.arm_width, p.arm_thickness)
    lay = geo["lay"]
    key_h = arm_key_height(out["hub_d"])
    en = names is NAMES["en"]
    collar = B.build_declutch_collar(out["hub_d"], key_h, ARM_FLAT * out["hub_d"], p.hub_fastener, geo, lay)
    arm = B.build_declutch_arm(p.arm_shape, p.arm_length, p.arm_width, p.arm_thickness, geo, lay["h_a"])
    cap = B.build_declutch_cap(out["hub_d"], p.hub_fastener, geo, DECLUTCH_CAP)
    round_arm = p.arm_shape == "ROUND"
    size = (f"Ø{p.arm_width:g} × {p.arm_length:g} mm" if round_arm
            else f"{p.arm_width:g} × {p.arm_length:g} × {p.arm_thickness:g} mm")
    out_parts = [
        Part("declutch_collar", "Declutch_Collar", "Drive collar (declutch)" if en else "Tahrik Bileziği (boşa alma)",
             g_key, g_label, collar, COLORS["carrier"], placements=[K.trsf_translate(0, 0, z0)],
             explode=[(0.0, 0.0, level + 3.5)], note="Omuz alta gelecek şekilde basın"),
        Part("output_arm", "Output_Arm", f"{names['arm_round' if round_arm else 'arm_flat']} {size}" +
             (" (free on the collar)" if en else " (bilezikte serbest)"), g_key, g_label, arm, COLORS["carrier"],
             placements=[K.trsf_translate(0, 0, z0 + lay["z_arm"])], explode=[(0.0, 0.0, level + 5.0)],
             note="Düz yüzü tablada basın; %40+ dolgu, 4+ duvar"),
        Part("declutch_cap", "Declutch_Cap", "Cap washer" if en else "Kapak Pulu", g_key, g_label, cap,
             COLORS["carrier"], placements=[K.trsf_translate(0, 0, z0 + lay["z_sp"])], explode=[(0.0, 0.0, level + 6.5)]),
    ]
    out_parts += _plunger_parts(geo, z0 + lay["z_arm"], g_key, g_label, level, "en" if en else "tr")
    pts = B.hub_screw_points(out["hub_d"], p.hub_fastener)
    floor = lay["z_cap"] - (key_h + 0.4)
    if p.hub_fastener == "INSERT":
        avail = floor + 0.4 + B.INSERT_DEPTH - 0.7
        scr_len = max([L for L in (6, 8, 10, 12, 16, 20, 25, 30) if L <= avail] or [6])
    else:
        need = floor + 0.4 + B.NUT_ROOF_ARM + B.M3_NUT_M + 0.5
        scr_len = min([L for L in (6, 8, 10, 12, 16, 20, 25, 30, 35) if L >= need] or [35])
    m3 = {"d": 3.0, "head_d": 5.5, "head_h": 3.0}
    out_parts.append(Part("arm_screw", f"Screw_M3x{scr_len}_Arm", f"M3×{scr_len} {names['arm_screw']}", g_key, g_label,
                          B.build_socket_bolt(m3, scr_len), COLORS["bolt"],
                          placements=[K.trsf_translate(x, y, z0 + lay["z_cap"]) for x, y in pts],
                          explode=[(0.0, 0.0, level + 7.0)] * len(pts), printable=False,
                          spec=f"ISO 4762 M3 × {scr_len} mm"))
    return out_parts


def drum_declutch_parts(p, z0: float, screw_pts: List[Tuple[float, float]], fastener: str, torque_ka: float,
                        lang: str, g_key: str, g_label: str, level: float) -> List[Part]:
    """
    Boşa alınabilen tambur / göbek kolu: yüze vidalanan tahrik halkası + boynunda serbest dönen kol + kapak pulu +
    yaylı indeks pimi + uzun M3 vidalar (pul, boyun ve diskten geçip yüzün somun / burçlarına).
    """
    from core.engineering import declutch_design, declutch_hub_d
    screw_r = max(math.hypot(x, y) for x, y in screw_pts)
    geo = declutch_design(declutch_hub_d(0.0, screw_r), torque_ka, p.load.struct_material, p.load.target_sf,
                          p.arm_shape, p.arm_width, p.arm_thickness)
    lay = geo["lay"]
    en = lang == "en"
    disc_r = max(geo["shoulder_r"], screw_r + 5.0)
    collar = B.build_drum_declutch_collar(geo, lay, screw_pts, disc_r)
    arm = B.build_declutch_arm(p.arm_shape, p.arm_length, p.arm_width, p.arm_thickness, geo, lay["h_a"])
    cap = B.build_declutch_cap(0.0, fastener, geo, DECLUTCH_CAP, screw_pts)
    round_arm = p.arm_shape == "ROUND"
    size = (f"Ø{p.arm_width:g} × {p.arm_length:g} mm" if round_arm
            else f"{p.arm_width:g} × {p.arm_length:g} × {p.arm_thickness:g} mm")
    out = [
        Part("declutch_collar", "Declutch_Collar", "Drive ring (release)" if en else "Tahrik Halkası (boşa alma)",
             g_key, g_label, collar, COLORS["carrier"], placements=[K.trsf_translate(0, 0, z0)],
             explode=[(0.0, 0.0, level + 3.0)], note="Disk alta gelecek şekilde basın"),
        Part("output_arm", "Output_Arm", ("Arm " if en else "Kol ") + size + (" (free on the ring)" if en else
                                                                           " (halkada serbest)"),
             g_key, g_label, arm, COLORS["carrier"], placements=[K.trsf_translate(0, 0, z0 + lay["z_arm"])],
             explode=[(0.0, 0.0, level + 4.5)], note="Düz yüzü tablada basın; %40+ dolgu, 4+ duvar"),
        Part("declutch_cap", "Declutch_Cap", "Cap washer" if en else "Kapak Pulu", g_key, g_label, cap,
             COLORS["carrier"], placements=[K.trsf_translate(0, 0, z0 + lay["z_sp"])], explode=[(0.0, 0.0, level + 6.0)]),
    ]
    out += _plunger_parts(geo, z0 + lay["z_arm"], g_key, g_label, level, lang)
    if fastener == "INSERT":
        avail = lay["z_cap"] + B.INSERT_DEPTH - 0.7
        scr_len = float(max([L for L in (6, 8, 10, 12, 16, 20, 25, 30, 35, 40) if L <= avail] or [6]))
    else:
        need = lay["z_cap"] + B.NUT_ROOF_FLANGE + B.M3_NUT_M + 0.5
        scr_len = float(min([L for L in (6, 8, 10, 12, 16, 20, 25, 30, 35, 40, 45) if L >= need] or [45]))
    m3 = {"d": 3.0, "head_d": 5.5, "head_h": 3.0}
    out.append(Part("arm_screw", f"Screw_M3x{scr_len:g}_Arm", f"M3×{scr_len:g} " + ("arm screw" if en else "kol vidası"),
                    g_key, g_label, B.build_socket_bolt(m3, scr_len), COLORS["bolt"],
                    placements=[K.trsf_translate(x, y, z0 + lay["z_cap"]) for x, y in screw_pts],
                    explode=[(0.0, 0.0, level + 7.0)] * len(screw_pts), printable=False,
                    spec=f"ISO 4762 M3 × {scr_len:g} mm"))
    return out


def _arm_screw_len(floor: float, fastener: str) -> float:
    """M3 screw through a printed hub floor into a captive nut (1 thread past it) or a heat-set insert."""
    if fastener == "INSERT":
        avail = floor + B.INSERT_DEPTH - 0.7
        return float(max([L for L in (6, 8, 10, 12, 16, 20) if L <= avail] or [6]))
    need = floor + B.NUT_ROOF_FLANGE + B.M3_NUT_M + 0.5
    return float(min([L for L in (6, 8, 10, 12, 16, 20, 25, 30) if L >= need] or [30]))


def _build_star_stage(p, out, lay, hd, tie, geo, st, centers, radial, pin_hole, pin_d, idx, n, tag, g_key, g_label,
                      level, collar_r, flange_spigot, n_fixed, names, pa, bl, helix, r_out,
                      R_eng: Optional[Dict] = None) -> List[Part]:
    """
    Last stage of a rotating housing: the carrier is fixed (base plate = its bottom, pressed pins, top plate
    with the stub of the drum bearing), the ring gear is the drum with a lid on top. The drum turns on one
    ball bearing in its lid; spur drums are one piece, herringbone drums two halves screwed together.
    """
    clr, fw, t_top = D.CLEARANCE, p.face_width, p.plate_t
    ex = lay.extra
    z_b0, base_t = ex["z_base0"], ex["base_t"]
    z0 = lay.z_planets[idx]
    zp, zt = z0 + fw + clr, lay.carrier_tops[idx]
    n_pl = st["num_planets"]
    level_d = level + 2.6
    parts: List[Part] = []
    # base plate (fixed carrier bottom), clamped by the tie rods, heads sunk below the drum
    hole_r = max(geo.tip_sun, collar_r if idx == 0 else 0.0) + 0.6
    base = B.build_ring_base(hd, z_b0, base_t, hole_r, centers, pin_hole, tie, lay.counterbore,
                             female_spigot=(n_fixed > 0) or flange_spigot, nut_pocket=lay.threaded_rod)
    parts.append(Part("ring_base", "Fixed_Base_Plate", names["ring_base"], "housing", names["g_housing"], base,
                      COLORS["flange"], explode=[(0.0, 0.0, level - 0.8)],
                      note="Pimler alttan yüzey hizasında preslenir; cıvata başları havşaya gömülür"))
    # fixed top plate with the drum bearing stub (inside the pin circle)
    db = get_bearing_info(out["bearing"])
    z_sh = ex["z_shoulder"]
    shoulder_r = inner_race_diameter(db) / 2.0 - 0.2
    stub = [K.cylinder(shoulder_r, zt - t_top / 2.0, z_sh),
            K.cylinder(db["d_inner"] / 2.0, zt - t_top / 2.0, z_sh + db["width"] - 0.3)]
    top = B.build_cage_top_plate(geo.center_distance, n_pl, pin_hole, zp, t_top, r_out, shoulder_r + 1.0, stub, [])
    parts.append(Part(f"carrier_top_s{n}", f"Carrier_Top_Stg{n}", f"{names['carrier_fixed']} ({tag})", g_key,
                      g_label, top, COLORS["carrier"], explode=[(0.0, 0.0, level + 1.8)],
                      note="Göbek yukarı bakacak şekilde, düz yüzü tablada basın"))
    # pins: pressed into the base plate (flush underneath), through the planets into the top plate
    need = base_t + clr + fw + clr + t_top
    # the drum lid turns 0.6 mm above the top plate: a pin may never be longer than the stack (a shorter
    # standard pin only loses engagement in the thick base plate)
    if p.pin_steel:
        fit = [L for L in DOWEL_LENGTHS if L <= need + 1e-6]
        pin_len = float(fit[-1]) if fit and fit[-1] >= need - base_t + 2.0 else need - 0.4
    else:
        pin_len = need - 0.4
    pin = B.build_pin(pin_d, pin_len, flat=not p.pin_steel)
    ppr = None if p.pin_steel else K.trsf_rotate_axis((0, 0, 0), (1, 0, 0), -math.pi / 2.0)
    parts.append(Part(f"pin_s{n}", f"Pin_Stg{n}", f"{names['pin']} Ø{pin_d:g}×{pin_len:g} ({tag})", g_key, g_label,
                      pin, COLORS["pin"] if p.pin_steel else COLORS["carrier"],
                      placements=[K.trsf_translate(x, y, z_b0) for x, y in centers],
                      explode=[(ux * 1.25, uy * 1.25, level + 2.4) for ux, uy in radial],
                      printable=not p.pin_steel, print_trsf=ppr,
                      spec=f"ISO 8734 / DIN 6325 Ø{pin_d:g} m6 × {pin_len:g} mm" if p.pin_steel else "",
                      note="" if p.pin_steel else "Düzlük alta gelecek şekilde yatay basın"))
    # drum bearing on the stub
    parts.append(Part("drum_bearing", f"Bearing_{out['bearing']}_Drum", f"{out['bearing']} {names['drum_bearing']}",
                      "housing", names["g_housing"], B.build_bearing(db["d_inner"], db["d_outer"], db["width"]),
                      COLORS["bearing"], placements=[K.trsf_translate(0, 0, z_sh)],
                      explode=[(0.0, 0.0, level_d - 0.4)], printable=False,
                      spec=f"{out['bearing']} ({db['d_inner']:g}x{db['d_outer']:g}x{db['width']:g})"))
    # the drum
    dz0, z_lu, z_lt = ex["drum_z0"], ex["z_lid0"], ex["z_lid1"]
    drum_r, rim = out["drum_r"], out["rim"]
    reach = drum_r + rim + 2.0
    n_b, n_j = int(out.get("bolt_n", 0)), int(out.get("join_n", 0))
    join_pts = [B._polar_xy(out["join_r"], 2.0 * math.pi * i / n_j) for i in range(n_j)]
    bolt_pts = [B._polar_xy(out["bolt_r"], 2.0 * math.pi * (i + (0.5 if n_j else 0.0)) / n_b) for i in range(n_b)]
    lid_cuts = B.lid_screw_cuts(bolt_pts, z_lt, reach, p.hub_fastener) if n_b else []
    winch = out["type"] == "DRUM_WINCH"
    rope = [B.rope_hole(drum_r, out["rope_d"], z_lt)] if winch else []
    dname = names["drum"]
    m3 = {"d": 3.0, "head_d": 5.5, "head_h": 3.0}
    if p.herringbone:
        tw_d = B.herringbone_twist(fw, geo.r_ring, helix)
        apex = z0 + fw / 2.0
        L_j, c_j, z_nb = B.join_screw_fit(z_lt, dz0, out["lid_t"])
        rims = B.winch_rims(drum_r, rim, dz0, z_lt, chamfer=False) if winch else [None, None]
        lower = B.build_drum_part(geo, pa, bl, [dz0, z0, apex], [0.0, 0.0, -tw_d], drum_r,
                                  extras=[rims[0]] if winch else [],
                                  cuts=B.join_cuts_lower(join_pts, dz0, apex, z_nb, reach))
        upper = B.build_drum_part(geo, pa, bl, [apex, z0 + fw, z_lu], [-tw_d, 0.0, 0.0], drum_r, (z_lu, z_lt),
                                  out["pocket_r"], db["width"], extras=[rims[1]] if winch else [],
                                  cuts=B.join_cuts_upper(join_pts, apex, z_lt, c_j) + lid_cuts + rope)
        parts.append(Part("drum_s1", "Drum_Lower_Half", names["drum_lo"], "housing", names["g_housing"], lower,
                          COLORS["housing"], explode=[(0.0, 0.0, level_d)],
                          note="Alt yüzü tablada basın; somunları yan yuvalara itin"))
        parts.append(Part("drum_s2", "Drum_Upper_Half_Lid", names["drum_hi"], "housing", names["g_housing"], upper,
                          COLORS["housing"], explode=[(0.0, 0.0, level_d + 1.2)], print_trsf=_flip_x(),
                          note="Kapak tablada (ters) basılır"))
        parts.append(Part("join_screw", f"Screw_M3x{L_j:g}_Drum_Joint", f"M3×{L_j:g} {names['join_screw']}",
                          "housing", names["g_housing"], B.build_socket_bolt(m3, L_j), COLORS["bolt"],
                          placements=[K.trsf_translate(x, y, z_lt - c_j) for x, y in join_pts],
                          explode=[(0.0, 0.0, level_d + 2.4)] * n_j, printable=False,
                          spec=f"ISO 4762 M3 × {L_j:g} mm"))
        parts.append(Part("join_nut", "Nut_M3_Drum_Joint", f"M3 {names['join_nut']}", "housing", names["g_housing"],
                          B.build_hex_nut(B.M3_NUT), COLORS["bolt"],
                          placements=[K.trsf_place(x, y, z_nb + 0.15, math.atan2(y, x) + math.pi / 6.0)
                                      for x, y in join_pts],
                          explode=[(math.cos(math.atan2(y, x)) * 1.2, math.sin(math.atan2(y, x)) * 1.2, level_d)
                                   for x, y in join_pts], printable=False, spec="ISO 4032 M3"))
    else:
        extras = B.winch_rims(drum_r, rim, dz0, z_lt, chamfer=True) if winch else []
        drum = B.build_drum_part(geo, pa, bl, [dz0, z_lu], [0.0, 0.0], drum_r, (z_lu, z_lt), out["pocket_r"],
                                 db["width"], extras=extras, cuts=lid_cuts + rope)
        parts.append(Part("drum", "Rotating_Drum", dname, "housing", names["g_housing"], drum, COLORS["housing"],
                          explode=[(0.0, 0.0, level_d)], print_trsf=_flip_x(),
                          note="Kapak tablada (ters) basılır; rulman yuvası yukarı bakar"))
    if p.hub_fastener == "NUT" and n_b:
        parts.append(Part("hub_nut", "Nut_M3_Drum_Lid", f"M3 {names['drum_nut']}", "housing", names["g_housing"],
                          B.build_hex_nut(B.M3_NUT), COLORS["bolt"],
                          placements=[K.trsf_place(x, y, z, a) for x, y, z, a in B.lid_nut_seats(bolt_pts, z_lt)],
                          explode=[(math.cos(a - math.pi / 6.0) * 1.2, math.sin(a - math.pi / 6.0) * 1.2, level_d + 1.0)
                                   for _x, _y, _z, a in B.lid_nut_seats(bolt_pts, z_lt)],
                          printable=False, spec="ISO 4032 M3"))
    if out["type"] == "DRUM_ARM" and p.declutch:
        torque_ka = R_eng["output_torque"] * p.load.application_factor
        parts += drum_declutch_parts(p, z_lt, bolt_pts, p.hub_fastener, torque_ka, "en" if names is NAMES["en"] else "tr",
                                     "housing", names["g_housing"], level_d)
    elif out["type"] == "DRUM_ARM":
        arm, arm_h = B.build_drum_arm(p.arm_shape, p.arm_length, p.arm_width, p.arm_thickness,
                                      D.drum_arm_hub_r(out), bolt_pts)
        round_arm = p.arm_shape == "ROUND"
        size = (f"Ø{p.arm_width:g} × {p.arm_length:g} mm" if round_arm
                else f"{p.arm_width:g} × {p.arm_length:g} × {p.arm_thickness:g} mm")
        parts.append(Part("output_arm", "Output_Arm", f"{names['drum_arm_round' if round_arm else 'drum_arm_flat']} {size}",
                          "housing", names["g_housing"], arm, COLORS["carrier"],
                          placements=[K.trsf_translate(0, 0, z_lt)], explode=[(0.0, 0.0, level_d + 3.5)],
                          note="Göbek alta gelecek şekilde, düz yüzü tablada basın; %40+ dolgu, 4+ duvar"))
        scr_len = _arm_screw_len(arm_h - B.M3_HEAD_DEPTH, p.hub_fastener)
        parts.append(Part("arm_screw", f"Screw_M3x{scr_len:g}_Arm", f"M3×{scr_len:g} {names['arm_screw']}",
                          "housing", names["g_housing"], B.build_socket_bolt(m3, scr_len), COLORS["bolt"],
                          placements=[K.trsf_translate(x, y, z_lt + arm_h - B.M3_HEAD_DEPTH) for x, y in bolt_pts],
                          explode=[(0.0, 0.0, level_d + 5.0)] * len(bolt_pts), printable=False,
                          spec=f"ISO 4762 M3 × {scr_len:g} mm"))
    return parts


def body_motion(body: Dict, theta: float) -> Tuple[float, float, float, float]:
    """(yörünge açısı, öz dönüş açısı, merkez x, merkez y) — giriş açısı theta [rad] için."""
    t = body.get("type")
    if t == "axis":
        return body["factor"] * theta, 0.0, 0.0, 0.0
    if t == "planet":
        cx, cy = body["center"]
        return body["orbit"] * theta, body["spin"] * theta, cx, cy
    return 0.0, 0.0, 0.0, 0.0


def motion_trsf(body: Dict, theta: float):
    """Gövdenin theta giriş açısındaki dönüşümü: Rz(a)·T(c)·Rz(b)·T(-c)."""
    a, b, cx, cy = body_motion(body, theta)
    t = K.trsf_rotate_z(a)
    if abs(b) > 0:
        t = t.Multiplied(K.trsf_rotate_z(b, cx, cy))
    return t


def placed_at(part: Part, i: int, kin: Dict, theta: float):
    """Instance i'nin theta giriş açısındaki katısı (doğrulama ve dışa aktarma için)."""
    base = K.transform(part.shape, part.placements[i]) if part.placements else part.shape
    body = kin["bodies"][part.bodies[i]] if part.bodies else {"type": "ground"}
    return K.transform(base, motion_trsf(body, theta)) if abs(theta) > 0 else base


def kinematics_table(result) -> Dict:
    """
    Fusion eklentisi için: her instance'ın STEP bileşen adı, sırası, rijit gövdesi ve merkezi (mm).
    İçe aktarılan bileşenler ad + konum ile eşleştirilir.
    """
    from .export import ascii_name
    items = []
    for part in result.parts:
        for i in range(part.quantity):
            x0, y0, z0, x1, y1, z1 = K.bounding_box(placed_at(part, i, result.kinematics, 0.0))
            items.append({"name": ascii_name(part.name), "index": i, "body": part.bodies[i] if part.bodies else "ground",
                          "group": part.group, "center": [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
                          "volume": K.volume(part.shape)})
    kin = dict(result.kinematics)
    kin["items"] = items
    return kin


def parts_table(result) -> List[Dict]:
    """Arayüzün parça listesi (bağımsız uygulama ve Fusion eklentisi aynı biçimi kullanır)."""
    return [{"key": p.key, "name": p.name, "label": p.label, "group": p.group, "group_label": p.group_label,
             "color": p.color, "quantity": p.quantity, "printable": p.printable, "spec": p.spec}
            for p in result.parts]


DRUM_KEYS = ("drum", "drum_s1", "drum_s2", "output_arm", "arm_screw", "hub_nut", "join_screw", "join_nut",
             "declutch_collar", "declutch_cap", "declutch_pin", "declutch_nut")


def assign_kinematics(parts: List[Part], stages: List[Dict], ring: bool = False) -> Dict:
    """
    Rijit gövdeler ve giriş açısına (güneş 1) göre dönüş oranları. Çember sabit, güneş giriş,
    taşıyıcı çıkış: kademe k girişi f_k, taşıyıcı c_k = f_k / i_k, planetin taşıyıcıya göre
    kendi ekseni etrafındaki dönüşü r_k = -(f_k - c_k) · Zs/Zp.
    Dönen gövde (ring): son kademenin taşıyıcısı sabit, planetler sabit eksenlerde r_n = -f_n · Zs/Zp
    döner, çember (tambur) d = -f_n · Zs/Zr ile ters yönde döner.
    Gövde tipleri: ground | axis (ana eksen, oran) | planet (yörünge = taşıyıcı, öz dönüş r_k).
    """
    bodies: Dict[str, Dict] = {"ground": {"type": "ground"}, "input": {"type": "axis", "factor": 1.0}}
    f = 1.0
    n_st = len(stages)
    out_factor = 1.0
    for idx, st in enumerate(stages):
        n = idx + 1
        cd = st["geo"].center_distance
        n_pl = st["num_planets"]
        if ring and idx == n_st - 1:
            rel = -f * st["z_sun"] / st["z_planet"]
            for i in range(n_pl):
                ang = 2.0 * math.pi * i / n_pl
                bodies[f"planet{n}_{i}"] = {"type": "planet", "orbit": 0.0, "spin": rel, "carrier": "ground",
                                            "center": [cd * math.cos(ang), cd * math.sin(ang)], "stage": n}
            out_factor = -f * st["z_sun"] / st["z_ring"]
            bodies["drum"] = {"type": "axis", "factor": out_factor, "stage": n}
            break
        c = f / st["ratio"]
        rel = -(f - c) * st["z_sun"] / st["z_planet"]
        bodies[f"carrier{n}"] = {"type": "axis", "factor": c, "stage": n}
        for i in range(n_pl):
            ang = 2.0 * math.pi * i / n_pl
            bodies[f"planet{n}_{i}"] = {"type": "planet", "orbit": c, "spin": rel, "carrier": f"carrier{n}",
                                        "center": [cd * math.cos(ang), cd * math.sin(ang)], "stage": n}
        f = c
        out_factor = c
    for part in parts:
        key = part.key
        q = part.quantity
        stage = int(key.rsplit("_s", 1)[1]) if "_s" in key and key.rsplit("_s", 1)[1].isdigit() else 0
        if ring and key in DRUM_KEYS:
            part.bodies = ["drum"] * q
        elif key == "sun_s1":
            part.bodies = ["input"]
        elif key.startswith("sun_s"):
            part.bodies = [f"carrier{stage - 1}"]
        elif key.startswith("planet_s"):
            part.bodies = [f"planet{stage}_{i}" for i in range(q)]
        elif key.startswith("bearing_s"):
            n_pl = stages[stage - 1]["num_planets"]
            part.bodies = [f"planet{stage}_{i % n_pl}" for i in range(q)]
        elif ring and stage == n_st and key.startswith(("spacer_s", "pin_s", "carrier")):
            part.bodies = ["ground"] * q           # the fixed carrier of the rotating housing
        elif key.startswith(("spacer_s", "pin_s", "carrier", "circlip_s")):
            part.bodies = [f"carrier{stage}"] * q
        elif key in ("steel_shaft", "output_arm", "arm_screw", "hub_nut", "declutch_collar", "declutch_cap",
                     "declutch_pin", "declutch_nut"):
            part.bodies = [f"carrier{len(stages)}"] * q
        else:
            part.bodies = ["ground"] * q
    output = "drum" if ring else f"carrier{n_st}"
    return {"bodies": bodies, "input": "input", "output": output,
            "total_ratio": 1.0 / abs(out_factor) if out_factor else 0.0}
