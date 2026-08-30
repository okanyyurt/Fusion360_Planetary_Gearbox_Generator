"""
Fusion 360 3D B-Rep Gear Builder.
Constructs Sun Gear, Planet Gears with internal bearing stop shoulders (fatura),
and Internal Ring Gear Enclosure using high-speed native Autodesk feature operations on exact Z Construction Planes.
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
    def get_z_plane(target_component: 'adsk.fusion.Component', z_offset_cm: float):
        """Returns or creates an XY construction plane at exact Z offset in cm."""
        if abs(z_offset_cm) < 0.0001:
            return target_component.xYConstructionPlane
        planes = target_component.constructionPlanes
        plane_input = planes.createInput()
        plane_input.setByOffset(target_component.xYConstructionPlane, adsk.core.ValueInput.createByReal(z_offset_cm))
        return planes.add(plane_input)

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
        center_x_cm: float = 0.0,
        center_y_cm: float = 0.0,
        shaft_type: str = "ROUND",
        d_flat_depth_mm: float = 0.5,
        tolerance_offset_mm: float = 0.05
    ) -> None:
        """
        Adds center shaft cutout profile (Round or D-Cut) on sketch at (center_x, center_y).
        """
        r_cm = (shaft_dia_mm / 2.0 + tolerance_offset_mm) * 0.1
        lines = sketch.sketchCurves.sketchLines
        circles = sketch.sketchCurves.sketchCircles
        
        if shaft_type == "ROUND" or not shaft_type:
            circles.addByCenterRadius(adsk.core.Point3D.create(center_x_cm, center_y_cm, 0), r_cm)
            
        elif shaft_type == "D_CUT":
            d_flat_cm = d_flat_depth_mm * 0.1
            y_flat = r_cm - d_flat_cm
            if y_flat < r_cm and y_flat > -r_cm:
                x_half = math.sqrt(max(0.0001, r_cm**2 - y_flat**2))
                p1 = adsk.core.Point3D.create(center_x_cm - x_half, center_y_cm + y_flat, 0)
                p2 = adsk.core.Point3D.create(center_x_cm + x_half, center_y_cm + y_flat, 0)
                lines.addByTwoPoints(p1, p2)
                
                p_bottom = adsk.core.Point3D.create(center_x_cm, center_y_cm - r_cm, 0)
                arcs = sketch.sketchCurves.sketchArcs
                arcs.addByThreePoints(p2, p_bottom, p1)
            else:
                circles.addByCenterRadius(adsk.core.Point3D.create(center_x_cm, center_y_cm, 0), r_cm)

    @classmethod
    def build_external_gear_body(
        cls,
        target_component: 'adsk.fusion.Component',
        z_teeth: int,
        module: float,
        face_width_mm: float,
        center_x_mm: float = 0.0,
        center_y_mm: float = 0.0,
        z_offset_mm: float = 0.0,
        is_herringbone: bool = False,
        helix_angle_deg: float = 25.0,
        bore_dia_mm: float = 5.0,
        bore_type: str = "ROUND",
        d_flat_depth_mm: float = 0.5,
        min_rim_thickness_mm: float = 2.0,
        bearing_outer_dia_mm: float = 8.0,
        bearing_width_mm: float = 2.5,
        pressure_angle_deg: float = 20.0,
        backlash_mm: float = 0.05,
        is_sun_gear: bool = False,
        name: str = "Gear"
    ) -> Optional['adsk.fusion.BRepBody']:
        """
        Builds external gear body (Spur or Herringbone) positioned at (center_x, center_y) on Z plane.
        Includes internal stop shoulder (fatura) for planet bearings.
        """
        features = target_component.features
        sketches = target_component.sketches
        face_width_cm = face_width_mm * 0.1
        half_w_cm = face_width_cm / 2.0
        cx_cm = center_x_mm * 0.1
        cy_cm = center_y_mm * 0.1
        z_off_cm = z_offset_mm * 0.1

        # Use Offset Construction Plane at Z elevation
        sketch_plane = cls.get_z_plane(target_component, z_off_cm)

        # 1. Compute Exact Involute Geometry
        geom = ToothProfileGenerator.get_external_tooth_features(
            z=z_teeth,
            module=module,
            pressure_angle_deg=pressure_angle_deg,
            backlash_mm=backlash_mm
        )

        pitch_r_cm = geom['pitch_r_cm']
        root_r_cm = geom['root_r_cm']
        base_r_cm = geom['base_r_cm']
        spline1_pts = geom['spline1_pts']
        spline2_pts = geom['spline2_pts']

        # Safe bore check with 3D print minimum rim thickness
        max_allowed_bore = max(1.0, (root_r_cm * 20.0) - (2.0 * min_rim_thickness_mm))
        safe_bore_dia = min(bore_dia_mm, max_allowed_bore)

        # 2. Base Cylinder Sketch at (cx, cy) on sketch_plane
        base_sketch = sketches.add(sketch_plane)
        base_sketch.name = f"{name}_Base_Sketch"
        base_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(cx_cm, cy_cm, 0), root_r_cm
        )

        if safe_bore_dia > 1.0:
            cls.add_shaft_bore(
                sketch=base_sketch,
                shaft_dia_mm=safe_bore_dia,
                center_x_cm=cx_cm,
                center_y_cm=cy_cm,
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

        # Extrude Base Cylinder upwards by face_width_cm
        extrudes = features.extrudeFeatures
        ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        dist = adsk.core.ValueInput.createByReal(face_width_cm)
        ext_input.setDistanceExtent(False, dist)
        base_extrude = extrudes.add(ext_input)
        base_body = base_extrude.bodies.item(0)
        base_body.name = name

        # 3. Single Tooth Profile Sketch on sketch_plane
        tooth_sketch = sketches.add(sketch_plane)
        tooth_sketch.name = f"{name}_Tooth_Sketch"
        tooth_sketch.isComputeDeferred = True

        p_coll1 = adsk.core.ObjectCollection.create()
        for p in spline1_pts:
            p_coll1.add(adsk.core.Point3D.create(p[0] + cx_cm, p[1] + cy_cm, 0.0))
        spline1 = tooth_sketch.sketchCurves.sketchFittedSplines.add(p_coll1)

        p_coll2 = adsk.core.ObjectCollection.create()
        for p in spline2_pts:
            p_coll2.add(adsk.core.Point3D.create(p[0] + cx_cm, p[1] + cy_cm, 0.0))
        spline2 = tooth_sketch.sketchCurves.sketchFittedSplines.add(p_coll2)

        # Tooth Tip Line (Robust ISO/AGMA tooth tip land)
        tooth_sketch.sketchCurves.sketchLines.addByTwoPoints(
            spline1.endSketchPoint, spline2.endSketchPoint
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
                cx_cm + (root_r_cm - tolerance) * math.cos(ang1),
                cy_cm + (root_r_cm - tolerance) * math.sin(ang1),
                0.0
            )
            root_p2 = adsk.core.Point3D.create(
                cx_cm + (root_r_cm - tolerance) * math.cos(ang2),
                cy_cm + (root_r_cm - tolerance) * math.sin(ang2),
                0.0
            )
            line1 = tooth_sketch.sketchCurves.sketchLines.addByTwoPoints(root_p1, spline1.startSketchPoint)
            line2 = tooth_sketch.sketchCurves.sketchLines.addByTwoPoints(root_p2, spline2.startSketchPoint)
            tooth_sketch.sketchCurves.sketchLines.addByTwoPoints(line1.startSketchPoint, line2.startSketchPoint)

        tooth_sketch.isComputeDeferred = False

        # 4. Form Tooth (Herringbone Sweep or Spur Extrude)
        tooth_prof = tooth_sketch.profiles.item(0)
        tooth_features = []

        if is_herringbone and helix_angle_deg > 1.0:
            try:
                # Calculate double-helical twist angle
                twist_rad = ToothProfileGenerator.calculate_herringbone_twist_angle(
                    face_width=face_width_mm,
                    pitch_radius=pitch_r_cm * 10.0,
                    helix_angle_deg=helix_angle_deg
                )

                # Lower half path sketch (along Z axis)
                xz_plane = target_component.xZConstructionPlane
                path_sketch1 = sketches.add(xz_plane)
                line_p1 = adsk.core.Point3D.create(cx_cm, z_off_cm, 0.0)
                line_p2 = adsk.core.Point3D.create(cx_cm, z_off_cm + half_w_cm, 0.0)
                path_line1 = path_sketch1.sketchCurves.sketchLines.addByTwoPoints(line_p1, line_p2)
                path1 = features.sweepFeatures.createPath(path_line1)

                sweep_input1 = features.sweepFeatures.createInput(tooth_prof, path1, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                sweep_input1.twistAngle = adsk.core.ValueInput.createByReal(twist_rad)
                sweep_input1.participantBodies = [base_body]
                sw1 = features.sweepFeatures.add(sweep_input1)
                tooth_features.append(sw1)

                # Upper half path sketch (along Z axis with reversed twist)
                path_sketch2 = sketches.add(xz_plane)
                line_p3 = adsk.core.Point3D.create(cx_cm, z_off_cm + half_w_cm, 0.0)
                line_p4 = adsk.core.Point3D.create(cx_cm, z_off_cm + face_width_cm, 0.0)
                path_line2 = path_sketch2.sketchCurves.sketchLines.addByTwoPoints(line_p3, line_p4)
                path2 = features.sweepFeatures.createPath(path_line2)

                sweep_input2 = features.sweepFeatures.createInput(tooth_prof, path2, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                sweep_input2.twistAngle = adsk.core.ValueInput.createByReal(-twist_rad)
                sweep_input2.participantBodies = [base_body]
                sw2 = features.sweepFeatures.add(sweep_input2)
                tooth_features.append(sw2)

            except Exception:
                # Safe fallback to straight extrusion
                tooth_ext_input = extrudes.createInput(tooth_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                tooth_ext_input.setDistanceExtent(False, dist)
                tooth_ext_input.participantBodies = [base_body]
                tooth_features = [extrudes.add(tooth_ext_input)]
        else:
            # Spur Gear (Straight Extrude)
            tooth_ext_input = extrudes.createInput(tooth_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            tooth_ext_input.setDistanceExtent(False, dist)
            tooth_ext_input.participantBodies = [base_body]
            tooth_features = [extrudes.add(tooth_ext_input)]

        # 5. Circular Pattern Tooth Around Base Cylinder
        circular_patterns = features.circularPatternFeatures
        entities = adsk.core.ObjectCollection.create()
        for feat in tooth_features:
            entities.add(feat)

        cyl_face = None
        for face in base_extrude.sideFaces:
            if face.geometry.surfaceType == adsk.core.SurfaceTypes.CylinderSurfaceType:
                cyl_face = face
                break
        if not cyl_face:
            cyl_face = base_extrude.sideFaces.item(0)

        pattern_input = circular_patterns.createInput(entities, cyl_face)
        pattern_input.quantity = adsk.core.ValueInput.createByString(str(z_teeth))
        pattern_input.patternComputeOption = adsk.fusion.PatternComputeOptions.IdenticalPatternCompute
        circular_patterns.add(pattern_input)

        # 6. If Planet Gear, add bearing stop shoulder (fatura)
        if not is_sun_gear and bearing_outer_dia_mm > safe_bore_dia:
            try:
                pocket_r_cm = (bearing_outer_dia_mm / 2.0) * 0.1
                pocket_depth_cm = min(bearing_width_mm, (face_width_mm - 1.5) / 2.0) * 0.1
                
                # Top bearing pocket cut
                top_pocket_sketch = sketches.add(cls.get_z_plane(target_component, z_off_cm + face_width_cm))
                top_pocket_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                    adsk.core.Point3D.create(cx_cm, cy_cm, 0), pocket_r_cm
                )
                tp_prof = top_pocket_sketch.profiles.item(0)
                tp_input = extrudes.createInput(tp_prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
                tp_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-pocket_depth_cm))
                tp_input.participantBodies = [base_body]
                extrudes.add(tp_input)

                # Bottom bearing pocket cut
                bot_pocket_sketch = sketches.add(sketch_plane)
                bot_pocket_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                    adsk.core.Point3D.create(cx_cm, cy_cm, 0), pocket_r_cm
                )
                bp_prof = bot_pocket_sketch.profiles.item(0)
                bp_input = extrudes.createInput(bp_prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
                bp_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(pocket_depth_cm))
                bp_input.participantBodies = [base_body]
                extrudes.add(bp_input)
            except Exception:
                pass

        # 7. If Sun gear, add integral motor shaft clamping collar below
        if is_sun_gear and safe_bore_dia > 0:
            collar_dia_mm = max(safe_bore_dia + 6.0, 11.0)
            collar_len_mm = 6.0
            collar_sketch = sketches.add(sketch_plane)
            collar_sketch.name = f"{name}_Collar_Sketch"
            collar_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(0, 0, 0), (collar_dia_mm / 2.0) * 0.1
            )
            cls.add_shaft_bore(
                sketch=collar_sketch,
                shaft_dia_mm=safe_bore_dia,
                center_x_cm=0.0,
                center_y_cm=0.0,
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
                screw_z = z_off_cm - (collar_len_mm * 0.5 * 0.1)
                screw_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                    adsk.core.Point3D.create(0, screw_z, 0), (3.0 / 2.0) * 0.1
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
        Builds complete Ring Gear Housing with internal teeth and 4 corner tie-rod through-holes.
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
        spline1_pts = geom['spline1_pts']
        spline2_pts = geom['spline2_pts']

        # Determine outer housing dimension
        pitch_r_mm = (module * z_ring) / 2.0
        min_housing_dia = (pitch_r_mm * 2.0) + (module * 6.0) + 6.0
        actual_housing_dia = max(min_housing_dia, outer_housing_dia_mm)
        actual_housing_r = actual_housing_dia / 2.0 * 0.1
        
        # 2. Base Housing Tube Sketch
        tube_sketch = sketches.add(xy_plane)
        tube_sketch.name = f"{name}_Tube_Sketch"
        tube_sketch.isComputeDeferred = True

        lines = tube_sketch.sketchCurves.sketchLines
        circles = tube_sketch.sketchCurves.sketchCircles

        # Inner tip cylinder bore
        circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), tip_r_cm)

        # Outer Housing Shape & 4 Corner Bolt Holes
        hole_r = (3.4 / 2.0) * 0.1  # M3 clearance hole

        if "NEMA17" in motor_code.upper() and actual_housing_dia <= 45.0:
            sq_w = 42.3 * 0.1
            half_sq = sq_w / 2.0
            half_hp = (31.0 / 2.0) * 0.1

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
            # Expanded Flange with 4 Corner Bolt Holes
            circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), actual_housing_r)
            bolt_pcd_cm = actual_housing_r * 0.85
            for i in range(4):
                ang = (math.pi / 4.0) + (i * math.pi / 2.0)
                bx = bolt_pcd_cm * math.cos(ang)
                by = bolt_pcd_cm * math.sin(ang)
                circles.addByCenterRadius(adsk.core.Point3D.create(bx, by, 0), hole_r)

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

        # 3. Single Tooth Space Cut Sketch
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

        # Root connection line (at outer root radius)
        space_sketch.sketchCurves.sketchLines.addByTwoPoints(
            spline1.endSketchPoint, spline2.endSketchPoint
        )

        # Tip connection line (at inner tip radius)
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

        # 5. Circular Pattern Cut Space around Z axis
        circular_patterns = features.circularPatternFeatures
        entities = adsk.core.ObjectCollection.create()
        entities.add(cut_extrude)

        axis = target_component.zConstructionAxis
        pattern_input = circular_patterns.createInput(entities, axis)
        pattern_input.quantity = adsk.core.ValueInput.createByString(str(z_ring))
        pattern_input.patternComputeOption = adsk.fusion.PatternComputeOptions.IdenticalPatternCompute
        circular_patterns.add(pattern_input)

        return ring_body
