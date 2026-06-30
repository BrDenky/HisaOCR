import os
import sys

# Desactivar MKLDNN/oneDNN por problemas con PIR executor en CPU con PaddlePaddle 3.3.0+
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
os.environ.setdefault('HUB_DATASET_ENDPOINT', 'https://modelscope.cn/api/v1/datasets')

# Aplicar bypass de dependencias de PaddleX/PaddleOCR (necesario en compilación con PyInstaller)
try:
    import importlib.metadata
    _orig_metadata = importlib.metadata.metadata
    _orig_requires = importlib.metadata.requires
    _orig_version = importlib.metadata.version

    def is_package_importable(package_name):
        import_name = package_name.replace("-", "_")
        if import_name in ("opencv_contrib_python", "opencv_python"):
            import_name = "cv2"
        try:
            __import__(import_name)
            return True
        except ImportError:
            return False

    class DummyMetadata:
        def get_all(self, name, default=None):
            return default or []

    def safe_metadata(package_name):
        try:
            return _orig_metadata(package_name)
        except importlib.metadata.PackageNotFoundError:
            if is_package_importable(package_name):
                return DummyMetadata()
            raise importlib.metadata.PackageNotFoundError(package_name)

    def safe_requires(package_name):
        try:
            return _orig_requires(package_name) or []
        except importlib.metadata.PackageNotFoundError:
            if is_package_importable(package_name):
                return []
            raise importlib.metadata.PackageNotFoundError(package_name)

    def safe_version(package_name):
        try:
            return _orig_version(package_name)
        except importlib.metadata.PackageNotFoundError:
            if is_package_importable(package_name):
                return "999.0.0"
            raise importlib.metadata.PackageNotFoundError(package_name)

    importlib.metadata.metadata = safe_metadata
    importlib.metadata.requires = safe_requires
    importlib.metadata.version = safe_version

    import paddlex.utils.deps as deps
    deps.is_dep_available = lambda *args, **kwargs: True
    deps.is_extra_available = lambda *args, **kwargs: True
    deps.require_deps = lambda *args, **kwargs: None
    deps.require_extra = lambda *args, **kwargs: None
    print("Bypass de dependencias de PaddleX/PaddleOCR aplicado con éxito.")
except Exception as e:
    print(f"Advertencia: No se pudo aplicar el bypass de dependencias: {e}")


def close_splash():
    """Cierra la pantalla de carga (Splash Screen) si está activa en PyInstaller."""
    try:
        import pyi_splash
        pyi_splash.close()
    except ImportError:
        pass

def start_main_app():
    from ui.app import App
    try:
        app = App()
        close_splash()
        app.mainloop()
    except Exception as e:
        print(f"Error fatal al arrancar la aplicación: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        input("\nPresione Enter para salir...")

def main():
    # Determinar base dir
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    env_path = os.path.join(base_dir, ".env")
    
    # Comprobar si existe el .env y tiene valores válidos
    configured = False
    if os.path.exists(env_path):
        config = {}
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        config[parts[0].strip()] = parts[1].strip()
                        
        if config.get("SENDER_EMAIL") and config.get("GMAIL_APP_PASSWORD") and config.get("RECIPIENT_EMAIL"):
            configured = True
            
    if configured:
        start_main_app()
    else:
        from ui.setup_wizard import SetupWizard
        try:
            wizard = SetupWizard(on_success_callback=start_main_app)
            close_splash()
            wizard.mainloop()
        except Exception as e:
            print(f"Error fatal al arrancar el asistente: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            input("\nPresione Enter para salir...")

if __name__ == "__main__":
    main()
