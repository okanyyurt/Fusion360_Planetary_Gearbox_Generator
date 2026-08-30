"""
Hierarchical Multi-Stage Planetary Gearbox Assembly Manager.
Assembles all gear stages, carriers, pins, and housing components in Autodesk Fusion 360.
"""
import math
from typing import Dict, List, Optional

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    adsk = None

from core.bearing_catalog import get_bearing_info
from core.motor_catalog import get_motor_info
from cad.gear_builder import GearBuilder
from cad.carrier_builder import CarrierBuilder
from cad.housing_builder import HousingBuilder

class PlanetaryAssemblyManager:
    """
    Coordinates end-to-end CAD construction of multi-stage planetary gearboxes.
    """
    
    @classmethod
    def apply_appearance(cls, body: 'adsk.fusion.BRepBody', color_name: str) -> None:
        """Applies a default appearance color to a CAD body if available."""
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return
            appearances = design.appearances
            # Try finding material or fallback
            for app_item in appearances:
                if color_name.lower() in app_item.name.lower():
                    body.appearance = app_item
                    return
        except Exception:
            pass

    @classmethod
    def _send_progress(cls, palette, message: str, percent: int = None) -> None:
        """Sends a progress update to the HTML UI palette."""
        if palette is None:
            return
        import json
        data = {'event': 'progress', 'message': message}
        if percent is not None:
            data['percent'] = percent
        try:
            palette.sendInfoToHTML('fusionMessageReceived', json.dumps(data))
        except Exception:
            pass

    @classmethod
    def generate_gearbox(cls, config: Dict) -> bool:
        """
        Main execution entry point: Generates the full 3D gearbox inside active Fusion 360 document.
        """
        app = adsk.core.Application.get()
        doc = app.activeDocument
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return False

        # Resolve palette for progress messages
        try:
            ui = app.userInterface
            palette = ui.palettes.itemById('PlanetaryGearboxPalette_v1')
        except Exception:
            palette = None

        root_comp = design.rootComponent

        # User settings extraction
        stages_data = config.get("stages", [])
        num_stages = len(stages_data)
        if num_stages == 0:
            return False

        is_herringbone = config.get("is_herringbone", True)
        helix_angle = float(config.get("helix_angle", 25.0))
        face_width = float(config.get("face_width", 12.0))
        pressure_angle = float(config.get("pressure_angle", 20.0))
        backlash = float(config.get("backlash", 0.20))

        # High-precision spline mode: use ALL computed involute points (no subsampling).
        # Automatically enabled for CNC_METAL (0.05mm tolerance needs maximum fidelity).
        # FDM/SLA use subsampled splines (≤200 pts) — well within their tolerances.
        mfg_preset = config.get("mfg_preset", "FDM_3D_PRINT")
        high_precision = (mfg_preset == "CNC_METAL")


        motor_code = config.get("motor_preset", "NEMA17")
        motor_shaft_dia = float(config.get("motor_shaft_dia", 5.0))
        motor_shaft_type = config.get("motor_shaft_type", "D_CUT")

        bearing_code = config.get("bearing_type", "688ZZ")
        bearing_info = get_bearing_info(bearing_code)

        # Calculate housing outer diameter based on largest ring gear
        first_stage = stages_data[0]
        module = float(first_stage.get("module", 1.0))
        z_ring = int(first_stage.get("z_ring", 48))
        d_ring_outer_pitch = module * z_ring
        housing_outer_dia = d_ring_outer_pitch + (module * 6.0) + 10.0

        cls._send_progress(palette, "⚙️ Redüktör bileşen ağacı kuruluyor...", 5)

        # Create Master Gearbox Sub-Component
        master_occ = root_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        master_comp = master_occ.component
        master_comp.name = f"Planetary_Gearbox_{config.get('total_ratio', 'Auto')}x"

        cls._send_progress(palette, "🔧 Çember dişli / gövde oluşturuluyor...", 15)

        # Build Common Outer Ring Gear & Housing
        if config.get("generate_housing", True):
            total_gearbox_length = num_stages * (face_width + 5.0) + 10.0
            ring_body = GearBuilder.build_internal_ring_gear_body(
                target_component=master_comp,
                z_ring=z_ring,
                module=module,
                face_width_mm=total_gearbox_length,
                outer_housing_dia_mm=housing_outer_dia,
                is_herringbone=is_herringbone,
                helix_angle_deg=helix_angle,
                pressure_angle_deg=pressure_angle,
                backlash_mm=backlash,
                name="Ring_Gear_Housing"
            )

            if ring_body:
                cls.apply_appearance(ring_body, "Steel")
                
            # Build Motor Flange Adapter
            HousingBuilder.build_motor_mount_plate(
                target_component=master_comp,
                motor_code=motor_code,
                housing_outer_dia_mm=housing_outer_dia,
                plate_thickness_mm=4.0,
                name="Motor_Mount_Flange"
            )
            
        # Build Each Stage
        z_current_offset = 2.0  # mm from motor mount plate
        
        for stage_idx, stage in enumerate(stages_data):
            stage_occ = master_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            stage_comp = stage_occ.component
            stage_comp.name = f"Stage_{stage_idx + 1}"
            
            zs = int(stage.get("z_sun", 12))
            zp = int(stage.get("z_planet", 18))
            zr = int(stage.get("z_ring", 48))
            np_planets = int(stage.get("num_planets", 3))
            cd_mm = module * (zs + zp) / 2.0
            
            # Sun gear bore: Stage 1 connects to motor shaft; Stage 2+ connects to Stage 1 carrier
            if stage_idx == 0:
                sun_bore_dia = motor_shaft_dia
                sun_bore_type = motor_shaft_type
            else:
                sun_bore_dia = 6.0  # Inter-stage connector coupling
                sun_bore_type = "ROUND"
                
            # 1. Build Sun Gear Body
            sun_body = GearBuilder.build_external_gear_body(
                target_component=stage_comp,
                z_teeth=zs,
                module=module,
                face_width_mm=face_width,
                is_herringbone=is_herringbone,
                helix_angle_deg=helix_angle,
                bore_dia_mm=sun_bore_dia,
                bore_type=sun_bore_type,
                pressure_angle_deg=pressure_angle,
                backlash_mm=backlash,
                name=f"Sun_Gear_Stg{stage_idx + 1}"
            )
            if sun_body:
                cls.apply_appearance(sun_body, "Gold")
                
            # 2. Build Planet Gears (x N)
            # Planet bore matches bearing outer diameter (for press-fit) or pin diameter (for plain pin)
            planet_bore_dia = bearing_info["d_outer"] if bearing_code != "CUSTOM_PIN" else bearing_info["d_inner"]
            pin_dia = bearing_info["d_inner"]
            
            for p_idx in range(np_planets):
                planet_angle = (2.0 * math.pi * p_idx) / np_planets
                px_cm = (cd_mm * math.cos(planet_angle)) * 0.1
                py_cm = (cd_mm * math.sin(planet_angle)) * 0.1
                
                planet_occ = stage_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
                planet_comp = planet_occ.component
                planet_comp.name = f"Planet_{stage_idx + 1}_{p_idx + 1}"
                
                planet_body = GearBuilder.build_external_gear_body(
                    target_component=planet_comp,
                    z_teeth=zp,
                    module=module,
                    face_width_mm=face_width,
                    is_herringbone=is_herringbone,
                    helix_angle_deg=helix_angle,
                    bore_dia_mm=planet_bore_dia,
                    bore_type="ROUND",
                    pressure_angle_deg=pressure_angle,
                    backlash_mm=backlash,
                    name=f"Planet_Gear_{p_idx + 1}"
                )
                if planet_body:
                    cls.apply_appearance(planet_body, "Satin")
                    
                # Move planet occurrence to its pitch circle position
                mat = adsk.core.Matrix3D.create()
                mat.setCell(0, 3, px_cm)
                mat.setCell(1, 3, py_cm)
                planet_occ.transform = mat
                
            # 3. Build Planet Carrier
            is_final = (stage_idx == num_stages - 1)
            carrier_body = CarrierBuilder.build_carrier_component(
                target_component=stage_comp,
                center_distance_mm=cd_mm,
                num_planets=np_planets,
                pin_dia_mm=pin_dia,
                gear_face_width_mm=face_width,
                plate_thickness_mm=3.5,
                output_shaft_dia_mm=8.0 if is_final else 6.0,
                output_shaft_length_mm=20.0 if is_final else 6.0,
                is_final_output_stage=is_final,
                name=f"Carrier_Stg{stage_idx + 1}"
            )
            if carrier_body:
                cls.apply_appearance(carrier_body, "Aluminum")
                
            # Shift stage along Z axis
            stage_mat = adsk.core.Matrix3D.create()
            stage_mat.setCell(2, 3, z_current_offset * 0.1)
            stage_occ.transform = stage_mat
            
            z_current_offset += face_width + 4.5
            
        return True
