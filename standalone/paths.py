# -*- coding: utf-8 -*-
"""
Uygulama yolları. Kullanıcı adı / OneDrive klasörü Türkçe karakter içerebilir
(ör. C:\\Users\\Okan Yeşilyurt\\OneDrive - ...\\Belgeler); tüm yollar Python str olarak
taşınır, OpenCASCADE'e yalnızca ASCII geçici yollar verilir (bkz. occ_cad.export).
"""
from __future__ import annotations

import os
import sys

APP_NAME = "PlanetaryGearbox"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> str:
    """Kaynakların kökü (core/, occ_cad/, ui/). PyInstaller paketinde _MEIPASS."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ui_dir() -> str:
    return os.path.join(project_root(), "ui")


def user_data_dir() -> str:
    """%APPDATA%\\PlanetaryGearbox (ayarlar ve günlük dosyaları)."""
    override = os.environ.get("PLANETARY_GEARBOX_HOME")
    if override:
        base = override
    elif os.name == "nt":
        base = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
    else:
        base = os.path.join(os.path.expanduser("~"), "." + APP_NAME.lower())
    os.makedirs(base, exist_ok=True)
    return base


def logs_dir() -> str:
    d = os.path.join(user_data_dir(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


def settings_path() -> str:
    return os.path.join(user_data_dir(), "settings.json")


def documents_dir() -> str:
    """Windows 'Belgeler' klasörü (OneDrive'a yönlendirilmiş olsa bile doğru yolu verir)."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]

            # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
            fid = GUID(0xFDD39AD0, 0x238F, 0x46AF, (wintypes.BYTE * 8)(
                0xAD - 256, 0xB4 - 256, 0x6C, 0x85 - 256, 0x48, 0x03, 0x69, 0xC7 - 256))
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(out)) == 0:
                path = out.value
                ctypes.windll.ole32.CoTaskMemFree(out)
                if path and os.path.isdir(path):
                    return path
        except Exception:
            pass
    home = os.path.expanduser("~")
    for name in ("Documents", "Belgeler"):
        cand = os.path.join(home, name)
        if os.path.isdir(cand):
            return cand
    return home


def default_export_dir() -> str:
    return os.path.join(documents_dir(), "Planet Reduktor Ciktilari")
