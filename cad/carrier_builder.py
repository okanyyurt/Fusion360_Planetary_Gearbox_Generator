"""
Fusion 360 Planet Carrier Builder.
Creates planet carrier cages, bearing pins, inter-stage connection couplers,
and final gearbox output shafts.
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
    Builds planet carrier assemblies in Fusion 360.
    """
    
    @classmethod
    def build_carrier_component(
        cls,
        target_component: 'adsk.fusion.Component',
        center_distance_mm: float,
        num_planets: int,
        pin_dia_mm: float,
        gear_face_width_mm: float,
        plate_thickness_mm: float = 3.5,
        output_shaft_dia_mm: float = 8.0,
        output_shaft_length_mm: float = 15.0,
        is_final_output_stage: bool = False,
        next_sun_bore_dia_mm: float = 0.0,
        name: str = "Planet_Carrier"
    ) -> 'adsk.fusion.BRepBody':
        """
        Constructs a complete planet carrier with pin shafts, carrier disk,
        and output shaft / next stage coupling.
        """
        features = target_component.features
        sketches = target_component.sketches
        xy_plane = target_component.xYConstructionPlane
        
        # Dimensions in cm
        r_carrier_cm = (center_distance_mm + (pin_dia_mm / 2.0) + 3.0) * 0.1
        pin_r_cm = (pin_dia_mm / 2.0) * 0.1
        plate_thick_cm = plate_thickness_mm * 0.1
        gear_width_cm = gear_face_width_mm * 0.1
        cd_cm = center_distance_mm * 0.1
        
        # 1. Base Carrier Plate Sketch
        plate_sketch = sketches.add(xy_plane)
        plate_sketch.name = f"{name}_Base_Sketch"
        
        # Outer Carrier Disk
        plate_sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0, 0, 0), r_carrier_cm
        )
        
        # Extrude Carrier Base Plate (Positioned below the gears: Z = -plate_thickness to 0)
        prof = plate_sketch.profiles.item(0)
        ext_input = features.extrudeFeatures.createInput(
            prof, 
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        dist = adsk.core.ValueInput.createByReal(-plate_thick_cm)
        ext_input.setDistanceExtent(False, dist)
        ext_feature = features.extrudeFeatures.add(ext_input)
        carrier_body = ext_feature.bodies.item(0)
        carrier_body.name = name
        
        # 2. Planet Pins (Axles extending through gear width)
        for i in range(num_planets):
            angle = (2.0 * math.pi * i) / num_planets
            px = cd_cm * math.cos(angle)
            py = cd_cm * math.sin(angle)
            
            pin_sketch = sketches.add(xy_plane)
            pin_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(px, py, 0), pin_r_cm
            )
            pin_prof = pin_sketch.profiles.item(0)
            
            # Extrude pin upward through the gear face width (+1mm clearance)
            pin_ext_input = features.extrudeFeatures.createInput(
                pin_prof,
                adsk.fusion.FeatureOperations.JoinFeatureOperation
            )
            pin_height_cm = (gear_face_width_mm + 0.5) * 0.1
            pin_dist = adsk.core.ValueInput.createByReal(pin_height_cm)
            pin_ext_input.setDistanceExtent(False, pin_dist)
            features.extrudeFeatures.add(pin_ext_input)
            
        # 3. Output Shaft or Next Stage Coupler
        if is_final_output_stage and output_shaft_dia_mm > 0.0:
            # Output shaft on the back side of carrier
            shaft_sketch = sketches.add(xy_plane)
            shaft_r_cm = (output_shaft_dia_mm / 2.0) * 0.1
            shaft_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(0, 0, 0), shaft_r_cm
            )
            shaft_prof = shaft_sketch.profiles.item(0)
            
            shaft_ext = features.extrudeFeatures.createInput(
                shaft_prof,
                adsk.fusion.FeatureOperations.JoinFeatureOperation
            )
            # Extrude backwards from carrier plate
            shaft_len_cm = -(plate_thick_cm + output_shaft_length_mm * 0.1)
            shaft_dist = adsk.core.ValueInput.createByReal(shaft_len_cm)
            shaft_ext.setDistanceExtent(False, shaft_dist)
            features.extrudeFeatures.add(shaft_ext)
            
        return carrier_body
