"""
Material database for gear strength and structural checks.

Values are DESIGN values (fatigue-relevant, room temperature) rather than datasheet ultimate
strengths. For FDM parts they are derated for layer adhesion and porosity; plastic gear limits
follow the approach of VDI 2736 (POM/PA reference values) scaled for printed parts.

    E        Young's modulus [MPa]
    nu       Poisson's ratio
    rho      density [g/cm^3]
    sigma_F  allowable tooth-root bending stress (fatigue, ~1e7 cycles) [MPa]
    sigma_H  allowable contact (Hertz) stress [MPa]
    sigma_S  allowable structural tensile/bending stress for carriers, pins, shafts [MPa]
    eta      typical efficiency of one planetary stage made of this material
    printed  FDM/SLA printed part (uses lower dynamic-factor quality, layer derating)

Always verify critical designs with test prints: printer, slicer settings and filament brand
change printed strength by +/-30 %.
"""
from typing import Dict, List

MATERIALS: Dict[str, Dict] = {
    "PLA": {"name": "PLA / PLA+", "E": 3500.0, "nu": 0.36, "rho": 1.24, "sigma_F": 22.0, "sigma_H": 40.0,
            "sigma_S": 20.0, "eta": 0.94, "printed": True, "t_max": 50,
            "print": "Katman 0.12-0.16 mm · 4+ duvar · %60+ gyroid dolgu (dişliler %100) · 205-215 °C"},
    "PETG": {"name": "PETG", "E": 2100.0, "nu": 0.38, "rho": 1.27, "sigma_F": 18.0, "sigma_H": 32.0,
             "sigma_S": 16.0, "eta": 0.94, "printed": True, "t_max": 70,
             "print": "Katman 0.12-0.16 mm · 4+ duvar · %60+ dolgu · 235-245 °C, fan %30-50"},
    "ABS": {"name": "ABS / ASA", "E": 2200.0, "nu": 0.35, "rho": 1.05, "sigma_F": 16.0, "sigma_H": 30.0,
            "sigma_S": 15.0, "eta": 0.94, "printed": True, "t_max": 85,
            "print": "Kapalı kabin · Katman 0.12-0.16 mm · 4+ duvar · %60+ dolgu · 245-255 °C"},
    "PA12": {"name": "Naylon (PA12 / PA6)", "E": 1700.0, "nu": 0.39, "rho": 1.02, "sigma_F": 20.0,
             "sigma_H": 36.0, "sigma_S": 18.0, "eta": 0.95, "printed": True, "t_max": 90,
             "print": "Kurutulmuş filament (6 sa 70 °C) · 4+ duvar · %80+ dolgu · 250-265 °C · kendinden yağlamalı, en iyi aşınma"},
    "PACF": {"name": "Karbon fiber naylon (PA-CF)", "E": 6000.0, "nu": 0.36, "rho": 1.18, "sigma_F": 30.0,
             "sigma_H": 45.0, "sigma_S": 30.0, "eta": 0.95, "printed": True, "t_max": 110,
             "print": "Sertleştirilmiş nozul (≥0.4) · kurutulmuş · 4+ duvar · %80+ dolgu · 260-280 °C"},
    "PC": {"name": "Polikarbonat (PC)", "E": 2300.0, "nu": 0.37, "rho": 1.20, "sigma_F": 22.0, "sigma_H": 38.0,
           "sigma_S": 22.0, "eta": 0.94, "printed": True, "t_max": 110,
           "print": "Kapalı kabin · 270-290 °C · 4+ duvar · %60+ dolgu"},
    "RESIN": {"name": "Reçine (SLA tough/ABS-like)", "E": 2000.0, "nu": 0.38, "rho": 1.15, "sigma_F": 15.0,
              "sigma_H": 30.0, "sigma_S": 15.0, "eta": 0.94, "printed": True, "t_max": 55,
              "print": "Tough/ABS-like reçine · 0.05 mm katman · tam kürleme sonrası yükleyin"},
    "POM": {"name": "POM / Delrin (CNC)", "E": 2800.0, "nu": 0.35, "rho": 1.41, "sigma_F": 35.0, "sigma_H": 50.0,
            "sigma_S": 30.0, "eta": 0.96, "printed": False, "t_max": 90,
            "print": "CNC işleme (VDI 2736 referans malzemesi)"},
    "AL7075": {"name": "Alüminyum 7075-T6 (CNC)", "E": 71700.0, "nu": 0.33, "rho": 2.81, "sigma_F": 120.0,
               "sigma_H": 400.0, "sigma_S": 200.0, "eta": 0.97, "printed": False, "t_max": 150,
               "print": "CNC işleme · eloksal önerilir"},
    "STEEL": {"name": "Çelik 42CrMo4 / C45 (CNC)", "E": 210000.0, "nu": 0.30, "rho": 7.85, "sigma_F": 250.0,
              "sigma_H": 600.0, "sigma_S": 300.0, "eta": 0.97, "printed": False, "t_max": 150,
              "print": "CNC / azdırma · ıslah veya indüksiyon sertleştirme"},
}

STEEL_PIN = {"name": "Çelik pim (DIN 6325 m6, sertleştirilmiş)", "sigma_S": 400.0, "E": 210000.0}


def get_material(code: str) -> Dict:
    return MATERIALS.get(code, MATERIALS["PLA"])


def material_list() -> List[Dict]:
    return [{"code": k, "name": v["name"], "printed": v["printed"]} for k, v in MATERIALS.items()]
