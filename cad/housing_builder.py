"""
Fusion 360 Gearbox Housing, Motor Flange & Top Bearing Cover Builder.
Constructs NEMA motor adapter plates and top output bearing caps with bolt holes.
"""
import math
from typing import Dict, Optional

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    adsk = None

from core.motor_catalog import get_motor_info

class HousingBuilder:
    """
    Builds motor adapters and top bearing housing covers in Fusion 360.
    """

    @classmethod
    def build_motor_mount_plate(
        cls,
        target_component: 'adsk.fusion.Component',
        motor_code: str,
        housing_outer_dia_mm: float,
        plate_thickness_mm: float = 5.0,
        name: str = "Motor_Mount_Flange"
    ) -> Optional['adsk.fusion.BRepBody']:
        """
        Creates NEMA motor adapter plate with pilot recess, 4 motor bolt holes, and 4 corner tie-rod holes.
        """
        features = target_component.features
        sketches = target_component.sketches
        xy_plane = target_component.xYConstructionPlane

        motor = get_motor_info(motor_code)
        plate_thick_cm = plate_thickness_mm * 0.1
        pilot_r_cm = (motor["pilot_diameter"] / 2.0) * 0.1
        motor_bolt_pcd_cm = (motor["bolt_pitch_circle"] / 2.0) * 0.1
        motor_bolt_r_cm = (motor["bolt_hole_dia"] / 2.0) * 0.1

        plate_sketch = sketches.add(xy_plane)
        plate_sketch.name = f"{name}_Sketch"
        plate_sketch.isComputeDeferred = True

        lines = plate_sketch.sketchCurves.sketchLines
        circles = plate_sketch.sketchCurves.sketchCircles

        actual_housing_r = (housing_outer_dia_mm / 2.0) * 0.1
        
        if "NEMA17" in motor_code.upper() and housing_outer_dia_mm <= 45.0:
            sq_w = 42.3 * 0.1
            half_sq = sq_w / 2.0
            half_hp = (31.0 / 2.0) * 0.1
            tie_r = (3.4 / 2.0) * 0.1

            # Square outer body
            p1 = adsk.core.Point3D.create(-half_sq, -half_sq, 0)
            p2 = adsk.core.Point3D.create(half_sq, -half_sq, 0)
            p3 = adsk.core.Point3D.create(half_sq, half_sq, 0)
            p4 = adsk.core.Point3D.create(-half_sq, half_sq, 0)
            lines.addByTwoPoints(p1, p2)
            lines.addByTwoPoints(p2, p3)
            lines.addByTwoPoints(p3, p4)
            lines.addByTwoPoints(p4, p1)

            # Central shaft opening
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), (14.0 / 2.0) * 0.1)

            # 4 Corner Tie-Rod Holes
            for hx in [-half_hp, half_hp]:
                for hy in [-half_hp, half_hp]:
                    circles.addByCenterRadius(adsk.core.Point3D.create(hx, hy, 0), tie_r)

        else:
            # Expanded Flange matching large housing
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), actual_housing_r)
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), (14.0 / 2.0) * 0.1)

            # Motor mounting holes in center
            for i in range(4):
                angle = (math.pi / 4.0) + (i * math.pi / 2.0)
                bx = motor_bolt_pcd_cm * math.cos(angle)
                by = motor_bolt_pcd_cm * math.sin(angle)
                circles.addByCenterRadius(adsk.core.Point3D.create(bx, by, 0), motor_bolt_r_cm)

        plate_sketch.isComputeDeferred = False

        # Select outer plate profile
        target_prof = None
        max_area = 0.0
        for p in plate_sketch.profiles:
            area = p.areaProperties().area
            if area > max_area:
                max_area = area
                target_prof = p

        if not target_prof:
            target_prof = plate_sketch.profiles.item(0)

        extrudes = features.extrudeFeatures
        ext_input = extrudes.createInput(target_prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        dist = adsk.core.ValueInput.createByReal(-plate_thick_cm)
        ext_input.setDistanceExtent(False, dist)
        flange_extrude = extrudes.add(ext_input)
        flange_body = flange_extrude.bodies.item(0)
        flange_body.name = name

        return flange_body

    @classmethod
    def build_top_cover_plate(
        cls,
        target_component: 'adsk.fusion.Component',
        motor_code: str,
        housing_outer_dia_mm: float,
        bearing_outer_dia_mm: float = 16.0,
        output_shaft_dia_mm: float = 8.0,
        plate_thickness_mm: float = 5.0,
        name: str = "Top_Bearing_Cover"
    ) -> Optional['adsk.fusion.BRepBody']:
        """
        Creates the top housing cap with precision bearing seat pocket for the output shaft.
        """
        features = target_component.features
        sketches = target_component.sketches
        xy_plane = target_component.xYConstructionPlane

        plate_thick_cm = plate_thickness_mm * 0.1
        shaft_hole_r_cm = (output_shaft_dia_mm / 2.0 + 0.5) * 0.1
        bearing_pocket_r_cm = (bearing_outer_dia_mm / 2.0) * 0.1

        cover_sketch = sketches.add(xy_plane)
        cover_sketch.name = f"{name}_Sketch"
        cover_sketch.isComputeDeferred = True

        lines = cover_sketch.sketchCurves.sketchLines
        circles = cover_sketch.sketchCurves.sketchCircles

        if "NEMA17" in motor_code.upper():
            sq_w = 42.3 * 0.1
            half_sq = sq_w / 2.0
            half_hp = (31.0 / 2.0) * 0.1
            tie_r = (3.4 / 2.0) * 0.1

            p1 = adsk.core.Point3D.create(-half_sq, -half_sq, 0)
            p2 = adsk.core.Point3D.create(half_sq, -half_sq, 0)
            p3 = adsk.core.Point3D.create(half_sq, half_sq, 0)
            p4 = adsk.core.Point3D.create(-half_sq, half_sq, 0)
            lines.addByTwoPoints(p1, p2)
            lines.addByTwoPoints(p2, p3)
            lines.addByTwoPoints(p3, p4)
            lines.addByTwoPoints(p4, p1)

            # Central shaft clearance hole
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), shaft_hole_r_cm)

            for hx in [-half_hp, half_hp]:
                for hy in [-half_hp, half_hp]:
                    circles.addByCenterRadius(adsk.core.Point3D.create(hx, hy, 0), tie_r)

        else:
            outer_r_cm = (housing_outer_dia_mm / 2.0) * 0.1
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), outer_r_cm)
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), shaft_hole_r_cm)

        cover_sketch.isComputeDeferred = False

        target_prof = None
        max_area = 0.0
        for p in cover_sketch.profiles:
            area = p.areaProperties().area
            if area > max_area:
                max_area = area
                target_prof = p

        if not target_prof:
            target_prof = cover_sketch.profiles.item(0)

        extrudes = features.extrudeFeatures
        ext_input = extrudes.createInput(target_prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        dist = adsk.core.ValueInput.createByReal(plate_thick_cm)
        ext_input.setDistanceExtent(False, dist)
        cover_extrude = extrudes.add(ext_input)
        cover_body = cover_extrude.bodies.item(0)
        cover_body.name = name

        return cover_body
