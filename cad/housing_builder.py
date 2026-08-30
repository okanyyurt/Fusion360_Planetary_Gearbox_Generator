"""
Fusion 360 Gearbox Housing, Motor Flange & Top Bearing Cover Builder.
High-Speed batch-feature operations for 100% solid 4-corner bolt lugs (kulaklar).
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
    High-Speed Builder for lightweight housing with solid reinforced bolt lugs in Fusion 360.
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
        Calculates safe bolt positions and lightweight compact housing wall radius.
        Returns: (bolt_radius_cm, housing_wall_radius_cm, list_of_(bx_cm, by_cm))
        """
        pitch_r_mm = (module * z_ring) / 2.0
        root_r_mm = pitch_r_mm + 1.25 * module
        bolt_hole_dia_mm = 3.4
        
        # Lightweight compact wall outside tooth roots
        wall_r_mm = root_r_mm + 2.5
        bolt_r_mm = root_r_mm + (bolt_hole_dia_mm / 2.0) + 2.5

        bolt_r_cm = bolt_r_mm * 0.1
        wall_r_cm = wall_r_mm * 0.1

        positions = []
        if "NEMA17" in motor_code.upper() and (bolt_r_mm + 3.0) <= 21.5:
            half_hp = (31.0 / 2.0) * 0.1
            for hx in [-half_hp, half_hp]:
                for hy in [-half_hp, half_hp]:
                    positions.append((hx, hy))
        else:
            for i in range(4):
                ang = (math.pi / 4.0) + (i * math.pi / 2.0)
                positions.append((bolt_r_cm * math.cos(ang), bolt_r_cm * math.sin(ang)))

        return bolt_r_cm, wall_r_cm, positions

    @classmethod
    def build_solid_lugged_body(
        cls,
        target_component: 'adsk.fusion.Component',
        sketch_plane: 'adsk.fusion.ConstructionPlane',
        inner_dia_r_cm: float,
        wall_r_cm: float,
        bolt_positions: List[tuple],
        height_cm: float,
        name: str = "Housing_Body"
    ) -> 'adsk.fusion.BRepBody':
        """
        Builds solid cylinder with 4 integrated solid ear lugs (kulaklar) using ultra-fast batch extrudes.
        """
        features = target_component.features
        sketches = target_component.sketches
        extrudes = features.extrudeFeatures
        tie_r = (3.4 / 2.0) * 0.1  # M3 bolt clearance
        lug_r = 0.48               # 4.8mm outer lug radius

        # 1. Base Cylinder Tube Extrusion (Single Instant Feature)
        tube_sketch = sketches.add(sketch_plane)
        tube_sketch.name = f"{name}_Tube_Sketch"
        tube_sketch.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), wall_r_cm)
        if inner_dia_r_cm > 0:
            tube_sketch.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), inner_dia_r_cm)

        prof = None
        if inner_dia_r_cm > 0:
            for p in tube_sketch.profiles:
                if p.profileLoops.count == 2:
                    prof = p
                    break
        if not prof:
            prof = tube_sketch.profiles.item(0)

        ext_in = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(height_cm))
        body_ext = extrudes.add(ext_in)
        body = body_ext.bodies.item(0)
        body.name = name

        # 2. 4 Solid Ear Lugs (Batch Join in 1 single instant operation)
        cls.add_lugs_and_holes_to_body(
            target_component=target_component,
            sketch_plane=sketch_plane,
            target_body=body,
            bolt_positions=bolt_positions,
            height_cm=height_cm,
            lug_r=lug_r,
            tie_r=tie_r,
            name=name
        )

        return body

    @classmethod
    def add_lugs_and_holes_to_body(
        cls,
        target_component: 'adsk.fusion.Component',
        sketch_plane: 'adsk.fusion.ConstructionPlane',
        target_body: 'adsk.fusion.BRepBody',
        bolt_positions: List[tuple],
        height_cm: float,
        lug_r: float = 0.48,
        tie_r: float = 0.17,
        name: str = "Part"
    ) -> None:
        """
        Adds 4 solid ear lugs and cuts 4 bolt holes in 2 ultra-fast batch operations.
        """
        features = target_component.features
        sketches = target_component.sketches
        extrudes = features.extrudeFeatures

        # Batch Lugs Join
        lugs_sketch = sketches.add(sketch_plane)
        lugs_sketch.name = f"{name}_Lugs_Sketch"
        lugs_sketch.isComputeDeferred = True
        for bx, by in bolt_positions:
            lugs_sketch.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(bx, by, 0), lug_r)
        lugs_sketch.isComputeDeferred = False

        lug_coll = adsk.core.ObjectCollection.create()
        for p in lugs_sketch.profiles:
            lug_coll.add(p)

        if lug_coll.count > 0:
            lug_in = extrudes.createInput(lug_coll, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            lug_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(height_cm))
            lug_in.participantBodies = [target_body]
            extrudes.add(lug_in)

        # Batch Holes Cut
        holes_sketch = sketches.add(sketch_plane)
        holes_sketch.name = f"{name}_Holes_Sketch"
        holes_sketch.isComputeDeferred = True
        for bx, by in bolt_positions:
            holes_sketch.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(bx, by, 0), tie_r)
        holes_sketch.isComputeDeferred = False

        hole_coll = adsk.core.ObjectCollection.create()
        for p in holes_sketch.profiles:
            hole_coll.add(p)

        if hole_coll.count > 0:
            hole_in = extrudes.createInput(hole_coll, adsk.fusion.FeatureOperations.CutFeatureOperation)
            hole_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(height_cm))
            hole_in.participantBodies = [target_body]
            extrudes.add(hole_in)

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
        Creates solid NEMA motor adapter plate with 4 solid corner bolt lugs.
        """
        features = target_component.features
        sketches = target_component.sketches
        extrudes = features.extrudeFeatures
        xy_plane = target_component.xYConstructionPlane

        motor = get_motor_info(motor_code)
        plate_thick_cm = plate_thickness_mm * 0.1
        motor_bolt_pcd_cm = (motor["bolt_pitch_circle"] / 2.0) * 0.1
        motor_bolt_r_cm = (motor["bolt_hole_dia"] / 2.0) * 0.1
        center_hole_r_cm = (14.0 / 2.0) * 0.1

        bolt_r_cm, wall_r_cm, bolt_positions = cls.get_bolt_and_housing_radii(z_ring, module, motor_code)

        # Build solid lugged body downwards from Z=0 to Z=-plate_thick_cm
        body = cls.build_solid_lugged_body(
            target_component=target_component,
            sketch_plane=xy_plane,
            inner_dia_r_cm=center_hole_r_cm,
            wall_r_cm=wall_r_cm,
            bolt_positions=bolt_positions,
            height_cm=-plate_thick_cm,
            name=name
        )

        # Cut 4 Motor Mounting Holes (Batch Cut)
        motor_sketch = sketches.add(xy_plane)
        motor_sketch.name = f"{name}_MotorHoles_Sketch"
        motor_sketch.isComputeDeferred = True
        for i in range(4):
            ang = (math.pi / 4.0) + (i * math.pi / 2.0)
            bx = motor_bolt_pcd_cm * math.cos(ang)
            by = motor_bolt_pcd_cm * math.sin(ang)
            motor_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(bx, by, 0), motor_bolt_r_cm
            )
        motor_sketch.isComputeDeferred = False

        m_coll = adsk.core.ObjectCollection.create()
        for p in motor_sketch.profiles:
            m_coll.add(p)

        if m_coll.count > 0:
            m_in = extrudes.createInput(m_coll, adsk.fusion.FeatureOperations.CutFeatureOperation)
            m_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-plate_thick_cm))
            m_in.participantBodies = [body]
            extrudes.add(m_in)

        return body

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
        Creates solid top housing cap with 4 solid corner bolt lugs.
        """
        cover_plane = cls.get_z_plane(target_component, z_offset_mm * 0.1)
        plate_thick_cm = plate_thickness_mm * 0.1
        shaft_hole_r_cm = (output_shaft_dia_mm / 2.0 + 0.5) * 0.1

        bolt_r_cm, wall_r_cm, bolt_positions = cls.get_bolt_and_housing_radii(z_ring, module, motor_code)

        body = cls.build_solid_lugged_body(
            target_component=target_component,
            sketch_plane=cover_plane,
            inner_dia_r_cm=shaft_hole_r_cm,
            wall_r_cm=wall_r_cm,
            bolt_positions=bolt_positions,
            height_cm=plate_thick_cm,
            name=name
        )

        return body

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
        Constructs 4 M3 Allen socket cap screws clamping top cover lugs, housing lugs, and motor flange lugs together.
        """
        features = target_component.features
        sketches = target_component.sketches
        extrudes = features.extrudeFeatures

        bolt_r_cm = (3.0 / 2.0) * 0.1
        head_r_cm = (5.5 / 2.0) * 0.1
        head_h_cm = 3.0 * 0.1
        total_len_cm = (total_length_mm + 5.0) * 0.1 + (5.0 * 0.1)

        _, _, positions = cls.get_bolt_and_housing_radii(z_ring, module, motor_code)

        cover_top_plane = cls.get_z_plane(target_component, (total_length_mm + 5.0) * 0.1)
        bolt_bodies = []

        # Batch Shanks
        shank_sketch = sketches.add(cover_top_plane)
        shank_sketch.isComputeDeferred = True
        for bx, by in positions:
            shank_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(bx, by, 0), bolt_r_cm
            )
        shank_sketch.isComputeDeferred = False

        shank_coll = adsk.core.ObjectCollection.create()
        for p in shank_sketch.profiles:
            shank_coll.add(p)

        shank_input = extrudes.createInput(shank_coll, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        shank_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-total_len_cm))
        shank_ext = extrudes.add(shank_input)
        for i in range(shank_ext.bodies.count):
            bolt_bodies.append(shank_ext.bodies.item(i))

        # Batch Heads
        head_sketch = sketches.add(cover_top_plane)
        head_sketch.isComputeDeferred = True
        for bx, by in positions:
            head_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(bx, by, 0), head_r_cm
            )
        head_sketch.isComputeDeferred = False

        head_coll = adsk.core.ObjectCollection.create()
        for p in head_sketch.profiles:
            head_coll.add(p)

        head_input = extrudes.createInput(head_coll, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        head_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(head_h_cm))
        extrudes.add(head_input)

        return bolt_bodies
