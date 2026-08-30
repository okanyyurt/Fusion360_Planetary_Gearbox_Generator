"""
Fusion 360 Planet Carrier Builder.
Creates high-strength Tri-Star / Spider carrier assemblies, axle pins,
and extended D-cut output shafts positioned visibly on top of the planet gears.
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
        z_base_mm: float = 2.0,
        plate_thickness_mm: float = 4.0,
        output_shaft_dia_mm: float = 8.0,
        output_shaft_length_mm: float = 20.0,
        is_final_output_stage: bool = True,
        name: str = "Planet_Carrier"
    ) -> Optional['adsk.fusion.BRepBody']:
        """
        Constructs a Tri-Star / Spider carrier with axle pins and output shaft.
        Spider plate sits on top of planet gears (Z = z_base + gear_face_width).
        Pins extend downwards into planet bores. Output shaft extends upwards.
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
        z_base_cm = z_base_mm * 0.1
        z_spider_top_cm = z_base_cm + gear_w_cm + plate_thick_cm
        hub_r_cm = max((output_shaft_dia_mm / 2.0 + 3.0) * 0.1, 0.8)

        # 1. Base Center Hub (Disk from Z = z_base + gear_w to Z = z_base + gear_w + plate_thick)
        hub_sketch = sketches.add(xy_plane)
        hub_sketch.name = f"{name}_Hub_Sketch"
        hub_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), hub_r_cm
        )
        hub_prof = hub_sketch.profiles.item(0)
        hub_input = extrudes.createInput(hub_prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        hub_input.setOffsetExtent(False, adsk.core.ValueInput.createByReal(z_base_cm + gear_w_cm))
        hub_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(plate_thick_cm))
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

            # Extrude Arm + Boss
            for prof in arm_sketch.profiles:
                arm_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                arm_input.setOffsetExtent(False, adsk.core.ValueInput.createByReal(z_base_cm + gear_w_cm))
                arm_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(plate_thick_cm))
                arm_input.participantBodies = [carrier_body]
                extrudes.add(arm_input)

        # 3. Planet Axle Pins (Extends DOWNWARDS from spider plate through planet gears: from z_spider_top down to z_base)
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
            pin_input.setOffsetExtent(False, adsk.core.ValueInput.createByReal(z_spider_top_cm))
            pin_dist = adsk.core.ValueInput.createByReal(-(gear_w_cm + plate_thick_cm))
            pin_input.setDistanceExtent(False, pin_dist)
            pin_input.participantBodies = [carrier_body]
            extrudes.add(pin_input)

        # 4. Output Shaft (Extends UPWARDS from spider top through top cover to the outside)
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
            shaft_input.setOffsetExtent(False, adsk.core.ValueInput.createByReal(z_spider_top_cm))
            shaft_len_cm = (output_shaft_length_mm * 0.1) + 0.5
            shaft_dist = adsk.core.ValueInput.createByReal(shaft_len_cm)
            shaft_input.setDistanceExtent(False, shaft_dist)
            shaft_input.participantBodies = [carrier_body]
            extrudes.add(shaft_input)

        return carrier_body
