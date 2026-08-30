"""
Offline Unit Test & Validation Script for Planetary Gearbox Engine.
Validates tooth synthesis, coaxiality, assembly conditions, clearance margins,
bearing catalog, and motor presets.
"""
import sys
import os

# Add directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.kinematics import PlanetarySynthesisEngine, StageKinematics
from core.tooth_profile import ToothProfileGenerator
from core.bearing_catalog import BEARING_CATALOG, get_bearing_info
from core.motor_catalog import MOTOR_CATALOG, get_motor_info

def run_tests():
    print("==================================================")
    print("RUNNING PLANETARY GEARBOX ENGINE TESTS")
    print("==================================================")
    
    # Test 1: Single Stage Synthesis (Target: 5:1 with 3 planets)
    print("\n[TEST 1] Single Stage 5:1 Synthesis (N=3, m=1.0mm)")
    res1 = PlanetarySynthesisEngine.synthesize_multistage(target_ratio=5.0, stages_count=1, num_planets=3, module=1.0)
    assert len(res1) > 0, "No candidates found for single stage 5:1!"
    best1 = res1[0]
    print(f"  [OK] Found {len(res1)} candidates. Best: {best1['total_ratio']}:1 (Error: {best1['error_percent']}%)")
    stage1 = best1['stages'][0]
    print(f"    Zs={stage1['z_sun']}, Zp={stage1['z_planet']}, Zr={stage1['z_ring']}")
    assert stage1['coaxiality_ok'], "Coaxiality failed!"
    assert stage1['assembly_ok'], "Assembly condition failed!"
    assert stage1['planet_clearance_ok'], "Planet collision detected!"
    
    # Test 2: Two Stage Synthesis (Target: 25:1 with 3 planets)
    print("\n[TEST 2] 2-Stage 25:1 Synthesis (N=3, m=1.0mm, Common Ring)")
    res2 = PlanetarySynthesisEngine.synthesize_multistage(target_ratio=25.0, stages_count=2, num_planets=3, module=1.0)
    assert len(res2) > 0, "No candidates found for 2-stage 25:1!"
    best2 = res2[0]
    print(f"  [OK] Found {len(res2)} candidates. Best: {best2['total_ratio']}:1 (Error: {best2['error_percent']}%)")
    for idx, s in enumerate(best2['stages']):
        print(f"    Stage {idx+1}: Ratio {s['ratio']}:1 | Zs={s['z_sun']}, Zp={s['z_planet']}, Zr={s['z_ring']} (Clearance: {s['clearance_mm']}mm)")
        assert s['coaxiality_ok'], f"Stage {idx+1} coaxiality failed!"
        assert s['assembly_ok'], f"Stage {idx+1} assembly condition failed!"
        assert s['planet_clearance_ok'], f"Stage {idx+1} clearance failed!"
    assert best2['stages'][0]['z_ring'] == best2['stages'][1]['z_ring'], "Shared ring gear failed in common ring mode!"

    # Test 3: 3-Stage High Reduction Synthesis (Target: 100:1 with 3 planets)
    print("\n[TEST 3] 3-Stage 100:1 Synthesis (N=3, m=1.0mm)")
    res3 = PlanetarySynthesisEngine.synthesize_multistage(target_ratio=100.0, stages_count=3, num_planets=3, module=1.0)
    assert len(res3) > 0, "No candidates found for 3-stage 100:1!"
    best3 = res3[0]
    print(f"  [OK] Found {len(res3)} candidates. Best: {best3['total_ratio']}:1 (Error: {best3['error_percent']}%)")

    # Test 4: High-Speed Involute Feature Generation
    print("\n[TEST 4] Tooth Profile Feature Generation")
    feat_ext = ToothProfileGenerator.get_external_tooth_features(z=16, module=1.0, backlash_mm=0.05)
    print(f"  [OK] External Sun/Planet features: RootR={feat_ext['root_r_cm']*10:.2f}mm, TipR={feat_ext['outside_r_cm']*10:.2f}mm, SplinePts={len(feat_ext['spline1_pts'])}")
    assert len(feat_ext['spline1_pts']) >= 10, "External spline points missing!"

    feat_int = ToothProfileGenerator.get_internal_tooth_space_features(z_ring=48, module=1.0, backlash_mm=0.05)
    print(f"  [OK] Internal Ring space features: TipBoreR={feat_int['tip_r_cm']*10:.2f}mm, RootCutR={feat_int['root_r_cm']*10:.2f}mm, SpaceSplinePts={len(feat_int['spline1_pts'])}")
    assert len(feat_int['spline1_pts']) >= 10, "Internal space points missing!"

    twist_angle = ToothProfileGenerator.calculate_herringbone_twist_angle(face_width=12.0, pitch_radius=10.0, helix_angle_deg=25.0)
    print(f"  [OK] Herringbone twist angle: {round(twist_angle * 180 / 3.14159, 2)} degrees")
    assert twist_angle > 0.1, "Twist angle computation invalid!"

    # Test 5: Catalogs Verification
    print("\n[TEST 5] Catalog Lookups")
    bearing_688 = get_bearing_info("688ZZ")
    assert bearing_688["d_inner"] == 8.0 and bearing_688["d_outer"] == 16.0
    print(f"  [OK] Bearing 688ZZ: d={bearing_688['d_inner']}mm, D={bearing_688['d_outer']}mm, B={bearing_688['width']}mm")

    motor_nema17 = get_motor_info("NEMA17")
    assert motor_nema17["default_shaft_dia"] == 5.0
    print(f"  [OK] Motor NEMA17: Shaft={motor_nema17['default_shaft_dia']}mm ({motor_nema17['default_shaft_type']}), PCD={motor_nema17['bolt_pitch_circle']}mm")

    print("\n==================================================")
    print("ALL TESTS PASSED WITH 100% SUCCESS!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
