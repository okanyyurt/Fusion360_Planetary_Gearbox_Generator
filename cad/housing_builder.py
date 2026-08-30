"""
Fusion 360 Gearbox Housing, Motor Flange & Top Bearing Cover Builder.
Constructs NEMA motor adapter plates, top output bearing caps, and 4 corner tie-rod bolts
with guaranteed structural wall thickness outside the internal gear teeth.
"""
import math
from typing import Dict, Optional, List

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    adsk = None

from core.motor_catalog import get_motor_info

class HousingBuilder:
    """
    Builds motor adapters, top bearing housing covers, and clamping tie-rod bolts in Fusion 360.
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
    def get_bolt_and_housing_radii(cls, z_ring: int, module: float, motor_code: str = "NEMA17") -> (float, float, List[tuple]):
        """
        Calculates safe bolt positions and housing outer radius guaranteed to be outside ring gear teeth.
        Returns: (bolt_radius_cm, housing_outer_radius_cm, list_of_(bx_cm, by_cm))
        """
        pitch_r_mm = (module * z_ring) / 2.0
        root_r_mm = pitch_r_mm + 1.25 * module
        bolt_hole_dia_mm = 3.4
        
        # Bolt center is placed at least 3.5mm outside the ring tooth roots
        bolt_r_mm = root_r_mm + (bolt_hole_dia_mm / 2.0) + 2.5
        housing_outer_r_mm = bolt_r_mm + (bolt_hole_dia_mm / 2.0) + 3.0

        bolt_r_cm = bolt_r_mm * 0.1
        housing_outer_r_cm = housing_outer_r_mm * 0.1

        positions = []
        if "NEMA17" in motor_code.upper() and housing_outer_r_mm <= 21.0:
            half_hp = (31.0 / 2.0) * 0.1
            for hx in [-half_hp, half_hp]:
                for hy in [-half_hp, half_hp]:
                    positions.append((hx, hy))
        else:
            for i in range(4):
                ang = (math.pi / 4.0) + (i * math.pi / 2.0)
                positions.append((bolt_r_cm * math.cos(ang), bolt_r_cm * math.sin(ang)))

        return bolt_r_cm, housing_outer_r_cm, positions

    @classmethod
    def build_motor_mount_plate(
        cls,
        target_component: 'adsk.fusion.Component',
        motor_code: str,
        z_ring: int,
        module: float,
        housing_outer_dia_mm: float,
        plate_thickness_mm: float = 5.0,
        name: str = "Motor_Mount_Flange"
    ) -> Optional['adsk.fusion.BRepBody']:
        """
        Creates NEMA motor adapter plate with pilot recess, 4 motor bolt holes, and 4 corner tie-rod holes.
        Extruded downwards from Z = 0 to Z = -plate_thickness.
        """
        features = target_component.features
        sketches = target_component.sketches
        xy_plane = target_component.xYConstructionPlane

        motor = get_motor_info(motor_code)
        plate_thick_cm = plate_thickness_mm * 0.1
        motor_bolt_pcd_cm = (motor["bolt_pitch_circle"] / 2.0) * 0.1
        motor_bolt_r_cm = (motor["bolt_hole_dia"] / 2.0) * 0.1
        tie_r = (3.4 / 2.0) * 0.1

        bolt_r_cm, housing_outer_r_cm, bolt_positions = cls.get_bolt_and_housing_radii(z_ring, module, motor_code)

        plate_sketch = sketches.add(xy_plane)
        plate_sketch.name = f"{name}_Sketch"
        plate_sketch.isComputeDeferred = True

        lines = plate_sketch.sketchCurves.sketchLines
        circles = plate_sketch.sketchCurves.sketchCircles

        if "NEMA17" in motor_code.upper() and housing_outer_r_cm <= 2.15:
            sq_w = 42.3 * 0.1
            half_sq = sq_w / 2.0
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

            # 4 Corner Holes
            for bx, by in bolt_positions:
                circles.addByCenterRadius(adsk.core.Point3D.create(bx, by, 0), tie_r)

        else:
            # Expanded Flange
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), housing_outer_r_cm)
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), (14.0 / 2.0) * 0.1)

            # Motor mounting holes in center
            for i in range(4):
                angle = (math.pi / 4.0) + (i * math.pi / 2.0)
                bx = motor_bolt_pcd_cm * math.cos(angle)
                by = motor_bolt_pcd_cm * math.sin(angle)
                circles.addByCenterRadius(adsk.core.Point3D.create(bx, by, 0), motor_bolt_r_cm)

            # 4 Outer Corner Tie-Rod Holes
            for bx, by in bolt_positions:
                circles.addByCenterRadius(adsk.core.Point3D.create(bx, by, 0), tie_r)

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
        z_ring: int,
        module: float,
        housing_outer_dia_mm: float,
        bearing_outer_dia_mm: float = 16.0,
        output_shaft_dia_mm: float = 8.0,
        z_offset_mm: float = 0.0,
        plate_thickness_mm: float = 5.0,
        name: str = "Top_Bearing_Cover"
    ) -> Optional['adsk.fusion.BRepBody']:
        """
        Creates the top housing cap on an exact Z offset plane with bearing pocket and 4 safe bolt holes.
        """
        features = target_component.features
        sketches = target_component.sketches

        cover_plane = cls.get_z_plane(target_component, z_offset_mm * 0.1)
        plate_thick_cm = plate_thickness_mm * 0.1
        shaft_hole_r_cm = (output_shaft_dia_mm / 2.0 + 0.5) * 0.1
        tie_r = (3.4 / 2.0) * 0.1

        bolt_r_cm, housing_outer_r_cm, bolt_positions = cls.get_bolt_and_housing_radii(z_ring, module, motor_code)

        cover_sketch = sketches.add(cover_plane)
        cover_sketch.name = f"{name}_Sketch"
        cover_sketch.isComputeDeferred = True

        lines = cover_sketch.sketchCurves.sketchLines
        circles = cover_sketch.sketchCurves.sketchCircles

        if "NEMA17" in motor_code.upper() and housing_outer_r_cm <= 2.15:
            sq_w = 42.3 * 0.1
            half_sq = sq_w / 2.0
            p1 = adsk.core.Point3D.create(-half_sq, -half_sq, 0)
            p2 = adsk.core.Point3D.create(half_sq, -half_sq, 0)
            p3 = adsk.core.Point3D.create(half_sq, half_sq, 0)
            p4 = adsk.core.Point3D.create(-half_sq, half_sq, 0)
            lines.addByTwoPoints(p1, p2)
            lines.addByTwoPoints(p2, p3)
            lines.addByTwoPoints(p3, p4)
            lines.addByTwoPoints(p4, p1)

            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), shaft_hole_r_cm)

            for bx, by in bolt_positions:
                circles.addByCenterRadius(adsk.core.Point3D.create(bx, by, 0), tie_r)

        else:
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), housing_outer_r_cm)
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), shaft_hole_r_cm)

            for bx, by in bolt_positions:
                circles.addByCenterRadius(adsk.core.Point3D.create(bx, by, 0), tie_r)

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

    @classmethod
    def build_tie_rod_bolts(
        cls,
        target_component: 'adsk.fusion.Component',
        motor_code: str,
        z_ring: int,
        module: float,
        total_length_mm: float,
        name: str = "Tie_Rod_Bolts"
    ) -> List['adsk.fusion.BRepBody']:
        """
        Constructs 4 M3 Allen socket cap screws clamping top cover, housing, and motor flange together.
        """
        features = target_component.features
        sketches = target_component.sketches
        extrudes = features.extrudeFeatures

        bolt_r_cm = (3.0 / 2.0) * 0.1
        head_r_cm = (5.5 / 2.0) * 0.1
        head_h_cm = 3.0 * 0.1
        total_len_cm = (total_length_mm + 5.0) * 0.1 + (5.0 * 0.1)

        _, _, positions = cls.get_bolt_and_housing_radii(z_ring, module, motor_code)

        # Top plane of cover
        cover_top_plane = cls.get_z_plane(target_component, (total_length_mm + 5.0) * 0.1)
        bolt_bodies = []

        for b_idx, (bx, by) in enumerate(positions):
            # Bolt Shank Sketch (Extrudes downwards through all 3 plates)
            shank_sketch = sketches.add(cover_top_plane)
            shank_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(bx, by, 0), bolt_r_cm
            )
            shank_prof = shank_sketch.profiles.item(0)
            shank_input = extrudes.createInput(shank_prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            shank_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-total_len_cm))
            shank_ext = extrudes.add(shank_input)
            bolt_body = shank_ext.bodies.item(0)
            bolt_body.name = f"M3_Bolt_{b_idx + 1}"

            # Bolt Head Sketch (Extrudes upwards from cover)
            head_sketch = sketches.add(cover_top_plane)
            head_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(bx, by, 0), head_r_cm
            )
            head_prof = head_sketch.profiles.item(0)
            head_input = extrudes.createInput(head_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            head_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(head_h_cm))
            head_input.participantBodies = [bolt_body]
            extrudes.add(head_input)

            bolt_bodies.append(bolt_body)

        return bolt_bodies
