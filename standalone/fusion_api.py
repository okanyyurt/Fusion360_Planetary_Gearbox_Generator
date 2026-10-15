# -*- coding: utf-8 -*-
"""
Fusion 360 paletinin API'si: bağımsız uygulamayla aynı metotlar (design, get_catalogs, generate,
open_path, AI asistanı ...). Tek fark üretimdir: geometri OCP motorunda üretilir, STEP montajı aktif
Fusion tasarımına aktarılır; STL'ler, mühendislik raporu ve parça listesi dışa aktarma klasörüne yazılır.
"""
from __future__ import annotations

import datetime as _dt
import logging
import os
import traceback
from typing import Callable, Dict, Optional

from .api import COMMON_METHODS, Api, _save_settings
from .fusion_engine import find_engine_python, run_engine

log = logging.getLogger(__name__)

# Fusion paletinden çağrılabilen metotlar (bağımsız uygulamayla ortak olanlar + Fusion'a özgüler)
FUSION_METHODS = set(COMMON_METHODS) | {"rotate", "set_group_visible"}


class FusionApi(Api):
    def __init__(self, push: Callable[[Dict], None], pump: Optional[Callable[[], None]] = None,
                 importer: Optional[Callable[[str, str, Dict], Optional[Dict]]] = None,
                 rotator: Optional[Callable[[float], None]] = None,
                 visibility: Optional[Callable[[str, bool], None]] = None,
                 addin_dir: str = ""):
        super().__init__()
        self._push_cb = push
        self._pump = pump
        self._importer = importer
        self._rotator = rotator
        self._visibility = visibility
        self._addin_dir = addin_dir

    def _push(self, data: Dict) -> None:
        self._progress.update({k: v for k, v in data.items() if k in ("message", "percent")})
        try:
            self._push_cb(data)
        except Exception:
            pass

    def get_app_info(self) -> Dict:
        info = super().get_app_info()
        info["host"] = "fusion"
        if self._addin_dir:
            info["app_dir"] = self._addin_dir
        return info

    def generate(self, payload: Dict) -> Dict:
        if not isinstance(payload, dict) or not payload.get("stages"):
            return self._error("Dişli kombinasyonu seçilmedi.")
        tr = not str(payload.get("lang", "tr")).startswith("en")
        self._push({"event": "progress", "percent": 2,
                    "message": "CAD motoru aranıyor..." if tr else "Looking for the CAD engine..."})
        cmd = find_engine_python(self._settings)
        if not cmd:
            return self._error(
                "OpenCascade (OCP) kurulu bir Python bulunamadı. Eklenti klasöründeki Baslat_Standalone.bat "
                "dosyasını bir kez çalıştırıp gerekli paketleri kurun, sonra tekrar deneyin." if tr else
                "No Python with OpenCascade (OCP) found. Run Baslat_Standalone.bat in the add-in folder once to "
                "install the packages, then try again.")
        _save_settings(self._settings)
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        ratio = ("%g" % round(float(payload.get("total_ratio", 0)), 2)).replace(".", "_")
        folder = os.path.join(self._export_dir(), f"Planetary_Gearbox_{ratio}x_{stamp}")
        try:
            result = run_engine(cmd, payload, folder,
                                lambda pct, msg: self._push({"event": "progress", "percent": min(pct, 95),
                                                             "message": msg}),
                                self._pump)
            kin_status = None
            if self._importer:
                self._push({"event": "progress", "percent": 97,
                            "message": "STEP montajı aktarılıyor, eklemler ve hareket bağlantıları kuruluyor..." if tr
                            else "Importing the STEP assembly, adding joints and motion links..."})
                kin_status = self._importer(result["step"], result.get("product", "Planetary_Gearbox"), result)
            kin = result.get("kinematics") or {}
            out_factor = kin.get("bodies", {}).get(kin.get("output", ""), {}).get("factor", 0.0)
            if kin_status is not None:
                kin_status = dict(kin_status, output_factor=out_factor)
            self._push({"event": "done"})
            self._payload = payload
            return {"success": True, "product": result.get("product"), "elapsed": result.get("elapsed"),
                    "summary": result.get("summary"), "warnings": result.get("warnings", []),
                    "engineering": result.get("engineering"), "parts": result.get("parts", []),
                    "folder": result.get("folder", folder), "step": result.get("step"),
                    "report": result.get("report"), "stl_count": result.get("stl_count"),
                    "kinematics": kin_status}
        except Exception as e:
            log.error("Fusion üretim hatası: %s", traceback.format_exc())
            self._push({"event": "done"})
            return self._error(str(e))

    def rotate(self, input_deg: float) -> Dict:
        """Giriş milini verilen açıya döndürür; Fusion eklemleri tüm dişlileri birlikte hareket ettirir."""
        if not self._rotator:
            return self._error("Önce modeli oluşturun.")
        try:
            self._rotator(float(input_deg))
            return {"success": True}
        except Exception as e:
            return self._error(str(e))

    def set_group_visible(self, group: str, on: bool) -> Dict:
        """Parça listesindeki grup kutusu: Fusion'daki bileşenleri gösterir/gizler."""
        if not self._visibility:
            return self._error("Önce modeli oluşturun.")
        try:
            self._visibility(str(group), bool(on))
            return {"success": True}
        except Exception as e:
            return self._error(str(e))

    def get_mesh(self, quality: str = "normal") -> Dict:
        return self._error("Fusion 360 kendi görünümünü kullanır.")

    def export_all(self) -> Dict:
        return self._error("Fusion 360'ta çıktılar üretimle birlikte klasöre yazılır.")
