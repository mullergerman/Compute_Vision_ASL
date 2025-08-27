import cv2
import numpy as np
import mediapipe as mp
import time
from typing import Tuple, Optional, Dict, Any

class HandDetectionOptimizer:
    """
    Optimizador de detección de manos para fondos complejos
    """
    
    def __init__(self):
        # Configuraciones múltiples de MediaPipe para diferentes escenarios
        self.mp_hands = mp.solutions.hands
        
        # Configuración para fondos simples (actual)
        self.hands_simple = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        
        # Configuración para fondos complejos (más sensible)
        self.hands_complex = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.3,  # Reducir umbral
            min_tracking_confidence=0.3,   # Reducir umbral
        )
        
        # Configuración ultra-sensible para casos difíciles
        self.hands_ultra_sensitive = self.mp_hands.Hands(
            static_image_mode=True,        # Más preciso pero más lento
            max_num_hands=1,
            min_detection_confidence=0.1,  # Muy bajo umbral
            min_tracking_confidence=0.1,
        )
        
        self.background_complexity_threshold = 30.0
        
    def analyze_background_complexity(self, image: np.ndarray) -> float:
        """
        Analiza la complejidad del fondo usando varianza de gradientes
        
        Returns:
            float: Score de complejidad (>30 = complejo, <30 = simple)
        """
        # Convertir a escala de grises
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # Calcular gradientes usando Sobel
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        
        # Magnitud del gradiente
        gradient_magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
        
        # Varianza como medida de complejidad
        complexity_score = np.var(gradient_magnitude)
        
        return complexity_score
    
    def preprocess_for_complex_background(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocesa la imagen para mejorar detección en fondos complejos
        """
        # 1. Mejora de contraste adaptativa (CLAHE)
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        
        # 2. Suavizado bilateral para reducir ruido manteniendo bordes
        smooth = cv2.bilateralFilter(enhanced, 9, 75, 75)
        
        # 3. Ajuste de gamma para resaltar tonos de piel
        gamma = 0.8  # Slightly darker to enhance skin tones
        gamma_corrected = np.power(smooth / 255.0, gamma)
        gamma_corrected = (gamma_corrected * 255).astype(np.uint8)
        
        return gamma_corrected
    
    def skin_color_enhancement(self, image: np.ndarray) -> np.ndarray:
        """
        Mejora específicamente los tonos de piel para mejor detección
        """
        # Convertir a HSV para manipulación de color más fácil
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        
        # Rangos de color de piel en HSV
        lower_skin = np.array([0, 20, 70], dtype=np.uint8)
        upper_skin = np.array([20, 255, 255], dtype=np.uint8)
        
        # Crear máscara de piel
        skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
        
        # Dilatar la máscara para incluir más área
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel)
        skin_mask = cv2.dilate(skin_mask, kernel, iterations=2)
        
        # Aplicar un ligero desenfoque gaussiano a la máscara
        skin_mask = cv2.GaussianBlur(skin_mask, (15, 15), 0)
        
        # Crear imagen mejorada donde las áreas de piel son más brillantes
        enhanced = image.copy()
        
        # Normalizar máscara a 0-1
        skin_mask_norm = skin_mask.astype(np.float32) / 255.0
        
        # Aumentar brillo en áreas de piel
        for i in range(3):  # Para cada canal RGB
            enhanced[:, :, i] = enhanced[:, :, i] * (1 + 0.3 * skin_mask_norm)
        
        # Clip valores para evitar overflow
        enhanced = np.clip(enhanced, 0, 255).astype(np.uint8)
        
        return enhanced
    
    def detect_hands_adaptive(self, image_rgb: np.ndarray) -> Tuple[Any, Dict[str, Any]]:
        """
        Detección adaptativa de manos basada en complejidad del fondo
        
        Returns:
            Tuple: (resultados_mediapipe, metadata)
        """
        start_time = time.perf_counter()
        
        # Analizar complejidad del fondo
        complexity_score = self.analyze_background_complexity(image_rgb)
        
        # Determinar estrategia basada en complejidad
        if complexity_score < 15:
            # Fondo muy simple - usar configuración estándar
            strategy = "simple"
            processed_image = image_rgb
            hands_detector = self.hands_simple
            
        elif complexity_score < 40:
            # Fondo moderadamente complejo
            strategy = "moderate"
            processed_image = self.preprocess_for_complex_background(image_rgb)
            hands_detector = self.hands_complex
            
        else:
            # Fondo muy complejo - usar todas las optimizaciones
            strategy = "complex"
            processed_image = self.preprocess_for_complex_background(image_rgb)
            processed_image = self.skin_color_enhancement(processed_image)
            hands_detector = self.hands_complex
        
        # Detección inicial
        results = hands_detector.process(processed_image)
        
        # Si no se detecta nada en fondo complejo, intentar con configuración ultra-sensible
        if not results.multi_hand_landmarks and strategy in ["moderate", "complex"]:
            results_ultra = self.hands_ultra_sensitive.process(processed_image)
            if results_ultra.multi_hand_landmarks:
                results = results_ultra
                strategy += "_ultra"
        
        end_time = time.perf_counter()
        processing_time = (end_time - start_time) * 1000
        
        metadata = {
            "complexity_score": complexity_score,
            "strategy": strategy,
            "processing_time_ms": processing_time,
            "hands_detected": len(results.multi_hand_landmarks) if results.multi_hand_landmarks else 0
        }
        
        return results, metadata
    
    def validate_landmarks(self, hand_landmarks, image_width: int, image_height: int) -> bool:
        """
        Valida que los landmarks detectados sean realistas
        """
        if not hand_landmarks or not hand_landmarks.landmark:
            return False
        
        # Verificar que los landmarks estén dentro de la imagen
        for lm in hand_landmarks.landmark:
            x, y = lm.x * image_width, lm.y * image_height
            if x < 0 or x >= image_width or y < 0 or y >= image_height:
                return False
        
        # Verificar que la mano tenga un tamaño razonable
        x_coords = [lm.x * image_width for lm in hand_landmarks.landmark]
        y_coords = [lm.y * image_height for lm in hand_landmarks.landmark]
        
        hand_width = max(x_coords) - min(x_coords)
        hand_height = max(y_coords) - min(y_coords)
        
        # La mano debe ocupar al menos 5% del ancho/alto de la imagen
        min_size = min(image_width, image_height) * 0.05
        
        return hand_width > min_size and hand_height > min_size
    
    def __del__(self):
        """Cleanup MediaPipe resources"""
        if hasattr(self, 'hands_simple'):
            self.hands_simple.close()
        if hasattr(self, 'hands_complex'):
            self.hands_complex.close()
        if hasattr(self, 'hands_ultra_sensitive'):
            self.hands_ultra_sensitive.close()

# Función de conveniencia para integración fácil
def create_optimized_detector():
    """Crear una instancia del detector optimizado"""
    return HandDetectionOptimizer()

# Ejemplo de uso
if __name__ == "__main__":
    # Test básico
    optimizer = HandDetectionOptimizer()
    print("HandDetectionOptimizer creado exitosamente")
    print(f"Umbral de complejidad: {optimizer.background_complexity_threshold}")
