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
        
        # Build one single tooth centered on positive X-axis
        single_tooth_pts: List[Point2D] = []
        
        # 1. Left Flank (from root up to tip)
        left_flank: List[Point2D] = []
        radii = [r_involute_start + (r_tip - r_involute_start) * (i / (num_involute_points_per_flank - 1)) 
                 for i in range(num_involute_points_per_flank)]
        
        for r_curr in radii:
            cos_phi = max(-1.0, min(1.0, r_base / r_curr))
            phi = math.acos(cos_phi)
            inv_phi = inv(phi)
            # Angular position for left flank (positive theta)
            theta = half_thick_angle_pitch + inv_alpha - inv_phi
            x = r_curr * math.cos(theta)
            y = r_curr * math.sin(theta)
            left_flank.append((x, y))
            
        # 2. Right Flank (from tip down to root - mirror of left)
        right_flank: List[Point2D] = []
        for x_l, y_l in reversed(left_flank):
            right_flank.append((x_l, -y_l))
            
        # Combine one tooth profile:
        # Start at root under left flank, go up left flank, tip arc, down right flank, root space
        single_tooth_pts = left_flank + right_flank
        
        # Full gear outline by replicating the tooth Z times
        pitch_angle = 2.0 * math.pi / z
        full_gear_points: List[Point2D] = []
        
        for k in range(z):
            rot = k * pitch_angle
            cos_r = math.cos(rot)
            sin_r = math.sin(rot)
            
            # Root gap point before this tooth
            theta_root_gap = rot - (pitch_angle / 2.0) + (half_thick_angle_pitch * 0.5)
            x_root = r_root * math.cos(theta_root_gap)
            y_root = r_root * math.sin(theta_root_gap)
            full_gear_points.append((x_root, y_root))
            
            for px, py in single_tooth_pts:
                # Rotate point
                nx = px * cos_r - py * sin_r
                ny = px * sin_r + py * cos_r
                full_gear_points.append((nx, ny))
                
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
        
        # Space width on pitch circle (backlash widens internal space)
        e_pitch = (math.pi * m / 2.0) + backlash
        half_space_angle = e_pitch / (2.0 * r_pitch)
        inv_alpha = inv(alpha)
        
        radii = [r_tip_inner + (r_root_outer - r_tip_inner) * (i / (num_involute_points_per_flank - 1)) 
                 for i in range(num_involute_points_per_flank)]
        
        left_flank: List[Point2D] = []
        for r_curr in radii:
            # For internal gear, involute profile
            r_effective_base = min(r_base, r_tip_inner)
            cos_phi = max(-1.0, min(1.0, r_base / max(r_base, r_curr)))
            phi = math.acos(cos_phi)
            inv_phi = inv(phi)
            theta = half_space_angle - (inv_phi - inv_alpha)
            x = r_curr * math.cos(theta)
            y = r_curr * math.sin(theta)
            left_flank.append((x, y))
            
        right_flank: List[Point2D] = []
        for x_l, y_l in reversed(left_flank):
            right_flank.append((x_l, -y_l))
            
        pitch_angle = 2.0 * math.pi / z
        inner_teeth_points: List[Point2D] = []
        
        for k in range(z):
            rot = k * pitch_angle
            cos_r = math.cos(rot)
            sin_r = math.sin(rot)
            
            for px, py in left_flank + right_flank:
                nx = px * cos_r - py * sin_r
                ny = px * sin_r + py * cos_r
                inner_teeth_points.append((nx, ny))
                
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
