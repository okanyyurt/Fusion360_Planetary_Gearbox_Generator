# -*- coding: utf-8 -*-
"""
Bağımsız (OpenCascade) tasarım ve CAD motoru testleri.

  py -3.14 tests/test_standalone.py          (pytest gerekmez; pytest ile de çalışır)

Kontroller:
  * tasarım motoru: rulman sığdırma, maksimum çap sınırı, dayanım hedefi, hız
  * her parça tek ve geçerli katı; planetler güneş ve çember dişliye girmiyor (faz + helis + uç düzeltmesi)
  * seçili yapılandırmalarda tüm parça çiftleri arasında çakışma yok (rulman, pim, cıvata dahil)
  * STEP / STL / rapor Türkçe karakterli klasöre yazılabiliyor
"""
from __future__ import annotations

import math
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.design import design, resolve  # noqa: E402
from core.gear_geometry import stage_geometry  # noqa: E402
from occ_cad import assembly, export, report  # noqa: E402
from occ_cad import kernel as K  # noqa: E402
from occ_cad import parts as B  # noqa: E402

BASE = dict(target_ratio=25, stages_count=2, num_planets=3, motor_preset="NEMA17", motor_shaft_dia=5.0,
            motor_shaft_type="D_CUT", is_herringbone=False, helix_angle=20, face_width=12, pressure_angle=20,
            backlash=0.2, bearing_tolerance=0.08, gear_material="PLA", struct_material="PLA",
            mfg_preset="FDM_3D", carrier_type="CAGE", pin_type="STEEL", output_type="FLANGE", target_sf=1.4,
            sizing_mode="AUTO", bearing_type="AUTO", carrier_thick=4.0, wall_thickness=3.0,
            generate_housing=True, lang="tr")


def payload(**kw):
    p = dict(BASE, **kw)
    res = design(p)
    assert res["candidates"], f"aday bulunamadı: {kw}"
    c = res["candidates"][0]
    p.update(total_ratio=c["total_ratio"], stages=c["stages"])
    return p, c


def _placed(part, i):
    return K.transform(part.shape, part.placements[i]) if part.placements else part.shape


def _overlap(a, b) -> bool:
    ba, bb = K.bounding_box(a), K.bounding_box(b)
    return not (ba[0] > bb[3] or bb[0] > ba[3] or ba[1] > bb[4] or bb[1] > ba[4] or ba[2] > bb[5] or bb[2] > ba[5])


def check_solids(res):
    for p in res.parts:
        assert K.is_valid(p.shape), f"{p.key}: geçersiz katı"
        assert K.solid_count(p.shape) == 1, f"{p.key}: {K.solid_count(p.shape)} katı"
        assert K.volume(p.shape) > 0.0, f"{p.key}: hacim sıfır"


def check_mesh(res):
    """Her kademede bir planet: güneş ve çember dişliyle (dönen gövdede tamburla) kesişim hacmi sıfır."""
    by_key = {p.key: p for p in res.parts}
    rings = [p.shape for p in res.parts if p.key.startswith("ring_housing") or p.key in ("drum", "drum_s1", "drum_s2")]
    for s in range(1, res.summary["stages"] + 1):
        # later suns are printed with the previous carrier (cage top plate or single plate)
        sun = by_key.get(f"sun_s{s}") or by_key.get(f"carrier_top_s{s - 1}") or by_key[f"carrier_s{s - 1}"]
        pl = _placed(by_key[f"planet_s{s}"], 0)
        v_sun = K.volume(K.common(sun.shape, pl))
        v_ring = sum(K.volume(K.common(r, pl)) for r in rings if _overlap(r, pl))
        assert v_sun < 1e-3, f"kademe {s}: planet güneşe giriyor ({v_sun:.4f} mm³)"
        assert v_ring < 1e-3, f"kademe {s}: planet çember dişliye giriyor ({v_ring:.4f} mm³)"


def check_clashes(res):
    """Tüm parça örnekleri arasında hacimsel çakışma yok (temas serbest)."""
    inst = [(f"{p.key}#{i + 1}", _placed(p, i)) for p in res.parts for i in range(p.quantity)]
    clashes = []
    for i in range(len(inst)):
        for j in range(i + 1, len(inst)):
            if not _overlap(inst[i][1], inst[j][1]):
                continue
            c = K.common(inst[i][1], inst[j][1])
            v = K.volume(c) if c is not None else 0.0
            if v > 0.01:
                clashes.append((inst[i][0], inst[j][0], round(v, 3)))
    assert not clashes, f"çakışmalar: {clashes}"


def test_geometry_interference_free():
    for zs, zp, zr in [(12, 18, 48), (12, 27, 66), (15, 21, 57), (24, 24, 72)]:
        g = stage_geometry(zs, zp, zr, 1.0, 20.0, 0.2)
        assert g.interference_free, (zs, zp, zr)
        assert g.eps_sun_planet > 1.2 and g.eps_planet_ring > 1.2
    print("  [OK] uç düzeltmeleri ile evolvent girişimi yok, temas oranı > 1.2")


def test_tooth_depth_geometry():
    """
    Diş yüksekliği katsayısı h*a: kısa dişte kavrama oranı düşer, kök güçlenir; uzun dişte kavrama artar, kök
    zayıflar, uçlar incelir. Standart (1.0) eski geometriyle birebir aynı (düzeltme faktörü 1).
    """
    from core.gear_geometry import depth_strength_factors
    for zs, zp, zr in [(12, 18, 48), (15, 30, 75), (13, 41, 95)]:
        std = stage_geometry(zs, zp, zr, 1.0, 20.0, 0.2)
        assert std.addendum == 1.0 and depth_strength_factors(std) == {"sun": 1.0, "planet": 1.0, "ring": 1.0}
        assert abs(std.root_sun - (std.r_sun - 1.157)) < 1e-9 and abs(std.root_ring - (std.r_ring + 1.25)) < 1e-9
        stub = stage_geometry(zs, zp, zr, 1.0, 20.0, 0.2, addendum=0.8)
        long_ = stage_geometry(zs, zp, zr, 1.0, 20.0, 0.2, addendum=1.25)
        for g in (stub, long_):
            assert g.interference_free, (zs, zp, zr, g.addendum)
        assert stub.eps_sun_planet < std.eps_sun_planet < long_.eps_sun_planet + 1e-9
        assert abs(stub.root_sun - (stub.r_sun - 0.957)) < 1e-9 and abs(long_.root_ring - (long_.r_ring + 1.5)) < 1e-9
        f_stub, f_long = depth_strength_factors(stub), depth_strength_factors(long_)
        assert f_stub["sun"] > 1.05 and f_long["sun"] < 0.95, (f_stub, f_long)
        assert long_.tip_land_sun < std.tip_land_sun < stub.tip_land_sun
    # out-of-range values are clamped (form input / AI payload)
    assert stage_geometry(12, 18, 48, 1.0, 20.0, 0.2, addendum=5).addendum == 1.3
    print("  [OK] diş yüksekliği: kısa diş (0.8) kök ↑ kavrama ↓, uzun diş (1.25) kavrama ↑ kök ↓ uç ↓, 1.0 değişmedi")


def test_tooth_depth_cad():
    """Kısa ve uzun dişli redüktörler geçerli katı, dişler birbirine girmiyor, uyarı ve rapor katsayıyı gösteriyor."""
    for ha, herring, clash in ((0.8, False, True), (1.25, True, False)):
        t = time.time()
        p, c = payload(addendum_coef=ha, is_herringbone=herring)
        assert all(s["addendum"] == ha for s in c["stages"]), c["stages"]
        res = assembly.generate(p)
        check_solids(res)
        check_mesh(res)
        if clash:
            check_clashes(res)
        assert res.summary["addendum"] == ha and res.design["params"]["addendum"] == ha
        geo = res.design["stages"][0]["geometry"]
        m = geo["module"]
        assert abs(geo["root_sun"] - (geo["r_sun"] - (ha + 0.157 - geo["x_sun"]) * m)) < 1e-9   # incl. profile shift
        if ha > 1.0:
            assert any("h*a" in w for w in res.warnings), res.warnings      # topped / thin tips are reported
        tmp = tempfile.mkdtemp(prefix="pgb_depth_")
        try:
            path = report.write_html_report(res, os.path.join(tmp, "r.html"), "tr")
            txt = open(path, encoding="utf-8").read()
            assert "Diş yüksekliği h*a" in txt and f"{ha:.2f}" in txt
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print(f"  [OK] h*a {ha:.2f} ({'balıksırtı' if herring else 'düz'}): {res.summary['part_count']} parça, "
              f"dişler girişimsiz{', çakışma yok' if clash else ''}, {len(res.warnings)} uyarı · {time.time() - t:.1f} s")


def test_application_load():
    """
    Uygulama yükü: kullanıcının kapı örneği (NEMA17, 45:1, 29 cm kol, 10 kg) uygun değil — neden ve seçenekler
    yazılır; 4 kg sınırda, 8 Nm uygun; kuvvet kolu olmadan kontrol yapılamadığı söylenir; eski arm_load çalışır.
    """
    gate = dict(target_ratio=45, stages_count=2, motor_torque=0.4, motor_speed=45, gear_material="PETG",
                struct_material="PETG", output_type="ARM", arm_length=290, arm_width=40, arm_thickness=12,
                is_herringbone=True, face_width=20, bearing_type="608ZZ", max_od=250)
    _, c = payload(**gate, load_value=10, load_unit="KG")
    lv = c["load"]
    assert lv["status"] == "fail" and abs(lv["need"] - 10 * 9.80665 * 0.29) < 0.05, lv
    assert lv["have"] < lv["need"] and lv["fixes"] and "Nm" in lv["text"], lv
    assert any("129:1" in f or ":1" in f for f in lv["fixes"]), lv["fixes"]
    p, c = payload(**gate, load_value=10, load_unit="KG", lang="tr")
    assert lv["text"] in resolve(p)["warnings"], "uygun değilse uyarılara da yazılmalı"
    assert payload(**gate, load_value=4, load_unit="KG")[1]["load"]["status"] == "low"
    ok = payload(**gate, load_value=8, load_unit="NM")[1]["load"]
    assert ok["status"] == "ok" and ok["reserve"] >= 1.5, ok
    p_ok, _ = payload(**gate, load_value=8, load_unit="NM")
    assert not any(w.startswith("✓") for w in resolve(p_ok)["warnings"]), "uygunsa uyarı listesine girmez"
    inc = payload(**dict(gate, output_type="FLANGE"), load_value=10, load_unit="KG")[1]["load"]
    assert inc["status"] == "incomplete", inc
    legacy = payload(**gate, arm_load=30)[1]["load"]
    assert legacy and legacy["status"] == "ok" and abs(legacy["need"] - 30 * 0.29) < 0.01, legacy
    # side load on a printed output shaft: bending is checked, the verdict names the shaft
    sh = payload(output_type="SHAFT_PRINTED", output_shaft_dia=8, strength_required=False, load_value=200,
                 load_unit="N", load_radius=25)[1]
    names = {x["name"] for x in sh["engineering"]["stages"][-1]["checks"]}
    assert "load_shaft" in names and sh["load"]["status"] == "fail" and "Ø8" in sh["load"]["text"], sh["load"]
    en = payload(**gate, load_value=10, load_unit="KG", lang="en")[1]["load"]
    assert en["text"].startswith("✗ Not suitable"), en["text"]
    print(f"  [OK] uygulama yükü: kapı 10 kg → {lv['short']} ({lv['need']:.1f} Nm > {lv['have']:.1f} Nm), "
          f"4 kg sınırda, 8 Nm uygun, kolsuz yük → eksik bilgi, mil yan yükü, EN metin")


def test_design_engine():
    t = time.time()
    r = design(dict(BASE, bearing_type="608ZZ", is_herringbone=True))
    assert time.time() - t < 3.0
    c = r["candidates"][0]
    assert c["feasible"] and all(s["bearing"] == "608ZZ" for s in c["stages"])
    assert abs(c["total_ratio"] - 25) / 25 <= 0.03 + 1e-9
    r = design(dict(BASE, sizing_mode="MAX_OD", max_od=75))
    assert r["candidates"] and all(c["outer_diameter"] <= 75.0 + 1e-6 for c in r["candidates"])
    r = design(dict(BASE, bearing_type="608ZZ", strength_required=False, stages_count=1, target_ratio=5))
    assert r["candidates"][0]["stages"][0]["bearing"] == "608ZZ"
    r = design(dict(BASE, stages_count=3, target_ratio=100, motor_torque=0.1))
    assert r["candidates"] and len(r["candidates"][0]["stages"]) == 3
    print(f"  [OK] tasarım motoru (608ZZ otomatik büyütme, maks. çap, 3 kademe)")


CASES = [
    ("1 kademe düz, 608ZZ, sadece geometri", dict(stages_count=1, target_ratio=5, bearing_type="608ZZ",
                                                   strength_required=False), True),
    ("2 kademe düz, 4 planet, NEMA23 çift-D, çelik mil",
     dict(target_ratio=20, num_planets=4, motor_preset="NEMA23", motor_shaft_dia=6.35, motor_shaft_type="DOUBLE_D",
          motor_torque=0.3, output_type="SHAFT_STEEL"), True),
    ("1 kademe düz, 5 planet, NEMA34 kamalı, baskı pim",
     dict(stages_count=1, target_ratio=4, num_planets=5, motor_preset="NEMA34", motor_shaft_dia=14.0,
          motor_shaft_type="KEYWAY", motor_torque=0.5, pin_type="PRINTED"), False),
    ("2 kademe düz, klasik tek plaka + segman, baskı D-mil",
     dict(carrier_type="SINGLE", circlip_type="DIN_471", generate_circlips=True, output_type="SHAFT_PRINTED",
          motor_torque=0.15, strength_required=False), False),
    ("1 kademe düz, gövdesiz, 775", dict(stages_count=1, target_ratio=5, generate_housing=False,
                                         motor_preset="MOTOR_775", motor_shaft_type="ROUND", motor_torque=0.12,
                                         motor_speed=9000), False),
    ("2 kademe balıksırtı, NEMA17 (varsayılan)", dict(is_herringbone=True), False),
]


def test_cases():
    for name, kw, clash in CASES:
        t = time.time()
        p, cand = payload(**kw)
        res = assembly.generate(p)
        check_solids(res)
        check_mesh(res)
        if clash:
            check_clashes(res)
        print(f"  [OK] {name}: {res.elapsed:.1f} s üretim, {time.time() - t:.1f} s toplam, "
              f"{res.summary['part_count']} parça, Ø{res.summary['outer_diameter']} mm, "
              f"{len(res.warnings)} uyarı{' · çakışma yok' if clash else ''}")


def test_export_turkish_path():
    p, _ = payload(stages_count=1, target_ratio=5)
    res = assembly.generate(p)
    base = tempfile.mkdtemp(prefix="pgb_")
    folder = os.path.join(base, "Çıktı Şişli Güneş Dişli")
    try:
        step = export.write_step(res, os.path.join(folder, "Redüktör_Ğüşiöç.step"))
        with open(step, "r", encoding="ascii", errors="strict") as fh:
            assert "ISO-10303-21" in fh.read(4000)
        stls = export.write_stls(res, os.path.join(folder, "STL"))
        assert len(stls) == sum(1 for pt in res.parts if pt.printable)
        rep = report.write_html_report(res, os.path.join(folder, "Mühendislik_Raporu.html"))
        with open(rep, encoding="utf-8") as fh:
            html_txt = fh.read()
        assert "Diş dibi eğilme" in html_txt and "ISO 4762" in html_txt
        mesh = export.mesh_payload(res, "fast")
        assert len(mesh["instances"]) == res.summary["part_count"]
        print(f"  [OK] Türkçe yola STEP ({os.path.getsize(step) // 1024} KB) + {len(stls)} STL + HTML rapor + mesh")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_api_export_all():
    os.environ["PLANETARY_GEARBOX_HOME"] = tempfile.mkdtemp(prefix="pgb_home_ş_")
    from standalone.api import Api
    api = Api()
    api._settings["export_dir"] = os.path.join(os.environ["PLANETARY_GEARBOX_HOME"], "Dışa Aktarım")
    d = api.design(dict(BASE, stages_count=1, target_ratio=5))
    assert d["success"] and d["candidates"]
    p = dict(BASE, stages_count=1, total_ratio=d["candidates"][0]["total_ratio"], stages=d["candidates"][0]["stages"])
    out = api.generate(p)
    assert out["success"], out
    assert api.get_mesh("fast")["success"]
    exp = api.export_all()
    assert exp["success"], exp
    with open(exp["bom"], "r", encoding="utf-8-sig") as fh:
        bom = fh.read()
    assert "ISO 4762" in bom and "ISO 8734" in bom
    assert os.path.isfile(exp["report"]) and os.path.isfile(exp["three_mf"]), exp
    print(f"  [OK] Api.design + generate + export_all -> {exp['folder']}")
    shutil.rmtree(os.environ["PLANETARY_GEARBOX_HOME"], ignore_errors=True)


def test_fusion_bridge():
    """Fusion eklentisinin yolu: tasarım süreç içinde, geometri ayrı süreçteki motorda, STEP içe aktarılır."""
    home = tempfile.mkdtemp(prefix="pgb_fusion_ş_")
    os.environ["PLANETARY_GEARBOX_HOME"] = home
    from standalone.fusion_api import FusionApi
    imported, progress = [], []
    api = FusionApi(push=progress.append, pump=lambda: None, importer=lambda step, name, res: imported.append((step, res)) or {"ok": True})
    api._settings["export_dir"] = os.path.join(home, "Fusion Çıktı")
    d = api.design(dict(BASE, stages_count=1, target_ratio=5))
    c = d["candidates"][0]
    out = api.generate(dict(BASE, stages_count=1, total_ratio=c["total_ratio"], stages=c["stages"]))
    assert out["success"], out
    assert imported and os.path.isfile(imported[0][0]) and out["stl_count"] > 0
    kin = imported[0][1]["kinematics"]
    assert kin["items"] and {"ground", "input", "carrier1"} <= set(kin["bodies"])
    assert out["kinematics"]["ok"] and out["kinematics"]["output_factor"] > 0
    assert any(m.get("percent") == 100 or m.get("event") == "done" for m in progress)
    # rotating housing through the same bridge: the drum is the output (opposite direction), the planets of the
    # fixed carrier turn against ground (the add-in joins them to the grounded parts)
    ring = dict(BASE, stages_count=1, target_ratio=5, arrangement="RING", output_type="DRUM_FLANGE")
    c = api.design(ring)["candidates"][0]
    imported.clear()
    out = api.generate(dict(ring, total_ratio=c["total_ratio"], stages=c["stages"]))
    assert out["success"], out
    kin = imported[0][1]["kinematics"]
    assert kin["output"] == "drum" and out["kinematics"]["output_factor"] < 0, (kin["output"], out["kinematics"])
    assert all(b["carrier"] == "ground" for b in kin["bodies"].values() if b.get("type") == "planet")
    assert any(it["body"] == "drum" for it in kin["items"]) and any(it["name"] == "Fixed_Base_Plate" for it in kin["items"])
    print(f"  [OK] Fusion köprüsü: ayrı süreçte motor + STEP içe aktarma ({len(progress)} ilerleme mesajı)")
    shutil.rmtree(home, ignore_errors=True)


def test_kinematics_rotated():
    """Giriş döndürüldüğünde (kinematik model) dişliler hâlâ birbirine girmiyor; çıkış oranı doğru."""
    p, _ = payload(stages_count=1, target_ratio=5, is_herringbone=True)
    res = assembly.generate(p)
    kin = res.kinematics
    by_key = {pt.key: pt for pt in res.parts}
    ring = by_key["ring_housing_s1"]
    for deg in (17.0, 133.0):
        th = math.radians(deg)
        sun = assembly.placed_at(by_key["sun_s1"], 0, kin, th)
        for i in range(by_key["planet_s1"].quantity):
            pl = assembly.placed_at(by_key["planet_s1"], i, kin, th)
            v = K.volume(K.common(sun, pl)) + K.volume(K.common(assembly.placed_at(ring, 0, kin, th), pl))
            assert v < 1e-3, f"{deg}°: planet {i + 1} kesişim {v:.4f}"
    out = kin["bodies"][kin["output"]]["factor"]
    assert abs(1.0 / out - res.summary["total_ratio"]) < 1e-3
    print(f"  [OK] kinematik: 17° / 133° girişte kesişim yok, çıkış oranı 1/{1 / out:.3f}")


def test_output_arm():
    """Çıkış kolu: geçerli tek katı, döndürülünce sabit parçalara değmiyor, hesaplar raporda."""
    for kw in (dict(arm_shape="FLAT", arm_length=300, arm_width=100, arm_thickness=8, arm_load=20),
               dict(arm_shape="ROUND", arm_length=120, arm_width=14, arm_load=10, stages_count=1, target_ratio=5)):
        p, c = payload(output_type="ARM", **kw)
        names = [x["name"] for x in c["engineering"]["stages"][-1]["checks"]]
        assert {"arm_bending", "arm_key", "load_drive", "load_capacity", "load_bearing"} <= set(names), names
        assert c["load"] and c["load"]["status"] in ("ok", "low", "fail"), c.get("load")
        res = assembly.generate(p)
        check_solids(res)
        check_clashes(res)
        kin = res.kinematics
        by_key = {pt.key: pt for pt in res.parts}
        assert by_key["output_arm"].bodies == [kin["output"]]
        fixed = [assembly.placed_at(pt, i, kin, 0.0) for pt in res.parts for i in range(pt.quantity)
                 if pt.bodies[i] == "ground"]
        for deg in (60.0, 200.0, 315.0):
            th = math.radians(deg) / kin["bodies"][kin["output"]]["factor"]     # kol bu açıya döner
            arm = assembly.placed_at(by_key["output_arm"], 0, kin, th)
            for f in fixed:
                if _overlap(arm, f):
                    assert K.volume(K.common(arm, f)) < 1e-3, f"kol {deg}°'de sabit parçaya değiyor"
    # elle seçilen büyük göbek kapağa sığıyor ve kullanılıyor
    p, c = payload(output_type="ARM", out_hub="6808ZZ")
    assert c["output"]["bearing"] == "6808ZZ"
    print("  [OK] çıkış kolu: yassı ve yuvarlak, 60°/200°/315°'de çakışma yok, elle göbek seçimi")


def test_layout_length():
    """Tasarım motorunun hesapladığı toplam boy (core.layout) üretilen modelin gerçek boyuna eşit."""
    for kw in (dict(stages_count=1, target_ratio=5),
               dict(output_type="SHAFT_PRINTED", output_shaft_len=25),
               dict(output_type="ARM", arm_shape="ROUND", arm_width=20, arm_length=120, stages_count=1, target_ratio=5),
               dict(stages_count=1, target_ratio=5, generate_housing=False)):
        p, c = payload(**kw)
        res = assembly.generate(p)
        zmin, zmax = 1e9, -1e9
        for pt in res.parts:
            if pt.key.startswith("tie_rod"):
                continue
            for i in range(pt.quantity):
                b = K.bounding_box(assembly.placed_at(pt, i, res.kinematics, 0.0))
                zmin, zmax = min(zmin, b[2]), max(zmax, b[5])
        real = zmax - zmin
        assert abs(real - res.summary["overall_length"]) < 0.05, (kw, real, res.summary["overall_length"])
        assert abs(c["overall_length"] - res.summary["overall_length"]) < 0.05, (kw, c["overall_length"])
        if not kw.get("generate_housing", True):
            assert abs(c["outer_diameter"] - res.summary["outer_diameter"]) < 0.05, (c["outer_diameter"],
                                                                                    res.summary["outer_diameter"])
    print("  [OK] toplam boy: tasarım motoru = üretilen model (flanş, baskı mil, kol, gövdesiz)")


def test_design_hints():
    """Çözümsüz ayarlar nedeniyle açıklanıyor; yüksek torkta güçlü tasarım bütçe içinde bulunuyor."""
    r = design(dict(BASE, stages_count=1, target_ratio=20))
    assert not r["candidates"] and "kademe" in r.get("hint", ""), r.get("hint")
    assert r["elapsed"] < 0.5
    r = design(dict(BASE, bearing_type="684ZZ", bearing_layout="DUAL", face_width=8))
    assert not r["candidates"] and "684ZZ" in r.get("hint", "") and "9.2" in r["hint"], r.get("hint")
    r = design(dict(BASE, sizing_mode="MAX_OD", max_od=45, lang="en"))
    assert not r["candidates"] and "Ø45" in r.get("hint", ""), r.get("hint")
    t = time.time()
    r = design(dict(BASE, target_ratio=40, motor_preset="NEMA23", motor_shaft_dia=6.35, num_planets="AUTO"))
    took = time.time() - t
    assert r["candidates"] and r["candidates"][0]["feasible"], r["candidates"][0]["label"] if r["candidates"] else r
    print(f"  [OK] çözümsüz ayar ipuçları (oran / rulman genişliği / maks. çap); NEMA23 40:1 güçlü tasarım "
          f"{took:.1f} s: {r['candidates'][0]['label']}")


def test_large_gearbox():
    """Büyük redüktör (3 kademe, M5 saplama): geçerli katılar, dişli girişimi yok, saplamalar gövdeye değmiyor."""
    from core.requirements import solve
    t = time.time()
    sol = solve(dict(motor_preset="NEMA23", ratio=100, max_od=200, gear_material="PETG", herringbone=False,
                     lang="tr"))
    s = sol["solutions"][0]
    assert s["recommended"], sol["diagnostics"]
    res = assembly.generate(s["payload"])
    check_solids(res)
    check_mesh(res)
    keys = {pt.key for pt in res.parts}
    rods = "tie_rod_top_nut" in keys          # no standard screw fits: DIN 976 rod cut to length + top nut
    if rods:
        assert "tie_rod_bolt" in keys
        assert any("DIN 976" in w for w in res.warnings), res.warnings
        from core.design import TIE_RODS
        by_key = {pt.key: pt for pt in res.parts}
        cover_top = K.bounding_box(_placed(by_key["top_cover"], 0))[5]
        rod_top = max(K.bounding_box(_placed(by_key["tie_rod_bolt"], i))[5] for i in range(by_key["tie_rod_bolt"].quantity))
        nut_m = TIE_RODS[res.summary["tie_rod"].split("x")[0]]["nut_m"]
        assert rod_top - cover_top <= nut_m + 1.5 + 5.0 + 0.1, ("saplama gereğinden uzun", rod_top - cover_top)
    fast = [(f"{p.key}#{i + 1}", _placed(p, i)) for p in res.parts for i in range(p.quantity)
            if p.key.startswith("tie_rod")]
    other = [(f"{p.key}#{i + 1}", _placed(p, i)) for p in res.parts for i in range(p.quantity)
             if p.key in ("motor_flange", "top_cover") or p.key.startswith("ring_housing")]
    for na, a in fast:
        for nb, b in other:
            if _overlap(a, b):
                v = K.volume(K.common(a, b))
                assert v < 1e-3, f"{na} ↔ {nb}: {v:.4f} mm³"
    # same box with an output arm: the arm sweeps over the rod ends / top nuts (or bolt heads) at every angle
    arm_res = assembly.generate(dict(s["payload"], output_type="ARM", arm_length=150, arm_width=30, arm_thickness=8))
    arm = next(p for p in arm_res.parts if p.key == "output_arm")
    fast = [_placed(p, i) for p in arm_res.parts for i in range(p.quantity) if p.key.startswith("tie_rod")]
    ratio = arm_res.summary["total_ratio"]
    for deg in range(0, 360, 15):
        placed = assembly.placed_at(arm, 0, arm_res.kinematics, math.radians(deg) * ratio)
        for f in fast:
            if _overlap(placed, f):
                v = K.volume(K.common(placed, f))
                assert v < 1e-3, f"kol {deg}°: bağlantı elemanına çarpıyor ({v:.3f} mm³)"
    print(f"  [OK] büyük redüktör {s['label']}: {len(res.parts)} parça, "
          f"{'DIN 976 saplama' if rods else 'cıvata'} {res.summary['tie_rod']} gövdeye değmiyor, çıkış kolu "
          f"360° boyunca saplama uçlarının üstünden geçiyor · {time.time() - t:.0f} s")


def _plate_outer_radii(shape):
    """Radii of the OUTER boundary of the largest flat (±Z) face of a plate: a full disk gives one value."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    best, best_area = None, 0.0
    for f in K.faces(shape):
        srf = BRepAdaptor_Surface(f)
        if srf.GetType() != GeomAbs_Plane or abs(abs(srf.Plane().Axis().Direction().Z()) - 1.0) > 1e-6:
            continue
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(f, props)
        if props.Mass() > best_area:
            best, best_area = f, props.Mass()
    radii = []
    ex = TopExp_Explorer(BRepTools.OuterWire_s(best), TopAbs_EDGE)
    while ex.More():
        c = BRepAdaptor_Curve(TopoDS.Edge(ex.Current()))
        a, b = c.FirstParameter(), c.LastParameter()
        for k in range(13):
            q = c.Value(a + (b - a) * k / 12)
            radii.append(math.hypot(q.X(), q.Y()))
        ex.Next()
    return radii


def test_carrier_plates():
    """Taşıyıcı plakalar tam disk: kol birleşimlerinde çentik / sivri iç köşe yok; hafifletme deliklerinde ≥3 mm et."""
    for kw in (dict(carrier_type="SINGLE", pin_type="PRINTED", stages_count=2, target_ratio=25),
               dict(carrier_type="CAGE", stages_count=2, target_ratio=25),
               # 6 planets on a large plate: lightening holes must leave spokes (they once merged into a ring
               # and cut the hub off the plate)
               dict(carrier_type="CAGE", pin_type="PRINTED", stages_count=3, target_ratio=52.6, face_width=8,
                    num_planets="AUTO", bearing_layout="DUAL", gear_material="PACF", struct_material="PACF",
                    output_type="SHAFT_STEEL", sizing_mode="MAX_OD", max_od=200, bearing_tolerance=0.15)):
        p, c = payload(**kw)
        res = assembly.generate(p)
        check_solids(res)
        for pt in res.parts:
            if not (pt.key.startswith("carrier_s") or pt.key.startswith("carrier_top") or
                    pt.key.startswith("carrier_bottom")):
                continue
            radii = _plate_outer_radii(pt.shape)
            spread = (max(radii) - min(radii)) / max(radii)
            assert spread < 0.005, f"{pt.key}: plaka dış hattı daire değil (sapma %{spread * 100:.1f})"
    print("  [OK] taşıyıcı plakalar tam disk (tek plaka + kafes, 6 planet): çentik / kopuk göbek yok")


def test_planets_auto():
    """Planet sayısı otomatik: her kademede sığan en çok planet; sığmayan sabit sayıda açıklayıcı ipucu."""
    a = design(dict(BASE, num_planets="AUTO", target_ratio=25, stages_count=2))["candidates"][0]
    n3 = design(dict(BASE, num_planets=3, target_ratio=25, stages_count=2))["candidates"][0]
    assert max(s["num_planets"] for s in a["stages"]) > 3, a["label"]
    assert a["outer_diameter"] <= n3["outer_diameter"] + 1e-6, (a["label"], n3["label"])
    r = design(dict(BASE, num_planets=5, target_ratio=45, stages_count=2))
    assert r.get("hint") and "5 planet" in r["hint"], r.get("hint")
    p, c = payload(num_planets="AUTO", target_ratio=25, stages_count=2)
    res = assembly.generate(p)
    check_solids(res)
    check_mesh(res)
    counts = [pt.quantity for pt in res.parts if pt.key.startswith("planet_s")]
    assert counts == [s["num_planets"] for s in c["stages"]], (counts, c["label"])
    print(f"  [OK] otomatik planet: {a['label']} (3 planetle Ø{n3['outer_diameter']}); 45:1/2k'da 5 planet için ipucu")


def test_hub_nuts():
    """Çıkış flanşı ve kol göbeği: yandan takılan M3 somun yuvaları, somun katmanı burulma kontrolü, BOM."""
    for kw in (dict(output_type="FLANGE", stages_count=1, target_ratio=5),
               dict(output_type="ARM", arm_length=150, arm_width=30, arm_thickness=8, stages_count=1, target_ratio=5)):
        p, c = payload(**kw)
        names = [x["name"] for x in c["engineering"]["stages"][-1]["checks"]]
        assert "hub_nut_layer" in names, names
        res = assembly.generate(p)
        check_solids(res)
        check_clashes(res)
        pu = report.bill_of_materials(res, "tr")[1]
        nuts = [x for x in pu if "çıkış göbeği" in x["label"]]
        assert nuts and nuts[0]["qty"] == res.design["hardware"]["hub_screw_count"], pu
        assert not any("burç" in x["label"].lower() for x in pu)
    print("  [OK] çıkış göbeği somun yuvaları: flanş ve kol, somun katmanı kontrolü, BOM'da somunlar")


def test_hub_nut_parts():
    """
    Büyük somun yuvalı göbek (6810ZZ / 6820ZZ, 2 ve 4 somun): yuva kesimi parça koparmıyor (her parça tek katı),
    yuvalarda somun var, somunlar göbeğe / başka parçaya girmiyor, kol vidası somunu geçiyor.
    """
    cases = (dict(carrier_type="SINGLE", pin_type="PRINTED", out_hub="6810ZZ", output_type="ARM", arm_length=200),
             dict(carrier_type="CAGE", out_hub="6810ZZ", output_type="ARM", arm_length=200),
             dict(carrier_type="SINGLE", pin_type="PRINTED", out_hub="6810ZZ", output_type="FLANGE"),
             dict(carrier_type="CAGE", out_hub="6820ZZ", output_type="FLANGE"))
    for kw in cases:
        p, c = payload(is_herringbone=True, **kw)
        res = assembly.generate(p)
        check_solids(res)
        by_key = {pt.key: pt for pt in res.parts}
        nut = by_key.get("hub_nut")
        assert nut and nut.quantity == res.design["hardware"]["hub_screw_count"] > 1, (kw, nut)
        assert set(nut.bodies) == {f"carrier{res.summary['stages']}"}, nut.bodies
        others = [(f"{pt.key}#{i + 1}", _placed(pt, i)) for pt in res.parts if pt.key != "hub_nut"
                  for i in range(pt.quantity)]
        r_hub = res.design["output"]["hub_d"] / 2.0
        for i in range(nut.quantity):
            shp = _placed(nut, i)
            x0, y0, z0, x1, y1, z1 = K.bounding_box(shp)
            assert math.hypot((x0 + x1) / 2.0, (y0 + y1) / 2.0) < r_hub, f"{kw}: somun #{i + 1} göbek dışında"
            for name, other in others:
                if _overlap(shp, other):
                    cm = K.common(shp, other)
                    v = K.volume(cm) if cm is not None else 0.0
                    assert v < 0.01, f"{kw}: somun #{i + 1} ↔ {name} çakışıyor ({v:.3f} mm³)"
        if kw["output_type"] == "ARM":
            scr = by_key["arm_screw"]
            nut_z0 = min(K.bounding_box(_placed(nut, i))[2] for i in range(nut.quantity))
            tip = max(K.bounding_box(_placed(scr, i))[2] for i in range(scr.quantity))
            assert tip < nut_z0 - 0.3, f"{kw}: kol vidası somunu geçmiyor (uç {tip:.2f}, somun {nut_z0:.2f})"
    print("  [OK] somun yuvalı büyük göbekler: tek katı parçalar, yuvalarda somun, çakışma yok")


def check_turning(res, degs=(23.0, 211.0), pair=None):
    """
    Döndürülmüş girişte farklı gövdelere ait parçalar (dişliler, tambur ↔ sabit parçalar) birbirine girmiyor.
    `pair(key_a, key_b)`: yalnızca bu çiftler (balıksırtı helis yüzeyleri arasındaki boolean çok yavaş).
    """
    kin = res.kinematics
    names = [(p, i) for p in res.parts for i in range(p.quantity)]
    body = [p.bodies[i] if p.bodies else "ground" for p, i in names]
    for deg in degs:
        th = math.radians(deg)
        inst = [(f"{p.key}#{i + 1}", assembly.placed_at(p, i, kin, th)) for p, i in names]
        for a in range(len(inst)):
            for b in range(a + 1, len(inst)):
                if body[a] == body[b] or not _overlap(inst[a][1], inst[b][1]):
                    continue
                if pair and not pair(names[a][0].key, names[b][0].key):
                    continue
                c = K.common(inst[a][1], inst[b][1])
                v = K.volume(c) if c is not None else 0.0
                assert v < 0.01, f"{deg}°: {inst[a][0]} ↔ {inst[b][0]} {v:.3f} mm³"


def test_rotating_housing():
    """
    Dönen gövde (çember çıkışı): son kademe yıldız (taşıyıcı sabit, i = Zr/Zs, ters yön). Tek ve geçerli katılar,
    dişliler / tambur girişimsiz, 0°'de çakışma yok, döndürünce tambur ve kol sabit parçalara değmiyor; boy ve
    oran model ile aynı; tambur rulmanı BOM'da; yük kolu: tambur kolunda kol boyu, vinçte halat yarıçapı.
    """
    cases = (("1 kademe, tambur flanşı", dict(stages_count=1, target_ratio=5, output_type="DRUM_FLANGE")),
             ("2 kademe, tambur kolu + 6 kg", dict(output_type="DRUM_ARM", arm_length=150, arm_width=30,
                                                   arm_thickness=8, load_value=6, load_unit="KG")),
             ("2 kademe balıksırtı vinç + 5 kg", dict(output_type="DRUM_WINCH", is_herringbone=True, target_ratio=30,
                                                      load_value=5, load_unit="KG", rope_dia=4)))
    for name, kw in cases:
        t = time.time()
        p, c = payload(arrangement="RING", **kw)
        st = c["stages"]
        assert st[-1]["star"] and abs(st[-1]["ratio"] - st[-1]["z_ring"] / st[-1]["z_sun"]) < 1e-3, st[-1]
        assert c["output"]["drum"] and c["output"]["bearing"] == st[-1]["drum_bearing"], c["output"]
        e = c["engineering"]
        assert e["star"] and e["stages"][-1]["carrier_speed"] == 0.0 and e["stages"][-1]["ring_speed"] > 0
        if kw.get("load_value"):
            lv = c["load"]
            lever = kw.get("arm_length") or c["output"]["load_r"]
            assert lv and abs(lv["need"] - kw["load_value"] * 9.80665 * lever / 1000.0) < 0.05, (lv, lever)
        res = assembly.generate(p)
        check_solids(res)
        check_mesh(res)
        if kw.get("is_herringbone"):
            # helical lofts make every boolean slow: the meshes are checked above; turning, the drum (and its
            # screws / nuts) must clear the fixed parts that are not gears
            fixed = ("ring_base", "carrier_top", "pin_s", "drum_bearing", "tie_rod", "motor_flange")
            moving = ("drum", "join_", "hub_nut", "output_arm", "arm_screw")
            check_turning(res, (211.0,), lambda a, b: (a.startswith(moving) and b.startswith(fixed)) or
                          (b.startswith(moving) and a.startswith(fixed)))
        else:
            check_clashes(res)
            check_turning(res)
        kin = res.kinematics
        f = kin["bodies"][kin["output"]]["factor"]
        assert kin["output"] == "drum" and f < 0 and abs(1.0 / abs(f) - res.summary["total_ratio"]) < 1e-3, f
        keys = {pt.key for pt in res.parts}
        assert {"ring_base", "drum_bearing"} <= keys and ("drum" in keys or "drum_s2" in keys), keys
        assert not any(k == "top_cover" or k == "output_bearing" for k in keys), keys
        zmin, zmax = 1e9, -1e9
        for pt in res.parts:
            if pt.key.startswith("tie_rod"):
                continue
            for i in range(pt.quantity):
                b = K.bounding_box(assembly.placed_at(pt, i, kin, 0.0))
                zmin, zmax = min(zmin, b[2]), max(zmax, b[5])
        assert abs((zmax - zmin) - res.summary["overall_length"]) < 0.05, (zmax - zmin, res.summary["overall_length"])
        pu = report.bill_of_materials(res, "tr")[1]
        assert any(st[-1]["drum_bearing"] in x["spec"] for x in pu), pu
        steps = report.assembly_steps(res, "tr")
        assert any("tambur" in s.lower() for s in steps) and not any("Çıkış rulmanını" in s for s in steps), steps
        print(f"  [OK] dönen gövde, {name}: {c['label']} · tambur {c['output']['bearing']} · 1/{1 / abs(f):.2f} ters yön"
              f"{' · yük ' + c['load']['short'] if c.get('load') else ''} · {time.time() - t:.1f} s")


def test_speed_up():
    """Hız artırıcı: jeneratör devri = giriş × oran, jeneratör torku = giriş / oran × verim; CAD standart düzenle aynı."""
    p, c = payload(arrangement="SPEED_UP", output_type="ARM", target_ratio=20, drive_torque=4, drive_speed=60,
                   arm_length=120)
    e = c["engineering"]
    i = c["total_ratio"]
    assert e["reverse"] and abs(e["output_speed"] - 60 * i) < 0.05 and abs(e["input_torque"] - 4.0) < 1e-6, e
    assert abs(e["output_torque"] - 4.0 / i * e["efficiency"]) < 1e-4, e["output_torque"]
    sp = e["speedup"]
    assert sp and sp["power_w"] > 0 and "Jeneratör" in sp["text"] and sp["detent_at_input"] > 0, sp
    # conservative loads: the last stage sun sees the full drive torque / last ratio (no efficiency credit)
    last = e["stages"][-1]
    assert abs(last["output_torque"] - 4.0) < 1e-6, last
    res = assembly.generate(p)
    check_solids(res)
    std = assembly.generate(dict(p, arrangement="CARRIER"))
    assert res.summary["part_count"] == std.summary["part_count"]
    print(f"  [OK] hız artırıcı: {c['label']} → jeneratör {sp['generator_speed']:.0f} rpm, {sp['generator_torque']:.3f} Nm, "
          f"{sp['power_w']:.1f} W; takılma girişte ~{sp['detent_at_input']:.2f} Nm")


def test_integral_suns():
    """Kademe arası: sonraki güneş tek plaka taşıyıcıda da taşıyıcıyla tek parça (D-mil yok); boyun burulması hesapta."""
    p, c = payload(carrier_type="SINGLE", pin_type="PRINTED", stages_count=3, target_ratio=60, motor_torque=0.2)
    assert all(s["inter_shaft_dia"] == 0.0 for s in c["stages"]), c["stages"]
    names = {x["name"] for st in c["engineering"]["stages"] for x in st["checks"]}
    assert "shaft_torsion" not in names and "sun_core_torsion" in names
    res = assembly.generate(p)
    keys = [pt.key for pt in res.parts]
    assert "sun_s1" in keys and not any(k in keys for k in ("sun_s2", "sun_s3")), keys
    check_solids(res)
    check_mesh(res)
    by = {pt.key: pt for pt in res.parts}
    assert by["carrier_s1"].gear and by["carrier_s2"].gear and not by["carrier_s3"].gear
    print("  [OK] tek plaka taşıyıcı: K2/K3 güneşleri taşıyıcıyla tek parça, D-mil yok, dişliler girişimsiz")


def test_phases():
    """Planet fazları: çember boşluğu 0°'de iken planet ve güneş dişleri kavrama konumunda."""
    sun_phase, phases = assembly.planet_phases(12, 18, 48, 3)
    assert abs(sun_phase - math.pi / 12) < 1e-9 and abs(phases[0]) < 1e-9
    assert assembly.planet_phases(15, 21, 57, 3)[0] == 0.0


def test_many_stages():
    """
    4-5 kademe: arama oranı tolerans içinde ve kademe oranları motordan çıkışa azalan; 4 kademenin CAD'i (tek ve
    geçerli katılar, kavrama, 0°'de çakışma yok, dönerken temas yok, çıkış 1/oran, verim uyarısı). Otomatik kademe:
    sınırsızken en küçük hacim, 3 kademenin sığmadığı çap sınırında 4 kademe; oran yükten: yük rezerviyle kaldırılıyor.
    """
    t = time.time()
    for n, ratio, kw in ((4, 300, {}), (5, 1500, dict(strength_required=False)),
                         (4, 300, dict(arrangement="RING", output_type="DRUM_FLANGE"))):
        c = design(dict(BASE, stages_count=n, target_ratio=ratio, motor_torque=0.05, **kw))["candidates"][0]
        assert len(c["stages"]) == n and abs(c["total_ratio"] - ratio) / ratio <= 0.03 + 1e-9, c["label"]
        plain = [s["ratio"] for s in c["stages"] if not s["star"]]
        assert all(a >= b - 1e-9 for a, b in zip(plain, plain[1:])), plain
    p, c = payload(stages_count=4, target_ratio=300, motor_torque=0.05)
    res = assembly.generate(p)
    check_solids(res)
    check_mesh(res)
    check_clashes(res)
    check_turning(res)
    kin = res.kinematics
    f = kin["bodies"][kin["output"]]["factor"]
    assert abs(1.0 / f - res.summary["total_ratio"]) < 1e-3, f
    assert any(w.startswith("4 kademe: toplam verim") for w in res.warnings), res.warnings
    q = dict(BASE, num_planets="AUTO", motor_torque=0.4)
    a = design(dict(q, stages_count="AUTO", target_ratio=25))
    assert a["auto"]["stages"] == 2 and len(a["candidates"][0]["stages"]) == 2, a["auto"]
    assert " · 2 kademe · " in a["candidates"][0]["label"], a["candidates"][0]["label"]
    od3 = design(dict(q, stages_count=3, target_ratio=133))["candidates"][0]["outer_diameter"]
    od4 = design(dict(q, stages_count=4, target_ratio=133))["candidates"][0]["outer_diameter"]
    assert od4 < od3, (od3, od4)
    lim = (od3 + od4) / 2.0
    tight = design(dict(q, stages_count="AUTO", target_ratio=133, od_limit=lim))
    best = tight["candidates"][0]
    assert tight["auto"]["stages"] == 4 and best["feasible"] and best["outer_diameter"] <= lim, (tight["auto"], best["label"])
    three = design(dict(q, stages_count=3, target_ratio=133, od_limit=lim))
    assert not three["candidates"][0]["feasible"] and "Otomatik" in (three.get("hint") or ""), three.get("hint")
    lr = design(dict(q, stages_count="AUTO", ratio_from_load=True, target_ratio=25, output_type="ARM", arm_length=150,
                     arm_width=40, arm_thickness=12, load_value=3, load_unit="KG"))
    au, c = lr["auto"], lr["candidates"][0]
    eta = 0.94 ** len(c["stages"])
    need = 3 * 9.80665 * 0.150 * 1.5 / (0.4 * eta)
    assert au["from_load"] and abs(au["min_ratio"] - need) < 0.05 and c["total_ratio"] >= need * 0.999, (au, c["label"])
    assert c["load"]["status"] == "ok" and c["feasible"], (c["label"], c["load"]["short"])
    print(f"  [OK] 4-5 kademe: {res.summary['part_count']} parça, 1/{1 / f:.1f}; otomatik 25:1 → 2 kademe, Ø{lim:.0f} "
          f"sınırında 133:1 → 4 kademe ({best['label']}); yükten {need:.1f}:1 → {c['total_ratio']}:1 "
          f"{c['load']['short']} · {time.time() - t:.1f} s")


def test_face_load_factor():
    """
    Diş genişliği boyunca yük dağılımı (K_Hβ): geniş diş orantılı kapasite vermez, balıksırtı daha iyi dağıtır, baskı
    pim (eğilir) ve büyük baskı hatası kötüleştirir; analiz K_Hβ'yi gösterir, geniş dişte uyarı verilir.
    """
    from core.design import Params
    from core.engineering import LoadCase, StageDesign, face_load_factor, stage_factors, stage_margin
    p = Params.from_payload(dict(BASE))
    geo = p.geo(18, 27, 72, 1.0)
    load = LoadCase(motor_torque=0.4, gear_material="PLA", struct_material="PLA")

    def khb(**kw):
        sd = StageDesign(**dict(dict(geo=geo, num_planets=3, face_width=12.0, helix_deg=0.0, herringbone=False,
                                     bearing_code="625ZZ", bearings_per_planet=1, pin_dia=5.0, pin_steel=True,
                                     carrier_cage=True, plate_t=4.0), **kw))
        f = stage_factors(sd, load)
        return face_load_factor(f, 5.0, 1.0)[0], f

    def capacity(f):                                   # teeth only (pins / bearings have their own checks)
        f = {k: v for k, v in f.items() if k not in ("pin", "core", "bearing", "shaft")}
        f["bushing"] = (1e9, 1e9)
        lo, hi = 0.01, 500.0
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if stage_margin(f, mid, 100.0, load) >= 1.0 else (lo, mid)
        return lo
    k12, f12 = khb()
    k45, f45 = khb(face_width=45.0, pin_dia=8.0, bearing_code="608ZZ")   # a wide planet gets a thicker pin
    assert 1.0 < k12 < 1.6 and k45 > k12, (k12, k45)
    gain = capacity(f45) / capacity(f12)
    assert 1.0 < gain < 45.0 / 12.0 * 0.85, gain          # wider is stronger, but well below proportional
    assert khb(herringbone=True, helix_deg=20.0)[0] < k12
    assert khb(pin_steel=False)[0] > k12 and khb(carrier_cage=False, pin_steel=False)[0] > k12   # printed pins bend
    assert khb(mfg_error=0.005)[0] < k12
    c = design(dict(BASE, face_width=12))["candidates"][0]
    st = c["engineering"]["stages"]
    assert all(s["k_hbeta"] >= 1.0 and s["misalignment_um"] > 0 for s in st), st
    from core.design import resolve
    wide = design(dict(BASE, face_width=45, stages_count=1, target_ratio=5, sizing_mode="MAX_OD", max_od=70,
                       strength_required=False))["candidates"][0]
    w = resolve(dict(BASE, face_width=45, stages_count=1, total_ratio=wide["total_ratio"], stages=wide["stages"]))
    assert any("eşit dağılmıyor" in x for x in w["warnings"]), w["warnings"]
    print(f"  [OK] yük dağılımı: K_Hβ 12 mm {k12:.2f} → 45 mm {k45:.2f}, 45/12 mm kapasite ×{gain:.2f} (orantılı ×3.75); "
          f"balıksırtı / CNC daha iyi, baskı pim kötü; tasarım K_Hβ {[s['k_hbeta'] for s in st]}; geniş dişte uyarı")


def test_profile_shift():
    """
    Profil kaydırma (V-sıfır): güneş +x, planet ve çember −x; eksen mesafesi, oran aynı; uç / kök x·m kayar, güneş
    kökü güçlenir, planet zayıflar; tüm kademeler ortak çemberi paylaştığı için x redüktör başına tektir; otomatik
    seçim hiçbir zaman x = 0'dan kötü değildir; elle x ile CAD'de dişliler girişimsiz.
    """
    from core.gear_geometry import depth_strength_factors, stage_geometry
    g0 = stage_geometry(13, 30, 73, 1.0, 20.0, 0.2)
    g1 = stage_geometry(13, 30, 73, 1.0, 20.0, 0.2, shift=0.3)
    assert abs(g1.center_distance - g0.center_distance) < 1e-12 and g1.x_planet == g1.x_ring == -0.3
    assert abs(g1.root_sun - g0.root_sun - 0.3) < 1e-9 and abs(g1.root_planet - g0.root_planet + 0.3) < 1e-9
    assert abs(g1.root_ring - g0.root_ring + 0.3) < 1e-9 and g1.interference_free
    f = depth_strength_factors(g1)
    assert f["sun"] > 1.0 > f["planet"], f
    for herr in (False, True):
        q = dict(BASE, num_planets="AUTO", is_herringbone=herr, target_ratio=133, stages_count=3, motor_torque=0.4)
        none = design(dict(q, profile_shift="NONE"))["candidates"][0]
        auto = design(dict(q, profile_shift="AUTO"))["candidates"][0]
        xs = {st["x_sun"] for st in auto["stages"]}
        assert len(xs) == 1, xs                       # one shift: the stages share the ring gear
        assert auto["feasible"] >= none["feasible"] and auto["outer_diameter"] <= none["outer_diameter"] + 1e-6,             (none["label"], auto["label"])
    p, c = payload(stages_count=2, target_ratio=25, motor_torque=0.05, profile_shift=0.35)
    assert all(st["x_sun"] == 0.35 for st in c["stages"]), c["stages"]
    res = assembly.generate(p)
    check_solids(res)
    check_mesh(res)
    check_clashes(res)
    check_turning(res)
    from core.design import resolve
    mixed = [dict(st, x_sun=(0.35 if k == 0 else -0.2)) for k, st in enumerate(c["stages"])]
    r = resolve(dict(p, stages=mixed))
    assert all(abs(st["geo"].x_sun - 0.35) < 1e-9 for st in r["stages"])       # the ring decides: stage 1's x
    print(f"  [OK] profil kaydırma: eksen mesafesi aynı, güneş ×{f['sun']:.2f} / planet ×{f['planet']:.2f} (x=+0.3); "
          f"otomatik: {auto['label']} x={xs.pop():+.2f} (x=0: Ø{none['outer_diameter']:.0f}); elle x=+0.35 CAD girişimsiz")


def test_calibration_coupon():
    """
    Kalibrasyon parçası: tasarımın her rulmanı / çelik pimi için numaralı yuvalar ve delikler, modülde boşluk dişli
    çiftleri; tek ve geçerli katılar, yerleşimde çakışma yok, dişli çiftleri pimlerde kavrar; Api ile üretilir ve
    STEP + STL + rehber olarak dışa aktarılır (rapor yerine kalibrasyon rehberi).
    """
    from occ_cad import calibration
    t = time.time()
    p, c = payload(stages_count=2, target_ratio=25, num_planets="AUTO")
    res = calibration.generate(p)
    check_solids(res)
    check_clashes(res)
    cal = res.design["calibration"]
    codes = {s["bearing"] for s in c["stages"]}
    assert codes <= {b["code"] for b in cal["bearings"]}, (codes, cal["bearings"])
    assert all(len(b["steps"]) == len(calibration.BEARING_STEPS) for b in cal["bearings"])
    assert {s["pin_dia"] for s in c["stages"]} == {pn["d"] for pn in cal["pins"]}
    assert [s["value"] for s in cal["backlash"]["steps"]] == list(calibration.BACKLASH_STEPS)
    gears = [pt for pt in res.parts if pt.key.startswith("cal_gear_")]
    assert len(gears) == len(calibration.BACKLASH_STEPS) and all(pt.quantity == 2 for pt in gears)
    bed = 256.0
    for pt in res.parts:
        x0, y0, z0, x1, y1, z1 = K.bounding_box(pt.shape)
        assert max(x1 - x0, y1 - y0) <= bed, (pt.key, x1 - x0, y1 - y0)
    os.environ["PLANETARY_GEARBOX_HOME"] = tempfile.mkdtemp(prefix="pgb_cal_ş_")
    from standalone.api import Api
    api = Api()
    api._settings["export_dir"] = os.path.join(os.environ["PLANETARY_GEARBOX_HOME"], "Dışa Aktarım")
    out = api.generate_calibration(p)
    assert out["success"] and out["calibration"]["bearings"] and out["steps"], out
    assert api.get_mesh("fast")["success"]
    exp = api.export_all()
    assert exp["success"] and exp["report"].endswith("Kalibrasyon_Rehberi.html"), exp
    txt = open(exp["report"], encoding="utf-8").read()
    assert "Tolerans Kalibrasyon" in txt and "+0.20 mm" in txt
    assert exp["stl_count"] == len(res.parts), exp
    shutil.rmtree(os.environ["PLANETARY_GEARBOX_HOME"], ignore_errors=True)
    print(f"  [OK] kalibrasyon parçası: {len(cal['bearings'])} rulman, {len(cal['pins'])} pim plakası, "
          f"{len(gears)} dişli çifti (m{cal['backlash']['module']}); çakışma yok; Api + STEP/STL/rehber · "
          f"{time.time() - t:.1f} s")


def test_print_3mf():
    """
    Baskıya hazır 3MF: tüm basılacak parçalar adet kadar, kapalı (manifold) ağlar, parça başına ayar (dişliler %100,
    gövde %40); Creality K1 Max profilinde Orca / Creality Print proje yapısı + yazıcı ve PETG ayarları, genel
    profilde sade 3MF + PrusaSlicer ayarları; tablaya sığmayan parça 45° çevrilir; Api dışa aktarması 3MF yazar.
    """
    import json as _json
    import re
    import zipfile
    from occ_cad import print3mf
    p, c = payload(stages_count=2, target_ratio=25, gear_material="PETG")
    res = assembly.generate(p)
    tmp = tempfile.mkdtemp(prefix="pgb_3mf_ş_")
    try:
        k1 = print3mf.write_3mf(res, os.path.join(tmp, "k1.3mf"), module=c["module"], bed=(300, 300),
                                profile="creality k1 max", material="PETG")
        z = zipfile.ZipFile(k1)
        ps = _json.loads(z.read("Metadata/project_settings.config"))
        assert ps["printer_settings_id"].startswith("Creality K1 Max") and ps["filament_type"] == ["PETG"], ps["filament_type"]
        assert ps["nozzle_temperature"] == ["250"], ps["nozzle_temperature"]
        ms = z.read("Metadata/model_settings.config").decode("utf-8")
        n_obj = ms.count("<object id=")
        assert n_obj == sum(pt.quantity for pt in res.parts if pt.printable), n_obj
        planet = re.search(r'<object id="\d+">\s*<metadata key="name" value="Planet[^"]*"/>(.*?)</object>', ms, re.S)
        assert planet and 'sparse_infill_density" value="100%"' in planet.group(1), ms[:400]
        mesh = z.read("3D/Objects/object_1.model").decode("utf-8")
        for obj in mesh.split("<object ")[1:]:
            edges = {}
            for a, b, cc in re.findall(r'v1="(\d+)" v2="(\d+)" v3="(\d+)"', obj):
                for e in ((a, b), (b, cc), (cc, a)):
                    k = tuple(sorted(e))
                    edges[k] = edges.get(k, 0) + 1
            assert edges and all(v == 2 for v in edges.values()), "açık kenar"
        gen = print3mf.write_3mf(res, os.path.join(tmp, "gen.3mf"), module=c["module"], bed=(256, 256))
        zg = zipfile.ZipFile(gen)
        assert "Metadata/Slic3r_PE_model.config" in zg.namelist() and "Metadata/project_settings.config" not in zg.namelist()
        assert 'key="fill_density" value="40%"' in zg.read("Metadata/Slic3r_PE_model.config").decode("utf-8")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"  [OK] 3MF: {n_obj} nesne, kapalı ağlar, parça ayarları; Creality K1 Max + PETG profili; genel PrusaSlicer biçimi")


def test_mount_bracket():
    """
    L montaj braketi: motor flanşının altında, cıvatalar rafa kadar uzar ve somunlar raftaki yuvalarda; tek ve
    geçerli katılar, çakışma yok, dönerken temas yok; cıvata ezilme kontrolü hesapta, duvar vidaları BOM'da;
    cıvataları motorun kendi deliklerinden geçen küçük gövdede uyarı.
    """
    t = time.time()
    p, c = payload(stages_count=2, target_ratio=25, num_planets="AUTO", motor_torque=0.4, mount_bracket=True,
                   sizing_mode="MAX_OD", max_od=130)
    names = [x["name"] for st in c["engineering"]["stages"] for x in st["checks"]]
    assert "mount_rods" in names, names
    plain = assembly.generate(dict(p, mount_bracket=False))
    res = assembly.generate(p)
    keys = [pt.key for pt in res.parts]
    assert "mount_bracket" in keys, keys
    check_solids(res)
    check_clashes(res)
    check_turning(res)
    bolt = next(pt for pt in res.parts if pt.key == "tie_rod_bolt")
    bolt0 = next(pt for pt in plain.parts if pt.key == "tie_rod_bolt")
    assert bolt.name != bolt0.name or "Rod" in bolt.name, (bolt.name, bolt0.name)       # longer by the shelf
    assert any("M5" in x["spec"] for x in report.bill_of_materials(res, "tr")[1])
    small = assembly.generate(dict(BASE, stages_count=1, total_ratio=5, mount_bracket=True,
                                   stages=design(dict(BASE, stages_count=1, target_ratio=5))["candidates"][0]["stages"]))
    assert "mount_bracket" in [pt.key for pt in small.parts] or any("braket" in w for w in small.warnings)
    print(f"  [OK] montaj braketi: {bolt0.name} → {bolt.name}, çakışma / temas yok, ezilme kontrolü, duvar vidaları "
          f"BOM'da · {time.time() - t:.1f} s")


MESH_KEYS = ("sun_s", "planet_s", "ring_housing", "carrier_top_s", "carrier_s", "drum")


def check_running_clearance(res, min_gap=0.2, sliding=(), meshing=()):
    """
    Birbirine göre dönen her parça çifti (farklı kinematik gövde) arasında en az `min_gap` boşluk: kademeler arası
    taşıyıcılar, pimler, plakalar ve gövde birbirine sürtmez. Diş kavramaları (planet ↔ güneş / çember / güneşli
    taşıyıcı) diş boşluğu kadar yaklaşır ve ayrıca kontrol edilir; rulmanlar iki gövdeye de değer (hariç).
    `sliding`: bilerek temas eden kaymalı yatak çiftleri ({anahtar_a, anahtar_b}); `meshing`: diş kavraması gibi
    yalnızca boşluğu > 0.02 mm olması gereken çiftler (sikloid disk ↔ halka pimi).
    Döndürür: en küçük kavrama dışı boşluk.
    """
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    inst = []
    for pt in res.parts:
        for i in range(pt.quantity):
            shp = _placed(pt, i)
            inst.append((f"{pt.key}#{i + 1}", pt.key, pt.bodies[i] if pt.bodies else "ground", shp, K.bounding_box(shp)))
    worst = (9.9, "", "")
    for a in range(len(inst)):
        for b in range(a + 1, len(inst)):
            A, B = inst[a], inst[b]
            if A[2] == B[2] or "bearing" in A[1] or "bearing" in B[1] or {A[1], B[1]} in sliding:
                continue
            if not all(A[4][k] - 1.0 <= B[4][k + 3] and B[4][k] - 1.0 <= A[4][k + 3] for k in range(3)):
                continue
            mesh = {A[1], B[1]} in meshing or ("planet_s" in A[1] or "planet_s" in B[1]) and A[1].startswith(MESH_KEYS) and B[1].startswith(MESH_KEYS)
            d = BRepExtrema_DistShapeShape(A[3], B[3])
            v = d.Value()
            if mesh:
                assert v > 0.02, f"kavrama sıkışık: {A[0]} ↔ {B[0]} {v:.3f} mm"
            elif v < worst[0]:
                worst = (v, A[0], B[0])
    assert worst[0] >= min_gap, f"sürtünme: {worst[1]} ↔ {worst[2]} arası {worst[0]:.3f} mm"
    return worst


def test_running_clearance():
    """Kademeler arası sürtünme yok: kafes ve tek plaka taşıyıcıda dönen parçalar arasında >= 0.2 mm boşluk."""
    t = time.time()
    out = []
    for kw in (dict(stages_count=3, target_ratio=60, motor_torque=0.2, num_planets="AUTO"),
               dict(stages_count=2, target_ratio=25, carrier_type="SINGLE", pin_type="PRINTED", motor_torque=0.2)):
        p, c = payload(**kw)
        res = assembly.generate(p)
        w = check_running_clearance(res)
        out.append(f"{w[0]:.2f} mm ({w[1].split('#')[0]} ↔ {w[2].split('#')[0]})")
    print(f"  [OK] kademeler arası sürtünme yok: en dar boşluk {'; '.join(out)} · {time.time() - t:.0f} s")


def test_wolfrom():
    """
    Wolfrom (kademeli planet, tek kademe): motor 50-500:1 aday üretir, oran Zr/Zp bağıntısıyla tutarlı; CAD geçerli
    tek katılar, kavramalar girişimsiz, döndürünce sürtünme yok (çıkış çemberi kaymalı yatakta bilerek temaslı),
    yüksek oranda kendiliğinden kilitlenir; rapor kendi montaj adımlarını yazar.
    """
    from core import wolfrom as W
    t = time.time()
    r, cf, i0, zr1, zr2 = W.ratio_of(21, 18, 19)
    assert zr1 == 57 and zr2 == 58 and abs(r - 1.0 / (cf * (1.0 - i0))) < 1e-9 and r < 0     # i0 > 1: reversed
    eta, back = W.efficiencies(i0, 0.94, 0.97)
    assert 0.2 < eta < 0.5 and back <= 0.0, (eta, back)          # high ratio: self-locking
    out = []
    for kw in (dict(target_ratio=100, output_type="DRUM_FLANGE", motor_torque=0.2),
               dict(target_ratio=60, output_type="DRUM_ARM", motor_torque=0.03, arm_length=120, arm_width=25)):
        p, c = payload(arrangement="WOLFROM", **kw)
        assert c["arrangement"] == "WOLFROM" and abs(c["total_ratio"] - kw["target_ratio"]) / kw["target_ratio"] < 0.05
        res = assembly.generate(p)
        assert res.summary["arrangement"] == "WOLFROM" and abs(res.summary["total_ratio"] - c["total_ratio"]) < 1e-3
        check_solids(res)
        check_clashes(res)
        by = {x.key: x for x in res.parts}
        pl = _placed(by["planet_s1"], 0)
        for k in ("sun_s1", "ring_housing", "drum"):
            assert K.volume(K.common(by[k].shape, pl)) < 1e-3, f"planet {k} dişlisine giriyor"
        check_turning(res, pair=lambda a, b: "planet" in a or "planet" in b or "drum" in a or "drum" in b)
        w = check_running_clearance(res, sliding=[{"ring_housing", "drum"}])
        steps = report.assembly_steps(res, "tr")
        assert any("Kademeli planet" in x for x in steps) and not any("taşıyıcıları sırayla" in x for x in steps)
        out.append(f"{c['total_ratio']:.1f}:1 Ø{res.summary['outer_diameter']:.0f} "
                   f"{'kilitli' if res.summary['wolfrom']['self_locking'] else 'geri sürülebilir'} · boşluk {w[0]:.2f} mm")
    print(f"  [OK] Wolfrom: {'; '.join(out)} · {time.time() - t:.0f} s")


def test_cycloid():
    """
    Sikloidal: oran = pim sayısı - 1 (ters yön), profil alt kesimsiz, disk ↔ halka pimi kavraması boşluklu ve
    girişimsiz, iki disk 180° karşılıklı; dönerken (planet tipi disk hareketi) hiçbir parça çakışmaz ve sürtmez.
    """
    from core import cycloid as C
    t = time.time()
    assert C.min_convex_radius(21, 22.5, 0.8) > 2.0 + 0.1          # 21 pins Ø4 @ R22.5, e 0.8: no undercut
    assert C.min_convex_radius(21, 22.5, 1.5) < 2.0                 # too large eccentricity: pointed lobes
    res0 = design(dict(BASE, arrangement="CYCLOID", target_ratio=120))
    assert not res0["candidates"] and res0.get("hint")
    out = []
    for kw in (dict(target_ratio=20, output_type="FLANGE", motor_torque=0.2),
               dict(target_ratio=30, output_type="ARM", motor_torque=0.2, arm_length=100, arm_width=25)):
        p, c = payload(arrangement="CYCLOID", **kw)
        cy = c["stages"][0]["cycloid"]
        assert c["total_ratio"] == cy["n_pins"] - 1 == kw["target_ratio"] and c["reversed"]
        res = assembly.generate(p)
        check_solids(res)
        check_clashes(res)
        by = {x.key: x for x in res.parts}
        pins = [_placed(by["ring_pin"], k) for k in range(by["ring_pin"].quantity)]
        for dk in ("disc_a", "disc_b"):
            dsk = _placed(by[dk], 0)
            assert sum(K.volume(K.common(dsk, q)) for q in pins if _overlap(dsk, q)) < 1e-3, f"{dk} pimlere giriyor"
        check_turning(res, degs=(23.0, 97.0, 211.0))
        w = check_running_clearance(res, meshing=[{"ring_pin", "disc_a"}, {"ring_pin", "disc_b"}])
        assert abs(res.kinematics["bodies"]["output"]["factor"] + 1.0 / kw["target_ratio"]) < 1e-9
        out.append(f"{c['total_ratio']:.0f}:1 {cy['n_pins']} pim Ø{2 * cy['rp']:g} e {cy['e']:.2f} "
                   f"Ø{res.summary['outer_diameter']:.0f} · boşluk {w[0]:.2f} mm")
    print(f"  [OK] Sikloidal: {'; '.join(out)} · {time.time() - t:.0f} s")


def test_declutch():
    """
    Boşa alma (kol çıkışı): bilezik + serbest kol + kapak pulu + yaylı indeks pimi (GN 617.1) ve ince somunu; parçalar
    çakışmaz, pim takılıyken kol çıkışla döner; pim çekilmiş kol bileziğe / pula / kapağa değmez (>= 0.25 mm), yani
    serbest döner. İndeks pimi boyu ve yarıçapı torkla büyür, delik ezilmesi kontrolü raporda; boy motorla aynı.
    """
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from core.engineering import declutch_design
    t = time.time()
    g1 = declutch_design(20.0, 5.0, "PLA", 1.4, "FLAT", 25.0, 8.0)
    g2 = declutch_design(32.0, 60.0, "PETG", 1.4, "FLAT", 30.0, 10.0)
    assert g2["r_c"] > g1["r_c"] and g2["pin_d"] > g1["pin_d"], (g1["pin_d"], g2["pin_d"])
    for g in (g1, g2):                                   # thin nut + clamped arm + lock nut fit on the thread
        pl, lay = g["plunger"], g["lay"]
        assert lay["local_top"] - (pl["m"] + 0.2) >= 3.0 and lay["t_s"] >= pl["l2"] + 2.0
    p, c = payload(output_type="ARM", declutch=True, arm_length=120, arm_width=25, arm_thickness=8, motor_torque=0.2)
    names = [ch["name"] for ch in c["engineering"]["stages"][-1]["checks"]]
    assert "declutch_hole" in names and "declutch_shear" in names, names
    res = assembly.generate(p)
    assert abs(res.summary["overall_length"] - c["overall_length"]) < 0.6, (res.summary["overall_length"], c["overall_length"])
    check_solids(res)
    check_clashes(res)
    check_turning(res, pair=lambda a, b: any(k in a or k in b for k in ("declutch", "output_arm", "arm_screw")))
    by = {x.key: x for x in res.parts}
    arm = _placed(by["output_arm"], 0)
    gaps = {k: BRepExtrema_DistShapeShape(arm, _placed(by[k], 0)).Value()
            for k in ("declutch_collar", "declutch_cap", "top_cover", "arm_screw") if k in by}
    assert min(gaps.values()) >= 0.25, gaps
    steps = report.assembly_steps(res, "tr")
    assert any("Boşa alma" in x for x in steps)
    assert "declutch_nut" in by and "GN 617.1" in by["declutch_pin"].spec
    print(f"  [OK] boşa alma (indeks pimi): {by['declutch_pin'].label.split(' ', 2)[-1]}; 5 Nm → Ø{g1['pin_d']:g} @ "
          f"r{g1['r_c']:g}, 60 Nm PETG → Ø{g2['pin_d']:g} @ r{g2['r_c']:g}; serbest kol boşluğu "
          f"{min(gaps.values()):.2f} mm · {time.time() - t:.0f} s")


def test_mount_types():
    """
    Montaj braketi her redüktör tipinde ve üç biçimde (yan L, ayaklı taban, panel): braket tek ve geçerli katı, hiçbir
    parçayla çakışmaz; bağlantı cıvataları rafa uzanır ve somunlar raftaki yuvalarda (motor flanşında değil); taşıyıcı
    hesapta braket kontrolü var.
    """
    t = time.time()
    out = []
    cases = (("standart", "SIDE", dict(stages_count=2, target_ratio=25, motor_torque=0.4)),
             ("standart", "BASE", dict(stages_count=2, target_ratio=25, motor_torque=0.4)),
             ("standart", "PANEL", dict(stages_count=2, target_ratio=25, motor_torque=0.4)),
             ("dönen gövde", "BASE", dict(stages_count=2, target_ratio=20, motor_torque=0.4, arrangement="RING",
                                          output_type="DRUM_FLANGE")),
             ("Wolfrom", "PANEL", dict(arrangement="WOLFROM", target_ratio=100, output_type="DRUM_FLANGE",
                                       motor_torque=0.2)),
             ("sikloidal", "SIDE", dict(arrangement="CYCLOID", target_ratio=25, output_type="FLANGE", motor_torque=0.4)),
             ("dönen gövde", "SIDE", dict(stages_count=2, target_ratio=20, motor_torque=0.4, arrangement="RING",
                                          output_type="DRUM_FLANGE")),
             ("standart kol", "SIDE", dict(stages_count=2, target_ratio=25, motor_torque=0.4, output_type="ARM",
                                           arm_length=150, arm_width=25)))
    for name, kind, kw in cases:
        p, c = payload(mount_type=kind, **kw)
        res = assembly.generate(p)
        by = {x.key: x for x in res.parts}
        assert "mount_bracket" in by, (name, kind, res.warnings)
        names = [ch["name"] for st in c["engineering"]["stages"] for ch in st["checks"]]
        assert "mount_rods" in names, (name, kind)
        check_solids(res)
        check_clashes(res)
        br = by["mount_bracket"]
        z_top = K.bounding_box(br.shape)[5]
        nut_zs = [K.bounding_box(_placed(by["tie_rod_nut"], i))[2] for i in range(by["tie_rod_nut"].quantity)]
        assert all(z < z_top - 2.0 for z in nut_zs), (name, kind, nut_zs, z_top)   # nuts in the shelf
        if kind == "SIDE":
            # the back plate stands outside the widest part: nothing of the gearbox reaches the wall
            wall = K.bounding_box(br.shape)[1] + B.MOUNT_BACK_T
            for pt in res.parts:
                if pt.key in ("mount_bracket",) + assembly.SWING_KEYS:
                    continue
                for i in range(pt.quantity):
                    y_min = K.bounding_box(_placed(pt, i))[1]
                    assert y_min >= wall + 1.0, (name, pt.key, y_min, wall)
            if "arm" in name:
                assert any("~" in w and "°" in w for w in res.warnings), res.warnings
        out.append(f"{name}/{kind}")
    print(f"  [OK] montaj braketi her tipte: {', '.join(out)} · {time.time() - t:.0f} s")


def test_drum_declutch():
    """
    Boşa alma pimi tambur / göbek kollarında (dönen gövde, Wolfrom, sikloidal): tahrik halkası yüze vidalı, kol
    halkanın boynunda serbest, pim dönme eksenine paralel; çakışma yok, takılıyken kol çıkışla döner, pim çekilmiş
    kol halkaya / pula / tambura değmez; hesapta kol eğilmesi ve pim kontrolleri, boy CAD ile aynı.
    """
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    t = time.time()
    out = []
    cases = (("dönen gövde", dict(stages_count=2, target_ratio=20, motor_torque=0.3, arrangement="RING",
                                  output_type="DRUM_ARM"), ("drum",)),
             ("Wolfrom", dict(arrangement="WOLFROM", target_ratio=100, output_type="DRUM_ARM", motor_torque=0.2),
              ("drum",)),
             ("sikloidal", dict(arrangement="CYCLOID", target_ratio=25, output_type="ARM", motor_torque=0.3),
              ("carrier_top_s1",)))
    for name, kw, faces in cases:
        p, c = payload(declutch=True, arm_length=150, arm_width=25, arm_thickness=8, **kw)
        names = [ch["name"] for st in c["engineering"]["stages"] for ch in st["checks"]]
        assert "declutch_hole" in names and "arm_bending" in names, (name, names)
        res = assembly.generate(p)
        assert abs(res.summary["overall_length"] - c["overall_length"]) < 0.6, (name, res.summary["overall_length"],
                                                                               c["overall_length"])
        by = {x.key: x for x in res.parts}
        for k in ("declutch_collar", "declutch_cap", "declutch_pin", "output_arm"):
            assert k in by, (name, k)
        check_solids(res)
        check_clashes(res)
        check_turning(res, pair=lambda a, b: any(k in a or k in b for k in ("declutch", "output_arm", "arm_screw")))
        arm = _placed(by["output_arm"], 0)
        gaps = {k: BRepExtrema_DistShapeShape(arm, _placed(by[k], 0)).Value()
                for k in ("declutch_collar", "declutch_cap") + faces if k in by}
        gaps["screws"] = min(BRepExtrema_DistShapeShape(arm, _placed(by["arm_screw"], i)).Value()
                             for i in range(by["arm_screw"].quantity))
        assert min(gaps.values()) >= 0.25, (name, gaps)
        out.append(f"{name} {by['declutch_pin'].label.split(' ')[-1]} boşluk {min(gaps.values()):.2f} mm")
    print(f"  [OK] tambur / göbek kolunda boşa alma pimi: {'; '.join(out)} · {time.time() - t:.0f} s")


def test_expert_mode():
    """
    Uzman modu: kapalıyken sonuçlar aynı; açıkken her kademede diş sıcaklığı, aşınma ve çevrim / sıcaklık çarpanları;
    sıcaklık artışı torkla doğrusal, ED ile düşer, ortamla artar; kuru çalışma gresliden ağır; durarak tutmada sünme
    kontrolü; arama uzman sınırlarını da sağlar; rapor uzman satırını ve yöntemini yazar.
    """
    from core import expert
    from core.engineering import LoadCase
    t = time.time()
    base = dict(BASE, stages_count=2, target_ratio=25, motor_torque=0.4)
    off = design(dict(base))["candidates"][0]
    off2 = design(dict(base, expert_mode=False, lubrication="DRY", ambient_temp=60))["candidates"][0]
    assert off["label"] == off2["label"] and not any(st.get("expert") for st in off["engineering"]["stages"])
    on = design(dict(base, expert_mode=True))["candidates"][0]
    for st in on["engineering"]["stages"]:
        names = [c["name"] for c in st["checks"]]
        assert st.get("expert") and "tooth_temp" in names and "wear_sun" in names, names
    assert on["feasible"] and on["margin"] >= 1.0
    # temperature physics on one stage's terms
    x = {"geo": 136.0 * 2.5 / 22.5, "b": 12.0, "z1": 15, "m": 1.0, "ra": 10.0, "mu": 0.07, "kw": 1e-6, "n_pl": 3,
         "t_max": 50.0, "l_fl": 2.25}
    lc = LoadCase(expert=True)
    r1 = expert.terms(x, 0.4, 250.0, 0.2, lc)["rise"]
    r2 = expert.terms(x, 0.8, 250.0, 0.2, lc)["rise"]
    r_ed = expert.terms(x, 0.4, 250.0, 0.2, LoadCase(expert=True, duty=0.2))["rise"]
    assert abs(r2 / r1 - 2.0) < 1e-9 and r_ed < 0.4 * r1
    hot = design(dict(base, expert_mode=True, ambient_temp=40))["candidates"][0]
    dry = design(dict(base, expert_mode=True, lubrication="DRY"))["candidates"][0]
    temp = lambda c: max(st["expert"]["temp"] for st in c["engineering"]["stages"])
    assert temp(hot) > temp(on) + 10.0
    assert dry["outer_diameter"] >= on["outer_diameter"] >= off["outer_diameter"], (off["outer_diameter"],
                                                                                    on["outer_diameter"],
                                                                                    dry["outer_diameter"])
    held = design(dict(base, expert_mode=True, hold_hours=1000, load_value=10, load_unit="KG", load_radius=100))
    assert any(c["name"] == "creep" for st in held["candidates"][0]["engineering"]["stages"] for c in st["checks"])
    p = dict(base, expert_mode=True, total_ratio=on["total_ratio"], stages=on["stages"])
    res = assembly.generate(p)
    html_path = os.path.join(tempfile.mkdtemp(prefix="pgb_exp_"), "r.html")
    report.write_html_report(res, html_path, "tr")
    doc = open(html_path, encoding="utf-8").read()
    assert "Uzman modu" in doc and "Diş sıcaklığı" in doc and "°C" in doc
    # Wolfrom and cycloidal: housing heat balance of the power loss, dry running lowers the efficiency
    special = []
    for arr, ratio, out in (("WOLFROM", 100, "DRUM_FLANGE"), ("CYCLOID", 25, "FLANGE")):
        kw = dict(BASE, arrangement=arr, target_ratio=ratio, output_type=out, motor_torque=0.4)
        plain = design(dict(kw))["candidates"][0]
        greased = design(dict(kw, expert_mode=True, hold_hours=2000, load_value=10, load_unit="KG",
                              load_radius=100))["candidates"][0]
        dry_c = design(dict(kw, expert_mode=True, lubrication="DRY"))["candidates"][0]
        names = [c["name"] for st in greased["engineering"]["stages"] for c in st["checks"]]
        assert "tooth_temp" in names and "creep" in names, (arr, names)
        assert not any(st.get("expert") for st in plain["engineering"]["stages"])
        assert dry_c["engineering"]["efficiency"] < greased["engineering"]["efficiency"] - 0.01, arr
        ex = next(st["expert"] for st in greased["engineering"]["stages"] if st.get("expert"))
        special.append(f"{arr} {ex['temp']:.0f} °C η {greased['engineering']['efficiency'] * 100:.0f}→"
                       f"{dry_c['engineering']['efficiency'] * 100:.0f} %")
        if arr == "WOLFROM":
            pw = dict(kw, expert_mode=True, total_ratio=greased["total_ratio"], stages=greased["stages"])
            res_w = assembly.generate(pw)
            assert res_w.engineering["stages"][0].get("expert")
    print(f"  [OK] uzman modu: Ø{off['outer_diameter']:.0f} → gresli Ø{on['outer_diameter']:.0f} "
          f"({temp(on):.0f} °C) / kuru Ø{dry['outer_diameter']:.0f}; 40 °C ortam {temp(hot):.0f} °C; sünme kontrolü; "
          f"rapor; {'; '.join(special)} · {time.time() - t:.0f} s")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    print("=" * 64)
    print("BAĞIMSIZ TASARIM VE CAD MOTORU TESTLERİ")
    print("=" * 64)
    t0 = time.time()
    test_phases()
    test_geometry_interference_free()
    test_tooth_depth_geometry()
    test_application_load()
    test_face_load_factor()
    test_profile_shift()
    test_design_engine()
    test_cases()
    test_tooth_depth_cad()
    test_kinematics_rotated()
    test_output_arm()
    test_layout_length()
    test_design_hints()
    test_carrier_plates()
    test_planets_auto()
    test_hub_nuts()
    test_hub_nut_parts()
    test_integral_suns()
    test_rotating_housing()
    test_speed_up()
    test_many_stages()
    test_large_gearbox()
    test_export_turkish_path()
    test_api_export_all()
    test_calibration_coupon()
    test_print_3mf()
    test_mount_bracket()
    test_running_clearance()
    test_wolfrom()
    test_cycloid()
    test_declutch()
    test_drum_declutch()
    test_mount_types()
    test_expert_mode()
    test_fusion_bridge()
    print("=" * 64)
    print(f"TÜM TESTLER GEÇTİ ({time.time() - t0:.0f} s)")
