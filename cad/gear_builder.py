"""
Fusion 360 3D B-Rep Gear Builder.
Constructs Sun Gear, Planet Gears, and Internal Ring Gear using native Autodesk
Fusion 360 parametric features: Base Cylinder Extrude + Involute Tooth Extrude + Circular Pattern.
"""
import math
from typing import List, Tuple, Optional

# Fusion 360 API imports (available when running inside Fusion 360)
try:
    import adsk.core
    import adsk.fusion
except ImportError:
    adsk = None

from core.tooth_profile import ToothProfileGenerator, Point2D

class GearBuilder:
    """
    Builds native 3D gear components in Autodesk Fusion 360 following official CAD standards.
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
                palette.sendInfoToHTML('progress', json.dumps({'message': message}))
                adsk.doEvents()
        except Exception:
            pass

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
        All coordinates converted to Centimeters (cm).
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
        name: str = "Gear"
    ) -> Optional['adsk.fusion.BRepBody']:
        """
        Builds native Autodesk-standard spur gear body using Base Cylinder + Single Involute Tooth + Circular Pattern.
        """
        app = adsk.core.Application.get()
        features = target_component.features
        sketches = target_component.sketches
        xy_plane = target_component.xYConstructionPlane
        face_width_cm = face_width_mm * 0.1

        # 1. Compute Exact Involute Tooth Geometry
        geom = ToothProfileGenerator.get_external_tooth_geometry(
            z=z_teeth,
            module=module,
            pressure_angle_deg=pressure_angle_deg,
            backlash_mm=backlash_mm
        )

        root_r_cm = geom['root_r_cm']
        base_r_cm = geom['base_r_cm']
        outside_r_cm = geom['outside_r_cm']
        spline1_pts = geom['spline1_pts']
        spline2_pts = geom['spline2_pts']

        # 2. Base Cylinder Sketch (Root Circle + Center Shaft Bore)
        base_sketch = sketches.add(xy_plane)
        base_sketch.name = f"{name}_Base_Sketch"
        base_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), root_r_cm
        )

        if bore_dia_mm > 0.0:
            cls.add_shaft_bore(
                sketch=base_sketch,
                shaft_dia_mm=bore_dia_mm,
                shaft_type=bore_type,
                d_flat_depth_mm=d_flat_depth_mm
            )

        # Select the base cylinder profile (donut with center hole if bore exists)
        prof = None
        if bore_dia_mm > 0.0:
            for p in base_sketch.profiles:
                if p.profileLoops.count == 2:
                    prof = p
                    break
        if not prof:
            prof = base_sketch.profiles.item(0)

        # Extrude Base Cylinder
        extrudes = features.extrudeFeatures
        ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        dist = adsk.core.ValueInput.createByReal(face_width_cm)
        ext_input.setDistanceExtent(False, dist)
        base_extrude = extrudes.add(ext_input)
        base_body = base_extrude.bodies.item(0)
        base_body.name = name

        # 3. Single Tooth Profile Sketch
        tooth_sketch = sketches.add(xy_plane)
        tooth_sketch.name = f"{name}_Tooth_Sketch"
        tooth_sketch.isComputeDeferred = True

        # Involute Spline 1 (Left flank)
        p_coll1 = adsk.core.ObjectCollection.create()
        for p in spline1_pts:
            p_coll1.add(adsk.core.Point3D.create(p[0], p[1], 0.0))
        spline1 = tooth_sketch.sketchCurves.sketchFittedSplines.add(p_coll1)

        # Involute Spline 2 (Right flank)
        p_coll2 = adsk.core.ObjectCollection.create()
        for p in spline2_pts:
            p_coll2.add(adsk.core.Point3D.create(p[0], p[1], 0.0))
        spline2 = tooth_sketch.sketchCurves.sketchFittedSplines.add(p_coll2)

        # Tooth Tip Arc
        mid_tip = adsk.core.Point3D.create(outside_r_cm, 0.0, 0.0)
        tooth_sketch.sketchCurves.sketchArcs.addByThreePoints(
            spline1.endSketchPoint, mid_tip, spline2.endSketchPoint
        )

        # Root connection lines
        tolerance = 0.001
        if base_r_cm < root_r_cm:
            tooth_sketch.sketchCurves.sketchLines.addByTwoPoints(
                spline2.startSketchPoint, spline1.startSketchPoint
            )
        else:
            ang1 = math.atan2(spline1_pts[0][1], spline1_pts[0][0])
            ang2 = math.atan2(spline2_pts[0][1], spline2_pts[0][0])
            root_p1 = adsk.core.Point3D.create(
                (root_r_cm - tolerance) * math.cos(ang1),
                (root_r_cm - tolerance) * math.sin(ang1),
                0.0
            )
            root_p2 = adsk.core.Point3D.create(
                (root_r_cm - tolerance) * math.cos(ang2),
                (root_r_cm - tolerance) * math.sin(ang2),
                0.0
            )
            line1 = tooth_sketch.sketchCurves.sketchLines.addByTwoPoints(root_p1, spline1.startSketchPoint)
            line2 = tooth_sketch.sketchCurves.sketchLines.addByTwoPoints(root_p2, spline2.startSketchPoint)
            tooth_sketch.sketchCurves.sketchLines.addByTwoPoints(line1.startSketchPoint, line2.startSketchPoint)

        tooth_sketch.isComputeDeferred = False

        # 4. Extrude Single Tooth (Join to Base Body)
        tooth_prof = tooth_sketch.profiles.item(0)
        tooth_ext_input = extrudes.createInput(tooth_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        tooth_ext_input.setDistanceExtent(False, dist)
        tooth_ext_input.participantBodies = [base_body]
        tooth_extrude = extrudes.add(tooth_ext_input)

        # 5. Circular Pattern Tooth Around Base Cylinder
        circular_patterns = features.circularPatternFeatures
        entities = adsk.core.ObjectCollection.create()
        entities.add(tooth_extrude)

        cyl_face = base_extrude.sideFaces.item(0)
        if cyl_face.edges.count == 2 and base_extrude.sideFaces.count > 1:
            cyl_face = base_extrude.sideFaces.item(1)

        pattern_input = circular_patterns.createInput(entities, cyl_face)
        pattern_input.quantity = adsk.core.ValueInput.createByString(str(z_teeth))
        pattern_input.patternComputeOption = adsk.fusion.PatternComputeOptions.IdenticalPatternCompute
        circular_patterns.add(pattern_input)

        return base_body

    @classmethod
    def build_internal_ring_gear_body(
        cls,
        target_component: 'adsk.fusion.Component',
        z_ring: int,
        module: float,
        face_width_mm: float,
        outer_housing_dia_mm: float,
        is_herringbone: bool = False,
        helix_angle_deg: float = 25.0,
        pressure_angle_deg: float = 20.0,
        backlash_mm: float = 0.05,
        name: str = "Ring_Gear_Housing"
    ) -> Optional['adsk.fusion.BRepBody']:
        """
        Builds native Autodesk-standard internal Ring Gear body using Outer Tube Extrude + Internal Involute Tooth + Circular Pattern.
        """
        features = target_component.features
        sketches = target_component.sketches
        xy_plane = target_component.xYConstructionPlane
        face_width_cm = face_width_mm * 0.1

        # 1. Compute Exact Internal Ring Geometry
        geom = ToothProfileGenerator.get_internal_ring_tooth_geometry(
            z_ring=z_ring,
            module=module,
            housing_outer_dia_mm=outer_housing_dia_mm,
            pressure_angle_deg=pressure_angle_deg,
            backlash_mm=backlash_mm
        )

        root_r_cm = geom['root_r_cm']
        tip_r_cm = geom['tip_r_cm']
        base_r_cm = geom['base_r_cm']
        housing_outer_r_cm = geom['housing_outer_r_cm']
        spline1_pts = geom['spline1_pts']
        spline2_pts = geom['spline2_pts']

        # 2. Base Outer Cylinder Tube (Outer Housing Wall + Inner Root Bore)
        tube_sketch = sketches.add(xy_plane)
        tube_sketch.name = f"{name}_Tube_Sketch"
        tube_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), housing_outer_r_cm
        )
        tube_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), root_r_cm
        )

        # Select donut profile
        prof = None
        for p in tube_sketch.profiles:
            if p.profileLoops.count == 2:
                prof = p
                break
        if not prof:
            prof = tube_sketch.profiles.item(0)

        extrudes = features.extrudeFeatures
        ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        dist = adsk.core.ValueInput.createByReal(face_width_cm)
        ext_input.setDistanceExtent(False, dist)
        tube_extrude = extrudes.add(ext_input)
        ring_body = tube_extrude.bodies.item(0)
        ring_body.name = name

        # 3. Single Internal Tooth Sketch (Points inward toward center)
        tooth_sketch = sketches.add(xy_plane)
        tooth_sketch.name = f"{name}_Tooth_Sketch"
        tooth_sketch.isComputeDeferred = True

        # Involute Spline 1
        p_coll1 = adsk.core.ObjectCollection.create()
        for p in spline1_pts:
            p_coll1.add(adsk.core.Point3D.create(p[0], p[1], 0.0))
        spline1 = tooth_sketch.sketchCurves.sketchFittedSplines.add(p_coll1)

        # Involute Spline 2
        p_coll2 = adsk.core.ObjectCollection.create()
        for p in spline2_pts:
            p_coll2.add(adsk.core.Point3D.create(p[0], p[1], 0.0))
        spline2 = tooth_sketch.sketchCurves.sketchFittedSplines.add(p_coll2)

        # Tip Arc at innermost radius (tip_r_cm)
        mid_tip = adsk.core.Point3D.create(tip_r_cm, 0.0, 0.0)
        tooth_sketch.sketchCurves.sketchArcs.addByThreePoints(
            spline1.startSketchPoint, mid_tip, spline2.startSketchPoint
        )

        # Root connection line along outer root radius
        tolerance = 0.001
        ang1 = math.atan2(spline1_pts[-1][1], spline1_pts[-1][0])
        ang2 = math.atan2(spline2_pts[-1][1], spline2_pts[-1][0])
        root_p1 = adsk.core.Point3D.create(
            (root_r_cm + tolerance) * math.cos(ang1),
            (root_r_cm + tolerance) * math.sin(ang1),
            0.0
        )
        root_p2 = adsk.core.Point3D.create(
            (root_r_cm + tolerance) * math.cos(ang2),
            (root_r_cm + tolerance) * math.sin(ang2),
            0.0
        )
        line1 = tooth_sketch.sketchCurves.sketchLines.addByTwoPoints(spline1.endSketchPoint, root_p1)
        line2 = tooth_sketch.sketchCurves.sketchLines.addByTwoPoints(spline2.endSketchPoint, root_p2)
        tooth_sketch.sketchCurves.sketchLines.addByTwoPoints(line1.endSketchPoint, line2.endSketchPoint)

        tooth_sketch.isComputeDeferred = False

        # 4. Extrude Internal Tooth (Join to Ring Housing Body)
        tooth_prof = tooth_sketch.profiles.item(0)
        tooth_ext_input = extrudes.createInput(tooth_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        tooth_ext_input.setDistanceExtent(False, dist)
        tooth_ext_input.participantBodies = [ring_body]
        tooth_extrude = extrudes.add(tooth_ext_input)

        # 5. Circular Pattern Internal Tooth Around Ring
        circular_patterns = features.circularPatternFeatures
        entities = adsk.core.ObjectCollection.create()
        entities.add(tooth_extrude)

        cyl_face = tube_extrude.sideFaces.item(0)
        if cyl_face.edges.count == 2 and tube_extrude.sideFaces.count > 1:
            cyl_face = tube_extrude.sideFaces.item(1)

        pattern_input = circular_patterns.createInput(entities, cyl_face)
        pattern_input.quantity = adsk.core.ValueInput.createByString(str(z_ring))
        pattern_input.patternComputeOption = adsk.fusion.PatternComputeOptions.IdenticalPatternCompute
        circular_patterns.add(pattern_input)

        return ring_body
