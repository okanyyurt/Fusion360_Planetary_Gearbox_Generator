"""
Standard Bearings & Bushings Database for Planetary Gearbox Design.
Provides standard dimensional data (inner bore, outer diameter, width), basic load ratings
and fit helpers.

Load ratings C (dynamic) and C0 (static) are in kN and are approximate values from
SKF / NSK miniature deep-groove ball bearing catalogs (2Z / ZZ shielded versions).
They are used for L10 life estimation; verify against your supplier's datasheet.
"""
from typing import Dict, List, Optional


def _b(name: str, d: float, D: float, B: float, C: float, C0: float, desc: str, min_module: float) -> Dict:
    return {"name": name, "d_inner": d, "d_outer": D, "width": B, "C_kN": C, "C0_kN": C0,
            "description": desc, "recommended_min_module": min_module}


BEARING_CATALOG: Dict[str, Dict] = {
    "608ZZ": _b("608ZZ (Skate/Standard)", 8.0, 22.0, 7.0, 3.30, 1.37,
                "Standard skate bearing, very robust, 8mm pin/bore", 1.5),
    "688ZZ": _b("688ZZ (Slim 8mm)", 8.0, 16.0, 5.0, 1.43, 0.67,
                "Slim series 8mm inner diameter, ideal for medium-compact gearboxes", 1.0),
    "686ZZ": _b("686ZZ (Slim 6mm)", 6.0, 13.0, 5.0, 1.08, 0.44,
                "Slim 6mm inner diameter, balanced size and strength", 0.8),
    "684ZZ": _b("684ZZ (Compact 4mm)", 4.0, 9.0, 4.0, 0.64, 0.23,
                "Compact 4mm bore, excellent for small NEMA 17 gearboxes", 0.6),
    "623ZZ": _b("623ZZ (Micro 3mm)", 3.0, 10.0, 4.0, 0.63, 0.22,
                "Micro bearing with 3mm pin, great for high gear ratios in small frames", 0.6),
    "MR105ZZ": _b("MR105-ZZ (Ultra-slim 5mm)", 5.0, 10.0, 4.0, 0.43, 0.17,
                  "Ultra slim 5mm bore x 10mm OD, popular for robotic joints", 0.7),
    "MR117ZZ": _b("MR117-ZZ (Ultra-slim 7mm)", 7.0, 11.0, 3.0, 0.43, 0.19,
                  "Very slim profile, saves maximum radial and axial space", 0.8),
    "MR128ZZ": _b("MR128-ZZ (Slim 8mm)", 8.0, 12.0, 3.5, 0.55, 0.27,
                  "Ultra-thin 8mm bore x 12mm OD", 0.8),
    "6700ZZ": _b("6700ZZ (Thin 10mm)", 10.0, 15.0, 4.0, 0.85, 0.43,
                 "Thin section 10mm bore for large hollow carriers", 1.0),
    # Extended catalog (used by automatic bearing selection)
    "MR85ZZ": _b("MR85-ZZ (5x8x2.5)", 5.0, 8.0, 2.5, 0.26, 0.11, "Miniature thin bearing", 0.5),
    "604ZZ": _b("604ZZ (4x12x4)", 4.0, 12.0, 4.0, 0.97, 0.36, "Miniature standard 4mm", 0.7),
    "685ZZ": _b("685ZZ (5x11x5)", 5.0, 11.0, 5.0, 0.71, 0.28, "Slim 5mm", 0.7),
    "695ZZ": _b("695ZZ (5x13x4)", 5.0, 13.0, 4.0, 1.08, 0.43, "Slim 5mm, higher capacity", 0.8),
    "625ZZ": _b("625ZZ (5x16x5)", 5.0, 16.0, 5.0, 1.73, 0.67, "Standard 5mm", 1.0),
    "687ZZ": _b("687ZZ (7x14x5)", 7.0, 14.0, 5.0, 1.17, 0.51, "Slim 7mm", 0.9),
    "626ZZ": _b("626ZZ (6x19x6)", 6.0, 19.0, 6.0, 2.60, 1.05, "Standard 6mm, high capacity", 1.25),
    "607ZZ": _b("607ZZ (7x19x6)", 7.0, 19.0, 6.0, 2.60, 1.05, "Standard 7mm, high capacity", 1.25),
    "698ZZ": _b("698ZZ (8x19x6)", 8.0, 19.0, 6.0, 2.20, 0.91, "Slim 8mm, high capacity", 1.25),
    "6800ZZ": _b("6800ZZ (10x19x5)", 10.0, 19.0, 5.0, 1.72, 0.84, "Thin section 10mm", 1.25),
    "6900ZZ": _b("6900ZZ (10x22x6)", 10.0, 22.0, 6.0, 2.70, 1.27, "Light series 10mm", 1.5),
    "6000ZZ": _b("6000ZZ (10x26x8)", 10.0, 26.0, 8.0, 4.55, 1.96, "Standard 10mm, heavy duty", 2.0),
    "6801ZZ": _b("6801ZZ (12x21x5)", 12.0, 21.0, 5.0, 1.92, 1.04, "Thin section 12mm", 1.5),
    "6001ZZ": _b("6001ZZ (12x28x8)", 12.0, 28.0, 8.0, 5.10, 2.39, "Standard 12mm, heavy duty", 2.0),
    "6802ZZ": _b("6802ZZ (15x24x5)", 15.0, 24.0, 5.0, 2.08, 1.26, "Thin section 15mm", 1.75),
    "6803ZZ": _b("6803ZZ (17x26x5)", 17.0, 26.0, 5.0, 2.24, 1.46, "Thin section 17mm (output flange)", 2.0),
    "6804ZZ": _b("6804ZZ (20x32x7)", 20.0, 32.0, 7.0, 4.03, 2.47, "Thin section 20mm (output flange)", 2.0),
    "6805ZZ": _b("6805ZZ (25x37x7)", 25.0, 37.0, 7.0, 4.36, 2.98, "Thin section 25mm (output flange)", 2.5),
    "6806ZZ": _b("6806ZZ (30x42x7)", 30.0, 42.0, 7.0, 4.70, 3.65, "Thin section 30mm (output flange)", 2.5),
    "6807ZZ": _b("6807ZZ (35x47x7)", 35.0, 47.0, 7.0, 4.90, 4.05, "Thin section 35mm (output flange)", 2.5),
    "6808ZZ": _b("6808ZZ (40x52x7)", 40.0, 52.0, 7.0, 5.10, 4.40, "Thin section 40mm (output flange)", 3.0),
    "6809ZZ": _b("6809ZZ (45x58x7)", 45.0, 58.0, 7.0, 6.05, 5.60, "Thin section 45mm (output flange)", 3.0),
    "6810ZZ": _b("6810ZZ (50x65x7)", 50.0, 65.0, 7.0, 6.60, 6.10, "Thin section 50mm (output flange)", 3.0),
    # Large thin-section bearings for high-torque output hubs (SKF 618xx-2Z, approximate ratings)
    "6811ZZ": _b("6811ZZ (55x72x9)", 55.0, 72.0, 9.0, 9.00, 8.80, "Thin section 55mm (output hub)", 3.0),
    "6812ZZ": _b("6812ZZ (60x78x10)", 60.0, 78.0, 10.0, 11.90, 11.40, "Thin section 60mm (output hub)", 3.0),
    "6813ZZ": _b("6813ZZ (65x85x10)", 65.0, 85.0, 10.0, 12.40, 12.70, "Thin section 65mm (output hub)", 3.0),
    "6814ZZ": _b("6814ZZ (70x90x10)", 70.0, 90.0, 10.0, 12.40, 13.20, "Thin section 70mm (output hub)", 3.0),
    "6815ZZ": _b("6815ZZ (75x95x10)", 75.0, 95.0, 10.0, 12.70, 14.30, "Thin section 75mm (output hub)", 3.0),
    "6816ZZ": _b("6816ZZ (80x100x10)", 80.0, 100.0, 10.0, 13.00, 15.00, "Thin section 80mm (output hub)", 3.0),
    "6817ZZ": _b("6817ZZ (85x110x13)", 85.0, 110.0, 13.0, 19.50, 20.80, "Thin section 85mm (output hub)", 3.0),
    "6818ZZ": _b("6818ZZ (90x115x13)", 90.0, 115.0, 13.0, 19.50, 22.00, "Thin section 90mm (output hub)", 3.0),
    "6819ZZ": _b("6819ZZ (95x120x13)", 95.0, 120.0, 13.0, 19.90, 22.80, "Thin section 95mm (output hub)", 3.0),
    "6820ZZ": _b("6820ZZ (100x125x13)", 100.0, 125.0, 13.0, 19.90, 24.00, "Thin section 100mm (output hub)", 3.0),
    # Larger planets of high-torque gearboxes (6904/6004: Ø20 bore -> ISO 8734 Ø20 steel pin)
    "6002ZZ": _b("6002ZZ (15x32x9)", 15.0, 32.0, 9.0, 5.85, 2.85, "Standard 15mm, heavy duty", 2.5),
    "6003ZZ": _b("6003ZZ (17x35x10)", 17.0, 35.0, 10.0, 6.37, 3.25, "Standard 17mm, heavy duty", 2.5),
    "6904ZZ": _b("6904ZZ (20x37x9)", 20.0, 37.0, 9.0, 6.37, 3.65, "Light series 20mm", 2.5),
    "6004ZZ": _b("6004ZZ (20x42x12)", 20.0, 42.0, 12.0, 9.95, 5.00, "Standard 20mm, heavy duty", 3.0),
    "6005ZZ": _b("6005ZZ (25x47x12)", 25.0, 47.0, 12.0, 11.90, 6.55, "Standard 25mm, heavy duty", 3.0),
    "CUSTOM_PIN": {
        "name": "No Bearing (Dowel Pin / Bushing)",
        "d_inner": 5.0,
        "d_outer": 5.0,
        "width": 0.0,
        "C_kN": 0.0,
        "C0_kN": 0.0,
        "description": "Direct smooth steel dowel pin or bronze sleeve bushing",
        "recommended_min_module": 0.5
    }
}


def get_bearing_info(bearing_code: str) -> Dict:
    """Returns bearing parameters for a given code."""
    return BEARING_CATALOG.get(bearing_code, BEARING_CATALOG["CUSTOM_PIN"])


def inner_race_diameter(info: Dict) -> float:
    """Approximate inner-ring shoulder diameter (carrier spacers must stay inside it)."""
    d, D = float(info["d_inner"]), float(info["d_outer"])
    return d + 0.28 * (D - d)


def real_bearings() -> List[str]:
    """Catalog codes of actual rolling bearings (excludes the bearingless option)."""
    return [code for code, b in BEARING_CATALOG.items() if b.get("width", 0.0) > 0.0]


def find_bearing(d_inner: float, max_outer: Optional[float] = None) -> Optional[str]:
    """Highest-capacity bearing with the given bore that fits within max_outer."""
    best = None
    for code in real_bearings():
        b = BEARING_CATALOG[code]
        if abs(b["d_inner"] - d_inner) > 1e-6:
            continue
        if max_outer is not None and b["d_outer"] > max_outer:
            continue
        if best is None or b["C_kN"] > BEARING_CATALOG[best]["C_kN"]:
            best = code
    return best


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
            "C_kN": data.get("C_kN", 0.0),
            "description": data["description"]
        })
    return items
