"""
Requirement-driven design: "my motor does X rpm / Y Nm, I need Z rpm and at least T Nm, it must fit
in D x L and print on my printer" -> ranked gearbox designs + plain-language diagnostics.

Steps:
  1. ratio: from the speeds for fixed-speed motors; for steppers (speed set by the driver) the ratio is
     a free choice up to (max motor speed / output speed)
  2. motor checks: nominal output torque T_m·i·η^n against the requirement (-> required motor torque
     or ratio), steel motor shaft torsion
  3. search with the design engine (core.design.design), planets chosen per stage automatically:
       small   smallest housing that meets the targets (AUTO sizing)
       strong  fill the given space: strongest design within the diameter and the length budget
               (MAX_OD sizing, widest gears); with a stepper the ratio is raised as far as the housing
               can still carry the full motor torque
       short   shortest design
     limits: outer diameter, overall length (motor body included if asked), print bed footprint
  4. rank, resolve warnings of the best ones

Deterministic and offline. The AI assistant calls `solve` as a tool; the UI can call it directly.
"""
import math
import re
import time
from typing import Dict, List, Optional, Tuple

from core.bearing_catalog import BEARING_CATALOG
from core.design import (CLEARANCE, MAX_STAGES, STAGE_COST, TIE_RODS, Params, app_load_from_payload, design,
                         max_planets, normalize_output, resolve)
from core.engineering import LOAD_RESERVE, LoadCase, motor_shaft_check, required_shaft_dia, torsion_allowable
from core.gear_geometry import clamp_addendum
from core.layout import axial_layout, drum_arm_height, output_protrusion, ring_layout
from core.materials import MATERIALS, get_material
from core.motor_catalog import MOTOR_CATALOG, get_motor_info

MAX_STAGE_RATIO = 9.0
CREALITY_K1 = ("creality k1 max", "creality k1", "creality k1c", "creality k1 se")   # print3mf profiles
MIN_RATIO = 3.0
STRONG_MATERIAL = "PACF"
CALL_BUDGET = 1.8         # s per design-engine call
FILL_BUDGET = 4.0         # s for the "fill the space" search (largest housings first)
TOTAL_BUDGET = 40.0       # s for one solve
STRONG_LADDER = (1.0, 0.8, 0.64, 0.5, 0.4, 0.3, 0.22)   # stepper ratio steps (fractions of the maximum)

# Build volume X, Y, Z (mm) of common FDM printers (matched by name, longest match first)
PRINTERS: Dict[str, Tuple[float, float, float]] = {
    "creality k1 max": (300, 300, 300), "creality k1c": (220, 220, 250), "creality k1": (220, 220, 250),
    "creality k2 plus": (350, 350, 350), "creality k2": (260, 260, 260), "ender 3 v3 se": (220, 220, 250),
    "ender 3 v3 ke": (220, 220, 240), "ender 3 v3": (220, 220, 250), "ender 3 s1 pro": (220, 220, 270),
    "ender 3 s1": (220, 220, 270), "ender 3 v2": (220, 220, 250), "ender 3 max": (300, 300, 340),
    "ender 3": (220, 220, 250), "ender 5 s1": (220, 220, 280), "ender 5 plus": (350, 350, 400),
    "cr 10 smart pro": (300, 300, 400), "cr 10": (300, 300, 400), "bambu lab x1": (256, 256, 256),
    "x1 carbon": (256, 256, 256), "x1c": (256, 256, 256), "x1e": (256, 256, 256), "p1s": (256, 256, 256),
    "p1p": (256, 256, 256), "p2s": (256, 256, 256), "a1 mini": (180, 180, 180), "bambu lab a1": (256, 256, 256),
    "bambu a1": (256, 256, 256), "h2d": (325, 320, 325), "prusa mk4": (250, 210, 220), "mk4s": (250, 210, 220),
    "prusa mk3": (250, 210, 210), "prusa core one": (250, 220, 270), "core one": (250, 220, 270),
    "prusa xl": (360, 360, 360), "prusa mini": (180, 180, 180), "neptune 4 max": (420, 420, 480),
    "neptune 4 plus": (320, 320, 385), "neptune 4 pro": (225, 225, 265), "neptune 4": (225, 225, 265),
    "kobra 2 max": (420, 420, 500), "kobra 2 plus": (320, 320, 400), "kobra 3": (250, 250, 260),
    "kobra 2": (220, 220, 250), "voron 2.4 350": (350, 350, 340), "voron 2.4 300": (300, 300, 280),
    "voron 2.4 250": (250, 250, 230), "voron trident 300": (300, 300, 250), "voron trident": (250, 250, 250),
    "qidi x max 3": (325, 325, 315), "qidi x plus 3": (280, 280, 270), "qidi q1 pro": (245, 245, 240),
    "qidi plus4": (305, 305, 280), "adventurer 5m": (220, 220, 220), "sidewinder x2": (300, 300, 400),
    "sovol sv08": (350, 350, 345), "sovol sv07": (220, 220, 250), "sovol sv06": (220, 220, 250),
}

BRANDS = ("creality", "bambu lab", "bambu", "prusa", "elegoo", "anycubic", "qidi", "sovol", "voron", "artillery",
          "flashforge")

TEXT = {
    "tr": {
        "ratio_conflict": "Verilen oran ({given:g}:1) devirlerle uyuşmuyor: {n_in:g} rpm → {n_out:g} rpm için oran {ratio:.1f}:1 olmalı. Devirleri esas aldım.",
        "ratio_low": "Oran {ratio:.2f}:1 çok düşük; planet redüktör en az ~3:1 verir (daha düşük oran için kayış/düz dişli düşünün).",
        "ratio_high": "Oran {ratio:.0f}:1, {n} kademenin pratik sınırının (~{lim:.0f}:1) üstünde.",
        "stepper": "Step motor: hız sürücüden ayarlanır, oran serbest seçilir. {n_out:g} rpm çıkış için motor en fazla {n_max:g} rpm → oran en fazla {i_max:.0f}:1.",
        "speed_high": "{ratio:g}:1 ile {n_out:g} rpm çıkış için motor {n_m:.0f} rpm dönmeli; bu, {n_max:g} rpm üst sınırının üstünde (step motorun torku yüksek devirde düşer).",
        "strong_ratio": "Verilen alanda tam motor torkunu güvenle taşıyan en yüksek oran {i:.0f}:1 (motor {n_m:.0f} rpm) → çıkış ~{t:.0f} Nm.",
        "strong_capped": "{i_max:.0f}:1 oranında bu alan motorun tam torkuna yetmiyor (kapasite {cap:.0f} Nm < {need:.0f} Nm); sürücü akımını ~%{pct:.0f}'e sınırlarsanız bu oran da kullanılabilir.",
        "torque_short": "Motor torku yetmiyor: {tm:g} Nm × {ratio:.1f} × verim {eta:.2f} = {tout:.0f} Nm < istenen {treq:g} Nm. Gerekli motor torku ≥ {tm_need:.2f} Nm veya oran ≥ {r_need:.0f}:1 (çıkış ~{n_need:.2f} rpm).",
        "torque_ok": "Nominal çıkış torku {tout:.0f} Nm (istenen ≥ {treq:g} Nm) — motor yeterli.",
        "torque_short_speed": "Motor torku yetmiyor: {tm:g} Nm × {ratio:.1f} × verim {eta:.2f} = {tout:.0f} Nm < istenen {treq:g} Nm. {n_out:g} rpm çıkışta oran en fazla {ratio:.1f}:1 (motor {n_max:g} rpm). Ya en az {tm_need:.2f} Nm torklu bir motor ya da en fazla {n_ok:.2f} rpm çıkış hızı (oran {r_need:.0f}:1) gerekir.",
        "shaft_auto": "Çıkış mili çapı torka göre seçildi: {kind} Ø{d:g} mm (sürekli {t:.0f} Nm, emniyet hedefi {sf:g}).",
        "no_ratio": "Oran veya çıkış hızı verilmedi: istenen çıkış devrini (rpm), oranı ya da gereken çıkış torkunu yazın.",
        "ratio_from_torque": "Oran ve hız verilmedi: {treq:g} Nm çıkış torku için en küçük oran {ratio:.1f}:1 seçildi (çıkış ~{n_out:.1f} rpm).",
        "motor_shaft": "Motor mili Ø{d:g} mm, {tm:g} Nm için ince (çelik mil burulma S={s:.2f}); ~Ø{need:.0f} mm veya üstü mil gerekir. Daha kalın milli motor ya da çelik kaplin/göbek kullanın.",
        "planets": "Kademe başına ~{i:.1f}:1 oranda en fazla {n} planet sığar; planet sayısı her kademede otomatik seçildi.",
        "no_solution": "{od} içinde istenen dayanımı sağlayan tasarım bulunamadı. En yakın: {best} — sürekli kapasite {cap:.0f} Nm (gereken ~{need:.0f} Nm), sınırlayan: {lim}.",
        "no_candidate": "Hiçbir diş kombinasyonu bulunamadı: {hint}",
        "no_solution_hint": "Seçenekler: daha büyük çap, daha güçlü malzeme (PA-CF), daha düşük emniyet hedefi/uygulama faktörü, ya da tork ihtiyacını azaltmak.",
        "bed_part": "Gövde ve flanş ~{fp:.0f}×{fp:.0f} mm, baskı tablasından ({bed:.0f} mm) büyük — daha büyük tablalı yazıcı veya parçalı gövde gerekir.",
        "length_budget": "Boy bütçesi {L:.0f} mm → en fazla ~{fw:.0f} mm diş genişliği ({n} kademe).",
        "length_short": "Boy bütçesi {L:.0f} mm, {n} kademe için çok kısa: en dar dişlilerle (6 mm) bile redüktör ~{need:.0f} mm olur. Boy sınırını artırın veya oranı düşürün (daha az kademe).",
        "motor_len": "Toplam boy sınırından motor gövdesi ({ml:.0f} mm) düşüldü: redüktöre {L:.0f} mm kalıyor.",
        "printer": "Yazıcı: {name} → tabla {x:.0f}×{y:.0f}×{z:.0f} mm; parçalar buna göre sınırlandı.",
        "alt_material": "{mat} ile çözüm bulunamadı; {alt} ile bulunan tasarım alternatif olarak eklendi.",
        "no_od_cap": "Dış çap sınırı verilmedi; en küçük uygun gövde arandı.",
        "strong_no_cap": "En güçlü tasarım için çap sınırı verilmedi; baskı tablası sınır alındı.",
        "arm_tip": "{L:.0f} mm kolun ucunda sürekli taşınabilecek kuvvet ≈ {f:.0f} N (~{kg:.1f} kg); önerilen ×{res:g} "
                   "tork rezerviyle ~{kg_r:.1f} kg. Kolun ucundaki yükü (kg) söylerseniz uygunluğunu kontrol ederim.",
        "load": "Uygulama yükü: {desc} → {t:.1f} Nm; önerilen ×{res:g} rezervle en az {treq:.1f} Nm çıkış torku arandı.",
        "load_no_radius": "Yük ({v:g} {u}) verildi ama kuvvet kolu yok: makara / tambur yarıçapını veya kolun boyunu "
                          "girin, yoksa tork hesaplanamaz.",
        "arm_auto_flat": "Kol kesiti torka göre seçildi: {L:.0f} mm yassı kol, {w:.0f} × {t:.0f} mm.",
        "arm_auto_round": "Kol kesiti torka göre seçildi: {L:.0f} mm yuvarlak kol, Ø{w:.0f} mm.",
        "bearing": "Planet rulmanı: {bc} (elinizdeki rulman) — sığmadığı kademeler için daha büyük planet seçildi.",
        "ring": "Dönen gövde: son kademenin taşıyıcısı sabit, çember (tambur) çıkış — o kademenin oranı Zr/Zs (bir "
                "eksik) ve çıkış ters yönde döner.",
        "winch_radius": "Vinç tamburu: yükün kuvvet kolu tasarlanan tamburun halat yarıçapından alındı (~{r:.0f} mm).",
        "speedup_form": "Hız artırıcı (jeneratör / krank) tasarımı formdan yapılır: 1. sekmede düzeni seçip giriş "
                        "torkunu ve devrini girin; çözücü redüktör olarak çözdü.",
    },
    "en": {
        "ratio_conflict": "The given ratio ({given:g}:1) does not match the speeds: {n_in:g} rpm → {n_out:g} rpm needs {ratio:.1f}:1. The speeds were used.",
        "ratio_low": "Ratio {ratio:.2f}:1 is too low; a planetary stage gives at least ~3:1 (consider a belt or spur pair).",
        "ratio_high": "Ratio {ratio:.0f}:1 exceeds the practical limit of {n} stages (~{lim:.0f}:1).",
        "stepper": "Stepper motor: the driver sets the speed, so the ratio is a free choice. For {n_out:g} rpm output the motor runs at most {n_max:g} rpm → ratio at most {i_max:.0f}:1.",
        "speed_high": "With {ratio:g}:1 the motor must turn {n_m:.0f} rpm for {n_out:g} rpm output, above the {n_max:g} rpm limit (stepper torque drops at high speed).",
        "strong_ratio": "Highest ratio whose housing safely carries the full motor torque in this space: {i:.0f}:1 (motor {n_m:.0f} rpm) → ~{t:.0f} Nm output.",
        "strong_capped": "At {i_max:.0f}:1 this space cannot carry the full motor torque (capacity {cap:.0f} Nm < {need:.0f} Nm); it can still be used with the driver current limited to ~{pct:.0f}%.",
        "torque_short": "Motor torque too low: {tm:g} Nm × {ratio:.1f} × efficiency {eta:.2f} = {tout:.0f} Nm < required {treq:g} Nm. Needs a motor with ≥ {tm_need:.2f} Nm or a ratio ≥ {r_need:.0f}:1 (output ~{n_need:.2f} rpm).",
        "torque_ok": "Nominal output torque {tout:.0f} Nm (required ≥ {treq:g} Nm) — the motor is sufficient.",
        "torque_short_speed": "Motor torque too low: {tm:g} Nm × {ratio:.1f} × efficiency {eta:.2f} = {tout:.0f} Nm < required {treq:g} Nm. At {n_out:g} rpm output the ratio is at most {ratio:.1f}:1 (motor {n_max:g} rpm). Either a motor with ≥ {tm_need:.2f} Nm or an output speed of at most {n_ok:.2f} rpm (ratio {r_need:.0f}:1) is needed.",
        "shaft_auto": "Output shaft diameter chosen for the torque: {kind} Ø{d:g} mm ({t:.0f} Nm continuous, safety target {sf:g}).",
        "no_ratio": "No ratio or output speed given: state the output speed (rpm), the ratio or the required output torque.",
        "ratio_from_torque": "No ratio or speed given: the smallest ratio for {treq:g} Nm output torque was chosen, {ratio:.1f}:1 (output ~{n_out:.1f} rpm).",
        "motor_shaft": "Motor shaft Ø{d:g} mm is too thin for {tm:g} Nm (steel shaft torsion S={s:.2f}); needs ~Ø{need:.0f} mm or more. Use a motor with a thicker shaft or a steel coupling/hub.",
        "planets": "At ~{i:.1f}:1 per stage at most {n} planets fit; the planet count was chosen per stage automatically.",
        "no_solution": "No design within {od} meets the strength targets. Closest: {best} — continuous capacity {cap:.0f} Nm (needs ~{need:.0f} Nm), limited by: {lim}.",
        "no_candidate": "No tooth combination was found: {hint}",
        "no_solution_hint": "Options: a larger diameter, a stronger material (PA-CF), lower safety target / application factor, or less torque.",
        "bed_part": "Housing and flange are ~{fp:.0f}×{fp:.0f} mm, larger than the print bed ({bed:.0f} mm) — needs a larger printer or a split housing.",
        "length_budget": "Length budget {L:.0f} mm → at most ~{fw:.0f} mm face width ({n} stages).",
        "length_short": "Length budget {L:.0f} mm is too short for {n} stages: even with the narrowest gears (6 mm) the gearbox is ~{need:.0f} mm. Allow more length or a lower ratio (fewer stages).",
        "motor_len": "The motor body ({ml:.0f} mm) was subtracted from the length limit: {L:.0f} mm remain for the gearbox.",
        "printer": "Printer: {name} → bed {x:.0f}×{y:.0f}×{z:.0f} mm; parts were limited to it.",
        "alt_material": "No solution with {mat}; a design with {alt} was added as an alternative.",
        "no_od_cap": "No diameter limit given; the smallest suitable housing was searched.",
        "strong_no_cap": "No diameter limit for the strongest design; the print bed was used as the limit.",
        "arm_tip": "Continuous force at the tip of the {L:.0f} mm arm ≈ {f:.0f} N (~{kg:.1f} kg); with the recommended "
                   "×{res:g} torque reserve ~{kg_r:.1f} kg. Tell me the load at the arm tip (kg) and I will check it.",
        "load": "Application load: {desc} → {t:.1f} Nm; with the recommended ×{res:g} reserve at least {treq:.1f} Nm "
                "output torque was searched.",
        "load_no_radius": "A load ({v:g} {u}) was given without its lever arm: enter the pulley / drum radius or the arm "
                          "length, otherwise the torque cannot be computed.",
        "ring": "Rotating housing: the last carrier is fixed and the ring (drum) is the output — that stage gives "
                "Zr/Zs (one less) and the output turns the opposite way.",
        "winch_radius": "Winch drum: the lever arm of the load is the rope radius of the designed drum (~{r:.0f} mm).",
        "speedup_form": "Speed-up (generator / crank) designs are made in the form: choose the arrangement on tab 1 and "
                        "enter the input torque and speed; the solver treated it as a reducer.",
        "arm_auto_flat": "Arm section chosen for the torque: {L:.0f} mm flat arm, {w:.0f} × {t:.0f} mm.",
        "arm_auto_round": "Arm section chosen for the torque: {L:.0f} mm round arm, Ø{w:.0f} mm.",
        "bearing": "Planet bearing: {bc} (the ones you have) — planets were sized so it fits.",
    },
}


def _f(d: Dict, key: str, default: float) -> float:
    try:
        v = d.get(key, default)
        return float(default if v in (None, "") else v)
    except (TypeError, ValueError):
        return float(default)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9.]+", " ", str(s).lower()).strip()


def printer_bed(name: str) -> Optional[Tuple[str, Tuple[float, float, float]]]:
    """Build volume of a printer named in plain words ('Creality K1 Max', 'bambu p1s' ...)."""
    if not name:
        return None
    n = " " + _norm(name) + " "
    keys = []
    for key in PRINTERS:                           # also without the brand: "k1 max", "p1s", "mk4"
        keys.append((key, key))
        for brand in BRANDS:
            if key.startswith(brand + " ") and any(ch.isdigit() for ch in key[len(brand) + 1:]):
                keys.append((key[len(brand) + 1:], key))
    for alias, key in sorted(keys, key=lambda k: len(k[0]), reverse=True):
        if " " + alias + " " in n:
            return key, PRINTERS[key]
    return None


def normalize(req: Dict) -> Dict:
    """Fill defaults (motor catalog, materials, printer) and coerce types."""
    code = str(req.get("motor_preset") or "CUSTOM").upper()
    if code not in MOTOR_CATALOG:
        code = "CUSTOM"
    motor = get_motor_info(code)
    gm = str(req.get("gear_material") or "AUTO").upper()
    sm = str(req.get("struct_material") or gm).upper()
    bed = (_f(req, "bed_x", 256.0), _f(req, "bed_y", 256.0), _f(req, "bed_z", 256.0))
    printer = printer_bed(str(req.get("printer") or ""))
    if printer:
        bed = printer[1]
    free = req.get("free_speed")
    bearing = str(req.get("planet_bearing") or "AUTO").upper()
    out = {
        "motor_preset": code,
        "motor_kind": motor.get("kind", "custom"),
        "motor_torque": _f(req, "motor_torque", motor.get("torque_nm", 0.4)),
        "motor_speed": _f(req, "motor_speed", motor.get("speed_rpm", 300)),
        "motor_shaft_dia": _f(req, "motor_shaft_dia", motor.get("default_shaft_dia", 5.0)),
        "motor_shaft_type": str(req.get("motor_shaft_type") or motor.get("default_shaft_type", "ROUND")).upper(),
        "motor_length": _f(req, "motor_length", motor.get("body_length", 40.0)),
        "free_speed": bool(free) if free is not None else motor.get("kind") == "stepper",
        "output_speed": _f(req, "output_speed", 0.0),
        "ratio": _f(req, "ratio", 0.0),
        "ratio_tol": max(0.5, _f(req, "ratio_tol", 3.0)),
        "min_output_torque": max(0.0, _f(req, "min_output_torque", 0.0)),
        "max_od": max(0.0, _f(req, "max_od", 0.0)),
        "max_length": max(0.0, _f(req, "max_length", 0.0)),
        "length_includes_motor": bool(req.get("length_includes_motor", True)),
        "bed": bed,
        "printer": printer[0] if printer else "",
        "fit_bed": bool(req.get("fit_bed", True)),
        "gear_material": gm if gm in MATERIALS or gm == "AUTO" else "AUTO",
        "struct_material": sm if sm in MATERIALS or sm == "AUTO" else "AUTO",
        "planet_bearing": bearing if bearing in BEARING_CATALOG and bearing != "CUSTOM_PIN" else "AUTO",
        "herringbone": bool(req.get("herringbone", True)),
        "helix_angle": _f(req, "helix_angle", 20.0),
        "output_type": str(req.get("output_type") or "FLANGE").upper(),
        "arrangement": str(req.get("arrangement") or "CARRIER").upper(),
        "rope_dia": _f(req, "rope_dia", 4.0),
        "output_shaft_dia": _f(req, "output_shaft_dia", 0.0),
        "output_shaft_len": _f(req, "output_shaft_len", 20.0),
        "arm_shape": str(req.get("arm_shape") or "FLAT").upper(),
        "arm_length": _f(req, "arm_length", 100.0),
        "arm_width": _f(req, "arm_width", 0.0),
        "arm_thickness": _f(req, "arm_thickness", 0.0),
        "arm_load": _f(req, "arm_load", 0.0),
        "hub_fastener": "INSERT" if str(req.get("hub_fastener", "NUT")).upper() == "INSERT" else "NUT",
        "num_planets": int(_f(req, "num_planets", 0)),
        "profile_shift": req.get("profile_shift") if req.get("profile_shift") not in (None, "") else "AUTO",
        "stages_count": int(_f(req, "stages_count", 0)),
        "face_width": _f(req, "face_width", 0.0),
        "app_factor": _f(req, "app_factor", 1.25),
        "target_sf": _f(req, "target_sf", 1.4),
        "target_sh": _f(req, "target_sh", 1.0),
        "target_life": _f(req, "target_life", 2000.0),
        "pin_type": str(req.get("pin_type") or "STEEL").upper(),
        "carrier_type": "SINGLE" if str(req.get("carrier_type", "CAGE")).upper() == "SINGLE" else "CAGE",
        "prefer": str(req.get("prefer") or "small").lower(),
        "lang": "en" if str(req.get("lang", "tr")).lower().startswith("en") else "tr",
    }
    out["speedup_asked"] = out["arrangement"] == "SPEED_UP"
    if out["speedup_asked"]:                    # the solver designs reducers; a speed-up is set up in the form
        out["arrangement"] = "CARRIER"
    out["arrangement"], out["output_type"] = normalize_output(out["arrangement"], out["output_type"])
    if out["prefer"] not in ("small", "strong", "short"):
        out["prefer"] = "small"
    if out["num_planets"] < 2:
        out["num_planets"] = 0
    out["arm_auto"] = out["arm_width"] <= 0 or (out["arm_shape"] == "FLAT" and out["arm_thickness"] <= 0)
    out["shaft_auto"] = out["output_shaft_dia"] <= 0
    out["addendum_coef"] = clamp_addendum(_f(req, "addendum_coef", 1.0))
    # application load (what the gearbox has to move): as entered + the resulting output torque
    app = app_load_from_payload(req, out["output_type"], max(10.0, out["arm_length"]))
    out.update(load_value=app["load_value"], load_unit=app["load_unit"],
               load_radius=_f(req, "load_radius", 0.0) if app["load_unit"] != "NM" else 0.0,
               load_torque=app["load_torque"], load_force=app["load_force"], load_lever=app["load_radius"])
    out["winch_est"] = False
    if out["output_type"] == "DRUM_WINCH" and app["load_force"] > 0 and app["load_radius"] <= 0:
        # the rope radius is known only with the design: first a typical drum, solve() refines it once
        est = _f(req, "_winch_r", 40.0)
        out.update(load_lever=est, load_torque=app["load_force"] * est / 1000.0, winch_est=not req.get("_winch_r"))
    out["arm_load"] = 0.0                       # legacy tip force: now part of the load above
    return out


STEEL_SHAFTS = (6.0, 8.0, 10.0, 12.0, 14.0, 15.0, 16.0, 17.0, 20.0, 25.0, 30.0, 35.0, 40.0)


def auto_output_shaft(r: Dict, ratio: float, stages: int, gm: str, sm: str) -> float:
    """Output shaft diameter for the output torque (shaft outputs, when the user did not give one)."""
    steel = r["output_type"] == "SHAFT_STEEL"
    t_ka = r["motor_torque"] * ratio * get_material(gm)["eta"] ** stages * r["app_factor"]
    allow = 150.0 if steel else torsion_allowable(get_material(sm))
    d = required_shaft_dia(t_ka, allow, r["target_sf"])
    if steel:
        return next((s for s in STEEL_SHAFTS if s >= d), STEEL_SHAFTS[-1])
    return float(max(8.0, math.ceil(d)))


def auto_arm(r: Dict, ratio: float, stages: int, mat: str) -> Tuple[float, float]:
    """Arm section that carries the design torque at the arm root (width, thickness; ROUND: diameter, 0)."""
    sm = get_material(mat if r["struct_material"] == "AUTO" else r["struct_material"])
    t_design = r["motor_torque"] * ratio * get_material(mat)["eta"] ** stages * r["app_factor"]      # Nm
    w_req = t_design * 1000.0 / (sm["sigma_S"] / r["target_sf"])                                   # mm^3
    if r["arm_shape"] == "ROUND":
        return float(max(12, math.ceil((32.0 * w_req / math.pi) ** (1.0 / 3.0)))), 0.0
    w = max(r["arm_width"], 30.0) if r["arm_width"] > 0 else 40.0
    t = 6.0 * w_req / (w * w)
    if r["arm_thickness"] <= 0 and t > 16.0 and r["arm_width"] <= 0:
        w = min(100.0, math.sqrt(6.0 * w_req / 16.0))
        t = 6.0 * w_req / (w * w)
    if r["arm_thickness"] > 0:
        t = r["arm_thickness"]
    return float(math.ceil(max(w, 30.0))), float(math.ceil(max(t, 8.0)))


def _payload(r: Dict, ratio: float, stages: int, fw: float, gm: str, sm: str, cap: float,
             strong: bool = False) -> Dict:
    """Design-engine payload (same keys as the UI form, so a solution can be applied to it)."""
    footprint = min(r["bed"][0], r["bed"][1]) if r["fit_bed"] else 0.0
    # stepper: the driver runs the motor at ratio × output speed (bearing life, output speed at that speed)
    motor_speed = ratio * r["output_speed"] if (r["free_speed"] and r["output_speed"] > 0) else r["motor_speed"]
    arm_w, arm_t = r["arm_width"], r["arm_thickness"]
    if r["output_type"] in ("ARM", "DRUM_ARM") and r["arm_auto"]:
        arm_w, arm_t = auto_arm(r, ratio, stages, gm)
    shaft = r["output_shaft_dia"]
    if r["output_type"] in ("SHAFT_PRINTED", "SHAFT_STEEL") and r["shaft_auto"]:
        shaft = auto_output_shaft(r, ratio, stages, gm, sm)
    elif shaft <= 0:
        shaft = 8.0
    return {
        "target_ratio": round(ratio, 4), "stages_count": stages, "num_planets": r["num_planets"] or "AUTO",
        "sizing_mode": "MAX_OD" if strong else "AUTO", "od_limit": 0.0 if strong else cap,
        "max_od": (cap or 600.0) if strong else (cap or 80.0), "ratio_tol": r["ratio_tol"],
        "strength_required": True, "is_herringbone": r["herringbone"], "helix_angle": r["helix_angle"],
        "face_width": fw, "pressure_angle": 20.0, "motor_preset": r["motor_preset"],
        "motor_shaft_dia": r["motor_shaft_dia"], "motor_shaft_type": r["motor_shaft_type"],
        "motor_torque": r["motor_torque"], "motor_speed": round(motor_speed, 2), "bearing_type": r["planet_bearing"],
        "bearing_layout": "AUTO", "pin_type": r["pin_type"], "carrier_type": r["carrier_type"],
        "output_type": r["output_type"], "output_shaft_dia": shaft, "arrangement": r["arrangement"],
        "rope_dia": r["rope_dia"],
        "output_shaft_len": r["output_shaft_len"], "out_hub": "AUTO", "hub_fastener": r["hub_fastener"],
        "arm_shape": r["arm_shape"], "arm_length": r["arm_length"], "arm_width": arm_w or 30.0,
        "arm_thickness": arm_t or 8.0, "load_value": r["load_value"], "load_unit": r["load_unit"],
        "load_radius": r["load_radius"], "addendum_coef": r["addendum_coef"], "profile_shift": r["profile_shift"],
        "gear_material": gm, "struct_material": sm,
        "app_factor": r["app_factor"], "target_sf": r["target_sf"], "target_sh": r["target_sh"],
        "target_life": r["target_life"], "max_length": r["gb_length"], "bed_x": r["bed"][0], "bed_y": r["bed"][1],
        "bed_z": r["bed"][2], "fit_bed": r["fit_bed"], "footprint_limit": footprint, "generate_housing": True,
        "slicer_profile": r["printer"] if r["printer"] in CREALITY_K1 else "",
        "mfg_preset": "FDM_3D", "lang": r["lang"],
    }


RING_LID_EST = 16.0       # drum lid of a rotating housing: widest drum bearing (13 mm) + roof


def _length_fn(r: Dict, n: int, gm: str):
    """Overall gearbox length as a function of the face width, for the worst tie-rod size."""
    p = Params.from_payload(_payload(r, 10.0, n, 12.0, gm, gm, 0.0))
    motor, cage = get_motor_info(r["motor_preset"]), r["carrier_type"] == "CAGE"
    if r["arrangement"] == "RING":
        prot = (drum_arm_height(r["arm_shape"], r["arm_width"] or 30.0, r["arm_thickness"] or 16.0)
                if r["output_type"] == "DRUM_ARM" else 0.0)
        return lambda fw: max(ring_layout(n, fw, p.plate_t, CLEARANCE, cage, motor, tie, RING_LID_EST,
                                          prot).overall_length for tie in TIE_RODS.values())
    prot = output_protrusion(r["output_type"], r["output_shaft_len"], 30.0,
                             {"shape": r["arm_shape"], "width": r["arm_width"] or 30.0,
                              "thickness": r["arm_thickness"] or 16.0}, r["hub_fastener"])
    # widest output bearing (13 mm); every tie-rod size, since the arm / flange face is lifted over the
    # actual bolt heads or rod ends (depends on the tie size and the screw length step)
    return lambda fw: max(axial_layout(n, fw, p.plate_t, CLEARANCE, cage, 13.0, motor, tie, prot, True,
                                       r["output_type"]).overall_length for tie in TIE_RODS.values())


def _layout_length(r: Dict, n: int, gm: str, fw: float) -> float:
    """Overall gearbox length at face width fw, for the worst tie-rod size (see _fw_max)."""
    return _length_fn(r, n, gm)(fw)


def _fw_max(r: Dict, n: int, gm: str) -> Optional[float]:
    """Widest gears the length budget allows (None: no length limit)."""
    if r["gb_length"] <= 0:
        return None
    length = _length_fn(r, n, gm)

    fw = min(80.0, math.floor((r["gb_length"] - length(0.0) - 1.0) / n))
    while fw > 0 and length(fw) > r["gb_length"] - 0.5:
        fw -= 1.0
    return float(fw)


def _face_widths(r: Dict, n: int, gm: str, strong: bool) -> List[float]:
    if r["face_width"] > 0:
        return [r["face_width"]]
    fw_max = _fw_max(r, n, gm)
    if fw_max is not None:
        if fw_max < 6:
            return [6.0]
        if strong:
            return [fw_max]
        return [fw_max] + [round(fw_max * k) for k in (0.65, 0.4) if round(fw_max * k) >= 8]
    return [45.0] if strong else [45.0, 30.0, 20.0, 12.0]


def _stage_options(r: Dict, ratio: float) -> List[int]:
    """Stage counts searched first: the fewest that reach the ratio and one more (lower stage ratios)."""
    if 1 <= r["stages_count"] <= MAX_STAGES:
        return [r["stages_count"]]
    n_min = min(MAX_STAGES, max(1, math.ceil(math.log(ratio) / math.log(MAX_STAGE_RATIO) - 1e-9)))
    if r["arrangement"] == "RING":
        while n_min < MAX_STAGES and MAX_STAGE_RATIO ** (n_min - 1) * (MAX_STAGE_RATIO - 1.0) < ratio:
            n_min += 1
    return [n_min] + ([n_min + 1] if n_min < MAX_STAGES else [])


MIN_STAGE_MEAN = 2.4      # below this mean stage ratio no planetary stage is left (sun as large as the ring)


def _more_stages(r: Dict, ratio: float) -> List[int]:
    """Automatic count: further stage counts for a tight space (lower stage ratios fit a smaller diameter)."""
    if r["stages_count"]:
        return []
    last = _stage_options(r, ratio)[-1]
    return [n for n in range(last + 1, MAX_STAGES + 1) if ratio ** (1.0 / n) >= MIN_STAGE_MEAN]


def _summarize(c: Dict, gm: str, fw: float, stages: int) -> Dict:
    e = c["engineering"]
    return {
        "feasible": c["feasible"], "material": gm, "num_planets": "/".join(str(s["num_planets"]) for s in c["stages"]),
        "face_width": fw, "stages": stages, "ratio": c["total_ratio"], "module": c["module"], "z_ring": c["z_ring"],
        "teeth": [(s["z_sun"], s["z_planet"], s["z_ring"]) for s in c["stages"]],
        "outer_diameter": c["outer_diameter"], "overall_length": c.get("overall_length"),
        "footprint": c.get("footprint"),
        "output_speed": round(e["output_speed"], 3), "output_torque": round(e["output_torque"], 1),
        "max_output_torque": round(e["max_output_torque"], 1), "margin": c["margin"],
        "limiting": e["limiting"]["label"] if e["limiting"] else "",
        "bed_ok": c.get("bed_ok", True), "length_ok": c.get("length_ok", True),
        "output": {"type": c["output"]["type"], "bearing": c["output"]["bearing"], "hub_d": c["output"]["hub_d"],
                   **({"drum_od": round(c["output"]["drum_od"], 1), "load_r": round(c["output"]["load_r"], 1)}
                      if c["output"].get("drum") else {})},
        "arrangement": c["output"].get("drum") and "RING" or "CARRIER",
        "planet_bearings": sorted({s["bearing"] for s in c["stages"]}), "label": c["label"],
        "load_check": load_summary(c.get("load")),
    }


def load_summary(v: Optional[Dict]) -> Optional[Dict]:
    """The application-load verdict of a candidate, compact (for the assistant and the proposal cards)."""
    if not v:
        return None
    return {k: v[k] for k in ("status", "short", "text", "need", "have", "reserve", "reserve_target") if k in v}


class _Search:
    """Runs design-engine calls for one solve and keeps the feasible items and the closest miss."""

    def __init__(self, r: Dict, t0: float, deadline: float):
        self.r, self.t0, self.deadline = r, t0, deadline
        self.found: List[Dict] = []
        self.closest: Optional[Tuple[float, Dict]] = None
        self.budget_hit = False
        self.hint = ""                   # design engine's reason when a call found no combination at all

    def out_of_time(self) -> bool:
        if time.time() - self.t0 > self.deadline:
            self.budget_hit = True
        return self.budget_hit

    def run(self, ratio: float, n: int, fw: float, mat: str, cap: float, strong: bool,
            budget: float = CALL_BUDGET) -> Optional[Dict]:
        """Best candidate of one engine call (feasible ones are kept)."""
        r = self.r
        sm = mat if r["struct_material"] == "AUTO" else r["struct_material"]
        pay = _payload(r, ratio, n, fw, mat, sm, cap, strong)
        res = design(pay, max_results=3, time_budget=budget, hard_budget=budget)
        if not res["candidates"] and res.get("hint"):
            self.hint = res["hint"]
        best = None
        for c in res["candidates"]:
            item = {"cand": c, "payload": pay, "material": mat, "fw": fw, "stages": n, "cap": cap, "ratio": ratio}
            if c["feasible"]:
                self.found.append(item)
                return item
            if best is None:
                best = item
            if self.closest is None or c["margin"] > self.closest[0]:
                self.closest = (c["margin"], item)
        return best


def solve(req: Dict, deadline: float = TOTAL_BUDGET) -> Dict:
    t0 = time.time()
    out = _solve(req, deadline)
    r = normalize(req)
    if r["winch_est"] and out.get("solutions"):
        # winch drum: solve once more with the rope radius of the drum that was found
        r_act = (out["solutions"][0].get("output") or {}).get("load_r", 0.0)
        if r_act > 0 and abs(r_act - 40.0) / 40.0 > 0.1 and time.time() - t0 < deadline * 0.6:
            out = _solve(dict(req, _winch_r=r_act), deadline - (time.time() - t0))
        elif r_act > 0:                       # the typical drum was close enough: just say which radius counts
            out["diagnostics"].append({"code": "winch_radius", "severity": "info",
                                       "text": TEXT[r["lang"]]["winch_radius"].format(r=r_act)})
    return out


def _solve(req: Dict, deadline: float = TOTAL_BUDGET) -> Dict:
    t0 = time.time()
    r = normalize(req)
    T = TEXT[r["lang"]]
    diag: List[Dict] = []

    def note(code: str, severity: str, **kw):
        diag.append({"code": code, "severity": severity, "text": T[code].format(**kw)})

    if r["speedup_asked"]:
        note("speedup_form", "info")
    if r["arrangement"] == "RING":
        note("ring", "info")
    if r["output_type"] == "DRUM_WINCH" and req.get("_winch_r"):
        note("winch_radius", "info", r=float(req["_winch_r"]))

    if r["printer"]:
        note("printer", "info", name=r["printer"].title(), x=r["bed"][0], y=r["bed"][1], z=r["bed"][2])
    # length available for the gearbox itself
    r["gb_length"] = r["max_length"]
    if r["max_length"] > 0 and r["length_includes_motor"] and r["motor_length"] > 0:
        r["gb_length"] = max(10.0, r["max_length"] - r["motor_length"])
        note("motor_len", "info", ml=r["motor_length"], L=r["gb_length"])
    if r["planet_bearing"] != "AUTO":
        note("bearing", "info", bc=r["planet_bearing"])
    # the application load sets a torque requirement with the recommended drive reserve
    if r["load_value"] > 0:
        if r["load_torque"] > 0:
            res = LOAD_RESERVE.get(r["motor_kind"], 1.25)
            t_req = r["load_torque"] * res
            unit = {"KG": "kg", "N": "N", "NM": "Nm"}[r["load_unit"]]
            desc = (f"{r['load_value']:g} Nm" if r["load_unit"] == "NM" else
                    f"{r['load_value']:g} {unit} × {r['load_lever']:.0f} mm")
            note("load", "info", desc=desc, t=r["load_torque"], res=res, treq=t_req)
            r["min_output_torque"] = max(r["min_output_torque"], round(t_req, 2))
        else:
            note("load_no_radius", "warn", v=r["load_value"],
                 u={"KG": "kg", "N": "N", "NM": "Nm"}[r["load_unit"]])

    # 1) ratio
    strong = r["prefer"] == "strong"
    ratio = r["ratio"]
    n_out = r["output_speed"]
    ladder: List[float] = []
    if n_out > 0 and r["motor_speed"] > 0:
        i_max = r["motor_speed"] / n_out
        if r["free_speed"]:
            note("stepper", "info", n_out=n_out, n_max=r["motor_speed"], i_max=i_max)
            if ratio > 0:                     # stated ratio: the driver turns the motor ratio × output speed
                if ratio * n_out > r["motor_speed"] * 1.05:
                    note("speed_high", "warn", ratio=ratio, n_out=n_out, n_m=ratio * n_out, n_max=r["motor_speed"])
            elif strong or r["min_output_torque"] <= 0:
                # strongest: the highest ratio whose housing still carries the full motor torque
                ladder = [i_max * k for k in STRONG_LADDER if i_max * k >= MIN_RATIO]
                ratio = i_max
            else:
                ratio = i_max
                if r["min_output_torque"] > 0:          # smallest ratio that still gives the torque
                    eta = get_material("PLA" if r["gear_material"] == "AUTO" else r["gear_material"])["eta"]
                    for n in range(1, MAX_STAGES + 1):
                        need = r["min_output_torque"] / (r["motor_torque"] * eta ** n) * 1.05
                        if need <= MAX_STAGE_RATIO ** n:
                            ratio = min(max(need, MIN_RATIO), i_max)
                            break
        else:
            if ratio > 0 and abs(ratio - i_max) / i_max > 0.05:
                note("ratio_conflict", "warn", given=ratio, n_in=r["motor_speed"], n_out=n_out, ratio=i_max)
            ratio = i_max
    if ratio <= 0 and n_out <= 0:
        if r["min_output_torque"] > 0 and r["motor_torque"] > 0:
            eta = get_material("PLA" if r["gear_material"] == "AUTO" else r["gear_material"])["eta"]
            need = r["min_output_torque"] / r["motor_torque"]
            for n in range(1, MAX_STAGES + 1):
                if need / eta ** n <= MAX_STAGE_RATIO ** n:
                    need = need / eta ** n * 1.05
                    break
            ratio = max(need, MIN_RATIO)
            note("ratio_from_torque", "info", treq=r["min_output_torque"], ratio=ratio,
                 n_out=r["motor_speed"] / ratio)
        else:
            note("no_ratio", "error")
            return {"success": True, "status": "error", "derived": {"ratio": 0.0}, "diagnostics": diag,
                    "solutions": [], "elapsed": round(time.time() - t0, 2)}
    if ratio < MIN_RATIO:
        note("ratio_low", "error", ratio=ratio)
        return {"success": True, "status": "error", "derived": {"ratio": ratio}, "diagnostics": diag, "solutions": [],
                "elapsed": round(time.time() - t0, 2)}
    if ratio > MAX_STAGE_RATIO ** MAX_STAGES:
        if ladder:
            ladder = [x for x in ladder if x <= MAX_STAGE_RATIO ** MAX_STAGES] or [MAX_STAGE_RATIO ** MAX_STAGES * 0.9]
            ratio = ladder[0]
        else:
            note("ratio_high", "error", ratio=ratio, n=MAX_STAGES, lim=MAX_STAGE_RATIO ** MAX_STAGES)
            return {"success": True, "status": "error", "derived": {"ratio": ratio}, "diagnostics": diag,
                    "solutions": [], "elapsed": round(time.time() - t0, 2)}
    if not ladder:
        ladder = [ratio]

    materials = ["PLA", STRONG_MATERIAL] if r["gear_material"] == "AUTO" else [r["gear_material"]]
    first_mat = materials[0]

    def derived_for(i: float, n0: int = 0) -> Dict:
        n0 = n0 or _stage_options(r, i)[0]
        eta0 = get_material(first_mat)["eta"] ** n0
        d = {"ratio": round(i, 3), "stages": n0, "efficiency": round(eta0, 3),
             "output_torque_nominal": round(r["motor_torque"] * i * eta0, 2),
             "motor": {"preset": r["motor_preset"], "torque": r["motor_torque"], "speed": r["motor_speed"],
                       "shaft": r["motor_shaft_dia"], "shaft_type": r["motor_shaft_type"], "kind": r["motor_kind"]},
             "printer_bed": list(r["bed"]), "gearbox_length_budget": r["gb_length"]}
        if r["free_speed"] and n_out > 0:
            d.update(output_speed=n_out, motor_speed_run=round(i * n_out, 1))
        else:
            d["output_speed"] = round(r["motor_speed"] / i, 3)
        return d

    derived = derived_for(ratio)

    # 2) motor checks
    eta0 = derived["efficiency"]
    t_out = derived["output_torque_nominal"]
    if r["min_output_torque"] > 0:
        if t_out < r["min_output_torque"]:
            tm_need = r["min_output_torque"] / (ratio * eta0)
            r_need = r["min_output_torque"] / (r["motor_torque"] * eta0)
            if r["free_speed"] and n_out > 0 and r_need * n_out > r["motor_speed"] * 1.001:
                note("torque_short_speed", "warn", tm=r["motor_torque"], ratio=ratio, eta=eta0, tout=t_out,
                     treq=r["min_output_torque"], tm_need=tm_need, r_need=r_need, n_out=n_out,
                     n_max=r["motor_speed"], n_ok=r["motor_speed"] / r_need)
            else:
                note("torque_short", "warn", tm=r["motor_torque"], ratio=ratio, eta=eta0, tout=t_out,
                     treq=r["min_output_torque"], tm_need=tm_need, r_need=r_need,
                     n_need=r["motor_speed"] / r_need)
        else:
            note("torque_ok", "info", tout=t_out, treq=r["min_output_torque"])
    load = LoadCase(motor_torque=r["motor_torque"], motor_speed=r["motor_speed"], application_factor=r["app_factor"],
                    target_sf=r["target_sf"], target_sh=r["target_sh"], target_life_h=r["target_life"],
                    gear_material=first_mat, struct_material=first_mat)
    ms = motor_shaft_check(r["motor_torque"] * r["app_factor"], r["motor_shaft_dia"], load)
    if not ms.ok:
        need = r["motor_shaft_dia"] * (ms.target / max(ms.safety, 1e-6)) ** (1 / 3.0)
        note("motor_shaft", "warn", d=r["motor_shaft_dia"], tm=r["motor_torque"], s=ms.safety, need=need)

    # 3) search
    cap = r["max_od"]
    if cap <= 0:
        note("strong_no_cap" if (strong and r["fit_bed"]) else "no_od_cap", "info")
    S = _Search(r, t0, deadline)
    top_miss = None                                # best try at the highest ratio (stepper: shows the gap)

    def feasible_at(i: float, li: int) -> Optional[Dict]:
        """Fast (pruned, smallest-housing) search at one ratio; widest gears first."""
        for mat in materials:
            counts = _stage_options(r, i)
            for n in counts + _more_stages(r, i):
                if n not in counts and any(f["ratio"] == i and f["material"] == mat for f in S.found):
                    break                                # tight space only: a further stage when none fits
                fws = _face_widths(r, n, mat, False)
                k = 0
                while k < len(fws):
                    fw = fws[k]
                    if S.out_of_time():
                        return None
                    item = S.run(i, n, fw, mat, cap, False)
                    nonlocal_miss(item, li)
                    if not (item and item["cand"]["feasible"]):
                        if k == 0 and fw == 45.0 and r["gb_length"] <= 0 and r["face_width"] <= 0:
                            fws, k = [60.0, 80.0], 0            # no length limit: high torque may need wider gears
                            continue
                        break
                    k += 1
            hit = next((f for f in S.found if f["ratio"] == i and f["material"] == mat), None)
            if hit:
                if mat != first_mat:
                    note("alt_material", "info", mat=first_mat, alt=mat)
                return hit
        return None

    def nonlocal_miss(item, li):
        nonlocal top_miss
        if item and li == 0 and len(ladder) > 1 and not item["cand"]["feasible"] and top_miss is None:
            top_miss = item

    hit = None
    for li, i in enumerate(ladder):                # ratios from the highest down: first feasible wins
        hit = feasible_at(i, li)
        if hit or S.budget_hit:
            break
    if hit and len(ladder) > 1:
        note("strong_ratio", "info", i=hit["ratio"], n_m=hit["ratio"] * n_out,
             t=hit["cand"]["engineering"]["output_torque"])
    if hit and strong and not S.out_of_time():
        # fill the given space: strongest design (widest gears, largest housing) at this ratio
        for n in dict.fromkeys(_stage_options(r, hit["ratio"]) + [hit["stages"]]):
            for fw in _face_widths(r, n, hit["material"], True):
                S.run(hit["ratio"], n, fw, hit["material"], cap, True, FILL_BUDGET)

    for n in _stage_options(r, ratio)[:1]:
        n_max = max_planets(ratio ** (1.0 / n))
        if n_max < 6 and r["num_planets"] < 2:
            note("planets", "info", i=ratio ** (1.0 / n), n=n_max)
    if r["gb_length"] > 0 and r["face_width"] <= 0:
        fw_max = _fw_max(r, _stage_options(r, ratio)[0], first_mat)
        if fw_max is not None:
            n_st = _stage_options(r, ratio)[0]
            if fw_max < 6:
                note("length_short", "warn", L=r["gb_length"], n=n_st,
                     need=_layout_length(r, n_st, first_mat, 6.0))
            else:
                note("length_budget", "info", L=r["gb_length"], fw=fw_max, n=n_st)

    # 4) rank and resolve
    pref = r["prefer"]
    t_top = max((f["cand"]["engineering"]["output_torque"] for f in S.found), default=1.0)

    def rank(it):
        c = it["cand"]
        od, length = c["outer_diameter"], c.get("overall_length") or 0.0
        base = (0 if c.get("bed_ok", True) else 1,)
        if pref == "strong":          # output torque in 3 % steps, then the largest safety reserve
            return base + (-round(c["engineering"]["output_torque"] / (0.03 * t_top)), -c["margin"], od)
        if pref == "short":
            return base + (length, od)
        # "small": least occupied volume; a further stage must save > 10 % (efficiency, parts, backlash)
        return base + (od * od * length * STAGE_COST ** it["stages"], od)

    S.found.sort(key=rank)
    if r["min_output_torque"] > 0:
        meets = [it for it in S.found
                 if it["cand"]["engineering"]["output_torque"] >= r["min_output_torque"] * 0.995]
        if meets:                                  # e.g. a 3-stage alternative loses torque to efficiency
            S.found = meets
    solutions: List[Dict] = []
    kept: List[Dict] = []
    for it in S.found:
        c = it["cand"]
        od, length = c["outer_diameter"], c.get("overall_length") or 0.0
        # alternatives must differ: same diameter (±2 %) and not shorter -> nothing new
        if any(abs(k["outer_diameter"] - od) <= 0.02 * od and (k.get("overall_length") or 0) <= length + 1e-6
               and abs(k["total_ratio"] - c["total_ratio"]) < 0.5 for k in kept):
            continue
        kept.append(c)
        solutions.append(_solution(it, len(solutions) + 1))
        if len(solutions) >= 3:
            break
    status = "ok"
    if solutions:
        best = solutions[0]
        derived = derived_for(best["target_ratio"], best["stages"])
        if top_miss is not None:
            e = top_miss["cand"]["engineering"]
            need = e["output_torque"]
            if e["max_output_torque"] > best["output_torque"] * 1.05:
                note("strong_capped", "warn", i_max=top_miss["ratio"], cap=e["max_output_torque"], need=need,
                     pct=100.0 * e["max_output_torque"] / max(need, 1e-9))
                alt = _solution(dict(top_miss, payload=dict(top_miss["payload"], strength_required=False)),
                                len(solutions) + 1)
                alt["recommended"] = False
                solutions.append(alt)
        if r["output_type"] in ("SHAFT_PRINTED", "SHAFT_STEEL") and r["shaft_auto"]:
            steel = r["output_type"] == "SHAFT_STEEL"
            kind = ("steel D-shaft" if steel else "printed D-shaft") if r["lang"] == "en" else \
                ("çelik D-mil" if steel else "basılı D-mil")
            note("shaft_auto", "info", kind=kind, d=best["payload"]["output_shaft_dia"], t=best["output_torque"],
                 sf=r["target_sf"])
        if r["output_type"] in ("ARM", "DRUM_ARM") and r["arm_length"] > 0:
            if r["arm_auto"]:
                aw, at = best["payload"]["arm_width"], best["payload"]["arm_thickness"]
                note("arm_auto_round" if r["arm_shape"] == "ROUND" else "arm_auto_flat", "info",
                     L=r["arm_length"], w=aw, t=at)
            if r["load_value"] <= 0:
                t_tip = min(best["output_torque"], best["max_output_torque"])
                f = t_tip * 1000.0 / r["arm_length"]
                res = LOAD_RESERVE.get(r["motor_kind"], 1.25)
                note("arm_tip", "info", L=r["arm_length"], f=f, kg=f / 9.81, res=res, kg_r=f / 9.81 / res)
    else:
        status = "infeasible"
        if S.closest:
            it = S.closest[1]
            c = it["cand"]
            e = c["engineering"]
            od_txt = f"Ø{it['cap']:.0f} mm" if it["cap"] > 0 else ("any size" if r["lang"] == "en" else "her boyut")
            note("no_solution", "error", od=od_txt, best=c["label"], cap=e["max_output_torque"],
                 need=e["output_torque"], lim=e["limiting"]["label"] if e["limiting"] else "-")
            note("no_solution_hint", "info")
            if it["cap"] > 0:               # the form reproduces it as "strongest design within the diameter"
                it = dict(it, payload=dict(it["payload"], sizing_mode="MAX_OD", max_od=it["cap"]))
            sol = _solution(it, 1)
            sol["recommended"] = False
            solutions.append(sol)
            derived = derived_for(sol["target_ratio"], sol["stages"])
        else:
            note("no_candidate", "error", hint=S.hint or T["no_solution_hint"])
    if status == "ok" and any(d["severity"] in ("warn", "error") for d in diag):
        status = "partial"
    for s in solutions[:1]:
        if not s.get("bed_ok", True):
            status = "partial" if status == "ok" else status
            note("bed_part", "warn", fp=s.get("footprint") or s["outer_diameter"], bed=min(r["bed"][0], r["bed"][1]))
    return {"success": True, "status": status, "derived": derived, "diagnostics": diag, "solutions": solutions,
            "budget_hit": S.budget_hit, "elapsed": round(time.time() - t0, 2)}


def _solution(it: Dict, idx: int) -> Dict:
    c = it["cand"]
    s = _summarize(c, it["material"], it["fw"], it["stages"])
    payload = dict(it["payload"], total_ratio=c["total_ratio"], stages=c["stages"], module=c["module"])
    payload.pop("od_limit", None)
    try:
        warnings = resolve(payload)["warnings"]
    except Exception:          # pragma: no cover - a design the engine returned always resolves
        warnings = []
    s.update({"id": f"S{idx}", "recommended": c["feasible"], "warnings": warnings, "payload": payload,
              "target_ratio": round(it.get("ratio", c["total_ratio"]), 3)})
    return s
