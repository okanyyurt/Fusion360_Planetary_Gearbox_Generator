"""
Fusion 360 Planetary Gearbox Assembly Manager.
Coordinates multi-stage hierarchy, dedicated component occurrences for every moving gear,
spider carriers, housing enclosures, and top output bearing caps.
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
    Orchestrates full 3D multi-stage planetary gearbox generation in Fusion 360.
    """

    @classmethod
    def apply_appearance(cls, body: 'adsk.fusion.BRepBody', color_name: str) -> None:
        """Applies realistic material appearance to BRep body."""
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return
            appearances = design.appearances
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
            adsk.doEvents()
        except Exception:
            pass

    @classmethod
    def generate_gearbox(cls, config: Dict) -> bool:
        """
        Main execution entry point: Generates the full 3D gearbox inside active Fusion 360 document.
        """
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        
        if not design:
            if ui:
                ui.messageBox("Lütfen aktif bir Fusion 360 tasarım belgesi açın.", "Hata")
            return False

        palette = ui.palettes.itemById('PlanetaryGearboxPalette_v1')
        root_comp = design.rootComponent

        # Extract config parameters
        total_ratio = config.get("total_ratio", 8.0)
        stages_data = config.get("stages", [])
        if not stages_data:
            return False
            
        num_stages = len(stages_data)
        is_herringbone = bool(config.get("is_herringbone", False))
        helix_angle = float(config.get("helix_angle", 25.0))
        face_width = float(config.get("face_width", 12.0))
        pressure_angle = float(config.get("pressure_angle", 20.0))
        motor_code = str(config.get("motor_preset", "NEMA17"))
        motor_shaft_dia = float(config.get("motor_shaft_dia", 5.0))
        motor_shaft_type = str(config.get("motor_shaft_type", "D_CUT"))
        bearing_code = str(config.get("bearing_type", "688ZZ"))
        pin_dia = float(config.get("pin_dia", 4.0))
        output_shaft_dia = float(config.get("output_shaft_dia", 8.0))
        output_shaft_len = float(config.get("output_shaft_len", 20.0))
        backlash = float(config.get("backlash", 0.05))

        bearing_info = get_bearing_info(bearing_code)

        # 1. Setup Master Gearbox Sub-Component
        cls._send_progress(palette, "⚙️ 1/5: Redüktör montaj ağacı kuruluyor...", 10)
        master_occ = root_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        master_comp = master_occ.component
        master_comp.name = f"Planetary_Gearbox_{total_ratio}x"

        # Dimensions
        first_stage = stages_data[0]
        module = float(first_stage.get("module", 1.0))
        z_ring = int(first_stage.get("z_ring", 48))
        d_ring_pitch = module * z_ring
        housing_outer_dia = d_ring_pitch + (module * 6.0) + 8.0
        total_gearbox_length = num_stages * (face_width + 6.0) + 2.0

        # 2. Build Motor Flange Adapter (Base Component at Z = 0)
        cls._send_progress(palette, "🔧 2/5: Motor montaj flanşı üretiliyor...", 25)
        flange_occ = master_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        flange_comp = flange_occ.component
        flange_comp.name = "Motor_Mount_Flange"

        flange_body = HousingBuilder.build_motor_mount_plate(
            target_component=flange_comp,
            motor_code=motor_code,
            housing_outer_dia_mm=housing_outer_dia,
            plate_thickness_mm=5.0,
            name="Motor_Mount_Flange"
        )
        if flange_body:
            cls.apply_appearance(flange_body, "Aluminum")

        # 3. Build Outer Ring Gear Housing Enclosure (Component at Z = 0)
        cls._send_progress(palette, "🛡️ 3/5: Çember dişli gövdesi oluşturuluyor...", 45)
        if config.get("generate_housing", True):
            ring_occ = master_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            ring_comp = ring_occ.component
            ring_comp.name = "Ring_Gear_Housing"

            ring_body = GearBuilder.build_internal_ring_gear_body(
                target_component=ring_comp,
                z_ring=z_ring,
                module=module,
                face_width_mm=total_gearbox_length,
                outer_housing_dia_mm=housing_outer_dia,
                motor_code=motor_code,
                pressure_angle_deg=pressure_angle,
                backlash_mm=backlash,
                name="Ring_Gear_Housing"
            )
            if ring_body:
                cls.apply_appearance(ring_body, "Steel")

        # 4. Build Each Gearbox Stage
        z_current_offset = 3.0  # mm offset from motor mount plate
        
        for stage_idx, stage in enumerate(stages_data):
            cls._send_progress(palette, f"⚡ 4/5: Kademe {stage_idx + 1} dişlileri ve taşıyıcı çiziliyor...", 60 + stage_idx * 15)
            
            stage_mat = adsk.core.Matrix3D.create()
            stage_mat.setCell(2, 3, z_current_offset * 0.1)
            stage_occ = master_comp.occurrences.addNewComponent(stage_mat)
            stage_comp = stage_occ.component
            stage_comp.name = f"Stage_{stage_idx + 1}"
            
            zs = int(stage.get("z_sun", 12))
            zp = int(stage.get("z_planet", 18))
            zr = int(stage.get("z_ring", 48))
            np_planets = int(stage.get("num_planets", 3))
            cd_mm = module * (zs + zp) / 2.0
            
            is_first_stage = (stage_idx == 0)
            is_final_stage = (stage_idx == num_stages - 1)
            
            sun_bore = motor_shaft_dia if is_first_stage else 6.0
            sun_bore_type = motor_shaft_type if is_first_stage else "ROUND"
            
            # A. Build Sun Gear Component
            sun_occ = stage_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            sun_comp = sun_occ.component
            sun_comp.name = f"Sun_Gear_Stg{stage_idx + 1}"

            sun_body = GearBuilder.build_external_gear_body(
                target_component=sun_comp,
                z_teeth=zs,
                module=module,
                face_width_mm=face_width,
                is_herringbone=is_herringbone,
                helix_angle_deg=helix_angle,
                bore_dia_mm=sun_bore,
                bore_type=sun_bore_type,
                pressure_angle_deg=pressure_angle,
                backlash_mm=backlash,
                is_sun_gear=is_first_stage,
                name=f"Sun_Gear_Stg{stage_idx + 1}"
            )
            if sun_body:
                cls.apply_appearance(sun_body, "Brass")
                
            # B. Build Planet Gears as Individual Components (x N)
            root_planet_r = (module * zp / 2.0) - 1.25 * module
            safe_planet_bore = min(bearing_info["d_outer"], (root_planet_r * 2.0) - 2.0)
            if safe_planet_bore < 3.0:
                safe_planet_bore = pin_dia
                
            for p_idx in range(np_planets):
                planet_angle = (2.0 * math.pi * p_idx) / np_planets
                px_cm = (cd_mm * math.cos(planet_angle)) * 0.1
                py_cm = (cd_mm * math.sin(planet_angle)) * 0.1
                
                planet_mat = adsk.core.Matrix3D.create()
                planet_mat.setCell(0, 3, px_cm)
                planet_mat.setCell(1, 3, py_cm)
                
                planet_occ = stage_comp.occurrences.addNewComponent(planet_mat)
                planet_comp = planet_occ.component
                planet_comp.name = f"Planet_{stage_idx + 1}_{p_idx + 1}"
                
                planet_body = GearBuilder.build_external_gear_body(
                    target_component=planet_comp,
                    z_teeth=zp,
                    module=module,
                    face_width_mm=face_width,
                    is_herringbone=is_herringbone,
                    helix_angle_deg=helix_angle,
                    bore_dia_mm=safe_planet_bore,
                    bore_type="ROUND",
                    pressure_angle_deg=pressure_angle,
                    backlash_mm=backlash,
                    is_sun_gear=False,
                    name=f"Planet_Gear_{p_idx + 1}"
                )
                if planet_body:
                    cls.apply_appearance(planet_body, "Steel")
                # Move Planet occurrence to its pitch circle position (px, py)
                p_trans = planet_occ.transform
                p_trans.translation = adsk.core.Vector3D.create(px_cm, py_cm, 0.0)
                planet_occ.transform = p_trans
                
            # C. Build Spider Planet Carrier Component
            carrier_occ = stage_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            carrier_comp = carrier_occ.component
            carrier_comp.name = f"Carrier_Stg{stage_idx + 1}"

            carrier_body = CarrierBuilder.build_carrier_component(
                target_component=carrier_comp,
                center_distance_mm=cd_mm,
                num_planets=np_planets,
                pin_dia_mm=pin_dia,
                gear_face_width_mm=face_width,
                plate_thickness_mm=4.0,
                output_shaft_dia_mm=output_shaft_dia if is_final_stage else 6.0,
                output_shaft_length_mm=output_shaft_len if is_final_stage else 6.0,
                is_final_output_stage=is_final_stage,
                name=f"Carrier_Stg{stage_idx + 1}"
            )
            if carrier_body:
                cls.apply_appearance(carrier_body, "Aluminum")
            
            # Position stage along Z axis
            s_trans = stage_occ.transform
            s_trans.translation = adsk.core.Vector3D.create(0.0, 0.0, z_current_offset * 0.1)
            stage_occ.transform = s_trans
            
            z_current_offset += face_width + 5.0

        # 5. Build Top Output Bearing Cover Cap (Component at Z = total_gearbox_length)
        cls._send_progress(palette, "🎯 5/5: Üst rulman kapağı ekleniyor...", 95)
        cover_occ = master_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        cover_comp = cover_occ.component
        cover_comp.name = "Top_Bearing_Cover"

        cover_body = HousingBuilder.build_top_cover_plate(
            target_component=cover_comp,
            motor_code=motor_code,
            housing_outer_dia_mm=housing_outer_dia,
            bearing_outer_dia_mm=16.0,
            output_shaft_dia_mm=output_shaft_dia,
            plate_thickness_mm=5.0,
            name="Top_Bearing_Cover"
        )
        if cover_body:
            cls.apply_appearance(cover_body, "Aluminum")

        # Move Top Cover to top of gearbox housing
        c_trans = cover_occ.transform
        c_trans.translation = adsk.core.Vector3D.create(0.0, 0.0, total_gearbox_length * 0.1)
        cover_occ.transform = c_trans

        cls._send_progress(palette, "✅ Redüktör Başarıyla Oluşturuldu!", 100)
        return True

AssemblyManager = PlanetaryAssemblyManager
