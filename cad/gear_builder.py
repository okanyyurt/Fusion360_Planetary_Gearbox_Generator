"""
Fusion 360 3D B-Rep Gear Builder.
Constructs Sun Gear, Planet Gears with single-bearing top seats and bottom retaining stop shoulders,
and lightweight Internal Ring Gear Housing with 4 corner bolt lugs (kulaklar).
"""
import math
from typing import List, Tuple, Optional

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    adsk = None

from core.tooth_profile import ToothProfileGenerator, Point2D
from cad.housing_builder import HousingBuilder

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
        Builds external gear body (Spur or Herringbone).
        For Planet Gear: Creates wide pin clearance bore + top bearing pocket + bottom retaining stop shoulder.
        """
        features = target_component.features
        sketches = target_component.sketches
        extrudes = features.extrudeFeatures
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

        # Determine through-hole bore
        if is_sun_gear:
            safe_bore_dia = min(bore_dia_mm, max(1.0, (root_r_cm * 20.0) - 1.5))
        else:
            # Pin clearance hole through the bottom retaining lip (e.g. pin + 1.0mm)
            safe_bore_dia = bore_dia_mm + 0.8

        # 2. Base Cylinder Sketch on sketch_plane
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

        # Tooth Tip Line
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

        # 4. Form Tooth: Extrude with exact face_width height
        tooth_prof = tooth_sketch.profiles.item(0)
        tooth_features = []

        if is_herringbone and helix_angle_deg > 1.0:
            try:
                twist_rad = ToothProfileGenerator.calculate_herringbone_twist_angle(
                    face_width=face_width_mm,
                    pitch_radius=pitch_r_cm * 10.0,
                    helix_angle_deg=helix_angle_deg
                )

                # 3D Sweep along true Z axis
                sweep_sketch1 = sketches.add(sketch_plane)
                sweep_sketch1.is3D = True
                p_start = adsk.core.Point3D.create(cx_cm, cy_cm, 0.0)
                p_mid = adsk.core.Point3D.create(cx_cm, cy_cm, half_w_cm)
                line1 = sweep_sketch1.sketchCurves.sketchLines.addByTwoPoints(p_start, p_mid)
                path1 = features.sweepFeatures.createPath(line1)

                sweep_in1 = features.sweepFeatures.createInput(tooth_prof, path1, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                sweep_in1.twistAngle = adsk.core.ValueInput.createByReal(twist_rad)
                sweep_in1.participantBodies = [base_body]
                sw1 = features.sweepFeatures.add(sweep_in1)
                tooth_features.append(sw1)

                sweep_sketch2 = sketches.add(sketch_plane)
                sweep_sketch2.is3D = True
                p_end = adsk.core.Point3D.create(cx_cm, cy_cm, face_width_cm)
                line2 = sweep_sketch2.sketchCurves.sketchLines.addByTwoPoints(p_mid, p_end)
                path2 = features.sweepFeatures.createPath(line2)

                sweep_in2 = features.sweepFeatures.createInput(tooth_prof, path2, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                sweep_in2.twistAngle = adsk.core.ValueInput.createByReal(-twist_rad)
                sweep_in2.participantBodies = [base_body]
                sw2 = features.sweepFeatures.add(sweep_in2)
                tooth_features.append(sw2)

            except Exception:
                tooth_ext_input = extrudes.createInput(tooth_prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                tooth_ext_input.setDistanceExtent(False, dist)
                tooth_ext_input.participantBodies = [base_body]
                tooth_features = [extrudes.add(tooth_ext_input)]
        else:
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

        # 6. If Planet Gear: Cut Top Bearing Seat Pocket down to bottom 1.5mm stop lip
        if not is_sun_gear and bearing_outer_dia_mm > safe_bore_dia:
            try:
                max_bearing_dia = (root_r_cm * 20.0) - (2.0 * min_rim_thickness_mm)
                actual_bearing_dia = min(bearing_outer_dia_mm, max_bearing_dia)
                
                if actual_bearing_dia > (safe_bore_dia + 0.6):
                    pocket_r_cm = (actual_bearing_dia / 2.0) * 0.1
                    # Depth leaves a 1.5mm solid retaining stop lip at the bottom
                    bottom_lip_mm = 1.5
                    pocket_depth_mm = max(bearing_width_mm, face_width_mm - bottom_lip_mm)
                    pocket_depth_cm = pocket_depth_mm * 0.1
                    
                    # Top Bearing Seat Pocket Cut
                    top_plane = cls.get_z_plane(target_component, z_off_cm + face_width_cm)
                    top_sketch = sketches.add(top_plane)
                    top_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                        adsk.core.Point3D.create(cx_cm, cy_cm, 0), pocket_r_cm
                    )
                    tp_prof = top_sketch.profiles.item(0)
                    tp_input = extrudes.createInput(tp_prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
                    tp_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-pocket_depth_cm))
                    tp_input.participantBodies = [base_body]
                    extrudes.add(tp_input)
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
        Builds lightweight Ring Gear Housing with 4 corner bolt lugs (kulaklar) saving material.
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

        # Determine lightweight housing wall and bolt lug positions
        bolt_r_cm, wall_r_cm, bolt_positions = HousingBuilder.get_bolt_and_housing_radii(
            z_ring=z_ring, module=module, motor_code=motor_code
        )
        
        # 2. Base Lightweight Lugged Housing Tube Sketch
        tube_sketch = sketches.add(xy_plane)
        tube_sketch.name = f"{name}_Tube_Sketch"
        tube_sketch.isComputeDeferred = True

        HousingBuilder.draw_lugged_housing_profile(
            sketch=tube_sketch,
            wall_r_cm=wall_r_cm,
            bolt_positions=bolt_positions,
            inner_dia_r_cm=tip_r_cm,
            motor_code=motor_code
        )

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

        # Root connection line
        space_sketch.sketchCurves.sketchLines.addByTwoPoints(
            spline1.endSketchPoint, spline2.endSketchPoint
        )

        # Tip connection line
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
