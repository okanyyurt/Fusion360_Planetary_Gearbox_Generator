# -*- coding: utf-8 -*-
"""
Gereksinimden tasarım çözücüsü (core/requirements.py) ve tasarım motorunun yeni sınırları:
çıkış göbeği önerisi, boy sınırı, tabla kontrolü, motor mili, büyük modül/cıvata seçimi.
Çalıştırma:  py -3.14 tests/test_requirements.py
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.design import auto_tie_rod, design, resolve      # noqa: E402
from core.hardware import is_threaded_rod, pick_tie_bolt   # noqa: E402
from core.requirements import max_planets, solve           # noqa: E402


def test_user_example():
    """Kullanıcının örneği: 300 rpm 5 Nm → 2 rpm, ≥600 Nm, D tipi Ø5 mil, Ø290 × 280 mm."""
    t = time.time()
    out = solve(dict(motor_preset="CUSTOM", motor_torque=5, motor_speed=300, motor_shaft_dia=5,
                     motor_shaft_type="D_CUT", output_speed=2, ratio=120, min_output_torque=600,
                     max_od=290, max_length=280, lang="tr"))
    el = time.time() - t
    d = out["derived"]
    codes = [x["code"] for x in out["diagnostics"]]
    assert abs(d["ratio"] - 150.0) < 1e-6, d
    assert "ratio_conflict" in codes, "120:1 ile 300→2 rpm çelişkisi bildirilmeli"
    assert 600 <= d["output_torque_nominal"] <= 640, d
    assert "motor_shaft" in codes, "Ø5 mil 5 Nm için ince olarak bildirilmeli"
    assert out["solutions"], "en yakın tasarım gösterilmeli"
    s = out["solutions"][0]
    assert s["outer_diameter"] <= 290 + 1e-6 and s["overall_length"] <= 280 + 1e-6, s["label"]
    assert out["status"] in ("infeasible", "partial", "ok")
    if out["status"] == "infeasible":
        assert "no_solution" in codes and not s["recommended"]
    assert el < 45, f"çözücü çok yavaş: {el:.1f} s"
    print(f"  [OK] kullanıcı örneği: oran 150 (120 çelişkisi bildirildi), nominal {d['output_torque_nominal']:.0f} Nm, "
          f"Ø5 mil uyarısı, en iyi {s['label']} ({s['material']}, kapasite {s['max_output_torque']} Nm) · {el:.1f} s")


def test_small_feasible():
    out = solve(dict(motor_preset="NEMA17", ratio=25, max_od=120))
    assert out["status"] == "ok", out["diagnostics"]
    s = out["solutions"][0]
    assert s["recommended"] and s["outer_diameter"] <= 120 and s["margin"] >= 1.0
    assert s["payload"]["stages"] and abs(s["ratio"] - 25) / 25 <= 0.03
    # çözümün yükü tasarım motorunda aynen yeniden üretilebilmeli (Forma uygula akışı)
    pay = dict(s["payload"])
    pay.pop("stages")
    again = design(pay)["candidates"][0]
    assert [(x["z_sun"], x["z_planet"]) for x in again["stages"]] == [tuple(t[:2]) for t in s["teeth"]], \
        "forma uygulanınca aynı diş kombinasyonu bulunmalı"
    print(f"  [OK] NEMA17 25:1 → {s['label']}; formdan aynı kombinasyon yeniden bulunuyor")


def test_impossible_and_errors():
    out = solve(dict(motor_preset="NEMA17", ratio=2.0))
    assert out["status"] == "error" and out["diagnostics"][0]["code"] == "ratio_low"
    # stepper at a stated output speed: the ratio cannot grow, the advice is a stronger motor or a lower speed
    out = solve(dict(motor_preset="NEMA17", output_speed=10, min_output_torque=50))
    short = [x for x in out["diagnostics"] if x["code"] == "torque_short_speed"]
    assert short and "rpm" in short[0]["text"], [x["code"] for x in out["diagnostics"]]
    # DC motor: a higher ratio (lower output speed) is a valid way out
    out = solve(dict(motor_preset="MOTOR_775", ratio=30, min_output_torque=20, lang="en"))
    assert any(x["code"] == "torque_short" for x in out["diagnostics"])
    # nothing about ratio / speed: ask for it; only a torque: smallest ratio that gives it
    out = solve(dict(motor_preset="CUSTOM", motor_torque=0.5, motor_speed=300))
    assert out["status"] == "error" and out["diagnostics"][-1]["code"] == "no_ratio"
    out = solve(dict(motor_preset="NEMA17", min_output_torque=20))
    assert any(x["code"] == "ratio_from_torque" for x in out["diagnostics"]) and out["solutions"]
    assert out["solutions"][0]["output_torque"] >= 20 * 0.95, out["solutions"][0]["label"]
    print("  [OK] çok düşük oran, yetersiz motor torku (step: hız / DC: oran önerisi), eksik oran anlaşılır şekilde bildiriliyor")


def test_planets_and_hardware():
    assert max_planets(5.3) == 4 and max_planets(4.0) >= 5 and max_planets(3.2) == 6
    assert auto_tie_rod(50) == "M4" and auto_tie_rod(100) == "M6" and auto_tie_rod(140) == "M8"
    L, c = pick_tie_bolt(260.0, -9.1, -8.5, 10.0, 6.8)
    assert is_threaded_rod(L) and c == 0.0 and L >= 260, (L, c)
    L2, c2 = pick_tie_bolt(60.0, -5.4, -4.8, 4.0)
    assert not is_threaded_rod(L2)
    print("  [OK] planet sayısı sınırı, M6/M8 seçimi, uzun gövdede DIN 976 saplama")


def test_output_hub_suggestion():
    base = dict(target_ratio=25, stages_count=2, is_herringbone=True, lang="tr", motor_torque=2.0,
                output_type="ARM", out_hub="6810ZZ", arm_length=300, arm_width=100, arm_thickness=8)
    c = design(base)["candidates"][0]
    out = c["output"]
    assert out["bearing"] == "6810ZZ" and not out["strong"]
    assert out["suggest"] and out["suggest"].startswith("68") and out["suggest"] != "6810ZZ"
    res = resolve(dict(base, total_ratio=c["total_ratio"], stages=c["stages"]))
    txt = " ".join(res["warnings"])
    assert out["suggest"] in txt, txt
    opts = {o["code"]: o for o in out["hub_options"]}
    assert "6820ZZ" in opts and opts["6810ZZ"]["fits"]
    auto = design(dict(base, out_hub="AUTO"))["candidates"][0]
    assert auto["output"]["strong"], "otomatik göbek gereken çapı seçmeli"
    print(f"  [OK] göbek önerisi: Ø50 zayıf → {out['suggest']}; otomatik seçim {auto['output']['bearing']}")


def test_gate_strongest():
    """Kullanıcının bahçe kapısı: NEMA17, 180°/30 s, alan Ø250 × 280 (motor dahil), PETG, 608ZZ, K1 Max, 29 cm kol."""
    t = time.time()
    out = solve(dict(motor_preset="NEMA17", motor_shaft_dia=5, motor_shaft_type="D_CUT", output_speed=1.0,
                     max_od=250, max_length=280, gear_material="PETG", planet_bearing="608ZZ",
                     printer="Creality K1 Max", output_type="ARM", arm_shape="FLAT", arm_length=290,
                     prefer="strong", lang="tr"))
    codes = [x["code"] for x in out["diagnostics"]]
    for code in ("printer", "motor_len", "stepper", "strong_ratio", "arm_auto_flat", "arm_tip"):
        assert code in codes, (code, codes)
    assert "ratio_conflict" not in codes, "step motorda oran/devir çelişkisi olmaz"
    s = out["solutions"][0]
    assert s["recommended"] and s["ratio"] >= 150, s["label"]
    assert s["output_torque"] >= 50 and abs(s["output_speed"] - 1.0) < 0.05, s["output_speed"]
    assert s["outer_diameter"] <= 250 and s["overall_length"] <= 240 + 1e-6, s["label"]
    assert s["planet_bearings"] == ["608ZZ"] and s["bed_ok"]
    assert out["derived"]["printer_bed"] == [300, 300, 300]
    pay = s["payload"]
    assert pay["arm_width"] >= 40 and pay["arm_thickness"] >= 8, (pay["arm_width"], pay["arm_thickness"])
    print(f"  [OK] kapı (en güçlü): {s['label']} · {s['output_torque']} Nm @ 1 rpm (motor "
          f"{out['derived']['motor_speed_run']} rpm), kol {pay['arm_width']:g}×{pay['arm_thickness']:g} · "
          f"{time.time() - t:.1f} s")


def test_gate_with_load():
    """
    Aynı kapı, bu kez yükle: 'kol ucunda en fazla 10 kg' → 28.4 Nm, step motor rezerviyle ≥ 42.7 Nm aranır;
    önerilen tasarımın yük kontrolü uygun çıkar ve forma uygulanınca aynı karar görünür.
    """
    t = time.time()
    out = solve(dict(motor_preset="NEMA17", motor_shaft_dia=5, motor_shaft_type="D_CUT", output_speed=1.0,
                     max_od=250, max_length=280, gear_material="PETG", planet_bearing="608ZZ",
                     printer="Creality K1 Max", output_type="ARM", arm_shape="FLAT", arm_length=290,
                     load_value=10, load_unit="KG", lang="tr"))
    codes = [x["code"] for x in out["diagnostics"]]
    assert "load" in codes and "arm_tip" not in codes, codes
    s = out["solutions"][0]
    assert s["recommended"] and s["output_torque"] >= 10 * 9.80665 * 0.29 * 1.5 * 0.99, s["label"]
    assert s["load_check"] and s["load_check"]["status"] == "ok", s["load_check"]
    pay = dict(s["payload"])
    assert pay["load_value"] == 10 and pay["load_unit"] == "KG"
    pay.pop("stages")
    again = design(pay)["candidates"][0]
    assert again["load"]["status"] == "ok", again["load"]
    # a load without its lever arm (flange output) cannot be turned into a torque: said plainly
    out = solve(dict(motor_preset="NEMA17", ratio=25, output_type="FLANGE", load_value=5, load_unit="KG"))
    assert any(x["code"] == "load_no_radius" for x in out["diagnostics"])
    print(f"  [OK] kapı + 10 kg yük: {s['label']} · {s['output_torque']} Nm ≥ 42.7 Nm · {s['load_check']['short']} "
          f"· {time.time() - t:.1f} s")


def test_gate_rotating_housing():
    """
    Kapı, dönen gövdeyle: kol tamburun kapağına vidalı (DRUM_ARM), 10 kg yük; çözüm dönen gövde düzeninde,
    yük kontrolü uygun. Vinç tamburunda yükün kuvvet kolu bulunan tamburun halat yarıçapından alınır.
    """
    t = time.time()
    out = solve(dict(motor_preset="NEMA17", motor_shaft_dia=5, motor_shaft_type="D_CUT", output_speed=1.0,
                     max_od=250, max_length=280, gear_material="PETG", printer="Creality K1 Max",
                     arrangement="RING", output_type="ARM", arm_shape="FLAT", arm_length=290,
                     load_value=10, load_unit="KG", lang="tr"))
    codes = [x["code"] for x in out["diagnostics"]]
    assert "ring" in codes and "load" in codes, codes
    s = out["solutions"][0]
    pay = s["payload"]
    assert pay["arrangement"] == "RING" and pay["output_type"] == "DRUM_ARM", (pay["arrangement"], pay["output_type"])
    assert s["recommended"] and s["load_check"]["status"] in ("ok", "low"), (s["label"], s["load_check"])
    assert pay["stages"][-1]["star"], pay["stages"][-1]
    w = solve(dict(motor_preset="NEMA17", ratio=30, output_type="DRUM_WINCH", arrangement="RING",
                   load_value=5, load_unit="KG", gear_material="PLA", lang="tr"))
    codes = [x["code"] for x in w["diagnostics"]]
    ws = w["solutions"][0]
    assert "winch_radius" in codes and ws["output"]["load_r"] > 0, (codes, ws["output"])
    assert abs(ws["load_check"]["need"] - 5 * 9.80665 * ws["output"]["load_r"] / 1000.0) < 0.05, ws["load_check"]
    print(f"  [OK] kapı dönen gövdeyle: {s['label']} · {s['load_check']['short']}; vinç 5 kg → kuvvet kolu "
          f"{ws['output']['load_r']:.0f} mm · {time.time() - t:.1f} s")


def test_printers():
    from core.requirements import printer_bed
    assert printer_bed("Creality K1 Max")[1] == (300, 300, 300)
    assert printer_bed("k1 max")[1] == (300, 300, 300)
    assert printer_bed("Creality K1C")[1] == (220, 220, 250)
    assert printer_bed("Bambu Lab P1S")[1] == (256, 256, 256)
    assert printer_bed("bilinmeyen yazıcı") is None
    print("  [OK] yazıcı adından tabla ölçüsü (K1 Max 300³, K1C, P1S)")


def test_length_limit():
    r = design(dict(target_ratio=25, stages_count=2, max_length=40))
    assert r["candidates"] and all(not c["feasible"] and "length" in c["issues"] for c in r["candidates"])
    ok = design(dict(target_ratio=25, stages_count=2, max_length=200))["candidates"][0]
    assert ok["length_ok"] and ok["overall_length"] <= 200
    print("  [OK] boy sınırı adaylara uygulanıyor")


def test_apply_pinned():
    """
    'Uygula': önerinin diş kombinasyonu form aramasında listelenmese de (süre / sıralama) motor onu
    pin_stages ile aynen ilk aday olarak döndürür (aynı etiket ve emniyet).
    """
    out = solve(dict(motor_preset="MOTOR_540_550", lang="en", prefer="strong", ratio=200, printer="Ender 3",
                     output_type="SHAFT_PRINTED"))
    best = out["solutions"][0]
    pay = dict(best["payload"])
    stages = pay.pop("stages")
    pay.pop("total_ratio")
    pin = [{k: st[k] for k in ("z_sun", "z_planet", "z_ring", "num_planets")} for st in stages]
    first = design(dict(pay, pin_stages=pin, pin_module=pay["module"]))["candidates"][0]
    assert [(x["z_sun"], x["z_planet"]) for x in first["stages"]] == [tuple(t[:2]) for t in best["teeth"]]
    assert first["label"] == best["label"], (first["label"], best["label"])
    print(f"  [OK] öneri forma aynen uygulanıyor (sabitlenmiş aday): {first['label']}")


def test_high_ratio_stages():
    """Çok yüksek oran: çözücü 4-5 kademe seçer; 5 kademenin pratik sınırının üstü anlaşılır hata."""
    t = time.time()
    out = solve(dict(motor_preset="NEMA17", motor_torque=0.02, ratio=2000, gear_material="PLA", output_type="FLANGE",
                     lang="tr"))
    s = out["solutions"][0]
    assert s["recommended"] and s["stages"] >= 4 and len(s["payload"]["stages"]) == s["stages"], s["label"]
    assert out["derived"]["stages"] == s["stages"], out["derived"]
    assert any("kademe:" in w and "toplam verim" in w for w in s["warnings"]), s["warnings"]
    bad = solve(dict(motor_preset="NEMA17", ratio=70000, lang="tr"))
    assert bad["status"] == "error" and any(d["code"] == "ratio_high" and "5 kademe" in d["text"]
                                            for d in bad["diagnostics"]), bad["diagnostics"]
    print(f"  [OK] 2000:1 → {s['stages']} kademe: {s['label']}; 70000:1 sınır dışı · {time.time() - t:.1f} s")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("GEREKSİNİM ÇÖZÜCÜ TESTLERİ")
    t0 = time.time()
    test_planets_and_hardware()
    test_printers()
    test_gate_strongest()
    test_gate_with_load()
    test_gate_rotating_housing()
    test_length_limit()
    test_output_hub_suggestion()
    test_impossible_and_errors()
    test_small_feasible()
    test_user_example()
    test_apply_pinned()
    test_high_ratio_stages()
    print(f"TÜM ÇÖZÜCÜ TESTLERİ GEÇTİ ({time.time() - t0:.0f} s)")
