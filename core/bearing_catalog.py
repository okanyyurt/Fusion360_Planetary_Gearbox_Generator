"""
Standard Bearings & Bushings Database for Planetary Gearbox Design.
Provides standard dimensional data (inner bore, outer diameter, width) and fit tolerances.
"""
from typing import Dict, List, Optional

BEARING_CATALOG: Dict[str, Dict] = {
    "608ZZ": {
        "name": "608ZZ (Skate/Standard)",
        "d_inner": 8.0,
        "d_outer": 22.0,
        "width": 7.0,
        "description": "Standard skate bearing, very robust, 8mm pin/bore",
        "recommended_min_module": 1.5
    },
    "688ZZ": {
        "name": "688ZZ (Slim 8mm)",
        "d_inner": 8.0,
        "d_outer": 16.0,
        "width": 5.0,
        "description": "Slim series 8mm inner diameter, ideal for medium-compact gearboxes",
        "recommended_min_module": 1.0
    },
    "686ZZ": {
        "name": "686ZZ (Slim 6mm)",
        "d_inner": 6.0,
        "d_outer": 13.0,
        "width": 5.0,
        "description": "Slim 6mm inner diameter, balanced size and strength",
        "recommended_min_module": 0.8
    },
    "684ZZ": {
        "name": "684ZZ (Compact 4mm)",
        "d_inner": 4.0,
        "d_outer": 9.0,
        "width": 4.0,
        "description": "Compact 4mm bore, excellent for small NEMA 17 gearboxes",
        "recommended_min_module": 0.6
    },
    "623ZZ": {
        "name": "623ZZ (Micro 3mm)",
        "d_inner": 3.0,
        "d_outer": 10.0,
        "width": 4.0,
        "description": "Micro bearing with 3mm pin, great for high gear ratios in small frames",
        "recommended_min_module": 0.6
    },
    "MR105ZZ": {
        "name": "MR105-ZZ (Ultra-slim 5mm)",
        "d_inner": 5.0,
        "d_outer": 10.0,
        "width": 4.0,
        "description": "Ultra slim 5mm bore x 10mm OD, popular for robotic joints",
        "recommended_min_module": 0.7
    },
    "MR117ZZ": {
        "name": "MR117-ZZ (Ultra-slim 7mm)",
        "d_inner": 7.0,
        "d_outer": 11.0,
        "width": 3.0,
        "description": "Very slim profile, saves maximum radial and axial space",
        "recommended_min_module": 0.8
    },
    "MR128ZZ": {
        "name": "MR128-ZZ (Slim 8mm)",
        "d_inner": 8.0,
        "d_outer": 12.0,
        "width": 3.5,
        "description": "Ultra-thin 8mm bore x 12mm OD",
        "recommended_min_module": 0.8
    },
    "6700ZZ": {
        "name": "6700ZZ (Thin 10mm)",
        "d_inner": 10.0,
        "d_outer": 15.0,
        "width": 4.0,
        "description": "Thin section 10mm bore for large hollow carriers",
        "recommended_min_module": 1.0
    },
    "CUSTOM_PIN": {
        "name": "No Bearing (Dowel Pin / Bushing)",
        "d_inner": 5.0,
        "d_outer": 5.0,
        "width": 0.0,
        "description": "Direct smooth steel dowel pin or bronze sleeve bushing",
        "recommended_min_module": 0.5
    }
}

def get_bearing_info(bearing_code: str) -> Dict:
    """Returns bearing parameters for a given code."""
    return BEARING_CATALOG.get(bearing_code, BEARING_CATALOG["CUSTOM_PIN"])

def get_bearing_list() -> List[Dict]:
    """Returns list of all available bearings."""
    items = []
    for code, data in BEARING_CATALOG.items():
        items.append({
            "code": code,
            "name": data["name"],
            "d_inner": data["d_inner"],
            "d_outer": data["d_outer"],
            "width": data["width"],
            "description": data["description"]
        })
    return items
