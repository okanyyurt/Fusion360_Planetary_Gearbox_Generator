# -*- coding: utf-8 -*-
"""
Bağımsız (Fusion 360 gerektirmeyen) uygulamanın giriş noktası.

  python -m standalone                 masaüstü penceresi (pywebview / WebView2)
  python -m standalone serve           arayüzü tarayıcıda açmak için yerel sunucu (127.0.0.1)
  python -m standalone build ...       arayüzsüz üretim: STEP + STL klasörü
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from . import paths


def _setup_logging(console: bool) -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        fh = RotatingFileHandler(os.path.join(paths.logs_dir(), "app.log"), maxBytes=1_000_000,
                                 backupCount=2, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass
    if console:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)


def _utf8_console() -> None:
    """Windows konsolunda (cp1254/cp857) Türkçe karakter ve emoji yazdırırken çökmeyi önler."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def run_gui() -> int:
    try:
        import webview
    except ImportError as e:
        print(f"pywebview yüklenemedi ({e}). 'python -m standalone serve' ile tarayıcıda açabilirsiniz.")
        return 1
    from .api import Api, VERSION
    api = Api()
    html = os.path.join(paths.ui_dir(), "index.html")
    if not os.path.exists(html):
        logging.error("Arayüz bulunamadı: %s", html)
        return 1
    window = webview.create_window(f"Planet Redüktör Tasarımcısı {VERSION}", url=html, js_api=api,
                                   width=1500, height=930, min_size=(1100, 700), background_color="#0f141c")
    api._set_window(window)
    webview.start(debug=os.environ.get("PGB_DEBUG") == "1")
    return 0


def run_server(port: int) -> int:
    from .server import serve
    return serve(port)


def run_build(args) -> int:
    from core.design import design
    from occ_cad import assembly, export, report

    payload = {}
    if args.config:
        with open(args.config, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    payload.setdefault("target_ratio", args.ratio)
    payload.setdefault("stages_count", args.stages)
    payload.setdefault("num_planets", args.planets)
    payload.setdefault("is_herringbone", args.herringbone)
    payload.setdefault("lang", "tr")
    if args.module:
        payload.setdefault("sizing_mode", "MANUAL")
        payload.setdefault("module", args.module)
    if not payload.get("stages"):
        cands = design(payload)["candidates"]
        if not cands:
            print("Uygun tasarım bulunamadı (oran toleransını veya boyutlandırma modunu değiştirin).")
            return 2
        print(f"Tasarım: {cands[0]['label']}")
        payload.update(total_ratio=cands[0]["total_ratio"], stages=cands[0]["stages"])

    res = assembly.generate(payload, progress=lambda m, p: print(f"  {p:3d}%  {m}", flush=True))
    out = os.path.abspath(args.output)
    step = export.write_step(res, os.path.join(out, f"{res.product_name}.step"))
    stls = export.write_stls(res, os.path.join(out, "STL"))
    rep = report.write_html_report(res, os.path.join(out, "Muhendislik_Raporu.html"), payload["lang"])
    report.write_bom_text(res, os.path.join(out, "Parca_Listesi.txt"), payload["lang"])
    e = res.engineering
    print(f"\nSüre: {res.elapsed:.2f} s  |  STEP: {step}  |  STL: {len(stls)} dosya  |  Rapor: {rep}")
    print(f"Çıkış: {e['output_torque']:.2f} Nm @ {e['output_speed']:.1f} rpm · sürekli kapasite "
          f"{e['max_output_torque']:.2f} Nm · sınırlayan: {e['limiting']['label'] if e['limiting'] else '-'}")
    for w in res.warnings:
        print(f"  ! {w}")
    if args.result_json:
        with open(args.result_json, "w", encoding="utf-8") as fh:
            json.dump({"product": res.product_name, "summary": res.summary, "warnings": res.warnings,
                       "engineering": e, "elapsed": round(res.elapsed, 2), "folder": out, "step": step,
                       "report": rep, "stl_count": len(stls), "kinematics": assembly.kinematics_table(res),
                       "parts": assembly.parts_table(res)},
                      fh, ensure_ascii=False, default=str)
    return 0


def main(argv=None) -> int:
    _utf8_console()
    root = paths.project_root()
    if root not in sys.path:
        sys.path.insert(0, root)

    parser = argparse.ArgumentParser(prog="python -m standalone", description="Planet Redüktör Tasarımcısı")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("gui", help="Masaüstü uygulaması (varsayılan)")
    p_srv = sub.add_parser("serve", help="Arayüzü tarayıcıda açmak için yerel sunucu")
    p_srv.add_argument("--port", type=int, default=8765)
    p_b = sub.add_parser("build", help="Arayüzsüz üretim (STEP + STL)")
    p_b.add_argument("-o", "--output", default="cikti")
    p_b.add_argument("--config", help="Arayüzün gönderdiği JSON yükü (payload)")
    p_b.add_argument("--ratio", type=float, default=25.0)
    p_b.add_argument("--stages", type=int, default=2)
    p_b.add_argument("--planets", type=int, default=3)
    p_b.add_argument("--module", type=float, default=None, help="Manuel modül (verilmezse otomatik boyutlandırma)")
    p_b.add_argument("--herringbone", action="store_true")
    p_b.add_argument("--result-json", help="Sonuç özetinin yazılacağı JSON dosyası (Fusion eklentisi için)")
    args = parser.parse_args(argv)

    cmd = args.cmd or "gui"
    _setup_logging(console=cmd != "gui" or not paths.is_frozen())
    if cmd == "serve":
        return run_server(args.port)
    if cmd == "build":
        return run_build(args)
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
