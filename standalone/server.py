# -*- coding: utf-8 -*-
"""
Yerel HTTP sunucusu: arayüzü normal bir tarayıcıda çalıştırır (pywebview yoksa veya
geliştirme/test için). Yalnızca 127.0.0.1'e bağlanır.

  GET  /...              ui/ klasöründeki statik dosyalar
  POST /api/<metot>      {"args": [...]}  ->  Api.<metot>(*args) sonucu (JSON)
"""
from __future__ import annotations

import json
import logging
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from . import paths
from .api import STANDALONE_METHODS, Api

log = logging.getLogger(__name__)

ALLOWED = STANDALONE_METHODS - {"choose_export_dir"}     # dosya diyaloğu yalnızca masaüstü penceresinde
# Başka bir sitenin tarayıcı üzerinden yerel API'yi çağırmasını (CSRF) önler: özel başlık, CORS ön
# kontrolü olmadan başka kaynaktan gönderilemez.
CLIENT_HEADER = "X-PGB-Client"


class _Handler(SimpleHTTPRequestHandler):
    api: Api = None  # type: ignore[assignment]

    def log_message(self, fmt, *args):  # sessiz
        log.debug(fmt, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, code: int, data) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not self.path.startswith("/api/"):
            return self._json(404, {"success": False, "error": "bulunamadı"})
        name = self.path[5:].split("?")[0]
        if self.headers.get(CLIENT_HEADER) != "1":
            return self._json(403, {"success": False, "error": "izin verilmeyen istemci"})
        if name not in ALLOWED:
            return self._json(404, {"success": False, "error": f"bilinmeyen metot: {name}"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}") if length else {}
            result = getattr(self.api, name)(*body.get("args", []))
            self._json(200, result)
        except Exception as e:  # pragma: no cover
            log.exception("API hatası")
            self._json(500, {"success": False, "error": str(e)})


def serve(port: int = 8765) -> int:
    handler = partial(_Handler, directory=paths.ui_dir())
    _Handler.api = Api()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/index.html"
    print(f"Arayüz: {url}  (durdurmak için Ctrl+C)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
