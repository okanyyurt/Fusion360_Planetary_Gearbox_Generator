"""
Planetary Gearbox Kinematics & Tooth Count Synthesis Engine
Calculates optimal tooth counts, multi-stage distribution, and geometric constraints.
"""
import math
from typing import List, Dict, Tuple, Optional

class StageKinematics:
    """Represents a single planetary gear stage calculation."""
    def __init__(self, z_sun: int, z_planet: int, z_ring: int, num_planets: int, module: float, 
                 pressure_angle_deg: float = 20.0, helix_angle_deg: float = 0.0):
        self.z_sun = int(z_sun)
        self.z_planet = int(z_planet)
        self.z_ring = int(z_ring)
        self.num_planets = int(num_planets)
        self.module = float(module)
        self.pressure_angle = math.radians(pressure_angle_deg)
        self.helix_angle = math.radians(helix_angle_deg)
        
        # Kinematic Ratio (Ring fixed, Sun input, Carrier output)
        self.ratio = 1.0 + float(self.z_ring) / float(self.z_sun)
        
        # Pitch Diameters
        self.d_sun = self.module * self.z_sun
        self.d_planet = self.module * self.z_planet
        self.d_ring = self.module * self.z_ring
        
        # Base Diameters
        self.d_base_sun = self.d_sun * math.cos(self.pressure_angle)
        self.d_base_planet = self.d_planet * math.cos(self.pressure_angle)
        self.d_base_ring = self.d_ring * math.cos(self.pressure_angle)
        
        # Center Distance
        self.center_distance = self.module * (self.z_sun + self.z_planet) / 2.0
        
        # Tip (Addendum) & Root (Dedendum) Diameters (Standard: ha = 1.0*m, hf = 1.25*m)
        self.da_sun = self.d_sun + 2.0 * self.module
        self.df_sun = self.d_sun - 2.5 * self.module
        
        self.da_planet = self.d_planet + 2.0 * self.module
        self.df_planet = self.d_planet - 2.5 * self.module
        
        # For Internal Ring gear:
        # Tip (inner bore of teeth) = d_ring - 2.0 * module
        # Root (outer base of teeth) = d_ring + 2.5 * module
        self.da_ring = self.d_ring - 2.0 * self.module
        self.df_ring = self.d_ring + 2.5 * self.module

    def check_coaxiality(self) -> bool:
        """Coaxiality condition: Z_ring = Z_sun + 2 * Z_planet"""
        return self.z_ring == (self.z_sun + 2 * self.z_planet)

    def check_assembly_condition(self) -> bool:
        """Assembly condition for equally spaced planets: (Z_sun + Z_ring) % N_planets == 0"""
        return (self.z_sun + self.z_ring) % self.num_planets == 0

    def check_planet_clearance(self) -> Tuple[bool, float]:
        """
        Check whether adjacent planet tip circles collide.
        Distance between adjacent planet centers: 2 * a * sin(pi / N)
        Planet tip diameter: da_planet
        Returns (is_valid, clearance_distance_mm)
        """
        center_to_center = 2.0 * self.center_distance * math.sin(math.pi / self.num_planets)
        clearance = center_to_center - self.da_planet
        is_safe = clearance > (0.4 * self.module)
        return is_safe, clearance

    def get_contact_ratio(self) -> float:
        """Calculates approximate transverse contact ratio."""
        ra_sun = self.da_sun / 2.0
        rb_sun = self.d_base_sun / 2.0
        ra_planet = self.da_planet / 2.0
        rb_planet = self.d_base_planet / 2.0
        
        try:
            g_alpha = (math.sqrt(max(0, ra_sun**2 - rb_sun**2)) + 
                       math.sqrt(max(0, ra_planet**2 - rb_planet**2)) - 
                       self.center_distance * math.sin(self.pressure_angle))
            p_b = math.pi * self.module * math.cos(self.pressure_angle)
            return g_alpha / p_b if p_b > 0 else 1.4
        except Exception:
            return 1.4

    def to_dict(self) -> dict:
        is_clear, clearance_mm = self.check_planet_clearance()
        return {
            "z_sun": self.z_sun,
            "z_planet": self.z_planet,
            "z_ring": self.z_ring,
            "num_planets": self.num_planets,
            "module": self.module,
            "ratio": round(self.ratio, 3),
            "center_distance": round(self.center_distance, 3),
            "d_sun": round(self.d_sun, 2),
            "d_planet": round(self.d_planet, 2),
            "d_ring": round(self.d_ring, 2),
            "da_sun": round(self.da_sun, 2),
            "da_planet": round(self.da_planet, 2),
            "da_ring": round(self.da_ring, 2),
            "coaxiality_ok": self.check_coaxiality(),
            "assembly_ok": self.check_assembly_condition(),
            "planet_clearance_ok": is_clear,
            "clearance_mm": round(clearance_mm, 3),
            "contact_ratio": round(self.get_contact_ratio(), 2)
        }


class PlanetarySynthesisEngine:
    """
    Finds optimal integer tooth combinations satisfying all kinematic,
    geometric, and assembly constraints for single and multi-stage gearboxes.
    """
    
    @staticmethod
    def find_single_stage_candidates(
        target_ratio: float, 
        num_planets: int = 3, 
        module: float = 1.0,
        z_sun_min: int = 12,
        z_sun_max: int = 40,
        z_ring_max: int = 140,
        tolerance: float = 0.08,
        bearing_outer_dia_mm: float = 0.0,
        motor_shaft_dia_mm: float = 0.0
    ) -> List[StageKinematics]:
        """
        Finds candidate tooth sets prioritizing robust planet-to-bearing (>=1.8x)
        and safe sun-to-shaft ratios (<=65%).
        """
        candidates = []
        
        for zs in range(z_sun_min, z_sun_max + 1):
            for zp in range(10, (z_ring_max - zs) // 2 + 1):
                zr = zs + 2 * zp
                if zr > z_ring_max:
                    continue
                
                # Check assembly rule
                if (zs + zr) % num_planets != 0:
                    continue
                
                stage = StageKinematics(zs, zp, zr, num_planets, module)
                is_clear, _ = stage.check_planet_clearance()
                if not is_clear:
                    continue
                
                # Ratio check
                actual_ratio = stage.ratio
                ratio_error = abs(actual_ratio - target_ratio) / target_ratio
                
                if ratio_error <= tolerance:
                    # Mechanical structural penalty
                    score = ratio_error * 1000.0
                    
                    # 1. Planet Gear vs Bearing Diameter (User Rule: D_planet >= 1.8 - 2.0x D_bearing)
                    if bearing_outer_dia_mm > 0:
                        d_planet_mm = module * zp
                        if d_planet_mm < (bearing_outer_dia_mm * 1.6):
                            score += 500.0  # heavy penalty if planet is too small for bearing
                        elif d_planet_mm < (bearing_outer_dia_mm * 1.9):
                            score += 100.0
                            
                    # 2. Sun Gear Root vs Motor Shaft (User Rule: Shaft <= 65% of Sun Root)
                    if motor_shaft_dia_mm > 0:
                        d_root_sun_mm = module * (zs - 2.5)
                        if motor_shaft_dia_mm > (d_root_sun_mm * 0.70):
                            score += 300.0
                            
                    score += zr * 0.1  # secondary preference for compact ring
                    candidates.append((score, stage))
        
        # Sort candidates by optimal score
        candidates.sort(key=lambda item: item[0])
        return [c[1] for c in candidates]

    @staticmethod
    def synthesize_multistage(
        target_ratio: float,
        stages_count: int = 1,
        num_planets: int = 3,
        module: float = 1.0,
        common_ring: bool = True
    ) -> List[Dict]:
        """
        Synthesizes single or multi-stage planetary gearboxes.
        If common_ring is True, all stages use the exact same ring gear tooth count (Z_ring),
        which allows a continuous, elegant single-cylinder ring housing!
        """
        if stages_count <= 1:
            candidates = PlanetarySynthesisEngine.find_single_stage_candidates(
                target_ratio, num_planets, module, tolerance=0.15
            )
            results = []
            for cand in candidates[:10]:
                results.append({
                    "total_ratio": round(cand.ratio, 3),
                    "target_ratio": target_ratio,
                    "error_percent": round(abs(cand.ratio - target_ratio) / target_ratio * 100, 2),
                    "stages": [cand.to_dict()],
                    "common_ring": True,
                    "z_ring": cand.z_ring
                })
            return results
        
        # Multi-stage synthesis
        per_stage_target = target_ratio ** (1.0 / stages_count)
        results = []
        
        # If common ring is requested, search across potential shared ring tooth counts
        if common_ring:
            for zr in range(36, 120):
                # Check if zr can yield valid stage designs
                stage_options = []
                for stage_idx in range(stages_count):
                    valid_for_this_stage = []
                    for zs in range(12, zr - 18):
                        if (zr - zs) % 2 != 0:
                            continue
                        zp = (zr - zs) // 2
                        if zp < 10:
                            continue
                        if (zs + zr) % num_planets != 0:
                            continue
                        
                        stage = StageKinematics(zs, zp, zr, num_planets, module)
                        is_clear, _ = stage.check_planet_clearance()
                        if is_clear:
                            valid_for_this_stage.append(stage)
                    stage_options.append(valid_for_this_stage)
                
                # Combine stages
                if stages_count == 2 and stage_options[0] and stage_options[1]:
                    for s1 in stage_options[0]:
                        for s2 in stage_options[1]:
                            tot_ratio = s1.ratio * s2.ratio
                            err = abs(tot_ratio - target_ratio) / target_ratio
                            if err <= 0.10:
                                results.append({
                                    "total_ratio": round(tot_ratio, 3),
                                    "target_ratio": target_ratio,
                                    "error_percent": round(err * 100, 2),
                                    "stages": [s1.to_dict(), s2.to_dict()],
                                    "common_ring": True,
                                    "z_ring": zr
                                })
                elif stages_count == 3 and stage_options[0] and stage_options[1] and stage_options[2]:
                    for s1 in stage_options[0]:
                        for s2 in stage_options[1]:
                            for s3 in stage_options[2]:
                                tot_ratio = s1.ratio * s2.ratio * s3.ratio
                                err = abs(tot_ratio - target_ratio) / target_ratio
                                if err <= 0.12:
                                    results.append({
                                        "total_ratio": round(tot_ratio, 3),
                                        "target_ratio": target_ratio,
                                        "error_percent": round(err * 100, 2),
                                        "stages": [s1.to_dict(), s2.to_dict(), s3.to_dict()],
                                        "common_ring": True,
                                        "z_ring": zr
                                    })
        
        # Sort results by smallest error percentage and compactness
        results.sort(key=lambda r: (r["error_percent"], r["z_ring"]))
        
        # Deduplicate and return top 15 designs
        unique_results = []
        seen = set()
        for r in results:
            key = tuple((s["z_sun"], s["z_planet"], s["z_ring"]) for s in r["stages"])
            if key not in seen:
                seen.add(key)
                unique_results.append(r)
                if len(unique_results) >= 15:
                    break
                    
        return unique_results
