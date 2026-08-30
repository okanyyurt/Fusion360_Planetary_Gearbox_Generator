"""
Parametric Involute Tooth Geometry Engine.
Generates mathematically exact single tooth and space profiles for native
Fusion 360 feature operations (Extrude + Circular Pattern).
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
    High-precision involute geometry calculator for native Fusion 360 CAD modeling.
    Outputs dimensions and coordinates in Centimeters (cm).
    """

    @staticmethod
    def get_external_tooth_features(
        z: int, 
        module: float, 
        pressure_angle_deg: float = 20.0, 
        backlash_mm: float = 0.05,
        num_involute_points: int = 12
    ) -> Dict:
        """
        Calculates Autodesk-standard tooth profile for Sun and Planet gears.
        Returns radial parameters and single tooth flank splines in centimeters (cm).
        """
        z = int(z)
        m_cm = float(module) * 0.1
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
    def get_internal_tooth_space_features(
        z_ring: int, 
        module: float, 
        pressure_angle_deg: float = 20.0, 
        backlash_mm: float = 0.05,
        num_involute_points: int = 12
    ) -> Dict:
        """
        Calculates the exact involute tooth space pocket for Internal Ring Gear cut operation.
        Returns radial parameters and space pocket flank splines in centimeters (cm).
        """
        z_r = int(z_ring)
        m_cm = float(module) * 0.1
        pa_rad = math.radians(pressure_angle_deg)
        pitch_dia_cm = z_r * m_cm
        pitch_r_cm = pitch_dia_cm / 2.0
        
        # In internal ring gear:
        # tip_r is inner cylinder bore
        tip_r_cm = pitch_r_cm - 1.0 * m_cm
        # root_r is the outer bottom of the tooth space
        root_r_cm = pitch_r_cm + 1.25 * m_cm
        base_r_cm = pitch_r_cm * math.cos(pa_rad)
        
        r_inv_start = max(base_r_cm, tip_r_cm)
        inv_size = root_r_cm - r_inv_start
        
        inv_pts = []
        for i in range(num_involute_points):
            r_curr = r_inv_start + (inv_size / (num_involute_points - 1)) * i
            inv_pts.append(involute_point(base_r_cm, r_curr))
            
        pitch_inv_pt = involute_point(base_r_cm, pitch_r_cm)
        pitch_pt_angle = math.atan2(pitch_inv_pt[1], pitch_inv_pt[0])
        
        space_angle = (math.pi / z_r) + ((backlash_mm * 0.1) / pitch_r_cm)
        rotate_angle = -((space_angle / 2.0) + pitch_pt_angle)
        
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
            'num_teeth': z_r,
            'module_cm': m_cm,
            'pitch_r_cm': pitch_r_cm,
            'tip_r_cm': tip_r_cm,
            'root_r_cm': root_r_cm,
            'base_r_cm': base_r_cm,
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
        """
        if pitch_radius <= 0.0 or helix_angle_deg <= 0.0:
            return 0.0
        beta_rad = math.radians(helix_angle_deg)
        half_w = face_width / 2.0
        lead = (2.0 * math.pi * pitch_radius) / math.tan(beta_rad)
        twist_rad = (2.0 * math.pi * half_w) / lead
        return twist_rad
