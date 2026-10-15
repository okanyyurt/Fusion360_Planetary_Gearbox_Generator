# -*- coding: utf-8 -*-
"""
Builds the offline Windows app and its release zip (no Python needed on the target PC).

    python -m pip install pyinstaller cadquery-ocp-novtk pywebview
    python packaging/build_release.py            ->  <temp>/pgb_build/PlanetaryGearbox-<version>-win64.zip

The build runs outside the project folder (it is ~200 MB; OneDrive would sync it).
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from standalone.api import VERSION  # noqa: E402

out = os.path.join(os.environ.get("PGB_BUILD_DIR") or tempfile.gettempdir(), "pgb_build")
dist, work = os.path.join(out, "dist"), os.path.join(out, "work")
subprocess.check_call([sys.executable, "-m", "PyInstaller", os.path.join(ROOT, "packaging", "pgb.spec"),
                       "--noconfirm", "--distpath", dist, "--workpath", work])
app = os.path.join(dist, "PlanetaryGearbox")
for doc in ("README.md",):
    shutil.copy2(os.path.join(ROOT, doc), app)
zip_base = os.path.join(out, f"PlanetaryGearbox-{VERSION}-win64")
shutil.make_archive(zip_base, "zip", dist, "PlanetaryGearbox")
print(f"{zip_base}.zip  ({os.path.getsize(zip_base + '.zip') / 2**20:.0f} MB)")
