#!/usr/bin/env python3
import os
import sys
import threading
import subprocess
import signal
import time
import json
import queue
import importlib

# Verificar e instalar dependencias necesarias
def ensure_gui_dependencies():
    # Primero instalamos dependencias que podemos manejar con pip
    packages = {
        'PIL': 'pillow',  # Para manejo de imágenes
    }
    
    for import_name, pip_name in packages.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"[DEPENDENCIAS] Instalando {pip_name}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            except subprocess.CalledProcessError as e:
                print(f"❌ Error instalando {pip_name}: {e}")
                sys.exit(1)

    # Ahora verificamos tkinter e intentamos instalarlo si es posible
    try:
        import tkinter
        print(f"[DEPENDENCIAS] ✓ tkinter disponible (versión {tkinter.TkVersion})")
        return True
    except ImportError:
        print("\n[DEPENDENCIAS] ❌ tkinter no está disponible.")
        print("\nIntentando instalar tkinter automáticamente...")
        
        try:
            if sys.platform == 'darwin':  # macOS
                if os.path.exists('/opt/homebrew/bin/brew') or os.path.exists('/usr/local/bin/brew'):
                    print("[DEPENDENCIAS] Detectado Homebrew, intentando instalar python-tk...")
                    try:
                        subprocess.check_call(['brew', 'install', 'python-tk'])
                        print("✓ Instalación completada. Por favor, reinicie el script.")
                        sys.exit(0)
                    except subprocess.CalledProcessError:
                        pass
                
            elif sys.platform == 'linux':  # Linux
                # Intentar detectar la distribución
                if os.path.exists('/etc/debian_version'):  # Debian/Ubuntu
                    print("[DEPENDENCIAS] Detectado sistema Debian/Ubuntu")
                    cmd = ['sudo', 'apt-get', 'install', '-y', 'python3-tk']
                elif os.path.exists('/etc/fedora-release'):  # Fedora
                    print("[DEPENDENCIAS] Detectado sistema Fedora")
                    cmd = ['sudo', 'dnf', 'install', '-y', 'python3-tkinter']
                else:
                    cmd = None

                if cmd:
                    print(f"[DEPENDENCIAS] Ejecutando: {' '.join(cmd)}")
                    print("Se solicitará contraseña de administrador...")
                    try:
                        subprocess.check_call(cmd)
                        print("✓ Instalación completada. Por favor, reinicie el script.")
                        sys.exit(0)
                    except subprocess.CalledProcessError:
                        pass
        
        except Exception as e:
            print(f"No se pudo instalar automáticamente: {e}")

        # Si llegamos aquí, no se pudo instalar automáticamente
        print("\n⚠️ No se pudo instalar tkinter automáticamente.")
        print("\nPor favor, instale tkinter manualmente según su sistema operativo:")
        print("\n📝 Instrucciones de instalación:")
        if sys.platform == 'darwin':  # macOS
            print("macOS:")
            print("1. Instale Homebrew desde https://brew.sh si no lo tiene")
            print("2. Ejecute: brew install python-tk")
        elif sys.platform == 'linux':  # Linux
            print("Ubuntu/Debian:")
            print("1. Ejecute: sudo apt-get update")
            print("2. Ejecute: sudo apt-get install python3-tk")
            print("\nFedora:")
            print("1. Ejecute: sudo dnf install python3-tkinter")
            print("\nOtras distribuciones:")
            print("Busque el paquete python3-tk en su gestor de paquetes")
        elif sys.platform == 'win32':  # Windows
            print("Windows:")
            print("1. Desinstale Python (Panel de Control > Programas > Desinstalar)")
            print("2. Descargue Python desde https://www.python.org/downloads/")
            print("3. Durante la instalación, marque la casilla 'tcl/tk and IDLE'")
            print("4. Complete la instalación y reinicie su computadora")
        
        print("\nDespués de instalar tkinter, ejecute este script nuevamente.")
        sys.exit(1)

# Verificar dependencias antes de importar
ensure_gui_dependencies()

# Importar módulos necesarios
# Reorganizado para incluir los nuevos imports y evitar duplicados
import csv
import re
import socket
import webbrowser

# Para la GUI
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from PIL import Image, ImageTk, ImageDraw, ImageChops

import urllib.request
import ssl

# Para redireccionar salida de hilos
import io
from contextlib import contextmanager

def resource_path(relative_path):
    """ Obtiene la ruta absoluta al recurso, funciona para dev y PyInstaller """
    try:
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class QueueRedirector:
    """ Redirecciona stdout a una cola para que la GUI la procese """
    def __init__(self, queue):
        self.queue = queue
    def write(self, string):
        if string and string.strip():
            self.queue.put(('line', string + '\n'))
    def flush(self):
        pass

@contextmanager
def redirect_stdout_to_queue(queue):
    old_stdout = sys.stdout
    sys.stdout = QueueRedirector(queue)
    try:
        yield
    finally:
        sys.stdout = old_stdout

# Importar el backend para ejecución directa (mejor para el empaquetado)
import configuracion_completa_antenas2

SETTINGS_FILE = 'gui_settings.json'
DEFAULT_SETTINGS = {
    'archivo_firmware': os.environ.get('ARCHIVO_LOCAL_FW', 'WA.v8.7.19.48279.250811.0636.bin'),
    'backup_cfg': os.environ.get('BACKUP_CFG', 'WA-28704EB63776.cfg'),
    'range_start': 11,
    'range_end': 18,
    'modo_flujo': 'full'  # 'full' = configurar y actualizar, 'config' = solo configurar
}

class GuiConfig:
    def round_corners(self, image, radius):
        """Redondea las esquinas de una imagen PIL"""
        mask = Image.new('L', image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0) + image.size, radius=radius, fill=255)
        
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
            
        r, g, b, a = image.split()
        # Combinar la máscara con el canal alfa existente
        new_a = ImageChops.multiply(a, mask)
        image.putalpha(new_a)
        return image

    # Eliminar duplicados de run_subprocess fuera de la clase. La versión dentro de la clase es la válida.
    def show_mac_summary(self, macs, success=True):
        """Carga los resultados desde el CSV y los muestra en la tabla"""
        self.load_results_from_csv()
        
        # Cambiar automáticamente a la pestaña de resultados
        if hasattr(self, 'notebook'):
            self.notebook.select(self.tab_resultados)
    
    def load_results_from_csv(self):
        """Carga los resultados desde el archivo CSV y los muestra en la tabla"""
        import csv
        csv_path = os.path.join(os.getcwd(), 'resultados_antenas.csv')
        
        # Limpiar tabla existente
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
            
        self.successful_ips = []
        
        if not os.path.exists(csv_path):
            self.copy_mac_btn.config(state='disabled')
            if hasattr(self, 'open_ips_btn'):
                self.open_ips_btn.pack_forget()
            return
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    count += 1
                    exito_val = str(row.get('exito', '')).lower()
                    exito_bool = exito_val in ['1', 'true', 'yes']
                    estado = "✅ OK" if exito_bool else "❌ ERROR"
                    self.results_tree.insert('', 'end', values=(
                        row.get('ip_inicial', '-'),
                        row.get('ip_final', '-'),
                        row.get('mac', 'No disponible'),
                        estado
                    ))
                    if exito_bool:
                        ip_final = row.get('ip_final')
                        if ip_final and ip_final != '-':
                            self.successful_ips.append(ip_final)
                
                if count > 0:
                    self.copy_mac_btn.config(state='normal')
                else:
                    self.copy_mac_btn.config(state='disabled')
                    
                if self.successful_ips and hasattr(self, 'open_ips_btn'):
                    self.open_ips_btn.pack(side='right', padx=5)
                elif hasattr(self, 'open_ips_btn'):
                    self.open_ips_btn.pack_forget()
        except Exception as e:
            print(f"Error al cargar resultados: {e}")
            self.copy_mac_btn.config(state='disabled')
            if hasattr(self, 'open_ips_btn'):
                self.open_ips_btn.pack_forget()
    def copy_macs_to_clipboard(self):
        """Copia todas las MACs de la tabla al portapapeles"""
        import re
        macs = []
        # Regex flexible para MACs (con o sin dos puntos, 12 caracteres hex)
        mac_regex = re.compile(r'^[0-9a-fA-F]{2}[:\-]?[0-9a-fA-F]{2}[:\-]?[0-9a-fA-F]{2}[:\-]?[0-9a-fA-F]{2}[:\-]?[0-9a-fA-F]{2}[:\-]?[0-9a-fA-F]{2}$')
        mac_simple = re.compile(r'^[0-9a-fA-F]{12}$') # Para formato sin separadores
        
        for item in self.results_tree.get_children():
            values = self.results_tree.item(item)['values']
            if len(values) >= 3:
                mac = str(values[2]).strip()  # La MAC está en la tercera columna
                # Validar que parezca una MAC real y no un mensaje de error
                if (mac_regex.match(mac) or mac_simple.match(mac)) and 'disponible' not in mac.lower() and 'desconocida' not in mac.lower():
                    macs.append(mac)
    
        if macs:
            mac_text = '\n'.join(macs)
            self.root.clipboard_clear()
            self.root.clipboard_append(mac_text)
            self.root.update()
            # Opcional: mostrar mensaje de confirmación
            self.status_var.set(f'Copiadas {len(macs)} MACs al portapapeles')
        else:
            self.status_var.set('No hay MACs válidas para copiar')

    def open_successful_ips(self):
        """Abre todas las IPs exitosas en pestañas del navegador predeterminado"""
        if not hasattr(self, 'successful_ips') or not self.successful_ips:
            return
            
        try:
            for ip in self.successful_ips:
                url = f"https://{ip}"
                webbrowser.open_new_tab(url)
            self.status_var.set(f"Abiertas {len(self.successful_ips)} IPs en el navegador")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el navegador: {e}", parent=self.root)

    def copy_console_log(self):
        """Copia el contenido de la consola al portapapeles"""
        log_text = self.console.get('1.0', 'end').strip()
        if log_text:
            self.root.clipboard_clear()
            self.root.clipboard_append(log_text)
            self.root.update()
            self.status_var.set('Log copiado al portapapeles')
        else:
            self.status_var.set('El log está vacío')

    def update_progress_fraction(self, frac):
        # Solo avanza para la antena en curso (active_idx, nunca suma a completed_antennas aquí)
        self.progress.config(mode='determinate')
        self.progress.stop()
        barra = self.active_idx + frac
        # La barra nunca retrocede: progreso no menor al valor anterior
        if barra > self.progress['value']:
            self.progress['value'] = min(self.total_antennas, barra)
        self.root.update_idletasks()
    def _update_naranja(self):
        self.set_antenna_in_progress()
        self.progress.config(mode='indeterminate')
        self.progress.start(10)  # Valor pequeño, animación visible
    def set_antenna_in_progress(self):
        # Ilumina sólo el punto activo
        # Colores que se ven bien en ambos temas
        inactive_fill = '#505050' if self.dark_mode else '#d0d0d0'
        inactive_outline = '#707070' if self.dark_mode else '#a0a0a0'
        
        for i, canvas in enumerate(self.antenna_points):
            canvas.delete("all")
            if i < self.active_idx:
                canvas.create_oval(2,4,14,16, fill='#14c714', outline='green')
            elif i == self.active_idx:
                canvas.create_oval(2,4,14,16, fill='#ffa500', outline='#b36a00')
            else:
                canvas.create_oval(2,4,14,16, fill=inactive_fill, outline=inactive_outline)

    def __init__(self, root):
        self.root = root
        self.root.title('CONFIGURADOR DE ANTENAS UBIQUITI SIIP INTERNET')
        self.status_var = tk.StringVar(value='Listo')
        self.settings = self.load_settings()
        self.proc = None
        self.proc_thread = None
        self.running = False
        self.queue = queue.Queue()
        self.successful_ips = []
        self.scanned_ips = []
        self.is_retry = False
        self.retry_ips = []
        self.total_antennas = max(1, int(self.settings.get('range_end', 18)) - int(self.settings.get('range_start', 11)) + 1)
        self.completed_antennas = 0
        
        # Dark mode state
        self.dark_mode = self.settings.get('dark_mode', False)
        self.setup_themes()

        self.build_ui()
        # Periodic queue flush
        self.root.after(100, self.flush_queue)
        
        # Apply initial theme
        self.apply_theme()

        # Check for firmware updates in background
        threading.Thread(target=self.check_firmware_updates, daemon=True).start()

    def check_firmware_updates(self):
        """Revisa la API de Ubiquiti en segundo plano para ver si hay una nueva versión."""
        try:
            url = "https://fw-update.ubnt.com/api/firmware?filter=eq~~product~~WA&filter=eq~~channel~~release&sort=-version&limit=1"
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            if '_embedded' in data and 'firmware' in data['_embedded'] and len(data['_embedded']['firmware']) > 0:
                latest_fw = data['_embedded']['firmware'][0]
                latest_version_str = latest_fw.get('version', '') # P.ej. 'v8.7.22'
                download_url = latest_fw.get('_links', {}).get('data', {}).get('href', '')
                
                # Extraer partes de versión online
                m_online = re.search(r'v(\d+)\.(\d+)\.(\d+)', latest_version_str)
                if not m_online or not download_url:
                    return
                version_online = tuple(map(int, m_online.groups()))
                
                # Extraer versión actual seleccionada
                current_fw_file = self.settings.get('archivo_firmware', '')
                m_current = re.search(r'v(\d+)\.(\d+)\.(\d+)', current_fw_file)
                if m_current:
                    version_current = tuple(map(int, m_current.groups()))
                    
                    if version_online > version_current:
                        # Hay nueva versión!
                        # Intentamos extraer el nombre original (tags.fullVersion) si existe,
                        # si no, armamos un nombre estándar para que coincida con el regex del backend
                        full_version = latest_fw.get('tags', {}).get('fullVersion', f"WA.{latest_version_str}.bin")
                        if not full_version.endswith('.bin'):
                            full_version += '.bin'
                            
                        self.root.after(0, self.prompt_firmware_update, latest_version_str, download_url, full_version)
                else:
                    # Si no hay versión parseable definida, asumimos que puede querer actualizar
                    full_version = latest_fw.get('tags', {}).get('fullVersion', f"WA.{latest_version_str}.bin")
                    if not full_version.endswith('.bin'):
                        full_version += '.bin'
                    self.root.after(0, self.prompt_firmware_update, latest_version_str, download_url, full_version)
        except Exception as e:
            print(f"[AUTO-UPDATE] Error verificando firmware: {e}")

    def prompt_firmware_update(self, version_str, download_url, target_filename):
        msg = f"Hay una nueva versión de firmware disponible: {version_str}\n¿Deseas descargarla y configurarla ahora?"
        if messagebox.askyesno("Nueva Versión Disponible", msg, parent=self.root):
            self.download_firmware(download_url, target_filename)

    def download_firmware(self, url, filename):
        dl_window = tk.Toplevel(self.root)
        dl_window.title("Descargando Firmware")
        dl_window.geometry("400x120")
        dl_window.transient(self.root)
        dl_window.grab_set()
        
        # Centrar
        dl_window.geometry(f"+{self.root.winfo_rootx() + 200}+{self.root.winfo_rooty() + 250}")
        
        lbl = ttk.Label(dl_window, text=f"Descargando {filename}...")
        lbl.pack(pady=10)
        
        progress = ttk.Progressbar(dl_window, orient='horizontal', mode='determinate', length=350)
        progress.pack(pady=10)
        
        status_lbl = ttk.Label(dl_window, text="Iniciando...")
        status_lbl.pack()
        
        def reporthook(count, block_size, total_size):
            if total_size > 0:
                percent = int(count * block_size * 100 / total_size)
                # Actualizar barra desde el hilo secundario (root.after es mejor, pero tkinter maneja enteros bien)
                self.root.after(0, progress.config, {'value': min(percent, 100)})
                self.root.after(0, status_lbl.config, {'text': f"{min(percent, 100)}%"})
        
        def _download_worker():
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                # Para evitar error 403 Forbidden, simulamos ser un navegador
                # IMPORTANTE: NO usar install_opener para no contaminar el backend que corre en el mismo proceso
                opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
                opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')]
                
                # Para urlretrieve con un opener personalizado, hay una forma:
                try:
                    urllib.request.install_opener(opener)
                    urllib.request.urlretrieve(url, filename, reporthook=reporthook)
                finally:
                    # Restaurar el opener por defecto inmediatamente para no afectar a esperar_web del backend
                    urllib.request.install_opener(urllib.request.build_opener())

                
                self.root.after(0, dl_window.destroy)
                
                # Actualizar configuración
                self.settings['archivo_firmware'] = filename
                self.save_settings()
                
                self.root.after(0, lambda: messagebox.showinfo("Descarga Completada", f"Firmware actualizado a {filename}. Por favor reinicia o revisa los ajustes.", parent=self.root))
            except Exception as e:
                self.root.after(0, dl_window.destroy)
                self.root.after(0, lambda txt=str(e): messagebox.showerror("Error", f"Fallo al descargar: {txt}", parent=self.root))
                
        threading.Thread(target=_download_worker, daemon=True).start()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return DEFAULT_SETTINGS.copy()

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            messagebox.showwarning('Error', f'No se pudo guardar configuración: {e}')
    
    def setup_themes(self):
        """Define los colores para modo claro y oscuro"""
        self.themes = {
            'light': {
                'bg': '#f0f0f0',
                'fg': 'black',
                'console_bg': '#fafafa',
                'console_fg': 'black',
                'button_bg': '#007AFF',  # Azul estilo App Store
                'button_fg': 'white',
                'status_bg': '#e0e0e0',
                'frame_bg': '#f0f0f0',
                'scrollbar_bg': '#c0c0c0',  # Gris claro para scrollbars
                'scrollbar_trough': '#e8e8e8',
            },
            'dark': {
                'bg': '#2b2b2b',
                'fg': '#e0e0e0',
                'console_bg': '#1e1e1e',
                'console_fg': '#e0e0e0',
                'button_bg': '#007AFF',  # Azul estilo App Store
                'button_fg': 'white',
                'status_bg': '#1e1e1e',
                'frame_bg': '#2b2b2b',
                'scrollbar_bg': '#3a3a3a',  # Gris oscuro para scrollbars
                'scrollbar_trough': '#2b2b2b',
            }
        }
    
    def toggle_theme(self):
        """Alterna entre modo oscuro y claro"""
        self.dark_mode = not self.dark_mode
        self.settings['dark_mode'] = self.dark_mode
        self.save_settings()
        self.apply_theme()
    
    def apply_theme(self):
        """Aplica el tema actual a todos los widgets"""
        theme = self.themes['dark'] if self.dark_mode else self.themes['light']
        
        # Actualizar root
        self.root.configure(bg=theme['bg'])
        
        # Actualizar main_frame
        if hasattr(self, 'main_frame'):
            self.main_frame.configure(bg=theme['bg'])
        
        # Actualizar header_frame
        if hasattr(self, 'header_frame'):
            self.header_frame.configure(bg=theme['bg'])
            for child in self.header_frame.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=theme['bg'], fg=theme['fg'])
        
        # Actualizar logo_theme_frame y logo_label
        if hasattr(self, 'logo_theme_frame'):
            self.logo_theme_frame.configure(bg=theme['bg'])
        if hasattr(self, 'logo_label'):
            self.logo_label.configure(bg=theme['bg'])
        
        # Actualizar frames con LabelFrame
        for frame_attr in ['control_frame', 'antennas_frame', 'log_frame']:
            if hasattr(self, frame_attr):
                frame = getattr(self, frame_attr)
                frame.configure(bg=theme['frame_bg'], fg=theme['fg'])
        
        # Actualizar btn_container
        if hasattr(self, 'btn_container'):
            self.btn_container.configure(bg=theme['frame_bg'])
        
        # El start_btn es ttk.Button y usa estilos, no necesita actualización aquí
        
        # Actualizar botón de tema
        if hasattr(self, 'theme_btn'):
            icon = '🌙' if not self.dark_mode else '☀️'
            self.theme_btn.configure(text=icon, bg=theme['button_bg'], fg=theme['button_fg'])

        # Actualizar botón de ajustes
        if hasattr(self, 'settings_btn'):
            # ttk.Button no usa bg/fg directamente, sino estilos.
            # Si se usa un estilo, se actualiza el estilo.
            # Para este botón específico, se mantiene el estilo "Blue.TButton"
            # y se asume que el estilo ya maneja los colores.
            # Si se necesita cambiar el color dinámicamente, se debería reconfigurar el estilo.
            # Por ahora, no se hace nada aquí ya que el estilo "Blue.TButton" es fijo.
            pass
        
        # Actualizar icons_container
        if hasattr(self, 'icons_container'):
            self.icons_container.configure(bg=theme['frame_bg'])
        
        # Actualizar antenna points
        if hasattr(self, 'antenna_points'):
            for canvas in self.antenna_points:
                canvas.configure(bg=theme['frame_bg'], highlightthickness=0)
        
        # Actualizar antenna icons labels
        if hasattr(self, 'antenna_icons'):
            for label in self.antenna_icons:
                label.configure(bg=theme['frame_bg'])
        
        # Actualizar consola y su scrollbar
        if hasattr(self, 'console'):
            self.console.configure(bg=theme['console_bg'], fg=theme['console_fg'], 
                                  insertbackground=theme['console_fg'])
            # Configurar scrollbar de la consola
            try:
                # ScrolledText tiene un scrollbar vertical interno
                vbar = self.console.vbar if hasattr(self.console, 'vbar') else None
                if vbar:
                    vbar.configure(bg=theme.get('scrollbar_bg', theme['console_bg']), 
                                 troughcolor=theme.get('scrollbar_trough', theme['console_bg']),
                                 activebackground=theme.get('scrollbar_bg', theme['fg']),
                                 highlightthickness=0, borderwidth=0)
            except:
                pass
        
        # Actualizar status bar
        if hasattr(self, 'status_bar'):
            self.status_bar.configure(bg=theme['status_bg'])
            for child in self.status_bar.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=theme['status_bg'], fg=theme['fg'])
        
        # Actualizar pestañas (notebook y tabs)
        if hasattr(self, 'notebook'):
            # El notebook de ttk se estiliza diferente
            pass
        
        if hasattr(self, 'tab_proceso'):
            self.tab_proceso.configure(bg=theme['bg'])
        
        # Actualizar log_frame y sus hijos
        if hasattr(self, 'log_frame'):
            self.log_frame.configure(bg=theme['frame_bg'], fg=theme['fg'])
            if hasattr(self, 'log_tools_frame'):
                self.log_tools_frame.configure(bg=theme['frame_bg'])
            if hasattr(self, 'copy_log_btn'):
                # Usar estilo nativo (ttk.Button en macOS maneja mejor el contraste sin bg/fg directo)
                pass

        if hasattr(self, 'tab_resultados'):
            self.tab_resultados.configure(bg=theme['bg'])
            # Actualizar todos los frames dentro de la pestaña de resultados
            for child in self.tab_resultados.winfo_children():
                if isinstance(child, tk.Frame):
                    child.configure(bg=theme['bg'])
                    for subchild in child.winfo_children():
                        if isinstance(subchild, tk.Frame):
                            subchild.configure(bg=theme['bg'])
                        elif isinstance(subchild, tk.Label):
                            subchild.configure(bg=theme['bg'], fg=theme['fg'])
                        elif isinstance(subchild, tk.Button):
                            pass # Eran para los botones antiguos tk.Button, ahora usamos ttk.Button
        
        # Actualizar estilo del Treeview (tabla de resultados)
        if hasattr(self, 'results_tree'):
            treeview_style = 'Dark.Treeview' if self.dark_mode else 'Light.Treeview'
            self.results_tree.configure(style=treeview_style)

    def build_ui(self):
        # Configurar estilos
        style = ttk.Style()
        style.theme_use('clam')  # 'clam' suele permitir más personalización de colores
        
        # Estilo para la barra de progreso (más ancha y verde)
        style.configure("Green.Horizontal.TProgressbar",
                        thickness=30,
                        troughcolor='#E0E0E0',
                        background='#4CAF50',
                        borderwidth=0)
        
        # Estilo para botones azules (App Store style)
        style.configure("Blue.TButton",
                       background='#007AFF',
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       relief='flat',
                       padding=(20, 10))
        style.map("Blue.TButton",
                 background=[('active', '#0051D5'), ('pressed', '#0051D5'), ('disabled', '#d0d0d0')],
                 foreground=[('active', 'white'), ('pressed', 'white'), ('disabled', '#a0a0a0')])
        
        # Estilos para Treeview (tabla de resultados)
        # Estilo claro
        style.configure("Light.Treeview",
                       background='#fafafa',
                       foreground='black',
                       fieldbackground='#fafafa',
                       borderwidth=0)
        style.configure("Light.Treeview.Heading",
                       background='#e0e0e0',
                       foreground='black',
                       relief='flat')
        style.map("Light.Treeview.Heading",
                 background=[('active', '#d0d0d0')])
        
        # Estilo oscuro
        style.configure("Dark.Treeview",
                       background='#1e1e1e',
                       foreground='#e0e0e0',
                       fieldbackground='#1e1e1e',
                       borderwidth=0)
        style.configure("Dark.Treeview.Heading",
                       background='#2b2b2b',
                       foreground='#e0e0e0',
                       relief='flat')
        style.map("Dark.Treeview.Heading",
                 background=[('active', '#3a3a3a')])
        
        # Guardar referencia al estilo para poder cambiarlo después
        self.style = style
        
        # Fuentes
        # Fuentes (Aumentadas)
        self.header_font = ('Segoe UI', 18, 'bold') if os.name == 'nt' else ('Helvetica', 18, 'bold')
        self.normal_font = ('Segoe UI', 11) if os.name == 'nt' else ('Helvetica', 11)
        self.bold_font = ('Segoe UI', 12, 'bold') if os.name == 'nt' else ('Helvetica', 12, 'bold')

        # --- Menú ---
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label='Ajustes', command=self.open_settings)
        filemenu.add_separator()
        filemenu.add_command(label='Salir', command=self.on_exit)
        menubar.add_cascade(label='Archivo', menu=filemenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label='Acerca de', command=self.about)
        menubar.add_cascade(label='Ayuda', menu=helpmenu)
        self.root.config(menu=menubar)

        # --- Contenedor Principal ---
        self.main_frame = tk.Frame(self.root, bg='#f0f0f0')
        self.main_frame.pack(fill='both', expand=True)
        self.root.configure(bg='#f0f0f0')

        # --- Header (Logo + Título) ---
        self.header_frame = tk.Frame(self.main_frame, bg='#f0f0f0')
        self.header_frame.pack(fill='x', pady=(20, 10), padx=20)

        # Logo y botón de tema en la misma fila
        self.logo_theme_frame = tk.Frame(self.header_frame, bg='#f0f0f0')
        self.logo_theme_frame.pack(fill='x')
        
        # Logo (centrado)
        logo_path = resource_path('logo.png')
        if os.path.exists(logo_path):
            try:
                logo_image = Image.open(logo_path)
                logo_image = logo_image.resize((200, 100), Image.LANCZOS)
                
                # Redondear esquinas
                try:
                    logo_image = self.round_corners(logo_image, 15)
                except Exception as e:
                    print(f"Error redondeando logo: {e}")
                
                logo_photo = ImageTk.PhotoImage(logo_image)
                self.logo_label = tk.Label(self.logo_theme_frame, image=logo_photo, bg='#f0f0f0')
                self.logo_label.image = logo_photo
                self.logo_label.pack(side='top', pady=(0, 10))
            except Exception:
                pass
        
        # Botón de tema (esquina superior derecha)
        self.theme_btn = tk.Button(self.logo_theme_frame, text='🌙', font=('Segoe UI', 16), 
                                   command=self.toggle_theme, width=3, height=1,
                                   bg='#007AFF', fg='white', cursor='hand2',
                                   relief='flat', borderwidth=0,
                                   activebackground='#0051D5', activeforeground='white',
                                   highlightbackground='#007AFF', highlightcolor='#007AFF')
        self.theme_btn.place(relx=1.0, rely=0.0, anchor='ne')

        # Botón de ajustes (al lado del botón de tema)
        self.settings_btn = tk.Button(self.logo_theme_frame, text='⚙️', font=('Segoe UI', 16), 
                                   command=self.open_settings, width=3, height=1,
                                   bg='#007AFF', fg='white', cursor='hand2',
                                   relief='flat', borderwidth=0,
                                   activebackground='#0051D5', activeforeground='white',
                                   highlightbackground='#007AFF', highlightcolor='#007AFF')
        self.settings_btn.place(relx=1.0, rely=0.0, x=-50, anchor='ne')

        # Título
        title = tk.Label(self.header_frame, text='CONFIGURADOR DE ANTENAS UBIQUITI SIIP INTERNET', 
                        font=self.header_font, bg='#f0f0f0', fg='#333333')
        title.pack(side='top')

        # --- Notebook (Pestañas) ---
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill='both', expand=True, padx=20, pady=(0, 10))
        
        # --- Pestaña 1: Proceso ---
        self.tab_proceso = tk.Frame(self.notebook, bg='#f0f0f0')
        self.notebook.add(self.tab_proceso, text='  Proceso  ')
        
        # --- Área de Control (Botón + Progreso) ---
        self.control_frame = tk.LabelFrame(self.tab_proceso, text="Control de Proceso", font=self.bold_font, bg='#f0f0f0', fg='black', padx=15, pady=15)
        self.control_frame.pack(fill='x', padx=20, pady=10)

        # Contenedor para centrar el botón
        self.btn_container = tk.Frame(self.control_frame, bg='#f0f0f0')
        self.btn_container.pack(fill='x', pady=(0, 15))
        
        self.start_btn = ttk.Button(self.btn_container, text='Iniciar proceso de configuración', 
                                   style='Blue.TButton',
                                   command=self.toggle_process, cursor='hand2')
        self.start_btn.pack(anchor='center', pady=10)

        # Progress bar customizada
        self.progress = ttk.Progressbar(self.control_frame, orient='horizontal', mode='determinate', style="Green.Horizontal.TProgressbar")
        self.progress['maximum'] = self.total_antennas
        self.progress['value'] = 0
        self.progress.pack(fill='x')

        # --- Área de Estado Visual (Iconos) ---
        self.antennas_frame = tk.LabelFrame(self.tab_proceso, text="Estado de Antenas", font=self.bold_font, bg='#f0f0f0', fg='black', padx=15, pady=15)
        self.antennas_frame.pack(fill='x', padx=20, pady=10)
        
        # Contenedor interno para centrar los iconos
        self.icons_container = tk.Frame(self.antennas_frame, bg='#f0f0f0')
        self.icons_container.pack(anchor='center')
        
        self.antenna_icons = []
        self.antenna_points = []
        
        # Cargar imágenes
        antenna_path = resource_path('antena.png')
        try:
            img = Image.open(antenna_path).convert("RGBA")
            img_normal = img.resize((48, 48), Image.LANCZOS)
            img_gray = img.convert('LA').convert("RGBA").resize((48, 48), Image.LANCZOS)
            self.antenna_photo_normal = ImageTk.PhotoImage(img_normal)
            self.antenna_photo_fail = ImageTk.PhotoImage(img_gray)
        except Exception:
            self.antenna_photo_normal = None
            self.antenna_photo_fail = None
            
        self.init_antenna_icons()

        # --- Consola y Logs ---
        # --- Consola y Logs ---
        self.log_frame = tk.LabelFrame(self.tab_proceso, text="Registro de Actividad", font=self.bold_font, bg='#f0f0f0', fg='black', padx=10, pady=10)
        self.log_frame.pack(fill='both', expand=True, padx=20, pady=(0, 10))

        # Toolbar para el log
        self.log_tools_frame = tk.Frame(self.log_frame, bg='#f0f0f0')
        self.log_tools_frame.pack(fill='x', pady=(0, 5))
        self.copy_log_btn = ttk.Button(self.log_tools_frame, text='Copiar Log', command=self.copy_console_log)
        self.copy_log_btn.pack(side='right')

        self.console = ScrolledText(self.log_frame, height=10, wrap='word', font=('Consolas', 9), bg='#fafafa', fg='black')
        self.console.pack(fill='both', expand=True)
        self.console.configure(state='disabled')

        # --- Pestaña 2: Resultados ---
        self.tab_resultados = tk.Frame(self.notebook, bg='#f0f0f0')
        self.notebook.add(self.tab_resultados, text='  Resultados  ')
        
        # Frame para resultados
        results_container = tk.Frame(self.tab_resultados, bg='#f0f0f0')
        results_container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Título y botón de copiar
        header_frame = tk.Frame(results_container, bg='#f0f0f0')
        header_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(header_frame, text='Resultados del Proceso', font=self.bold_font, bg='#f0f0f0', fg='black').pack(side='left')
        self.copy_mac_btn = ttk.Button(header_frame, text='Copiar MACs', command=self.copy_macs_to_clipboard, state='disabled')
        self.copy_mac_btn.pack(side='right')
        self.open_ips_btn = ttk.Button(header_frame, text='Abrir IPs Exitosas 🌐', command=self.open_successful_ips)
        
        # Tabla de resultados con Treeview
        table_frame = tk.Frame(results_container, bg='#f0f0f0')
        table_frame.pack(fill='both', expand=True)
        
        # Definir columnas
        columns = ('ip_inicial', 'ip_final', 'mac', 'estado')
        self.results_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15, style='Light.Treeview')
        
        # Configurar encabezados
        self.results_tree.heading('ip_inicial', text='IP Inicial')
        self.results_tree.heading('ip_final', text='IP Final')
        self.results_tree.heading('mac', text='MAC')
        self.results_tree.heading('estado', text='Estado')
        
        # Configurar anchos de columnas
        self.results_tree.column('ip_inicial', width=150, anchor='center')
        self.results_tree.column('ip_final', width=150, anchor='center')
        self.results_tree.column('mac', width=200, anchor='center')
        self.results_tree.column('estado', width=120, anchor='center')
        
        # Scrollbar para la tabla
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        
        self.results_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # --- Barra de Estado Inferior ---
        self.status_bar = tk.Frame(self.root, bg='#e0e0e0', height=25)
        self.status_bar.pack(side='bottom', fill='x')
        
        status = tk.Label(self.status_bar, textvariable=self.status_var, bg='#e0e0e0', font=('Segoe UI', 9), anchor='w', padx=10)
        status.pack(side='left')

        # Botón de Test de Conexión (Ping Scan)
        self.test_conn_btn = ttk.Button(self.status_bar, text='Test de Conexión', 
                                       style='Blue.TButton', command=self.run_connectivity_test, cursor='hand2')
        self.test_conn_btn.pack(side='right', padx=10, pady=2)

    def init_antenna_icons(self):
        self.progress['maximum'] = self.total_antennas
        self.progress['value'] = 0
        self.completed_antennas = 0
        self.active_idx = 0 # Reset al iniciar proceso visual
        for w in getattr(self, 'antenna_icons', []):
            w.destroy()
        for w in getattr(self, 'antenna_points', []):
            w.destroy()
        self.antenna_icons = []
        self.antenna_points = []
        
        # Usar icons_container en lugar de antennas_frame directo
        target_frame = getattr(self, 'icons_container', self.antennas_frame)
        
        # Colores que se ven bien en ambos temas
        inactive_fill = '#505050' if self.dark_mode else '#d0d0d0'
        inactive_outline = '#707070' if self.dark_mode else '#a0a0a0'
        theme = self.themes['dark'] if self.dark_mode else self.themes['light']
        
        max_icons = min(self.total_antennas, 8)
        for i in range(max_icons):
            lbl = tk.Label(target_frame, image=self.antenna_photo_normal, bg=theme['frame_bg'])
            lbl.grid(row=0, column=i, padx=8)
            self.antenna_icons.append(lbl)
            cnv = tk.Canvas(target_frame, width=16, height=18, highlightthickness=0, bg=theme['frame_bg'])
            cnv.create_oval(2,4,14,16, fill=inactive_fill, outline=inactive_outline)
            cnv.grid(row=1, column=i)
            self.antenna_points.append(cnv)

    def update_antenna_icon(self, estado):
        i = getattr(self, 'active_idx', 0)
        if 0 <= i < len(self.antenna_points):
            canvas = self.antenna_points[i]
            if estado == "ok":
                # Siempre rellena barra a 100% antes de pasar
                self.update_progress_fraction(1.0)
                self.antenna_icons[i]['image'] = self.antenna_photo_normal
                canvas.delete("all")
                canvas.create_oval(2,4,14,16, fill='#14c714', outline='green')
                self.active_idx += 1
            elif estado == "fail":
                self.update_progress_fraction(1.0)
                self.antenna_icons[i]['image'] = self.antenna_photo_fail
                canvas.delete("all")
                canvas.create_oval(2,4,14,16, fill='#fa1e1e', outline='darkred')
                self.active_idx += 1
            else:
                # Colores que se ven bien en ambos temas
                inactive_fill = '#505050' if self.dark_mode else '#d0d0d0'
                inactive_outline = '#707070' if self.dark_mode else '#a0a0a0'
                self.antenna_icons[i]['image'] = self.antenna_photo_normal
                canvas.delete("all")
                canvas.create_oval(2,4,14,16, fill=inactive_fill, outline=inactive_outline)
            self.root.update_idletasks()

    def _update_naranja_for_index(self, index):
        self.set_antenna_in_progress_by_index(index)
        self.progress.config(mode='indeterminate')
        self.progress.start(10)

    def set_antenna_in_progress_by_index(self, index):
        if 0 <= index < len(self.antenna_points):
            canvas = self.antenna_points[index]
            canvas.delete("all")
            canvas.create_oval(2,4,14,16, fill='#ffa500', outline='#b36a00')
            self.root.update_idletasks()

    def update_antenna_icon_by_index(self, index, estado):
        if 0 <= index < len(self.antenna_points):
            canvas = self.antenna_points[index]
            # Detener animación indeterminada
            self.progress.config(mode='determinate')
            self.progress.stop()
            if estado == "ok":
                self.antenna_icons[index]['image'] = self.antenna_photo_normal
                canvas.delete("all")
                canvas.create_oval(2,4,14,16, fill='#14c714', outline='green')
            elif estado == "fail":
                self.antenna_icons[index]['image'] = self.antenna_photo_fail
                canvas.delete("all")
                canvas.create_oval(2,4,14,16, fill='#fa1e1e', outline='darkred')
            self.root.update_idletasks()


    def open_settings(self):
        # Evita ventana doble de ajustes
        if hasattr(self, 'ajustes_window') and self.ajustes_window is not None and self.ajustes_window.winfo_exists():
            self.ajustes_window.lift()
            self.ajustes_window.focus_set()
            return
        win = tk.Toplevel(self.root)
        win.title('Ajustes')
        win.transient(self.root)
        self.ajustes_window = win

        tk.Label(win, text='Archivo firmware:').grid(row=0, column=0, sticky='e', padx=5, pady=5)
        firmware_var = tk.StringVar(value=self.settings.get('archivo_firmware', ''))
        fw_entry = tk.Entry(win, textvariable=firmware_var, width=60)
        fw_entry.grid(row=0, column=1, padx=5, pady=5)
        tk.Button(win, text='Seleccionar...', command=lambda: self.select_firmware(firmware_var)).grid(row=0, column=2, padx=5, pady=5)

        tk.Label(win, text='Backup .cfg:').grid(row=1, column=0, sticky='e', padx=5, pady=5)
        backup_var = tk.StringVar(value=self.settings.get('backup_cfg', ''))
        backup_entry = tk.Entry(win, textvariable=backup_var, width=60)
        backup_entry.grid(row=1, column=1, padx=5, pady=5)
        tk.Button(win, text='Seleccionar...', command=lambda: self.select_backup(backup_var)).grid(row=1, column=2, padx=5, pady=5)

        tk.Label(win, text='Rango inicio (octeto):').grid(row=2, column=0, sticky='e', padx=5, pady=5)
        start_var = tk.IntVar(value=self.settings.get('range_start', 11))
        tk.Entry(win, textvariable=start_var, width=10).grid(row=2, column=1, sticky='w', padx=5, pady=5)
        
        # Rango específico para Test
        tk.Label(win, text='Rango Test (Ping):', fg='#28a745').grid(row=2, column=2, sticky='e', padx=5)
        test_start_var = tk.IntVar(value=self.settings.get('range_start_test', 11))
        test_end_var = tk.IntVar(value=self.settings.get('range_end_test', 18))
        
        tf = tk.Frame(win)
        tf.grid(row=2, column=3, sticky='w')
        tk.Entry(tf, textvariable=test_start_var, width=5).pack(side='left')
        tk.Label(tf, text='-').pack(side='left')
        tk.Entry(tf, textvariable=test_end_var, width=5).pack(side='left')

        tk.Label(win, text='Rango fin (octeto):').grid(row=3, column=0, sticky='e', padx=5, pady=5)
        end_var = tk.IntVar(value=self.settings.get('range_end', 18))
        tk.Entry(win, textvariable=end_var, width=10).grid(row=3, column=1, sticky='w', padx=5, pady=5)

        # Rango específico para Update Only
        tk.Label(win, text='Rango Act. (Update Only):', fg='#007AFF').grid(row=3, column=2, sticky='e', padx=5)
        update_start_var = tk.IntVar(value=self.settings.get('range_start_update', 11))
        update_end_var = tk.IntVar(value=self.settings.get('range_end_update', 18))
        
        uf = tk.Frame(win)
        uf.grid(row=3, column=3, sticky='w')
        tk.Entry(uf, textvariable=update_start_var, width=5).pack(side='left')
        tk.Label(uf, text='-').pack(side='left')
        tk.Entry(uf, textvariable=update_end_var, width=5).pack(side='left')

        modo_frame = tk.Frame(win)
        modo_frame.grid(row=4, column=0, columnspan=3, pady=8, sticky='w')
        tk.Label(modo_frame, text='Modo de operación:').pack(side='left', padx=3)
        modo_var = tk.StringVar(value=self.settings.get('modo_flujo', 'full'))
        tk.Radiobutton(modo_frame, text='Configurar y actualizar', variable=modo_var, value='full').pack(side='left')
        tk.Radiobutton(modo_frame, text='Sólo configurar', variable=modo_var, value='config').pack(side='left')
        tk.Radiobutton(modo_frame, text='Sólo actualizar', variable=modo_var, value='update_only').pack(side='left')

        def apply_and_close():
            self.settings['archivo_firmware'] = firmware_var.get()
            self.settings['backup_cfg'] = backup_var.get()
            self.settings['modo_flujo'] = modo_var.get()
            try:
                self.settings['range_start'] = int(start_var.get())
                self.settings['range_end'] = int(end_var.get())
                self.settings['range_start_update'] = int(update_start_var.get())
                self.settings['range_end_update'] = int(update_end_var.get())
                self.settings['range_start_test'] = int(test_start_var.get())
                self.settings['range_end_test'] = int(test_end_var.get())
            except Exception:
                messagebox.showwarning('Error', 'Rango inválido')
                return
            self.save_settings()
            
            # Recalcular total_antennas según el modo seleccionado
            if self.settings['modo_flujo'] == 'update_only':
                start = self.settings['range_start_update']
                end = self.settings['range_end_update']
            else:
                start = self.settings['range_start']
                end = self.settings['range_end']
                
            self.total_antennas = max(1, end - start + 1)
            self.progress['maximum'] = self.total_antennas
            win.destroy()
            self.ajustes_window = None

        def on_close():
            self.ajustes_window = None
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)

        btn_frame = tk.Frame(win)
        btn_frame.grid(row=10, column=0, columnspan=3, pady=10)
        tk.Button(btn_frame, text='Guardar', command=apply_and_close).pack(side='left', padx=5)
        tk.Button(btn_frame, text='Cancelar', command=win.destroy).pack(side='left', padx=5)

    def select_firmware(self, var):
        path = filedialog.askopenfilename(title='Seleccionar firmware', filetypes=[('BIN files', '*.bin'), ('All files','*.*')])
        if path:
            var.set(path)

    def select_backup(self, var):
        path = filedialog.askopenfilename(title='Seleccionar backup .cfg', filetypes=[('CFG files', '*.cfg'), ('All files','*.*')])
        if path:
            var.set(path)

    def about(self):
        messagebox.showinfo('Acerca de', 'Autor: Daniel Humberto Soto Villegas (2025)\nEmpresa: SIIP INTERNET')

    def on_exit(self):
        if self.running:
            if not messagebox.askyesno('Confirmar', 'Hay un proceso en ejecución. ¿Deseas salir y cancelar el proceso?'):
                return
            self.request_cancel()
        self.root.quit()

    def toggle_process(self):
        if not self.running:
            self.start_process()
        else:
            # Ask for confirmation to cancel
            if messagebox.askyesno('Confirmar cancelación', '¿Deseas realmente cancelar el proceso?'):
                self.request_cancel()

    def append_console(self, text):
        self.console.configure(state='normal')
        self.console.insert('end', text)
        self.console.see('end')
        self.console.configure(state='disabled')

    def flush_queue(self):
        try:
            while True:
                item = self.queue.get_nowait()
                typ, data = item
                if typ == 'line':
                    # Filtrar etiquetas internas de la GUI para que no salgan en la consola
                    if '[GUI]' not in data:
                        self.append_console(data)
                    # Parsear siempre, incluso si no se muestra
                    self.parse_progress(data)
                elif typ == 'finished':
                    self.append_console('\nProceso finalizado.\n')
                    self.on_process_finished()
                elif typ == 'error':
                    self.append_console(f'\nERROR: {data}\n')
                elif typ == 'finished_test':
                    self.status_var.set('Test de conexión finalizado.')
                    self.running = False
                    self.toggle_inputs(True)
                    self.test_conn_btn.config(state='normal')
                    self.start_btn.config(state='normal') # Asegurar que el botón de inicio vuelva a la normalidad
        except queue.Empty:
            pass
        self.root.after(100, self.flush_queue)

    def get_ip_inicial_from_final(self, ip_final):
        # 1. Si ip_final ya está en scanned_ips, es que ya es la ip inicial (o son iguales)
        if hasattr(self, 'scanned_ips') and ip_final in self.scanned_ips:
            return ip_final
            
        # 2. Buscar en el CSV la fila correspondiente
        csv_path = os.path.join(os.getcwd(), 'resultados_antenas.csv')
        if os.path.exists(csv_path):
            try:
                import csv
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Si coincide por ip_final, retornamos su ip_inicial
                        if row.get('ip_final') == ip_final:
                            ip_init = row.get('ip_inicial')
                            if ip_init:
                                return ip_init
            except Exception as e:
                print(f"[DEBUG] Error mapeando ip_final a inicial por CSV: {e}")
                
        # 3. Fallback matemático por si no está en el CSV
        try:
            octetos = ip_final.split('.')
            octeto_final = int(octetos[-1])
            # Si el octeto inicial era octeto_final + 10 (rango 11-18)
            octeto_inicial = octeto_final + 10
            ip_inicial_fallback = f"{'.'.join(octetos[:-1])}.{octeto_inicial}"
            return ip_inicial_fallback
        except Exception:
            pass
            
        return ip_final

    def parse_progress(self, line):
        # Detectar inicio de antena (opcional, para debug o validación)
        if '[GUI] START_ANTENNA:' in line:
            # Resetear fase actual para esta antena
            self.current_phase = None
            self.current_phase_progress = 0
            try:
                ip = line.split(':', 1)[1].strip()
                mapped_ip = self.get_ip_inicial_from_final(ip)
                if hasattr(self, 'scanned_ips') and mapped_ip in self.scanned_ips:
                    idx = self.scanned_ips.index(mapped_ip)
                    self.active_idx = idx
                    self._update_naranja_for_index(idx)
                else:
                    self._update_naranja()
            except Exception as e:
                print(f"Error parsing START_ANTENNA: {e}")
                self._update_naranja()
            
        # Detectar fin de antena con estado explícito
        if '[GUI] END_ANTENNA:' in line:
            try:
                parts = line.split(':', 1)[1].strip().split(',')
                if len(parts) >= 2:
                    ip = parts[0].strip()
                    status = parts[1].strip()
                    
                    mapped_ip = self.get_ip_inicial_from_final(ip)
                    if hasattr(self, 'scanned_ips') and mapped_ip in self.scanned_ips:
                        idx = self.scanned_ips.index(mapped_ip)
                        self.update_antenna_icon_by_index(idx, status)
                    else:
                        self.update_antenna_icon(status)
                    
                    self.completed_antennas += 1
                    self.progress['value'] = self.completed_antennas
                    self.status_var.set(f'Antenas completadas: {self.completed_antennas}/{self.total_antennas}')
            except Exception as e:
                print(f"Error parsing END_ANTENNA: {e}")

        # Parse [GUI] PHASE_PROGRESS: <phase_name>, <percentage>
        if '[GUI] PHASE_PROGRESS:' in line:
            try:
                content = line.split(':', 1)[1].strip()
                parts = content.split(',')
                if len(parts) >= 2:
                    phase_name = parts[0].strip()
                    phase_percent = int(parts[1].strip())
                    
                    # Definir pesos de cada fase según el modo
                    # Estos pesos suman 100% para una antena completa
                    if hasattr(self, 'settings') and self.settings.get('modo_flujo') == 'config':
                        # Modo solo configurar (sin actualización)
                        phase_weights = {
                            'detection': (0, 10),      # 0-10%
                            'web_config': (10, 40),    # 10-40%  (no se usa en config, pero por si acaso)
                            'ssh_config': (40, 70),    # 40-70%
                            'reboot': (70, 100)        # 70-100%
                        }
                    else:
                        # Modo full (configurar y actualizar)
                        phase_weights = {
                            'detection': (0, 5),           # 0-5%
                            'web_config': (5, 20),         # 5-20%
                            'ssh_config': (20, 35),        # 20-35%
                            'reboot': (35, 45),            # 35-45%
                            'firmware_update': (45, 100)   # 45-100%
                        }
                    
                    if phase_name in phase_weights:
                        start_percent, end_percent = phase_weights[phase_name]
                        # Calcular progreso dentro de esta antena
                        antenna_progress = start_percent + (phase_percent / 100.0) * (end_percent - start_percent)
                        
                        # Calcular progreso total
                        total_progress = self.completed_antennas + (antenna_progress / 100.0)
                        self.progress['value'] = min(self.total_antennas, total_progress)
                        
                        # Actualizar estado
                        phase_names_es = {
                            'detection': 'Detectando',
                            'web_config': 'Configurando web',
                            'ssh_config': 'Configurando SSH',
                            'reboot': 'Reiniciando',
                            'firmware_update': 'Actualizando firmware'
                        }
                        phase_display = phase_names_es.get(phase_name, phase_name)
                        self.status_var.set(f'{phase_display} ({int(antenna_progress)}%)')
            except Exception as e:
                print(f"Error parsing PHASE_PROGRESS: {e}")

        # Parse [GUI] PROGRESS: <seconds_remaining> (legacy, para compatibilidad)
        if '[GUI] PROGRESS:' in line:
            try:
                parts = line.split(':', 1)[1].strip()
                rem = int(parts)
                # Este tag ahora es redundante con PHASE_PROGRESS, pero lo mantenemos por si acaso
                # No hacemos nada aquí porque PHASE_PROGRESS ya maneja el progreso
            except Exception:
                pass

        # Detectar lista de IPs para ajustar el número de iconos
        if 'IPs activas encontradas:' in line:
            try:
                # Esperamos algo como: IPs activas encontradas: ['192.168.1.12', '192.168.1.13']
                content = line.split(':', 1)[1].strip()
                # Limpieza básica para evaluar la lista
                import ast
                ips = ast.literal_eval(content)
                if isinstance(ips, list) and len(ips) > 0:
                    if not getattr(self, 'is_retry', False):
                        self.total_antennas = len(ips)
                        self.scanned_ips = ips
                        # Re-inicializar iconos en el hilo principal
                        self.root.after(0, self.init_antenna_icons)
            except Exception as e:
                print(f"Error parsing IPs: {e}")

    def toggle_inputs(self, enable):
        state = 'normal' if enable else 'disabled'
        self.start_btn.config(state=state)
        # Menú de archivo
        try:
            # Índice 0 es 'Archivo', dentro de ese 'Ajustes' es índice 0
            # Esto es complejo en tkinter nativo si no guardamos referencia al item
            pass
        except:
            pass
        
        # Botón de test
        if hasattr(self, 'test_conn_btn'):
            self.test_conn_btn.config(state=state)

    def start_process(self):
        # Save settings before starting
        self.save_settings()
        self.cancel_requested = False
        configuracion_completa_antenas2.cancel_requested = False
        self.successful_ips = []
        self.is_retry = False
        self.retry_ips = []
        if hasattr(self, 'open_ips_btn'):
            self.open_ips_btn.pack_forget()
        self.console.configure(state='normal')
        self.console.delete('1.0', 'end')
        self.console.configure(state='disabled')
        self.progress.configure(mode='determinate')
        self.progress['maximum'] = self.total_antennas
        self.progress['value'] = 0
        self.completed_antennas = 0
        self.active_idx = 0
        self.start_btn.config(text='Cancelar proceso')
        
        self.running = True
        self.status_var.set('Ejecutando...')
        
        # Deshabilitar botón de test durante la ejecución principal
        if hasattr(self, 'test_conn_btn'):
            self.test_conn_btn.config(state='disabled')
            
        # Launch thread
        self.proc_thread = threading.Thread(target=self.run_subprocess, daemon=True)
        self.proc_thread.start()


    def run_subprocess(self):
        """Ejecuta la lógica del backend directamente en un hilo secundario."""
        # Preparar variables de entorno (el backend las lee de os.environ)
        os.environ['ARCHIVO_LOCAL_FW'] = self.settings.get('archivo_firmware', '')
        os.environ['BACKUP_CFG'] = self.settings.get('backup_cfg', '')
        
        is_retry_run = getattr(self, 'is_retry', False)
        retry_ips = getattr(self, 'retry_ips', None)
        
        if is_retry_run and retry_ips:
            os.environ['MODO_FLUJO'] = 'update_only'
        else:
            os.environ['MODO_FLUJO'] = self.settings.get('modo_flujo', 'full')
        
        # Enviar rango correcto según el modo
        if os.environ['MODO_FLUJO'] == 'update_only':
            r_start = int(self.settings.get('range_start_update', 11))
            r_end = int(self.settings.get('range_end_update', 18))
        else:
            r_start = int(self.settings.get('range_start', 11))
            r_end = int(self.settings.get('range_end', 18))
            
        os.environ['RANGE_START'] = str(r_start)
        os.environ['RANGE_END'] = str(r_end)
        os.environ['PYTHONUNBUFFERED'] = '1'

        if not is_retry_run:
            self.root.after(0, self.init_antenna_icons)
            self.active_idx = 0
        macs_encontradas = []

        try:
            with redirect_stdout_to_queue(self.queue):
                print(f"[DEBUG] Iniciando ejecución directa del módulo backend...")
                # Llamar a la función principal del backend
                # capturamos la salida línea por línea en el redirector
                configuracion_completa_antenas2.run_all(
                    range_start=r_start,
                    range_end=r_end,
                    backup_cfg=os.environ['BACKUP_CFG'],
                    archivo_local_fw=os.environ['ARCHIVO_LOCAL_FW'],
                    target_ips=retry_ips if is_retry_run else None
                )
        except KeyboardInterrupt:
            self.queue.put(('line', '\n[GUI] Proceso cancelado por el usuario.\n'))
            self.queue.put(('finished', None))
            return
        except Exception as e:
            self.queue.put(('error', f'Error en la ejecución del backend: {e}'))
            import traceback
            with open('crash_log.txt', 'w') as f:
                f.write(traceback.format_exc())
            print(traceback.format_exc())
            self.queue.put(('finished', None))
            return

        # Intentar extraer MACs de la tabla de resultados (CSV) al finalizar
        # Ya que ahora compartimos memoria, podríamos obtenerlas más directo, 
        # pero para mantener compatibilidad leemos el CSV generado.
        try:
            csv_path = 'resultados_antenas.csv'
            if os.path.exists(csv_path):
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('mac') and row['mac'] != 'No disponible':
                            macs_encontradas.append(row['mac'])
        except Exception as e:
            print(f"[DEBUG] Error leyendo MACs finales: {e}")

        self.root.after(0, self.progress.stop)
        self.root.after(0, lambda: self.progress.config(mode='determinate'))
        self.queue.put(('finished', None))

    def _set_progress(self, value):
        self.completed_antennas = value
        self.progress['maximum'] = self.total_antennas
        self.progress['value'] = value
        self.status_var.set(f'Antenas completadas: {self.completed_antennas}/{self.total_antennas}')


    def request_cancel(self):
        self.cancel_requested = True
        configuracion_completa_antenas2.cancel_requested = True
        self.queue.put(('line', '\n[GUI] Cancelación solicitada por el usuario, esperando detención...\n'))
        
        if self.proc and self.proc.poll() is None:
            try:
                # Try to send SIGINT first
                if os.name == 'posix':
                    self.proc.send_signal(signal.SIGINT)
                else:
                    self.proc.terminate()
                # give it a second, then kill
                time.sleep(1)
                if self.proc.poll() is None:
                    self.proc.kill()
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        # After cancel, try to show partial summary if CSV exists
        csv_path = os.path.join(os.getcwd(), 'resultados_antenas.csv')
        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    data = f.read()
                self.queue.put(('line', '\n--- Resumen parcial (CSV) ---\n'))
                self.queue.put(('line', data + '\n'))
            except Exception as e:
                self.queue.put(('line', f'No se pudo leer CSV: {e}\n'))

    def on_process_finished(self):
        self.running = False
        self.start_btn.config(text='Iniciar proceso de configuración')
        self.toggle_inputs(True)
        
        # Cargar los resultados en la tabla
        self.load_results_from_csv()
        
        if getattr(self, 'cancel_requested', False):
            self.status_var.set('Cancelado')
            self.cancel_requested = False
            self.show_final_csv_summary()
            if hasattr(self, 'notebook'):
                self.notebook.select(self.tab_resultados)
        else:
            self.status_var.set('Terminado')
            
            # Si NO es un reintento, ver si hay fallas y preguntar si se desea reintentar
            is_retry_run = getattr(self, 'is_retry', False)
            if not is_retry_run:
                failed_ips = self.get_failed_antennas()
                if failed_ips:
                    msg = f"Se detectaron fallos en la actualización de {len(failed_ips)} antena(s).\n\n¿Deseas realizar un último intento de actualización con estas IPs?"
                    if messagebox.askyesno("Reintento de Actualización", msg, parent=self.root):
                        self.root.after(100, lambda: self.start_retry_process(failed_ips))
                        return
                        
            # Si llegamos aquí: no hubo fallas, el usuario rechazó el reintento o ya era un reintento
            self.is_retry = False
            self.show_final_csv_summary()
            if hasattr(self, 'notebook'):
                self.notebook.select(self.tab_resultados)

    def show_final_csv_summary(self):
        csv_path = os.path.join(os.getcwd(), 'resultados_antenas.csv')
        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    data = f.read()
                self.append_console('\n--- Resumen final (CSV) ---\n')
                self.append_console(data + '\n')
            except Exception:
                pass

    def get_failed_antennas(self):
        """Lee el CSV y regresa la lista de ip_final para las antenas que fallaron"""
        import csv
        csv_path = os.path.join(os.getcwd(), 'resultados_antenas.csv')
        if not os.path.exists(csv_path):
            return []
            
        failed_ips = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    exito_val = str(row.get('exito', '')).lower()
                    exito_bool = exito_val in ['1', 'true', 'yes']
                    if not exito_bool:
                        ip_final = row.get('ip_final')
                        if ip_final and ip_final != '-':
                            failed_ips.append(ip_final)
        except Exception as e:
            print(f"Error checking failures: {e}")
        return failed_ips

    def start_retry_process(self, failed_ips):
        self.is_retry = True
        self.retry_ips = failed_ips
        
        self.cancel_requested = False
        configuracion_completa_antenas2.cancel_requested = False
        self.successful_ips = []
        if hasattr(self, 'open_ips_btn'):
            self.open_ips_btn.pack_forget()
            
        self.console.configure(state='normal')
        self.console.delete('1.0', 'end')
        self.console.configure(state='disabled')
        
        # No re-inicializamos iconos visuales, mantenemos los colores anteriores (verdes/rojos)
        self.total_antennas = len(failed_ips)
        self.progress.configure(mode='determinate')
        self.progress['maximum'] = self.total_antennas
        self.progress['value'] = 0
        self.completed_antennas = 0
        
        self.start_btn.config(text='Cancelar proceso')
        self.running = True
        self.status_var.set('Reintentando actualización...')
        
        self.toggle_inputs(False)
        
        # Lanzar hilo secundario para el reintento
        self.proc_thread = threading.Thread(target=self.run_subprocess, daemon=True)
        self.proc_thread.start()


    def _update_naranja(self):
        """Pone el icono actual en naranja (en proceso) sin avanzar el índice."""
        i = getattr(self, 'completed_antennas', 0)
        if 0 <= i < len(self.antenna_points):
            canvas = self.antenna_points[i]
            canvas.delete("all")
            # Naranja vibrante para visibilidad
            canvas.create_oval(2,4,14,16, fill='#FFA500', outline='#FF8C00')
            
    def run_connectivity_test(self):
        """Inicia el test de conectividad en un hilo separado."""
        if self.running:
            return
            
        # Deshabilitar controles
        self.toggle_inputs(False)
        self.test_conn_btn.config(state='disabled')
        self.start_btn.config(state='disabled')
        self.running = True # Usamos running para bloquear, aunque sea un proceso ligero
        self.status_var.set('Ejecutando test de conexión...')
        
        # Iniciar worker
        threading.Thread(target=self._connectivity_worker, daemon=True).start()

    def _connectivity_worker(self):
        try:
            r_start = self.settings.get('range_start_test', 11)
            r_end = self.settings.get('range_end_test', 18)
            base_ip = '192.168.1.'
            
            self.queue.put(('line', '\n' + '='*40 + '\n'))
            self.queue.put(('line', '🔍 INICIANDO TEST DE CONEXIÓN (PING SCAN)\n'))
            self.queue.put(('line', '='*40 + '\n'))
            
            detected_ips = []
            total_scanned = 0
            
            for i in range(r_start, r_end + 1):
                ip = f"{base_ip}{i}"
                total_scanned += 1
                try:
                    # Ping rápido (1 paquete, 1 segundo timeout)
                    subprocess.check_output(["ping", "-c", "1", "-W", "1", ip], stderr=subprocess.STDOUT)
                    self.queue.put(('line', f"✅ {ip}: ONLINE\n"))
                    detected_ips.append(ip)
                except subprocess.CalledProcessError:
                    self.queue.put(('line', f"❌ {ip}: OFFLINE\n"))
            
            self.queue.put(('line', '\n' + '-'*40 + '\n'))
            self.queue.put(('line', f"📊 RESUMEN DEL TEST:\n"))
            self.queue.put(('line', f"   Antenas detectadas: {len(detected_ips)}/{total_scanned}\n"))
            
            if detected_ips:
                self.queue.put(('line', f"   IPs Activas: {', '.join(detected_ips)}\n"))
            else:
                self.queue.put(('line', "   Ninguna antena respondió al ping.\n"))
            
            self.queue.put(('line', '-'*40 + '\n\n'))
            
        except Exception as e:
            self.queue.put(('error', f"Error en test de conexión: {e}"))
        finally:
            # Restaurar estado en GUI (usando queue para thread safety si fuera necesario, 
            # pero aquí finalizamos el bloque de 'running')
            self.queue.put(('finished_test', None))

            
if __name__ == '__main__':
    root = tk.Tk()
    root.title('Configurador de antenas SIIP INTERNET')
    w, h = 900, 800
    root.geometry(f'{w}x{h}')
    root.update_idletasks()
    ws = root.winfo_screenwidth()
    hs = root.winfo_screenheight()
    x = (ws // 2) - (w // 2)
    y = (hs // 2) - (h // 2)
    root.geometry(f'{w}x{h}+{x}+{y}')
    try:
        icon_path = resource_path('icono.png')
        icon_img = Image.open(icon_path)
        icon_tk = ImageTk.PhotoImage(icon_img)
        root.iconphoto(True, icon_tk)
    except Exception as e:
        print(f'No se pudo establecer el icono de la ventana: {e}')
    app = GuiConfig(root)
    root.mainloop()
