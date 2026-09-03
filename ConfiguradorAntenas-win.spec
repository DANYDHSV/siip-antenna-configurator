# -*- mode: python ; coding: utf-8 -*-

hiddenimports = [
    'selenium.webdriver.chrome.service',
    'selenium.webdriver.chrome.options',
    'webdriver_manager.chrome',
]

a = Analysis(
    ['gui_configurador.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('logo.png', '.'),
        ('antena.png', '.'),
        ('icono.png', '.'),
        ('app_manifest.json', '.'),
    ],
    hiddenimports=hiddenimports,
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
    name='ConfiguradorAntenas',
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
    icon=None,
)
