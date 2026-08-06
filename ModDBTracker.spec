# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: single-file, windowed ModDB Tracker GUI exe.

Build:  .venv\Scripts\pyinstaller ModDBTracker.spec --noconfirm
Set console=True for a debug build that shows stderr; False for the release.
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = []
binaries = []
hiddenimports = []

# curl_cffi ships a native libcurl + CA bundle; must be bundled wholesale.
for pkg in ("curl_cffi",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# reportlab loads its font/metrics tables dynamically.
hiddenimports += collect_submodules("reportlab")

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["hooks/rt_hook_moddb.py"],
    excludes=["tkinter", "PyQt5", "PySide2", "PySide6"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ModDBTracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="ModDBTracker.ico",
)
