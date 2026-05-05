# -*- mode: python ; coding: utf-8 -*-
# Run from repo root: pyinstaller packaging/realtime_translation.spec
# Or: scripts/build_windows.ps1
#
# PySide6 is pulled in via import graph + official PyInstaller hooks (hook-PySide6.py).
# Avoid collect_all(PySide6): it bundles the entire Qt tree (WebEngine, SQL drivers, etc.).

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

spec_dir = Path(SPECPATH)
project_root = spec_dir.parent

block_cipher = None

datas = collect_data_files("certifi")
binaries = collect_dynamic_libs("pyaudiowpatch")
hiddenimports = list(collect_submodules("qasync"))
hiddenimports += [
    "keyring.backends.Windows",
    "keyring.backends.chainer",
]

a = Analysis(
    [str(project_root / "app" / "main.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RealTimeTranslation",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="RealTimeTranslation",
)
