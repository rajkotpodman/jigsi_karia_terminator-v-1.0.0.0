# -*- mode: python ; coding: utf-8 -*-
# PyFileShare - PyInstaller spec for a single-file, self-contained executable
# that embeds the `cloudflared` binary (extracted to sys._MEIPASS at runtime).
#
# Usage (run from the directory containing this file):
#   pyinstaller app.spec
#
# Before building, place the correct `cloudflared` binary in THIS folder:
#   Windows : cloudflared.exe
#   macOS   : cloudflared   (arm64 or x86_64 to match the target Mac)
#   Linux   : cloudflared   (amd64/arm64 to match the target machine)
#
# If the binary is missing, PyInstaller still builds the app but the tunnel
# feature degrades gracefully (the app then looks in CWD / APP_DIR / PATH).

import os
import sys
from shutil import which

# --- 1. Locate the cloudflared binary to embed -----------------------------
if sys.platform.startswith("win"):
    binary_name = "cloudflared.exe"
else:
    binary_name = "cloudflared"

_candidates = [
    os.path.join(SPECPATH, binary_name),   # next to this spec file
    os.path.join(os.getcwd(), binary_name),
    which(binary_name) or "",
]
cloudflared_path = next((p for p in _candidates if p and os.path.isfile(p)), None)

if cloudflared_path:
    # ('source', 'dest') -> dest '.' places it at the root of the temp
    # extraction dir, so sys._MEIPASS/cloudflared(.exe) works at runtime.
    binaries = [(cloudflared_path, ".")]
    print(f"[app.spec] Bundling cloudflared: {cloudflared_path}")
else:
    binaries = []
    print(f"[app.spec] WARNING: {binary_name} not found next to the spec, in "
          f"CWD, or on PATH. The bundled binary will be MISSING.",
          file=sys.stderr)

# --- 2. Static data (icon etc.) -------------------------------------------
datas = []
_icon = os.path.join(SPECPATH, "app.ico")
if os.path.isfile(_icon):
    datas.append((_icon, "."))
else:
    _icon = None

# --- 3. Platform-specific hidden imports ----------------------------------
hiddenimports = []
if sys.platform.startswith("win"):
    hiddenimports += ["pystray._win32"]
elif sys.platform.startswith("linux"):
    hiddenimports += ["pystray._xorg"]

# --- 4. Analysis -----------------------------------------------------------
a = Analysis(
    ["app.py"],
    pathex=[SPECPATH],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

# --- 5. One-file executable (GUI / windowed: console=False) ---------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,          # <- embeds the cloudflared binary in the onefile exe
    a.datas,
    [],
    name="PyFileShare",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # deterministic builds; enable if UPX is installed
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # windowed GUI (no console window on Windows)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)

# --- 6. macOS .app bundle (single-file style) ------------------------------
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="PyFileShare.app",
        icon=_icon,
        bundle_identifier="com.pyfileshare.server",
        info_plist={
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "PyFileShare",
        },
    )
