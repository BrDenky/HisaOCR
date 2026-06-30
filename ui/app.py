import os
import sys
import cv2
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk
import json
from datetime import datetime, timedelta

# Importar módulos locales
from core.camera_stream import CameraStream
from core.ocr_engine import OCREngine
from data.excel_handler import ExcelHandler
from ui.camera_view import CameraView
from core.email_sender import send_excel_email
from core.version import __version__
from core.updater import check_for_updates
from ui.update_dialog import UpdateDialog

# Determinar directorio base del ejecutable o script
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_env():
    """Carga variables desde el archivo .env si existe."""
    env_path = os.path.abspath(os.path.join(BASE_DIR, ".env"))
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key, val = parts[0].strip(), parts[1].strip()
                        # Quitar comillas si existen
                        if val.startswith('"') and val.endswith('"'):
                            val = val[1:-1]
                        elif val.startswith("'") and val.endswith("'"):
                            val = val[1:-1]
                        os.environ[key] = val

# Cargar variables de entorno al importar/arrancar
load_env()

def get_last_reset_time():
    """Lee el timestamp del último reset desde el archivo config.json."""
    config_path = os.path.abspath(os.path.join(BASE_DIR, "data", "config.json"))
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
                return datetime.fromisoformat(data["last_weekly_reset"])
        except Exception:
            pass
    # Por defecto, devuelve el tiempo actual (y lo guarda para evitar disparos inmediatos)
    now = datetime.now()
    save_last_reset_time(now)
    return now

def save_last_reset_time(dt):
    """Guarda el timestamp del último reset en el archivo config.json."""
    config_path = os.path.abspath(os.path.join(BASE_DIR, "data", "config.json"))
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    try:
        with open(config_path, "w") as f:
            json.dump({"last_weekly_reset": dt.isoformat()}, f)
    except Exception:
        pass

def get_next_scheduled_reset(dt, target_day=None, target_time_str=None):
    """
    Calcula el próximo momento del reset programado posterior al datetime dt dado.
    target_day: "Lunes", "Martes", "Miércoles", etc. (por defecto lee de RESET_DAY env var)
    target_time_str: "HH:MM" (por defecto lee de RESET_TIME env var)
    """
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    
    # Resolver el día objetivo (0 para Lunes, 6 para Domingo)
    if not target_day:
        target_day = os.environ.get("RESET_DAY", "Lunes")
    if target_day not in dias:
        target_day = "Lunes"
    target_day_idx = dias.index(target_day)
    
    # Resolver la hora y minuto objetivo
    if not target_time_str:
        target_time_str = os.environ.get("RESET_TIME", "07:00")
    try:
        parts = target_time_str.split(":")
        target_hour = int(parts[0])
        target_min = int(parts[1])
    except Exception:
        target_hour = 7
        target_min = 0
        
    # Encontrar el día programado en la semana actual de dt
    days_diff = target_day_idx - dt.weekday()
    scheduled_dt = dt + timedelta(days=days_diff)
    scheduled_dt = scheduled_dt.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
    
    # Si el momento calculado ya pasó respecto a dt, sumamos 7 días para el próximo
    if dt >= scheduled_dt:
        scheduled_dt += timedelta(days=7)
        
    return scheduled_dt

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configurar la ventana principal
        self.title("HisaOCR")
        self.geometry("1024x680")
        self.minsize(900, 600)
        self._set_window_icon()
        
        # Tema estético premium (Oscuro + Neon)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Componentes lógicos
        self.excel_handler = ExcelHandler()
        self.ocr_engine = OCREngine()
        self.camera_stream = None
        self.camera_active = True
        
        # Estado de la UI
        self.selected_camera_index = 0
        self.scanned_history = []
        
        # Estado de la lógica de reinicio semanal
        self.reset_in_progress = False
        
        # Construir Interfaz Gráfica
        self._build_ui()
        
        # Asegurar archivo Excel base al arrancar
        self._initialize_excel_database()
        
        # Iniciar revisión periódica del reinicio semanal
        self._check_weekly_reset()
        
        # Iniciar cámara por defecto
        self._start_camera_stream(self.selected_camera_index)
        
        # Bucle de actualización del feed
        self.update_feed_loop()
        
        # Comprobar actualizaciones en segundo plano al iniciar
        threading.Thread(target=self._check_update_on_startup, daemon=True).start()
        
        # Manejar cierre de la aplicación
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _set_window_icon(self):
        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, "ui_icon.ico")
            else:
                icon_path = os.path.join(BASE_DIR, "ui_icon.ico")
            
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

    def _initialize_excel_database(self):
        """Inicializa la base de datos predeterminada al iniciar."""
        success, msg = self.excel_handler.ensure_file_exists()
        if not success:
            self._update_status(f"Error Excel: {msg}", "red")
        else:
            self._update_status("Base de datos lista.", "green")

    def _build_ui(self):
        # Configuración del Grid principal (1 fila, 2 columnas)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=320) # Panel de control fijo
        self.grid_columnconfigure(1, weight=1)              # Feed de cámara expandible

        # ----------------- PANEL IZQUIERDO (CONTROLES) -----------------
        self.left_panel = ctk.CTkFrame(self, fg_color="#18181b", corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.left_panel.grid_rowconfigure(5, weight=1) # Empujar historia abajo

        # Título del panel
        self.title_label = ctk.CTkLabel(
            self.left_panel, 
            text="HisaOCR- Proinco", 
            font=ctk.CTkFont(family="Helvetica", size=20, weight="bold"),
            text_color="#00f0ff"
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=(25, 5), sticky="w")
        
        self.subtitle_label = ctk.CTkLabel(
            self.left_panel, 
            text="Registro de Personas Automatizado", 
            font=ctk.CTkFont(family="Helvetica", size=12),
            text_color="#a1a1aa"
        )
        self.subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 5), sticky="w")
        
        # Separador visual
        self.divider = ctk.CTkFrame(self.left_panel, height=2, fg_color="#27272a")
        self.divider.grid(row=2, column=0, padx=20, pady=(0, 5), sticky="ew")

        # --- SECCIÓN CONFIGURACIÓN CÁMARA ---
        self.cam_title = ctk.CTkLabel(
            self.left_panel, 
            text="Seleccionar Cámara", 
            font=ctk.CTkFont(family="Helvetica", size=11, weight="bold"),
            text_color="#00f0ff"
        )
        self.cam_title.grid(row=3, column=0, padx=20, pady=(5, 5), sticky="w")
        
        self.cam_controls_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.cam_controls_frame.grid(row=4, column=0, padx=20, pady=(0, 25), sticky="ew")
        self.cam_controls_frame.grid_columnconfigure(0, weight=3)
        self.cam_controls_frame.grid_columnconfigure(1, weight=2)
        
        self.cam_dropdown = ctk.CTkComboBox(
            self.cam_controls_frame,
            values=["Cámara 0", "Cámara 1", "Cámara 2", "Cámara 3"],
            command=self._on_camera_select,
            height=32,
            font=ctk.CTkFont(size=11)
        )
        self.cam_dropdown.set("Cámara 0")
        self.cam_dropdown.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.btn_restart_cam = ctk.CTkButton(
            self.cam_controls_frame,
            text="Reiniciar",
            command=self._restart_camera_action,
            height=32,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1e293b",
            hover_color="#334155"
        )
        self.btn_restart_cam.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # --- SECCIÓN HISTORIAL ---
        self.history_frame = ctk.CTkFrame(self.left_panel, fg_color="#09090b", corner_radius=8)
        self.history_frame.grid(row=5, column=0, padx=20, pady=(0, 10), sticky="nsew")
        self.history_frame.grid_rowconfigure(1, weight=1)
        self.history_frame.grid_columnconfigure(0, weight=1)
        
        self.history_title = ctk.CTkLabel(
            self.history_frame,
            text="HISTORIAL DE ESCANEOS",
            font=ctk.CTkFont(family="Helvetica", size=11, weight="bold"),
            text_color="#a1a1aa"
        )
        self.history_title.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="w")
        
        self.history_listbox = tk.Listbox(
            self.history_frame,
            bg="#09090b",
            fg="#e4e4e7",
            selectbackground="#27272a",
            selectforeground="#00f0ff",
            bd=0,
            highlightthickness=0,
            font=("Consolas", 9),
            activestyle="none"
        )
        self.history_listbox.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # --- PIE DE PÁGINA (VERSIÓN Y ACTUALIZACIONES) ---
        self.footer_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.footer_frame.grid(row=6, column=0, padx=20, pady=(5, 15), sticky="ew")
        self.footer_frame.grid_columnconfigure(0, weight=1)
        self.footer_frame.grid_columnconfigure(1, weight=0)
        
        self.lbl_version = ctk.CTkLabel(
            self.footer_frame,
            text=f"Versión {__version__}",
            font=ctk.CTkFont(family="Helvetica", size=10),
            text_color="#71717a"
        )
        self.lbl_version.grid(row=0, column=0, sticky="w")
        
        self.btn_check_update = ctk.CTkButton(
            self.footer_frame,
            text="Buscar actualización",
            command=self._check_update_manual,
            font=ctk.CTkFont(family="Helvetica", size=10, underline=True),
            fg_color="transparent",
            text_color="#3b82f6",
            hover_color="#27272a",
            width=120,
            height=20
        )
        self.btn_check_update.grid(row=0, column=1, sticky="e")

        # ----------------- PANEL DERECHO (CÁMARA FEED) -----------------
        self.right_panel = ctk.CTkFrame(self, fg_color="#0c0c0e", corner_radius=0)
        self.right_panel.grid(row=0, column=1, sticky="nsew")
        self.right_panel.grid_rowconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(1, weight=0)
        self.right_panel.grid_columnconfigure(0, weight=1)

        # Cámara View Canvas
        self.camera_view = CameraView(self.right_panel)
        self.camera_view.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="nsew")

        # Barra inferior de estado y botones de escaneo
        self.bottom_bar = ctk.CTkFrame(self.right_panel, fg_color="#18181b", height=80, corner_radius=8)
        self.bottom_bar.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.bottom_bar.grid_columnconfigure(0, weight=1)
        self.bottom_bar.grid_columnconfigure(1, weight=0)

        # Estado del OCR
        self.status_label = ctk.CTkLabel(
            self.bottom_bar,
            text="Inicializando cámara...",
            font=ctk.CTkFont(family="Helvetica", size=13, weight="bold"),
            text_color="#e4e4e7",
            anchor="w"
        )
        self.status_label.grid(row=0, column=0, padx=20, pady=20, sticky="ew")

        # Botón de acción principal
        self.btn_scan = ctk.CTkButton(
            self.bottom_bar,
            text="ESCANEAR CÉDULA",
            command=self._trigger_ocr_scan,
            font=ctk.CTkFont(family="Helvetica", size=14, weight="bold"),
            fg_color="#10b981", # Verde esmeralda
            hover_color="#059669",
            height=45,
            width=180
        )
        self.btn_scan.grid(row=0, column=1, padx=(5, 20), pady=15, sticky="e")
        
        # Vincular tecla Enter (Return) a la ventana modal
        self.bind("<Return>", lambda event: self._trigger_ocr_scan())

    # --- CONTROL DE CÁMARA ---

    def _start_camera_stream(self, index):
        """Inicia el hilo de captura de cámara."""
        self._update_status("Abriendo cámara... por favor espere.", "yellow")
        self.btn_scan.configure(state="disabled")
        
        # Detener cámara existente
        if self.camera_stream:
            self.camera_stream.stop()
            
        self.camera_stream = CameraStream(index)
        self.camera_stream.start()
        
        # Dar un momento al driver y habilitar escaneo
        self.after(1000, lambda: self.btn_scan.configure(state="normal"))
        self.after(1000, lambda: self._update_status("Cámara lista. Ubique la cédula.", "green"))

    def _on_camera_select(self, val):
        """Callback al cambiar de cámara en la UI."""
        idx_str = val.replace("Cámara ", "")
        if idx_str.isdigit():
            self.selected_camera_index = int(idx_str)
            self._start_camera_stream(self.selected_camera_index)

    def _restart_camera_action(self):
        """Reinicia la cámara actual."""
        self._start_camera_stream(self.selected_camera_index)

    # --- BUCLE PRINCIPAL DE VIDEO ---

    def update_feed_loop(self):
        """Actualiza recursivamente el widget de cámara."""
        if self.camera_stream and self.camera_active:
            frame = self.camera_stream.get_frame()
            if frame is not None:
                self.camera_view.update_feed(frame)
        
        # Volver a invocar cada 15 ms (~60 FPS)
        self.after(15, self.update_feed_loop)

    # --- LOGICA DE ESCANEO OCR ---

    def _update_status(self, text, color="white"):
        """Actualiza el texto y color del label de estado inferior."""
        colors = {
            "white": "#e4e4e7",
            "green": "#10b981",
            "yellow": "#f59e0b",
            "red": "#ef4444"
        }
        self.status_label.configure(text=text, text_color=colors.get(color, "#e4e4e7"))

    def _trigger_ocr_scan(self):
        """
        Pausa la cámara, extrae la región de interés y ejecuta
        el procesamiento de OCR en un hilo secundario.
        """
        crop = self.camera_view.get_cropped_card()
        if crop is None or crop.size == 0:
            self._update_status("Error: No hay fotograma disponible de la cámara.", "red")
            return

        # Pausar feed de cámara en la pantalla (congela el fotograma actual)
        self.camera_active = False
        self._update_status("Procesando documento... espere por favor.", "yellow")
        self.btn_scan.configure(state="disabled")

        # Lanzar OCR en un hilo separado para que no se congele la GUI
        ocr_thread = threading.Thread(target=self._run_ocr_background, args=(crop,), daemon=True)
        ocr_thread.start()

    def _run_ocr_background(self, crop):
        """Ejecuta el OCR en segundo plano y abre el modal en el hilo principal."""
        try:
            ci, nombres = self.ocr_engine.extract_data(crop)
            # Volver al hilo principal para mostrar el cuadro de diálogo
            self.after(0, self._show_verification_dialog, crop, ci, nombres)
        except Exception as e:
            # En caso de error, volver al hilo principal y restaurar
            self.after(0, self._handle_ocr_error, str(e))

    def _handle_ocr_error(self, err_msg):
        self._update_status(f"Error en OCR: {err_msg}", "red")
        self.camera_active = True
        self.btn_scan.configure(state="normal")
        messagebox.showerror("Error del Motor OCR", f"Ocurrió un error inesperado al procesar la imagen:\n{err_msg}")

    # --- DIÁLOGO MODAL DE CONFIRMACIÓN ---

    def _show_verification_dialog(self, crop_bgr, detected_ci, detected_nombres):
        """Crea una ventana modal interactiva para confirmar los datos."""
        self._update_status("Esperando confirmación del usuario...", "yellow")
        
        # Crear ventana secundaria modal
        modal = ctk.CTkToplevel(self)
        modal.title("Verificar Datos Extraídos")
        modal.geometry("520x480")  # Modificado para más altura libre
        modal.resizable(False, False)
        
        # Hacerla modal
        modal.transient(self)
        modal.grab_set()
        modal.focus_set()
        
        # Centrar el modal respecto a la app principal
        main_x = self.winfo_x()
        main_y = self.winfo_y()
        main_w = self.winfo_width()
        main_h = self.winfo_height()
        modal_x = main_x + (main_w - 520) // 2
        modal_y = main_y + (main_h - 480) // 2
        modal.geometry(f"+{modal_x}+{modal_y}")

        modal.grid_columnconfigure(0, weight=1)
        
        # Título
        lbl_title = ctk.CTkLabel(
            modal, 
            text="VERIFICACIÓN DE DOCUMENTO", 
            font=ctk.CTkFont(family="Helvetica", size=14, weight="bold"),
            text_color="#00f0ff"
        )
        lbl_title.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="ew")

        # Mostrar el recorte capturado para comparación visual
        crop_h, crop_w = crop_bgr.shape[:2]
        disp_w = 320
        disp_h = int((crop_h / crop_w) * disp_w)
        
        crop_resized = cv2.resize(crop_bgr, (disp_w, disp_h))
        crop_rgb = cv2.cvtColor(crop_resized, cv2.COLOR_BGR2RGB)
        
        pil_crop = Image.fromarray(crop_rgb)
        photo_crop = ImageTk.PhotoImage(image=pil_crop)
        
        modal.photo_reference = photo_crop
        
        lbl_crop = tk.Label(modal, image=photo_crop, bg="#18181b")
        lbl_crop.grid(row=1, column=0, padx=20, pady=(0, 15))

        # Contenedor de formulario
        form_frame = ctk.CTkFrame(modal, fg_color="transparent")
        form_frame.grid(row=2, column=0, padx=30, pady=5, sticky="ew")
        form_frame.grid_columnconfigure(1, weight=1)

        # Campo Cédula
        lbl_ci = ctk.CTkLabel(form_frame, text="Cédula (C.I.):", font=ctk.CTkFont(weight="bold"))
        lbl_ci.grid(row=0, column=0, padx=(0, 10), pady=8, sticky="w")
        
        entry_ci = ctk.CTkEntry(form_frame, font=ctk.CTkFont(family="Consolas", size=12))
        entry_ci.insert(0, detected_ci)
        entry_ci.grid(row=0, column=1, pady=8, sticky="ew")

        # Campo Nombres
        lbl_name = ctk.CTkLabel(form_frame, text="Nombres:", font=ctk.CTkFont(weight="bold"))
        lbl_name.grid(row=1, column=0, padx=(0, 10), pady=8, sticky="w")
        
        entry_name = ctk.CTkEntry(form_frame, font=ctk.CTkFont(size=12))
        entry_name.insert(0, detected_nombres)
        entry_name.grid(row=1, column=1, pady=8, sticky="ew")
        
        # Campo Oficina
        lbl_office = ctk.CTkLabel(form_frame, text="Oficina:", font=ctk.CTkFont(weight="bold"))
        lbl_office.grid(row=2, column=0, padx=(0, 10), pady=8, sticky="w")
        
        entry_office = ctk.CTkEntry(form_frame, font=ctk.CTkFont(size=12))
        entry_office.insert(0, "Matriz")
        entry_office.grid(row=2, column=1, pady=8, sticky="ew")

        # Campo Observaciones
        lbl_obs = ctk.CTkLabel(form_frame, text="Observaciones:", font=ctk.CTkFont(weight="bold"))
        lbl_obs.grid(row=3, column=0, padx=(0, 10), pady=8, sticky="w")
        
        entry_obs = ctk.CTkEntry(form_frame, placeholder_text="Opcional...", font=ctk.CTkFont(size=12))
        entry_obs.grid(row=3, column=1, pady=8, sticky="ew")

        # Contenedor Botones del Modal
        btn_frame = ctk.CTkFrame(modal, fg_color="transparent")
        btn_frame.grid(row=3, column=0, padx=30, pady=(20, 25), sticky="ew") # pady bottom aumentado para espacio
        btn_frame.grid_columnconfigure(0, weight=1)

        # Callbacks de botones
        def on_save():
            ci = entry_ci.get().strip()
            name = entry_name.get().strip().upper()
            office = entry_office.get().strip()
            obs = entry_obs.get().strip()
            
            if not ci or not name or not office:
                messagebox.showwarning("Campos Requeridos", "Cédula, Nombres y Oficina son campos obligatorios.", parent=modal)
                return
                
            # Validar cédula localmente
            if not self.ocr_engine.validate_ecuadorian_ci(ci):
                confirm = messagebox.askyesno(
                    "Cédula Invalida", 
                    "El número de cédula no pasa la validación de módulo-10.\n¿Desea guardarla de todas formas?", 
                    parent=modal
                )
                if not confirm:
                    return

            # Guardar en Excel
            success, msg = self.excel_handler.add_record(name, ci, office, obs)
            if success:
                # Actualizar historial de la UI
                display_str = f"{ci} | {name}"
                self.history_listbox.insert(0, display_str)
                self.scanned_history.append(display_str)
                if self.history_listbox.size() > 15:
                    self.history_listbox.delete(15, tk.END)
                
                self._update_status("Registro guardado con éxito.", "green")
                modal.destroy()
                self._resume_camera()
            else:
                messagebox.showerror("Error de guardado", msg, parent=modal)

        def on_cancel():
            modal.destroy()
            self._resume_camera()

        # Botón Confirmar y Guardar (Centrado y abarcando todo el ancho disponible)
        btn_save = ctk.CTkButton(
            btn_frame, 
            text="Confirmar y Guardar", 
            command=on_save,
            fg_color="#10b981",
            hover_color="#059669",
            height=38
        )
        btn_save.grid(row=0, column=0, padx=0, sticky="ew")

        # Vincular tecla Enter (Return) a la ventana modal
        modal.bind("<Return>", lambda event: on_save())

        # Asegurar reanudación de cámara si cierran el modal con la 'X'
        modal.protocol("WM_DELETE_WINDOW", on_cancel)

    def _resume_camera(self):
        """Reactiva el feed en vivo y el botón de escaneo."""
        self.camera_active = True
        self.btn_scan.configure(state="normal")
        self._update_status("Cámara activa. Listo para el siguiente escaneo.", "green")

    # --- PLANIFICADOR Y REPORTE SEMANAL ---

    def _check_weekly_reset(self):
        """Revisa periódicamente si corresponde el reinicio semanal."""
        if getattr(self, "reset_in_progress", False):
            self.after(60000, self._check_weekly_reset)
            return

        last_reset = get_last_reset_time()
        now = datetime.now()
        next_reset = get_next_scheduled_reset(last_reset)
        
        if now >= next_reset:
            sender = os.environ.get("SENDER_EMAIL", "mateopilaquinga@gmail.com")
            app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
            recipient = os.environ.get("RECIPIENT_EMAIL", "mateo.pilaquinga@yachaytech.edu.ec")
            
            if not app_password:
                self._update_status("Error: GMAIL_APP_PASSWORD no configurada en el .env", "red")
            else:
                self.reset_in_progress = True
                threading.Thread(
                    target=self._perform_weekly_reset_thread,
                    args=(next_reset, sender, app_password, recipient),
                    daemon=True
                ).start()
                
        # Programar siguiente revisión en 60 segundos
        self.after(60000, self._check_weekly_reset)

    def _perform_weekly_reset_thread(self, target_reset_time, sender, app_password, recipient):
        """Realiza el envío del correo y el archivado del Excel en segundo plano."""
        try:
            self._update_status("Enviando reporte semanal por correo...", "yellow")
            excel_path = self.excel_handler.get_file_path()
            
            if not os.path.exists(excel_path):
                save_last_reset_time(target_reset_time)
                self.after(0, lambda: self._update_status("No hay datos para enviar. Reset completado.", "green"))
                return

            # Intentar enviar el correo
            success, msg = send_excel_email(excel_path, sender, app_password, recipient)
            if success:
                # Archivar el Excel antiguo
                history_dir = os.path.abspath(os.path.join(os.path.dirname(excel_path), "historial"))
                os.makedirs(history_dir, exist_ok=True)
                
                date_str = target_reset_time.strftime("%Y_%m_%d")
                backup_name = f"registros_cedulas_{date_str}.xlsx"
                backup_path = os.path.join(history_dir, backup_name)
                
                if os.path.exists(backup_path):
                    backup_name = f"registros_cedulas_{date_str}_{int(datetime.now().timestamp())}.xlsx"
                    backup_path = os.path.join(history_dir, backup_name)
                
                try:
                    os.rename(excel_path, backup_path)
                    self.excel_handler.ensure_file_exists()
                    save_last_reset_time(target_reset_time)
                    
                    self.after(0, lambda: self._update_status("Reporte semanal enviado. Reset exitoso.", "green"))
                except Exception as e:
                    self.after(0, lambda: self._update_status(f"Error al archivar Excel: {str(e)}", "red"))
            else:
                self.after(0, lambda: self._update_status(f"Fallo envío de correo: {msg}. Se reintentará.", "red"))
        except Exception as e:
            self.after(0, lambda: self._update_status(f"Error en reset semanal: {str(e)}", "red"))
        finally:
            self.reset_in_progress = False

    # --- CIERRE DE LA APLICACIÓN ---

    def on_closing(self):
        """Se asegura de apagar la cámara y liberar recursos de forma forzada."""
        try:
            if self.camera_stream:
                self.camera_stream.stop()
        except Exception:
            pass
        finally:
            self.destroy()
            os._exit(0)

    # --- GESTIÓN DE ACTUALIZACIONES ---

    def _check_update_on_startup(self):
        """Comprueba si hay actualizaciones al iniciar la aplicación en segundo plano."""
        # Esperar un momento breve para dejar que la cámara e interfaz se inicialicen
        import time
        time.sleep(2.5)
        
        update_available, latest_version, changelog, download_url = check_for_updates()
        if update_available:
            self.after(500, lambda: self._show_update_dialog(latest_version, changelog, download_url))

    def _show_update_dialog(self, latest_version, changelog, download_url):
        """Abre la ventana modal del actualizador."""
        try:
            UpdateDialog(self, latest_version, changelog, download_url)
        except Exception as e:
            print(f"Error al abrir el diálogo de actualización: {e}", file=sys.stderr)

    def _check_update_manual(self):
        """Comprobación manual de actualización disparada por el botón."""
        self.btn_check_update.configure(text="Buscando...", state="disabled")
        
        def worker():
            update_available, latest_version, changelog, download_url = check_for_updates()
            
            def update_ui():
                self.btn_check_update.configure(text="Buscar actualización", state="normal")
                if update_available:
                    self._show_update_dialog(latest_version, changelog, download_url)
                else:
                    messagebox.showinfo(
                        "Sin actualizaciones", 
                        "¡Estás ejecutando la versión más reciente de la aplicación!"
                    )
            self.after(0, update_ui)
            
        threading.Thread(target=worker, daemon=True).start()
