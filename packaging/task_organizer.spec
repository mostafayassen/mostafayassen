# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Task Organizer Windows build.
#
# Build from the repo root with:
#   pyinstaller --noconfirm --distpath dist --workpath build packaging/task_organizer.spec
#
# Produces dist/TaskOrganizer/TaskOrganizer.exe (a one-folder build -- more
# reliable for PySide6 apps than --onefile, and what packaging/installer.iss
# expects to find).

from pathlib import Path

block_cipher = None
repo_root = Path(SPECPATH).resolve().parent

# Explicitly listed because PyInstaller's static import scan can miss
# plugin-style imports these libraries load dynamically at runtime.
hiddenimports = [
    "apscheduler.schedulers.background",
    "apscheduler.triggers.date",
    "apscheduler.triggers.interval",
    "apscheduler.triggers.cron",
    "apscheduler.executors.pool",
    "apscheduler.jobstores.memory",
    "plyer.platforms.win.notification",
    "msal",
]

a = Analysis(
    [str(repo_root / "launcher.py")],
    pathex=[str(repo_root)],
    binaries=[],
    datas=[],
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
    name="TaskOrganizer",
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
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TaskOrganizer",
)
