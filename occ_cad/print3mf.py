# -*- coding: utf-8 -*-
"""
Baskıya hazır 3MF: basılacak tüm parçalar baskı yönünde, tablaya yan yana yerleştirilmiş (adet kadar kopya) ve
her parçanın dilimleme ayarı kendi üzerinde: duvar sayısı, dolgu oranı / deseni, katman yüksekliği.

Dosya Bambu Studio / OrcaSlicer / Creality Print proje yapısıyla yazılır (üretim uzantısı: ağlar
3D/Objects/object_1.model içinde, her yerleşik kopya tek bileşenli bir nesne; parça ayarları
Metadata/model_settings.config içinde Orca anahtarlarıyla). Creality K1 / K1 Max'in Creality Print'i ve
OrcaSlicer ayarları doğrudan alır; PrusaSlicer 2.6+ bu yapıyı geometri olarak okur. Ağlar kaynaklanır (komşu
yüzlerin ortak düğümleri tek düğüm), dilimleyici açık kenar onarımı istemez.

Parça türüne göre ayar (FDM):
  güneş / planet / dişli taşıyan parça   tam dolu (%100), 4-5 duvar: dişler ve göbek dolu
  çember gövdesi / tambur                %40 gyroid, 4-5 duvar: dişler duvarlarla dolar, gövde hafif kalır
  taşıyıcı plakaları, kapak, flanş       %60 gyroid, 4 duvar
  kol                                    %80 gyroid, 5-6 duvar (eğilme)
  ara halka, segman, kalibrasyon dişlisi %100
Katman yüksekliği: modül <= 1 için 0.12 mm, üstü 0.16 mm (dişin yanağı ince katmanla basılsın).
"""
from __future__ import annotations

import json
import math
import os
import uuid
import zipfile
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import quoteattr

from . import kernel as K
from .export import _move_into_place, _print_ready, _triangulate, ascii_name, ascii_temp_dir

GAP = 6.0             # mm between parts on the plate
MARGIN_XY = 4.0       # mm from the plate edge
ORCA_KEYS = {"perimeters": "wall_loops", "fill_density": "sparse_infill_density",
             "fill_pattern": "sparse_infill_pattern", "layer_height": "layer_height"}
NS = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
      'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
      'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p"')


def part_settings(part, module: float) -> Dict[str, str]:
    """Slicer settings of one printed part (PrusaSlicer key names)."""
    key = part.key
    walls = 5 if module >= 2.0 else 4
    if key.startswith(("ring_housing", "drum")) and not key.startswith(("drum_bearing", "drum_nut")):
        fill, pattern = 40, "gyroid"
    elif part.gear or key.startswith(("sun", "planet")):
        fill, pattern = 100, "rectilinear"
    elif key.startswith(("spacer", "circlip", "cal_gear")):
        fill, pattern = 100, "rectilinear"
    elif key.startswith(("output_arm", "arm")):
        fill, pattern, walls = 80, "gyroid", walls + 1
    else:
        fill, pattern = 60, "gyroid"
    return {"perimeters": str(walls), "fill_density": f"{fill}%", "fill_pattern": pattern,
            "layer_height": "0.12" if module <= 1.0 else "0.16"}


def orca_settings(part, module: float) -> Dict[str, str]:
    """The same settings with the Orca / Bambu / Creality Print keys."""
    return {ORCA_KEYS[k]: v for k, v in part_settings(part, module).items()}


def _uuid(n: int, kind: int) -> str:
    return f"{n:08x}-{kind:04x}-4000-8000-{n * 7919 + kind:012x}"


def _weld(pos, idx) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]:
    """Merge the duplicated face-boundary nodes (same coordinates) and drop degenerate triangles."""
    verts: List[Tuple[float, float, float]] = []
    lookup: Dict[Tuple[int, int, int], int] = {}
    remap = []
    for i in range(0, len(pos), 3):
        q = (round(pos[i] * 1e4), round(pos[i + 1] * 1e4), round(pos[i + 2] * 1e4))
        j = lookup.get(q)
        if j is None:
            j = lookup[q] = len(verts)
            verts.append((pos[i], pos[i + 1], pos[i + 2]))
        remap.append(j)
    tris = []
    for i in range(0, len(idx), 3):
        a, b, c = remap[idx[i]], remap[idx[i + 1]], remap[idx[i + 2]]
        if a != b and b != c and a != c:
            tris.append((a, b, c))
    return verts, tris


def _pack_plates(sizes: List[Tuple[float, float]], bed: Tuple[float, float]) -> List[Tuple[int, float, float]]:
    """
    Shelf packing of footprints (w, d) onto as many plates as needed: (plate index, x, y) of each lower-left corner
    inside its plate. A part larger than the bed gets a plate of its own (the slicer reports it).
    """
    out, plate, x, y, row = [], 0, 0.0, 0.0, 0.0
    used = False
    for w, d in sizes:
        if used and x > 0 and x + w > bed[0]:
            x, y, row = 0.0, y + row + GAP, 0.0
        if used and y + d > bed[1]:
            plate, x, y, row, used = plate + 1, 0.0, 0.0, 0.0, False
        out.append((plate, x, y))
        used = True
        x += w + GAP
        row = max(row, d)
    return out


def plate_origin(index: int, n_plates: int, bed: Tuple[float, float]) -> Tuple[float, float]:
    """Origin of plate `index` in the Bambu / Orca plate grid (columns = ceil(sqrt(n)), stride 1.2 x bed)."""
    cols = max(1, math.ceil(math.sqrt(n_plates)))
    return (index % cols) * bed[0] * 1.2, -(index // cols) * bed[1] * 1.2


SLICER_PROFILES = ("creality k1 max", "creality k1", "creality k1c", "creality k1 se")
FILAMENT_TYPE = {"PLA": "PLA", "PETG": "PETG", "ABS": "ABS", "PACF": "PA-CF", "PC": "PC"}
PROFILE_MATERIAL = {"PLA": "PLA", "PETG": "PETG", "ABS": "ABS", "PACF": "PACF", "PA12": "PACF", "PC": "PC"}


def project_settings(profile: str, material: str) -> Optional[Dict]:
    """Complete Orca / Creality Print project settings of a Creality K1 printer with the material's filament."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "slicer_profiles",
                        "creality_k1.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError:
        return None
    base = data["printers"].get((profile or "").lower())
    if base is None:
        return None
    mat = PROFILE_MATERIAL.get(material.upper(), "PLA")
    out = dict(base, **data["filaments"].get(mat, {}))
    out["filament_type"] = [FILAMENT_TYPE[mat]]         # not part of the exported preset difference
    return out


def write_3mf(result, path: str, module: float = 1.0, bed: Tuple[float, float] = (256.0, 256.0),
              linear: float = 0.02, angular: float = 0.2, profile: str = "", material: str = "PLA") -> str:
    """
    All printable parts (each as many times as needed) with their slicer settings, ready to slice.
    `profile` a Creality K1 printer (SLICER_PROFILES): Orca / Creality Print project with the printer, process and
    filament presets; otherwise a plain 3MF (any slicer reads the geometry, PrusaSlicer also the part settings).
    """
    objects, instances = [], []
    for part in result.parts:
        if not part.printable:
            continue
        shape = _print_ready(part.shape, part.print_trsf)       # centred in XY, base on z = 0
        x0, y0, _z0, x1, y1, _z1 = K.bounding_box(shape)
        if not ((x1 - x0 <= bed[0] and y1 - y0 <= bed[1]) or (x1 - x0 <= bed[1] and y1 - y0 <= bed[0])):
            # too long for the bed (e.g. an output arm): diagonally, on a plate of its own
            shape = _print_ready(K.rotate_z(shape, math.pi / 4.0))
        elif x1 - x0 > bed[0] or y1 - y0 > bed[1]:
            shape = _print_ready(K.rotate_z(shape, math.pi / 2.0))
        pos, idx = _triangulate(shape, linear, angular)
        verts, tris = _weld(pos, idx)
        x0, y0, _z0, x1, y1, _z1 = K.bounding_box(shape)
        objects.append({"id": len(objects) + 1, "part": part, "verts": verts, "tris": tris,
                        "w": x1 - x0, "d": y1 - y0, "x0": x0, "y0": y0})
        instances += [len(objects) - 1] * part.quantity
    order = sorted(range(len(instances)), key=lambda k: -objects[instances[k]]["w"] * objects[instances[k]]["d"])
    slots = _pack_plates([(objects[instances[k]]["w"], objects[instances[k]]["d"]) for k in order], bed)
    n_plates = max((sl[0] for sl in slots), default=0) + 1
    placed = []
    for (pl, cx, cy), k in zip(slots, order):
        ox, oy = plate_origin(pl, n_plates, bed)
        o = objects[instances[k]]
        placed.append(((ox + cx - o["x0"] + MARGIN_XY, oy + cy - o["y0"] + MARGIN_XY), instances[k], pl))

    settings = project_settings(profile, material) if profile else None
    if settings is None:
        return _write_plain(result, path, module, objects, placed)
    mesh = ['<?xml version="1.0" encoding="UTF-8"?>', f'<model unit="millimeter" xml:lang="en-US" {NS}>',
            ' <metadata name="BambuStudio:3mfVersion">1</metadata>', ' <resources>']
    for o in objects:
        mesh.append(f'  <object id="{o["id"]}" p:UUID="{_uuid(o["id"], 1)}" type="model">')
        mesh += ['   <mesh>', '    <vertices>']
        mesh += [f'     <vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>' for x, y, z in o["verts"]]
        mesh += ['    </vertices>', '    <triangles>']
        mesh += [f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in o["tris"]]
        mesh += ['    </triangles>', '   </mesh>', '  </object>']
    mesh += [' </resources>', '</model>']

    base = len(objects)
    model = ['<?xml version="1.0" encoding="UTF-8"?>', f'<model unit="millimeter" xml:lang="en-US" {NS}>',
             ' <metadata name="Application">BambuStudio-02.00.00.00</metadata>',
             ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
             f' <metadata name="Title">{ascii_name(result.product_name)}</metadata>',
             ' <resources>']
    config = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>']
    build = [f' <build p:UUID="{_uuid(0, 9)}">']
    plates: Dict[int, List[int]] = {}
    for n, ((tx, ty), oi, pl) in enumerate(placed, start=1):
        o = objects[oi]
        wid = base + n
        part = o["part"]
        name = quoteattr(part.label)
        model += [f'  <object id="{wid}" p:UUID="{_uuid(wid, 2)}" type="model">', '   <components>',
                  f'    <component p:path="/3D/Objects/object_1.model" objectid="{o["id"]}" '
                  f'p:UUID="{_uuid(wid, 3)}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>',
                  '   </components>', '  </object>']
        build.append(f'  <item objectid="{wid}" p:UUID="{_uuid(wid, 4)}" '
                     f'transform="1 0 0 0 1 0 0 0 1 {tx:.4f} {ty:.4f} 0" printable="1"/>')
        config += [f'  <object id="{wid}">', f'    <metadata key="name" value={name}/>',
                   '    <metadata key="extruder" value="1"/>']
        config += [f'    <metadata key="{k}" value="{v}"/>' for k, v in orca_settings(part, module).items()]
        config += [f'    <part id="{o["id"]}" subtype="normal_part">', f'      <metadata key="name" value={name}/>',
                   '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
                   '      <metadata key="extruder" value="1"/>', '    </part>', '  </object>']
        plates.setdefault(pl, []).append(wid)
    model += [' </resources>'] + build + [' </build>', '</model>']
    for pl in sorted(plates):
        config += ['  <plate>', f'    <metadata key="plater_id" value="{pl + 1}"/>',
                   '    <metadata key="plater_name" value=""/>', '    <metadata key="locked" value="false"/>']
        for wid in plates[pl]:
            config += ['    <model_instance>', f'      <metadata key="object_id" value="{wid}"/>',
                       '      <metadata key="instance_id" value="0"/>',
                       f'      <metadata key="identify_id" value="{100 + wid}"/>', '    </model_instance>']
        config.append('  </plate>')
    config.append('</config>')

    rel = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
    head = '<?xml version="1.0" encoding="UTF-8"?>\n'
    rels_ns = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'
    content_types = (head + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
                     '<Default Extension="png" ContentType="image/png"/>'
                     '<Default Extension="gcode" ContentType="text/x.gcode"/></Types>')
    rels = (head + f'<Relationships {rels_ns}><Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="{rel}"/>'
            '</Relationships>')
    model_rels = (head + f'<Relationships {rels_ns}><Relationship Target="/3D/Objects/object_1.model" Id="rel-1" '
                  f'Type="{rel}"/></Relationships>')
    slice_info = (head + '<config>\n  <header>\n    <header_item key="X-BBL-Client-Type" value="slicer"/>\n'
                  '    <header_item key="X-BBL-Client-Version" value="02.00.00.00"/>\n  </header>\n</config>')
    tmp = os.path.join(ascii_temp_dir(), f"pgb_{uuid.uuid4().hex}.3mf")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", "\n".join(model))
        z.writestr("3D/_rels/3dmodel.model.rels", model_rels)
        z.writestr("3D/Objects/object_1.model", "\n".join(mesh))
        z.writestr("Metadata/model_settings.config", "\n".join(config))
        z.writestr("Metadata/slice_info.config", slice_info)
        z.writestr("Metadata/project_settings.config", json.dumps(settings, ensure_ascii=False, indent=1))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    return _move_into_place(tmp, path)


def _write_plain(result, path: str, module: float, objects: List[Dict], placed: List) -> str:
    """Plain 3MF (core spec): geometry for every slicer; part settings in PrusaSlicer's Slic3r_PE_model.config."""
    model = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
             'xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">',
             ' <metadata name="slic3rpe:Version3mf">1</metadata>',
             ' <metadata name="Application">Planetary Gearbox Generator</metadata>',
             f' <metadata name="Title">{ascii_name(result.product_name)}</metadata>', ' <resources>']
    config = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>']
    for o in objects:
        part = o["part"]
        name = quoteattr(part.label)
        model += [f'  <object id="{o["id"]}" type="model" name={name}>', '   <mesh>', '    <vertices>']
        model += [f'     <vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>' for x, y, z in o["verts"]]
        model += ['    </vertices>', '    <triangles>']
        model += [f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in o["tris"]]
        model += ['    </triangles>', '   </mesh>', '  </object>']
        config += [f' <object id="{o["id"]}" instances_count="{part.quantity}">',
                   f'  <metadata type="object" key="name" value={name}/>']
        config += [f'  <metadata type="object" key="{k}" value="{v}"/>' for k, v in part_settings(part, module).items()]
        config += [f'  <volume firstid="0" lastid="{len(o["tris"]) - 1}">',
                   f'   <metadata type="volume" key="name" value={name}/>',
                   '   <metadata type="volume" key="volume_type" value="ModelPart"/>', '  </volume>', ' </object>']
    model.append(' </resources>')
    model.append(' <build>')
    model += [f'  <item objectid="{objects[oi]["id"]}" transform="1 0 0 0 1 0 0 0 1 {tx:.4f} {ty:.4f} 0" printable="1"/>'
              for (tx, ty), oi, _pl in placed]
    model += [' </build>', '</model>']
    config.append('</config>')
    head = '<?xml version="1.0" encoding="UTF-8"?>' + chr(10)
    content_types = (head + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
                     '<Default Extension="config" ContentType="text/xml"/></Types>')
    rels = (head + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    tmp = os.path.join(ascii_temp_dir(), f"pgb_{uuid.uuid4().hex}.3mf")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", chr(10).join(model))
        z.writestr("Metadata/Slic3r_PE_model.config", chr(10).join(config))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    return _move_into_place(tmp, path)
