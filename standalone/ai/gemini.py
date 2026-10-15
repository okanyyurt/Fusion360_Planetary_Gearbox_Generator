# -*- coding: utf-8 -*-
"""
Gemini API istemcisi (REST, yalnızca standart kütüphane: hem bağımsız uygulamada hem de Fusion 360'ın
gömülü Python'unda çalışır).

  GET  {BASE}/models                         modeller (generateContent destekleyenler)
  POST {BASE}/models/{model}:generateContent  araç (function calling) destekli üretim

Anahtar `x-goog-api-key` başlığıyla yalnızca generativelanguage.googleapis.com adresine gönderilir.
Modelin yanıt içeriği (düşünce imzaları / thoughtSignature dahil) geçmişe aynen eklenmelidir.
"""
from __future__ import annotations

import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional, Tuple

BASE = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT = 180.0
EXCLUDE = ("embedding", "imagen", "image", "tts", "audio", "live", "veo", "aqa", "learnlm", "robotics",
           "computer-use", "omni", "gemma", "nano", "vision", "dialog", "lyria", "native")


class GeminiError(Exception):
    def __init__(self, message: str, status: int = 0, retry: bool = False, quota: bool = False):
        super().__init__(message)
        self.status = status
        self.retry = retry
        self.quota = quota


def _request(method: str, url: str, api_key: str, body: Optional[Dict] = None, timeout: float = TIMEOUT) -> Dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("x-goog-api-key", api_key)
    if data is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            info = json.loads(e.read().decode("utf-8") or "{}").get("error", {})
        except (ValueError, OSError):
            info = {}
        msg = info.get("message") or str(e)
        status = e.code
        quota = status == 429 and ("limit: 0" in msg or "free_tier" in msg.replace(" ", "_").lower())
        if status in (400, 401, 403) and ("API key" in msg or "API_KEY" in msg or "PERMISSION" in str(info.get("status"))):
            raise GeminiError("API anahtarı geçersiz veya yetkisiz: " + msg, status) from None
        raise GeminiError(msg, status, retry=status in (429, 500, 502, 503, 504) and not quota, quota=quota) from None
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, ssl.SSLError):
            raise GeminiError("TLS/SSL doğrulama hatası — şirket ağı veya proxy HTTPS trafiğini denetliyor olabilir "
                              f"({reason}).", 0) from None
        raise GeminiError(f"Gemini sunucusuna ulaşılamadı: {reason}", 0, retry=True) from None
    except (socket.timeout, TimeoutError):
        raise GeminiError("Gemini yanıtı zaman aşımına uğradı.", 0, retry=True) from None


def list_models(api_key: str, transport: Optional[Callable] = None) -> List[Dict]:
    out, token = [], None
    for _ in range(5):
        url = f"{BASE}/models?pageSize=200" + (f"&pageToken={token}" if token else "")
        res = (transport("GET", url, api_key, None) if transport
               else _request("GET", url, api_key, timeout=30.0))
        for m in res.get("models", []):
            if "generateContent" not in (m.get("supportedGenerationMethods") or []):
                continue
            mid = str(m.get("name", "")).split("/", 1)[-1]
            out.append({"id": mid, "name": m.get("displayName") or mid, "description": m.get("description", ""),
                        "input_tokens": m.get("inputTokenLimit"), "thinking": bool(m.get("thinking"))})
        token = res.get("nextPageToken")
        if not token:
            break
    return out


def _version(mid: str) -> float:
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", mid)
    return float(m.group(1)) if m else 0.0


TIER_BONUS = {"lite": -1.2, "flash": 0.4, "other": 0.6, "pro": 0.8}


def model_score(mid: str) -> Tuple:
    """
    'En güçlü model' sıralaması: sürüm + seviye. Hafif (lite) modeller araç kullanan ajan için en son
    tercih edilir: gemini-3.1-pro > gemini-3-flash > gemini-2.5-pro > gemini-2.5-flash > *-flash-lite.
    """
    low = mid.lower()
    if "lite" in low:
        tier = "lite"
    elif "flash" in low:
        tier = "flash"
    elif "pro" in low or "ultra" in low:
        tier = "pro"
    else:
        tier = "other"
    stable = 0 if ("preview" in low or "exp" in low) else 1
    return (round(_version(low) + TIER_BONUS[tier], 3), stable, -len(low))


def rank_models(models: List[Dict]) -> List[str]:
    ids = [m["id"] for m in models if m["id"].startswith("gemini") and not any(x in m["id"].lower() for x in EXCLUDE)
           and not re.search(r"-\d{3}$", m["id"])]                 # sabit sürüm kopyaları (…-001) yerine takma adlar
    return sorted(set(ids), key=model_score, reverse=True)


def to_openapi(schema: Dict) -> Dict:
    """JSON Schema (küçük harf türler) -> Gemini Schema (OpenAPI alt kümesi, büyük harf türler)."""
    out = {}
    for k, v in schema.items():
        if k == "type":
            out["type"] = str(v).upper()
        elif k == "properties":
            out["properties"] = {n: to_openapi(s) for n, s in v.items()}
        elif k == "items":
            out["items"] = to_openapi(v)
        elif k in ("description", "enum", "required", "format", "nullable", "minimum", "maximum"):
            out[k] = v
    return out


class GeminiClient:
    def __init__(self, api_key: str, model: str, log: Optional[Callable[[str], None]] = None,
                 transport: Optional[Callable[[str, str, str, Optional[Dict]], Dict]] = None):
        self.api_key = api_key
        self.model = model
        self._log = log or (lambda s: None)
        self._transport = transport or (lambda method, url, key, body: _request(method, url, key, body))

    def generate(self, contents: List[Dict], system: str, tools: List[Dict], tool_mode: str = "AUTO") -> Dict:
        body = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system}]},
            "tools": [{"functionDeclarations": tools}] if tools else [],
            "toolConfig": {"functionCallingConfig": {"mode": tool_mode}},
        }
        if not tools:
            body.pop("tools")
            body.pop("toolConfig")
        url = f"{BASE}/models/{self.model}:generateContent"
        delay = 2.0
        for attempt in range(4):
            try:
                res = self._transport("POST", url, self.api_key, body)
                break
            except GeminiError as e:
                if not e.retry or attempt == 3:
                    raise
                self._log(f"retry {attempt + 1}: {e}")
                time.sleep(delay)
                delay *= 2.0
        cands = res.get("candidates") or []
        if not cands:
            fb = res.get("promptFeedback") or {}
            raise GeminiError("Model yanıt üretmedi" + (f" ({fb.get('blockReason')})" if fb.get("blockReason") else "."))
        cand = cands[0]
        content = cand.get("content") or {"role": "model", "parts": []}
        content.setdefault("role", "model")
        content.setdefault("parts", [])
        return {"content": content, "finish": cand.get("finishReason", ""), "usage": res.get("usageMetadata", {}),
                "model_version": res.get("modelVersion", self.model)}


def function_calls(content: Dict) -> List[Dict]:
    return [p["functionCall"] for p in content.get("parts", []) if isinstance(p, dict) and "functionCall" in p]


def text_of(content: Dict) -> str:
    return "".join(p.get("text", "") for p in content.get("parts", [])
                   if isinstance(p, dict) and "text" in p and not p.get("thought"))
