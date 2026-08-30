"""
Fusion 360 Planet Carrier Builder.
Creates high-strength Tri-Star / Spider carrier cages, bearing pins,
inter-stage sun couplings, and output shaft assemblies.
"""
import math
from typing import List, Tuple, Optional

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    adsk = None

class CarrierBuilder:
    """
    Builds realistic Spider / Tri-Star planet carriers in Fusion 360.
    """

    @classmethod
    def build_carrier_component(
        cls,
        target_component: 'adsk.fusion.Component',
        center_distance_mm: float,
        num_planets: int,
        pin_dia_mm: float,
        gear_face_width_mm: float,
        plate_thickness_mm: float = 4.0,
        output_shaft_dia_mm: float = 8.0,
        output_shaft_length_mm: float = 20.0,
        is_final_output_stage: bool = True,
        name: str = "Planet_Carrier"
    ) -> Optional['adsk.fusion.BRepBody']:
        """
        Constructs a Tri-Star / Spider carrier with axle pins and output shaft.
        """
        features = target_component.features
        sketches = target_component.sketches
        xy_plane = target_component.xYConstructionPlane

        cd_cm = center_distance_mm * 0.1
        pin_r_cm = (pin_dia_mm / 2.0) * 0.1
        boss_r_cm = (pin_dia_mm / 2.0 + 2.5) * 0.1
        plate_thick_cm = plate_thickness_mm * 0.1
        gear_w_cm = gear_face_width_mm * 0.1
        hub_r_cm = max((output_shaft_dia_mm / 2.0 + 3.0) * 0.1, 0.7)

        # 1. Base Spider Carrier Sketch on XY Plane
        spider_sketch = sketches.add(xy_plane)
        spider_sketch.name = f"{name}_Spider_Sketch"
        spider_sketch.isComputeDeferred = True

        circles = spider_sketch.sketchCurves.sketchCircles
        lines = spider_sketch.sketchCurves.sketchLines

        # Center Hub Circle
        circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), hub_r_cm)

        # Planet Boss Circles & Connecting Arms
        for i in range(num_planets):
            angle = (2.0 * math.pi * i) / num_planets
            px = cd_cm * math.cos(angle)
            py = cd_cm * math.sin(angle)

            # Boss circle around each planet axle
            circles.addByCenterRadius(adsk.core.Point3D.create(px, py, 0), boss_r_cm)

            # Tangent arm lines connecting center hub to boss
            arm_half_w = (pin_dia_mm / 2.0 + 1.0) * 0.1
            perp_angle = angle + (math.pi / 2.0)
            dx = arm_half_w * math.cos(perp_angle)
            dy = arm_half_w * math.sin(perp_angle)

            # Lines
            p_hub1 = adsk.core.Point3D.create(hub_r_cm * math.cos(angle) + dx, hub_r_cm * math.sin(angle) + dy, 0)
            p_pin1 = adsk.core.Point3D.create(px + dx, py + dy, 0)
            p_hub2 = adsk.core.Point3D.create(hub_r_cm * math.cos(angle) - dx, hub_r_cm * math.sin(angle) - dy, 0)
            p_pin2 = adsk.core.Point3D.create(px - dx, py - dy, 0)

            lines.addByTwoPoints(p_hub1, p_pin1)
            lines.addByTwoPoints(p_hub2, p_pin2)

        spider_sketch.isComputeDeferred = False

        # Select the outer combined carrier profile
        target_prof = None
        max_area = 0.0
        for p in spider_sketch.profiles:
            area = p.areaProperties().area
            if area > max_area:
                max_area = area
                target_prof = p

        if not target_prof:
            target_prof = spider_sketch.profiles.item(0)

        # Extrude Carrier Spider Plate (Positioned at Z = -plate_thick to Z = 0)
        extrudes = features.extrudeFeatures
        ext_input = extrudes.createInput(target_prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        dist = adsk.core.ValueInput.createByReal(-plate_thick_cm)
        ext_input.setDistanceExtent(False, dist)
        carrier_extrude = extrudes.add(ext_input)
        carrier_body = carrier_extrude.bodies.item(0)
        carrier_body.name = name

        # 2. Extrude Planet Axle Pins (Z = 0 to Z = gear_face_width + 0.5mm)
        for i in range(num_planets):
            angle = (2.0 * math.pi * i) / num_planets
            px = cd_cm * math.cos(angle)
            py = cd_cm * math.sin(angle)

            pin_sketch = sketches.add(xy_plane)
            pin_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(px, py, 0), pin_r_cm
            )
            pin_prof = pin_sketch.profiles.item(0)

            pin_input = extrudes.createInput(pin_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            pin_dist = adsk.core.ValueInput.createByReal(gear_w_cm + 0.05)
            pin_input.setDistanceExtent(False, pin_dist)
            pin_input.participantBodies = [carrier_body]
            extrudes.add(pin_input)

        # 3. Output Shaft (if final stage) or Inter-Stage Coupler
        if is_final_output_stage and output_shaft_dia_mm > 0.0:
            shaft_sketch = sketches.add(xy_plane)
            shaft_r_cm = (output_shaft_dia_mm / 2.0) * 0.1
            
            # Round shaft with D-flat for setscrews
            d_flat_depth_mm = 0.5
            d_flat_cm = d_flat_depth_mm * 0.1
            y_flat = shaft_r_cm - d_flat_cm
            x_half = math.sqrt(max(0.0001, shaft_r_cm**2 - y_flat**2))
            
            p1 = adsk.core.Point3D.create(-x_half, y_flat, 0)
            p2 = adsk.core.Point3D.create(x_half, y_flat, 0)
            shaft_sketch.sketchCurves.sketchLines.addByTwoPoints(p1, p2)
            
            center = adsk.core.Point3D.create(0, 0, 0)
            shaft_sketch.sketchCurves.sketchArcs.addByCenterStartSweep(
                center, p2, 2.0 * math.pi - 2.0 * math.asin(x_half / shaft_r_cm)
            )
            
            shaft_prof = shaft_sketch.profiles.item(0)
            shaft_input = extrudes.createInput(shaft_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            # Extrude output shaft forward through top cover
            shaft_len_cm = (gear_w_cm + output_shaft_length_mm * 0.1)
            shaft_dist = adsk.core.ValueInput.createByReal(shaft_len_cm)
            shaft_input.setDistanceExtent(False, shaft_dist)
            shaft_input.participantBodies = [carrier_body]
            extrudes.add(shaft_input)

        return carrier_body
