# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

yt_dlp_submodules = collect_submodules('yt_dlp')
yt_dlp_datas = collect_data_files('yt_dlp')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')] + yt_dlp_datas,
    hiddenimports=['yt_dlp', 'flet_video', 'flet_webview', 'certifi'] + yt_dlp_submodules,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    version='C:\\Users\\Admin\\AppData\\Local\\Temp\\f94e0259-b790-444e-bfe2-f4b7ea5b3b3b',
    icon=['C:\\Users\\Admin\\Desktop\\Code\\NU-Front\\assets\\icon.ico'],
)
