# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    # gui.py importa estos con importlib.import_module("core.xxx")
    # (string dinámico), que el análisis estático de PyInstaller no
    # detecta por su cuenta -hay que declararlos a mano.
    hiddenimports=['core', 'core.system', 'core.project_analyzer', 'core.dev_ai'],
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
    name='DevBox',
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
    icon=['assets/icon/icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DevBox',
)
app = BUNDLE(
    coll,
    name='DevBox.app',
    icon='assets/icon/icon.icns',
    bundle_identifier=None,
)
