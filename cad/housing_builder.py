"""
Fusion 360 Gearbox Housing & Motor Flange Builder.
Constructs motor mounting plates (NEMA & custom), outer housing, and output caps.
"""
import math
from typing import Dict, Optional

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    adsk = None

from core.motor_catalog import get_motor_info

class HousingBuilder:
    """
    Builds motor adapters and casing housings in Fusion 360.
    """
    
    @classmethod
    def build_motor_mount_plate(
        cls,
        target_component: 'adsk.fusion.Component',
        motor_code: str,
        housing_outer_dia_mm: float,
        plate_thickness_mm: float = 4.0,
        name: str = "Motor_Mount_Flange"
    ) -> 'adsk.fusion.BRepBody':
        """
        Creates motor adapter plate with pilot recess and mounting bolt holes.
        """
        features = target_component.features
        sketches = target_component.sketches
        xy_plane = target_component.xYConstructionPlane
        
        motor = get_motor_info(motor_code)
        
        # Dimensions in cm
        plate_r_cm = (housing_outer_dia_mm / 2.0) * 0.1
        plate_thick_cm = plate_thickness_mm * 0.1
        pilot_r_cm = (motor["pilot_diameter"] / 2.0) * 0.1
        bolt_pcd_cm = (motor["bolt_pitch_circle"] / 2.0) * 0.1
        bolt_hole_r_cm = (motor["bolt_hole_dia"] / 2.0) * 0.1
        
        # Base Plate Sketch
        plate_sketch = sketches.add(xy_plane)
        plate_sketch.name = f"{name}_Sketch"
        
        # Outer circle
        plate_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), plate_r_cm
        )
        # Center pilot hole / shaft clearance hole
        plate_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), pilot_r_cm
        )
        # Motor bolt holes (4 holes arranged in 90 degrees or square)
        for i in range(4):
            angle = (math.pi / 4.0) + (i * math.pi / 2.0)
            bx = bolt_pcd_cm * math.cos(angle)
            by = bolt_pcd_cm * math.sin(angle)
            plate_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(bx, by, 0), bolt_hole_r_cm
            )
            
        # Find main plate profile (largest profile with holes subtracted)
        profiles = plate_sketch.profiles
        target_prof = None
        max_area = 0.0
        for p in profiles:
            area = p.areaProperties().area
            if area > max_area:
                max_area = area
                target_prof = p
                
        if not target_prof:
            return None
            
        ext_input = features.extrudeFeatures.createInput(
            target_prof,
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        dist = adsk.core.ValueInput.createByReal(-plate_thick_cm)
        ext_input.setDistanceExtent(False, dist)
        ext_feature = features.extrudeFeatures.add(ext_input)
        
        body = ext_feature.bodies.item(0)
        body.name = name
        return body
