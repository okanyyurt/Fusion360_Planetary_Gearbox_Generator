"""
Fusion 360 Planet Carrier Builder.
Creates high-strength Tri-Star / Spider carrier assemblies, axle pins,
and extended D-cut output shafts as dedicated CAD components.
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
    Builds Spider / Tri-Star planet carriers in Fusion 360.
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
        extrudes = features.extrudeFeatures

        cd_cm = center_distance_mm * 0.1
        pin_r_cm = (pin_dia_mm / 2.0) * 0.1
        boss_r_cm = (pin_dia_mm / 2.0 + 2.5) * 0.1
        plate_thick_cm = plate_thickness_mm * 0.1
        gear_w_cm = gear_face_width_mm * 0.1
        hub_r_cm = max((output_shaft_dia_mm / 2.0 + 3.0) * 0.1, 0.8)

        # 1. Base Center Hub (Disk from Z = -plate_thick to Z = 0)
        hub_sketch = sketches.add(xy_plane)
        hub_sketch.name = f"{name}_Hub_Sketch"
        hub_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), hub_r_cm
        )
        hub_prof = hub_sketch.profiles.item(0)
        hub_input = extrudes.createInput(hub_prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        hub_dist = adsk.core.ValueInput.createByReal(-plate_thick_cm)
        hub_input.setDistanceExtent(False, hub_dist)
        hub_extrude = extrudes.add(hub_input)
        carrier_body = hub_extrude.bodies.item(0)
        carrier_body.name = name

        # 2. Build Spider Arms and Planet Bosses (Join to carrier_body)
        for i in range(num_planets):
            angle = (2.0 * math.pi * i) / num_planets
            px = cd_cm * math.cos(angle)
            py = cd_cm * math.sin(angle)

            arm_sketch = sketches.add(xy_plane)
            arm_sketch.isComputeDeferred = True
            
            # Boss circle at planet center
            arm_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(px, py, 0), boss_r_cm
            )

            # Connecting arm
            arm_half_w = (pin_dia_mm / 2.0 + 1.2) * 0.1
            perp_angle = angle + (math.pi / 2.0)
            dx = arm_half_w * math.cos(perp_angle)
            dy = arm_half_w * math.sin(perp_angle)

            lines = arm_sketch.sketchCurves.sketchLines
            p1 = adsk.core.Point3D.create(hub_r_cm * 0.6 * math.cos(angle) + dx, hub_r_cm * 0.6 * math.sin(angle) + dy, 0)
            p2 = adsk.core.Point3D.create(px + dx, py + dy, 0)
            p3 = adsk.core.Point3D.create(px - dx, py - dy, 0)
            p4 = adsk.core.Point3D.create(hub_r_cm * 0.6 * math.cos(angle) - dx, hub_r_cm * 0.6 * math.sin(angle) - dy, 0)

            lines.addByTwoPoints(p1, p2)
            lines.addByTwoPoints(p2, p3)
            lines.addByTwoPoints(p3, p4)
            lines.addByTwoPoints(p4, p1)

            arm_sketch.isComputeDeferred = False

            # Extrude Arm + Boss downwards
            for prof in arm_sketch.profiles:
                arm_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                arm_input.setDistanceExtent(False, hub_dist)
                arm_input.participantBodies = [carrier_body]
                extrudes.add(arm_input)

        # 3. Planet Axle Pins (Extends upwards: Z = 0 to Z = gear_face_width + 1.0mm)
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
            pin_dist = adsk.core.ValueInput.createByReal(gear_w_cm + 0.1)
            pin_input.setDistanceExtent(False, pin_dist)
            pin_input.participantBodies = [carrier_body]
            extrudes.add(pin_input)

        # 4. Output Shaft (Extends upwards through top cover to the outside)
        if is_final_output_stage and output_shaft_dia_mm > 0.0:
            shaft_sketch = sketches.add(xy_plane)
            shaft_r_cm = (output_shaft_dia_mm / 2.0) * 0.1
            d_flat_depth_mm = 0.6
            d_flat_cm = d_flat_depth_mm * 0.1
            y_flat = shaft_r_cm - d_flat_cm

            if y_flat < shaft_r_cm and y_flat > -shaft_r_cm:
                x_half = math.sqrt(max(0.0001, shaft_r_cm**2 - y_flat**2))
                p1 = adsk.core.Point3D.create(-x_half, y_flat, 0)
                p2 = adsk.core.Point3D.create(x_half, y_flat, 0)
                shaft_sketch.sketchCurves.sketchLines.addByTwoPoints(p1, p2)
                
                p_bottom = adsk.core.Point3D.create(0, -shaft_r_cm, 0)
                shaft_sketch.sketchCurves.sketchArcs.addByThreePoints(p2, p_bottom, p1)
            else:
                shaft_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                    adsk.core.Point3D.create(0, 0, 0), shaft_r_cm
                )

            shaft_prof = shaft_sketch.profiles.item(0)
            shaft_input = extrudes.createInput(shaft_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            # Total shaft length extends past the gears and past the top cover
            total_shaft_cm = gear_w_cm + (output_shaft_length_mm * 0.1) + 0.5
            shaft_dist = adsk.core.ValueInput.createByReal(total_shaft_cm)
            shaft_input.setDistanceExtent(False, shaft_dist)
            shaft_input.participantBodies = [carrier_body]
            extrudes.add(shaft_input)

        return carrier_body
