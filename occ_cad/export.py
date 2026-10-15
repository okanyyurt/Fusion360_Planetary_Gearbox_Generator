# -*- coding: utf-8 -*-
"""
Dışa aktarma: STEP montajı (XCAF: ad, renk, alt montaj, instance), parça başına STL ve
3B görüntüleyici için üçgen ağ (mesh) verisi.

Türkçe karakterli yollar: OpenCASCADE'in dosya yazıcıları ASCII dışı yollarda güvenilir
değildir. Dosyalar önce ASCII bir geçici klasöre yazılır, sonra Python ile hedefe atomik
olarak taşınır (Mesh2Step projesindeki yöntemle aynı).
"""
from __future__ import annotations

import base64
import os
import re
import shutil
import tempfile
import unicodedata
import uuid
from array import array
from typing import Dict, List, Tuple

from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.StlAPI import StlAPI_Writer
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool

from . import kernel as K

_TR = str.maketrans({"ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ı": "i", "İ": "I", "ö": "o", "Ö": "O",
                     "ş": "s", "Ş": "S", "ü": "u", "Ü": "U", "â": "a", "Â": "A", "î": "i", "û": "u"})


def ascii_name(name: str, fallback: str = "Part") -> str:
    """STEP ürün adı / dosya adı için ASCII karşılık (tüm CAD programlarında doğru görünür)."""
    s = (name or fallback).translate(_TR)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9_.()-]+", "_", s).strip("_")
    return s or fallback


def ascii_temp_dir() -> str:
    """ASCII karakterli yazılabilir geçici klasör (8.3 kısa yol, PUBLIC veya C:\\Temp)."""
    base = tempfile.gettempdir()
    try:
        base.encode("ascii")
        return base
    except UnicodeEncodeError:
        pass
    if os.name == "nt":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.kernel32.GetShortPathNameW(base, buf, 1024) > 0:
                short = buf.value
                short.encode("ascii")
                return short
        except Exception:
            pass
        for cand in (os.environ.get("PUBLIC", ""), "C:\\Temp"):
            try:
                if cand:
                    cand.encode("ascii")
                    os.makedirs(cand, exist_ok=True)
                    return cand
            except Exception:
                continue
    return base


def _move_into_place(tmp: str, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    part = path + ".part"
    shutil.copyfile(tmp, part)
    os.replace(part, path)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return path


def _ext(s: str) -> TCollection_ExtendedString:
    try:
        return TCollection_ExtendedString(s, True)
    except TypeError:
        return TCollection_ExtendedString(s)


def _rgb(hex_color: str) -> Tuple[float, float, float]:
    h = (hex_color or "#a0a0a0").lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore


def _quiet():
    try:
        from OCP.Message import Message, Message_Gravity
        for prn in Message.DefaultMessenger_s().Printers():
            try:
                prn.SetTraceLevel(Message_Gravity.Message_Fail)
            except Exception:
                pass
    except Exception:
        pass


# ─── STEP ────────────────────────────────────────────────────────────────────

def write_step(result, path: str) -> str:
    """
    Montajı tek STEP dosyasına yazar. Yapı Fusion eklentisindeki bileşen ağacıyla aynıdır:
    Planetary_Gearbox_25x > Gövde / Kademe N / Bağlantı Elemanları > parçalar.
    Tekrarlanan parçalar (planet, segman, cıvata) aynı prototipin instance'larıdır.
    """
    _quiet()
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(_ext("MDTV-XCAF"))
    app.NewDocument(_ext("MDTV-XCAF"), doc)
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    colors = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    root = shapes.NewShape()
    TDataStd_Name.Set_s(root, _ext(ascii_name(result.product_name)))
    groups: Dict[str, object] = {}
    for part in result.parts:
        if part.group not in groups:
            g = shapes.NewShape()
            TDataStd_Name.Set_s(g, _ext(ascii_name(_group_cad_name(part.group))))
            groups[part.group] = g
        proto = shapes.AddShape(part.shape, False)
        TDataStd_Name.Set_s(proto, _ext(ascii_name(part.name)))
        r, gr, b = _rgb(part.color)
        colors.SetColor(proto, Quantity_Color(r, gr, b, Quantity_TOC_RGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        placements = part.placements or [None]
        for i, trsf in enumerate(placements):
            loc = TopLoc_Location(trsf) if trsf is not None else TopLoc_Location()
            comp = shapes.AddComponent(groups[part.group], proto, loc)
            if len(placements) > 1:
                TDataStd_Name.Set_s(comp, _ext(ascii_name(f"{part.name}_{i + 1}")))
    for gkey, glabel in groups.items():
        shapes.AddComponent(root, glabel, TopLoc_Location())
    shapes.UpdateAssemblies()

    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    try:
        Interface_Static.SetCVal_s("write.step.product.name", ascii_name(result.product_name))
    except Exception:
        pass
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    if not writer.Transfer(doc, STEPControl_AsIs):
        raise K.GeometryError("STEP aktarımı başarısız (Transfer).")
    tmp = os.path.join(ascii_temp_dir(), f"pgb_{uuid.uuid4().hex}.step")
    status = writer.Write(tmp)
    if status != IFSelect_RetDone or not os.path.exists(tmp):
        raise K.GeometryError(f"STEP dosyası yazılamadı (durum: {status}).")
    return _move_into_place(tmp, path)


def _group_cad_name(group: str) -> str:
    if group.startswith("stage"):
        return f"Stage_{group[5:]}"
    return {"housing": "Housing", "fasteners": "Assembly_Bolts"}.get(group, group)


# ─── STL ─────────────────────────────────────────────────────────────────────

def _mesh(shape, linear: float, angular: float):
    BRepMesh_IncrementalMesh(shape, linear, False, angular, True)


def _print_ready(shape, trsf=None):
    """Baskı için: (gerekirse baskı yönüne çevrilir) XY merkezde, tabanı z=0 düzleminde."""
    if trsf is not None:
        shape = K.transform(shape, trsf)
    x0, y0, z0, x1, y1, z1 = K.bounding_box(shape)
    return K.translate(shape, -(x0 + x1) / 2.0, -(y0 + y1) / 2.0, -z0)


def write_stls(result, folder: str, linear: float = 0.02, angular: float = 0.2,
               printable_only: bool = True) -> List[str]:
    """
    Basılacak her benzersiz parça için bir STL (adet dosya adında: ..._x3.stl). Parçalar baskı
    yönünde ve tablaya oturmuş konumdadır. Satın alınan parçalar (rulman, pim, cıvata) atlanır.
    Dosyalar ASCII geçici klasörden taşınır.
    """
    os.makedirs(folder, exist_ok=True)
    written = []
    for idx, part in enumerate(result.parts, 1):
        if printable_only and not part.printable:
            continue
        shape = _print_ready(part.shape, part.print_trsf)
        _mesh(shape, linear, angular)
        qty = f"_x{part.quantity}" if part.quantity > 1 else ""
        fname = f"{idx:02d}_{ascii_name(part.name)}{qty}.stl"
        tmp = os.path.join(ascii_temp_dir(), f"pgb_{uuid.uuid4().hex}.stl")
        writer = StlAPI_Writer()
        writer.ASCIIMode = False                         # ikili STL (ASCII'nin ~1/5'i)
        if not writer.Write(shape, tmp) or not os.path.exists(tmp):
            raise K.GeometryError(f"STL yazılamadı: {fname}")
        written.append(_move_into_place(tmp, os.path.join(folder, fname)))
    return written


# ─── Görüntüleyici mesh ──────────────────────────────────────────────────────

def _triangulate(shape, linear: float, angular: float):
    """Yüz bazında üçgenler: (float32 konumlar, uint32 indeksler, üçgen sayısı)."""
    _mesh(shape, linear, angular)
    pos = array("f")
    idx = array("I")
    base = 0
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        face = TopoDS.Face(ex.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            trsf = loc.Transformation()
            identity = loc.IsIdentity()
            n_nodes = tri.NbNodes()
            for i in range(1, n_nodes + 1):
                p = tri.Node(i)
                if not identity:
                    p = p.Transformed(trsf)
                pos.extend((p.X(), p.Y(), p.Z()))
            reverse = face.Orientation() == TopAbs_REVERSED
            for i in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(i).Get()
                if reverse:
                    b, c = c, b
                idx.extend((base + a - 1, base + b - 1, base + c - 1))
            base += n_nodes
        ex.Next()
    return pos, idx


def _motion(result, part, i: int) -> Dict:
    """Görüntüleyici için: yörünge oranı a, öz dönüş oranı b ve öz dönüş merkezi."""
    kin = getattr(result, "kinematics", None) or {}
    body = kin.get("bodies", {}).get(part.bodies[i] if part.bodies else "ground", {"type": "ground"})
    if body.get("type") == "axis":
        return {"a": body["factor"], "b": 0.0, "cx": 0.0, "cy": 0.0, "body": part.bodies[i]}
    if body.get("type") == "planet":
        return {"a": body["orbit"], "b": body["spin"], "cx": body["center"][0], "cy": body["center"][1],
                "body": part.bodies[i]}
    return {"a": 0.0, "b": 0.0, "cx": 0.0, "cy": 0.0, "body": "ground"}


def mesh_payload(result, quality: str = "normal") -> Dict:
    """
    three.js için veri: prototip başına base64 Float32 konum + Uint32 indeks,
    her instance için 4x4 matris ve patlatma (explode) yönü.
    """
    x0, y0, z0, x1, y1, z1 = K.bounding_box(K.compound([p.shape for p in result.parts]))
    diag = max(1.0, ((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2) ** 0.5)
    linear = {"fast": 0.0012, "normal": 0.0006, "fine": 0.0003}.get(quality, 0.0006) * diag
    angular = {"fast": 0.4, "normal": 0.25, "fine": 0.15}.get(quality, 0.25)
    protos, instances = {}, []
    tri_total = 0
    for part in result.parts:
        pos, idx = _triangulate(part.shape, linear, angular)
        tri_total += len(idx) // 3
        protos[part.key] = {
            "positions": base64.b64encode(pos.tobytes()).decode("ascii"),
            "indices": base64.b64encode(idx.tobytes()).decode("ascii"),
        }
        placements = part.placements or [None]
        for i, trsf in enumerate(placements):
            instances.append({
                "proto": part.key,
                "name": part.label if len(placements) == 1 else f"{part.label} #{i + 1}",
                "group": part.group,
                "group_label": part.group_label,
                "color": part.color,
                "matrix": K.trsf_to_matrix(trsf) if trsf is not None else None,
                "printable": part.printable,
                "motion": _motion(result, part, i),
                "explode": list(part.explode[i] if i < len(part.explode) else (0.0, 0.0, 0.0)),
            })
    return {
        "protos": protos,
        "instances": instances,
        "bbox": [x0, y0, z0, x1, y1, z1],
        "triangles": tri_total,
        "output_factor": (getattr(result, "kinematics", None) or {}).get("bodies", {}).get(
            (getattr(result, "kinematics", None) or {}).get("output", ""), {}).get("factor", 0.0),
    }
