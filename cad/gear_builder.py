"""
Fusion 360 3D B-Rep Gear Builder.
Constructs Sun Gear, Planet Gears, and Internal Ring Gear Enclosure using high-speed
native Autodesk feature operations (Base Extrude + Single Tooth Extrude/Cut + Circular Pattern).
Total execution time: < 0.1s per gear, eliminating UI freezes.
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
    Builds native parametric 3D gear components in Autodesk Fusion 360.
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
                
                p_bottom = adsk.core.Point3D.create(0, -r_cm, 0)
                arcs = sketch.sketchCurves.sketchArcs
                arcs.addByThreePoints(p2, p_bottom, p1)
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
        Builds external gear body via Base Cylinder Extrusion + Single Involute Tooth + Circular Pattern.
        """
        features = target_component.features
        sketches = target_component.sketches
        xy_plane = target_component.xYConstructionPlane
        face_width_cm = face_width_mm * 0.1

        # 1. Compute Exact Involute Geometry
        geom = ToothProfileGenerator.get_external_tooth_features(
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

        # Safe bore check
        safe_bore_dia = min(bore_dia_mm, (root_r_cm * 20.0) - 2.0)

        # 2. Base Cylinder Sketch (Root Circle + Center Shaft Bore)
        base_sketch = sketches.add(xy_plane)
        base_sketch.name = f"{name}_Base_Sketch"
        base_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), root_r_cm
        )

        if safe_bore_dia > 1.0:
            cls.add_shaft_bore(
                sketch=base_sketch,
                shaft_dia_mm=safe_bore_dia,
                shaft_type=bore_type,
                d_flat_depth_mm=d_flat_depth_mm
            )

        prof = None
        if safe_bore_dia > 1.0:
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

        # 3. Single Tooth Profile Sketch (12 points per flank)
        tooth_sketch = sketches.add(xy_plane)
        tooth_sketch.name = f"{name}_Tooth_Sketch"
        tooth_sketch.isComputeDeferred = True

        p_coll1 = adsk.core.ObjectCollection.create()
        for p in spline1_pts:
            p_coll1.add(adsk.core.Point3D.create(p[0], p[1], 0.0))
        spline1 = tooth_sketch.sketchCurves.sketchFittedSplines.add(p_coll1)

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

        # 5. Circular Pattern Tooth Around Base Cylinder (using component Z axis)
        circular_patterns = features.circularPatternFeatures
        entities = adsk.core.ObjectCollection.create()
        entities.add(tooth_extrude)

        axis = target_component.zConstructionAxis
        pattern_input = circular_patterns.createInput(entities, axis)
        pattern_input.quantity = adsk.core.ValueInput.createByString(str(z_teeth))
        pattern_input.patternComputeOption = adsk.fusion.PatternComputeOptions.IdenticalPatternCompute
        circular_patterns.add(pattern_input)

        # If Sun gear, add integral motor shaft clamping collar on bottom + M3 setscrew hole
        if is_sun_gear and safe_bore_dia > 0:
            collar_dia_mm = max(safe_bore_dia + 6.0, 11.0)
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
            c_input.participantBodies = [base_body]
            extrudes.add(c_input)

            # Radial M3 Setscrew Hole on side of collar
            try:
                xz_plane = target_component.xZConstructionPlane
                screw_sketch = sketches.add(xz_plane)
                screw_sketch.name = f"{name}_Setscrew_Sketch"
                screw_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                    adsk.core.Point3D.create(0, -(collar_len_mm * 0.5 * 0.1), 0), (3.0 / 2.0) * 0.1
                )
                screw_prof = screw_sketch.profiles.item(0)
                screw_input = extrudes.createInput(screw_prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
                screw_dist = adsk.core.ValueInput.createByReal((collar_dia_mm / 2.0) * 0.1)
                screw_input.setDistanceExtent(False, screw_dist)
                screw_input.participantBodies = [base_body]
                extrudes.add(screw_input)
            except Exception:
                pass

        return base_body

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
        Builds complete Ring Gear Housing via Base Housing Tube Extrusion + Single Tooth Space Cut + Circular Pattern.
        """
        features = target_component.features
        sketches = target_component.sketches
        xy_plane = target_component.xYConstructionPlane
        face_width_cm = face_width_mm * 0.1

        # 1. Compute Involute Tooth Space Features
        geom = ToothProfileGenerator.get_internal_tooth_space_features(
            z_ring=z_ring,
            module=module,
            pressure_angle_deg=pressure_angle_deg,
            backlash_mm=backlash_mm
        )

        tip_r_cm = geom['tip_r_cm']
        root_r_cm = geom['root_r_cm']
        spline1_pts = geom['spline1_pts']
        spline2_pts = geom['spline2_pts']

        # Determine outer housing dimension (NEMA 17 / 23 square or scaled square)
        pitch_r_mm = (module * z_ring) / 2.0
        min_housing_dia = (pitch_r_mm * 2.0) + (module * 6.0) + 6.0
        
        # 2. Base Housing Tube Sketch (Outer Profile + Inner Tip Bore)
        tube_sketch = sketches.add(xy_plane)
        tube_sketch.name = f"{name}_Tube_Sketch"
        tube_sketch.isComputeDeferred = True

        lines = tube_sketch.sketchCurves.sketchLines
        circles = tube_sketch.sketchCurves.sketchCircles

        # Inner tip cylinder bore
        circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), tip_r_cm)

        # Outer Housing Shape (NEMA 17 square or expanded square/round)
        if "NEMA17" in motor_code.upper() and min_housing_dia <= 40.0:
            sq_w = 42.3 * 0.1
            half_sq = sq_w / 2.0
            half_hp = (31.0 / 2.0) * 0.1
            hole_r = (3.4 / 2.0) * 0.1

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
            # Scaled square/flanged housing
            actual_housing_r = max(min_housing_dia, outer_housing_dia_mm) / 2.0 * 0.1
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), actual_housing_r)

        tube_sketch.isComputeDeferred = False

        # Find donut tube profile
        prof = None
        for p in tube_sketch.profiles:
            if p.profileLoops.count >= 2:
                prof = p
                break
        if not prof:
            prof = tube_sketch.profiles.item(0)

        # Extrude Base Housing Tube
        extrudes = features.extrudeFeatures
        ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        dist = adsk.core.ValueInput.createByReal(face_width_cm)
        ext_input.setDistanceExtent(False, dist)
        tube_extrude = extrudes.add(ext_input)
        ring_body = tube_extrude.bodies.item(0)
        ring_body.name = name

        # 3. Single Tooth Space Cut Sketch (pocket from tip_r out to root_r)
        space_sketch = sketches.add(xy_plane)
        space_sketch.name = f"{name}_Space_Sketch"
        space_sketch.isComputeDeferred = True

        p_coll1 = adsk.core.ObjectCollection.create()
        for p in spline1_pts:
            p_coll1.add(adsk.core.Point3D.create(p[0], p[1], 0.0))
        spline1 = space_sketch.sketchCurves.sketchFittedSplines.add(p_coll1)

        p_coll2 = adsk.core.ObjectCollection.create()
        for p in spline2_pts:
            p_coll2.add(adsk.core.Point3D.create(p[0], p[1], 0.0))
        spline2 = space_sketch.sketchCurves.sketchFittedSplines.add(p_coll2)

        # Root connection arc at outer root radius
        mid_root = adsk.core.Point3D.create(root_r_cm, 0.0, 0.0)
        space_sketch.sketchCurves.sketchArcs.addByThreePoints(
            spline1.endSketchPoint, mid_root, spline2.endSketchPoint
        )

        # Tip connection line at inner tip radius
        space_sketch.sketchCurves.sketchLines.addByTwoPoints(
            spline1.startSketchPoint, spline2.startSketchPoint
        )

        space_sketch.isComputeDeferred = False

        # 4. Extrude Single Tooth Space Cut
        space_prof = space_sketch.profiles.item(0)
        cut_input = extrudes.createInput(space_prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
        cut_input.setDistanceExtent(False, dist)
        cut_input.participantBodies = [ring_body]
        cut_extrude = extrudes.add(cut_input)

        # 5. Circular Pattern Cut Space around inner cylinder (using component Z axis)
        circular_patterns = features.circularPatternFeatures
        entities = adsk.core.ObjectCollection.create()
        entities.add(cut_extrude)

        axis = target_component.zConstructionAxis
        pattern_input = circular_patterns.createInput(entities, axis)
        pattern_input.quantity = adsk.core.ValueInput.createByString(str(z_ring))
        pattern_input.patternComputeOption = adsk.fusion.PatternComputeOptions.IdenticalPatternCompute
        circular_patterns.add(pattern_input)

        return ring_body
