# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

yt_dlp_submodules = collect_submodules('yt_dlp')
yt_dlp_datas = collect_data_files('yt_dlp')

base_dir = os.path.abspath(SPECPATH)
icon_path = os.path.join(base_dir, 'assets', 'icon.ico')

a = Analysis(
    ['main.py'],
    pathex=[base_dir],
    binaries=[],
    datas=[('assets', 'assets')] + yt_dlp_datas,
    hiddenimports=[
        'yt_dlp',
        'flet',
        'flet_video',
        'flet_webview',
        'flet_charts',
        'flet_shadcn_ui',
        'websockets',
        'certifi',
    ] + yt_dlp_submodules,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

temp_version = 'C:\\Users\\Admin\\AppData\\Local\\Temp\\f94e0259-b790-444e-bfe2-f4b7ea5b3b3b'
version_file = temp_version if os.path.exists(temp_version) else None

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Nu Age',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=version_file,
    icon=[icon_path] if os.path.exists(icon_path) else None,
)
