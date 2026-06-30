import os
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
except Exception:
    pass


import cv2
import re
import numpy as np

class OCREngine:
    def __init__(self):
        # Inicialización diferida del lector para evitar congelar el inicio de la app
        self.reader = None

    def initialize_reader(self):
        """
        Inicializa el lector de PaddleOCR para el idioma español.
        Se ejecuta una sola vez al primer escaneo o inicio del módulo.
        """
        if self.reader is None:
            # paddleocr detecta automáticamente si hay GPU disponible y la usa.
            from paddleocr import PaddleOCR
            self.reader = PaddleOCR(use_textline_orientation=True, lang='es')
            
    def validate_ecuadorian_ci(self, ci_str):
        """
        Valida si una cédula ecuatoriana de 10 dígitos es correcta 
        según el algoritmo estándar del dígito verificador (módulo 10).
        """
        if not ci_str or len(ci_str) != 10 or not ci_str.isdigit():
            return False
            
        prov = int(ci_str[:2])
        # Las provincias válidas en Ecuador son del 01 al 24, y el 30 para ecuatorianos en el exterior
        if not (1 <= prov <= 24 or prov == 30):
            return False
            
        third = int(ci_str[2])
        # El tercer dígito debe ser menor a 6 para cédulas de personas naturales
        if third >= 6:
            return False
            
        coefs = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        total = 0
        for i in range(9):
            val = int(ci_str[i]) * coefs[i]
            if val >= 10:
                val -= 9
            total += val
            
        check_digit = int(ci_str[9])
        calc_check = (10 - (total % 10)) % 10
        return check_digit == calc_check

    def preprocess_image(self, bgr_image):
        """
        Preprocesa el recorte de imagen de la cámara.
        Convierte a escala de grises, escala para homogeneizar resolución, 
        y aplica CLAHE para corregir iluminación irregular y sombras.
        """
        # Convertir a escala de grises
        gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
        
        # Redimensionar si es muy pequeña para mejorar legibilidad del OCR
        h, w = gray.shape[:2]
        if w < 700:
            scale = 700.0 / w
            gray = cv2.resize(gray, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            
        # Aplicar ecualización de histograma adaptativa (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Filtro bilateral para reducir ruido preservando bordes nítidos de las letras
        filtered = cv2.bilateralFilter(enhanced, 9, 75, 75)
        
        return filtered

    def extract_data(self, bgr_image):
        """
        Ejecuta PaddleOCR en la imagen preprocesada y extrae la cédula (C.I.) y nombres.
        Retorna: (cédula_detectada, nombres_detectados)
        """
        self.initialize_reader()
        
        preprocessed = self.preprocess_image(bgr_image)
        
        # Si preprocessed es escala de grises (1 canal), convertir a BGR (3 canales) para PaddleOCR
        if len(preprocessed.shape) == 2:
            preprocessed = cv2.cvtColor(preprocessed, cv2.COLOR_GRAY2BGR)
            
        # Ejecutar PaddleOCR
        results = self.reader.predict(preprocessed)
        
        ci_candidates = []
        all_text_lines = []
        img_h, img_w = preprocessed.shape[:2]
        
        ci_regex = re.compile(r"\b\d{10}\b")
        
        if results and len(results) > 0:
            res_dict = results[0]
            rec_texts = res_dict.get('rec_texts', [])
            rec_scores = res_dict.get('rec_scores', [])
            rec_polys = res_dict.get('rec_polys', [])
            
            for i in range(len(rec_texts)):
                text = rec_texts[i]
                prob = rec_scores[i]
                bbox = rec_polys[i]
                
                text_clean = text.strip()
                if not text_clean:
                    continue
                    
                # Convertir a lista de puntos si es un array de numpy
                if hasattr(bbox, 'tolist'):
                    pts = bbox.tolist()
                else:
                    pts = list(bbox)
                    
                num_pts = len(pts)
                if num_pts > 0:
                    x_coords = [pt[0] for pt in pts]
                    y_coords = [pt[1] for pt in pts]
                    cx = sum(x_coords) / float(num_pts)
                    cy = sum(y_coords) / float(num_pts)
                else:
                    cx = 0.0
                    cy = 0.0
                    
                ncx = cx / img_w
                ncy = cy / img_h
                
                all_text_lines.append({
                    "text": text_clean,
                    "bbox": pts,
                    "prob": float(prob),
                    "ncx": ncx,
                    "ncy": ncy
                })
                
                # Intentar extraer dígitos eliminando caracteres no numéricos
                digits_only = re.sub(r"\D", "", text_clean)
                
                # Buscar patrones de 10 dígitos en la cadena limpia
                matches = ci_regex.findall(digits_only)
                for m in matches:
                    ci_candidates.append((m, float(prob)))
        
        # 1. Determinar la mejor cédula (que valide con el módulo 10)
        valid_ci = ""
        best_ci_prob = 0.0
        
        for ci, prob in ci_candidates:
            if self.validate_ecuadorian_ci(ci):
                if prob > best_ci_prob:
                    valid_ci = ci
                    best_ci_prob = prob
                    
        # Fallback si no hay ninguna válida con checksum: tomar el de mayor confianza
        if not valid_ci and ci_candidates:
            ci_candidates.sort(key=lambda x: x[1], reverse=True)
            valid_ci = ci_candidates[0][0]
            
        # 2. Determinar nombres (Algoritmo geométrico y espacial)
        nombres = ""
        apellidos_label = None
        nombres_label = None
        
        for line in all_text_lines:
            text_upper = line["text"].upper()
            if "APEL" in text_upper:
                apellidos_label = line
            elif "NOM" in text_upper:
                nombres_label = line
                
        surnames_list = []
        firstnames_list = []
        
        if apellidos_label:
            # Buscar candidatos de apellidos: abajo de la etiqueta y alineados horizontalmente (máximo 2 líneas, dy < 0.16)
            for line in all_text_lines:
                dy = line["ncy"] - apellidos_label["ncy"]
                dx = abs(line["ncx"] - apellidos_label["ncx"])
                if 0.01 < dy < 0.16 and dx < 0.15:
                    if self._is_valid_name_candidate(line["text"]):
                        surnames_list.append((line["text"], line["ncy"]))
            surnames_list.sort(key=lambda x: x[1])

        if nombres_label:
            # Buscar candidatos de nombres: abajo de la etiqueta y alineados horizontalmente (máximo 1 línea típica, dy < 0.12)
            for line in all_text_lines:
                dy = line["ncy"] - nombres_label["ncy"]
                dx = abs(line["ncx"] - nombres_label["ncx"])
                if 0.01 < dy < 0.12 and dx < 0.15:
                    if self._is_valid_name_candidate(line["text"]):
                        firstnames_list.append((line["text"], line["ncy"]))
            firstnames_list.sort(key=lambda x: x[1])
            
        surnames = " ".join([item[0] for item in surnames_list])
        firstnames = " ".join([item[0] for item in firstnames_list])
        
        if surnames or firstnames:
            nombres = f"{surnames} {firstnames}".strip()
            
        # Fallback espacial si no se encontró nada por etiquetas
        if not nombres:
            zone_candidates = []
            for line in all_text_lines:
                # Filtrar por zona espacial del nombre: X en [0.28, 0.70] e Y en [0.15, 0.52]
                if 0.28 <= line["ncx"] <= 0.70 and 0.15 <= line["ncy"] <= 0.52:
                    if self._is_valid_name_candidate(line["text"]):
                        zone_candidates.append(line)
            
            if zone_candidates:
                zone_candidates.sort(key=lambda x: x["ncy"])
                nombres = " ".join([line["text"] for line in zone_candidates])
                
        # Limpieza final del nombre
        nombres_clean = re.sub(r"[^A-ZÁÉÍÓÚÑa-zzáéíóúñ ]", "", nombres)
        nombres_clean = " ".join(nombres_clean.split()) # normalizar espacios
        
        return valid_ci, nombres_clean.upper()

    def _is_valid_name_candidate(self, text):
        """
        Valida si una línea de texto puede corresponder a un nombre.
        """
        text_upper = text.upper().strip()
        # No debe contener números
        if any(char.isdigit() for char in text):
            return False
        # Longitud razonable
        if len(text_upper) < 3:
            return False
        # Evitar cabeceras, metadatos y etiquetas comunes (incluyendo posibles errores del OCR)
        exclude_patterns = [
            "APEL",      # APELLIDOS, APELLDOS, APELIDOS
            "NOMB",      # NOMBRES, NOMERES
            "NOMA",      # NOMA (error del OCR)
            "NACI",      # NACIONALIDAD, NACION
            "VACI",      # VACION, VACION DAD
            "NADI",      # NADIONALIDAD
            "REPU",      # REPÚBLICA, REPUBLICA
            "ECUA",      # ECUADOR, ECUATORIANA, ECUATORIANO
            "CIVIL",     # CIVIL
            "REGIS",     # REGISTRO
            "DOCU",      # DOCUMENTO
            "ESTADO",    # ESTADO CIVIL
            "CONDIC",    # CONDICIÓN, CONDICION
            "CIUDAD",    # CIUDADANA, CIUDADANO, CIUDADANÍA
            "FIRMA",     # FIRMA
            "TITULAR",   # TITULAR
            "LUGAR",     # LUGAR
            "FECHA",     # FECHA
            "SEXO",      # SEXO
            "HOMBRE",    # HOMBRE
            "MUJER",     # MUJER
            "CADUC",     # CADUCIDAD
            "VENCIM",    # VENCIMIENTO
            "NUI"        # NUI
        ]
        if any(pattern in text_upper for pattern in exclude_patterns):
            return False
        # Debe ser predominantemente alfabético
        letters_only = re.sub(r"[^A-ZÁÉÍÓÚÑ ]", "", text_upper)
        if len(letters_only) < len(text_upper) * 0.7:
            return False
        return True
