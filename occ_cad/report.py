# -*- coding: utf-8 -*-
"""
Mühendislik raporu, malzeme listesi (BOM) ve montaj talimatı.

Rapor tek dosyalık, internet bağlantısı gerektirmeyen bir HTML'dir (yazdırılabilir); BOM ayrıca
Not Defteri uyumlu metin olarak yazılır.
"""
from __future__ import annotations

import datetime as _dt
import html
from typing import Dict, List, Tuple

from core.materials import get_material
from core.motor_catalog import get_motor_info

from . import kernel as K

T = {
    "tr": {
        "title": "Planet Redüktör — Mühendislik Raporu", "summary": "Özet", "ratio": "Toplam oran",
        "stages": "Kademe", "type": "Diş tipi", "herring": "Balıksırtı", "spur": "Düz", "module": "Modül / Zr",
        "out_t": "Nominal çıkış torku", "out_max": "Sürekli taşınabilir çıkış torku", "out_n": "Çıkış devri",
        "eff": "Verim", "limit": "Sınırlayan eleman", "dims": "Dış çap / gövde boyu", "mass": "Baskı kütlesi",
        "inputs": "Yük durumu", "motor": "Motor", "ka": "Uygulama faktörü K_A", "targets": "Hedef emniyetler",
        "materials": "Malzeme (dişli / yapısal)", "stage": "Kademe", "check": "Kontrol", "value": "Değer",
        "allow": "Sınır", "safety": "Emniyet", "target": "Hedef", "geometry": "Dişli geometrisi",
        "teeth": "Zs / Zp / Zr", "cd": "Eksen mesafesi", "tips": "Uç yarıçapları (güneş/planet/çember)",
        "eps": "Temas oranı εα (G-P / P-Ç) · εβ", "bearing": "Planet rulmanı", "layout": "Düzen",
        "life": "L10h", "pins": "Pim", "printed": "Basılacak parçalar", "purchased": "Satın alınacak parçalar",
        "qty": "Adet", "part": "Parça", "material": "Malzeme", "mass_each": "Kütle/adet", "note": "Not",
        "print": "Baskı ayarları", "assembly": "Montaj talimatı", "warnings": "Uyarılar", "method": "Hesap yöntemi ve varsayımlar",
        "dual": "çift (sırt sırta)", "single": "tek (üstte)", "bushing": "rulmansız burç",
        "generated": "Oluşturulma", "ok": "UYGUN", "fail": "YETERSİZ",
        "depth": "Diş yüksekliği h*a", "depth_std": "standart", "depth_stub": "kısa diş", "depth_long": "uzun diş",
        "land": "Diş ucu kalınlığı (güneş / planet)", "root_f": "Diş dibi dayanımı (standarda göre)",
        "khb": "Yük dağılımı K_Hβ / K_Fβ · eğiklik",
        "expert": "Uzman: diş sıcaklığı · sıcaklık / çevrim çarpanları · çevrim · sürtünme", "shift": "Profil kaydırma x (güneş / planet / çember)",
        "app_load": "Uygulama yükü", "fixes": "Seçenekler", "gear_sun": "güneş", "gear_planet": "planet",
        "gear_ring": "çember", "arrangement": "Düzen", "arr_CARRIER": "Standart — taşıyıcı çıkışı, gövde sabit",
        "arr_RING": "Dönen gövde — taşıyıcı sabit, çember (tambur) çıkışı, ters yön",
        "arr_SPEED_UP": "Hız artırıcı — çıkıştan döndürülür, motor jeneratör olarak çalışır",
        "arr_WOLFROM": "Wolfrom — kademeli planet, sabit + dönen çember, tek kademe",
        "arr_CYCLOID": "Sikloidal — eksantrik + 2 sikloid disk, halka pimleri, çıkış pimleri (ters yön)",
        "cy_pins": "Halka pimleri", "cy_ecc": "Eksantriklik e · K1", "cy_disc": "Disk (2 adet, 180°)",
        "cy_out": "Çıkış pimleri", "cy_brg": "Eksantrik rulmanı", "cy_lobes": "lob", "cy_force": "En büyük pim kuvveti",
        "drum": "Tambur (Ø / rulman)", "generator": "Jeneratör", "drive": "Giriş (krank / türbin)",
        "speedup": "Hız artırıcı",
    },
    "en": {
        "title": "Planetary Gearbox — Engineering Report", "summary": "Summary", "ratio": "Total ratio",
        "stages": "Stages", "type": "Tooth type", "herring": "Herringbone", "spur": "Spur", "module": "Module / Zr",
        "out_t": "Nominal output torque", "out_max": "Continuous output torque capacity", "out_n": "Output speed",
        "eff": "Efficiency", "limit": "Limiting element", "dims": "Outer diameter / body length",
        "mass": "Printed mass", "inputs": "Load case", "motor": "Motor", "ka": "Application factor K_A",
        "targets": "Target safety factors", "materials": "Material (gears / structure)", "stage": "Stage",
        "check": "Check", "value": "Value", "allow": "Limit", "safety": "Safety", "target": "Target",
        "geometry": "Gear geometry", "teeth": "Zs / Zp / Zr", "cd": "Center distance",
        "tips": "Tip radii (sun/planet/ring)", "eps": "Contact ratio εα (S-P / P-R) · εβ", "bearing": "Planet bearing",
        "layout": "Layout", "life": "L10h", "pins": "Pin", "printed": "Printed parts", "purchased": "Purchased parts",
        "qty": "Qty", "part": "Part", "material": "Material", "mass_each": "Mass each", "note": "Note",
        "print": "Print settings", "assembly": "Assembly instructions", "warnings": "Warnings",
        "method": "Method and assumptions", "dual": "dual (back-to-back)", "single": "single (top)",
        "bushing": "plain bushing", "generated": "Generated", "ok": "OK", "fail": "INSUFFICIENT",
        "depth": "Tooth depth h*a", "depth_std": "standard", "depth_stub": "stub", "depth_long": "long teeth",
        "land": "Tooth tip thickness (sun / planet)", "root_f": "Root strength (vs. standard depth)",
        "khb": "Face load K_Hβ / K_Fβ · misalignment",
        "expert": "Expert: tooth temperature · temperature / cycle factors · cycles · friction", "shift": "Profile shift x (sun / planet / ring)",
        "app_load": "Application load", "fixes": "Options", "gear_sun": "sun", "gear_planet": "planet",
        "gear_ring": "ring", "arrangement": "Arrangement", "arr_CARRIER": "Standard — carrier output, housing fixed",
        "arr_RING": "Rotating housing — carrier fixed, ring (drum) output, opposite direction",
        "arr_SPEED_UP": "Speed-up — driven from the output side, the motor works as a generator",
        "arr_WOLFROM": "Wolfrom — stepped planets, fixed + turning ring, one stage",
        "arr_CYCLOID": "Cycloidal — eccentric + 2 cycloid discs, ring pins, output pins (opposite direction)",
        "cy_pins": "Ring pins", "cy_ecc": "Eccentricity e · K1", "cy_disc": "Disc (2, 180°)",
        "cy_out": "Output pins", "cy_brg": "Eccentric bearing", "cy_lobes": "lobes", "cy_force": "Largest pin force",
        "drum": "Drum (Ø / bearing)", "generator": "Generator", "drive": "Input (crank / rotor)",
        "speedup": "Speed-up",
    },
}


def _fmt(v: float, unit: str) -> str:
    if unit == "h":
        return f"{v:,.0f} h".replace(",", " ")
    if unit == "MPa":
        return f"{v:.1f} MPa"
    if unit == "°C":
        return f"{v:.0f} °C"
    if unit:
        return f"{v:.2f} {unit}"
    return f"{v:.2f}"


def bill_of_materials(result, lang: str = "tr") -> Tuple[List[Dict], List[Dict]]:
    """(basılacak parçalar, satın alınacak parçalar) listeleri."""
    d = result.design
    prm = d.get("params", {})
    gm, sm = get_material(prm.get("gear_material", "PLA")), get_material(prm.get("struct_material", "PLA"))
    printed, purchased = [], []
    for i, part in enumerate(result.parts, 1):
        if part.printable:
            mat = gm if (part.gear or part.key.startswith(("sun", "planet", "ring", "drum"))) else sm
            mass = K.volume(part.shape) * mat["rho"] / 1000.0
            printed.append({"no": i, "label": part.label, "qty": part.quantity, "material": mat["name"],
                            "mass_g": round(mass, 1), "note": part.note})
        elif part.spec:
            purchased.append({"label": part.label, "qty": part.quantity, "spec": part.spec})
    hw = d.get("hardware", {})
    motor = get_motor_info(prm.get("motor", "NEMA17"))
    en = lang == "en"
    keys = {p.key for p in result.parts}
    if "tie_rod_bolt" in keys:
        size = motor.get("bolt_size", "M3")
        purchased.append({"label": "Motor screw" if en else "Motor vidası", "qty": 4,
                          "spec": f"ISO 4762 {size} × {hw.get('motor_screw', 8):g} mm"})
    purchased.append({"label": "Setscrew (sun collar)" if en else "Setskur (güneş bileziği)", "qty": 1,
                      "spec": f"ISO 4026 M3 × {hw.get('setscrew', 4):g} mm + DIN 562 M3 " +
                              ("square nut" if en else "kare somun")})
    if hw.get("hub_fastener") == "NUT" and hw.get("hub_screw_count") and "hub_nut" not in keys:
        purchased.append({"label": "Hex nut (output hub pockets)" if en else "Somun (çıkış göbeği yuvaları)",
                          "qty": hw["hub_screw_count"],
                          "spec": "ISO 4032 M3 " + ("— pushed into the side pockets" if en else "— yan yuvalara itilir")})
    if hw.get("insert_holes"):
        purchased.append({"label": "Heat-set insert (output hub)" if en else "Isıl burç (çıkış göbeği)",
                          "qty": hw.get("insert_count", 4),
                          "spec": "M3 × 5.7 mm " + ("heat-set insert (Ø4.0 hole)" if en else "ısıl burç (Ø4.0 delik)")})
    if not prm.get("cage", True) and not any(p.key.startswith("circlip") for p in result.parts):
        purchased.append({"label": "Circlip" if en else "Segman", "qty": sum(s["num_planets"] for s in d.get("stages", [])),
                          "spec": "DIN 471 " + ("external circlip (pin diameter)" if en else "dış segman (pim çapına uygun)")})
    if "mount_bracket" in keys:
        purchased.append({"label": "Mounting screws (bracket)" if en else "Montaj vidası (braket)", "qty": 4,
                          "spec": "M5 / Ø5 " + ("screw + anchor / nut for your wall, floor, post or panel" if en else
                                                 "vida + duvar / zemin / direk / panelinize uygun dübel veya somun")})
    purchased.append({"label": "Grease" if en else "Gres", "qty": 1,
                      "spec": "PTFE / lithium grease, plastic compatible" if en else
                              "Plastik uyumlu PTFE / lityum gres (dişliler ve rulmanlar)"})
    return printed, purchased


def _ring_steps(result, lang: str) -> List[str]:
    """Steps after the fixed stages of a rotating housing: base plate, fixed carrier, drum, output."""
    herring = result.summary.get("herringbone")
    out_type = result.summary.get("output_type", "DRUM_FLANGE")
    tie = result.summary.get("tie_rod", "M3")
    nuts = result.design.get("hardware", {}).get("hub_fastener") == "NUT"
    drum_b = result.summary.get("drum_bearing", "")
    if lang == "en":
        steps = [f"Fixed base plate: put it on the housing (or the motor flange), insert the {tie} bolts and tighten "
                 "them crosswise into the captive nuts — the heads must sit below the face, the drum turns right above.",
                 "Press the pins of the last stage into the base plate, add the spacer rings and the planets with "
                 "their bearings, the upper spacers, then press the fixed top plate (with the drum stub) onto the pins.",
                 f"Press the {drum_b} bearing into the pocket under the drum lid, then lower the drum over the planets "
                 "until its bearing sits on the stub of the fixed top plate."]
        if herring:
            steps[-1] = (f"Herringbone drum: push the M3 nuts into the side pockets at the bottom of the lower half, "
                         f"screw the lower half onto the planets (turn while pushing), press the {drum_b} bearing into "
                         "the lid of the upper half, screw it on the same way and join both halves with the M3 joint "
                         "screws through the lid.")
        if out_type == "DRUM_FLANGE":
            steps.append(("Push the M3 nuts into the side pockets of the lid; bolt your wheel / pulley / table onto "
                          "the screw circle (part thickness + ~7 mm screws)." if nuts else
                          "Fit the heat-set inserts into the lid holes; bolt your part onto the screw circle."))
        elif out_type == "DRUM_ARM":
            steps.append(("Push the M3 nuts into the side pockets of the lid, put the arm on the lid and tighten the "
                          "M3 screws crosswise (the screw circle carries the torque)." if nuts else
                          "Fit the heat-set inserts into the lid, put the arm on and tighten the M3 screws crosswise."))
        else:
            steps.append("Pass the rope through the hole in the top rim, knot it and wind it onto the drum.")
        return steps
    steps = [f"Sabit taban plakası: gövdenin (veya motor flanşının) üstüne koyun, {tie} cıvatalarını takıp somunlara "
             "çapraz sırayla sıkın — başlar yüzeyin altında kalmalı, tambur hemen üstünde döner.",
             "Son kademenin pimlerini taban plakasına presleyin, ara halkaları ve rulmanlı planetleri takın, üst ara "
             "halkaları koyup tambur göbekli sabit üst plakayı pimlere presleyin.",
             f"{drum_b} rulmanını tambur kapağının altındaki yuvaya presleyin, tamburu planetlerin üzerine indirin; "
             "rulman sabit üst plakanın göbeğine oturur."]
    if herring:
        steps[-1] = (f"Balıksırtı tambur: M3 somunları alt yarının altındaki yan yuvalara itin, alt yarıyı planetlerin "
                     f"üzerine çevirerek geçirin; {drum_b} rulmanını üst yarının kapağına presleyin, üst yarıyı da "
                     "aynı şekilde geçirip iki yarıyı kapaktan giren M3 birleşim vidalarıyla sıkın.")
    if out_type == "DRUM_FLANGE":
        steps.append("M3 somunları kapaktaki yan yuvalara itin; tekerlek / kasnak / tablayı vida dairesine M3 "
                     "vidalarla bağlayın (parça kalınlığı + ~7 mm)." if nuts else
                     "Isıl burçları kapak deliklerine yerleştirin; parçanızı vida dairesine bağlayın.")
    elif out_type == "DRUM_ARM":
        steps.append("M3 somunları kapaktaki yan yuvalara itin, kolu kapağa oturtup M3 vidaları çapraz sırayla sıkın "
                     "(torku vida dairesi taşır)." if nuts else
                     "Isıl burçları kapağa yerleştirin, kolu oturtup M3 vidaları çapraz sırayla sıkın.")
    else:
        steps.append("Halatı üst kenardaki delikten geçirip düğümleyin ve tambura sarın.")
    return steps


def _wolfrom_steps(result, lang: str) -> List[str]:
    s = result.summary
    tie, plain = s.get("tie_rod", "M4"), s.get("drum_bearing") == "PLAIN"
    arm = s.get("output_type") == "DRUM_ARM"
    if lang == "en":
        steps = ["Motor flange: push the hex nuts into the side pockets of the lugs, bolt the motor on with its 4 cap "
                 "screws (the heads sink into the counterbores).",
                 "Sun: put the M3 square nut into the collar pocket, slide the sun onto the motor shaft with the set "
                 "screw on the flat and tighten it.",
                 "Stepped planets: press one bearing flush into each end. All planets are identical; in the model each one "
                 "is turned to its own tooth phase — if a planet does not drop in, turn it one tooth at a time until "
                 "both gears enter the rings.",
                 "Carrier: press the pins into the bottom plate (flush underneath), put on the spacer rings, slide the "
                 "planets on, the upper spacers, then press the top plate onto the pins.",
                 "Put the carrier with the planets around the sun, then lower the fixed ring housing over the lower "
                 "planet gears onto the motor flange."]
        steps.append("Grease the plain bearing surfaces of the output ring and the housing sleeve generously, then "
                     "lower the output ring over the upper planet gears into the sleeve." if plain else
                     "Press the output bearing into the housing sleeve, then press the output ring into the bearing "
                     "while it slides over the upper planet gears.")
        steps.append(f"Insert the {tie} tie bolts through the housing into the nuts of the motor flange and tighten "
                     f"them crosswise.")
        steps.append("Press the M3 heat-set inserts into the lid of the output ring" +
                     (", put the arm on the lid and tighten the M3 screws crosswise." if arm else
                      "; bolt your wheel / pulley / table onto them."))
        steps.append("Turn the motor slowly in both directions; the output turns very slowly. A self-locking set cannot "
                     "be turned at the output by hand — that is intended.")
        return steps
    steps = ["Motor flanşı: altıgen somunları kulaklardaki yan yuvalara itin, motoru 4 imbus vidayla bağlayın (başlar "
             "havşalara gömülü kalır).",
             "Güneş: M3 kare somunu bilezikteki yuvaya yerleştirin, güneşi setskur düzlüğe bakacak şekilde motor miline "
             "geçirip sıkın.",
             "Kademeli planetler: her iki uca birer rulmanı yüzeyle aynı hizada presleyin. Planetlerin hepsi aynıdır; "
             "modelde her biri kendi diş fazına çevrilmiştir — bir planet yerine girmezse iki dişlisi de çemberlere "
             "oturana kadar birer diş çevirin.",
             "Taşıyıcı: pimleri alt plakaya presleyin (altta yüzey hizasında), ara halkaları takın, planetleri geçirin, "
             "üst ara halkaları koyup üst plakayı pimlere presleyin.",
             "Planetli taşıyıcıyı güneşin çevresine yerleştirin, sabit çember gövdesini alt planet dişlilerinin "
             "üzerinden motor flanşına indirin."]
    steps.append("Çıkış çemberinin ve gövde kovanının kaymalı yatak yüzeylerini bolca gresleyin, çıkış çemberini üst "
                 "planet dişlilerinin üzerinden kovana indirin." if plain else
                 "Çıkış rulmanını gövde kovanına presleyin, çıkış çemberini üst planet dişlilerinin üzerinden geçirerek "
                 "rulmana presleyin.")
    steps.append(f"{tie} bağlantı cıvatalarını gövdeden motor flanşındaki somunlara takıp çapraz sırayla sıkın.")
    steps.append("M3 ısıl burçları çıkış çemberinin kapağına presleyin" +
                 ("; kolu kapağa oturtup M3 vidaları çapraz sırayla sıkın." if arm else
                  "; tekerlek / kasnak / tablayı bunlara vidalayın."))
    steps.append("Motoru iki yönde yavaşça çalıştırın; çıkış çok yavaş döner. Kendiliğinden kilitlenen bir set çıkıştan "
                 "elle çevrilemez — bu istenen davranıştır.")
    return steps


def _cycloid_steps(result, lang: str) -> List[str]:
    s = result.summary
    tie, arm = s.get("tie_rod", "M4"), s.get("output_type") == "ARM"
    if lang == "en":
        return ["Motor flange: push the hex nuts into the side pockets of the lugs, bolt the motor on with its 4 cap screws.",
                "Housing: put it on the flange and press the steel ring pins into the half holes of the bore (down to "
                "the floor).",
                "Eccentric hub: put the M3 square nut into the collar pocket, slide the hub onto the motor shaft with the "
                "set screw on the flat and tighten it.",
                "Press a bearing into the pocket on the underside of each disc. Lay disc A (lower cam) between the ring "
                "pins, then disc B on the upper cam — B is turned by half a lobe and only drops in that way round.",
                "Output plate: press the steel output pins into the blind holes from below, grease them and lower the "
                "plate so that the pins pass through the holes of both discs.",
                "Press the output bearing into the cover from below, put the cover over the output hub onto the housing, "
                f"insert the {tie} tie bolts into the flange nuts and tighten them crosswise.",
                "Press the M3 heat-set inserts into the output hub" +
                (", put the arm on it and tighten the M3 screws crosswise." if arm else
                 "; bolt your wheel / pulley / table onto them."),
                "Grease the ring pins and the disc edges generously; run the motor slowly in both directions — the output "
                "turns against the input."]
    return ["Motor flanşı: altıgen somunları kulaklardaki yan yuvalara itin, motoru 4 imbus vidayla bağlayın.",
            "Gövde: flanşın üstüne koyun, çelik halka pimlerini delikteki yarım yuvalara zemine kadar presleyin.",
            "Eksantrik göbek: M3 kare somunu bilezikteki yuvaya yerleştirin, göbeği setskur düzlüğe bakacak şekilde motor "
            "miline geçirip sıkın.",
            "Her diskin altındaki yuvaya bir rulman presleyin. Disk A'yı (alt kam) halka pimlerinin arasına, disk B'yi "
            "üst kama yerleştirin — B yarım lob döndürülmüştür ve yalnızca o yönde oturur.",
            "Çıkış plakası: çelik çıkış pimlerini alttan kör deliklere presleyin, gresleyip plakayı pimler iki diskin "
            "deliklerinden geçecek şekilde indirin.",
            "Çıkış rulmanını kapağa alttan presleyin, kapağı çıkış göbeğinin üzerinden gövdeye oturtun, "
            f"{tie} bağlantı cıvatalarını flanş somunlarına takıp çapraz sırayla sıkın.",
            "M3 ısıl burçları çıkış göbeğine presleyin" +
            ("; kolu oturtup M3 vidaları çapraz sırayla sıkın." if arm else
             "; tekerlek / kasnak / tablayı bunlara vidalayın."),
            "Halka pimlerini ve disk kenarlarını bolca gresleyin; motoru iki yönde yavaşça çalıştırın — çıkış girişin "
            "tersine döner."]


def assembly_steps(result, lang: str = "tr") -> List[str]:
    steps = _arrangement_steps(result, lang)
    pin = next((pt for pt in result.parts if pt.key == "declutch_pin"), None)
    if pin:
        code = pin.label.split(" ", 2)[-1]
        steps.insert(len(steps) - 1, (
            f"Release: screw the drive collar / ring onto the output (hub or drum lid) instead of the arm, slide the "
            f"arm over its neck, put the cap washer on and tighten the M3 screws. Push the thin nut into the pocket "
            f"under the arm, screw the {code} index plunger in from the top until its thread ends flush with the arm "
            f"underside and lock it with its lock nut. Driving: the spring pushes the pin into the collar. Release: pull "
            f"the knob and turn it a quarter — it stays up and the arm turns freely by hand. Re-engage: turn the knob "
            f"back and move the arm until the pin snaps in. A pull solenoid can take the knob's place later." if lang == "en"
            else
            f"Boşa alma: kol yerine tahrik bileziğini / halkasını çıkışa (göbek veya tambur kapağı) vidalayın, kolu "
            f"boynuna geçirin, kapak pulunu koyup M3 vidaları sıkın. İnce somunu kolun altındaki cebe itin, {code} "
            f"indeks pimini üstten dişi kolun alt yüzüyle aynı hizaya gelene kadar vidalayın ve kilit somunuyla "
            f"sabitleyin. Çalışırken yay pimi bileziğe iter. Boşa almak için topuzu çekip çeyrek tur çevirin: pim yukarıda "
            f"kalır, kol elle serbest döner. Geri bağlamak için topuzu geri çevirip kolu pim tık diye girene kadar "
            f"oynatın. İleride topuzun yerine bir çekme solenoidi takılabilir."))
    br = next((pt for pt in result.parts if pt.key == "mount_bracket"), None)
    if br:
        steps.insert(0, (f"{br.label}: put it under the motor flange (the motor passes through its opening); the tie "
                         f"rods run on through its shelf into the nuts in the pockets underneath. Screw it to the wall / "
                         f"floor / post / panel with 4 M5 screws before mounting the load." if lang == "en" else
                         f"{br.label}: motor flanşının altına yerleştirin (motor açıklıktan geçer); bağlantı cıvataları "
                         f"rafından geçip alttaki yuvalardaki somunlara girer. Yükü takmadan önce 4 adet M5 vidayla "
                         f"duvara / zemine / direğe / panele vidalayın."))
    return steps


def _arrangement_steps(result, lang: str = "tr") -> List[str]:
    arr = result.summary.get("arrangement", "CARRIER")
    if arr == "WOLFROM":
        return _wolfrom_steps(result, lang)
    if arr == "CYCLOID":
        return _cycloid_steps(result, lang)
    steps = _assembly_steps(result, lang)
    if arr == "RING":
        # the cover / output bearing / output member steps do not apply: base plate, fixed carrier, drum instead
        drop = ["kapağa alttan", "into the cover", "Çıkış rulmanını", "output bearing", "M3 somunları çıkış",
                "çıkış göbeğine", "çıkış flanşına", "output flange", "output hub", "Çıkış milinin", "output shaft",
                "Çelik çıkış", "steel output"]
        if result.summary.get("stages") == 1:      # one star stage: no fixed ring housing at all
            drop += ["gövde bölümünü", "Çember dişli gövdesini", "ring housing section", "Slide the ring housing"]
        keep = [s for s in steps if not any(k in s for k in drop)]
        tail = keep[-1:]                      # the run-in step stays last
        steps = keep[:-1] + _ring_steps(result, lang) + tail
    if arr == "SPEED_UP":
        steps.insert(len(steps) - 1, (
            "Speed-up: connect the motor as a generator (stepper: rectifier bridge per phase; DC motor: diode + "
            "capacitor), fit the crank or rotor to the arm / shaft / flange and turn it slowly by hand first."
            if lang == "en" else
            "Hız artırıcı: motoru jeneratör olarak bağlayın (step motor: her faza köprü diyot; DC motor: diyot + "
            "kondansatör), kol / mil / flanşa krank veya rotoru takın ve önce elle yavaşça çevirin."))
    return steps


def _assembly_steps(result, lang: str = "tr") -> List[str]:
    d = result.design
    cage = d.get("params", {}).get("cage", True)
    herring = result.summary.get("herringbone")
    out_type = result.summary.get("output_type", "FLANGE")
    tie = result.summary.get("tie_rod", "M3")
    rods = any(pt.key == "tie_rod_top_nut" for pt in result.parts)
    nuts = d.get("hardware", {}).get("hub_fastener") == "NUT"
    if lang == "en":
        steps = [
            "Print all parts with the settings below; remove brims and check that bearings slide into their seats with light pressure.",
            "Motor flange: push the hex nuts into the side slots of the lugs, then mount the motor with 4 socket screws (heads sit flush in the counterbores).",
            "Stage-1 sun: insert the M3 square nut into the collar slot, slide the sun onto the motor shaft with the setscrew facing the flat, tighten.",
            "Press the bearings into each planet flush with the faces (one from each side for the dual layout).",
        ]
        if cage:
            steps += ["For each carrier: press the pins into the bottom plate (flush underneath), put the green spacer rings, "
                      "slide on the planets, add the top spacer rings and press the top plate onto the pins.",
                      "Carriers of the next stages already contain the next sun gear — stack the carriers in order."]
        else:
            steps += ["Slide the planets onto the carrier pins and snap the circlips into the grooves."]
        steps += [("Herringbone: screw each ring housing section onto the planets by turning it while pushing — "
                   "the sections only go on in one way. " if herring else "Slide the ring housing over the gear set. ")
                  + "The centering lips make every joint concentric.",
                  "Press the output bearing into the cover (from below), place the cover, insert the " + tie +
                  (" threaded rods into the captive nuts, add the top nuts and tighten crosswise." if rods
                   else " bolts and tighten crosswise into the captive nuts."),
                  ((("Push the M3 nuts into the side pockets of the output flange; fasten your part with M3 screws "
                      "(part thickness + ~6 mm).") if nuts else
                    "Fit the threaded inserts into the output flange with a soldering iron.") if out_type == "FLANGE"
                   else (("Push the M3 nuts into the side pockets of the output hub, slide the arm onto the double-D "
                          "lock and tighten the M3 screws (the flats carry the torque, the screws only hold the arm).")
                         if nuts else
                         "Fit the threaded inserts into the output hub, slide the arm onto the double-D lock and "
                         "tighten the M3 screws (the flats carry the torque, the screws only hold the arm).")
                   if out_type == "ARM"
                   else "Press the steel output shaft into the carrier hub." if out_type == "SHAFT_STEEL" else
                   "Check that the output shaft spins freely."),
                  "Grease the teeth lightly and run in at low speed for a few minutes in both directions."]
        return steps
    steps = [
        "Tüm parçaları aşağıdaki ayarlarla basın; kenar fırçalarını (brim) temizleyin, rulmanların yuvalara hafif baskıyla girdiğini kontrol edin.",
        "Motor flanşı: altıgen somunları kulaklardaki yan yuvalara itin, motoru 4 imbus vidayla bağlayın (başlar havşalara gömülü kalır).",
        "1. kademe güneşi: M3 kare somunu bilezikteki yuvaya yerleştirin, güneşi setskur düzlüğe bakacak şekilde motor miline geçirip sıkın.",
        "Rulmanları planetlere yüzeyle aynı hizada presleyin (çift düzende her yüzden birer tane).",
    ]
    if cage:
        steps += ["Her taşıyıcı için: pimleri alt plakaya presleyin (altta yüzey hizasında), yeşil ara halkaları takın, "
                  "planetleri geçirin, üst ara halkaları koyup üst plakayı pimlere presleyin.",
                  "Sonraki kademelerin üst plakası bir sonraki güneş dişliyi içerir — taşıyıcıları sırayla üst üste yerleştirin."]
    else:
        steps += ["Planetleri taşıyıcı pimlerine geçirin ve segmanları kanallara oturtun."]
    steps += [("Balıksırtı: her gövde bölümünü itip aynı anda çevirerek planetlerin üzerine vidalar gibi geçirin — "
               "bölümler tek yönde takılır. " if herring else "Çember dişli gövdesini dişli setinin üzerine geçirin. ")
              + "Merkezleme omuzları her birleşimi eş eksenli yapar.",
              "Çıkış rulmanını kapağa alttan presleyin, kapağı yerleştirin, " + tie +
              (" saplamalarını alttaki somunlara geçirin, üst somunları takıp çapraz sırayla sıkın." if rods
               else " cıvatalarını takıp somunlara çapraz sırayla sıkın."),
              (("M3 somunları çıkış flanşındaki yan yuvalara itin; bağlayacağınız parçayı M3 vidalarla "
                "(parça kalınlığı + ~6 mm) sıkın." if nuts else
                "Isıl burçları havya ile çıkış flanşına yerleştirin.") if out_type == "FLANGE"
               else ("M3 somunları çıkış göbeğindeki yan yuvalara itin, kolu çift-D kilide geçirip M3 vidaları sıkın "
                     "(torku düzlükler taşır, vidalar yalnızca kolu tutar)." if nuts else
                     "Isıl burçları çıkış göbeğine yerleştirin, kolu çift-D kilide geçirip M3 vidaları sıkın "
                     "(torku düzlükler taşır, vidalar yalnızca kolu tutar).") if out_type == "ARM"
               else "Çelik çıkış milini taşıyıcı göbeğine presleyin." if out_type == "SHAFT_STEEL"
               else "Çıkış milinin serbest döndüğünü kontrol edin."),
              "Dişlileri hafifçe gresleyin, birkaç dakika düşük devirde iki yönde alıştırın."]
    return steps


def write_bom_text(result, path: str, lang: str = "tr") -> str:
    t = T["en" if lang == "en" else "tr"]
    printed, purchased = bill_of_materials(result, lang)
    lines = [result.product_name, "=" * len(result.product_name), ""]
    s = result.summary
    lines += [f"{t['ratio']:<32}: {s['total_ratio']} : 1",
              f"{t['out_t']:<32}: {s['output_torque']} Nm @ {s['output_speed']} rpm",
              f"{t['out_max']:<32}: {s['max_output_torque']} Nm",
              f"{t['dims']:<32}: Ø{s['outer_diameter']} / {s['body_length']} mm", "",
              t["printed"].upper(), "-" * 40]
    for r in printed:
        lines.append(f"{r['no']:02d}  {r['qty']} x  {r['label']}  ({r['material']}, {r['mass_g']} g)")
    lines += ["", t["purchased"].upper(), "-" * 40]
    for r in purchased:
        lines.append(f"{r['qty']} x  {r['spec']}  — {r['label']}")
    if result.warnings:
        lines += ["", t["warnings"].upper(), "-" * 40] + [f"- {w}" for w in result.warnings]
    with open(path, "w", encoding="utf-8-sig") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def write_html_report(result, path: str, lang: str = "tr") -> str:
    t = T["en" if lang == "en" else "tr"]
    e = result.engineering
    s = result.summary
    d = result.design
    prm = d.get("params", {})
    gm, sm = get_material(prm.get("gear_material", "PLA")), get_material(prm.get("struct_material", "PLA"))
    esc = html.escape
    lc = e.get("load_case", {})
    lim = e.get("limiting") or {}
    ha = float(prm.get("addendum", 1.0) or 1.0)
    depth_kind = t["depth_std"] if abs(ha - 1.0) < 1e-6 else (t["depth_stub"] if ha < 1.0 else t["depth_long"])
    load_v = e.get("load")

    def row(k, v):
        return f"<tr><th>{esc(k)}</th><td>{esc(str(v))}</td></tr>"

    arr = s.get("arrangement", "CARRIER")
    rev = bool(e.get("reverse"))
    summary_rows = "".join([
        row(t["arrangement"], t.get("arr_" + arr, arr)),
        *([row(t["drum"], f"Ø{s.get('drum_diameter', 0)} mm / {s.get('drum_bearing', '')}")] if arr == "RING" else []),
        row(t["ratio"], f"{s['total_ratio']} : 1"),
        row(t["stages"], s["stages"]),
        *([row(t["type"], t["herring"] if s["herringbone"] else t["spur"]),
           row(t["module"], f"m {s['module']:g} / Zr {s['z_ring']}")] if arr != "CYCLOID" else []),
        *([row(t["drive"], f"{e['input_torque']:.2f} Nm @ {e['input_speed']:.1f} rpm"),
           row(t["generator"], f"{e['output_torque']:.3f} Nm @ {e['output_speed']:.0f} rpm")] if rev else
          [row(t["out_t"], f"{e['output_torque']:.2f} Nm"),
           row(t["out_max"], f"{e['max_output_torque']:.2f} Nm"),
           row(t["out_n"], f"{e['output_speed']:.2f} rpm")]),
        row(t["eff"], f"%{e['efficiency'] * 100:.1f}"),
        row(t["limit"], f"{lim.get('label', '-')} ({t['stage']} {lim.get('stage', '-')})"),
        row(t["dims"], f"Ø{s['outer_diameter']} mm / {s['body_length']} mm"),
        *([row(t["depth"], f"{ha:.2f} ({depth_kind})")] if arr != "CYCLOID" else []),
        row(t["mass"], f"~{s['printed_mass_g']:.0f} g (%100 dolgu)" if lang != "en" else f"~{s['printed_mass_g']:.0f} g (100% infill)"),
    ])
    input_rows = "".join([
        row(t["motor"], f"{prm.get('motor')}" + ("" if rev else f" — {e['input_torque']:.2f} Nm @ {e['input_speed']:.0f} rpm")),
        row(t["ka"], lc.get("application_factor")),
        row(t["targets"], f"S_F ≥ {lc.get('target_sf')} · S_H ≥ {lc.get('target_sh')} · L10h ≥ {lc.get('target_life_h'):.0f} h"),
        row(t["materials"], f"{gm['name']} / {sm['name']}"),
    ] + ([row(t["app_load"], load_v.get("short", ""))] if load_v else []))
    load_html = ""
    if rev and e.get("speedup"):
        sp = e["speedup"]
        load_html = (f"<h2>{t['speedup']}</h2><p class='load {esc(sp.get('status', ''))}'>{esc(sp.get('text', ''))}</p>")
    if load_v:
        fixes = "".join(f"<li>{esc(x)}</li>" for x in load_v.get("fixes") or [])
        load_html = (f"<h2>{t['app_load']}</h2><p class='load {esc(load_v.get('status', ''))}'>"
                     f"{esc(load_v.get('summary') or load_v.get('text', ''))}</p>"
                     + (f"<p><b>{t['fixes']}:</b></p><ul>{fixes}</ul>" if fixes else ""))
    stage_html = []
    for st, geo_st in zip(e["stages"], d.get("stages", [])):
        if "cycloid" in geo_st:
            cy = geo_st["cycloid"]
            geo_rows = "".join([
                row(t["cy_pins"], f"{cy['n_pins']} × Ø{2 * cy['rp']:g} mm @ R {cy['R']:g} mm (i = {st['ratio']:.0f})"),
                row(t["cy_ecc"], f"{cy['e']:.2f} mm · {cy['e'] * cy['n_pins'] / cy['R']:.2f}"),
                row(t["cy_disc"], f"{cy['n_pins'] - 1} {t['cy_lobes']} · {cy['disc_t']:g} mm"),
                row(t["cy_out"], f"{cy['n_out']} × Ø{cy['d_out']:g} mm @ R {cy['R_out']:.1f} mm"),
                row(t["cy_brg"], cy["bearing"]),
                row("T_in / T_out", f"{st['input_torque']:.2f} / {st['output_torque']:.2f} Nm"),
                row(t["cy_force"], f"{st['tangential_force']:.0f} N"),
                *([row(t["expert"], f"{st['expert']['temp']:.0f} °C (≤ {st['expert']['t_max']:.0f}) · f_T "
                                    f"{st['expert']['f_t']:.2f} · Y_NT {st['expert']['y_nt']:.2f} · Z_NT "
                                    f"{st['expert']['z_nt']:.2f} · {st['expert']['cycles']:.2e} · µ {st['expert']['mu']:.2f}")]
                  if st.get("expert") else []),
            ])
        else:
            g = geo_st["geometry"]
            geo_rows = "".join([
                row(t["teeth"], f"{geo_st['z_sun']} / {geo_st['z_planet']} / {geo_st['z_ring']} (i = {st['ratio']:.3f})"),
                row(t["cd"], f"{g['center_distance']:.3f} mm"),
                row(t["tips"], f"{g['tip_sun']:.3f} / {g['tip_planet']:.3f} / {g['tip_ring']:.3f} mm"),
                row(t["eps"], f"{st['eps_alpha_sp']:.2f} / {st['eps_alpha_pr']:.2f} · {st['eps_beta']:.2f}"),
                row(t["land"], f"{g.get('tip_land_sun', 0.0):.2f} / {g.get('tip_land_planet', 0.0):.2f} mm"),
                *([row(t["shift"], f"{g['x_sun']:+.3f} / {g['x_planet']:+.3f} / {g['x_ring']:+.3f}")]
                  if abs(g.get("x_sun", 0.0)) > 1e-9 else []),
                *([row(t["root_f"], " / ".join(f"{t['gear_' + k]} ×{v:.2f}" for k, v in (st.get('depth_factor') or {}).items()))]
                  if abs(ha - 1.0) > 1e-6 else []),
                row(t["bearing"], f"{geo_st['bearing']} — {t.get(geo_st['layout'], geo_st['layout'])}"),
                row(t["pins"], f"Ø{geo_st['pin_dia']:g} mm"),
                row("T_in / T_out", f"{st['input_torque']:.2f} / {st['output_torque']:.2f} Nm"),
                row("F_t · v", f"{st['tangential_force']:.0f} N · {st['pitch_velocity']:.3f} m/s"),
                *([row(t["khb"], f"{st['k_hbeta']:.2f} / {st['k_fbeta']:.2f} · {st['misalignment_um']:.1f} µm")]
                  if "k_hbeta" in st else []),
                *([row(t["expert"], f"{st['expert']['temp']:.0f} °C (≤ {st['expert']['t_max']:.0f}) · f_T "
                                    f"{st['expert']['f_t']:.2f} · Y_NT {st['expert']['y_nt']:.2f} · Z_NT "
                                    f"{st['expert']['z_nt']:.2f} · {st['expert']['cycles']:.2e} · µ {st['expert']['mu']:.2f}")]
                  if st.get("expert") else []),
            ])
        checks = "".join(
            f"<tr class='{'ok' if c['ok'] else 'bad'}'><td>{esc(c['label'])}</td><td>{_fmt(c['value'], c['unit'])}</td>"
            f"<td>{_fmt(c['limit'], c['unit'])}</td><td><b>{c['safety']:.2f}</b></td><td>{c['target']:.2f}</td>"
            f"<td>{t['ok'] if c['ok'] else t['fail']}</td></tr>" for c in st["checks"])
        stage_html.append(
            f"<section><h3>{t['stage']} {st['index']}</h3><div class='two'><table class='kv'>{geo_rows}</table>"
            f"<table class='checks'><thead><tr><th>{t['check']}</th><th>{t['value']}</th><th>{t['allow']}</th>"
            f"<th>{t['safety']}</th><th>{t['target']}</th><th></th></tr></thead><tbody>{checks}</tbody></table></div></section>")
    printed, purchased = bill_of_materials(result, lang)
    p_rows = "".join(f"<tr><td>{r['no']:02d}</td><td>{esc(r['label'])}</td><td>{r['qty']}</td><td>{esc(r['material'])}</td>"
                     f"<td>{r['mass_g']} g</td><td>{esc(r['note'])}</td></tr>" for r in printed)
    b_rows = "".join(f"<tr><td>{r['qty']}</td><td>{esc(r['spec'])}</td><td>{esc(r['label'])}</td></tr>" for r in purchased)
    steps = "".join(f"<li>{esc(x)}</li>" for x in assembly_steps(result, lang))
    warns = "".join(f"<li>{esc(w)}</li>" for w in result.warnings)
    method = (
        "Diş dibi: Lewis form faktörü (sanal diş sayısı) + ISO 6336-3 Yε, Yβ; diş yüksekliği h*a ≠ 1 ise ISO 6336-3 "
        "Y_F·Y_S oranıyla düzeltilir (yük gerçek uçta); yüzey: Hertz (ISO 6336-2 biçimi); "
        "uygulama yükü: T = F·r, motor×oran×verim ≥ rezerv×T (step 1.5, diğer 1.25), kapasite ≥ T, çıkış rulmanı C0/F ≥ 2; "
        "K_v Barth (baskı: (3.05+v)/3.05), yük paylaşımı Kγ (N=3: 1.15, baskıda +0.10); planet ters eğilme ×0.7; "
        "profil kaydırma V-sıfır (güneş +x, planet ve çember −x; eksen mesafesi standart), otomatik x diş dibi "
        "dayanımlarını dengeler (ISO 6336-3 B yöntemi, x ile); "
        "diş genişliği boyunca yük dağılımı K_Hβ (ISO 6336-1 C yöntemi, sadeleştirilmiş): eğiklik = pim deliği konum "
        "hatası (FDM 0.02 mm) + yük altında pim eğilmesi (kafeste serbest plakanın burulması, tek plakada konsol), "
        "plastiklerde %65 alışma, diş rijitliği c_γ = 20·E/210000 N/(mm·µm); K_Fβ = K_Hβ^N_F; "
        "rulman L10h = (C/P)³·10⁶/(60 n); pim eğilmesi kafes taşıyıcıda iki mesnetli; burulma τ = 16T/(πd³), "
        "katmanlar arası kayma için baskıda ×0.6. Dönen gövdede son kademe yıldız düzenindedir (taşıyıcı sabit, "
        "i = Zr/Zs, planet bağıl devri = güneş devri); tambur vida daireleri delik ezilmesine göre kontrol edilir. "
        "Hız artırıcıda torklar verim indirimi olmadan çıkış tarafından hesaplanır (güvenli taraf). "
        "Malzeme değerleri tasarım değeridir; kritik uygulamalarda test baskısı ile doğrulayın."
        if lang != "en" else
        "Root: Lewis form factor on the virtual tooth count + ISO 6336-3 Yε, Yβ; tooth depth h*a ≠ 1 corrected by the "
        "ISO 6336-3 Y_F·Y_S ratio (load at the actual tip); contact: Hertz (ISO 6336-2 form); "
        "application load: T = F·r, motor×ratio×efficiency ≥ reserve×T (stepper 1.5, other 1.25), capacity ≥ T, output "
        "bearing C0/F ≥ 2; "
        "K_v Barth (printed: (3.05+v)/3.05), load sharing Kγ (N=3: 1.15, +0.10 printed); planet reversed bending ×0.7; "
        "profile shift V-zero (sun +x, planet and ring −x; standard centre distances), the automatic x balances the "
        "root strengths (ISO 6336-3 method B with x); "
        "face load factor K_Hβ (simplified ISO 6336-1 method C): misalignment = pin hole position error (FDM 0.02 mm) "
        "+ pin deflection under load (cage: wind-up of the free plate, single plate: cantilever), 65 % running-in for "
        "plastics, mesh stiffness c_γ = 20·E/210000 N/(mm·µm); K_Fβ = K_Hβ^N_F; "
        "bearing L10h = (C/P)³·10⁶/(60 n); cage pins as simply supported beams; torsion τ = 16T/(πd³), ×0.6 for "
        "printed interlayer shear. A rotating housing has a star last stage (carrier fixed, i = Zr/Zs, planet "
        "relative speed = sun speed); the drum screw circles are checked for hole bearing pressure. A speed-up "
        "gearbox is calculated from the input side without efficiency credit (safe side). "
        "Material values are design values — validate critical designs with test prints.")
    if any(st.get("expert") for st in e.get("stages", [])):
        method += (" Expert mode: tooth temperature after the structure of VDI 2736-2 (root, plastic/plastic k2 = 2.4, "
                   "closed printed housing R = 0.172 K·m²/W over the stage surface, duty ED^0.64), allowables × f_T "
                   "(1 at 23 °C → 0.5 at the material limit), load cycles over the target life: root Y_NT = "
                   "(10⁶/N)^0.1, flank Z_NT = (10⁶/N)^(1/15); wear W = T·2π·N·k_w/(b·z·2.25m) ≤ 0.15m; creep of a "
                   "load held at rest: σ_F·(0.55 − 0.07 log t). Wolfrom / cycloidal: housing heat balance of the power loss "
                   "P·(1 − η)·0.172/A (+ the sun mesh tooth term, resp. ×1.5 at the pin contacts); dry running lowers "
                   "their efficiency. Constants are approximate — validate with tests."
                   if lang == "en" else
                   " Uzman modu: diş sıcaklığı VDI 2736-2 yapısında (diş dibi, plastik/plastik k2 = 2.4, kapalı baskı "
                   "gövde R = 0,172 K·m²/W kademe yüzeyi üzerinden, ED^0,64), emniyet sınırları × f_T (23 °C'de 1 → "
                   "malzeme sınırında 0,5), hedef ömürdeki çevrim: diş dibi Y_NT = (10⁶/N)^0,1, yüzey Z_NT = "
                   "(10⁶/N)^(1/15); aşınma W = T·2π·N·k_w/(b·z·2,25m) ≤ 0,15m; durarak yük tutmada sünme: "
                   "σ_F·(0,55 − 0,07 log t). Wolfrom / sikloidal: kayıp gücün P·(1 − η)·0,172/A gövde ısı dengesi (+ güneş "
                   "kavramasının diş terimi, sikloidalde pim temasında ×1,5); kuru çalışmada verimleri düşer. Katsayılar "
                   "yaklaşıktır — deneme baskılarıyla doğrulayın.")
    doc = f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{esc(result.product_name)}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:28px auto;max-width:1100px;color:#1d2733;font-size:13px}}
h1{{font-size:22px;margin:0}} h2{{font-size:16px;margin:26px 0 8px;border-bottom:2px solid #0077b6;padding-bottom:4px}}
h3{{font-size:14px;margin:18px 0 6px}} table{{border-collapse:collapse;width:100%}} td,th{{padding:4px 8px;border-bottom:1px solid #e3e8ee;text-align:left;vertical-align:top}}
.kv th{{width:42%;color:#4a5869;font-weight:600}} .two{{display:grid;grid-template-columns:1fr 1.5fr;gap:18px}}
.checks thead th{{background:#eef3f8}} tr.ok td:last-child{{color:#127a4a;font-weight:700}} tr.bad td{{background:#fff3f0}} tr.bad td:last-child{{color:#c0392b;font-weight:700}}
.meta{{color:#6b7a8c;font-size:12px}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}} ol li,ul li{{margin:4px 0}}
.warn li{{color:#8a5a00}} .load{{padding:6px 10px;border-left:4px solid #6b7a8c;background:#f5f7fa}}
.load.ok{{border-color:#127a4a}} .load.low{{border-color:#d08a00}} .load.fail{{border-color:#c0392b}} @media print{{body{{margin:10mm}} section{{break-inside:avoid}}}}
</style></head><body>
<h1>{esc(t['title'])}</h1><div class="meta">{esc(result.product_name)} · {t['generated']}: {_dt.datetime.now():%Y-%m-%d %H:%M}</div>
<div class="grid"><div><h2>{t['summary']}</h2><table class="kv">{summary_rows}</table></div>
<div><h2>{t['inputs']}</h2><table class="kv">{input_rows}</table>
{f'<h2>{t["warnings"]}</h2><ul class="warn">{warns}</ul>' if warns else ''}</div></div>
{load_html}
<h2>{t['geometry']} &amp; {t['check']}</h2>{''.join(stage_html)}
<h2>{t['printed']}</h2><table><thead><tr><th>#</th><th>{t['part']}</th><th>{t['qty']}</th><th>{t['material']}</th><th>{t['mass_each']}</th><th>{t['note']}</th></tr></thead><tbody>{p_rows}</tbody></table>
<h2>{t['purchased']}</h2><table><thead><tr><th>{t['qty']}</th><th>Spec</th><th>{t['part']}</th></tr></thead><tbody>{b_rows}</tbody></table>
<h2>{t['print']}</h2><p><b>{esc(gm['name'])}:</b> {esc(gm['print'])}<br><b>{esc(sm['name'])}:</b> {esc(sm['print'])}</p>
<h2>{t['assembly']}</h2><ol>{steps}</ol>
<h2>{t['method']}</h2><p>{esc(method)}</p>
</body></html>"""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return path
