#!/usr/bin/env python3
"""Build the native macOS app/DMG or Windows executable."""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent


def run(command):
    print('$', ' '.join(str(part) for part in command))
    subprocess.check_call(command, cwd=ROOT)


def require_files(names):
    missing = [name for name in names if not (ROOT / name).is_file()]
    if missing:
        raise FileNotFoundError('Faltan recursos: ' + ', '.join(missing))


def clear_macos_metadata(path):
    """Avoid Finder quarantine/resource forks inside the distributable bundle."""
    run(['xattr', '-cr', str(path)])


def build_mac():
    if sys.platform != 'darwin':
        raise RuntimeError('El build macOS debe ejecutarse en macOS.')

    require_files(['logo.png', 'antena.png', 'icono.png', 'icono.icns', 'app_manifest.json'])
    for resource in ('logo.png', 'antena.png', 'icono.png', 'icono.icns', 'app_manifest.json'):
        clear_macos_metadata(ROOT / resource)
    architecture = platform.machine().lower()
    if architecture in ('arm64', 'aarch64'):
        architecture = 'arm64'
    elif architecture in ('x86_64', 'amd64'):
        architecture = 'x86_64'
    else:
        raise RuntimeError(f'Arquitectura macOS no soportada: {platform.machine()}')

    app_path = ROOT / 'dist' / 'ConfiguradorAntenas.app'
    dmg_path = ROOT / 'dist' / f'ConfiguradorAntenas-macOS-{architecture}.dmg'
    run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
         '--distpath', str(ROOT / 'dist'), '--workpath', str(ROOT / 'build' / f'mac-{architecture}'),
         'ConfiguradorAntenas-mac.spec'])
    if not app_path.is_dir():
        raise RuntimeError(f'PyInstaller no generó {app_path}')
    clear_macos_metadata(app_path)
    staging_dir = ROOT / 'build' / f'dmg-{architecture}'
    staging_app = staging_dir / 'ConfiguradorAntenas.app'
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)
    # ditto --norsrc prevents Finder metadata from entering the distributable DMG.
    run(['ditto', '--norsrc', str(app_path), str(staging_app)])
    clear_macos_metadata(staging_app)
    applications_link = staging_dir / 'Applications'
    applications_link.symlink_to('/Applications')
    if dmg_path.exists():
        dmg_path.unlink()
    run(['hdiutil', 'create', '-volname', 'Configurador Antenas',
         '-srcfolder', str(staging_dir), '-ov', '-format', 'UDZO', str(dmg_path)])
    print(f'Generado: {dmg_path}')


def build_windows():
    if sys.platform != 'win32':
        raise RuntimeError('El build Windows debe ejecutarse en Windows.')

    require_files(['logo.png', 'antena.png', 'icono.png', 'app_manifest.json'])
    icon_path = ROOT / 'icono.ico'
    if not icon_path.exists():
        Image.open(ROOT / 'icono.png').save(
            icon_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)]
        )
    run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
         '--distpath', str(ROOT / 'dist'), '--workpath', str(ROOT / 'build' / 'windows'),
         '--icon', str(icon_path), 'ConfiguradorAntenas-win.spec'])
    exe_path = ROOT / 'dist' / 'ConfiguradorAntenas.exe'
    if not exe_path.is_file():
        raise RuntimeError(f'PyInstaller no generó {exe_path}')
    print(f'Generado: {exe_path}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('target', choices=('mac', 'windows'))
    target = parser.parse_args().target
    if target == 'mac':
        build_mac()
    else:
        build_windows()


if __name__ == '__main__':
    main()
