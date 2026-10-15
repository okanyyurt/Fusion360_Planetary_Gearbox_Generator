# -*- coding: utf-8 -*-
"""
Fusion 360 eklentisi için CAD motoru köprüsü.

Fusion'ın gömülü Python'unda OpenCascade (OCP) yoktur ve Fusion sürecine büyük yerel DLL'ler
yüklemek risklidir. Bu yüzden tasarım ve mühendislik hesapları (core/, saf Python) Fusion içinde,
geometri ise OCP kurulu sistem Python'unda ayrı süreçte (`python -m standalone build`) üretilir.
Üretilen STEP montajı Fusion'a aktarılır; STL'ler ve rapor aynı klasöre yazılır.
"""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import threading
import time
from typing import Callable, Dict, List, Optional

from . import paths

CANDIDATES = [["py", "-3.14"], ["py", "-3.13"], ["py", "-3.12"], ["py", "-3.11"], ["python"], ["python3"]]
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
PROGRESS = re.compile(r"^\s*(\d+)%\s+(.*)$")


def _probe(cmd: List[str]) -> bool:
    try:
        r = subprocess.run(cmd + ["-c", "import OCP"], capture_output=True, timeout=40, creationflags=NO_WINDOW)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def find_engine_python(settings: Dict) -> Optional[List[str]]:
    """OCP kurulu bir Python bulur; sonucu ayarlarda saklar (ör. ["py", "-3.14"])."""
    cached = settings.get("engine_python")
    if isinstance(cached, list) and cached and _probe(cached):
        return cached
    for cmd in CANDIDATES:
        if _probe(cmd):
            settings["engine_python"] = cmd
            return cmd
    return None


def run_engine(cmd: List[str], payload: Dict, out_dir: str, on_progress: Callable[[int, str], None],
               pump: Optional[Callable[[], None]] = None, timeout: float = 900.0) -> Dict:
    """
    Motoru çalıştırır, ilerleme satırlarını iletir. `pump` Fusion arayüzünün donmaması için
    beklerken düzenli çağrılır (adsk.doEvents). Döndürür: motorun yazdığı sonuç sözlüğü.
    """
    os.makedirs(out_dir, exist_ok=True)
    cfg = os.path.join(out_dir, "_payload.json")
    result_path = os.path.join(out_dir, "_result.json")
    with open(cfg, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    proc = subprocess.Popen(cmd + ["-m", "standalone", "build", "--config", cfg, "-o", out_dir,
                                   "--result-json", result_path],
                            cwd=paths.project_root(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                            creationflags=NO_WINDOW)
    lines: "queue.Queue[Optional[str]]" = queue.Queue()

    def reader():
        for raw in proc.stdout:
            lines.put(raw.decode("utf-8", "replace").rstrip())
        lines.put(None)

    threading.Thread(target=reader, daemon=True).start()
    tail: List[str] = []
    done = False
    t0 = time.time()
    while not done:
        try:
            while True:
                line = lines.get_nowait()
                if line is None:
                    done = True
                    break
                tail = (tail + [line])[-25:]
                m = PROGRESS.match(line)
                if m:
                    on_progress(int(m.group(1)), m.group(2))
        except queue.Empty:
            pass
        if pump:
            pump()
        if time.time() - t0 > timeout:
            proc.kill()
            raise RuntimeError("CAD motoru zaman aşımına uğradı.")
        time.sleep(0.05)
    proc.wait()
    try:
        os.remove(cfg)
    except OSError:
        pass
    if proc.returncode != 0 or not os.path.exists(result_path):
        raise RuntimeError("CAD motoru hata verdi:\n" + "\n".join(tail[-12:]))
    with open(result_path, "r", encoding="utf-8") as fh:
        result = json.load(fh)
    os.remove(result_path)
    return result
