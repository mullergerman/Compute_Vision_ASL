#!/usr/bin/env python3

"""
Herramienta de configuración rápida para optimizar detección de manos
Ajusta automáticamente parámetros según el rendimiento de tu hardware
"""

import cv2
import numpy as np
import time
import sys
import mediapipe as mp

def test_basic_mediapipe_performance():
    """Prueba el rendimiento básico de MediaPipe en tu sistema"""
    print("🔍 Probando rendimiento básico de MediaPipe...")
    
    mp_hands = mp.solutions.hands
    
    # Configuraciones a probar
    configs = [
        {"name": "Conservative", "conf": 0.7, "track": 0.7},
        {"name": "Standard", "conf": 0.5, "track": 0.5},
        {"name": "Sensitive", "conf": 0.3, "track": 0.3},
        {"name": "Ultra-Sensitive", "conf": 0.1, "track": 0.1}
    ]
    
    # Crear imagen de prueba
    test_image = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
    
    # Simular una mano muy básica
    cv2.rectangle(test_image, (250, 150), (350, 300), (220, 180, 140), -1)
    cv2.circle(test_image, (300, 130), 30, (220, 180, 140), -1)
    
    results = {}
    
    for config in configs:
        hands = mp_hands.Hands(
            static_image_mode=True,
            max_num_hands=1,
            min_detection_confidence=config["conf"],
            min_tracking_confidence=config["track"]
        )
        
        # Probar 10 veces para obtener promedio
        times = []
        detections = 0
        
        for _ in range(10):
            start = time.perf_counter()
            result = hands.process(test_image)
            end = time.perf_counter()
            
            times.append((end - start) * 1000)
            if result.multi_hand_landmarks:
                detections += 1
        
        avg_time = np.mean(times)
        results[config["name"]] = {
            "avg_time_ms": avg_time,
            "detections": detections,
            "config": config
        }
        
        print(f"  {config['name']:15} - {avg_time:5.1f}ms avg, {detections}/10 detections")
        
        hands.close()
    
    return results

def recommend_configuration(perf_results):
    """Recomienda configuración basada en resultados de rendimiento"""
    print("\n💡 RECOMENDACIONES:")
    
    # Encontrar configuración más rápida que detecte algo
    fast_configs = []
    for name, data in perf_results.items():
        if data["detections"] > 0 and data["avg_time_ms"] < 50:  # Menos de 50ms
            fast_configs.append((name, data))
    
    if not fast_configs:
        print("⚠️  Tu sistema es lento para MediaPipe. Recomendaciones:")
        print("   1. Usa 'Standard' o 'Conservative' configuration")
        print("   2. Considera reducir resolución de imagen")
        print("   3. Procesa menos frames por segundo")
        return "Standard"
    
    # Ordenar por velocidad
    fast_configs.sort(key=lambda x: x[1]["avg_time_ms"])
    best_config = fast_configs[0]
    
    print(f"✅ Configuración recomendada: {best_config[0]}")
    print(f"   Tiempo promedio: {best_config[1]['avg_time_ms']:.1f}ms")
    print(f"   Tasa de detección: {best_config[1]['detections']}/10")
    
    return best_config[0]

def generate_optimized_config(recommended_config):
    """Genera configuración optimizada para tu sistema"""
    
    config_map = {
        "Conservative": {
            "min_detection_confidence": 0.7,
            "min_tracking_confidence": 0.7,
            "processing_interval": 0.12,  # 8 FPS
            "enhancement_threshold": 40    # Solo fondos muy complejos
        },
        "Standard": {
            "min_detection_confidence": 0.5,
            "min_tracking_confidence": 0.5,
            "processing_interval": 0.10,  # 10 FPS
            "enhancement_threshold": 30   # Fondos moderadamente complejos
        },
        "Sensitive": {
            "min_detection_confidence": 0.3,
            "min_tracking_confidence": 0.3,
            "processing_interval": 0.08,  # 12.5 FPS
            "enhancement_threshold": 25   # Fondos ligeramente complejos
        },
        "Ultra-Sensitive": {
            "min_detection_confidence": 0.1,
            "min_tracking_confidence": 0.1,
            "processing_interval": 0.15,  # 6.7 FPS (más lento pero más sensible)
            "enhancement_threshold": 20   # Casi cualquier fondo
        }
    }
    
    return config_map.get(recommended_config, config_map["Standard"])

def create_custom_detector(config):
    """Crea un archivo de detector personalizado basado en la configuración"""
    
    template = f'''
import cv2
import numpy as np
import mediapipe as mp
import time

class TunedHandDetector:
    """Detector de manos optimizado para tu hardware específico"""
    
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        
        # Configuración optimizada para tu sistema
        self.hands_detector = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence={config["min_detection_confidence"]},
            min_tracking_confidence={config["min_tracking_confidence"]},
        )
        
        self.processing_interval = {config["processing_interval"]}
        self.enhancement_threshold = {config["enhancement_threshold"]}
        self.last_process_time = 0
        
    def should_process_frame(self):
        """Determina si procesar el frame actual basado en timing"""
        current_time = time.time()
        if current_time - self.last_process_time >= self.processing_interval:
            self.last_process_time = current_time
            return True
        return False
    
    def needs_enhancement(self, image):
        """Determina si la imagen necesita preprocesamiento"""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        std_intensity = np.std(gray)
        return std_intensity < self.enhancement_threshold
    
    def enhance_image(self, image):
        """Mejoramiento ligero de imagen"""
        if not self.needs_enhancement(image):
            return image
            
        # Corrección gamma muy rápida
        mean_val = np.mean(image)
        if mean_val < 90:
            gamma = 0.8
            image = np.power(image / 255.0, gamma)
            image = (image * 255).astype(np.uint8)
        
        return image
    
    def detect_hands(self, image_rgb):
        """Detección optimizada de manos"""
        if not self.should_process_frame():
            return None, {{"skipped": True}}
            
        start_time = time.perf_counter()
        
        # Mejoramiento condicional
        processed_image = self.enhance_image(image_rgb)
        
        # Detección
        results = self.hands_detector.process(processed_image)
        
        end_time = time.perf_counter()
        
        metadata = {{
            "processing_time_ms": (end_time - start_time) * 1000,
            "hands_detected": len(results.multi_hand_landmarks) if results.multi_hand_landmarks else 0,
            "skipped": False
        }}
        
        return results, metadata
    
    def __del__(self):
        if hasattr(self, 'hands_detector'):
            self.hands_detector.close()

def create_tuned_detector():
    return TunedHandDetector()
'''
    
    with open("tuned_hand_detector.py", "w") as f:
        f.write(template)
    
    print(f"\n📁 Archivo generado: tuned_hand_detector.py")
    print(f"   Este detector está optimizado específicamente para tu hardware")

def main():
    print("🛠️  Quick Tune - Optimizador de Detección de Manos")
    print("=" * 55)
    
    try:
        # Probar rendimiento básico
        perf_results = test_basic_mediapipe_performance()
        
        # Obtener recomendación
        recommended = recommend_configuration(perf_results)
        
        # Generar configuración optimizada
        optimal_config = generate_optimized_config(recommended)
        
        print(f"\n⚙️  CONFIGURACIÓN OPTIMIZADA:")
        for key, value in optimal_config.items():
            print(f"   {key}: {value}")
        
        # Crear detector personalizado
        create_custom_detector(optimal_config)
        
        print(f"\n🚀 PRÓXIMOS PASOS:")
        print(f"   1. El detector optimizado se guardó como 'tuned_hand_detector.py'")
        print(f"   2. Puedes usarlo en lugar del detector actual:")
        print(f"      from tuned_hand_detector import create_tuned_detector")
        print(f"   3. Si la detección sigue siendo lenta, considera:")
        print(f"      - Reducir resolución de entrada")
        print(f"      - Procesar cada N frames en lugar de todos")
        print(f"      - Usar ROI (región de interés) más agresivo")
        
        # Mostrar integración rápida
        print(f"\n📝 INTEGRACIÓN RÁPIDA:")
        print(f"   Reemplaza en tu app.py:")
        print(f"   # hand_detector = LightweightHandDetectionOptimizer()")
        print(f"   hand_detector = create_tuned_detector()")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Cancelado por usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error durante la optimización: {{e}}")
        print(f"   Usando configuración estándar como fallback")

if __name__ == "__main__":
    main()
