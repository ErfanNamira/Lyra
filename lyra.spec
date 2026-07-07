# -*- mode: python ; coding: utf-8 -*-
# Build with: pyinstaller lyra.spec

import sys
from pathlib import Path

block_cipher = None

_spec_dir = Path(SPECPATH)

if sys.platform.startswith("win"):
    _icon_path = _spec_dir / "icon.ico"
elif sys.platform == "darwin":
    _icon_path = _spec_dir / "icon.icns"
else:
    _icon_path = None

icon_file = str(_icon_path) if _icon_path and _icon_path.exists() else None

if _icon_path is not None and icon_file is None:
    print(f"!! WARNING: expected icon '{_icon_path.name}' not found at "
          f"'{_icon_path}' - building WITHOUT an icon. Make sure "
          f"'{_icon_path.name}' is committed next to lyra.py in the repo root.")
else:
    print(f">> Using icon: {icon_file}")

a = Analysis(
    ["lyra.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "spotdl",
        "rich",
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="lyra",
    version="version_info.txt",
    icon=icon_file,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX is known to strip/corrupt the embedded icon resource on Windows
    # exes in some PyInstaller/UPX version combos - keep it off so the icon
    # reliably shows up. The size savings aren't worth the flakiness here.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
