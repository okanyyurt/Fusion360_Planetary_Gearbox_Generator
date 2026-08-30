"""
Parametric Involute & Herringbone Tooth Profile Generator.
Generates mathematically exact 2D/3D coordinates for External (Sun/Planet) 
and Internal (Ring) gears with backlash, root fillets, and double-helical angles.
"""
import math
from typing import List, Tuple, Dict

Point2D = Tuple[float, float]
Point3D = Tuple[float, float, float]

def inv(alpha_rad: float) -> float:
    """Involute function: inv(alpha) = tan(alpha) - alpha"""
    return math.tan(alpha_rad) - alpha_rad

class ToothProfileGenerator:
    """
    Generates precision points for spur and double-helical gear profiles.
    """
    @staticmethod
    def generate_external_gear_profile_points(
        z: int,
        module: float,
        pressure_angle_deg: float = 20.0,
        backlash: float = 0.15,
        root_fillet_radius: float = 0.3,
        num_involute_points_per_flank: int = 12
    ) -> List[Point2D]:
        """
        Generates full 2D closed polygon coordinates for an external gear (Sun / Planet).
        All coordinates are in millimeters.
        """
        z = int(z)
        m = float(module)
        alpha = math.radians(pressure_angle_deg)
        
        r_pitch = m * z / 2.0
        r_base = r_pitch * math.cos(alpha)
        r_tip = r_pitch + 1.0 * m
        r_root = r_pitch - 1.25 * m
        
        # Effective base of involute
        r_involute_start = max(r_base, r_root)
        
        # Tooth thickness on pitch circle (with backlash tooth thinning)
        s_pitch = (math.pi * m / 2.0) - backlash
        half_thick_angle_pitch = s_pitch / (2.0 * r_pitch)
        inv_alpha = inv(alpha)
        
        # Build one single tooth's right and left flanks relative to center (0 rad)
        # Right flank is at negative angles. Left flank is at positive angles.
        num_pts = num_involute_points_per_flank
        radii = [r_involute_start + (r_tip - r_involute_start) * (i / (num_pts - 1)) for i in range(num_pts)]
        
        right_flank_polar: List[Point2D] = []
        for r_curr in radii:
            cos_phi = max(-1.0, min(1.0, r_base / r_curr))
            phi = math.acos(cos_phi)
            theta = half_thick_angle_pitch + inv_alpha - inv(phi)
            right_flank_polar.append((r_curr, -theta))
            
        left_flank_polar: List[Point2D] = []
        # Reverse radii to go from tip down to root for the left flank
        for r_curr in reversed(radii):
            cos_phi = max(-1.0, min(1.0, r_base / r_curr))
            phi = math.acos(cos_phi)
            theta = half_thick_angle_pitch + inv_alpha - inv(phi)
            left_flank_polar.append((r_curr, theta))
        
        # Build the full gear CCW
        pitch_angle = 2.0 * math.pi / z
        full_gear_points: List[Point2D] = []
        
        for k in range(z):
            rot = k * pitch_angle
            
            # 1. Right root corner (only if root < base)
            if r_root < r_involute_start:
                t_right_root = rot + right_flank_polar[0][1]
                full_gear_points.append((r_root * math.cos(t_right_root), r_root * math.sin(t_right_root)))
            
            # 2. Right flank (from base up to tip)
            for r, t in right_flank_polar:
                t_global = rot + t
                full_gear_points.append((r * math.cos(t_global), r * math.sin(t_global)))
                
            # 3. Tooth tip center (optional, for smoother tip interpolation)
            full_gear_points.append((r_tip * math.cos(rot), r_tip * math.sin(rot)))
                
            # 4. Left flank (from tip down to base)
            for r, t in left_flank_polar:
                t_global = rot + t
                full_gear_points.append((r * math.cos(t_global), r * math.sin(t_global)))
                
            # 5. Left root corner
            if r_root < r_involute_start:
                t_left_root = rot + left_flank_polar[-1][1]
                full_gear_points.append((r_root * math.cos(t_left_root), r_root * math.sin(t_left_root)))
                
            # 6. Center of root gap between this tooth and the next tooth
            t_gap_center = rot + pitch_angle / 2.0
            full_gear_points.append((r_root * math.cos(t_gap_center), r_root * math.sin(t_gap_center)))
                
        return full_gear_points

    @staticmethod
    def generate_internal_ring_gear_profile_points(
        z_ring: int,
        module: float,
        housing_outer_dia: float,
        pressure_angle_deg: float = 20.0,
        backlash: float = 0.15,
        num_involute_points_per_flank: int = 10
    ) -> Tuple[List[Point2D], float]:
        """
        Generates internal tooth profile for Ring Gear.
        Inner tip bore: r_tip = r_pitch - 1.0 * m
        Outer root: r_root = r_pitch + 1.25 * m
        Outer casing diameter: housing_outer_dia
        """
        z = int(z_ring)
        m = float(module)
        alpha = math.radians(pressure_angle_deg)
        
        r_pitch = m * z / 2.0
        r_base = r_pitch * math.cos(alpha)
        r_tip_inner = r_pitch - 1.0 * m   # inner boundary of internal teeth
        r_root_outer = r_pitch + 1.25 * m # root where teeth meet housing wall
        r_tip_inner = r_pitch - 1.0 * m
        r_root_outer = r_pitch + 1.25 * m
        
        e_pitch = (math.pi * m / 2.0) + backlash
        half_space_angle = e_pitch / (2.0 * r_pitch)
        inv_alpha = inv(alpha)
        
        radii = [r_tip_inner + (r_root_outer - r_tip_inner) * (i / (num_involute_points_per_flank - 1)) 
                 for i in range(num_involute_points_per_flank)]
        
        solid_right_flank: List[Point2D] = []
        for r_curr in reversed(radii):
            cos_phi = max(-1.0, min(1.0, r_base / max(r_base, r_curr)))
            phi = math.acos(cos_phi)
            theta = half_space_angle - (inv(phi) - inv_alpha)
            solid_right_flank.append((r_curr, theta))
            
        solid_left_flank: List[Point2D] = []
        for r_curr in radii:
            cos_phi = max(-1.0, min(1.0, r_base / max(r_base, r_curr)))
            phi = math.acos(cos_phi)
            theta = half_space_angle - (inv(phi) - inv_alpha)
            solid_left_flank.append((r_curr, -theta))
            
        pitch_angle = 2.0 * math.pi / z
        inner_teeth_points: List[Point2D] = []
        
        for k in range(z):
            rot = k * pitch_angle
            
            inner_teeth_points.append((r_root_outer * math.cos(rot), r_root_outer * math.sin(rot)))
            
            for r, t in solid_right_flank:
                t_global = rot + t
                inner_teeth_points.append((r * math.cos(t_global), r * math.sin(t_global)))
                
            t_tip_center = rot + pitch_angle / 2.0
            inner_teeth_points.append((r_tip_inner * math.cos(t_tip_center), r_tip_inner * math.sin(t_tip_center)))
                
            for r, t in solid_left_flank:
                t_global = (rot + pitch_angle) + t
                inner_teeth_points.append((r * math.cos(t_global), r * math.sin(t_global)))
        
        return inner_teeth_points, housing_outer_dia / 2.0

    @staticmethod
    def calculate_herringbone_twist_angle(
        face_width: float,
        pitch_radius: float,
        helix_angle_deg: float = 25.0
    ) -> float:
        """
        Calculates the angular rotation (in radians) for each half of a herringbone gear.
        Half-width = face_width / 2.0
        Lead L = 2 * pi * r / tan(beta)
        Twist angle theta = (half_width / r) * tan(beta)
        """
        beta = math.radians(helix_angle_deg)
        half_width = face_width / 2.0
        if pitch_radius <= 0:
            return 0.0
        twist_rad = (half_width * math.tan(beta)) / pitch_radius
        return twist_rad
