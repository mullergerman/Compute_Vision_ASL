import cv2
import numpy as np
import mediapipe as mp
import time
from typing import Tuple, Optional, Dict, Any

class AdvancedHandDetectionOptimizer:
    """
    Optimizador avanzado para detección de manos en fondos con personas/caras
    Enfocado en distinguir manos de otras partes del cuerpo humano
    """
    
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.mp_face = mp.solutions.face_detection
        self.mp_pose = mp.solutions.pose
        
        # Detector de manos principal
        self.hands_detector = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.4,    # Ligeramente más estricto
            min_tracking_confidence=0.4,
        )
        
        # Detector de manos ultra sensible para casos difíciles
        self.hands_sensitive = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,  # Permitir 2 para filtrar mejor
            min_detection_confidence=0.2,
            min_tracking_confidence=0.2,
        )
        
        # Detectores auxiliares para filtrar falsos positivos
        self.face_detector = self.mp_face.FaceDetection(
            model_selection=0,
            min_detection_confidence=0.3
        )
        
        self.pose_detector = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,  # Más rápido
            smooth_landmarks=True,
            min_detection_confidence=0.3,
            min_tracking_confidence=0.3
        )
        
        self.consecutive_failures = 0
        self.max_consecutive_failures = 8
        self.last_hand_position = None
        self.position_history = []
        
    def detect_faces_and_poses(self, image_rgb: np.ndarray) -> Dict[str, Any]:
        """
        Detecta caras y poses para evitar confusiones con manos
        """
        height, width = image_rgb.shape[:2]
        
        # Reducir resolución para detección rápida de contexto
        scale_factor = 0.5
        small_image = cv2.resize(image_rgb, (int(width * scale_factor), int(height * scale_factor)))
        
        faces_info = {"faces": [], "face_regions": []}
        pose_info = {"pose_landmarks": None, "excluded_regions": []}
        
        try:
            # Detectar caras rápidamente
            face_results = self.face_detector.process(small_image)
            if face_results.detections:
                for detection in face_results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    # Escalar de vuelta a imagen original
                    x = int(bbox.xmin * width)
                    y = int(bbox.ymin * height) 
                    w = int(bbox.width * width)
                    h = int(bbox.height * height)
                    
                    # Expandir región de cara para evitar detección de manos cerca
                    expansion = 0.3
                    x_exp = max(0, x - int(w * expansion))
                    y_exp = max(0, y - int(h * expansion))
                    w_exp = min(width - x_exp, w + int(w * expansion * 2))
                    h_exp = min(height - y_exp, h + int(h * expansion * 2))
                    
                    faces_info["face_regions"].append((x_exp, y_exp, w_exp, h_exp))
                    faces_info["faces"].append((x, y, w, h))
            
            # Detectar pose rápidamente
            pose_results = self.pose_detector.process(small_image)
            if pose_results.pose_landmarks:
                pose_info["pose_landmarks"] = pose_results.pose_landmarks
                
                # Identificar regiones del torso/brazos para evitar
                landmarks = pose_results.pose_landmarks.landmark
                
                # Puntos clave del torso (escalados)
                shoulder_left = landmarks[11] if len(landmarks) > 11 else None
                shoulder_right = landmarks[12] if len(landmarks) > 12 else None
                
                if shoulder_left and shoulder_right:
                    # Región del torso a evitar
                    torso_x = int(min(shoulder_left.x, shoulder_right.x) * width)
                    torso_y = int(min(shoulder_left.y, shoulder_right.y) * height)
                    torso_w = int(abs(shoulder_right.x - shoulder_left.x) * width * 1.5)
                    torso_h = int(height * 0.4)  # 40% de la altura de la imagen
                    
                    pose_info["excluded_regions"].append((torso_x, torso_y, torso_w, torso_h))
                    
        except Exception as e:
            # Si falla la detección de contexto, continuar sin ella
            pass
        
        return {"faces": faces_info, "pose": pose_info}
    
    def is_hand_in_excluded_region(self, hand_landmarks, width: int, height: int, context_info: Dict) -> bool:
        """
        Verifica si la mano detectada está en una región que debería ser excluida
        """
        if not hand_landmarks or not hand_landmarks.landmark:
            return False
            
        # Calcular centro de la mano
        x_coords = [lm.x * width for lm in hand_landmarks.landmark]
        y_coords = [lm.y * height for lm in hand_landmarks.landmark]
        hand_center_x = sum(x_coords) / len(x_coords)
        hand_center_y = sum(y_coords) / len(y_coords)
        
        # Verificar si está en región de cara
        for face_region in context_info["faces"]["face_regions"]:
            fx, fy, fw, fh = face_region
            if (fx <= hand_center_x <= fx + fw and 
                fy <= hand_center_y <= fy + fh):
                return True
        
        # Verificar si está en región de torso
        for excluded_region in context_info["pose"]["excluded_regions"]:
            ex, ey, ew, eh = excluded_region
            if (ex <= hand_center_x <= ex + ew and 
                ey <= hand_center_y <= ey + eh):
                return True
                
        return False
    
    def calculate_hand_quality_score(self, hand_landmarks, width: int, height: int) -> float:
        """
        Calcula un score de calidad para determinar si es realmente una mano
        """
        if not hand_landmarks or not hand_landmarks.landmark:
            return 0.0
            
        landmarks = hand_landmarks.landmark
        
        # 1. Verificar proporciones típicas de una mano
        x_coords = [lm.x * width for lm in landmarks]
        y_coords = [lm.y * height for lm in landmarks]
        
        hand_width = max(x_coords) - min(x_coords)
        hand_height = max(y_coords) - min(y_coords)
        
        # Ratio típico de una mano (debe ser entre 0.6 y 1.4)
        aspect_ratio = hand_width / hand_height if hand_height > 0 else 0
        aspect_score = 1.0 if 0.6 <= aspect_ratio <= 1.4 else 0.3
        
        # 2. Verificar que los dedos estén en posiciones lógicas
        # Puntos clave de MediaPipe para dedos
        finger_tips = [4, 8, 12, 16, 20]  # Puntas de dedos
        finger_score = 0.0
        
        try:
            wrist = landmarks[0]
            wrist_y = wrist.y * height
            
            # Contar cuántas puntas están por encima de la muñeca (posición típica)
            tips_above_wrist = 0
            for tip_idx in finger_tips:
                if tip_idx < len(landmarks):
                    tip_y = landmarks[tip_idx].y * height
                    if tip_y < wrist_y:  # Punta por encima de muñeca
                        tips_above_wrist += 1
            
            finger_score = tips_above_wrist / len(finger_tips)
            
        except:
            finger_score = 0.5  # Score neutral si no se puede calcular
        
        # 3. Verificar variabilidad en las posiciones (no todos los puntos iguales)
        x_var = np.var(x_coords) if len(x_coords) > 1 else 0
        y_var = np.var(y_coords) if len(y_coords) > 1 else 0
        
        variability_score = min(1.0, (x_var + y_var) / 1000.0)
        
        # Score final combinado
        final_score = (aspect_score * 0.3 + finger_score * 0.5 + variability_score * 0.2)
        
        return min(1.0, max(0.0, final_score))
    
    def track_hand_position(self, hand_landmarks, width: int, height: int):
        """
        Hace seguimiento de la posición de la mano para detectar movimientos consistentes
        """
        if not hand_landmarks or not hand_landmarks.landmark:
            return
            
        # Calcular centro de la mano
        x_coords = [lm.x * width for lm in hand_landmarks.landmark]
        y_coords = [lm.y * height for lm in hand_landmarks.landmark]
        center = (sum(x_coords) / len(x_coords), sum(y_coords) / len(y_coords))
        
        self.position_history.append(center)
        
        # Mantener solo últimas 10 posiciones
        if len(self.position_history) > 10:
            self.position_history.pop(0)
            
        self.last_hand_position = center
    
    def is_hand_movement_consistent(self) -> bool:
        """
        Verifica si el movimiento de la mano es consistente (no saltos erráticos)
        """
        if len(self.position_history) < 3:
            return True  # Pocas muestras, asumir consistente
            
        # Calcular distancias entre posiciones consecutivas
        distances = []
        for i in range(1, len(self.position_history)):
            prev_x, prev_y = self.position_history[i-1]
            curr_x, curr_y = self.position_history[i]
            dist = np.sqrt((curr_x - prev_x)**2 + (curr_y - prev_y)**2)
            distances.append(dist)
        
        if not distances:
            return True
            
        # Si hay saltos muy grandes, probablemente es ruido
        avg_distance = np.mean(distances)
        max_distance = max(distances)
        
        # Si el salto máximo es más de 3x el promedio, es inconsistente
        return max_distance <= avg_distance * 3.0
    
    def detect_hands_with_context(self, image_rgb: np.ndarray) -> Tuple[Any, Dict[str, Any]]:
        """
        Detección avanzada de manos considerando el contexto de personas/caras
        """
        start_time = time.perf_counter()
        
        # 1. Detectar contexto (caras, poses) cada cierto tiempo para no ralentizar
        context_info = {"faces": {"faces": [], "face_regions": []}, "pose": {"pose_landmarks": None, "excluded_regions": []}}
        context_time = 0.0
        
        if self.consecutive_failures > 3:  # Solo cuando hay problemas
            context_start = time.perf_counter()
            context_info = self.detect_faces_and_poses(image_rgb)
            context_time = float((time.perf_counter() - context_start) * 1000)
        
        # 2. Detección inicial de manos
        detection_start = time.perf_counter()
        results = self.hands_detector.process(image_rgb)
        detection_time = float((time.perf_counter() - detection_start) * 1000)
        
        best_hand = None
        best_score = 0.0
        filtered_hands = 0
        
        # 3. Si no se detectó nada, usar detector más sensible
        if not results.multi_hand_landmarks and self.consecutive_failures >= 5:
            sensitive_start = time.perf_counter()
            results = self.hands_sensitive.process(image_rgb)
            detection_time += float((time.perf_counter() - sensitive_start) * 1000)
        
        # 4. Filtrar y evaluar manos detectadas
        if results.multi_hand_landmarks:
            height, width = image_rgb.shape[:2]
            
            for hand_landmarks in results.multi_hand_landmarks:
                # Verificar si está en región excluida
                if self.is_hand_in_excluded_region(hand_landmarks, width, height, context_info):
                    filtered_hands += 1
                    continue
                
                # Calcular score de calidad
                quality_score = self.calculate_hand_quality_score(hand_landmarks, width, height)
                
                # Verificar consistencia de movimiento
                self.track_hand_position(hand_landmarks, width, height)
                movement_consistent = self.is_hand_movement_consistent()
                
                # Score final considerando calidad y movimiento
                final_score = quality_score * (1.2 if movement_consistent else 0.8)
                
                if final_score > best_score:
                    best_score = final_score
                    best_hand = hand_landmarks
        
        # 5. Crear resultado final
        if best_hand and best_score >= 0.3:  # Umbral mínimo de calidad
            final_results = type('Results', (), {})()
            final_results.multi_hand_landmarks = [best_hand]
            self.consecutive_failures = 0
        else:
            final_results = type('Results', (), {})()
            final_results.multi_hand_landmarks = None
            self.consecutive_failures += 1
        
        # Reset contador si es muy alto
        if self.consecutive_failures > self.max_consecutive_failures * 2:
            self.consecutive_failures = 0
            self.position_history = []
        
        end_time = time.perf_counter()
        total_time = float((end_time - start_time) * 1000)
        
        metadata = {
            "total_time_ms": total_time,
            "detection_time_ms": detection_time,
            "context_time_ms": context_time,
            "hands_detected": 1 if best_hand and best_score >= 0.3 else 0,
            "hands_filtered": int(filtered_hands),
            "best_quality_score": float(best_score),
            "consecutive_failures": int(self.consecutive_failures),
            "faces_detected": len(context_info["faces"]["faces"]),
            "pose_detected": bool(context_info["pose"]["pose_landmarks"]),
            "movement_consistent": self.is_hand_movement_consistent()
        }
        
        return final_results, metadata
    
    def simple_landmark_validation(self, hand_landmarks, image_width: int, image_height: int) -> bool:
        """
        Validación básica de landmarks
        """
        if not hand_landmarks or not hand_landmarks.landmark:
            return False
        
        # Verificar variación mínima
        x_coords = [lm.x for lm in hand_landmarks.landmark[:5]]
        y_coords = [lm.y for lm in hand_landmarks.landmark[:5]]
        
        x_var = max(x_coords) - min(x_coords)
        y_var = max(y_coords) - min(y_coords)
        
        return bool(x_var > 0.02 and y_var > 0.02)
    
    def __del__(self):
        """Cleanup MediaPipe resources"""
        if hasattr(self, 'hands_detector'):
            self.hands_detector.close()
        if hasattr(self, 'hands_sensitive'):
            self.hands_sensitive.close()
        if hasattr(self, 'face_detector'):
            self.face_detector.close()
        if hasattr(self, 'pose_detector'):
            self.pose_detector.close()

# Función de conveniencia
def create_advanced_detector():
    """Crear una instancia del detector avanzado"""
    return AdvancedHandDetectionOptimizer()

if __name__ == "__main__":
    # Test básico
    detector = AdvancedHandDetectionOptimizer()
    print("AdvancedHandDetectionOptimizer creado exitosamente")
    
    # Test con imagen sintética
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    start = time.perf_counter()
    results, metadata = detector.detect_hands_with_context(test_image)
    end = time.perf_counter()
    
    print(f"Tiempo de procesamiento: {(end-start)*1000:.2f}ms")
    print(f"Metadata: {metadata}")
