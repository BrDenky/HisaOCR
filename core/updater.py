import os
import sys
import json
import urllib.request
import urllib.error
import subprocess
from core.version import __version__, GITHUB_OWNER, GITHUB_REPO

def parse_version(v_str):
    """
    Convierte una cadena de versión como 'v1.0.2' o '1.0' en una tupla de enteros.
    Descarta prefijos como 'v' o espacios en blanco.
    """
    v_str = v_str.lower().lstrip('v').strip()
    try:
        return tuple(map(int, v_str.split('.')))
    except ValueError:
        return (0, 0, 0)

def check_for_updates():
    """
    Comprueba si hay una nueva versión disponible en GitHub Releases.
    Retorna: (update_available, latest_version, changelog, download_url)
    """
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "HisaOCR-Updater"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            latest_version_str = data.get("tag_name", "0.0.0")
            changelog = data.get("body", "No hay notas de versión disponibles.")
            
            # Buscar el ejecutable en los assets de la release
            download_url = None
            for asset in data.get("assets", []):
                if asset.get("name") == "Lector_OCR_Cedula.exe":
                    download_url = asset.get("browser_download_url")
                    break
            
            local_version = parse_version(__version__)
            remote_version = parse_version(latest_version_str)
            
            update_available = remote_version > local_version and download_url is not None
            
            return update_available, latest_version_str, changelog, download_url
            
    except urllib.error.URLError as e:
        print(f"Error al verificar actualizaciones: {e}", file=sys.stderr)
        return False, None, None, None
    except Exception as e:
        print(f"Error inesperado al verificar actualizaciones: {e}", file=sys.stderr)
        return False, None, None, None

def download_update(url, dest_path, progress_callback=None):
    """
    Descarga el nuevo ejecutable desde la URL especificada.
    Llama a progress_callback(bytes_downloaded, total_size) para reportar progreso.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "HisaOCR-Updater"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            total_size = int(response.headers.get('content-length', 0))
            bytes_downloaded = 0
            
            with open(dest_path, 'wb') as f:
                while True:
                    chunk = response.read(32768) # Bloques de 32KB
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(bytes_downloaded, total_size)
        return True
    except Exception as e:
        print(f"Error al descargar la actualización: {e}", file=sys.stderr)
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except:
                pass
        return False

def apply_update_and_restart(new_exe_path):
    """
    Crea un archivo por lotes (.bat) temporal para realizar el reemplazo
    del ejecutable actual una vez cerrado, reinicia la app y se auto-elimina.
    """
    current_exe = os.path.abspath(sys.executable)
    new_exe = os.path.abspath(new_exe_path)
    
    # Si la app se ejecuta desde código fuente (no congelado), solo simulamos
    if not getattr(sys, 'frozen', False):
        print(f"[Modo Desarrollo] Simulación de actualización: Reemplazo de {current_exe} por {new_exe}")
        sys.exit(0)
        
    temp_dir = os.path.dirname(new_exe)
    bat_path = os.path.join(temp_dir, "update.bat")
    
    # Script por lotes (.bat) que realiza:
    # 1. Retardo de 2 segundos para dar tiempo a que la app principal se cierre.
    # 2. Borra el ejecutable antiguo.
    # 3. Mueve y renombra el ejecutable nuevo.
    # 4. Limpia la variable de entorno _MEIPASS de PyInstaller para evitar que
    #    el nuevo ejecutable intente cargar recursos de la carpeta temporal vieja.
    # 5. Inicia el ejecutable nuevo.
    # 6. Se elimina a sí mismo (del "%~f0").
    bat_content = f"""@echo off
timeout /t 2 /nobreak > NUL 2>&1 || ping 127.0.0.1 -n 3 > NUL
del /f /q "{current_exe}"
move /y "{new_exe}" "{current_exe}"
set _MEIPASS=
start "" "{current_exe}"
del "%~f0"
"""
    
    # Escribir el archivo .bat
    try:
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
    except Exception:
        # Fallback usando codificación por defecto del sistema
        with open(bat_path, "w") as f:
            f.write(bat_content)
            
    # Limpiar _MEIPASS del entorno del proceso subprocess para estar doblemente seguros
    env = os.environ.copy()
    if "_MEIPASS" in env:
        del env["_MEIPASS"]
            
    # Lanzar el archivo .bat en segundo plano sin ventana de consola
    try:
        subprocess.Popen(
            [bat_path],
            shell=True,
            env=env,
            creationflags=0x08000000 # CREATE_NO_WINDOW
        )
    except Exception as e:
        print(f"Error al iniciar el script por lotes de actualización: {e}", file=sys.stderr)
        sys.exit(1)
        
    sys.exit(0)
