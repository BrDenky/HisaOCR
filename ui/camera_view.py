import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
import cv2

class CameraView(ctk.CTkCanvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(bg="#151515", highlightthickness=0)
        
        self.photo_img = None
        self.current_frame = None  # Imagen BGR original de OpenCV
        self.scaled_width = 0
        self.scaled_height = 0
        self.offset_x = 0
        self.offset_y = 0
        self.scale_factor = 1.0
        
        # Dimensiones de la guía visual (proporción aproximada de la cédula)
        self.guide_width = 400
        self.guide_height = 250
        
        # Redibujar al cambiar tamaño de ventana
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        self.draw_overlay()

    def update_feed(self, frame):
        """
        Actualiza el canvas con el fotograma de la cámara.
        """
        if frame is None:
            return
            
        self.current_frame = frame.copy()
        
        canvas_w = self.winfo_width()
        canvas_h = self.winfo_height()
        
        if canvas_w <= 1 or canvas_h <= 1:
            return
            
        # Tamaño original de la cámara
        orig_h, orig_w = frame.shape[:2]
        
        # Mantener relación de aspecto al reescalar para el canvas
        scale_w = canvas_w / orig_w
        scale_h = canvas_h / orig_h
        self.scale_factor = min(scale_w, scale_h)
        
        self.scaled_width = int(orig_w * self.scale_factor)
        self.scaled_height = int(orig_h * self.scale_factor)
        
        # Calcular desfase para centrar la imagen en el canvas
        self.offset_x = (canvas_w - self.scaled_width) // 2
        self.offset_y = (canvas_h - self.scaled_height) // 2
        
        # Redimensionar el fotograma
        resized = cv2.resize(frame, (self.scaled_width, self.scaled_height))
        # Convertir de BGR a RGB
        rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Convertir a PhotoImage para Tkinter
        pil_img = Image.fromarray(rgb_frame)
        self.photo_img = ImageTk.PhotoImage(image=pil_img)
        
        # Limpiar canvas y pintar fotograma
        self.delete("all")
        self.create_image(self.offset_x, self.offset_y, image=self.photo_img, anchor=tk.NW)
        
        # Dibujar la cuadrícula y marcos guía sobre la imagen
        self.draw_overlay()

    def draw_overlay(self):
        """
        Dibuja una máscara de sombreado y una caja guía neon enfocada
        para alinear la cédula física.
        """
        canvas_w = self.winfo_width()
        canvas_h = self.winfo_height()
        
        if canvas_w <= 1 or canvas_h <= 1:
            return
            
        cx = canvas_w // 2
        cy = canvas_h // 2
        
        # Coordenadas del rectángulo guía (redimensionable proporcionalmente al feed de cámara)
        if self.scaled_width > 0:
            self.guide_width = int(self.scaled_width * 0.6)
            self.guide_height = int(self.guide_width / 1.6)
        else:
            self.guide_width = 400
            self.guide_height = 250

        x1 = cx - self.guide_width // 2
        y1 = cy - self.guide_height // 2
        x2 = cx + self.guide_width // 2
        y2 = cy + self.guide_height // 2
        
        # Máscara semitransparente (sombreado) usando stipple para simular transparencia
        # Superior
        self.create_rectangle(0, 0, canvas_w, y1, fill="#080808", stipple="gray50", outline="")
        # Inferior
        self.create_rectangle(0, y2, canvas_w, canvas_h, fill="#080808", stipple="gray50", outline="")
        # Izquierda
        self.create_rectangle(0, y1, x1, y2, fill="#080808", stipple="gray50", outline="")
        # Derecha
        self.create_rectangle(x2, y1, canvas_w, y2, fill="#080808", stipple="gray50", outline="")
        
        # Bordes neon de la caja guía principal
        self.create_rectangle(x1, y1, x2, y2, outline="#00f0ff", width=2)
        
        # Esquinas gruesas neon verde para efecto de escaneo/enfoque
        c_len = 25  # Longitud de las esquinas
        # Arriba-Izquierda
        self.create_line(x1, y1 + c_len, x1, y1, x1 + c_len, y1, fill="#39ff14", width=4)
        # Arriba-Derecha
        self.create_line(x2 - c_len, y1, x2, y1, x2, y1 + c_len, fill="#39ff14", width=4)
        # Abajo-Izquierda
        self.create_line(x1, y2 - c_len, x1, y2, x1 + c_len, y2, fill="#39ff14", width=4)
        # Abajo-Derecha
        self.create_line(x2 - c_len, y2, x2, y2, x2, y2 - c_len, fill="#39ff14", width=4)
        
        # Texto de ayuda
        self.create_text(cx, y1 - 20, text="ALINEE LA CÉDULA AQUÍ", fill="#00f0ff", font=("Helvetica", 11, "bold"))
        self.create_text(cx, y2 + 20, text="Posicione el documento de forma frontal y plana", fill="#e0e0e0", font=("Helvetica", 9))

    def get_cropped_card(self):
        """
        Recorta la región correspondiente a la caja guía neon en la resolución
        original del fotograma de la cámara.
        """
        if self.current_frame is None:
            return None
            
        canvas_w = self.winfo_width()
        canvas_h = self.winfo_height()
        
        cx = canvas_w // 2
        cy = canvas_h // 2
        
        # Caja guía en el espacio de coordenadas del canvas
        gx1 = cx - self.guide_width // 2
        gy1 = cy - self.guide_height // 2
        gx2 = cx + self.guide_width // 2
        gy2 = cy + self.guide_height // 2
        
        # 1. Desplazar restando el offset del centrado de imagen
        img_x1 = gx1 - self.offset_x
        img_y1 = gy1 - self.offset_y
        img_x2 = gx2 - self.offset_x
        img_y2 = gy2 - self.offset_y
        
        # 2. Dividir por el factor de escala para pasar a resolución original
        orig_x1 = int(img_x1 / self.scale_factor)
        orig_y1 = int(img_y1 / self.scale_factor)
        orig_x2 = int(img_x2 / self.scale_factor)
        orig_y2 = int(img_y2 / self.scale_factor)
        
        # Validar límites de la matriz de la imagen original
        orig_h, orig_w = self.current_frame.shape[:2]
        orig_x1 = max(0, min(orig_x1, orig_w - 1))
        orig_y1 = max(0, min(orig_y1, orig_h - 1))
        orig_x2 = max(0, min(orig_x2, orig_w - 1))
        orig_y2 = max(0, min(orig_y2, orig_h - 1))
        
        # Retornar el recorte de alta resolución
        crop = self.current_frame[orig_y1:orig_y2, orig_x1:orig_x2]
        return crop
