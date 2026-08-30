"""
Standard Motor Presets & Shaft Interface Catalog.
Defines motor flange dimensions, shaft diameters, pilot rings, and mounting patterns.
"""
from typing import Dict, List

MOTOR_CATALOG: Dict[str, Dict] = {
    "NEMA17": {
        "name": "NEMA 17 Stepper (42mm)",
        "flange_size": 42.3,
        "pilot_diameter": 22.0,
        "pilot_depth": 2.0,
        "bolt_pitch_circle": 43.8,  # Diagonal PCD (31mm x 31mm square = ~43.84mm PCD)
        "bolt_size": "M3",
        "bolt_hole_dia": 3.4,
        "default_shaft_dia": 5.0,
        "default_shaft_type": "D_CUT",
        "default_d_flat_depth": 0.5  # 5mm shaft with 4.5mm flat
    },
    "NEMA23": {
        "name": "NEMA 23 Stepper (57mm)",
        "flange_size": 57.0,
        "pilot_diameter": 38.1,
        "pilot_depth": 2.0,
        "bolt_pitch_circle": 66.7,  # 47.14mm square = ~66.7mm PCD
        "bolt_size": "M4",
        "bolt_hole_dia": 4.5,
        "default_shaft_dia": 6.35,  # 1/4 inch or 8mm
        "default_shaft_type": "D_CUT",
        "default_d_flat_depth": 0.6
    },
    "NEMA34": {
        "name": "NEMA 34 Stepper (86mm)",
        "flange_size": 86.0,
        "pilot_diameter": 73.0,
        "pilot_depth": 3.0,
        "bolt_pitch_circle": 98.4,
        "bolt_size": "M5",
        "bolt_hole_dia": 5.5,
        "default_shaft_dia": 14.0,
        "default_shaft_type": "KEYWAY",
        "default_d_flat_depth": 1.0
    },
    "MOTOR_775": {
        "name": "775 DC Motor (44mm)",
        "flange_size": 44.0,
        "pilot_diameter": 17.5,
        "pilot_depth": 4.5,
        "bolt_pitch_circle": 29.0,
        "bolt_size": "M4",
        "bolt_hole_dia": 4.2,
        "default_shaft_dia": 5.0,
        "default_shaft_type": "ROUND",
        "default_d_flat_depth": 0.5
    },
    "MOTOR_540_550": {
        "name": "540 / 550 DC / BLDC Motor (36mm)",
        "flange_size": 36.0,
        "pilot_diameter": 13.0,
        "pilot_depth": 3.0,
        "bolt_pitch_circle": 25.0,
        "bolt_size": "M3",
        "bolt_hole_dia": 3.2,
        "default_shaft_dia": 3.175,  # 1/8 inch
        "default_shaft_type": "D_CUT",
        "default_d_flat_depth": 0.4
    },
    "CUSTOM": {
        "name": "Custom Motor / Shaft",
        "flange_size": 50.0,
        "pilot_diameter": 20.0,
        "pilot_depth": 2.0,
        "bolt_pitch_circle": 40.0,
        "bolt_size": "M3",
        "bolt_hole_dia": 3.4,
        "default_shaft_dia": 5.0,
        "default_shaft_type": "ROUND",
        "default_d_flat_depth": 0.5
    }
}

def get_motor_info(motor_code: str) -> Dict:
    """Returns motor preset specs."""
    return MOTOR_CATALOG.get(motor_code, MOTOR_CATALOG["CUSTOM"])

def get_motor_list() -> List[Dict]:
    """Returns all motor presets."""
    items = []
    for code, data in MOTOR_CATALOG.items():
        items.append({
            "code": code,
            "name": data["name"],
            "flange_size": data["flange_size"],
            "default_shaft_dia": data["default_shaft_dia"],
            "default_shaft_type": data["default_shaft_type"]
        })
    return items
