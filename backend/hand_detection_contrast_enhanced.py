import cv2
import numpy as np
import mediapipe as mp
import time
from typing import Tuple, Optional, Dict, Any

class ContrastEnhancedHandDetector:
    """
    Detector súper avanzado para manos en fondos de color similar
    Combina múltiples técnicas de realce de contraste y análisis espectral
    """
    
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.mp_face = mp.solutions.face_detection
        
        # Detector principal con configuración balanced
        self.hands_detector = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.35,
            min_tracking_confidence=0.35,
        )
        
        # Detector súper sensible para fondos difíciles
        self.hands_ultra_sensitive = self.mp_hands.Hands(
            static_image_mode=True,  # Más preciso para casos difíciles
            max_num_hands=2,
            min_detection_confidence=0.15,  # Muy bajo para fondos similares
            min_tracking_confidence=0.15,
        )
        
        # Detector de caras para contexto
        self.face_detector = self.mp_face.FaceDetection(
            model_selection=0,
            min_detection_confidence=0.3
        )
        
        self.consecutive_failures = 0
        self.max_failures = 10
        self.position_history = []
        self.contrast_history = []
        
        # Parámetros adaptativos
        self.adaptive_gamma = 1.0
        self.adaptive_contrast = 1.0
        
    def analyze_skin_background_similarity(self, image_rgb: np.ndarray) -> Dict[str, float]:
        """
        Analiza qué tan similar es el fondo al color de piel
        """
        height, width = image_rgb.shape[:2]
        
        # Convertir a diferentes espacios de color para análisis
        hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
        lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
        yuv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2YUV)
        
        # Definir rangos de piel en diferentes espacios
        # HSV - Rango amplio de tonos de piel
        skin_hsv_lower = np.array([0, 15, 50])
        skin_hsv_upper = np.array([35, 255, 255])
        skin_mask_hsv = cv2.inRange(hsv, skin_hsv_lower, skin_hsv_upper)
        
        # YUV - Mejor para detectar tonos de piel diversos
        skin_yuv_lower = np.array([80, 85, 90])
        skin_yuv_upper = np.array([255, 135, 180])
        skin_mask_yuv = cv2.inRange(yuv, skin_yuv_lower, skin_yuv_upper)
        
        # LAB - Excelente para separar luminancia de cromaticidad  
        skin_lab_lower = np.array([20, 15, 20])
        skin_lab_upper = np.array([200, 165, 170])
        skin_mask_lab = cv2.inRange(lab, skin_lab_lower, skin_lab_upper)
        
        # Combinar máscaras con pesos diferentes
        combined_mask = (
            skin_mask_hsv * 0.4 + 
            skin_mask_yuv * 0.35 + 
            skin_mask_lab * 0.25
        ).astype(np.uint8)
        
        # Calcular porcentaje de área que parece piel
        total_pixels = width * height
        skin_pixels_hsv = np.sum(skin_mask_hsv > 0)
        skin_pixels_yuv = np.sum(skin_mask_yuv > 0)
        skin_pixels_lab = np.sum(skin_mask_lab > 0)
        skin_pixels_combined = np.sum(combined_mask > 128)
        
        skin_percentage_hsv = (skin_pixels_hsv / total_pixels) * 100
        skin_percentage_yuv = (skin_pixels_yuv / total_pixels) * 100
        skin_percentage_lab = (skin_pixels_lab / total_pixels) * 100
        skin_percentage_combined = (skin_pixels_combined / total_pixels) * 100
        
        # Calcular uniformidad del color (menor = más uniforme)
        std_dev_rgb = np.std(image_rgb.reshape(-1, 3), axis=0).mean()
        std_dev_hsv = np.std(hsv.reshape(-1, 3), axis=0).mean()
        
        return {
            "skin_percentage_hsv": float(skin_percentage_hsv),
            "skin_percentage_yuv": float(skin_percentage_yuv), 
            "skin_percentage_lab": float(skin_percentage_lab),
            "skin_percentage_combined": float(skin_percentage_combined),
            "color_uniformity_rgb": float(std_dev_rgb),
            "color_uniformity_hsv": float(std_dev_hsv),
            "is_challenging_background": bool(
                skin_percentage_combined > 25 and std_dev_rgb < 35
            )
        }
    
    def apply_advanced_contrast_enhancement(self, image_rgb: np.ndarray, skin_analysis: Dict) -> np.ndarray:
        """
        Aplica realce de contraste específico para fondos de color similar
        """
        enhanced_image = image_rgb.copy()
        
        # Técnica 1: Realce adaptativo basado en análisis de piel
        if skin_analysis["is_challenging_background"]:
            
            # A. Separación de canales L*a*b* para mejor manipulación de color
            lab = cv2.cvtColor(enhanced_image, cv2.COLOR_RGB2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            
            # B. CLAHE adaptativo en canal L (luminancia)
            clahe_strength = min(4.0, 2.0 + skin_analysis["skin_percentage_combined"] / 20)
            clahe = cv2.createCLAHE(clipLimit=clahe_strength, tileGridSize=(6, 6))
            l_enhanced = clahe.apply(l_channel)
            
            # C. Realce sutil de canales a* y b* (cromaticidad)
            a_enhanced = cv2.multiply(a_channel, 1.15)  # Realzar verde-rojo
            b_enhanced = cv2.multiply(b_channel, 1.1)   # Realzar azul-amarillo
            
            # D. Recombinar canales LAB
            lab_enhanced = cv2.merge([l_enhanced, a_enhanced, b_enhanced])
            enhanced_image = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)
        
        # Técnica 2: Filtro bilateral adaptativo
        if skin_analysis["color_uniformity_rgb"] < 30:  # Fondo muy uniforme
            # Preservar bordes mientras suaviza áreas uniformes
            bilateral_d = 9 if skin_analysis["is_challenging_background"] else 7
            bilateral_sigma = 75 if skin_analysis["is_challenging_background"] else 50
            enhanced_image = cv2.bilateralFilter(enhanced_image, bilateral_d, bilateral_sigma, bilateral_sigma)
        
        # Técnica 3: Corrección gamma adaptativa
        if skin_analysis["skin_percentage_combined"] > 30:
            # Calcular gamma óptimo basado en análisis
            mean_brightness = np.mean(cv2.cvtColor(enhanced_image, cv2.COLOR_RGB2GRAY))
            
            if mean_brightness < 100:
                gamma = 0.8  # Aclarar imagen oscura
            elif mean_brightness > 180:
                gamma = 1.2  # Oscurecer imagen muy clara
            else:
                gamma = 0.9  # Ligero ajuste para resaltar contraste
                
            self.adaptive_gamma = gamma
            gamma_corrected = np.power(enhanced_image / 255.0, gamma)
            enhanced_image = (gamma_corrected * 255).astype(np.uint8)
        
        # Técnica 4: Realce de bordes sutil usando Unsharp Masking
        if skin_analysis["is_challenging_background"]:
            # Crear versión desenfocada
            blurred = cv2.GaussianBlur(enhanced_image, (3, 3), 1.0)
            
            # Máscara de realce (diferencia entre original y desenfocada)
            unsharp_mask = cv2.subtract(enhanced_image, blurred)
            
            # Aplicar máscara con peso adaptativo
            strength = 0.3 if skin_analysis["skin_percentage_combined"] > 40 else 0.2
            enhanced_image = cv2.addWeighted(enhanced_image, 1.0, unsharp_mask, strength, 0)
        
        return enhanced_image
    
    def apply_spectral_hand_enhancement(self, image_rgb: np.ndarray) -> np.ndarray:
        """
        Realza específicamente las características espectrales de las manos
        """
        # Convertir a HSV para manipulación selectiva
        hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
        h, s, v = cv2.split(hsv)
        
        # Crear máscara más precisa para tonos de piel de manos
        # Rango más específico que excluye fondos similares
        hand_hue_lower = 5   # Más específico que el rango general de piel
        hand_hue_upper = 25
        hand_sat_lower = 30  # Manos tienden a tener más saturación que paredes
        hand_val_lower = 60
        
        # Máscara para posibles regiones de mano
        mask_h = cv2.inRange(h, hand_hue_lower, hand_hue_upper)
        mask_s = cv2.inRange(s, hand_sat_lower, 255)
        mask_v = cv2.inRange(v, hand_val_lower, 255)
        
        # Combinar máscaras
        hand_mask = cv2.bitwise_and(cv2.bitwise_and(mask_h, mask_s), mask_v)
        
        # Limpiar la máscara con operaciones morfológicas
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        hand_mask = cv2.morphologyEx(hand_mask, cv2.MORPH_OPEN, kernel)
        hand_mask = cv2.morphologyEx(hand_mask, cv2.MORPH_CLOSE, kernel)
        
        # Aplicar realce solo en regiones potenciales de mano
        enhanced_image = image_rgb.copy()
        
        if np.sum(hand_mask) > 1000:  # Si hay suficiente área potencial
            # Realzar contraste local en regiones de mano
            mask_normalized = hand_mask.astype(np.float32) / 255.0
            
            # Aplicar realce gradual
            for i in range(3):  # Para cada canal RGB
                channel = enhanced_image[:, :, i].astype(np.float32)
                
                # Realzar contraste local
                enhanced_channel = cv2.multiply(channel, 1.0 + 0.2 * mask_normalized)
                
                # Asegurar rango válido
                enhanced_image[:, :, i] = np.clip(enhanced_channel, 0, 255).astype(np.uint8)
        
        return enhanced_image
    
    def detect_hands_with_contrast_enhancement(self, image_rgb: np.ndarray) -> Tuple[Any, Dict[str, Any]]:
        """
        Detección de manos con realce de contraste avanzado
        """
        start_time = time.perf_counter()
        
        # 1. Analizar similaridad con color de piel
        analysis_start = time.perf_counter()
        skin_analysis = self.analyze_skin_background_similarity(image_rgb)
        analysis_time = float((time.perf_counter() - analysis_start) * 1000)
        
        # 2. Decidir si aplicar técnicas avanzadas
        needs_enhancement = (
            skin_analysis["is_challenging_background"] or 
            self.consecutive_failures > 3
        )
        
        # 3. Aplicar realces si es necesario
        processed_image = image_rgb
        enhancement_time = 0.0
        
        if needs_enhancement:
            enhance_start = time.perf_counter()
            
            # Aplicar realce de contraste avanzado
            processed_image = self.apply_advanced_contrast_enhancement(image_rgb, skin_analysis)
            
            # Si aún es muy desafiante, aplicar realce espectral específico
            if skin_analysis["skin_percentage_combined"] > 35:
                processed_image = self.apply_spectral_hand_enhancement(processed_image)
            
            enhancement_time = float((time.perf_counter() - enhance_start) * 1000)
        
        # 4. Detección con configuración apropiada
        detection_start = time.perf_counter()
        
        if skin_analysis["is_challenging_background"]:
            # Usar detector ultra-sensible para casos difíciles
            results = self.hands_ultra_sensitive.process(processed_image)
        else:
            # Usar detector estándar
            results = self.hands_detector.process(processed_image)
            
        detection_time = float((time.perf_counter() - detection_start) * 1000)
        
        # 5. Post-procesamiento y validación
        valid_hands = []
        if results.multi_hand_landmarks:
            height, width = image_rgb.shape[:2]
            
            for hand_landmarks in results.multi_hand_landmarks:
                # Validar que la mano sea consistente con el contexto
                if self.validate_hand_in_context(hand_landmarks, width, height, skin_analysis):
                    valid_hands.append(hand_landmarks)
        
        # 6. Actualizar contadores y adaptación
        if valid_hands:
            self.consecutive_failures = 0
            # Actualizar parámetros adaptativos basados en éxito
            if skin_analysis["is_challenging_background"]:
                self.adaptive_contrast = min(1.3, self.adaptive_contrast + 0.05)
        else:
            self.consecutive_failures += 1
            
        # Reset si es muy alto
        if self.consecutive_failures > self.max_failures:
            self.consecutive_failures = 0
            self.adaptive_gamma = 1.0
            self.adaptive_contrast = 1.0
        
        # 7. Crear resultado final
        final_results = type('Results', (), {})()
        final_results.multi_hand_landmarks = valid_hands if valid_hands else None
        
        end_time = time.perf_counter()
        total_time = float((end_time - start_time) * 1000)
        
        metadata = {
            "total_time_ms": total_time,
            "analysis_time_ms": analysis_time,
            "enhancement_time_ms": enhancement_time,
            "detection_time_ms": detection_time,
            "hands_detected": len(valid_hands),
            "skin_similarity": skin_analysis,
            "needs_enhancement": needs_enhancement,
            "consecutive_failures": int(self.consecutive_failures),
            "adaptive_gamma": float(self.adaptive_gamma),
            "adaptive_contrast": float(self.adaptive_contrast)
        }
        
        return final_results, metadata
    
    def validate_hand_in_context(self, hand_landmarks, width: int, height: int, skin_analysis: Dict) -> bool:
        """
        Validación contextual de la mano detectada
        """
        if not hand_landmarks or not hand_landmarks.landmark:
            return False
        
        # 1. Validación básica de variabilidad
        x_coords = [lm.x for lm in hand_landmarks.landmark]
        y_coords = [lm.y for lm in hand_landmarks.landmark]
        
        x_var = max(x_coords) - min(x_coords)
        y_var = max(y_coords) - min(y_coords)
        
        if x_var < 0.02 or y_var < 0.02:
            return False
        
        # 2. Validación específica para fondos desafiantes
        if skin_analysis["is_challenging_background"]:
            # Requerir mayor variabilidad en fondos similares
            if x_var < 0.05 or y_var < 0.05:
                return False
            
            # Verificar que tenga estructura de mano realista
            wrist = hand_landmarks.landmark[0]
            middle_finger_tip = hand_landmarks.landmark[12]
            
            # La distancia muñeca-dedo medio debe ser razonable
            distance = np.sqrt(
                (wrist.x - middle_finger_tip.x)**2 + 
                (wrist.y - middle_finger_tip.y)**2
            )
            
            if distance < 0.08:  # Muy pequeña para ser una mano real
                return False
        
        return True
    
    def simple_landmark_validation(self, hand_landmarks, image_width: int, image_height: int) -> bool:
        """Validación básica rápida"""
        return self.validate_hand_in_context(
            hand_landmarks, image_width, image_height, 
            {"is_challenging_background": False}
        )
    
    def __del__(self):
        """Cleanup MediaPipe resources"""
        if hasattr(self, 'hands_detector'):
            self.hands_detector.close()
        if hasattr(self, 'hands_ultra_sensitive'):
            self.hands_ultra_sensitive.close()
        if hasattr(self, 'face_detector'):
            self.face_detector.close()

def create_contrast_enhanced_detector():
    """Crear instancia del detector con realce de contraste"""
    return ContrastEnhancedHandDetector()

if __name__ == "__main__":
    detector = ContrastEnhancedHandDetector()
    print("ContrastEnhancedHandDetector creado exitosamente")
    
    # Test con imagen sintética de color similar a piel
    test_image = np.ones((480, 640, 3), dtype=np.uint8)
    test_image[:, :] = [220, 180, 150]  # Color similar a piel
    
    start = time.perf_counter()
    results, metadata = detector.detect_hands_with_contrast_enhancement(test_image)
    end = time.perf_counter()
    
    print(f"Tiempo de procesamiento: {(end-start)*1000:.2f}ms")
    print(f"Metadata: {metadata}")
