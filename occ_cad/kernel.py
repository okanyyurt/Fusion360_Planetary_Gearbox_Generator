# -*- coding: utf-8 -*-
"""
OpenCascade (OCP) çekirdek yardımcıları.

Fusion 360'taki sketch / extrude / sweep / pattern işlemlerinin OCP karşılıkları.
Tüm ölçüler milimetredir (Fusion API'deki santimetre dönüşümü burada yoktur).

Performans kuralları (OCCT boolean motoru için):
  * Kesici aletler, kesilen gövdenin yüzeylerinden taşacak şekilde uzatılır;
    çakışık (coplanar) yüzeyler boolean işlemini 3-5 kat yavaşlatır.
  * Birden fazla kesici tek bir işlemde (araç listesi) uygulanır.
  * Helisel / balıksırtı yüzeyler boolean yerine döndürülmüş kesitlerden loft ile kurulur;
    yüzeyler dikilerek (sewing) katıya çevrilir.
"""
from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

from OCP.BRep import BRep_Builder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import (BRepBuilderAPI_Copy, BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace,
                                BRepBuilderAPI_MakeSolid, BRepBuilderAPI_MakeWire, BRepBuilderAPI_Sewing,
                                BRepBuilderAPI_Transform)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.Bnd import Bnd_Box
from OCP.GC import GC_MakeArcOfCircle
from OCP.GeomAPI import GeomAPI_Interpolate
from OCP.GProp import GProp_GProps
from OCP.ShapeFix import ShapeFix_Face, ShapeFix_Solid
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopAbs import TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.collections import HArray1_gp_Pnt, List_TopoDS_Shape
from OCP.gp import gp_Ax1, gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

Point2 = Tuple[float, float]


class GeometryError(RuntimeError):
    """B-Rep kurulumu başarısız olduğunda fırlatılır (mesaj kullanıcıya gösterilir)."""


# ─── Temel elemanlar ─────────────────────────────────────────────────────────

def pnt(x: float, y: float, z: float = 0.0) -> gp_Pnt:
    return gp_Pnt(float(x), float(y), float(z))


def polar(r: float, ang: float, cx: float = 0.0, cy: float = 0.0, z: float = 0.0) -> gp_Pnt:
    return gp_Pnt(cx + r * math.cos(ang), cy + r * math.sin(ang), z)


def line_edge(a: gp_Pnt, b: gp_Pnt):
    mk = BRepBuilderAPI_MakeEdge(a, b)
    if not mk.IsDone():
        raise GeometryError("Doğru kenarı oluşturulamadı.")
    return mk.Edge()


def arc_edge(a: gp_Pnt, mid: gp_Pnt, b: gp_Pnt):
    """Üç noktadan yay (Fusion: sketchArcs.addByThreePoints)."""
    return BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(a, mid, b).Value()).Edge()


def circle_edge(r: float, cx: float = 0.0, cy: float = 0.0, z: float = 0.0):
    circ = gp_Circ(gp_Ax2(pnt(cx, cy, z), gp_Dir(0, 0, 1)), float(r))
    return BRepBuilderAPI_MakeEdge(circ).Edge()


def spline_edge(points: Sequence[gp_Pnt]):
    """Noktalardan geçen B-spline (Fusion: sketchFittedSplines)."""
    arr = HArray1_gp_Pnt(1, len(points))
    for i, p in enumerate(points, 1):
        arr.SetValue(i, p)
    itp = GeomAPI_Interpolate(arr, False, 1e-7)
    itp.Perform()
    if not itp.IsDone():
        raise GeometryError("Diş profili spline eğrisi oluşturulamadı.")
    return BRepBuilderAPI_MakeEdge(itp.Curve()).Edge()


def make_wire(edges: Iterable) -> "TopoDS_Wire":
    mk = BRepBuilderAPI_MakeWire()
    for e in edges:
        mk.Add(e)
        if not mk.IsDone():
            raise GeometryError(f"Profil kenarları birleştirilemedi (hata kodu {mk.Error()}).")
    return mk.Wire()


def circle_wire(r: float, cx: float = 0.0, cy: float = 0.0, z: float = 0.0):
    return make_wire([circle_edge(r, cx, cy, z)])


def polygon_wire(pts: Sequence[Point2], z: float = 0.0):
    ps = [pnt(x, y, z) for x, y in pts]
    return make_wire([line_edge(ps[i], ps[(i + 1) % len(ps)]) for i in range(len(ps))])


def planar_face(outer, holes: Sequence = ()):
    """Dış kontur + delikler -> düzlemsel yüz. Delik yönleri ShapeFix ile düzeltilir."""
    mk = BRepBuilderAPI_MakeFace(outer, True)
    if not mk.IsDone():
        raise GeometryError("Düzlemsel yüz oluşturulamadı.")
    for h in holes:
        mk.Add(TopoDS.Wire(h.Reversed()))
    face = mk.Face()
    if holes:
        fix = ShapeFix_Face(face)
        fix.FixOrientation()
        fix.Perform()
        face = TopoDS.Face(fix.Face())
    return face


# ─── Katı üretimi ────────────────────────────────────────────────────────────

def prism(face_or_wire, height: float):
    """Z yönünde extrude (Fusion: extrudeFeatures, setDistanceExtent)."""
    return BRepPrimAPI_MakePrism(face_or_wire, gp_Vec(0, 0, float(height))).Shape()


def extrude(face, z0: float, z1: float):
    """z=0 düzleminde kurulmuş yüzü [z0, z1] aralığına extrude eder."""
    return translate(prism(face, z1 - z0), 0.0, 0.0, z0)


def cylinder(r: float, z0: float, z1: float, cx: float = 0.0, cy: float = 0.0):
    ax = gp_Ax2(pnt(cx, cy, min(z0, z1)), gp_Dir(0, 0, 1))
    return BRepPrimAPI_MakeCylinder(ax, float(r), float(abs(z1 - z0))).Shape()


def cone(r0: float, r1: float, z0: float, z1: float, cx: float = 0.0, cy: float = 0.0):
    """Kesik koni: z0'da yarıçap r0, z1'de r1 (z1 > z0)."""
    ax = gp_Ax2(pnt(cx, cy, z0), gp_Dir(0, 0, 1))
    return BRepPrimAPI_MakeCone(ax, float(r0), float(r1), float(z1 - z0)).Shape()


def cylinder_along(r: float, origin: Tuple[float, float, float], direction: Tuple[float, float, float],
                   length: float):
    ax = gp_Ax2(pnt(*origin), gp_Dir(*direction))
    return BRepPrimAPI_MakeCylinder(ax, float(r), float(length)).Shape()


MAX_LOFT_STEP = math.radians(8.0)   # helisel bölgede kesitler arası en büyük dönme


def place_wire(wire, z: float, angle: float = 0.0):
    """z=0'da kurulmuş teli Z ekseni etrafında döndürüp z yüksekliğine taşır."""
    t = trsf_translate(0.0, 0.0, z).Multiplied(trsf_rotate_z(angle))
    return TopoDS.Wire(BRepBuilderAPI_Transform(wire, t, True).Shape())


def twisted_faces(wire, zs: Sequence[float], angles: Sequence[float]):
    """
    Profilin Z ekseni boyunca dönerek ilerlediği yanal yüzeyler (Fusion: sweep + twistAngle).

    Kırılma noktaları arasında dönme yoksa düz extrude, varsa döndürülmüş kesitler
    arasından loft (ThruSections) kullanılır. Loft, helisel süpürmeye göre ~10 kat küçük
    STEP dosyası ve ~8 kat hızlı üretim sağlar; sapma mikron mertebesindedir.
    `wire` z=0 düzleminde ve 0° açıda verilir.

    Döndürür: (yüz listesi, ilk kesit teli, son kesit teli)
    """
    if len(zs) < 2 or len(zs) != len(angles):
        raise GeometryError("Helis kırılma noktaları hatalı.")
    face_list = []
    for i in range(len(zs) - 1):
        z0, z1, a0, a1 = zs[i], zs[i + 1], angles[i], angles[i + 1]
        if z1 - z0 <= 1e-9:
            continue
        if abs(a1 - a0) < 1e-12:
            face_list += faces(prism(place_wire(wire, z0, a0), z1 - z0))
            continue
        n_sec = max(2, int(math.ceil(abs(a1 - a0) / MAX_LOFT_STEP)))
        loft = BRepOffsetAPI_ThruSections(False, False, 1e-6)
        loft.CheckCompatibility(False)
        for k in range(n_sec + 1):
            s = k / n_sec
            loft.AddWire(place_wire(wire, z0 + (z1 - z0) * s, a0 + (a1 - a0) * s))
        loft.Build()
        if not loft.IsDone():
            raise GeometryError("Helisel (balıksırtı) yüzey oluşturulamadı.")
        face_list += faces(loft.Shape())
    return face_list, place_wire(wire, zs[0], angles[0]), place_wire(wire, zs[-1], angles[-1])


def twisted_solid(wire, zs: Sequence[float], angles: Sequence[float]):
    """Kapalı profilden dönerek ilerleyen katı (balıksırtı dişli gövdesi)."""
    side, first, last = twisted_faces(wire, zs, angles)
    solid = sew_solid(side + [planar_face(first), planar_face(last)])
    if not is_valid(solid):
        raise GeometryError("Balıksırtı dişli katısı geçersiz.")
    return solid


def sew_solid(face_list: Sequence, tol: float = 1e-4):
    """Kapalı bir yüz kümesini dikerek katı üretir (çember dişli gövdesi için hızlı yol)."""
    sew = BRepBuilderAPI_Sewing(tol)
    for f in face_list:
        sew.Add(f)
    sew.Perform()
    sewn = sew.SewedShape()
    ex = TopExp_Explorer(sewn, TopAbs_SHELL)
    if not ex.More():
        raise GeometryError("Gövde yüzeyleri kapalı bir kabuk oluşturmadı.")
    shell = TopoDS.Shell(ex.Current())
    ex.Next()
    if ex.More():
        raise GeometryError("Gövde yüzeyleri birden fazla kabuğa ayrıldı.")
    mk = BRepBuilderAPI_MakeSolid(shell)
    fix = ShapeFix_Solid(mk.Solid())
    fix.Perform()
    return fix.Solid()


# ─── Boolean işlemler ────────────────────────────────────────────────────────

def _shape_list(shapes: Iterable) -> List_TopoDS_Shape:
    lst = List_TopoDS_Shape()
    for s in shapes:
        lst.Append(s)
    return lst


def _run_boolean(op, base, tools: Sequence, what: str):
    # non-destructive: OCC otherwise raises tolerances of the *input* shapes in place, so a prototype
    # used once as a tool (or a part shape reused later) silently becomes invalid
    op.SetArguments(_shape_list([base]))
    op.SetTools(_shape_list(tools))
    op.SetRunParallel(True)
    op.SetNonDestructive(True)
    op.Build()
    if not op.IsDone():
        raise GeometryError(f"Boolean işlemi başarısız: {what}.")
    return op.Shape()


def fuse(base, tools: Sequence, what: str = "birleştirme", unify: bool = False):
    if not tools:
        return base
    result = _run_boolean(BRepAlgoAPI_Fuse(), base, list(tools), what)
    return unify_faces(result) if unify else result


def cut(base, tools: Sequence, what: str = "kesme"):
    """
    base − tools. A cut can never add material or detach pieces we did not intend; if the multi-tool
    boolean misclassifies a tool (seen with tools crossing a face/edge junction), it is redone one
    tool at a time, which OCC handles reliably.
    """
    if not tools:
        return base
    tools = list(tools)
    result = _run_boolean(BRepAlgoAPI_Cut(), base, tools, what)
    if len(tools) > 1 and solid_count(result) > solid_count(base):
        result = base
        for tool in tools:
            result = _run_boolean(BRepAlgoAPI_Cut(), result, [tool], what)
    return result


def common(a, b):
    op = BRepAlgoAPI_Common()
    op.SetArguments(_shape_list([a]))
    op.SetTools(_shape_list([b]))
    op.SetNonDestructive(True)
    op.Build()
    return op.Shape() if op.IsDone() else None


def unify_faces(shape):
    """
    Birleştirme sonrası aynı düzlem/silindir üzerindeki parçalı yüzleri tek yüze indirger. Sonuç
    geçersizse (ör. silindir üst yüzü + çift-D kilit alt yüzü birleşince) birleştirilmemiş, geçerli
    şekil döner — geçersiz bir katı sonraki her boolean işlemi bozar.
    """
    try:
        # UnifySameDomain edits the shared sub-shapes of its input: work on a copy so the fallback
        # really is the untouched original
        up = ShapeUpgrade_UnifySameDomain(BRepBuilderAPI_Copy(shape, True, False).Shape(), True, True, False)
        up.Build()
        result = up.Shape()
    except Exception:
        return shape
    if not is_valid(result) or solid_count(result) != solid_count(shape):
        return shape
    return result


# ─── Dönüşümler ──────────────────────────────────────────────────────────────

def trsf_translate(dx: float, dy: float, dz: float) -> gp_Trsf:
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(float(dx), float(dy), float(dz)))
    return t


def trsf_rotate_z(angle: float, cx: float = 0.0, cy: float = 0.0) -> gp_Trsf:
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(pnt(cx, cy, 0.0), gp_Dir(0, 0, 1)), float(angle))
    return t


def trsf_rotate_axis(origin: Tuple[float, float, float], direction: Tuple[float, float, float],
                     angle: float) -> gp_Trsf:
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(pnt(*origin), gp_Dir(*direction)), float(angle))
    return t


def trsf_place(x: float, y: float, z: float, rot_z: float = 0.0) -> gp_Trsf:
    """Önce Z ekseni etrafında döndür, sonra (x, y, z) noktasına taşı."""
    return trsf_translate(x, y, z).Multiplied(trsf_rotate_z(rot_z))


def transform(shape, trsf: gp_Trsf):
    """Dönüşümü geometriye işler (konum/instance bırakmaz)."""
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def translate(shape, dx: float, dy: float, dz: float):
    if abs(dx) < 1e-12 and abs(dy) < 1e-12 and abs(dz) < 1e-12:
        return shape
    return transform(shape, trsf_translate(dx, dy, dz))


def rotate_z(shape, angle: float, cx: float = 0.0, cy: float = 0.0):
    if abs(angle) < 1e-12:
        return shape
    return transform(shape, trsf_rotate_z(angle, cx, cy))


def trsf_to_matrix(t: gp_Trsf) -> List[float]:
    """gp_Trsf -> three.js Matrix4.fromArray için sütun öncelikli 16 eleman."""
    m = [[t.Value(r, c) for c in range(1, 5)] for r in range(1, 4)]
    return [m[0][0], m[1][0], m[2][0], 0.0,
            m[0][1], m[1][1], m[2][1], 0.0,
            m[0][2], m[1][2], m[2][2], 0.0,
            m[0][3], m[1][3], m[2][3], 1.0]


# ─── Sorgular ────────────────────────────────────────────────────────────────

def faces(shape) -> list:
    out = []
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        out.append(TopoDS.Face(ex.Current()))
        ex.Next()
    return out


def solid_count(shape) -> int:
    n = 0
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        n += 1
        ex.Next()
    return n


def volume(shape) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return props.Mass()


def is_valid(shape) -> bool:
    return BRepCheck_Analyzer(shape).IsValid()


def bounding_box(shape) -> Tuple[float, float, float, float, float, float]:
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    return lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()


def compound(shapes: Iterable):
    comp = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(comp)
    for s in shapes:
        builder.Add(comp, s)
    return comp
