"""
Fusion 360 Planet Carrier Builder.
Creates high-strength Tri-Star / Spider carrier assemblies, axle pins with spacer steps & DIN 471 circlip grooves,
inter-stage sun driver shafts, and extended D-cut output shafts.
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
    Builds Spider / Tri-Star planet carriers on exact Z planes in Fusion 360.
    """

    @staticmethod
    def get_z_plane(target_component: 'adsk.fusion.Component', z_offset_cm: float):
        """Returns or creates an XY construction plane at exact Z offset in cm."""
        if abs(z_offset_cm) < 0.0001:
            return target_component.xYConstructionPlane
        planes = target_component.constructionPlanes
        plane_input = planes.createInput()
        plane_input.setByOffset(target_component.xYConstructionPlane, adsk.core.ValueInput.createByReal(z_offset_cm))
        return planes.add(plane_input)

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
        Constructs a Tri-Star / Spider carrier with axle pins, bearing spacer steps,
        DIN 471 precision external circlip grooves, and output/driver shafts.
        """
        features = target_component.features
        sketches = target_component.sketches
        extrudes = features.extrudeFeatures

        cd_cm = center_distance_mm * 0.1
        pin_r_cm = (pin_dia_mm / 2.0) * 0.1
        boss_r_cm = (pin_dia_mm / 2.0 + 2.5) * 0.1
        plate_thick_cm = plate_thickness_mm * 0.1
        gear_w_cm = gear_face_width_mm * 0.1
        z_spider_plane_cm = (z_base_mm + gear_face_width_mm) * 0.1
        hub_r_cm = max((output_shaft_dia_mm / 2.0 + 3.0) * 0.1, 0.8)

        # Construction Plane right on top of the planet gears
        carrier_plane = cls.get_z_plane(target_component, z_spider_plane_cm)

        # 1. Base Center Hub
        hub_sketch = sketches.add(carrier_plane)
        hub_sketch.name = f"{name}_Hub_Sketch"
        hub_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), hub_r_cm
        )
        hub_prof = hub_sketch.profiles.item(0)
        hub_input = extrudes.createInput(hub_prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        hub_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(plate_thick_cm))
        hub_extrude = extrudes.add(hub_input)
        carrier_body = hub_extrude.bodies.item(0)
        carrier_body.name = name

        # 2. Build Spider Arms and Planet Bosses
        for i in range(num_planets):
            angle = (2.0 * math.pi * i) / num_planets
            px = cd_cm * math.cos(angle)
            py = cd_cm * math.sin(angle)

            arm_sketch = sketches.add(carrier_plane)
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

            # Extrude Arm + Boss upwards
            for prof in arm_sketch.profiles:
                arm_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                arm_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(plate_thick_cm))
                arm_input.participantBodies = [carrier_body]
                extrudes.add(arm_input)

        # 3. Planet Axle Pins, Spacer Steps & DIN 471 External Circlip Grooves
        groove_d2_mm = max(1.0, pin_dia_mm - 0.4)  # d2 groove diameter as per DIN 471
        groove_d2_r_cm = (groove_d2_mm / 2.0) * 0.1
        groove_w_cm = 0.09  # 0.9mm groove width (m)

        for i in range(num_planets):
            angle = (2.0 * math.pi * i) / num_planets
            px = cd_cm * math.cos(angle)
            py = cd_cm * math.sin(angle)

            # A. Axle Pin (Extends DOWNWARDS past the bottom of the planet gear)
            pin_sketch = sketches.add(carrier_plane)
            pin_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(px, py, 0), pin_r_cm
            )
            pin_prof = pin_sketch.profiles.item(0)

            pin_input = extrudes.createInput(pin_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            pin_total_len_cm = -(gear_w_cm + 0.25)  # 2.5mm extra length below planet gear
            pin_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(pin_total_len_cm))
            pin_input.participantBodies = [carrier_body]
            extrudes.add(pin_input)

            # B. Bearing Spacer Step (Fatura) under spider plate (0.8mm step)
            try:
                step_sketch = sketches.add(carrier_plane)
                step_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                    adsk.core.Point3D.create(px, py, 0), pin_r_cm + 0.08
                )
                step_prof = step_sketch.profiles.item(0)
                step_input = extrudes.createInput(step_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                step_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-0.08))
                step_input.participantBodies = [carrier_body]
                extrudes.add(step_input)
            except Exception:
                pass

            # C. DIN 471 Precision External Circlip Groove (Direct Cut into the pin)
            try:
                groove_z_mm = z_base_mm - 0.5  # 0.5mm below planet gear bottom
                groove_plane = cls.get_z_plane(target_component, groove_z_mm * 0.1)
                groove_sketch = sketches.add(groove_plane)
                groove_sketch.name = f"{name}_DIN471_Groove_Sketch_{i + 1}"
                
                # Outer clearing circle and inner d2 groove circle
                groove_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                    adsk.core.Point3D.create(px, py, 0), pin_r_cm + 0.15
                )
                groove_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                    adsk.core.Point3D.create(px, py, 0), groove_d2_r_cm
                )

                donut_prof = None
                for p in groove_sketch.profiles:
                    if p.profileLoops.count == 2:
                        donut_prof = p
                        break
                if not donut_prof:
                    donut_prof = groove_sketch.profiles.item(0)

                g_input = extrudes.createInput(donut_prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
                g_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-groove_w_cm))
                g_input.participantBodies = [carrier_body]
                extrudes.add(g_input)
            except Exception:
                pass

        # 4. Shaft Generation: Main Output Shaft vs Inter-Stage Driver Shaft
        top_plane = cls.get_z_plane(target_component, z_spider_plane_cm + plate_thick_cm)
        
        if is_final_output_stage:
            # Main Final Output Shaft (Ø8mm with D-cut, extends through top cover)
            if output_shaft_dia_mm > 0.0:
                shaft_sketch = sketches.add(top_plane)
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
                shaft_len_cm = (output_shaft_length_mm * 0.1)
                shaft_dist = adsk.core.ValueInput.createByReal(shaft_len_cm)
                shaft_input.setDistanceExtent(False, shaft_dist)
                shaft_input.participantBodies = [carrier_body]
                extrudes.add(shaft_input)

        else:
            # Inter-Stage Driver Shaft (Ø6mm D-shaft, length = 8mm, driving Stage 2/3 Sun Gear)
            inter_shaft_dia_mm = 6.0
            inter_shaft_r_cm = (inter_shaft_dia_mm / 2.0) * 0.1
            inter_sketch = sketches.add(top_plane)
            inter_sketch.name = f"{name}_InterStage_Shaft_Sketch"
            
            d_flat_cm = 0.5 * 0.1
            y_flat = inter_shaft_r_cm - d_flat_cm
            x_half = math.sqrt(max(0.0001, inter_shaft_r_cm**2 - y_flat**2))
            p1 = adsk.core.Point3D.create(-x_half, y_flat, 0)
            p2 = adsk.core.Point3D.create(x_half, y_flat, 0)
            inter_sketch.sketchCurves.sketchLines.addByTwoPoints(p1, p2)
            p_bottom = adsk.core.Point3D.create(0, -inter_shaft_r_cm, 0)
            inter_sketch.sketchCurves.sketchArcs.addByThreePoints(p2, p_bottom, p1)

            inter_prof = inter_sketch.profiles.item(0)
            inter_input = extrudes.createInput(inter_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            inter_dist = adsk.core.ValueInput.createByReal(8.0 * 0.1)  # 8mm inter-stage coupling length
            inter_input.setDistanceExtent(False, inter_dist)
            inter_input.participantBodies = [carrier_body]
            extrudes.add(inter_input)

        return carrier_body
