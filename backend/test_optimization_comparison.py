#!/usr/bin/env python3

"""
Script de prueba para comparar la detección de manos optimizada vs. estándar
"""

import cv2
import numpy as np
import time
import os
from pathlib import Path
import mediapipe as mp
from hand_detection_optimizer import HandDetectionOptimizer

def create_test_images():
    """Crear imágenes de prueba con diferentes tipos de fondo"""
    test_images = []
    
    # 1. Fondo blanco simple (ideal)
    simple_white = np.ones((480, 640, 3), dtype=np.uint8) * 255
    # Simular una mano simple
    cv2.rectangle(simple_white, (250, 150), (350, 300), (220, 180, 140), -1)
    cv2.circle(simple_white, (300, 130), 30, (220, 180, 140), -1)
    test_images.append(("Simple White Background", simple_white))
    
    # 2. Fondo complejo con textura
    complex_texture = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    # Agregar algunos patrones más realistas
    for i in range(10):
        center = (np.random.randint(50, 590), np.random.randint(50, 430))
        radius = np.random.randint(20, 80)
        color = tuple(np.random.randint(0, 255, 3).tolist())
        cv2.circle(complex_texture, center, radius, color, -1)
    
    # Simular mano en fondo complejo
    cv2.rectangle(complex_texture, (250, 150), (350, 300), (220, 180, 140), -1)
    cv2.circle(complex_texture, (300, 130), 30, (220, 180, 140), -1)
    test_images.append(("Complex Textured Background", complex_texture))
    
    # 3. Fondo con objetos similares al color de piel
    skin_confusing = np.ones((480, 640, 3), dtype=np.uint8) * 200
    # Agregar objetos del color de la piel
    for i in range(5):
        center = (np.random.randint(50, 590), np.random.randint(50, 430))
        size = (np.random.randint(30, 80), np.random.randint(30, 80))
        cv2.rectangle(skin_confusing, 
                     (center[0] - size[0]//2, center[1] - size[1]//2),
                     (center[0] + size[0]//2, center[1] + size[1]//2),
                     (210, 170, 130), -1)
    
    # Mano real
    cv2.rectangle(skin_confusing, (250, 150), (350, 300), (220, 180, 140), -1)
    cv2.circle(skin_confusing, (300, 130), 30, (220, 180, 140), -1)
    test_images.append(("Skin-colored Confusing Background", skin_confusing))
    
    # 4. Fondo muy oscuro
    dark_bg = np.ones((480, 640, 3), dtype=np.uint8) * 30
    # Mano en fondo oscuro
    cv2.rectangle(dark_bg, (250, 150), (350, 300), (220, 180, 140), -1)
    cv2.circle(dark_bg, (300, 130), 30, (220, 180, 140), -1)
    test_images.append(("Very Dark Background", dark_bg))
    
    # 5. Fondo muy brillante con reflejos
    bright_bg = np.ones((480, 640, 3), dtype=np.uint8) * 240
    # Agregar algunos "reflejos"
    for i in range(15):
        center = (np.random.randint(50, 590), np.random.randint(50, 430))
        radius = np.random.randint(5, 25)
        cv2.circle(bright_bg, center, radius, (255, 255, 255), -1)
    
    # Mano en fondo brillante
    cv2.rectangle(bright_bg, (250, 150), (350, 300), (200, 160, 120), -1)
    cv2.circle(bright_bg, (300, 130), 30, (200, 160, 120), -1)
    test_images.append(("Very Bright Background", bright_bg))
    
    return test_images

def test_standard_detection(image_rgb):
    """Prueba con detección estándar de MediaPipe"""
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        static_image_mode=True,
        max_num_hands=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    
    start_time = time.perf_counter()
    results = hands.process(image_rgb)
    end_time = time.perf_counter()
    
    processing_time = (end_time - start_time) * 1000
    hands_detected = len(results.multi_hand_landmarks) if results.multi_hand_landmarks else 0
    
    hands.close()
    
    return {
        "hands_detected": hands_detected,
        "processing_time_ms": processing_time,
        "method": "standard"
    }

def test_optimized_detection(image_rgb, optimizer):
    """Prueba con detección optimizada"""
    start_time = time.perf_counter()
    results, metadata = optimizer.detect_hands_adaptive(image_rgb)
    end_time = time.perf_counter()
    
    total_processing_time = (end_time - start_time) * 1000
    hands_detected = len(results.multi_hand_landmarks) if results.multi_hand_landmarks else 0
    
    return {
        "hands_detected": hands_detected,
        "processing_time_ms": total_processing_time,
        "method": "optimized",
        "strategy": metadata.get("strategy", "unknown"),
        "complexity_score": metadata.get("complexity_score", 0),
        "internal_processing_time_ms": metadata.get("processing_time_ms", 0)
    }

def main():
    print("🧪 Prueba Comparativa: Detección Estándar vs. Optimizada")
    print("=" * 60)
    
    # Crear optimizador
    optimizer = HandDetectionOptimizer()
    
    # Generar imágenes de prueba
    test_images = create_test_images()
    
    results = []
    
    for test_name, test_image in test_images:
        print(f"\n🔍 Probando: {test_name}")
        print("-" * 40)
        
        # Convertir BGR a RGB para MediaPipe
        image_rgb = cv2.cvtColor(test_image, cv2.COLOR_BGR2RGB)
        
        # Prueba estándar
        standard_result = test_standard_detection(image_rgb)
        print(f"  📊 Estándar:   {standard_result['hands_detected']} manos, "
              f"{standard_result['processing_time_ms']:.2f}ms")
        
        # Prueba optimizada
        optimized_result = test_optimized_detection(image_rgb, optimizer)
        print(f"  🚀 Optimizado: {optimized_result['hands_detected']} manos, "
              f"{optimized_result['processing_time_ms']:.2f}ms")
        print(f"     Estrategia: {optimized_result['strategy']}")
        print(f"     Complejidad: {optimized_result['complexity_score']:.1f}")
        
        # Calcular mejora
        detection_improvement = optimized_result['hands_detected'] - standard_result['hands_detected']
        
        if detection_improvement > 0:
            print(f"  ✅ Mejora: +{detection_improvement} detecciones")
        elif detection_improvement < 0:
            print(f"  ❌ Empeora: {detection_improvement} detecciones")
        else:
            print(f"  ➡️  Sin cambio en detección")
        
        # Guardar resultados para análisis
        results.append({
            "test_name": test_name,
            "standard": standard_result,
            "optimized": optimized_result,
            "improvement": detection_improvement
        })
        
        # Guardar imagen de prueba para inspección visual
        output_path = f"test_output_{test_name.replace(' ', '_').lower()}.jpg"
        cv2.imwrite(output_path, test_image)
    
    # Resumen final
    print("\n" + "=" * 60)
    print("📈 RESUMEN COMPARATIVO")
    print("=" * 60)
    
    total_improvements = sum(r["improvement"] for r in results)
    successful_optimizations = sum(1 for r in results if r["improvement"] > 0)
    
    print(f"Tests ejecutados: {len(results)}")
    print(f"Mejoras exitosas: {successful_optimizations}/{len(results)}")
    print(f"Mejora total en detecciones: +{total_improvements}")
    
    # Análisis de estrategias utilizadas
    strategies_used = {}
    for r in results:
        strategy = r["optimized"]["strategy"]
        strategies_used[strategy] = strategies_used.get(strategy, 0) + 1
    
    print(f"\nEstrategias utilizadas:")
    for strategy, count in strategies_used.items():
        print(f"  {strategy}: {count} veces")
    
    # Casos donde la optimización funcionó mejor
    print(f"\nMejores casos para optimización:")
    for r in results:
        if r["improvement"] > 0:
            print(f"  ✅ {r['test_name']}: +{r['improvement']} detecciones "
                  f"(estrategia: {r['optimized']['strategy']})")
    
    print(f"\n💡 RECOMENDACIONES:")
    if successful_optimizations >= len(results) * 0.6:
        print("  🚀 La optimización muestra mejoras significativas!")
        print("  📝 Reemplaza tu app.py actual con app_optimized.py")
    else:
        print("  ⚠️  La optimización muestra mejoras mixtas")
        print("  🔧 Considera ajustar los parámetros del optimizador")
    
    print(f"\n📁 Imágenes de prueba guardadas en el directorio actual")
    
    # Cleanup
    del optimizer

if __name__ == "__main__":
    main()
