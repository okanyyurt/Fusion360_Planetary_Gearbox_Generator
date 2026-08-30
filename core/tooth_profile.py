"""
Parametric Involute & Herringbone Tooth Profile Generator.
Based on Autodesk Fusion 360 native SpurGear CAD standards.
"""
import math
from typing import List, Tuple, Dict

Point2D = Tuple[float, float]
Point3D = Tuple[float, float, float]

def involute_point(base_circle_radius: float, dist_from_center: float) -> Tuple[float, float]:
    """
    Autodesk standard involute curve point calculator.
    Returns (x, y) coordinates for a point at distance dist_from_center from gear center.
    """
    if dist_from_center < base_circle_radius:
        dist_from_center = base_circle_radius
        
    triangle_side = math.sqrt(max(0.0, dist_from_center**2 - base_circle_radius**2))
    alpha = triangle_side / base_circle_radius
    ratio = max(-1.0, min(1.0, base_circle_radius / dist_from_center))
    theta = alpha - math.acos(ratio)
    
    x = dist_from_center * math.cos(theta)
    y = dist_from_center * math.sin(theta)
    return x, y

class ToothProfileGenerator:
    """
    High-precision involute tooth generator following Autodesk Fusion 360 standards.
    Outputs coordinates in centimeters (Fusion 360 internal units).
    """

    @staticmethod
    def get_external_tooth_geometry(
        z: int, 
        module: float, 
        pressure_angle_deg: float = 20.0, 
        backlash_mm: float = 0.05,
        num_involute_points: int = 15
    ) -> Dict:
        """
        Calculates Autodesk-standard tooth profile for Sun and Planet gears.
        All returned radial dimensions and points are in Centimeters (cm).
        """
        m_cm = module * 0.1
        pa_rad = math.radians(pressure_angle_deg)
        pitch_dia_cm = z * m_cm
        pitch_r_cm = pitch_dia_cm / 2.0
        dedendum_cm = 1.157 * m_cm
        root_r_cm = pitch_r_cm - dedendum_cm
        base_r_cm = pitch_r_cm * math.cos(pa_rad)
        outside_r_cm = (z + 2.0) * m_cm / 2.0
        
        inv_pts = []
        inv_size = outside_r_cm - base_r_cm
        for i in range(num_involute_points):
            r_curr = base_r_cm + (inv_size / (num_involute_points - 1)) * i
            inv_pts.append(involute_point(base_r_cm, r_curr))
            
        pitch_inv_pt = involute_point(base_r_cm, pitch_r_cm)
        pitch_pt_angle = math.atan2(pitch_inv_pt[1], pitch_inv_pt[0])
        
        tooth_thick_angle = math.pi / z
        backlash_cm = backlash_mm * 0.1
        backlash_angle = backlash_cm / pitch_r_cm
        rotate_angle = -((tooth_thick_angle / 2.0) - backlash_angle + pitch_pt_angle)
        
        cos_a = math.cos(rotate_angle)
        sin_a = math.sin(rotate_angle)
        
        spline1_pts = []
        spline2_pts = []
        for x, y in inv_pts:
            rx = x * cos_a - y * sin_a
            ry = x * sin_a + y * cos_a
            spline1_pts.append((rx, ry))
            spline2_pts.append((rx, -ry))
            
        return {
            'num_teeth': z,
            'module_cm': m_cm,
            'pitch_r_cm': pitch_r_cm,
            'root_r_cm': root_r_cm,
            'base_r_cm': base_r_cm,
            'outside_r_cm': outside_r_cm,
            'spline1_pts': spline1_pts,
            'spline2_pts': spline2_pts
        }

    @staticmethod
    def get_internal_ring_tooth_geometry(
        z_ring: int, 
        module: float, 
        housing_outer_dia_mm: float,
        pressure_angle_deg: float = 20.0, 
        backlash_mm: float = 0.05,
        num_involute_points: int = 15
    ) -> Dict:
        """
        Calculates Autodesk-standard internal tooth profile for Ring gear housing.
        All returned radial dimensions and points are in Centimeters (cm).
        """
        m_cm = module * 0.1
        pa_rad = math.radians(pressure_angle_deg)
        pitch_dia_cm = z_ring * m_cm
        pitch_r_cm = pitch_dia_cm / 2.0
        
        # In internal ring gears:
        # Root is the outer circle where teeth meet housing wall
        dedendum_cm = 1.157 * m_cm
        root_r_cm = pitch_r_cm + dedendum_cm
        # Tip is the innermost circle (addendum points inward)
        addendum_cm = 1.0 * m_cm
        tip_r_cm = pitch_r_cm - addendum_cm
        base_r_cm = pitch_r_cm * math.cos(pa_rad)
        housing_outer_r_cm = (housing_outer_dia_mm / 2.0) * 0.1
        
        # Effective base of involute for internal tooth
        r_start = max(base_r_cm, tip_r_cm)
        inv_size = root_r_cm - r_start
        inv_pts = []
        for i in range(num_involute_points):
            r_curr = r_start + (inv_size / (num_involute_points - 1)) * i
            inv_pts.append(involute_point(base_r_cm, r_curr))
            
        pitch_inv_pt = involute_point(base_r_cm, pitch_r_cm)
        pitch_pt_angle = math.atan2(pitch_inv_pt[1], pitch_inv_pt[0])
        
        # Solid tooth thickness on pitch circle
        tooth_thick_angle = math.pi / z_ring
        backlash_cm = backlash_mm * 0.1
        backlash_angle = backlash_cm / pitch_r_cm
        rotate_angle = -((tooth_thick_angle / 2.0) - backlash_angle + pitch_pt_angle)
        
        cos_a = math.cos(rotate_angle)
        sin_a = math.sin(rotate_angle)
        
        spline1_pts = []
        spline2_pts = []
        for x, y in inv_pts:
            rx = x * cos_a - y * sin_a
            ry = x * sin_a + y * cos_a
            spline1_pts.append((rx, ry))
            spline2_pts.append((rx, -ry))
            
        return {
            'num_teeth': z_ring,
            'module_cm': m_cm,
            'pitch_r_cm': pitch_r_cm,
            'root_r_cm': root_r_cm,
            'tip_r_cm': tip_r_cm,
            'base_r_cm': base_r_cm,
            'housing_outer_r_cm': housing_outer_r_cm,
            'spline1_pts': spline1_pts,
            'spline2_pts': spline2_pts
        }

    @staticmethod
    def calculate_herringbone_twist_angle(
        face_width: float,
        pitch_radius: float,
        helix_angle_deg: float = 25.0
    ) -> float:
        """
        Calculates rotation twist in radians across half face-width for herringbone gear.
        twist = (face_width / 2) * tan(beta) / pitch_radius
        """
        if pitch_radius <= 0.0 or helix_angle_deg <= 0.0:
            return 0.0
        beta_rad = math.radians(helix_angle_deg)
        half_w = face_width / 2.0
        lead = (2.0 * math.pi * pitch_radius) / math.tan(beta_rad)
        twist_rad = (2.0 * math.pi * half_w) / lead
        return twist_rad
