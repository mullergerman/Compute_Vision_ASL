import cv2
import numpy as np
import mediapipe as mp
import time
from typing import Tuple, Optional, Dict, Any

class LightweightHandDetectionOptimizer:
    """
    Optimizador ligero y eficiente para detección de manos en fondos complejos
    Enfocado en velocidad y efectividad práctica
    """
    
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        
        # Configuración única optimizada para velocidad y efectividad
        self.hands_detector = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.3,    # Reducido del 0.5 original
            min_tracking_confidence=0.3,     # Reducido del 0.5 original
        )
        
        # Configuración de respaldo solo para casos críticos
        self.hands_fallback = self.mp_hands.Hands(
            static_image_mode=True,
            max_num_hands=1,
            min_detection_confidence=0.2,    # Más sensible
            min_tracking_confidence=0.2,
        )
        
        self.use_fallback = False
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        
    def quick_background_check(self, image: np.ndarray) -> bool:
        """
        Verificación rápida si el fondo es problemático
        Returns True si es un fondo complejo que necesita procesamiento extra
        """
        # Convertir a escala de grises para análisis rápido
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # Calcular estadísticas básicas muy rápido
        mean_intensity = np.mean(gray)
        std_intensity = np.std(gray)
        
        # Detectar condiciones problemáticas específicas
        is_too_dark = mean_intensity < 60       # Muy oscuro
        is_too_bright = mean_intensity > 220    # Muy brillante
        is_low_contrast = std_intensity < 25    # Poco contraste
        is_high_noise = std_intensity > 80      # Mucho ruido/complejidad
        
        return is_too_dark or is_too_bright or is_low_contrast or is_high_noise
    
    def fast_image_enhancement(self, image: np.ndarray) -> np.ndarray:
        """
        Mejoras rápidas y ligeras de imagen (< 5ms)
        """
        # 1. Corrección rápida de gamma solo si es necesario
        mean_val = np.mean(image)
        if mean_val < 80:  # Imagen muy oscura
            gamma = 0.7  # Aclarar
            image = np.power(image / 255.0, gamma)
            image = (image * 255).astype(np.uint8)
        elif mean_val > 200:  # Imagen muy brillante
            gamma = 1.3  # Oscurecer
            image = np.power(image / 255.0, gamma)
            image = (image * 255).astype(np.uint8)
        
        # 2. Realce de contraste muy ligero usando CV2
        if np.std(image) < 30:  # Solo si hay poco contraste
            lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
            l_channel = lab[:, :, 0]
            
            # CLAHE ligero solo en canal L
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
            lab[:, :, 0] = clahe.apply(l_channel)
            
            image = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        
        return image
    
    def smart_roi_detection(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Detecta región de interés probable para la mano (muy rápido)
        Reduce el área de procesamiento para MediaPipe
        """
        height, width = image.shape[:2]
        
        # Convertir a HSV para detección de piel rápida
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        
        # Rango amplio de tonos de piel
        lower_skin = np.array([0, 15, 50])
        upper_skin = np.array([25, 255, 255])
        
        # Crear máscara de piel
        skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
        
        # Limpiar ruido rápido
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel)
        
        # Encontrar el contorno más grande (posible mano)
        contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
            
        # Obtener el contorno más grande
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)
        
        # Verificar que el área sea significativa
        min_area = (width * height) * 0.01  # Al menos 1% de la imagen
        if area < min_area:
            return None
        
        # Obtener bounding box expandido
        x, y, w, h = cv2.boundingRect(largest_contour)
        
        # Expandir ROI un poco para capturar toda la mano
        expansion = 0.2
        x_exp = max(0, int(x - w * expansion))
        y_exp = max(0, int(y - h * expansion))
        w_exp = min(width - x_exp, int(w * (1 + 2 * expansion)))
        h_exp = min(height - y_exp, int(h * (1 + 2 * expansion)))
        
        # Extraer ROI
        roi = image[y_exp:y_exp + h_exp, x_exp:x_exp + w_exp]
        
        return roi, (x_exp, y_exp, w_exp, h_exp)
    
    def detect_hands_optimized(self, image_rgb: np.ndarray) -> Tuple[Any, Dict[str, Any]]:
        """
        Detección optimizada y ligera de manos
        """
        start_time = time.perf_counter()
        original_height, original_width = image_rgb.shape[:2]
        
        # 1. Verificación rápida del fondo
        needs_enhancement = self.quick_background_check(image_rgb)
        
        # 2. Procesar imagen solo si es necesario
        processed_image = image_rgb
        enhancement_time = 0
        
        if needs_enhancement:
            enhance_start = time.perf_counter()
            processed_image = self.fast_image_enhancement(image_rgb)
            enhancement_time = (time.perf_counter() - enhance_start) * 1000
        
        # 3. Intentar detección con ROI inteligente para acelerar
        roi_time = 0
        use_roi = False
        
        if needs_enhancement and self.consecutive_failures > 2:
            roi_start = time.perf_counter()
            roi_result = self.smart_roi_detection(processed_image)
            roi_time = (time.perf_counter() - roi_start) * 1000
            
            if roi_result is not None:
                roi_image, (roi_x, roi_y, roi_w, roi_h) = roi_result
                
                # Procesar solo el ROI con MediaPipe (mucho más rápido)
                detection_start = time.perf_counter()
                results = self.hands_detector.process(roi_image)
                detection_time = (time.perf_counter() - detection_start) * 1000
                
                # Ajustar coordenadas de vuelta a imagen completa
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        for landmark in hand_landmarks.landmark:
                            # Convertir coordenadas ROI a coordenadas globales
                            landmark.x = (landmark.x * roi_w + roi_x) / original_width
                            landmark.y = (landmark.y * roi_h + roi_y) / original_height
                
                use_roi = True
            else:
                # Fallback: procesar imagen completa
                detection_start = time.perf_counter()
                results = self.hands_detector.process(processed_image)
                detection_time = (time.perf_counter() - detection_start) * 1000
        else:
            # Procesamiento estándar rápido
            detection_start = time.perf_counter()
            results = self.hands_detector.process(processed_image)
            detection_time = (time.perf_counter() - detection_start) * 1000
        
        # 4. Usar fallback solo si es crítico y no se detectó nada
        used_fallback = False
        if not results.multi_hand_landmarks and self.consecutive_failures >= self.max_consecutive_failures:
            fallback_start = time.perf_counter()
            fallback_results = self.hands_fallback.process(processed_image)
            fallback_time = (time.perf_counter() - fallback_start) * 1000
            
            if fallback_results.multi_hand_landmarks:
                results = fallback_results
                detection_time += fallback_time
                used_fallback = True
        
        # 5. Actualizar contador de fallos
        if results.multi_hand_landmarks:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
        
        # Resetear contador si es muy alto
        if self.consecutive_failures > self.max_consecutive_failures * 2:
            self.consecutive_failures = 0
        
        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000
        
        metadata = {
            "total_time_ms": total_time,
            "detection_time_ms": detection_time,
            "enhancement_time_ms": enhancement_time,
            "roi_time_ms": roi_time,
            "hands_detected": len(results.multi_hand_landmarks) if results.multi_hand_landmarks else 0,
            "needs_enhancement": needs_enhancement,
            "used_roi": use_roi,
            "used_fallback": used_fallback,
            "consecutive_failures": self.consecutive_failures
        }
        
        return results, metadata
    
    def simple_landmark_validation(self, hand_landmarks, image_width: int, image_height: int) -> bool:
        """
        Validación muy básica y rápida de landmarks
        """
        if not hand_landmarks or not hand_landmarks.landmark:
            return False
        
        # Solo verificar que no estén todos en el mismo punto (detección fallida)
        x_coords = [lm.x for lm in hand_landmarks.landmark[:5]]  # Solo primeros 5 puntos
        y_coords = [lm.y for lm in hand_landmarks.landmark[:5]]
        
        # Si la variación es muy pequeña, probablemente es un error
        x_var = max(x_coords) - min(x_coords)
        y_var = max(y_coords) - min(y_coords)
        
        return x_var > 0.02 and y_var > 0.02  # Al menos 2% de variación
    
    def __del__(self):
        """Cleanup MediaPipe resources"""
        if hasattr(self, 'hands_detector'):
            self.hands_detector.close()
        if hasattr(self, 'hands_fallback'):
            self.hands_fallback.close()

# Función de conveniencia
def create_lightweight_detector():
    """Crear una instancia del detector ligero"""
    return LightweightHandDetectionOptimizer()

if __name__ == "__main__":
    # Test básico de rendimiento
    detector = LightweightHandDetectionOptimizer()
    print("LightweightHandDetectionOptimizer creado exitosamente")
    
    # Test con imagen sintética
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    start = time.perf_counter()
    results, metadata = detector.detect_hands_optimized(test_image)
    end = time.perf_counter()
    
    print(f"Tiempo de procesamiento: {(end-start)*1000:.2f}ms")
    print(f"Metadata: {metadata}")
