# -*- coding: utf-8 -*-
"""
resources/slicer_profiles/creality_k1.json: complete OrcaSlicer / Creality Print project settings of the Creality
K1 family, so a 3MF of the app opens with the right printer, process and filament (print3mf.write_3mf).

Run once on a Windows machine with OrcaSlicer installed (the presets ship with it):
    python tools/make_slicer_profiles.py
For every printer the Orca CLI loads machine + "0.16mm Optimal" process + a filament onto a reference model and
exports a project; its Metadata/project_settings.config is the flattened preset set. The result keeps one base
config per printer (with PLA) and, per material, only the keys that differ from PLA (the filament part).
"""
import json
import os
import subprocess
import sys
import tempfile
import zipfile

ORCA = r"C:\Program Files\OrcaSlicer"
PROFILES = os.path.join(ORCA, "resources", "profiles", "Creality")
REFERENCE = os.path.join(ORCA, "resources", "calib", "pressure_advance", "auto_pa_line_single.3mf")
PRINTERS = {   # app printer key -> (machine preset, process preset)
    "creality k1 max": ("Creality K1 Max (0.4 nozzle)", "0.16mm Optimal @Creality K1Max (0.4 nozzle)"),
    "creality k1": ("Creality K1 (0.4 nozzle)", "0.16mm Optimal @Creality K1 (0.4 nozzle)"),
    "creality k1c": ("Creality K1C 0.4 nozzle", "0.16mm Optimal @Creality K1C 0.4 nozzle"),
    "creality k1 se": ("Creality K1 SE 0.4 nozzle", "0.16mm Optimal @Creality K1 SE 0.4 nozzle"),
}
FILAMENTS = {  # app material -> filament preset
    "PLA": "Creality Generic PLA @K1-all", "PETG": "Creality Generic PETG @K1-all",
    "ABS": "Creality Generic ABS @K1-all", "PACF": "Creality Generic PA-CF @K1-all",
    "PC": "Creality Generic PC @K1-all",
}


def trim_to_one_filament(ps: dict) -> dict:
    """The reference has 8 filament slots: keep the first (the per-filament lists, the flush matrix / vector)."""
    n = len(ps.get("filament_settings_id") or [])
    if n <= 1:
        return ps
    out = {}
    for k, v in ps.items():
        if isinstance(v, list) and len(v) == n:
            v = v[:1]
        elif k == "flush_volumes_matrix" and isinstance(v, list) and len(v) == n * n:
            v = v[:1]
        elif k == "flush_volumes_vector" and isinstance(v, list) and len(v) == 2 * n:
            v = v[:2]
        elif k in ("different_settings_to_system", "inherits_group") and isinstance(v, list) and len(v) == n + 2:
            v = [v[0], v[1], v[-1]]
        out[k] = v
    return out


def export(machine: str, process: str, filament: str, work: str) -> dict:
    out = os.path.join(work, "out.3mf")
    if os.path.exists(out):
        os.remove(out)
    args = [os.path.join(ORCA, "orca-slicer.exe"),
            "--load-settings", f"{os.path.join(PROFILES, 'machine', machine + '.json')};"
                               f"{os.path.join(PROFILES, 'process', process + '.json')}",
            "--load-filaments", os.path.join(PROFILES, "filament", filament + ".json"),
            "--export-3mf", out, REFERENCE]
    subprocess.run(args, timeout=300, check=False)
    with zipfile.ZipFile(out) as z:
        return trim_to_one_filament(json.loads(z.read("Metadata/project_settings.config")))


def main(target: str):
    work = tempfile.mkdtemp(prefix="orca_profiles_")
    data = {"source": "OrcaSlicer presets (Creality)", "printers": {}, "filaments": {}}
    first = None
    for key, (machine, process) in PRINTERS.items():
        base = export(machine, process, FILAMENTS["PLA"], work)
        data["printers"][key] = base
        first = first or (key, machine, process, base)
        print("printer", key, len(base), "keys")
    key, machine, process, base = first
    for mat, fil in FILAMENTS.items():
        if mat == "PLA":
            data["filaments"][mat] = {}
            continue
        cfg = export(machine, process, fil, work)
        data["filaments"][mat] = {k: v for k, v in cfg.items() if base.get(k) != v}
        print("filament", mat, len(data["filaments"][mat]), "keys")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print("written", target, os.path.getsize(target), "bytes")


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "resources", "slicer_profiles", "creality_k1.json"))
