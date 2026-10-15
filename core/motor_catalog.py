"""
Standard Motor Presets & Shaft Interface Catalog.
Defines motor flange dimensions, shaft diameters, pilot rings, and mounting patterns.
"""
from typing import Dict, List

MOTOR_CATALOG: Dict[str, Dict] = {
    "NEMA17": {
        "kind": "stepper",                  # stepper: speed set by the driver (ratio is a free choice)
        "body_length": 40,              # motor body behind the flange, mm (envelope check)
        "torque_nm": 0.40,             # continuous torque for strength calc (NEMA 17 (42x48): ~0.45 Nm holding, ~0.4 Nm usable at low speed)
        "speed_rpm": 300,
        "screw_head_dia": 5.5,        # DIN 912 mounting screw head (flange counterbore)
        "screw_head_h": 3.0,
        "name": "NEMA 17 Stepper (42mm)",
        "detent_nm": 0.02,              # detent / cogging torque, unpowered (speed-up: start-up feel)
        "max_speed_rpm": 1500,          # highest sensible speed as a generator (0 = unknown)
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
        "kind": "stepper",                  # stepper: speed set by the driver (ratio is a free choice)
        "body_length": 56,              # motor body behind the flange, mm (envelope check)
        "torque_nm": 1.00,             # continuous torque for strength calc (NEMA 23 (57x76): ~1.26 Nm holding)
        "speed_rpm": 300,
        "screw_head_dia": 7.0,        # DIN 912 mounting screw head (flange counterbore)
        "screw_head_h": 4.0,
        "name": "NEMA 23 Stepper (57mm)",
        "detent_nm": 0.05,              # detent / cogging torque, unpowered (speed-up: start-up feel)
        "max_speed_rpm": 1200,          # highest sensible speed as a generator (0 = unknown)
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
        "kind": "stepper",                  # stepper: speed set by the driver (ratio is a free choice)
        "body_length": 80,              # motor body behind the flange, mm (envelope check)
        "torque_nm": 3.50,             # continuous torque for strength calc (NEMA 34 (86x98): ~4.5 Nm holding)
        "speed_rpm": 300,
        "screw_head_dia": 8.5,        # DIN 912 mounting screw head (flange counterbore)
        "screw_head_h": 5.0,
        "name": "NEMA 34 Stepper (86mm)",
        "detent_nm": 0.15,              # detent / cogging torque, unpowered (speed-up: start-up feel)
        "max_speed_rpm": 1000,          # highest sensible speed as a generator (0 = unknown)
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
        "kind": "dc",                  # stepper: speed set by the driver (ratio is a free choice)
        "body_length": 67,              # motor body behind the flange, mm (envelope check)
        "torque_nm": 0.12,             # continuous torque for strength calc (775 DC 12V: rated point)
        "speed_rpm": 9000,
        "screw_head_dia": 7.0,        # DIN 912 mounting screw head (flange counterbore)
        "screw_head_h": 4.0,
        "name": "775 DC Motor (44mm)",
        "detent_nm": 0.005,              # detent / cogging torque, unpowered (speed-up: start-up feel)
        "max_speed_rpm": 12000,          # highest sensible speed as a generator (0 = unknown)
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
        "kind": "dc",                  # stepper: speed set by the driver (ratio is a free choice)
        "body_length": 50,              # motor body behind the flange, mm (envelope check)
        "torque_nm": 0.03,             # continuous torque for strength calc (540/550: rated point)
        "speed_rpm": 15000,
        "screw_head_dia": 5.5,        # DIN 912 mounting screw head (flange counterbore)
        "screw_head_h": 3.0,
        "name": "540 / 550 DC / BLDC Motor (36mm)",
        "detent_nm": 0.002,              # detent / cogging torque, unpowered (speed-up: start-up feel)
        "max_speed_rpm": 20000,          # highest sensible speed as a generator (0 = unknown)
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
        "kind": "custom",                  # stepper: speed set by the driver (ratio is a free choice)
        "body_length": 40,              # motor body behind the flange, mm (envelope check)
        "torque_nm": 0.30,             # continuous torque for strength calc (Custom motor defaults)
        "speed_rpm": 1000,
        "screw_head_dia": 5.5,        # DIN 912 mounting screw head (flange counterbore)
        "screw_head_h": 3.0,
        "name": "Custom Motor / Shaft",
        "detent_nm": 0.0,              # detent / cogging torque, unpowered (speed-up: start-up feel)
        "max_speed_rpm": 0,          # highest sensible speed as a generator (0 = unknown)
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
            "default_shaft_type": data["default_shaft_type"],
            "torque_nm": data.get("torque_nm", 0.3),
            "speed_rpm": data.get("speed_rpm", 1000)
        })
    return items
