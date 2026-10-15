# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec of the standalone app (offline, no Python needed):  python -m PyInstaller packaging/pgb.spec
# Folder build (onedir): OpenCascade is ~100 MB, a one-file exe would unpack it on every start.
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
datas = [(os.path.join(ROOT, "ui"), "ui"), (os.path.join(ROOT, "resources"), "resources"),
         (os.path.join(ROOT, "LICENSE"), "."), (os.path.join(ROOT, "CHANGELOG.md"), ".")]
binaries, hidden = [], []
for pkg in ("OCP", "webview"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hidden += h
hidden += collect_submodules("core") + collect_submodules("occ_cad") + collect_submodules("standalone")

a = Analysis([os.path.join(SPECPATH, "launcher.py")], pathex=[ROOT], binaries=binaries, datas=datas,
             hiddenimports=hidden, excludes=["tkinter", "matplotlib", "numpy.tests", "PyQt5", "PyQt6", "PySide6"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PlanetaryGearbox", icon=os.path.join(SPECPATH, "logo.ico"),
          console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="PlanetaryGearbox", upx=False)
