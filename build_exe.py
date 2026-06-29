import subprocess
import sys
import os
import shutil

def install_pyinstaller():
    try:
        import PyInstaller
        print("PyInstaller ya está instalado.")
    except ImportError:
        print("PyInstaller no está instalado en el entorno virtual. Instalando...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
            print("PyInstaller instalado correctamente.")
        except Exception as e:
            print(f"Error al instalar PyInstaller: {e}")
            sys.exit(1)

def run_build():
    # Asegurar que el archivo de icono esté copiado localmente
    icon_dest = os.path.abspath("ui_icon.ico")
    if not os.path.exists(icon_dest):
        try:
            import customtkinter
            ctk_path = os.path.dirname(customtkinter.__file__)
            icon_src = os.path.join(ctk_path, "assets", "icons", "CustomTkinter_icon_Windows.ico")
            if os.path.exists(icon_src):
                shutil.copy(icon_src, icon_dest)
                print("Icono oficial de CustomTkinter copiado a la raíz como ui_icon.ico")
        except Exception as e:
            print(f"Advertencia: No se pudo copiar el icono por defecto: {e}")

    # Asegurar que la imagen del splash exista
    splash_src = os.path.abspath("splash.png")
    if not os.path.exists(splash_src):
        print("Error: No se encontró la imagen de carga 'splash.png' en el directorio raíz.")
        sys.exit(1)

    # Asegurar que el directorio de salida esté limpio
    dist_dir = os.path.abspath("dist")
    build_dir = os.path.abspath("build")
    
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name=Lector_OCR_Cedula",
        "--icon=ui_icon.ico",
        "--splash=splash.png",
        "--add-data=models;models",
        "--add-data=ui_icon.ico;.",
        "--collect-all=paddleocr",
        "--collect-all=paddlex",
        "--collect-all=customtkinter",
        "--collect-all=cv2",
        "main.py"
    ]
    
    print("\nIniciando compilación con PyInstaller...")
    print("Comando a ejecutar:\n", " ".join(cmd))
    
    try:
        subprocess.run(cmd, check=True)
        print("\n¡Compilación finalizada con éxito!")
        exe_path = os.path.join(dist_dir, "Lector_OCR_Cedula.exe")
        print(f"El archivo ejecutable se encuentra en: {exe_path}")
    except subprocess.CalledProcessError as e:
        print(f"\nError durante la compilación de PyInstaller: {e}")
        sys.exit(1)

if __name__ == "__main__":
    install_pyinstaller()
    run_build()
