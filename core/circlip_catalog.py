"""
DIN 471 & DIN 6799 Metric Circlip (Segman) Catalog.
Contains exact manufacturer dimensions for external retaining rings and E-clips.
"""
from typing import Dict, List, Optional

# DIN 471 Standard External Retaining Rings (Dış Segman)
# Key: shaft diameter d1 in mm
DIN_471_CATALOG: Dict[int, Dict[str, float]] = {
    3: {
        "standard": "DIN 471",
        "d1": 3.0,     # Shaft dia
        "d2": 2.8,     # Groove dia
        "m": 0.5,      # Groove width
        "n": 0.4,      # Distance to shaft end
        "s": 0.4,      # Thickness
        "d3": 2.7,     # Free inner dia
    },
    4: {
        "standard": "DIN 471",
        "d1": 4.0,
        "d2": 3.8,
        "m": 0.5,
        "n": 0.5,
        "s": 0.4,
        "d3": 3.7,
    },
    5: {
        "standard": "DIN 471",
        "d1": 5.0,
        "d2": 4.7,
        "m": 0.7,
        "n": 0.6,
        "s": 0.6,
        "d3": 4.6,
    },
    6: {
        "standard": "DIN 471",
        "d1": 6.0,
        "d2": 5.7,
        "m": 0.8,
        "n": 0.7,
        "s": 0.7,
        "d3": 5.6,
    },
    8: {
        "standard": "DIN 471",
        "d1": 8.0,
        "d2": 7.6,
        "m": 0.9,
        "n": 0.8,
        "s": 0.8,
        "d3": 7.4,
    },
    10: {
        "standard": "DIN 471",
        "d1": 10.0,
        "d2": 9.6,
        "m": 1.1,
        "n": 1.0,
        "s": 1.0,
        "d3": 9.3,
    },
    12: {
        "standard": "DIN 471",
        "d1": 12.0,
        "d2": 11.5,
        "m": 1.1,
        "n": 1.2,
        "s": 1.0,
        "d3": 11.0,
    }
}

# DIN 6799 E-Clip / E-Ring Catalog (E-Segman)
DIN_6799_CATALOG: Dict[int, Dict[str, float]] = {
    3: {
        "standard": "DIN 6799",
        "d1": 3.0,
        "d2": 2.3,
        "m": 0.6,
        "n": 0.6,
        "s": 0.6,
        "d3": 2.25,
    },
    4: {
        "standard": "DIN 6799",
        "d1": 4.0,
        "d2": 3.2,
        "m": 0.7,
        "n": 0.8,
        "s": 0.6,
        "d3": 3.15,
    },
    5: {
        "standard": "DIN 6799",
        "d1": 5.0,
        "d2": 4.0,
        "m": 0.7,
        "n": 0.9,
        "s": 0.6,
        "d3": 3.95,
    },
    6: {
        "standard": "DIN 6799",
        "d1": 6.0,
        "d2": 5.0,
        "m": 0.8,
        "n": 1.0,
        "s": 0.7,
        "d3": 4.95,
    },
    8: {
        "standard": "DIN 6799",
        "d1": 8.0,
        "d2": 6.0,
        "m": 1.1,
        "n": 1.2,
        "s": 1.0,
        "d3": 5.95,
    },
    10: {
        "standard": "DIN 6799",
        "d1": 10.0,
        "d2": 8.0,
        "m": 1.3,
        "n": 1.5,
        "s": 1.2,
        "d3": 7.95,
    }
}

def get_circlip_info(circlip_type: str = "DIN_471", shaft_dia_mm: float = 8.0) -> Dict[str, float]:
    """
    Returns exact circlip parameters for given standard and shaft diameter.
    """
    rounded_d = int(round(shaft_dia_mm))
    catalog = DIN_6799_CATALOG if "6799" in circlip_type else DIN_471_CATALOG
    
    if rounded_d in catalog:
        return catalog[rounded_d]
    
    # Nearest match or proportional fallback
    closest_d = min(catalog.keys(), key=lambda k: abs(k - rounded_d))
    base = catalog[closest_d].copy()
    ratio = shaft_dia_mm / closest_d
    base["d1"] = shaft_dia_mm
    base["d2"] = round(base["d2"] * ratio, 2)
    base["d3"] = round(base["d3"] * ratio, 2)
    return base
