"""
Fusion 360 3D Printable Snap Circlip (Segman) Builder.
Generates parametric DIN 471 / C-Clip snap rings for 3D printing and CAD assembly.
"""
import math
from typing import Optional, Dict

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    adsk = None

from core.circlip_catalog import get_circlip_info

class CirclipBuilder:
    """
    Constructs 3D Printable Snap Circlips / Retaining Rings in Fusion 360.
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
    def build_3d_circlip_body(
        cls,
        target_component: 'adsk.fusion.Component',
        center_x_mm: float,
        center_y_mm: float,
        z_offset_mm: float,
        pin_dia_mm: float = 8.0,
        circlip_type: str = "DIN_471",
        name: str = "Snap_Circlip"
    ) -> Optional['adsk.fusion.BRepBody']:
        """
        Creates a parametric, flexible 3D printable snap retaining ring (C-Clip / DIN 471).
        """
        if not adsk or not target_component:
            return None

        features = target_component.features
        sketches = target_component.sketches
        extrudes = features.extrudeFeatures

        info = get_circlip_info(circlip_type, pin_dia_mm)
        d1 = info.get("d1", pin_dia_mm)
        d2 = info.get("d2", max(1.0, pin_dia_mm - 0.4))
        thickness_mm = info.get("s", 0.8)

        cx_cm = center_x_mm * 0.1
        cy_cm = center_y_mm * 0.1
        z_off_cm = (z_offset_mm) * 0.1
        thickness_cm = thickness_mm * 0.1

        # Geometry dimensions
        r_in_cm = (d2 / 2.0) * 0.1
        r_out_cm = ((d1 + 2.4) / 2.0) * 0.1
        half_open_angle = math.radians(35.0)  # 70-degree snap mouth opening

        sketch_plane = cls.get_z_plane(target_component, z_off_cm)
        sketch = sketches.add(sketch_plane)
        sketch.name = f"{name}_Sketch"
        sketch.isComputeDeferred = True

        # Inner Arc (From +35 deg through 180 deg to -35 deg)
        p_in_start = adsk.core.Point3D.create(
            cx_cm + r_in_cm * math.cos(half_open_angle),
            cy_cm + r_in_cm * math.sin(half_open_angle),
            0.0
        )
        p_in_mid = adsk.core.Point3D.create(
            cx_cm - r_in_cm,
            cy_cm,
            0.0
        )
        p_in_end = adsk.core.Point3D.create(
            cx_cm + r_in_cm * math.cos(-half_open_angle),
            cy_cm + r_in_cm * math.sin(-half_open_angle),
            0.0
        )

        inner_arc = sketch.sketchCurves.sketchArcs.addByThreePoints(p_in_start, p_in_mid, p_in_end)

        # Outer Arc (From +35 deg through 180 deg to -35 deg)
        p_out_start = adsk.core.Point3D.create(
            cx_cm + r_out_cm * math.cos(half_open_angle),
            cy_cm + r_out_cm * math.sin(half_open_angle),
            0.0
        )
        p_out_mid = adsk.core.Point3D.create(
            cx_cm - r_out_cm,
            cy_cm,
            0.0
        )
        p_out_end = adsk.core.Point3D.create(
            cx_cm + r_out_cm * math.cos(-half_open_angle),
            cy_cm + r_out_cm * math.sin(-half_open_angle),
            0.0
        )

        outer_arc = sketch.sketchCurves.sketchArcs.addByThreePoints(p_out_start, p_out_mid, p_out_end)

        # Closing end lines (or plier ear lobes)
        lines = sketch.sketchCurves.sketchLines
        lines.addByTwoPoints(inner_arc.startSketchPoint, outer_arc.startSketchPoint)
        lines.addByTwoPoints(inner_arc.endSketchPoint, outer_arc.endSketchPoint)

        # Optional plier eyelets (0.8mm holes for pliers / disassembly)
        if (r_out_cm - r_in_cm) > 0.08:
            hole_r = 0.04  # Ø0.8mm
            ear_r = (r_in_cm + r_out_cm) / 2.0
            h1_x = cx_cm + ear_r * math.cos(half_open_angle + 0.15)
            h1_y = cy_cm + ear_r * math.sin(half_open_angle + 0.15)
            h2_x = cx_cm + ear_r * math.cos(-half_open_angle - 0.15)
            h2_y = cy_cm + ear_r * math.sin(-half_open_angle - 0.15)
            sketch.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(h1_x, h1_y, 0), hole_r)
            sketch.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(h2_x, h2_y, 0), hole_r)

        sketch.isComputeDeferred = False

        prof = None
        for p in sketch.profiles:
            # Profile with 2 holes has 3 loops, or outer profile
            if p.profileLoops.count >= 1:
                prof = p
                break
        if not prof:
            prof = sketch.profiles.item(0)

        ext_in = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-thickness_cm))
        ext_result = extrudes.add(ext_in)

        body = ext_result.bodies.item(0)
        body.name = name
        return body
