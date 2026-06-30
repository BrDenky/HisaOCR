import os
import sys
import shutil
import threading
import smtplib
import re
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

class SetupWizard(ctk.CTk):
    def __init__(self, on_success_callback):
        super().__init__()
        self.on_success_callback = on_success_callback
        self.success = False
        self.recipient_list = []

        # Configurar ventana
        self.title("Instalación y Configuración - HisaOCR")
        self.geometry("560x460")
        self.resizable(False, False)
        
        # Tema estético premium (Oscuro + Neon)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color="#0d0d0f")
        
        self.excel_dir_path = ""
        
        # Intentar centrar la ventana
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        pos_x = (screen_w - 560) // 2
        pos_y = (screen_h - 460) // 2
        self.geometry(f"+{pos_x}+{pos_y}")

        # Establecer icono de ventana
        self._set_window_icon()

        self._build_ui()
        self._set_default_paths()

    def _set_window_icon(self):
        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, "ui_icon.ico")
            else:
                icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui_icon.ico")
            
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

    def _build_ui(self):
        # ----------------- TÍTULO Y PRESENTACIÓN -----------------
        self.title_label = ctk.CTkLabel(
            self,
            text="ASISTENTE DE CONFIGURACIÓN",
            font=ctk.CTkFont(family="Helvetica", size=18, weight="bold"),
            text_color="#00f0ff"
        )
        self.title_label.pack(pady=(20, 5))

        # ----------------- EXPLICACIÓN CORREOS -----------------
        self.exp_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.exp_frame.pack(padx=30, pady=(5, 10), fill="x")
        
        self.lbl_explanation = ctk.CTkLabel(
            self.exp_frame,
            text="ENVÍO DE REPORTES:\nSe enviará automáticamente un reporte semanal en formato Excel a las direcciones configuradas.",
            font=ctk.CTkFont(family="Helvetica", size=10, weight="bold"),
            text_color="#a1a1aa",
            justify="center"
        )
        self.lbl_explanation.pack(fill="x")

        # ----------------- FORMULARIO PRINCIPAL -----------------
        # Usar ScrollableFrame para garantizar que todo quepa perfectamente en pantalla
        self.form_frame = ctk.CTkScrollableFrame(self, fg_color="#18181b", border_color="#27272a", border_width=1)
        self.form_frame.pack(padx=30, pady=5, fill="both", expand=True)

        # 1. Correo Remitente (Gmail)
        self.lbl_sender = ctk.CTkLabel(self.form_frame, text="Correo Remitente (Gmail):", font=ctk.CTkFont(weight="bold"))
        self.lbl_sender.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")
        self.entry_sender = ctk.CTkEntry(self.form_frame, placeholder_text="ejemplo@gmail.com", font=ctk.CTkFont(size=12))
        self.entry_sender.grid(row=0, column=1, padx=20, pady=(15, 5), sticky="ew")

        # 2. Contraseña de Aplicación
        self.lbl_password = ctk.CTkLabel(self.form_frame, text="Contraseña de Aplicación:", font=ctk.CTkFont(weight="bold"))
        self.lbl_password.grid(row=1, column=0, padx=20, pady=5, sticky="w")
        self.entry_password = ctk.CTkEntry(self.form_frame, placeholder_text="xxxx xxxx xxxx xxxx", show="*", font=ctk.CTkFont(family="Consolas", size=12))
        self.entry_password.grid(row=1, column=1, padx=20, pady=5, sticky="ew")

        # 3. Destinatarios (Chips/Etiquetas)
        self.lbl_recipients = ctk.CTkLabel(self.form_frame, text="Destinatarios (Enter para agregar):", font=ctk.CTkFont(weight="bold"))
        self.lbl_recipients.grid(row=2, column=0, padx=20, pady=5, sticky="w")
        
        self.rec_entry_frame = ctk.CTkFrame(self.form_frame, fg_color="transparent")
        self.rec_entry_frame.grid(row=2, column=1, padx=20, pady=5, sticky="ew")
        self.rec_entry_frame.grid_columnconfigure(0, weight=1)

        self.entry_recipients = ctk.CTkEntry(self.rec_entry_frame, placeholder_text="correo@ejemplo.com + Enter", font=ctk.CTkFont(size=12))
        self.entry_recipients.grid(row=0, column=0, sticky="ew")
        self.entry_recipients.bind("<Return>", lambda event: self._add_recipient_chip())
        self.entry_recipients.bind("<Key>", lambda event: self._reset_recipient_border())

        # Mensaje de error de validación de correo (oculto por defecto)
        self.lbl_rec_error = ctk.CTkLabel(self.form_frame, text="", font=ctk.CTkFont(size=10), text_color="#ef4444")

        # Contenedor para los chips de destinatarios (oculto por defecto)
        self.chips_container = ctk.CTkFrame(self.form_frame, fg_color="transparent")

        # 4. Programación del Envío Semanal
        self.lbl_schedule = ctk.CTkLabel(self.form_frame, text="Día y Hora de Envío:", font=ctk.CTkFont(weight="bold"))
        self.lbl_schedule.grid(row=5, column=0, padx=20, pady=5, sticky="w")

        self.sched_frame = ctk.CTkFrame(self.form_frame, fg_color="transparent")
        self.sched_frame.grid(row=5, column=1, padx=20, pady=5, sticky="ew")
        self.sched_frame.grid_columnconfigure(0, weight=1)
        self.sched_frame.grid_columnconfigure(1, weight=1)

        self.combo_day = ctk.CTkComboBox(
            self.sched_frame, 
            values=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
            font=ctk.CTkFont(size=12),
            state="readonly"
        )
        self.combo_day.set("Lunes")
        self.combo_day.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        time_slots = []
        for h in range(24):
            for m in ["00", "30"]:
                time_slots.append(f"{h:02d}:{m}")
        
        self.combo_time = ctk.CTkComboBox(
            self.sched_frame, 
            values=time_slots,
            font=ctk.CTkFont(size=12),
            state="readonly"
        )
        self.combo_time.set("07:00")
        self.combo_time.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # 5. Checkbox de Acceso Directo
        self.check_shortcut = ctk.CTkCheckBox(
            self.form_frame,
            text="Crear acceso directo en el Escritorio",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e4e4e7"
        )
        self.check_shortcut.grid(row=6, column=0, columnspan=2, padx=20, pady=10, sticky="w")
        self.check_shortcut.select()

        # Configurar pesos del formulario
        self.form_frame.grid_columnconfigure(1, weight=1)

        # Mensaje de estado inferior
        self.status_label = ctk.CTkLabel(
            self,
            text="Listo para configurar.",
            font=ctk.CTkFont(size=11),
            text_color="#a1a1aa"
        )
        self.status_label.pack(pady=5)

        # Botón Iniciar Instalación
        self.btn_save = ctk.CTkButton(
            self,
            text="Validar y Guardar Configuración",
            fg_color="#10b981",
            hover_color="#059669",
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_save
        )
        self.btn_save.pack(pady=(5, 15), fill="x", padx=30)

    def _set_default_paths(self):
        if getattr(sys, 'frozen', False):
            default_dir = os.path.dirname(sys.executable)
        else:
            default_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        self.excel_dir_path = default_dir
        
        # Intentar precargar variables si el .env ya existe
        env_path = os.path.join(default_dir, ".env")
        if os.path.exists(env_path):
            try:
                config = {}
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            parts = line.split("=", 1)
                            if len(parts) == 2:
                                config[parts[0].strip()] = parts[1].strip()
                
                if "SENDER_EMAIL" in config:
                    self.entry_sender.insert(0, config["SENDER_EMAIL"])
                if "GMAIL_APP_PASSWORD" in config:
                    self.entry_password.insert(0, config["GMAIL_APP_PASSWORD"])
                if "RECIPIENT_EMAIL" in config:
                    for email in config["RECIPIENT_EMAIL"].split(","):
                        mail_clean = email.strip()
                        if mail_clean:
                            self.recipient_list.append(mail_clean)
                    self._render_chips()
                if "RESET_DAY" in config:
                    self.combo_day.set(config["RESET_DAY"])
                if "RESET_TIME" in config:
                    self.combo_time.set(config["RESET_TIME"])
                if "EXCEL_PATH" in config:
                    self.excel_dir_path = os.path.dirname(config["EXCEL_PATH"])
            except Exception:
                pass

    def _add_recipient_chip(self):
        email = self.entry_recipients.get().strip()
        if not email:
            return
            
        # Validación con RegEx
        email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_regex, email):
            self.entry_recipients.configure(border_color="#ef4444")
            self.lbl_rec_error.configure(text="Formato de correo electrónico inválido.")
            self.lbl_rec_error.grid(row=3, column=1, padx=20, pady=(0, 2), sticky="w")
            return

        if email in self.recipient_list:
            self.entry_recipients.configure(border_color="#ef4444")
            self.lbl_rec_error.configure(text="El correo electrónico ya está en la lista.")
            self.lbl_rec_error.grid(row=3, column=1, padx=20, pady=(0, 2), sticky="w")
            return

        # Éxito: Agregar
        self.recipient_list.append(email)
        self.entry_recipients.delete(0, tk.END)
        self._reset_recipient_border()
        self._render_chips()

    def _reset_recipient_border(self):
        self.entry_recipients.configure(border_color=["#3a3a44", "#3a3a44"])
        self.lbl_rec_error.configure(text="")
        self.lbl_rec_error.grid_remove()

    def _remove_recipient_chip(self, email):
        if email in self.recipient_list:
            self.recipient_list.remove(email)
            self._render_chips()

    def _render_chips(self):
        # Limpiar contenedor de chips anterior
        for widget in self.chips_container.winfo_children():
            widget.destroy()

        if not self.recipient_list:
            self.chips_container.grid_remove()
            return

        # Mostrar contenedor y renderizar chips en un grid fluido de Tkinter
        self.chips_container.grid(row=4, column=0, columnspan=2, padx=20, pady=(2, 8), sticky="ew")
        max_cols = 2
        for idx, email in enumerate(self.recipient_list):
            r = idx // max_cols
            c = idx % max_cols

            chip = ctk.CTkFrame(self.chips_container, fg_color="#27272a", border_width=1, border_color="#3f3f46", corner_radius=12)
            chip.grid(row=r, column=c, padx=5, pady=3, sticky="w")

            lbl = ctk.CTkLabel(chip, text=email, font=ctk.CTkFont(size=11), text_color="#e4e4e7")
            lbl.pack(side="left", padx=(10, 5), pady=2)

            btn_del = ctk.CTkButton(
                chip, 
                text="✕", 
                width=16, 
                height=16, 
                fg_color="transparent", 
                hover_color="#ef4444", 
                text_color="#a1a1aa",
                font=ctk.CTkFont(size=9, weight="bold"),
                command=lambda e=email: self._remove_recipient_chip(e)
            )
            btn_del.pack(side="right", padx=(0, 6), pady=2)

    def _update_status(self, text, color="white"):
        colors = {
            "white": "#e4e4e7",
            "green": "#10b981",
            "yellow": "#f59e0b",
            "red": "#ef4444"
        }
        self.status_label.configure(text=text, text_color=colors.get(color, "#e4e4e7"))
        self.update_idletasks()

    def _on_save(self):
        sender = self.entry_sender.get().strip()
        password = self.entry_password.get().strip().replace(" ", "")
        db_dir = self.excel_dir_path
        reset_day = self.combo_day.get()
        reset_time = self.combo_time.get()

        if not sender or not password or not self.recipient_list or not db_dir:
            messagebox.showwarning("Campos Incompletos", "Por favor complete todos los campos de configuración y añada al menos un destinatario.")
            return

        # Desactivar controles
        self.btn_save.configure(state="disabled")
        self.combo_day.configure(state="disabled")
        self.combo_time.configure(state="disabled")
        
        # Validar en segundo plano
        self._update_status("Probando conexión SMTP con Gmail...", "yellow")
        threading.Thread(
            target=self._validate_and_install_thread, 
            args=(sender, password, ",".join(self.recipient_list), db_dir, reset_day, reset_time), 
            daemon=True
        ).start()

    def _validate_and_install_thread(self, sender, password, recipients_str, db_dir, reset_day, reset_time):
        # 1. Probar SMTP
        smtp_success = False
        smtp_msg = ""
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587, timeout=5)
            server.starttls()
            server.login(sender, password)
            server.quit()
            smtp_success = True
        except Exception as e:
            smtp_msg = str(e)

        if not smtp_success:
            self.after(0, lambda: self._handle_smtp_failure(sender, password, recipients_str, db_dir, reset_day, reset_time, smtp_msg))
        else:
            self.after(0, lambda: self._proceed_with_installation(sender, password, recipients_str, db_dir, reset_day, reset_time))

    def _handle_smtp_failure(self, sender, password, recipients_str, db_dir, reset_day, reset_time, error_msg):
        self._update_status("Fallo de conexión SMTP.", "red")
        self.btn_save.configure(state="normal")
        self.combo_day.configure(state="normal")
        self.combo_time.configure(state="normal")
        
        confirm = messagebox.askyesno(
            "Fallo de Prueba SMTP",
            f"No se pudo verificar la Contraseña de Aplicación:\n\n{error_msg}\n\n"
            "¿Desea guardar la configuración e instalar la app de todas formas?"
        )
        if confirm:
            self.btn_save.configure(state="disabled")
            self.combo_day.configure(state="disabled")
            self.combo_time.configure(state="disabled")
            self._update_status("Instalando...", "yellow")
            threading.Thread(
                target=self._proceed_with_installation, 
                args=(sender, password, recipients_str, db_dir, reset_day, reset_time), 
                daemon=True
            ).start()

    def _proceed_with_installation(self, sender, password, recipients_str, db_dir, reset_day, reset_time):
        try:
            # 2. Instalar modelos OCR locales (si es un empaquetado congelado)
            if getattr(sys, 'frozen', False):
                self.after(0, lambda: self._update_status("Instalando archivos de modelos OCR (Offline)...", "yellow"))
                src_dir = os.path.join(sys._MEIPASS, "models")
                dest_dir = os.path.join(os.path.expanduser("~"), ".paddlex", "official_models")
                
                if os.path.exists(src_dir):
                    os.makedirs(dest_dir, exist_ok=True)
                    subfolders = os.listdir(src_dir)
                    total_folders = len(subfolders)
                    for idx, folder in enumerate(subfolders):
                        src_item = os.path.join(src_dir, folder)
                        dest_item = os.path.join(dest_dir, folder)
                        if os.path.isdir(src_item) and not os.path.exists(dest_item):
                            self.after(0, lambda f=folder, i=idx: self._update_status(f"Copiando modelo ({i+1}/{total_folders}): {f}...", "yellow"))
                            shutil.copytree(src_item, dest_item)
                            
            # 3. Guardar archivo .env
            self.after(0, lambda: self._update_status("Guardando archivo de configuración (.env)...", "yellow"))
            if getattr(sys, 'frozen', False):
                env_path = os.path.join(os.path.dirname(sys.executable), ".env")
            else:
                env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

            # Construir ruta final para registros_cedulas.xlsx
            excel_path = os.path.join(db_dir, "registros_cedulas.xlsx")
            
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(f"SENDER_EMAIL={sender}\n")
                f.write(f"GMAIL_APP_PASSWORD={password}\n")
                f.write(f"RECIPIENT_EMAIL={recipients_str}\n")
                f.write(f"EXCEL_PATH={excel_path}\n")
                f.write(f"RESET_DAY={reset_day}\n")
                f.write(f"RESET_TIME={reset_time}\n")

            # 4. Establecer en variables de entorno para ejecución inmediata
            os.environ["SENDER_EMAIL"] = sender
            os.environ["GMAIL_APP_PASSWORD"] = password
            os.environ["RECIPIENT_EMAIL"] = recipients_str
            os.environ["EXCEL_PATH"] = excel_path
            os.environ["RESET_DAY"] = reset_day
            os.environ["RESET_TIME"] = reset_time

            # 5. Crear acceso directo si el checkbox está marcado
            if self.check_shortcut.get() == 1:
                self.after(0, lambda: self._update_status("Creando acceso directo en el Escritorio...", "yellow"))
                if getattr(sys, 'frozen', False):
                    target_exe = sys.executable
                else:
                    # En modo desarrollo creamos el script ejecutable para pruebas
                    target_exe = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
                self._create_desktop_shortcut(target_exe)

            self.after(0, self._finish_success)
        except Exception as e:
            self.after(0, lambda err=e: self._handle_installation_error(err))

    def _create_desktop_shortcut(self, target_exe_path):
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        shortcut_path = os.path.join(desktop, "Lector OCR Cédula.lnk")
        working_dir = os.path.dirname(target_exe_path)
        icon_path = target_exe_path
        
        # Script en PowerShell para crear el acceso directo de forma nativa
        ps_command = (
            f'$WshShell = New-Object -ComObject WScript.Shell; '
            f'$Shortcut = $WshShell.CreateShortcut("{shortcut_path}"); '
            f'$Shortcut.TargetPath = "{target_exe_path}"; '
            f'$Shortcut.WorkingDirectory = "{working_dir}"; '
            f'$Shortcut.IconLocation = "{icon_path},0"; '
            f'$Shortcut.Save()'
        )
        try:
            subprocess.run(["powershell", "-Command", ps_command], capture_output=True, check=True)
            return True
        except Exception as e:
            print(f"Error al crear acceso directo: {e}")
            return False

    def _handle_installation_error(self, err):
        self._update_status("Error durante la instalación.", "red")
        self.btn_save.configure(state="normal")
        self.combo_day.configure(state="normal")
        self.combo_time.configure(state="normal")
        messagebox.showerror("Error de Instalación", f"No se pudo completar la instalación/guardado:\n{str(err)}")

    def _finish_success(self):
        self.success = True
        self._update_status("¡Instalación y Configuración completada!", "green")
        messagebox.showinfo("Configuración Completada", "La aplicación se ha configurado y está lista para iniciarse.")
        self.destroy()
        self.on_success_callback()
