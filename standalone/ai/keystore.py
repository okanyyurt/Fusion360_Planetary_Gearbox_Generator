# -*- coding: utf-8 -*-
"""
API anahtarının diskte saklanması. Windows'ta DPAPI (CryptProtectData, kullanıcı kapsamı) ile
şifrelenir: dosya kopyalansa bile başka kullanıcı/bilgisayarda çözülemez. Bağımsız uygulama ve
Fusion eklentisi aynı Windows kullanıcısıyla çalıştığı için anahtar bir kez girilir.
Windows dışı sistemlerde (geliştirme) yalnızca base64 ile saklanır ve bu durum belirtilir.
"""
from __future__ import annotations

import base64
import os
from typing import Optional

_ENTROPY = b"PlanetaryGearbox.ai.v1"


def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob(b: bytes):
        buf = ctypes.create_string_buffer(b, len(b))
        return DATA_BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    src, _keep1 = blob(data)
    ent, _keep2 = blob(_ENTROPY)
    out = DATA_BLOB()
    flags = 0x1                                   # CRYPTPROTECT_UI_FORBIDDEN
    if protect:
        ok = crypt32.CryptProtectData(ctypes.byref(src), ctypes.c_wchar_p("PlanetaryGearbox AI"), ctypes.byref(ent),
                                      None, None, flags, ctypes.byref(out))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(src), None, ctypes.byref(ent), None, None, flags,
                                        ctypes.byref(out))
    if not ok:
        raise OSError("DPAPI işlemi başarısız")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def encrypt(secret: str) -> str:
    raw = secret.encode("utf-8")
    if os.name == "nt":
        return "dpapi:" + base64.b64encode(_dpapi(raw, True)).decode("ascii")
    return "b64:" + base64.b64encode(raw).decode("ascii")


def decrypt(stored: Optional[str]) -> Optional[str]:
    if not stored or not isinstance(stored, str):
        return None
    try:
        kind, _, payload = stored.partition(":")
        data = base64.b64decode(payload)
        if kind == "dpapi":
            return _dpapi(data, False).decode("utf-8")
        if kind == "b64":
            return data.decode("utf-8")
    except (OSError, ValueError):
        return None
    return None


def is_protected(stored: Optional[str]) -> bool:
    return bool(stored) and str(stored).startswith("dpapi:")


def hint(secret: Optional[str]) -> str:
    """Arayüzde gösterilen maskeli hali: yalnızca son 4 karakter."""
    if not secret:
        return ""
    return "••••" + secret[-4:]
