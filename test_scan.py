import subprocess
import sys

def scan_active_ips(base_ip='192.168.1.', inicio=1, fin=20):
    encontrados = []
    timeout_val = "1000" if sys.platform == 'darwin' else "1"
    print(f"Platform: {sys.platform}, timeout: {timeout_val}")
    for octeto in [1, 4, 11, 20]:  # Just a few common ones
        ip = f"{base_ip}{octeto}"
        res = subprocess.run(["ping", "-c", "1", "-W", timeout_val, ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            print(f"[SCAN] IP activa encontrada: {ip}")
            encontrados.append(ip)
        else:
            print(f"[SCAN] IP sin respuesta: {ip} (Code: {res.returncode})")
            print(f"  stdout: {res.stdout.strip()}")
            print(f"  stderr: {res.stderr.strip()}")
    return encontrados

print(scan_active_ips())
