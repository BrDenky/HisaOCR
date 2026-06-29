import os
import sys

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
