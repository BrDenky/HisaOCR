import cv2
import threading
import time

class CameraStream:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = None
        self.frame = None
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
    def start(self):
        """
        Inicia el hilo secundario para leer los fotogramas de la cámara.
        """
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def _update(self):
        """
        Bucle interno que lee de la cámara.
        """
        # Intentar con el backend predeterminado de Windows (nativamente Media Foundation)
        self.cap = cv2.VideoCapture(self.camera_index)
        
        # Si no abre con el predeterminado, intentar con CAP_DSHOW como fallback
        if not self.cap or not self.cap.isOpened():
            if self.cap:
                self.cap.release()
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            
        # Configurar resoluciones preferidas
        if self.cap and self.cap.isOpened():
            # Intentar configurar compresión MJPG para evitar líneas de muestreo en YUY2 y parpadeos
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
        while self.running:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    with self.lock:
                        self.frame = frame.copy()
                else:
                    time.sleep(0.01)
            else:
                time.sleep(0.1)
                
        # Liberar recursos al salir del bucle
        if self.cap:
            self.cap.release()
            self.cap = None

    def get_frame(self):
        """
        Retorna una copia del último fotograma capturado en formato BGR de OpenCV.
        """
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
            return None

    def stop(self):
        """
        Detiene el hilo de la cámara y libera los recursos del dispositivo.
        """
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.5)
            self.thread = None
        if self.cap:
            self.cap.release()
            self.cap = None
        self.frame = None

    def change_camera(self, new_index):
        """
        Cambia el índice de la cámara de manera dinámica reiniciando el hilo.
        """
        self.stop()
        self.camera_index = new_index
        self.start()