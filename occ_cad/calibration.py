# -*- coding: utf-8 -*-
"""
Tolerans kalibrasyon parçası: seçili tasarımın geçmelerini kullanıcının kendi yazıcısında dener ve en iyi
sonucu formun toleranslarına çevirir.

  1. Rulman yuvaları  tasarımın her rulman ölçüsü için bir plaka; delik = D + adım (BEARING_STEPS). Rulman elle /
                      mengeneyle hafif baskıyla girmeli ve kendiliğinden düşmemeli -> bearing_tolerance
  2. Pim delikleri    her çelik pim çapı için bir plaka; delik = d + adım (PIN_STEPS). Pim mengene / hafif çekiçle
                      girmeli, elle çıkmamalı -> pin_tolerance
  3. Diş boşluğu      tasarımın modülünde aynı dişli çiftleri, tabandaki pimlerde tam eksen mesafesinde; her çift bir
                      boşluk değeriyle (BACKLASH_STEPS). Sıkışmadan dönen ve en az boşluklu çift -> backlash

Her yuvanın / çiftin numarası yüzeye kazınır (yedi segmentli rakam, yazı tipi gerekmez); dişli çiftleri göbekteki
nokta sayısıyla ayırt edilir. Sonuç numaraları arayüzde girilir, değerler forma yazılır ve hatırlanır.
"""
from __future__ import annotations

import math
import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from core import design as D
from core.bearing_catalog import get_bearing_info

from . import kernel as K
from . import parts as B
from .assembly import COLORS, BuildCancelled, BuildResult, Part

BEARING_STEPS = (-0.05, 0.0, 0.05, 0.10, 0.15, 0.20)     # mm on the bearing outer diameter D
PIN_STEPS = (-0.10, -0.05, 0.0, 0.05, 0.10, 0.15)        # mm on the dowel diameter d
BACKLASH_STEPS = (0.10, 0.15, 0.20, 0.25, 0.30)          # mm total circumferential backlash of one mesh
DIGIT_H = 5.0               # engraved digit height (stroke 0.9 mm: two FDM lines)
ENGRAVE = 0.6               # engraving depth
MARGIN = 4.0
POST_D = 5.0                # printed post of the backlash test
POST_CLEAR = 0.15           # gear bore over the post (tight: a loose bore would hide binding)
GEAR_FW = 6.0
GAP_Z = 0.4                 # gear above the base plate on the posts (viewer)

SEGMENTS = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg", "6": "acdefg",
            "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g"}

TEXT = {
    "tr": {
        "bearing": "Rulman yuvası {code}", "pins": "Pim deliği Ø{d:g}", "backlash": "Diş boşluğu tabanı",
        "gear": "Boşluk dişlisi {k}", "group": "Kalibrasyon", "product": "Kalibrasyon_Parcasi",
        "no_design": "Kalibrasyon parçası için önce bir tasarım (aday) seçin.",
        "steps": [
            "Plakaları ve dişlileri redüktörü basacağınız malzeme, nozül ve dilimleme ayarlarıyla basın (aynı katman "
            "yüksekliği, duvar sayısı, akış). Plakaları düz, yazılı yüz üstte basın.",
            "Rulman yuvaları: her numaraya rulmanı elle / mengeneyle bastırın. Doğru yuva: hafif baskıyla girer, ters "
            "çevirince düşmez, sökerken zorlanmaz. Gevşek kalanlar fazla, giremeyenler dar.",
            "Pim delikleri: çelik pimi mengeneyle veya hafif çekiçle çakın. Doğru delik: pim sıkı girer, elle "
            "döndürülemez ve çekilemez; plaka çatlamaz.",
            "Diş boşluğu: her numaralı dişli çiftini (göbekteki nokta sayısı = numara) tabandaki aynı numaralı pim "
            "çiftine takın ve çevirin. Doğru çift: hiçbir konumda sıkışmaz, takılmaz ve en az boşlukludur.",
            "Uygulamada 5. sekmedeki 'Kalibrasyon sonucu' bölümüne her testte en iyi numarayı girip 'Uygula'ya basın: "
            "toleranslar forma yazılır ve bu bilgisayarda hatırlanır.",
        ],
    },
    "en": {
        "bearing": "Bearing pocket {code}", "pins": "Pin hole Ø{d:g}", "backlash": "Backlash test base",
        "gear": "Backlash gear {k}", "group": "Calibration", "product": "Calibration_Coupon",
        "no_design": "Select a design (candidate) first for the calibration coupon.",
        "steps": [
            "Print the plates and gears with the material, nozzle and slicer settings of the gearbox (same layer "
            "height, wall count, flow). Print the plates flat, numbers up.",
            "Bearing pockets: press the bearing into every number by hand / vise. The right pocket takes it with light "
            "pressure, holds it upside down and lets it out without force. Loose ones are too big, those it does not "
            "enter are too small.",
            "Pin holes: press the steel pin in with a vise or a light hammer. The right hole holds it tight: it cannot "
            "be turned or pulled by hand and the plate does not crack.",
            "Backlash: put every gear pair (dots on the hub = number) on the post pair with the same number and turn "
            "it. The right pair never binds or catches and has the least play.",
            "In the app enter the best number of every test under 'Calibration result' on tab 5 and press 'Apply': "
            "the tolerances go into the form and are remembered on this computer.",
        ],
    },
}


# ─── Kazınmış rakamlar ───────────────────────────────────────────────────────

def _digit_boxes(ch: str, cx: float, cy: float, h: float) -> List[Tuple[float, float, float, float]]:
    w, t, g = 0.56 * h, 0.18 * h, 0.03 * h
    xl, xr, yt, ym, yb = cx - w / 2.0, cx + w / 2.0, cy + h / 2.0, cy, cy - h / 2.0
    seg = {"a": (xl + t / 2, yt - t, xr - t / 2, yt), "b": (xr - t, ym + g, xr, yt - g),
           "c": (xr - t, yb + g, xr, ym - g), "d": (xl + t / 2, yb, xr - t / 2, yb + t),
           "e": (xl, yb + g, xl + t, ym - g), "f": (xl, ym + g, xl + t, yt - g),
           "g": (xl + t / 2, ym - t / 2, xr - t / 2, ym + t / 2)}
    return [seg[s] for s in SEGMENTS.get(ch, "")]


def engrave_tools(text: str, cx: float, cy: float, z_top: float, h: float = DIGIT_H,
                  depth: float = ENGRAVE) -> List:
    """Cutting tools of a seven-segment number centred at (cx, cy) on the face z_top."""
    tools = []
    pitch = 0.78 * h
    x0 = cx - pitch * (len(text) - 1) / 2.0
    for i, ch in enumerate(text):
        for (a, b, c, d) in _digit_boxes(ch, x0 + i * pitch, cy, h):
            face = K.planar_face(K.polygon_wire([(a, b), (c, b), (c, d), (a, d)]))
            tools.append(K.extrude(face, z_top - depth, z_top + 1.0))
    return tools


def _plate(w: float, h: float, t: float, chamfer: float = 3.0):
    c = min(chamfer, w / 4.0, h / 4.0)
    pts = [(c, 0.0), (w - c, 0.0), (w, c), (w, h - c), (w - c, h), (c, h), (0.0, h - c), (0.0, c)]
    return K.extrude(K.planar_face(K.polygon_wire(pts)), 0.0, t)


def _code_digits(code: str) -> str:
    return "".join(ch for ch in code if ch.isdigit())[:4] or "0"


# ─── Testler ─────────────────────────────────────────────────────────────────

def bearing_plate(code: str) -> Tuple[object, Dict]:
    """
    Pockets D + step for one bearing size, 6 numbers + the code. A thin base plate with a ring boss of the bearing
    width around every pocket (full seat length, little material); the pockets go through (a loose bearing falls
    out, a tight one can be pushed out from below).
    """
    b = get_bearing_info(code)
    dd, bw = b["d_outer"], max(3.0, b["width"])
    base_t, wall = 2.4, 2.4
    cols = 6 if dd <= 14.0 else 3
    rows = math.ceil(len(BEARING_STEPS) / cols)
    px, py = dd + 2 * wall + 3.0, dd + 2 * wall + DIGIT_H + 3.0
    head = DIGIT_H + 4.0
    w, h = cols * px + 2 * MARGIN, rows * py + head + MARGIN
    plate = _plate(w, h, base_t)
    bosses, tools, layout = [], [], []
    for k, step in enumerate(BEARING_STEPS):
        r, c = divmod(k, cols)
        cx = MARGIN + px * (c + 0.5)
        cy = MARGIN + py * (rows - 1 - r) + DIGIT_H + 2.0 + dd / 2.0 + wall
        bosses.append(K.cylinder(dd / 2.0 + wall, base_t - 0.01, bw, cx, cy))
        tools.append(K.cylinder((dd + step) / 2.0, -1.0, bw + 1.0, cx, cy))
        tools += engrave_tools(str(k + 1), cx, cy - dd / 2.0 - wall - 1.0 - DIGIT_H / 2.0, base_t, depth=0.5)
        layout.append({"index": k + 1, "value": step, "dia": round(dd + step, 3)})
    digits = _code_digits(code)
    tools += engrave_tools(digits, MARGIN + 2.0 + 0.39 * DIGIT_H * len(digits), h - head / 2.0, base_t, depth=0.5)
    body = K.fuse(plate, bosses, "rulman kalibrasyonu yuvalar")
    return K.cut(body, tools, "rulman kalibrasyonu"), {"code": code, "D": dd, "steps": layout, "size": (w, h, bw)}


def pin_plate(d: float) -> Tuple[object, Dict]:
    """Holes d + step for one steel dowel diameter (6 mm deep plate, the pin is pressed through)."""
    t = 6.0                                   # about a carrier plate: the pin is held over a similar length
    px = d + 8.0
    w, h = len(PIN_STEPS) * px + 2 * MARGIN, d + 2 * MARGIN + DIGIT_H + 3.0 + DIGIT_H + 3.0
    plate = _plate(w, h, t)
    tools, layout = [], []
    cy = MARGIN + DIGIT_H + 3.0 + d / 2.0 + 1.0
    for k, step in enumerate(PIN_STEPS):
        cx = MARGIN + px * (k + 0.5)
        tools.append(K.cylinder((d + step) / 2.0, -1.0, t + 1.0, cx, cy))
        tools += engrave_tools(str(k + 1), cx, cy - d / 2.0 - 1.5 - DIGIT_H / 2.0, t)
        layout.append({"index": k + 1, "value": step, "dia": round(d + step, 3)})
    tools += engrave_tools(str(int(round(d))), MARGIN + 5.0, h - DIGIT_H / 2.0 - 2.0, t)
    return K.cut(plate, tools, "pim kalibrasyonu"), {"d": d, "steps": layout, "size": (w, h, t)}


def _test_teeth(module: float) -> int:
    return 18 if module <= 1.5 else 14


def backlash_base(module: float, z: int) -> Tuple[object, Dict, List[Tuple[float, float]]]:
    """Base plate with one post pair per backlash step at the exact centre distance m·z, numbered."""
    a = module * z
    od = module * (z + 2.0)
    t = 3.0
    pitch_y = od + 6.0
    w = a + od + 2 * MARGIN + DIGIT_H + 4.0
    h = len(BACKLASH_STEPS) * pitch_y + 2 * MARGIN
    plate = _plate(w, h, t)
    posts, tools, centres = [], [], []
    x1 = MARGIN + DIGIT_H + 4.0 + od / 2.0
    for k in range(len(BACKLASH_STEPS)):
        cy = MARGIN + pitch_y * (len(BACKLASH_STEPS) - 1 - k) + pitch_y / 2.0
        for cx in (x1, x1 + a):
            posts.append(K.cylinder(POST_D / 2.0, t - 0.5, t + GEAR_FW + GAP_Z + 1.0, cx, cy))
            centres.append((cx, cy))
        tools += engrave_tools(str(k + 1), MARGIN + DIGIT_H / 2.0 + 1.0, cy, t)
    base = K.fuse(K.cut(plate, tools, "boşluk tabanı yazı"), posts, "boşluk pimleri")
    return base, {"a": a, "size": (w, h, t + GEAR_FW + GAP_Z + 1.0)}, centres


def backlash_gear(module: float, z: int, backlash: float, k: int, pressure_angle: float, addendum: float):
    """Test gear of pair k (k dots on the hub) with the given mesh backlash, bore over the post."""
    body, info = B.external_gear_solid(z, module, pressure_angle, backlash, GEAR_FW, 0.0, 0.0, 1.0, 0.0,
                                       addendum=addendum)
    tools = [K.cylinder((POST_D + POST_CLEAR) / 2.0, -1.0, GEAR_FW + 1.0)]
    r_dot = (POST_D / 2.0 + info["root_r"]) / 2.0
    dots = [K.cylinder(0.8, GEAR_FW - 0.01, GEAR_FW + 0.8, r_dot * math.cos(2 * math.pi * i / k),
                       r_dot * math.sin(2 * math.pi * i / k)) for i in range(k)]
    return K.fuse(K.cut(body, tools, "boşluk dişlisi göbeği"), dots, "boşluk dişlisi işareti")


# ─── Üretim ──────────────────────────────────────────────────────────────────

def generate(config: Dict, progress: Optional[Callable[[str, int], None]] = None,
             cancelled: Optional[Callable[[], bool]] = None) -> BuildResult:
    t0 = time.time()
    lang = "en" if str(config.get("lang", "tr")).lower().startswith("en") else "tr"
    T = TEXT[lang]

    def report(pct: int, text: str = ""):
        if cancelled and cancelled():
            raise BuildCancelled()
        if progress:
            progress(text or T["group"], pct)

    if not config.get("stages"):
        raise K.GeometryError(T["no_design"])
    R = D.resolve(config)
    p: D.Params = R["params"]
    codes: List[str] = []
    for st in R["stages"]:
        if st["bearings_per_planet"] > 0 and st["bearing"] not in codes:
            codes.append(st["bearing"])
    out = R["output"]
    if out.get("bearing") and out["bearing"] in D.BEARING_CATALOG and out["bearing"] not in codes:
        codes.append(out["bearing"])
    pins = sorted({float(st["pin_dia"]) for st in R["stages"]}) if p.pin_steel else []
    module = float(R["module"])
    z = _test_teeth(module)

    parts: List[Part] = []
    data = {"bearings": [], "pins": [], "backlash": {}, "lang": lang}
    x_cursor, row_h, gap = 0.0, 0.0, 8.0
    bed_w = max(120.0, min(p.bed[0], p.bed[1]) - 10.0)
    y_cursor = 0.0

    def place(shape, w: float, h: float) -> object:
        nonlocal x_cursor, y_cursor, row_h
        if x_cursor > 0 and x_cursor + w > bed_w:
            x_cursor, y_cursor, row_h = 0.0, y_cursor + row_h + gap, 0.0
        trsf = K.trsf_translate(x_cursor, y_cursor, 0.0)
        x_cursor += w + gap
        row_h = max(row_h, h)
        return trsf

    n_steps = len(codes) + len(pins) + 2
    done = 0
    for code in codes:
        report(10 + int(80 * done / n_steps), T["bearing"].format(code=code))
        shape, info = bearing_plate(code)
        w, h, _ = info["size"]
        parts.append(Part(f"cal_bearing_{code}", f"Calibration_Bearing_{code}", T["bearing"].format(code=code),
                          "calibration", T["group"], shape, COLORS["housing"], placements=[place(shape, w, h)]))
        data["bearings"].append({"code": code, "D": info["D"], "steps": info["steps"]})
        done += 1
    for d in pins:
        report(10 + int(80 * done / n_steps), T["pins"].format(d=d))
        shape, info = pin_plate(d)
        w, h, _ = info["size"]
        key = f"cal_pins_{str(d).replace('.', '_')}"
        parts.append(Part(key, f"Calibration_Pins_{d:g}", T["pins"].format(d=d), "calibration", T["group"], shape,
                          COLORS["carrier"], placements=[place(shape, w, h)]))
        data["pins"].append({"d": d, "steps": info["steps"]})
        done += 1
    report(10 + int(80 * done / n_steps), T["backlash"])
    base, info, centres = backlash_base(module, z)
    w, h, _ = info["size"]
    base_trsf = place(base, w, h)
    parts.append(Part("cal_backlash_base", "Calibration_Backlash_Base", T["backlash"], "calibration", T["group"],
                      base, COLORS["housing"], placements=[base_trsf]))
    ox, oy = base_trsf.TranslationPart().X(), base_trsf.TranslationPart().Y()
    done += 1
    report(10 + int(80 * done / n_steps), T["backlash"])
    steps = []
    for k, bl in enumerate(BACKLASH_STEPS, start=1):
        gear = backlash_gear(module, z, bl, k, p.pressure_angle, p.addendum)
        (c1x, c1y), (c2x, c2y) = centres[2 * (k - 1)], centres[2 * (k - 1) + 1]
        # the second gear is turned half a pitch so its teeth fall into the first one's spaces
        pl = [K.trsf_translate(ox + c1x, oy + c1y, 3.0 + GAP_Z),
              K.trsf_place(ox + c2x, oy + c2y, 3.0 + GAP_Z, math.pi / z)]
        parts.append(Part(f"cal_gear_{k}", f"Calibration_Gear_{k}", T["gear"].format(k=k), "calibration", T["group"],
                          gear, COLORS["planet"] if k % 2 else COLORS["sun"], placements=pl))
        steps.append({"index": k, "value": bl})
    data["backlash"] = {"module": module, "z": z, "a": info["a"], "steps": steps}
    data["current"] = {"bearing_tolerance": p.bearing_tol, "pin_tolerance": float(config.get("pin_tolerance") or 0.0),
                       "backlash": p.backlash}
    report(95)
    n_parts = sum(pt.quantity for pt in parts)
    summary = {"calibration": True, "part_count": n_parts, "unique_parts": len(parts),
               "bearings": codes, "pins": pins, "module": module}
    return BuildResult(parts=parts, warnings=[], summary=summary, elapsed=time.time() - t0,
                       product_name=T["product"], steps=list(T["steps"]), design={"calibration": data})


# ─── Rehber (HTML) ve parça listesi ──────────────────────────────────────────

GUIDE = {
    "tr": {"title": "Tolerans Kalibrasyon Parçası", "intro": "Bu parçalar seçili redüktörün rulman, pim ve diş "
           "geçmelerini sizin yazıcınızda dener. Her testte en iyi numarayı uygulamaya girin.",
           "bearing": "Rulman yuvası {code} (D = {D:g} mm)", "pins": "Çelik pim deliği Ø{d:g} mm",
           "backlash": "Diş boşluğu (m{m:g}, z = {z}, eksen mesafesi {a:g} mm)", "no": "No", "offset": "Ofset",
           "hole": "Delik Ø", "value": "Boşluk", "form": "Formdaki karşılığı", "steps": "Nasıl test edilir?",
           "current": "Şu anki form değerleri: rulman {b:+.2f} mm · pim {p:+.2f} mm · diş boşluğu {bl:.2f} mm",
           "f_bearing": "Rulman / Pim Yuvası Ofseti", "f_pin": "Pim Deliği Toleransı", "f_backlash": "Diş Profil Boşluğu",
           "parts": "Basılacak parçalar"},
    "en": {"title": "Tolerance Calibration Coupon", "intro": "These parts test the bearing, pin and tooth fits of the "
           "selected gearbox on your printer. Enter the best number of every test in the app.",
           "bearing": "Bearing pocket {code} (D = {D:g} mm)", "pins": "Steel pin hole Ø{d:g} mm",
           "backlash": "Backlash (m{m:g}, z = {z}, centre distance {a:g} mm)", "no": "No", "offset": "Offset",
           "hole": "Hole Ø", "value": "Backlash", "form": "Form field", "steps": "How to test",
           "current": "Current form values: bearing {b:+.2f} mm · pin {p:+.2f} mm · backlash {bl:.2f} mm",
           "f_bearing": "Bearing / pin seat offset", "f_pin": "Pin hole tolerance", "f_backlash": "Tooth backlash",
           "parts": "Parts to print"},
}


def write_html(result, path: str, lang: str = "tr") -> str:
    import html
    import os
    g = GUIDE["en" if lang == "en" else "tr"]
    data = result.design["calibration"]
    esc = html.escape

    def table(rows, head):
        th = "".join(f"<th>{esc(h)}</th>" for h in head)
        tr = "".join("<tr>" + "".join(f"<td>{esc(str(c))}</td>" for c in r) + "</tr>" for r in rows)
        return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"

    sections = []
    for b in data["bearings"]:
        sections.append(f"<h2>{esc(g['bearing'].format(code=b['code'], D=b['D']))}</h2><p>{esc(g['form'])}: "
                        f"{esc(g['f_bearing'])}</p>" + table(
                            [(s["index"], f"{s['value']:+.2f} mm", f"{s['dia']:.2f} mm") for s in b["steps"]],
                            (g["no"], g["offset"], g["hole"])))
    for pn in data["pins"]:
        sections.append(f"<h2>{esc(g['pins'].format(d=pn['d']))}</h2><p>{esc(g['form'])}: {esc(g['f_pin'])}</p>" +
                        table([(s["index"], f"{s['value']:+.2f} mm", f"{s['dia']:.2f} mm") for s in pn["steps"]],
                              (g["no"], g["offset"], g["hole"])))
    bl = data["backlash"]
    sections.append(f"<h2>{esc(g['backlash'].format(m=bl['module'], z=bl['z'], a=bl['a']))}</h2><p>{esc(g['form'])}: "
                    f"{esc(g['f_backlash'])}</p>" + table([(s["index"], f"{s['value']:.2f} mm") for s in bl["steps"]],
                                                          (g["no"], g["value"])))
    cur = data.get("current", {})
    parts = "".join(f"<li>{p.quantity} × {esc(p.label)}</li>" for p in result.parts)
    steps = "".join(f"<li>{esc(s)}</li>" for s in result.steps)
    doc = f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{esc(g['title'])}</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:28px auto;max-width:900px;color:#1d2733;font-size:13px}}
h1{{color:#0b6e99}}h2{{margin-top:22px;font-size:15px;color:#0b6e99}}table{{border-collapse:collapse;margin:6px 0}}
td,th{{border:1px solid #c9d3dd;padding:4px 10px;text-align:left}}th{{background:#eef3f7}}</style></head><body>
<h1>{esc(g['title'])}</h1><p>{esc(g['intro'])}</p>
<p>{esc(g['current'].format(b=cur.get('bearing_tolerance', 0.0), p=cur.get('pin_tolerance', 0.0),
                             bl=cur.get('backlash', 0.0)))}</p>
<h2>{esc(g['steps'])}</h2><ol>{steps}</ol>
{''.join(sections)}
<h2>{esc(g['parts'])}</h2><ul>{parts}</ul>
</body></html>"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return path
