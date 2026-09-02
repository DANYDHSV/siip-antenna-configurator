import os
import sys
import subprocess
import shutil

def build():
    print("🛠️ Iniciando proceso de empaquetado...")
    
    # 1. Verificar dependencias
    try:
        import PyInstaller
        print("✅ PyInstaller detectado.")
    except ImportError:
        print("📦 Instalando PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    try:
        import ttkbootstrap
        print("✅ ttkbootstrap detectado.")
    except ImportError:
        print("📦 Instalando ttkbootstrap...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ttkbootstrap"])

    # 2. Definir archivos y recursos
    main_script = "gui_configurador.py"
    backend_script = "configuracion_completa_antenas2.py"
    assets = ["app_manifest.json", "logo.png", "antena.png", "icono.png"]
    
    # 3. Construir comando de PyInstaller
    # --noconsole: No mostrar terminal negra (Windows)
    # --onefile: Empaquetar todo en un solo ejecutable
    # --add-data: Incluir recursos y el script backend
    
    is_windows = sys.platform.startswith('win')
    sep = ';' if is_windows else ':'
    
    cmd = [
        "pyinstaller",
        "--noconsole",
        "--onefile",
        f"--name=ConfiguradorAntenas",
        f"--add-data={backend_script}{sep}.",
    ]
    
    # Agregar assets
    for asset in assets:
        if os.path.exists(asset):
            cmd.append(f"--add-data={asset}{sep}.")
        else:
            print(f"⚠️ Advertencia: Recurso {asset} no encontrado. Se omitirá.")

    # Icono
    if is_windows:
        if os.path.exists("icono.ico"):
            cmd.append("--icon=icono.ico")
    elif sys.platform == 'darwin':
        if os.path.exists("icono.icns"):
            cmd.append("--icon=icono.icns")

    cmd.append(main_script)

    print(f"🚀 Ejecutando comando: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
        print("\n✨ ¡Empaquetado completado exitosamente!")
        print(f"📁 Busca tu aplicación en la carpeta 'dist'")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error durante el empaquetado: {e}")

if __name__ == "__main__":
    build()
