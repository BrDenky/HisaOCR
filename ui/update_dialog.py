import os
import sys
import threading
import customtkinter as ctk
from core.updater import download_update, apply_update_and_restart
from core.version import __version__

class UpdateDialog(ctk.CTkToplevel):
    def __init__(self, parent, latest_version, changelog, download_url):
        super().__init__(parent)
        self.parent = parent
        self.latest_version = latest_version
        self.changelog = changelog
        self.download_url = download_url
        
        self.title("Actualización Disponible")
        self.geometry("520x420")
        self.resizable(False, False)
        
        # Hacerlo modal y forzar que esté por encima de la ventana principal
        self.transient(parent)
        self.grab_set()
        
        # Centrar la ventana de actualización con respecto al padre
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self._build_ui()
        
    def _build_ui(self):
        # Frame principal
        self.main_frame = ctk.CTkFrame(self, fg_color="#18181b", corner_radius=0)
        self.main_frame.pack(fill="both", expand=True)
        
        # Título de Cabecera
        self.header_label = ctk.CTkLabel(
            self.main_frame,
            text="¡NUEVA VERSIÓN DISPONIBLE!",
            font=ctk.CTkFont(family="Helvetica", size=16, weight="bold"),
            text_color="#00f0ff"
        )
        self.header_label.pack(pady=(25, 5), padx=20)
        
        # Subtítulo informativo
        self.version_label = ctk.CTkLabel(
            self.main_frame,
            text=f"Versión instalada: v{__version__}   ->   Última versión: {self.latest_version}",
            font=ctk.CTkFont(family="Helvetica", size=12),
            text_color="#a1a1aa"
        )
        self.version_label.pack(pady=(0, 20), padx=20)
        
        # Contenedor para el cuerpo central dinámico
        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=25, pady=5)
        
        # Notas del Changelog
        self.notes_title = ctk.CTkLabel(
            self.content_frame,
            text="Novedades y correcciones:",
            font=ctk.CTkFont(family="Helvetica", size=11, weight="bold"),
            text_color="#39ff14",
            anchor="w"
        )
        self.notes_title.pack(fill="x", pady=(0, 5))
        
        self.notes_textbox = ctk.CTkTextbox(
            self.content_frame,
            fg_color="#09090b",
            border_color="#27272a",
            border_width=1,
            text_color="#e4e4e7",
            font=("Consolas", 10),
            corner_radius=6
        )
        self.notes_textbox.pack(fill="both", expand=True, pady=(0, 15))
        self.notes_textbox.insert("1.0", self.changelog)
        self.notes_textbox.configure(state="disabled") # Lectura
        
        # Frame para botones de acción inferior
        self.btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent", height=50)
        self.btn_frame.pack(fill="x", side="bottom", padx=25, pady=(5, 25))
        
        self.btn_update = ctk.CTkButton(
            self.btn_frame,
            text="Actualizar Ahora",
            command=self._start_download,
            font=ctk.CTkFont(family="Helvetica", size=12, weight="bold"),
            fg_color="#10b981", # Verde
            hover_color="#059669",
            height=36
        )
        self.btn_update.pack(side="right", padx=(10, 0))
        
        self.btn_later = ctk.CTkButton(
            self.btn_frame,
            text="Más Tarde",
            command=self._on_close,
            font=ctk.CTkFont(family="Helvetica", size=12, weight="bold"),
            fg_color="#27272a", # Gris oscuro
            hover_color="#3f3f46",
            height=36
        )
        self.btn_later.pack(side="right")
        
        # Elementos de progreso de descarga (ocultos inicialmente)
        self.progress_label = None
        self.progress_bar = None
        self.progress_percent = None
        self.btn_error_close = None
        
        self.downloading = False
        
    def _start_download(self):
        if self.downloading:
            return
        
        self.downloading = True
        
        # Ocultar la sección de notas de versión y botones
        self.notes_title.pack_forget()
        self.notes_textbox.pack_forget()
        self.btn_frame.pack_forget()
        
        # Crear visuales para la descarga
        self.progress_label = ctk.CTkLabel(
            self.content_frame,
            text="Descargando actualización desde GitHub...",
            font=ctk.CTkFont(family="Helvetica", size=13, weight="bold"),
            text_color="#e4e4e7"
        )
        self.progress_label.pack(pady=(45, 15))
        
        self.progress_bar = ctk.CTkProgressBar(
            self.content_frame,
            width=420,
            height=14,
            progress_color="#10b981"
        )
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0.0)
        
        self.progress_percent = ctk.CTkLabel(
            self.content_frame,
            text="Conectando... 0% (0.0 MB / 0.0 MB)",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#a1a1aa"
        )
        self.progress_percent.pack(pady=5)
        
        # Lanzar la descarga en un hilo asíncrono secundario
        threading.Thread(target=self._download_thread_worker, daemon=True).start()
        
    def _download_thread_worker(self):
        # Resolver la ruta temporal del nuevo exe en el mismo directorio que el ejecutable actual
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        temp_exe_path = os.path.join(base_dir, "Lector_OCR_Cedula.new")
        
        success = download_update(
            self.download_url,
            temp_exe_path,
            progress_callback=self._update_progress_ui
        )
        
        if success:
            self.after(0, self._on_download_success, temp_exe_path)
        else:
            self.after(0, self._on_download_error)
            
    def _update_progress_ui(self, bytes_downloaded, total_size):
        """Llamado periódicamente por el descargador."""
        if total_size <= 0:
            pct = 0.0
            pct_str = "Descargando..."
        else:
            pct = bytes_downloaded / total_size
            pct_str = f"{pct * 100:.1f}% ({bytes_downloaded / (1024*1024):.2f} MB / {total_size / (1024*1024):.2f} MB)"
            
        # Actualizar la interfaz de forma segura en el hilo principal
        self.after(0, lambda: self._apply_progress(pct, pct_str))
        
    def _apply_progress(self, progress_val, text_val):
        if self.progress_bar:
            self.progress_bar.set(progress_val)
        if self.progress_percent:
            self.progress_percent.configure(text=text_val)
            
    def _on_download_success(self, temp_exe_path):
        self.progress_label.configure(text="¡Actualización descargada correctamente!", text_color="#10b981")
        self.progress_percent.configure(text="Aplicando actualización y reiniciando app...")
        
        # Dar tiempo a que el usuario lea el mensaje y luego ejecutar reemplazo
        self.after(1800, lambda: apply_update_and_restart(temp_exe_path))
        
    def _on_download_error(self):
        self.downloading = False
        self.progress_label.configure(text="Ocurrió un error al descargar la actualización", text_color="#ef4444")
        self.progress_percent.configure(text="Comprueba tu conexión e intenta nuevamente.")
        
        self.btn_error_close = ctk.CTkButton(
            self.content_frame,
            text="Cerrar",
            command=self._on_close,
            fg_color="#27272a",
            hover_color="#3f3f46",
            width=120
        )
        self.btn_error_close.pack(pady=20)
        
    def _on_close(self):
        if self.downloading:
            return # Evitar cerrar a mitad de descarga
        self.grab_release()
        self.destroy()
