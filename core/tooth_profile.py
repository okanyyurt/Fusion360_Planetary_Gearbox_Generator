"""
Parametric Involute Tooth Profile Generator.
Generates mathematically exact 2D coordinates for External (Sun/Planet) 
and Internal (Ring) gears following ISO/AGMA gear standards.
"""
import math
from typing import List, Tuple, Dict

Point2D = Tuple[float, float]
Point3D = Tuple[float, float, float]

def inv(phi_rad: float) -> float:
    """Involute function: inv(phi) = tan(phi) - phi"""
    return math.tan(phi_rad) - phi_rad

class ToothProfileGenerator:
    """
    Precision Involute Tooth Profile Generator for Fusion 360.
    Generates continuous, smooth closed polygons in millimeters.
    """

    @staticmethod
    def generate_external_gear_polygon(
        z: int,
        module: float,
        pressure_angle_deg: float = 20.0,
        backlash_mm: float = 0.05,
        pts_per_flank: int = 10
    ) -> List[Point2D]:
        """
        Generates full 2D closed polygon coordinates for an external spur gear (Sun / Planet).
        All coordinates returned in millimeters (mm).
        """
        z = int(z)
        m = float(module)
        alpha = math.radians(pressure_angle_deg)
        
        r_pitch = m * z / 2.0
        r_base = r_pitch * math.cos(alpha)
        r_tip = r_pitch + 1.0 * m
        r_root = r_pitch - 1.25 * m
        
        # Effective base of involute
        r_inv_start = max(r_base, r_root)
        
        # Tooth thickness on pitch circle (with backlash tooth thinning)
        s_pitch = (math.pi * m / 2.0) - backlash_mm
        half_thick_angle = s_pitch / (2.0 * r_pitch)
        inv_alpha = inv(alpha)
        
        pitch_angle = 2.0 * math.pi / z
        
        # 1. Right flank radii (root up to tip)
        radii_up = [r_inv_start + (r_tip - r_inv_start) * (i / (pts_per_flank - 1)) for i in range(pts_per_flank)]
        # 2. Left flank radii (tip down to root)
        radii_down = list(reversed(radii_up))
        
        gear_points: List[Point2D] = []
        
        for k in range(z):
            rot = k * pitch_angle
            
            # A. Root land center before tooth
            t_gap_start = rot - (pitch_angle / 2.0)
            gear_points.append((r_root * math.cos(t_gap_start), r_root * math.sin(t_gap_start)))
            
            # B. Root corner under right flank
            t_right_root = rot - (half_thick_angle + inv_alpha)
            gear_points.append((r_root * math.cos(t_right_root), r_root * math.sin(t_right_root)))
            
            # C. Right Involute Flank (from base to tip)
            for r in radii_up:
                cos_phi = max(-1.0, min(1.0, r_base / r))
                phi = math.acos(cos_phi)
                theta = half_thick_angle + inv_alpha - inv(phi)
                t_curr = rot - theta
                gear_points.append((r * math.cos(t_curr), r * math.sin(t_curr)))
                
            # D. Tooth Tip Center
            gear_points.append((r_tip * math.cos(rot), r_tip * math.sin(rot)))
            
            # E. Left Involute Flank (from tip down to base)
            for r in radii_down:
                cos_phi = max(-1.0, min(1.0, r_base / r))
                phi = math.acos(cos_phi)
                theta = half_thick_angle + inv_alpha - inv(phi)
                t_curr = rot + theta
                gear_points.append((r * math.cos(t_curr), r * math.sin(t_curr)))
                
            # F. Root corner under left flank
            t_left_root = rot + (half_thick_angle + inv_alpha)
            gear_points.append((r_root * math.cos(t_left_root), r_root * math.sin(t_left_root)))
            
        return gear_points

    @staticmethod
    def generate_internal_ring_gear_polygon(
        z_ring: int,
        module: float,
        pressure_angle_deg: float = 20.0,
        backlash_mm: float = 0.05,
        pts_per_flank: int = 10
    ) -> List[Point2D]:
        """
        Generates internal tooth profile for Ring Gear (pointing inward).
        Inner tip bore: r_tip = r_pitch - 1.0 * m
        Outer root: r_root = r_pitch + 1.25 * m
        All coordinates returned in millimeters (mm).
        """
        z = int(z_ring)
        m = float(module)
        alpha = math.radians(pressure_angle_deg)
        
        r_pitch = m * z / 2.0
        r_base = r_pitch * math.cos(alpha)
        r_tip_inner = r_pitch - 1.0 * m
        r_root_outer = r_pitch + 1.25 * m
        
        r_inv_start = max(r_base, r_tip_inner)
        
        # Solid tooth thickness on pitch circle
        s_pitch = (math.pi * m / 2.0) - backlash_mm
        half_thick_angle = s_pitch / (2.0 * r_pitch)
        inv_alpha = inv(alpha)
        
        pitch_angle = 2.0 * math.pi / z
        
        # Internal tooth: Right flank goes from outer root down to inner tip
        radii_in = [r_root_outer - (r_root_outer - r_inv_start) * (i / (pts_per_flank - 1)) for i in range(pts_per_flank)]
        radii_out = list(reversed(radii_in))
        
        ring_points: List[Point2D] = []
        
        for k in range(z):
            rot = k * pitch_angle
            
            # A. Root land center before tooth
            t_gap = rot - (pitch_angle / 2.0)
            ring_points.append((r_root_outer * math.cos(t_gap), r_root_outer * math.sin(t_gap)))
            
            # B. Right Flank of Solid Tooth (outer root down to inner tip)
            for r in radii_in:
                cos_phi = max(-1.0, min(1.0, r_base / max(r_base, r)))
                phi = math.acos(cos_phi)
                theta = half_thick_angle + (inv(phi) - inv_alpha)
                t_curr = rot - theta
                ring_points.append((r * math.cos(t_curr), r * math.sin(t_curr)))
                
            # C. Tip Center of Solid Tooth (innermost point)
            ring_points.append((r_tip_inner * math.cos(rot), r_tip_inner * math.sin(rot)))
            
            # D. Left Flank of Solid Tooth (inner tip up to outer root)
            for r in radii_out:
                cos_phi = max(-1.0, min(1.0, r_base / max(r_base, r)))
                phi = math.acos(cos_phi)
                theta = half_thick_angle + (inv(phi) - inv_alpha)
                t_curr = rot + theta
                ring_points.append((r * math.cos(t_curr), r * math.sin(t_curr)))
                
        return ring_points

    @staticmethod
    def calculate_herringbone_twist_angle(
        face_width: float,
        pitch_radius: float,
        helix_angle_deg: float = 25.0
    ) -> float:
        """
        Calculates rotation twist in radians across half face-width for herringbone gear.
        """
        if pitch_radius <= 0.0 or helix_angle_deg <= 0.0:
            return 0.0
        beta_rad = math.radians(helix_angle_deg)
        half_w = face_width / 2.0
        lead = (2.0 * math.pi * pitch_radius) / math.tan(beta_rad)
        twist_rad = (2.0 * math.pi * half_w) / lead
        return twist_rad
