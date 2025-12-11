import os
import time
import sys
import re
import socket
import subprocess
import importlib
import csv
import shutil

# -------------------
# DEPENDENCY CHECK / AUTO-INSTALL
# -------------------
def ensure_python_packages(packages):
    """Ensure required python packages are importable, install via pip if missing."""
    for import_name, pip_name in packages.items():
        try:
            importlib.import_module(import_name)
        except Exception:
            print(f"[DEPENDENCIAS] Instalando paquete faltante: {pip_name} (import: {import_name})")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            except subprocess.CalledProcessError as e:
                print(f"❌ Error instalando {pip_name}: {e}")
                raise
    # Verificar tkinter (no siempre instalable vía pip). Solo validamos y tratamos de ayudar.
    try:
        import tkinter  # type: ignore
        print(f"[DEPENDENCIAS] tkinter disponible. Tk version: {tkinter.TkVersion}")
    except Exception as e:
        print("[DEPENDENCIAS] tkinter NO está disponible en este intérprete de Python.")
        # En macOS intentamos instalar tcl-tk mediante Homebrew si está disponible
        if sys.platform == 'darwin' and shutil.which('brew'):
            print("[DEPENDENCIAS] Intentando instalar tcl-tk vía Homebrew (requiere brew y conexión a internet)...")
            try:
                subprocess.check_call(['brew', 'install', 'tcl-tk'])
                print("[DEPENDENCIAS] tcl-tk instalado (intenta reinstalar/usar un Python que enlace con este tcl-tk).")
            except subprocess.CalledProcessError:
                print("[DEPENDENCIAS] No se pudo instalar tcl-tk automáticamente. Por favor instala tcl-tk o usa el instalador oficial de Python desde python.org que incluye Tcl/Tk.")
        else:
            print("[DEPENDENCIAS] No se pudo encontrar tkinter. En macOS instala Python desde python.org o instala tcl-tk y recompila/usa un Python que lo enlace. En Linux instala el paquete de desarrollo de tk (por ejemplo, apt install tk-dev) o usa tu gestor de paquetes.")
        # No lanzamos excepción aquí para permitir uso headless del script; la GUI comprobará y fallará si intenta abrir.

def check_chrome_available():
    """On macOS try to detect Google Chrome application; otherwise warn the user.
    We can't install Chrome automatically, only check presence.
    """
    # macOS standard path
    mac_path = "/Applications/Google Chrome.app"
    if sys.platform == 'darwin':
        if os.path.exists(mac_path):
            return True
        # also try which for chrome commands
        if shutil.which('google-chrome') or shutil.which('chromium'):
            return True
        print("[DEPENDENCIAS] Advertencia: Google Chrome no parece instalado en esta máquina (macOS).")
        print("  Instala Google Chrome para que Selenium pueda iniciar un navegador real.")
        return False
    else:
        # On other systems, rely on webdriver_manager to fetch a driver; still warn if no chrome binary
        if shutil.which('google-chrome') or shutil.which('chrome') or shutil.which('chromium'):
            return True
        print("[DEPENDENCIAS] Advertencia: No se detectó un binario de Chrome/Chromium en PATH.")
        return False

# Install required dependencies
REQUIRED_PACKAGES = {
    'paramiko': 'paramiko',
    'selenium': 'selenium',
    'webdriver_manager': 'webdriver-manager',  # for selenium
    'PIL': 'pillow',  # for image handling in GUI
}

# Try to ensure packages are available before importing them
ensure_python_packages(REQUIRED_PACKAGES)

# Now import the heavy modules (they should be available)
import paramiko
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# -------------------
# CONFIGURACIÓN
# -------------------
# Nota: IP_INICIAL se determina dinámicamente buscando en un rango
# por defecto el script buscaba 192.168.1.20 cuando no hay DHCP.
# Ahora se intentará encontrar la primera IP que responda en el rango
# 192.168.1.11 - 192.168.1.18 y a partir de esa IP se mapeará
# la IP final (netconf.2.ip) en el .cfg.
IP_INICIAL = "192.168.1.20"  # valor por defecto (se sobrescribe en tiempo de ejecución)
IP_FINAL = "192.168.1.1"     # valor por defecto (se sobrescribe en tiempo de ejecución)
USUARIO = "ubnt"
PASSWORD = "Siip.567"
# Allow overrides from environment so GUIs or other runners can change files dynamically
BACKUP_CFG = os.environ.get('BACKUP_CFG', "WA-28704EB63776.cfg")
ARCHIVO_LOCAL_FW = os.environ.get('ARCHIVO_LOCAL_FW', 'WA.v8.7.19.48279.250811.0636.bin')
ARCHIVO_REMOTO_FW = '/tmp/firmware.bin'
# Extrae dinámicamente la versión esperada del nombre del archivo de firmware
match_version = re.search(r'v(\d+\.\d+\.\d+)', ARCHIVO_LOCAL_FW)
VERSION_ESPERADA = match_version.group(1) if match_version else None

# -------------------
# FUNCIONES DE RED Y VERIFICACIÓN
# -------------------
def esperar_ping(ip, intentos=60, espera=1, verbose=False):
    """
    Espera a que un host responda a ping.
    """
    if verbose:
        print(f"[Verificación] Esperando a que responda {ip}...")
    for _ in range(intentos):
        if subprocess.run(["ping", "-c", "1", "-W", "1", ip],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            if verbose:
                print(f"✅ {ip} responde a ping")
            return True
        time.sleep(espera)
    raise TimeoutError(f"❌ {ip} no respondió a ping en el tiempo esperado")

def esperar_web(ip, puerto=443, timeout=2, reintentos=120, verbose=False):
    """
    Espera a que un puerto web esté disponible.
    Aumentado el timeout y reintentos para la actualización de firmware.
    """
    if verbose:
        print(f"[Verificación] Esperando a que {ip}:{puerto} abra el servicio web...")
    for intento in range(reintentos):
        try:
            with socket.create_connection((ip, puerto), timeout=timeout):
                if verbose:
                    print(f"✅ {ip}:{puerto} ya está disponible.")
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            if verbose and intento % 20 == 0 and intento > 0:  # Mensaje cada 20 segundos
                print(f"[{intento}/{reintentos}] Esperando interfaz web en {ip}...")
            time.sleep(1)
    raise TimeoutError(f"❌ El puerto {puerto} en {ip} no se abrió a tiempo")

def esperar_ssh(ip, puerto=22, timeout=2, reintentos=60, verbose=False):
    """
    Espera a que un puerto SSH esté disponible.
    """
    if verbose:
        print(f"[Verificación] Esperando a que {ip}:{puerto} permita conexión SSH...")
    for intento in range(reintentos):
        try:
            with socket.create_connection((ip, puerto), timeout=timeout):
                if verbose:
                    print(f"✅ SSH disponible en {ip}")
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            if verbose and intento % 10 == 0 and intento > 0:  # Mensaje cada 10 segundos
                print(f"[{intento}/{reintentos}] Esperando SSH en {ip}...")
            time.sleep(1)
    raise TimeoutError(f"❌ SSH en {ip} no se abrió a tiempo")

def verificar_interfaz_web_lista(ip, max_intentos=10, espera_entre_intentos=5):
    """
    Verifica que la interfaz web esté completamente cargada y funcional.
    """
    print(f"[Verificación Web] Verificando que la interfaz web esté completamente lista en {ip}...")
    
    chrome_options = Options()
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-insecure-localhost")
    chrome_options.add_argument("--headless")  # Ejecutar en modo headless para verificación
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    
    for intento in range(max_intentos):
        driver = None
        try:
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(10)
            
            driver.get(f"https://{ip}")
            time.sleep(2)  # Espera a que la página cargue
            
            # Verifica que hay elementos de la interfaz de login
            WebDriverWait(driver, 5).until(
                lambda d: d.find_element(By.TAG_NAME, "body")
            )
            
            # Si llegamos aquí, la página se cargó correctamente
            print(f"✅ Interfaz web completamente cargada en {ip}")
            return True
            
        except Exception as e:
            print(f"[{intento+1}/{max_intentos}] Interfaz web no lista todavía: {str(e)[:100]}...")
            time.sleep(espera_entre_intentos)
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    print(f"❌ La interfaz web no estuvo lista después de {max_intentos} intentos")
    return False

def get_version_from_device(ip, usuario, contrasena, max_reintentos=5):
    """
    Obtiene la versión de firmware del dispositivo a través de SSH con reintentos.
    """
    for intento in range(max_reintentos):
        ssh_client = None
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(
                hostname=ip, 
                username=usuario, 
                password=contrasena, 
                timeout=10,
                look_for_keys=False,
                allow_agent=False
            )
            
            stdin, stdout, stderr = ssh_client.exec_command("cat /etc/version")
            full_version_string = stdout.read().decode().strip()
            match_version = re.search(r'v(\d+\.\d+\.\d+)', full_version_string)
            version = match_version.group(1) if match_version else "Desconocida"
            return version
            
        except Exception as e:
            print(f"[{intento+1}/{max_reintentos}] Error al obtener la versión: {e}")
            if intento < max_reintentos - 1:
                time.sleep(5)  # Espera antes del siguiente intento
        finally:
            if ssh_client:
                try:
                    ssh_client.close()
                except:
                    pass
    
    return "Desconocida"

def get_mac_from_ifconfig(ip, usuario, contrasena):
    """
    Obtiene la dirección MAC de la interfaz ath0 a través de SSH.
    """
    ssh_client = None
    try:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname=ip, username=usuario, password=contrasena, timeout=10)
        
        stdin_mac, stdout_mac, stderr_mac = ssh_client.exec_command("ip link show ath0")
        raw_mac = stdout_mac.read().decode().strip()
        match_mac = re.search(r'link/ether\s+([0-9a-fA-F:]{17})', raw_mac)
        
        if not match_mac:
            stdin_mac, stdout_mac, stderr_mac = ssh_client.exec_command("ifconfig ath0")
            raw_mac = stdout_mac.read().decode().strip()
            match_mac = re.search(r'HWaddr\s+([0-9a-fA-F:]{17})', raw_mac)

        mac_address = match_mac.group(1).replace(':', '').upper() if match_mac else "Desconocida"
        return mac_address
    except Exception as e:
        print(f"Error al obtener la dirección MAC: {e}")
        return "Desconocida"
    finally:
        if ssh_client:
            ssh_client.close()


def buscar_dispositivo_en_rango(base_ip='192.168.1.', inicio=11, fin=18, espera=0.2):
    """
    Busca la primera IP que responda a ping en el rango especificado.
    Retorna la IP completa como string, o lanza excepción si no encuentra ninguna.
    """
    print(f"[Búsqueda] Escanenado rango {base_ip}{inicio} - {base_ip}{fin} en busca de dispositivo...")
    for octeto in range(inicio, fin + 1):
        ip = f"{base_ip}{octeto}"
        # Usamos un ping rápido de 1 intento con timeout corto
        try:
            if subprocess.run(["ping", "-c", "1", "-W", "1", ip],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                print(f"[Búsqueda] Encontrado dispositivo en: {ip}")
                return ip
        except Exception:
            pass
        time.sleep(espera)
    raise RuntimeError(f"No se encontró ningún dispositivo respondiendo en {base_ip}{inicio}-{base_ip}{fin}")


def modificar_cfg_para_ip(ruta_cfg_original, nueva_ip_final, ruta_cfg_modificada=None):
    """
    Lee el archivo .cfg original, modifica (o añade) la línea `netconf.2.ip=` para
    que tenga el valor `nueva_ip_final`. Devuelve la ruta del archivo modificado.
    """
    if ruta_cfg_modificada is None:
        ruta_cfg_modificada = f"temp_{os.path.basename(ruta_cfg_original)}"

    with open(ruta_cfg_original, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Reemplaza la línea si existe
    if re.search(r"^netconf\.2\.ip\s*=\s*\d+\.\d+\.\d+\.\d+", contenido, flags=re.M):
        contenido_mod = re.sub(r"^netconf\.2\.ip\s*=\s*\d+\.\d+\.\d+\.\d+",
                                f"netconf.2.ip={nueva_ip_final}", contenido, flags=re.M)
    else:
        # Si no existe esa línea, añadimos al final
        if not contenido.endswith('\n'):
            contenido += '\n'
        contenido_mod = contenido + f"netconf.2.ip={nueva_ip_final}\n"

    with open(ruta_cfg_modificada, 'w', encoding='utf-8') as f:
        f.write(contenido_mod)

    print(f"[CFG] Archivo de configuración modificado preparado: {ruta_cfg_modificada} (netconf.2.ip={nueva_ip_final})")
    return ruta_cfg_modificada

# -------------------
# CONFIGURACIÓN SELENIUM
# -------------------
def configurar_inicial(ip):
    # Esperar explícitamente que la interfaz web esté ready antes de Selenium
    esperar_web(ip, puerto=443)

    print("[Selenium] Abriendo navegador para configuración inicial...")
    chrome_options = Options()
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-insecure-localhost")
    chrome_options.add_argument("--start-maximized")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(f"https://{ip}")
        wait = WebDriverWait(driver, 15)

        language_select = wait.until(EC.presence_of_element_located((By.ID, "loginform-language")))
        Select(language_select).select_by_value("sp_SP")
        print("✅ Idioma seleccionado (Español)")

        wait.until(EC.staleness_of(language_select))
        time.sleep(1)

        country_select = wait.until(EC.presence_of_element_located((By.ID, "loginform-country")))
        Select(country_select).select_by_value("484")  # México
        print("✅ País seleccionado (México)")

        checkbox = wait.until(EC.element_to_be_clickable((By.ID, "loginform-agreed")))
        checkbox.click()
        print("✅ Términos aceptados")

        continue_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".loginform-continue")))
        continue_btn.click()
        print("✅ Botón continuar presionado")

        wait.until(EC.presence_of_element_located((By.ID, "loginform-new-username")))
        driver.find_element(By.ID, "loginform-new-username").send_keys(USUARIO)
        driver.find_element(By.ID, "loginform-new-password").send_keys(PASSWORD)
        driver.find_element(By.ID, "loginform-new-password2").send_keys(PASSWORD)
        print(f"✅ Usuario y contraseña rellenados: {USUARIO} / {PASSWORD}")

        save_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".loginform-submit")))
        save_btn.click()
        print("✅ Botón Guardar presionado. Configuración inicial completada!")
        
        time.sleep(2)  # Pausa breve por si hay procesos internos

    finally:
        driver.quit()

# -------------------
# FUNCIONES SSH para CONFIGURACIÓN
# -------------------
def conectar(ip):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=USUARIO, password=PASSWORD,
                look_for_keys=False, allow_agent=False,
                timeout=10,
                disabled_algorithms={"pubkeys": ["rsa-sha2-256","rsa-sha2-512"]})
    return ssh

def subir_cfg(ssh, archivo_local):
    with open(archivo_local, "r") as f:
        contenido = f.read()
    cmd = f"cat > /tmp/system.cfg <<'EOF'\n{contenido}\nEOF"
    ssh.exec_command(cmd)

def aplicar_cfg_y_reiniciar(ssh):
    ssh.exec_command("cfgmtd -w -p /etc")
    time.sleep(2)
    ssh.exec_command("reboot")
    ssh.close()

# -------------------
# FUNCIÓN DE ACTUALIZACIÓN DE FIRMWARE MEJORADA
# -------------------
def actualizar_firmware(ip, usuario, contrasena, archivo_local, archivo_remoto):
    """
    Establece una conexión SSH, transfiere el firmware y ejecuta la actualización.
    Versión mejorada que maneja correctamente el proceso de actualización.
    """
    ssh_client = None
    selenium_driver = None
    try:
        # 1. Obtiene la versión actual y la MAC antes de la actualización
        print(f"Obteniendo la versión actual del firmware en {ip}...")
        print("[GUI] PHASE_PROGRESS: firmware_update, 0")
        version_pre_actualizacion = get_version_from_device(ip, usuario, contrasena)
        mac_address_pre = get_mac_from_ifconfig(ip, usuario, contrasena)
        
        if version_pre_actualizacion:
            print(f"Versión actual del firmware (pre-actualización): {version_pre_actualizacion} 📡")
            print(f"Dirección MAC: {mac_address_pre}")
        else:
            print("No se pudo obtener la versión actual del firmware. Continuando...")
        print("[GUI] PHASE_PROGRESS: firmware_update, 5")

        print(f"Estableciendo conexión SSH a {ip}...")
        print("[GUI] PHASE_PROGRESS: firmware_update, 7")
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(
            hostname=ip, 
            username=usuario, 
            password=contrasena,
            look_for_keys=False,
            allow_agent=False,
            timeout=15
        )
        print("Conexión SSH exitosa. 🚀")

        # 2. Transfiere el archivo de firmware usando stdin
        print(f"Transfiriendo archivo de firmware: {archivo_local} -> {archivo_remoto}")
        print("[GUI] PHASE_PROGRESS: firmware_update, 10")
        comando_transferencia = f'cat - > {archivo_remoto}'
        stdin_transfer, stdout_transfer, stderr_transfer = ssh_client.exec_command(comando_transferencia)
        
        with open(archivo_local, 'rb') as f:
            stdin_transfer.write(f.read())
        stdin_transfer.close()
        
        # Espera a que la transferencia se complete
        stdout_transfer.channel.recv_exit_status()
        print("Archivo transferido exitosamente. ✅")
        print("[GUI] PHASE_PROGRESS: firmware_update, 15")

        # 3. Verifica que el archivo se transfirió correctamente
        stdin_check, stdout_check, stderr_check = ssh_client.exec_command(f'ls -la {archivo_remoto}')
        check_output = stdout_check.read().decode().strip()
        if archivo_remoto.split('/')[-1] in check_output:
            print(f"✅ Archivo verificado en el dispositivo: {check_output}")
        else:
            print("❌ Error: El archivo no se encuentra en el dispositivo")
            return False

        # 4. Ejecuta el comando de actualización
        print("Iniciando la actualización del firmware...")
        print("⚠️  IMPORTANTE: La antena se reiniciará y el proceso tomará 90 segundos exactos.")
        
        try:
            comando_final = f'fwupdate.real -m {archivo_remoto}'
            # Ejecutar el comando sin esperar respuesta (get_pty=True para forzar la ejecución inmediata)
            ssh_client.exec_command(comando_final, timeout=5, get_pty=True)
        except:
            # Ignorar cualquier error de comunicación, es esperado que la conexión se corte
            pass
        
        # No intentamos leer la salida porque la conexión se cortará
        print("✅ Comando de actualización enviado exitosamente.")
        print("🔄 La antena está actualizando el firmware y se reiniciará automáticamente...")
        print("[GUI] PHASE_PROGRESS: firmware_update, 18")
        
        # Cerrar la conexión SSH inmediatamente
        try:
            ssh_client.close()
        except:
            pass
        finally:
            ssh_client = None
        
        # 5. Esperar el tiempo exacto de actualización (1 minuto y 30 segundos)
        total_espera = 100  # 90 + 10 extra
        print(f"\n⏳ ACTUALIZANDO FIRMWARE - NO INTERRUMPIR")
        print(f"   Tiempo total de espera: {total_espera} segundos")
        
        # Mostrar una cuenta regresiva (reducida para el usuario, detallada para la GUI)
        for segundos in range(total_espera, 0, -1):
            # Calcular progreso: de 18% a 90% durante los 100 segundos
            progress_in_wait = 18 + int((total_espera - segundos) / total_espera * 72)
            # Notificar a la GUI cada segundo para la barra de progreso
            print(f"[GUI] PROGRESS: {segundos}")
            print(f"[GUI] PHASE_PROGRESS: firmware_update, {progress_in_wait}")
            
            # Mensajes visibles para el usuario (solo al inicio y al final)
            if segundos == total_espera:
                print(f"   ⌛ Tiempo restante: {segundos} segundos...")
            elif segundos == 5:
                print(f"   ⌛ Tiempo restante: {segundos} segundos...")
            
            time.sleep(1)
        
        print("\n✅ Tiempo de actualización completado")
        print("   Verificando conectividad y versión de la antena...")
        print("[GUI] PHASE_PROGRESS: firmware_update, 92")
        
        # 6. Esperar a que la antena complete la actualización y vuelva online
        # Después de los 90 segundos, verificamos que la antena responda
        try:
            # Primero esperamos ping con timeout reducido ya que debería estar lista
            esperar_ping(ip, intentos=30, espera=1)  # 30 segundos máximo
            time.sleep(5)  # Pequeña pausa después del ping
            print("[GUI] PHASE_PROGRESS: firmware_update, 94")
            # Luego esperamos SSH
            esperar_ssh(ip, puerto=22, reintentos=60)
            time.sleep(5)
            print("[GUI] PHASE_PROGRESS: firmware_update, 96")
            # Finalmente esperamos la interfaz web
            esperar_web(ip, puerto=443, reintentos=60)
            try:
                if verificar_interfaz_web_lista(ip):
                    print("✅ Interfaz web completamente disponible")
                else:
                    print("⚠️  La interfaz web tardó más de lo esperado, pero continuando...")
            except Exception as e:
                print(f"⚠️  Error verificando interfaz web: {e}, pero continuando...")
            
            # Verificación final de la versión del firmware
            print("\n" + "="*50)
            print("🔍 VERIFICACIÓN FINAL DE LA ACTUALIZACIÓN")
            print("="*50)
            print("[GUI] PHASE_PROGRESS: firmware_update, 98")
            version_actual = get_version_from_device(ip, usuario, contrasena)
            mac_address_post = get_mac_from_ifconfig(ip, usuario, contrasena)
            print(f"📋 RESUMEN DE LA ACTUALIZACIÓN:")
            print(f"   • Versión anterior: {version_pre_actualizacion}")
            print(f"   • Versión actual:   {version_actual}")
            print(f"   • Versión esperada: {VERSION_ESPERADA}")
            print(f"   • Dirección MAC:    {mac_address_post}")
            if version_actual and VERSION_ESPERADA and version_actual.startswith(VERSION_ESPERADA):
                print(f"\n🎉 ¡ACTUALIZACIÓN COMPLETADA EXITOSAMENTE!")
                print(f"✅ La antena ahora tiene el firmware versión {version_actual}")
                print(f"✅ La interfaz web está disponible en: https://{ip}")
                return True
            else:
                print(f"\n⚠️  La versión no coincide, reintentando actualización una vez más...")
                return False
        except Exception as e:
            print(f"\n❌ Error durante la verificación post-actualización: {e}")
            return False

        except TimeoutError as e:
            print(f"\n❌ TIMEOUT: {e}")
            print("🔧 Posibles causas:")
            print("   • La actualización está tomando más tiempo del esperado")
            print("   • Hubo un error durante la actualización")
            print("   • Problemas de conectividad de red")
            print(f"\n💡 Recomendación: Intenta acceder manualmente a https://{ip}")
            print("   Si la interfaz web no responde, podría ser necesario un reset de fábrica.")
            return False

    except paramiko.AuthenticationException:
        print("❌ Error de autenticación SSH. Verifica usuario y contraseña.")
        return False
    except paramiko.SSHException as e:
        print(f"❌ Error SSH: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ Error: El archivo {archivo_local} no se encontró.")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False
    finally:
        # Limpiar recursos de SSH
        if ssh_client:
            try:
                ssh_client.close()
            except:
                pass
            ssh_client = None

# -------------------
# Run logic as an importable function
# -------------------
def run_all(range_start=11, range_end=18, backup_cfg=None, archivo_local_fw=None, csv_file='resultados_antenas.csv', callback=None):
    # Modo flujo: 'config' = solo configurar (sin Selenium, sin update), 'full' = flujo completo.
    modo_flujo = os.environ.get('MODO_FLUJO', 'full')
    """Ejecuta todo el flujo de configuración y actualización para el rango indicado.
    Devuelve la lista de resultados.
    """
    # Allow callers to override module-level globals for file paths and recompute version
    global BACKUP_CFG, ARCHIVO_LOCAL_FW, VERSION_ESPERADA
    if backup_cfg:
        BACKUP_CFG = backup_cfg
    if archivo_local_fw:
        ARCHIVO_LOCAL_FW = archivo_local_fw
    # recompute expected version from filename
    m = re.search(r'v(\d+\.\d+\.\d+)', ARCHIVO_LOCAL_FW)
    VERSION_ESPERADA = m.group(1) if m else None

    print("🚀 INICIANDO PROCESO COMPLETO DE CONFIGURACIÓN Y ACTUALIZACIÓN")
    print("="*60)

    # Verificaciones iniciales
    if not os.path.exists(BACKUP_CFG):
        print(f"❌ Error: El archivo de backup '{BACKUP_CFG}' no existe.")
        raise FileNotFoundError(f"Backup not found: {BACKUP_CFG}")

    if not os.path.exists(ARCHIVO_LOCAL_FW):
        print(f"❌ Error: El archivo de firmware '{ARCHIVO_LOCAL_FW}' no existe.")
        raise FileNotFoundError(f"Firmware not found: {ARCHIVO_LOCAL_FW}")

    if not VERSION_ESPERADA:
        print(f"❌ Error: No se pudo extraer la versión del archivo de firmware.")
        print(f"   Asegúrate de que el nombre contenga 'vX.Y.Z'.")
        raise RuntimeError("No se pudo extraer la versión esperada del firmware")

    # Verificar disponibilidad del Chrome/ChromeDriver y navegador
    try:
        check_chrome_available()
        service = Service(ChromeDriverManager().install())
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Solo para verificación
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.quit()
        print("✅ ChromeDriver y navegador verificados")
    except Exception as e:
        print(f"❌ Error: No se pudo inicializar Chrome/ChromeDriver: {e}")
        print("   Asegúrate de tener Chrome instalado y actualizado.")
        raise

    print(f"✅ Archivos verificados:")
    print(f"   • Backup config: {BACKUP_CFG}")
    print(f"   • Firmware:      {ARCHIVO_LOCAL_FW}")
    print(f"   • Versión:       {VERSION_ESPERADA}")
    print()

    print("="*60)
    print("📡 FASE 1: CONFIGURACIÓN SECUENCIAL DE TODAS LAS ANTENAS EN EL RANGO")
    print("="*60)



    def scan_active_ips(base_ip='192.168.1.', inicio=range_start, fin=range_end, ping_timeout=1):
        """
        Escanea IPs en el rango y regresa una lista de las que responden a ping.
        """
        encontrados = []
        for octeto in range(inicio, fin + 1):
            ip = f"{base_ip}{octeto}"
            if subprocess.run(["ping", "-c", "1", "-W", str(ping_timeout), ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                print(f"[SCAN] IP activa encontrada: {ip}")
                encontrados.append(ip)
            else:
                print(f"[SCAN] IP sin respuesta: {ip}")
        return encontrados

    print("\n=== ESCANEANDO IPs DISPONIBLES EN EL RANGO ===")
    lista_ips = scan_active_ips()
    print(f"\nIPs activas encontradas: {lista_ips}\n")

    resultados = []
    idx_icono = 0
    if not lista_ips:
        print('No se encontraron antenas para configurar.')
    for IP_INICIAL in lista_ips:
        print(f"\n{'='*80}")
        print(f"PROCESANDO ANTENA EN {IP_INICIAL}")
        print(f"[GUI] START_ANTENNA: {IP_INICIAL}")
        print(f"{'='*80}")

        try:
            octeto = int(IP_INICIAL.split('.')[-1])
        except Exception:
            octeto = 0
        IP_FINAL = f"192.168.1.{octeto-10}" if octeto > 10 else '192.168.1.1'


        # Notificar visual (compatibilidad con GUI que parsea stdout)
        print(f"[GUI] INICIANDO_CONFIGURACION_IP: {IP_INICIAL}")
        print(f"[GUI] START_ANTENNA: {IP_INICIAL}")
        resultado_in_progress = {
            "ip_inicial": IP_INICIAL,
            "ip_final": IP_FINAL,
            "mac": None,
            "exito": None,
            "error": None,
            "progreso": True
        }
        if 'callback' in globals() and callable(callback):
            try:
                callback(idx_icono, resultado_in_progress)
            except Exception as cbe:
                print(f'[CALLBACK] Error llamando callback GUI (progreso): {cbe}')
        elif 'callback' in locals() and callable(callback):
            try:
                callback(idx_icono, resultado_in_progress)
            except Exception as cbe:
                print(f'[CALLBACK] Error llamando callback GUI (progreso): {cbe}')

        # Variables para limpiar al final
        ssh = None
        cfg_temporal = None
        driver = None
        exito_actualizacion = False
        error_txt = ''

        try:
            print("\n--- FASE 1: Configuración Inicial ---")
            print("1. Verificando conectividad inicial...")
            print("[GUI] PHASE_PROGRESS: detection, 0")
            esperar_ping(IP_INICIAL)
            esperar_web(IP_INICIAL, puerto=443)
            print("[GUI] PHASE_PROGRESS: detection, 100")

            if modo_flujo == 'full':
                print("\n2. Realizando configuración web inicial...")
                print("[GUI] PHASE_PROGRESS: web_config, 0")
                configurar_inicial(IP_INICIAL)
                print("[GUI] PHASE_PROGRESS: web_config, 100")

            print("\n3. Aplicando configuración por SSH...")
            print("[GUI] PHASE_PROGRESS: ssh_config, 0")
            esperar_ssh(IP_INICIAL)
            ssh = conectar(IP_INICIAL)
            print("[GUI] PHASE_PROGRESS: ssh_config, 30")
            cfg_temporal = modificar_cfg_para_ip(BACKUP_CFG, IP_FINAL)
            subir_cfg(ssh, cfg_temporal)
            print("[GUI] PHASE_PROGRESS: ssh_config, 70")
            aplicar_cfg_y_reiniciar(ssh)
            print("[GUI] PHASE_PROGRESS: ssh_config, 100")

            try:
                ssh.close()
            except:
                pass
            ssh = None

            try:
                if os.path.exists(cfg_temporal):
                    os.remove(cfg_temporal)
                    cfg_temporal = None
            except:
                pass

            print(f"\n4. Esperando que la antena reinicie con IP {IP_FINAL}...")
            print("[GUI] PHASE_PROGRESS: reboot, 0")
            esperar_ping(IP_FINAL)
            print("[GUI] PHASE_PROGRESS: reboot, 40")
            esperar_web(IP_FINAL, puerto=443)
            print("[GUI] PHASE_PROGRESS: reboot, 70")
            esperar_ssh(IP_FINAL)
            print("[GUI] PHASE_PROGRESS: reboot, 100")
            print(f"✅ FASE 1 COMPLETADA: Antena configurada y lista en {IP_FINAL}")
            
            # Si estamos en modo 'config', consideramos esto un éxito parcial (o total para ese modo)
            if modo_flujo == 'config':
                exito_actualizacion = True

            if modo_flujo == 'full':
                try:
                    print("\n" + "="*60)
                    print("🔧 FASE 2: ACTUALIZACIÓN DE FIRMWARE")
                    print("="*60)
                    exito_actualizacion = actualizar_firmware(IP_FINAL, USUARIO, PASSWORD, ARCHIVO_LOCAL_FW, ARCHIVO_REMOTO_FW)
                    if not exito_actualizacion:
                        print(f"[REINTENTO] La antena {IP_FINAL} no se actualizó correctamente, reintentando actualización...")
                        exito_actualizacion = actualizar_firmware(IP_FINAL, USUARIO, PASSWORD, ARCHIVO_LOCAL_FW, ARCHIVO_REMOTO_FW)
                finally:
                    try:
                        driver.quit()  # Aseguramos que cualquier instancia de Selenium esté cerrada
                    except:
                        pass
            try:
                mac_address = get_mac_from_ifconfig(IP_FINAL, USUARIO, PASSWORD)
            except:
                mac_address = "No disponible"
        except Exception as e:
            error_txt = str(e)
            print(f"\n❌ ERROR EN ANTENA {IP_INICIAL}: {e}")
            print("🔧 El proceso se detuvo para esta antena. Verifica la conectividad y los archivos.")
            exito_actualizacion = False
            mac_address = "No disponible"
        finally:
            # Limpieza final de recursos para esta antena
            if ssh:
                try:
                    ssh.close()
                except:
                    pass

            if cfg_temporal and os.path.exists(cfg_temporal):
                try:
                    os.remove(cfg_temporal)
                except:
                    pass

            try:
                if driver:
                    driver.quit()
            except:
                pass

        resultado_dict = {
            "ip_inicial": IP_INICIAL,
            "ip_final": IP_FINAL,
            "mac": mac_address,
            "exito": exito_actualizacion,
            "error": error_txt
        }
        resultados.append(resultado_dict)
        # --- CALLBACK EN TIEMPO REAL ---
        if 'callback' in globals() and callable(callback):
            try:
                callback(idx_icono, resultado_dict)
            except Exception as cbe:
                print(f'[CALLBACK] Error llamando callback GUI: {cbe}')
        elif 'callback' in locals() and callable(callback):
            try:
                callback(idx_icono, resultado_dict)
            except Exception as cbe:
                print(f'[CALLBACK] Error llamando callback GUI: {cbe}')
        idx_icono += 1
        
        # Notificar fin de antena para la GUI
        status_tag = "ok" if exito_actualizacion else "fail"
        print(f"[GUI] END_ANTENNA: {IP_INICIAL}, {status_tag}")
        print(f"🏁 PROCESO COMPLETADO PARA ANTENA EN {IP_INICIAL}")

    print("\nRESUMEN FINAL DE TODAS LAS ANTENAS PROBADAS:")
    print("="*70)
    print(f"{'IP INICIAL':15} {'IP FINAL':15} {'MAC':20} {'ESTADO':10}")
    print("-"*70)
    for r in resultados:
        estado = "✅ OK" if r.get('exito') else "❌ ERROR"
        ip_ini = r.get('ip_inicial', '-')
        ip_fin = r.get('ip_final', '-')
        mac = r.get('mac', 'No disponible')
        print(f"{ip_ini:15} {ip_fin:15} {mac:20} {estado:10}")

    # Exportar resumen a CSV
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as cf:
            writer = csv.writer(cf)
            writer.writerow(['ip_inicial', 'ip_final', 'mac', 'exito', 'error'])
            for r in resultados:
                writer.writerow([
                    r.get('ip_inicial', ''),
                    r.get('ip_final', ''),
                    r.get('mac', ''),
                    r.get('exito', False),
                    r.get('error', '')
                ])
        print(f"\n✅ Resumen exportado a CSV: {csv_file}")
    except Exception as e:
        print(f"⚠️  No se pudo exportar el CSV: {e}")

    return resultados


if __name__ == "__main__":
    # Read runtime overrides from environment and run
    env_backup = os.environ.get('BACKUP_CFG', BACKUP_CFG)
    env_fw = os.environ.get('ARCHIVO_LOCAL_FW', ARCHIVO_LOCAL_FW)
    start = int(os.environ.get('RANGE_START', 11))
    end = int(os.environ.get('RANGE_END', 18))
    csv_out = os.environ.get('RESULTADOS_CSV', 'resultados_antenas.csv')
    try:
        run_all(start, end, env_backup, env_fw, csv_out)
    except Exception as e:
        print(f"Error durante la ejecución: {e}")
        sys.exit(1)
