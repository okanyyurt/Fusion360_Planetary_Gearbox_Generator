# -*- coding: utf-8 -*-
"""
Arayüz köprüsü: pywebview `js_api` nesnesi ve HTTP geliştirme sunucusu aynı sınıfı kullanır.

Fusion eklentisinde `adsk.fusionSendData('generateGearbox', ...)` ile yapılan çağrının
karşılığı `generate(payload)` metodudur; ilerleme mesajları aynı JSON biçimiyle
(`{event: 'progress', message, percent}`) arayüze gönderilir.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import subprocess
import sys
import threading
import time
import traceback
from typing import Dict, List, Optional

from . import paths

log = logging.getLogger(__name__)

VERSION = "2.8.0"

# Arayüzden çağrılabilen metotlar: her iki host (bağımsız uygulama + Fusion paleti) için ortak olanlar
COMMON_METHODS = frozenset({
    "get_app_info", "get_catalogs", "design", "generate", "get_progress", "cancel", "open_path",
    "solve_requirements", "ai_settings_get", "ai_settings_set", "ai_list_models", "ai_test",
    "ai_send", "ai_poll", "ai_reset",
})
# Yalnızca bağımsız uygulamada (3D görüntüleyici ve dışa aktarma düğmeleri)
STANDALONE_METHODS = COMMON_METHODS | {"get_mesh", "export_all", "export_step", "choose_export_dir",
                                       "generate_calibration"}
OPENABLE = {".html", ".htm", ".txt", ".step", ".stp", ".stl", ".pdf"}


def _load_settings() -> Dict:
    try:
        with open(paths.settings_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_settings(data: Dict) -> None:
    path = paths.settings_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _dialog_type(name: str):
    import webview
    fd = getattr(webview, "FileDialog", None)
    if fd is not None and hasattr(fd, name):
        return getattr(fd, name)
    return getattr(webview, f"{name}_DIALOG")


class Api:
    """Arayüzden çağrılan metotlar (alt çizgiyle başlayanlar JS'e açılmaz)."""

    def __init__(self):
        self._window = None
        self._result = None
        self._payload: Optional[Dict] = None
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._progress = {"message": "", "percent": 0, "running": False}
        self._settings = _load_settings()
        self._assistant = None
        self._ai_model_cache = None          # (zaman, sıralı model listesi)
        self._ai_transport = None            # testler: sahte Gemini sunucusu

    # ── Altyapı ──────────────────────────────────────────────────────────────
    def _set_window(self, window) -> None:
        self._window = window

    def _push(self, data: Dict) -> None:
        self._progress.update({k: v for k, v in data.items() if k in ("message", "percent")})
        if self._window is None:
            return
        code = f"window.hostMessageReceived && window.hostMessageReceived({json.dumps(json.dumps(data, ensure_ascii=False))});"
        try:
            self._window.evaluate_js(code)
        except Exception:
            pass

    @staticmethod
    def _error(message: str, **extra) -> Dict:
        log.warning(message)
        return {"success": False, "error": message, **extra}

    def _export_dir(self) -> str:
        d = self._settings.get("export_dir") or paths.default_export_dir()
        return d

    # ── Bilgi ────────────────────────────────────────────────────────────────
    def get_app_info(self) -> Dict:
        try:
            import OCP
            occ = getattr(OCP, "__version__", "?")
        except Exception:
            occ = "?"
        return {
            "success": True,
            "version": VERSION,
            "host": "pywebview" if self._window is not None else "http",
            "python": sys.version.split()[0],
            "occ": occ,
            "export_dir": self._export_dir(),
            "has_result": self._result is not None,
            "app_dir": paths.project_root(),
        }

    def get_progress(self) -> Dict:
        return dict(self._progress)

    def cancel(self) -> Dict:
        self._cancel.set()
        return {"success": True}

    # ── Tasarım (otomatik boyutlandırma) ─────────────────────────────────────
    def get_catalogs(self) -> Dict:
        from core.bearing_catalog import BEARING_CATALOG
        from core.materials import MATERIALS
        from core.motor_catalog import MOTOR_CATALOG
        return {
            "success": True,
            "bearings": [{"code": c, "name": b["name"], "d": b["d_inner"], "D": b["d_outer"], "B": b["width"],
                          "C": b.get("C_kN", 0.0)} for c, b in BEARING_CATALOG.items()],
            "materials": [{"code": c, "name": m["name"], "printed": m["printed"]} for c, m in MATERIALS.items()],
            "motors": {c: {"torque": m.get("torque_nm", 0.3), "speed": m.get("speed_rpm", 1000),
                           "shaft": m["default_shaft_dia"], "shaft_type": m["default_shaft_type"]}
                       for c, m in MOTOR_CATALOG.items()},
        }

    def design(self, payload: Dict) -> Dict:
        """Otomatik boyutlandırma: aday tasarımlar + her biri için mühendislik özeti."""
        from core.design import design
        try:
            out = design(payload)
            out["success"] = True
            return out
        except Exception as e:
            log.error("Tasarım hatası: %s", traceback.format_exc())
            return self._error(f"Tasarım hesaplanamadı: {e}")

    # ── Üretim ───────────────────────────────────────────────────────────────
    def generate(self, payload: Dict) -> Dict:
        return self._build(payload, calibration=False)

    def generate_calibration(self, payload: Dict) -> Dict:
        """Seçili tasarımın rulman / pim / diş boşluğu geçmelerini deneyen kalibrasyon parçası."""
        return self._build(payload, calibration=True)

    def _build(self, payload: Dict, calibration: bool) -> Dict:
        if not isinstance(payload, dict):
            return self._error("Geçersiz istek.")
        if not self._lock.acquire(blocking=False):
            return self._error("Bir model zaten oluşturuluyor.")
        from occ_cad import assembly
        from occ_cad.kernel import GeometryError
        self._cancel.clear()
        self._progress.update({"running": True, "message": "", "percent": 0})
        try:
            if calibration:
                from occ_cad import calibration as builder
            else:
                builder = assembly
            result = builder.generate(
                payload,
                progress=lambda m, p: self._push({"event": "progress", "message": m, "percent": p}),
                cancelled=self._cancel.is_set,
            )
            self._result = result
            self._payload = payload
            log.info("Model üretildi: %s (%.2f s)", result.product_name, result.elapsed)
            out = {
                "success": True,
                "product": result.product_name,
                "elapsed": round(result.elapsed, 2),
                "warnings": result.warnings,
                "summary": result.summary,
                "engineering": result.engineering,
                "parts": assembly.parts_table(result),
            }
            if calibration:
                out.update(calibration=result.design["calibration"], steps=result.steps)
            return out
        except assembly.BuildCancelled:
            return self._error("İşlem iptal edildi.", cancelled=True)
        except GeometryError as e:
            return self._error(str(e))
        except Exception as e:  # pragma: no cover - beklenmeyen OCC hataları
            log.error("Model üretilemedi:\n%s", traceback.format_exc())
            return self._error(f"Modelleme hatası: {e}")
        finally:
            self._progress["running"] = False
            self._lock.release()

    def get_mesh(self, quality: str = "normal") -> Dict:
        if self._result is None:
            return self._error("Önce bir model oluşturun.")
        from occ_cad import export
        try:
            data = export.mesh_payload(self._result, quality)
            data["success"] = True
            return data
        except Exception as e:
            log.error("Mesh üretilemedi:\n%s", traceback.format_exc())
            return self._error(f"Görüntüleme verisi üretilemedi: {e}")

    # ── Dışa aktarma ─────────────────────────────────────────────────────────
    def choose_export_dir(self) -> Dict:
        if self._window is None:
            return self._error("Klasör seçimi yalnızca masaüstü uygulamasında kullanılabilir.")
        start = self._export_dir()
        os.makedirs(start, exist_ok=True)
        picked = self._window.create_file_dialog(_dialog_type("FOLDER"), directory=start)
        if not picked:
            return {"success": False, "cancelled": True}
        folder = picked[0] if isinstance(picked, (list, tuple)) else picked
        self._settings["export_dir"] = folder
        _save_settings(self._settings)
        return {"success": True, "export_dir": folder}

    def export_all(self) -> Dict:
        """STEP + baskıya hazır STL'ler + mühendislik raporu + parça listesi -> zaman damgalı klasör."""
        if self._result is None:
            return self._error("Önce bir model oluşturun.")
        from occ_cad import export, report
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = os.path.join(self._export_dir(), f"{self._result.product_name}_{stamp}")
        lang = "en" if str((self._payload or {}).get("lang", "tr")).startswith("en") else "tr"
        try:
            step = export.write_step(self._result, os.path.join(folder, f"{self._result.product_name}.step"))
            stls = export.write_stls(self._result, os.path.join(folder, "STL"))
            three_mf = self._write_3mf(folder)
            if self._result.design.get("calibration"):        # calibration coupon: its guide instead of the report
                from occ_cad import calibration
                rep_path = calibration.write_html(self._result, os.path.join(
                    folder, "Calibration_Guide.html" if lang == "en" else "Kalibrasyon_Rehberi.html"), lang)
                return {"success": True, "folder": folder, "step": step, "stl_count": len(stls), "bom": None,
                        "report": rep_path, "three_mf": three_mf}
            rep_path = report.write_html_report(self._result, os.path.join(
                folder, "Engineering_Report.html" if lang == "en" else "Muhendislik_Raporu.html"), lang)
            bom = report.write_bom_text(self._result, os.path.join(
                folder, "Bill_of_Materials.txt" if lang == "en" else "Parca_Listesi.txt"), lang)
            return {"success": True, "folder": folder, "step": step, "stl_count": len(stls), "bom": bom,
                    "three_mf": three_mf,
                    "report": rep_path}
        except Exception as e:
            log.error("Dışa aktarma hatası:\n%s", traceback.format_exc())
            return self._error(f"Dışa aktarma başarısız: {e}")

    def _write_3mf(self, folder: str) -> str:
        """Baskıya hazır 3MF: parça başına ayarlar; Creality K1 profili seçiliyse yazıcı + malzeme ayarlarıyla."""
        from occ_cad import print3mf
        pay = self._payload or {}
        stages = pay.get("stages") or []
        module = float((stages[0].get("module") if stages else None) or pay.get("module") or 1.0)
        bed = (float(pay.get("bed_x") or 256.0), float(pay.get("bed_y") or 256.0))
        profile = str(pay.get("slicer_profile") or "")
        name = f"{self._result.product_name}{'_' + profile.replace(' ', '_') if profile else ''}.3mf"
        return print3mf.write_3mf(self._result, os.path.join(folder, name), module=module, bed=bed, profile=profile,
                                  material=str(pay.get("gear_material") or "PLA"))

    def export_step(self) -> Dict:
        """Kaydetme penceresiyle tek STEP dosyası (Fusion 360'a montaj olarak aktarılır)."""
        if self._result is None:
            return self._error("Önce bir model oluşturun.")
        from occ_cad import export
        name = f"{self._result.product_name}.step"
        if self._window is None:
            target = os.path.join(self._export_dir(), name)
        else:
            os.makedirs(self._export_dir(), exist_ok=True)
            picked = self._window.create_file_dialog(_dialog_type("SAVE"), directory=self._export_dir(),
                                                     save_filename=name, file_types=("STEP (*.step;*.stp)",))
            if not picked:
                return {"success": False, "cancelled": True}
            target = picked[0] if isinstance(picked, (list, tuple)) else picked
            if not target.lower().endswith((".step", ".stp")):
                target += ".step"
        try:
            return {"success": True, "path": export.write_step(self._result, target)}
        except Exception as e:
            log.error("STEP hatası:\n%s", traceback.format_exc())
            return self._error(f"STEP yazılamadı: {e}")

    def open_path(self, path: str) -> Dict:
        if not path or not os.path.exists(path):
            return self._error("Klasör bulunamadı.")
        # yalnızca klasörler ve üretilen çıktı türleri açılır (çalıştırılabilir dosyalar asla)
        if not os.path.isdir(path) and os.path.splitext(path)[1].lower() not in OPENABLE:
            return self._error("Bu dosya türü açılamaz.")
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            return {"success": True}
        except OSError as e:
            return self._error(str(e))

    # ── Gereksinimden tasarım (internetsiz) ──────────────────────────────────
    def solve_requirements(self, req: Dict) -> Dict:
        from core.requirements import solve
        try:
            return solve(req or {})
        except Exception as e:
            log.error("Çözücü hatası: %s", traceback.format_exc())
            return self._error(f"Çözüm hesaplanamadı: {e}")

    # ── AI asistan (Gemini) ──────────────────────────────────────────────────
    def _ai_key(self) -> Optional[str]:
        from .ai import keystore
        return keystore.decrypt(self._settings.get("ai", {}).get("key"))

    def _ai_client(self, key: str, model: str):
        from .ai import gemini
        return gemini.GeminiClient(key, model, log=log.info, transport=self._ai_transport)

    def _ai_models(self) -> List[str]:
        """Kullanılacak modeller (en güçlü önce). 'auto': hesabın model listesinden seçilir (1 saat önbellek)."""
        from .ai import gemini
        chosen = self._settings.get("ai", {}).get("model", "auto") or "auto"
        if chosen != "auto":
            return [chosen]
        if self._ai_model_cache and time.time() - self._ai_model_cache[0] < 3600:
            return self._ai_model_cache[1]
        key = self._ai_key()
        if not key:
            return []
        ranked = gemini.rank_models(gemini.list_models(key, self._ai_transport))[:5]
        self._ai_model_cache = (time.time(), ranked)
        return ranked

    def _ai(self):
        if self._assistant is None:
            from .ai.agent import Assistant
            self._assistant = Assistant(lambda: {"api_key": self._ai_key(),
                                                 "model": self._settings.get("ai", {}).get("model", "auto")},
                                        self._ai_client, self._ai_models)
        return self._assistant

    def ai_settings_get(self) -> Dict:
        from .ai import keystore
        cfg = self._settings.get("ai", {})
        key = self._ai_key()
        return {"success": True, "has_key": bool(key), "key_hint": keystore.hint(key),
                "protected": keystore.is_protected(cfg.get("key")), "model": cfg.get("model", "auto"),
                "models": cfg.get("models", [])}

    def ai_settings_set(self, data: Dict) -> Dict:
        """{'api_key': '...'} anahtarı şifreleyip saklar ('' + clear_key: siler); {'model': 'auto' | id}."""
        from .ai import keystore
        data = data or {}
        cfg = self._settings.setdefault("ai", {})
        if "api_key" in data:
            k = str(data.get("api_key") or "").strip()
            if k:
                if len(k) < 20 or any(c.isspace() for c in k):
                    return self._error("Bu bir Gemini API anahtarına benzemiyor.")
                cfg["key"] = keystore.encrypt(k)
            elif data.get("clear_key"):
                cfg.pop("key", None)
        if data.get("model"):
            cfg["model"] = str(data["model"]).strip()
        self._ai_model_cache = None
        _save_settings(self._settings)
        return self.ai_settings_get()

    def ai_list_models(self) -> Dict:
        from .ai import gemini
        key = self._ai_key()
        if not key:
            return self._error("Önce Gemini API anahtarını kaydedin.")
        try:
            models = gemini.list_models(key, self._ai_transport)
        except gemini.GeminiError as e:
            return self._error(str(e))
        ranked = gemini.rank_models(models)
        names = {m["id"]: m["name"] for m in models}
        listing = [{"id": mid, "name": names.get(mid, mid)} for mid in ranked]
        self._settings.setdefault("ai", {})["models"] = listing[:30]
        _save_settings(self._settings)
        self._ai_model_cache = (time.time(), ranked[:5])
        return {"success": True, "models": listing, "auto": ranked[0] if ranked else None}

    def ai_test(self) -> Dict:
        from .ai import gemini
        key = self._ai_key()
        if not key:
            return self._error("Önce Gemini API anahtarını kaydedin.")
        try:
            models = self._ai_models()
            if not models:
                return self._error("Kullanılabilir model bulunamadı.")
            t0 = time.time()
            last = None
            for model in models[:3]:
                try:
                    res = self._ai_client(key, model).generate(
                        [{"role": "user", "parts": [{"text": "Reply with the single word OK."}]}], "Reply briefly.", [])
                    return {"success": True, "model": model, "reply": gemini.text_of(res["content"]).strip()[:40],
                            "seconds": round(time.time() - t0, 1)}
                except gemini.GeminiError as e:
                    last = e
                    if not (e.quota or e.status in (403, 404)):
                        break
            return self._error(str(last))
        except gemini.GeminiError as e:
            return self._error(str(e))

    def ai_send(self, message: str, form_state: Optional[Dict] = None) -> Dict:
        if not str(message or "").strip():
            return self._error("Boş mesaj.")
        lang = str((form_state or {}).get("lang", "tr"))
        try:
            job = self._ai().send(str(message)[:8000], form_state or {}, lang)
        except RuntimeError as e:
            return self._error(str(e))
        return {"success": True, "job": job.id}

    def ai_poll(self, job_id: str) -> Dict:
        return self._ai().poll(str(job_id))

    def ai_reset(self) -> Dict:
        if not self._ai().reset():
            return self._error("Önceki istek hâlâ sürüyor.")
        return {"success": True}
