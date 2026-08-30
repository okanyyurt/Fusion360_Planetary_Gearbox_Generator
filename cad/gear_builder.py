"""
Fusion 360 3D B-Rep Gear Builder.
Constructs Sun Gear, Planet Gears, and Internal Ring Gear Enclosure using native
Fusion 360 parametric sketches, splines, and extrusions.
"""
import math
from typing import List, Tuple, Optional

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    adsk = None

from core.tooth_profile import ToothProfileGenerator, Point2D

class GearBuilder:
    """
    Builds native 3D gear components in Autodesk Fusion 360.
    """

    @staticmethod
    def _notify_progress(message: str) -> None:
        """Sends a progress message to the Fusion 360 palette UI via the HTML bridge."""
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            palette = ui.palettes.itemById('PlanetaryGearboxPalette_v1')
            if palette:
                import json
                palette.sendInfoToHTML('fusionMessageReceived', json.dumps({'event': 'progress', 'message': message}))
                adsk.doEvents()
        except Exception:
            pass

    @staticmethod
    def draw_closed_spline_from_points(sketch: 'adsk.fusion.Sketch', points_mm: List[Point2D]) -> None:
        """
        Draws a smooth closed fitted spline from 2D points in mm.
        Converts coordinates to Fusion 360 internal centimeters (cm).
        """
        if len(points_mm) < 3:
            return
        
        pts_obj = adsk.core.ObjectCollection.create()
        for p in points_mm:
            pts_obj.add(adsk.core.Point3D.create(p[0] * 0.1, p[1] * 0.1, 0.0))
            
        spline = sketch.sketchCurves.sketchFittedSplines.add(pts_obj)
        spline.isClosed = True

    @staticmethod
    def add_shaft_bore(
        sketch: 'adsk.fusion.Sketch', 
        shaft_dia_mm: float, 
        shaft_type: str = "ROUND",
        d_flat_depth_mm: float = 0.5,
        key_width_mm: float = 2.0,
        key_height_mm: float = 1.0,
        tolerance_offset_mm: float = 0.05
    ) -> None:
        """
        Adds center shaft cutout profile (Round, D-Cut, Double D-Cut, or Keyway) on sketch.
        """
        r_cm = (shaft_dia_mm / 2.0 + tolerance_offset_mm) * 0.1
        lines = sketch.sketchCurves.sketchLines
        circles = sketch.sketchCurves.sketchCircles
        
        if shaft_type == "ROUND" or not shaft_type:
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), r_cm)
            
        elif shaft_type == "D_CUT":
            d_flat_cm = d_flat_depth_mm * 0.1
            y_flat = r_cm - d_flat_cm
            if y_flat < r_cm and y_flat > -r_cm:
                x_half = math.sqrt(max(0.0001, r_cm**2 - y_flat**2))
                p1 = adsk.core.Point3D.create(-x_half, y_flat, 0)
                p2 = adsk.core.Point3D.create(x_half, y_flat, 0)
                lines.addByTwoPoints(p1, p2)
                
                center = adsk.core.Point3D.create(0, 0, 0)
                arcs = sketch.sketchCurves.sketchArcs
                arcs.addByCenterStartSweep(center, p2, 2.0 * math.pi - 2.0 * math.asin(x_half / r_cm))
            else:
                circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), r_cm)
                
        elif shaft_type == "DOUBLE_D":
            d_flat_cm = d_flat_depth_mm * 0.1
            y_top = r_cm - d_flat_cm
            y_bot = -y_top
            if y_top < r_cm:
                x_half = math.sqrt(max(0.0001, r_cm**2 - y_top**2))
                p_tr = adsk.core.Point3D.create(x_half, y_top, 0)
                p_tl = adsk.core.Point3D.create(-x_half, y_top, 0)
                p_br = adsk.core.Point3D.create(x_half, y_bot, 0)
                p_bl = adsk.core.Point3D.create(-x_half, y_bot, 0)
                
                lines.addByTwoPoints(p_tl, p_tr)
                lines.addByTwoPoints(p_bl, p_br)
                
                center = adsk.core.Point3D.create(0, 0, 0)
                arcs = sketch.sketchCurves.sketchArcs
                sweep_angle = math.pi - 2.0 * math.asin(x_half / r_cm)
                arcs.addByCenterStartSweep(center, p_tr, -sweep_angle)
                arcs.addByCenterStartSweep(center, p_bl, -sweep_angle)
            else:
                circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), r_cm)
                
        elif shaft_type == "KEYWAY":
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), r_cm)
            kw_cm = key_width_mm * 0.1
            kh_cm = key_height_mm * 0.1
            
            p1 = adsk.core.Point3D.create(-kw_cm / 2.0, r_cm, 0)
            p2 = adsk.core.Point3D.create(-kw_cm / 2.0, r_cm + kh_cm, 0)
            p3 = adsk.core.Point3D.create(kw_cm / 2.0, r_cm + kh_cm, 0)
            p4 = adsk.core.Point3D.create(kw_cm / 2.0, r_cm, 0)
            
            lines.addByTwoPoints(p1, p2)
            lines.addByTwoPoints(p2, p3)
            lines.addByTwoPoints(p3, p4)

    @classmethod
    def build_external_gear_body(
        cls,
        target_component: 'adsk.fusion.Component',
        z_teeth: int,
        module: float,
        face_width_mm: float,
        is_herringbone: bool = False,
        helix_angle_deg: float = 25.0,
        bore_dia_mm: float = 5.0,
        bore_type: str = "ROUND",
        d_flat_depth_mm: float = 0.5,
        pressure_angle_deg: float = 20.0,
        backlash_mm: float = 0.05,
        is_sun_gear: bool = False,
        name: str = "Gear"
    ) -> Optional['adsk.fusion.BRepBody']:
        """
        Builds complete precision external gear body (Sun or Planet).
        """
        features = target_component.features
        sketches = target_component.sketches
        xy_plane = target_component.xYConstructionPlane
        face_width_cm = face_width_mm * 0.1

        # 1. Generate 2D Profile Points
        points_mm = ToothProfileGenerator.generate_external_gear_polygon(
            z=z_teeth,
            module=module,
            pressure_angle_deg=pressure_angle_deg,
            backlash_mm=backlash_mm
        )

        # 2. Create Sketch
        gear_sketch = sketches.add(xy_plane)
        gear_sketch.name = f"{name}_Sketch"
        gear_sketch.isComputeDeferred = True

        # Draw outer tooth profile
        cls.draw_closed_spline_from_points(gear_sketch, points_mm)

        # Draw center bore (prevent bore larger than root circle)
        pitch_r = module * z_teeth / 2.0
        root_r = pitch_r - 1.25 * module
        safe_bore_dia = min(bore_dia_mm, (root_r * 2.0) - 2.0)
        
        if safe_bore_dia > 1.0:
            cls.add_shaft_bore(
                sketch=gear_sketch,
                shaft_dia_mm=safe_bore_dia,
                shaft_type=bore_type,
                d_flat_depth_mm=d_flat_depth_mm
            )

        gear_sketch.isComputeDeferred = False

        # Find gear profile (donut with center hole)
        prof = None
        for p in gear_sketch.profiles:
            if safe_bore_dia > 1.0:
                if p.profileLoops.count == 2:
                    prof = p
                    break
            else:
                prof = p
                break
        if not prof:
            prof = gear_sketch.profiles.item(0)

        # Extrude Gear Body
        extrudes = features.extrudeFeatures
        ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        dist = adsk.core.ValueInput.createByReal(face_width_cm)
        ext_input.setDistanceExtent(False, dist)
        gear_extrude = extrudes.add(ext_input)
        gear_body = gear_extrude.bodies.item(0)
        gear_body.name = name

        # If Sun gear with motor shaft, add integral motor shaft coupling collar on bottom
        if is_sun_gear and safe_bore_dia > 0:
            collar_dia_mm = max(safe_bore_dia + 5.0, 11.0)
            collar_len_mm = 6.0
            
            collar_sketch = sketches.add(xy_plane)
            collar_sketch.name = f"{name}_Collar_Sketch"
            collar_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(0, 0, 0), (collar_dia_mm / 2.0) * 0.1
            )
            cls.add_shaft_bore(
                sketch=collar_sketch,
                shaft_dia_mm=safe_bore_dia,
                shaft_type=bore_type,
                d_flat_depth_mm=d_flat_depth_mm
            )
            
            collar_prof = None
            for p in collar_sketch.profiles:
                if p.profileLoops.count == 2:
                    collar_prof = p
                    break
            if not collar_prof:
                collar_prof = collar_sketch.profiles.item(0)
                
            c_input = extrudes.createInput(collar_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            c_dist = adsk.core.ValueInput.createByReal(-(collar_len_mm * 0.1))
            c_input.setDistanceExtent(False, c_dist)
            extrudes.add(c_input)

        return gear_body

    @classmethod
    def build_internal_ring_gear_body(
        cls,
        target_component: 'adsk.fusion.Component',
        z_ring: int,
        module: float,
        face_width_mm: float,
        outer_housing_dia_mm: float,
        motor_code: str = "NEMA17",
        pressure_angle_deg: float = 20.0,
        backlash_mm: float = 0.05,
        name: str = "Ring_Gear_Housing"
    ) -> Optional['adsk.fusion.BRepBody']:
        """
        Builds the Complete Outer Ring Gear Housing Enclosure (NEMA square profile with corner bolt holes + internal teeth).
        """
        features = target_component.features
        sketches = target_component.sketches
        xy_plane = target_component.xYConstructionPlane
        face_width_cm = face_width_mm * 0.1

        # 1. Generate 2D Internal Teeth Points
        inner_points_mm = ToothProfileGenerator.generate_internal_ring_gear_polygon(
            z_ring=z_ring,
            module=module,
            pressure_angle_deg=pressure_angle_deg,
            backlash_mm=backlash_mm
        )

        # 2. Create Housing Sketch
        housing_sketch = sketches.add(xy_plane)
        housing_sketch.name = f"{name}_Sketch"
        housing_sketch.isComputeDeferred = True

        # Draw Internal Teeth Profile
        cls.draw_closed_spline_from_points(housing_sketch, inner_points_mm)

        # Draw Outer Housing Profile (NEMA 17 / 23 Square with corner bolt holes or Round)
        lines = housing_sketch.sketchCurves.sketchLines
        circles = housing_sketch.sketchCurves.sketchCircles

        if "NEMA17" in motor_code.upper():
            # NEMA 17: 42.3mm square, 31.0mm hole pitch (43.84mm PCD)
            sq_w = 42.3 * 0.1
            half_sq = sq_w / 2.0
            hole_pitch = 31.0 * 0.1
            half_hp = hole_pitch / 2.0
            hole_r = (3.4 / 2.0) * 0.1  # M3 bolt clearance hole

            # Square outer box
            p1 = adsk.core.Point3D.create(-half_sq, -half_sq, 0)
            p2 = adsk.core.Point3D.create(half_sq, -half_sq, 0)
            p3 = adsk.core.Point3D.create(half_sq, half_sq, 0)
            p4 = adsk.core.Point3D.create(-half_sq, half_sq, 0)
            lines.addByTwoPoints(p1, p2)
            lines.addByTwoPoints(p2, p3)
            lines.addByTwoPoints(p3, p4)
            lines.addByTwoPoints(p4, p1)

            # 4 Corner Bolt Holes
            for hx in [-half_hp, half_hp]:
                for hy in [-half_hp, half_hp]:
                    circles.addByCenterRadius(adsk.core.Point3D.create(hx, hy, 0), hole_r)

        elif "NEMA23" in motor_code.upper():
            # NEMA 23: 56.4mm square, 47.14mm hole pitch
            sq_w = 56.4 * 0.1
            half_sq = sq_w / 2.0
            half_hp = (47.14 / 2.0) * 0.1
            hole_r = (4.5 / 2.0) * 0.1  # M4 bolt hole

            p1 = adsk.core.Point3D.create(-half_sq, -half_sq, 0)
            p2 = adsk.core.Point3D.create(half_sq, -half_sq, 0)
            p3 = adsk.core.Point3D.create(half_sq, half_sq, 0)
            p4 = adsk.core.Point3D.create(-half_sq, half_sq, 0)
            lines.addByTwoPoints(p1, p2)
            lines.addByTwoPoints(p2, p3)
            lines.addByTwoPoints(p3, p4)
            lines.addByTwoPoints(p4, p1)

            for hx in [-half_hp, half_hp]:
                for hy in [-half_hp, half_hp]:
                    circles.addByCenterRadius(adsk.core.Point3D.create(hx, hy, 0), hole_r)

        else:
            # Round Housing with Outer Diameter
            outer_r_cm = (outer_housing_dia_mm / 2.0) * 0.1
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), outer_r_cm)

        housing_sketch.isComputeDeferred = False

        # Find housing profile (the body enclosing the internal gear teeth)
        target_prof = None
        max_area = 0.0
        for p in housing_sketch.profiles:
            area = p.areaProperties().area
            if area > max_area:
                max_area = area
                target_prof = p

        if not target_prof:
            target_prof = housing_sketch.profiles.item(0)

        # Extrude Housing Enclosure
        extrudes = features.extrudeFeatures
        ext_input = extrudes.createInput(target_prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        dist = adsk.core.ValueInput.createByReal(face_width_cm)
        ext_input.setDistanceExtent(False, dist)
        housing_extrude = extrudes.add(ext_input)
        ring_body = housing_extrude.bodies.item(0)
        ring_body.name = name

        return ring_body
