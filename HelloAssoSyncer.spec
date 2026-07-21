# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\Btarrade\\Documents\\Perso\\Repos\\ACA_HelloAsso\\Syncer\\gui\\styles\\styles.css', 'Syncer/gui/styles'), ('C:\\Users\\Btarrade\\Documents\\Perso\\Repos\\ACA_HelloAsso\\Syncer\\secrets.template.json', 'Syncer'), ('C:\\Users\\Btarrade\\Documents\\Perso\\Repos\\ACA_HelloAsso\\Syncer\\Readme.md', 'Syncer')],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='HelloAssoSyncer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\Btarrade\\Documents\\Perso\\Repos\\ACA_HelloAsso\\Syncer\\assets\\app_icon.png'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HelloAssoSyncer',
)
