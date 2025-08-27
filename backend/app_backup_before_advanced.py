import cv2
import numpy as np
import json
import time
import os
import urllib.request
import urllib.parse
import struct
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from flask import Flask
from flask_sock import Sock
import mediapipe as mp
import pickle
from hand_detection_lightweight import LightweightHandDetectionOptimizer

app = Flask(__name__)
sock = Sock(app)

# Inicializar el optimizador ligero
hand_detector = LightweightHandDetectionOptimizer()

# MediaPipe setup (mantener para compatibilidad)
mp_hands = mp.solutions.hands

DEFAULT_TOPOLOGY = [
    (
        c[0].value if hasattr(c[0], "value") else c[0],
        c[1].value if hasattr(c[1], "value") else c[1],
    )
    for c in mp_hands.HAND_CONNECTIONS
]

# Helper function to convert numpy types to Python types
def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    return obj

# Simple metrics function
def send_metrics(measurement, tags=None, fields=None):
    """Send metrics directly to Telegraf - ultra simple version"""
    if not fields:
        return
    
    try:
        data = {
            'measurement': measurement,
            'ts': int(time.time() * 1000)  # timestamp in milliseconds
        }
        
        # Add tags and fields, converting numpy types
        if tags:
            data.update(convert_numpy_types(tags))
        if fields:
            data.update(convert_numpy_types(fields))
        
        # Send to Telegraf HTTP endpoint
        req = urllib.request.Request(
            'http://localhost:8088/ingest',
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        urllib.request.urlopen(req, timeout=1)
        
    except Exception as e:
        # Silenciar errores de métricas para no afectar rendimiento
        pass

# Load ASL classification model with better error handling
def load_model():
    try:
        with open("asl_model.pkl", "rb") as f:
            model = pickle.load(f)
        print("ASL model loaded successfully")
        return model
    except FileNotFoundError:
        print("Warning: ASL model 'asl_model.pkl' not found. Classification disabled.")
        return None
    except Exception as e:
        print(f"Error loading model: {e}")
        return None
    
# Load ASL classification model with better error handling
asl_model = load_model()

def _extract_features(hand_landmarks):
    """Return a flat array of landmark coordinates."""
    feats = []
    for lm in hand_landmarks.landmark:
        feats.extend([lm.x, lm.y, lm.z])
    return np.array(feats).reshape(1, -1)

def predict_letter(hand_landmarks) -> str:
    """Predict the ASL letter for the given hand landmarks."""
    if asl_model is None:
        return ""
    features = _extract_features(hand_landmarks)
    try:
        return asl_model.predict(features)[0]
    except Exception:
        return ""

def parse_yuv_data(data):
    """Parse YUV data with metadata header."""
    try:
        if len(data) < 16:
            return None
            
        # Parse metadata header (16 bytes)
        header = data[:16]
        width, height, rotation, yuv_size = struct.unpack('>IIII', header)  # Big-endian
        
        # Validate metadata
        expected_yuv_size = width * height * 3 // 2
        if yuv_size != expected_yuv_size:
            return None
            
        if len(data) != 16 + yuv_size:
            return None
            
        # Extract YUV data
        yuv_data = data[16:]
        yuv_array = np.frombuffer(yuv_data, dtype=np.uint8)
        
        return width, height, rotation, yuv_array
        
    except Exception as e:
        return None

def yuv_to_rgb(yuv_data, width, height):
    """Convert NV21 YUV data to RGB using OpenCV."""
    try:
        # Reshape YUV data for OpenCV
        yuv_image = yuv_data.reshape((height * 3 // 2, width))
        
        # Convert NV21 to RGB
        rgb_image = cv2.cvtColor(yuv_image, cv2.COLOR_YUV2RGB_NV21)
        
        return rgb_image
        
    except Exception as e:
        return None

@sock.route('/ws')
def process_video(ws):
    frame_count = 0
    last_processed_time = 0
    processing_interval = 0.08  # Procesar máximo 12.5 FPS (más rápido que antes)
    
    # Variables para estadísticas de rendimiento
    detection_times = []
    last_stats_time = time.time()
    
    while True:
        data = ws.receive()
        if not data:
            break

        frame_count += 1
        current_time = time.time()
        
        # Drop frames más agresivamente para mantener velocidad
        if (current_time - last_processed_time) < processing_interval:
            # Envío respuesta mínima para mantener conexión
            try:
                response = {
                    "keypoints": [],
                    "topology": [],
                    "image_width": 640,
                    "image_height": 480,
                    "letter": ""
                }
                ws.send(json.dumps(response))
            except:
                pass
            continue
            
        last_processed_time = current_time

        try:
            if isinstance(data, str):
                data = data.encode('utf-8')

            # Procesar datos de imagen
            image_rgb = None
            width, height = 640, 480  # Valores por defecto
            
            # Try to parse as YUV data first
            yuv_result = parse_yuv_data(data)
            
            if yuv_result is not None:
                # Process YUV data
                width, height, rotation, yuv_array = yuv_result
                
                # Convert YUV to RGB (optimizado: sin timing detallado)
                image_rgb = yuv_to_rgb(yuv_array, width, height)
                
                if image_rgb is None:
                    continue
                    
            else:
                # Fallback: try to decode as JPEG
                np_arr = np.frombuffer(data, dtype=np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                if frame is None:
                    continue
                    
                # Convert BGR to RGB for JPEG fallback
                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                width, height = frame.shape[1], frame.shape[0]
            
            # 🚀 DETECCIÓN SÚPER OPTIMIZADA
            start_detection = time.perf_counter()
            results, detection_metadata = hand_detector.detect_hands_optimized(image_rgb)
            end_detection = time.perf_counter()
            total_detection_time = (end_detection - start_detection) * 1000
            
            # Guardar estadística para análisis
            detection_times.append(total_detection_time)
            if len(detection_times) > 50:  # Mantener solo últimas 50 mediciones
                detection_times.pop(0)

            keypoints = []
            topology = []
            letter = ""
            duration_asl_ms = 0

            if results.multi_hand_landmarks:
                for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    # Validación súper rápida
                    if hand_detector.simple_landmark_validation(hand_landmarks, width, height):
                        base = idx * len(hand_landmarks.landmark)
                        
                        # Append keypoints
                        for lm in hand_landmarks.landmark:
                            x_px = int(lm.x * width)
                            y_px = int(lm.y * height)
                            keypoints.append([x_px, y_px])

                        # Offset the predefined topology
                        for start, end in DEFAULT_TOPOLOGY:
                            topology.append([start + base, end + base])

                        # ASL prediction (con timing mínimo)
                        start_asl = time.perf_counter()
                        letter = predict_letter(hand_landmarks)
                        end_asl = time.perf_counter()
                        duration_asl_ms = (end_asl - start_asl) * 1000

            # Enviar métricas simplificadas (menos frecuentemente)
            if frame_count % 10 == 0:  # Solo cada 10 frames
                avg_detection_time = float(np.mean(detection_times[-10:])) if detection_times else 0.0
                send_metrics(
                    measurement="asl_processing_fast",
                    tags={
                        "endpoint": "ws", 
                        "service": "asl-backend-fast"
                    },
                    fields={
                        "avg_detection_time_ms": avg_detection_time,
                        "hands_detected": int(detection_metadata.get("hands_detected", 0)),
                        "frame_count": int(frame_count),
                        "needs_enhancement": bool(detection_metadata.get("needs_enhancement", False)),
                        "used_roi": bool(detection_metadata.get("used_roi", False)),
                        "consecutive_failures": int(detection_metadata.get("consecutive_failures", 0))
                    }
                )

            # Respuesta optimizada (campos mínimos necesarios)
            response = {
                "keypoints": keypoints,
                "topology": topology,
                "image_width": int(width),
                "image_height": int(height),
                "letter": str(letter)
            }
            
            # Solo agregar debug info si es necesario (para debugging)
            if frame_count % 30 == 0:  # Solo cada 30 frames
                response["debug_info"] = {
                    "detection_time": f"{total_detection_time:.1f}ms",
                    "needs_enhancement": bool(detection_metadata.get("needs_enhancement", False)),
                    "used_roi": bool(detection_metadata.get("used_roi", False)),
                    "consecutive_failures": int(detection_metadata.get("consecutive_failures", 0))
                }
            
            ws.send(json.dumps(response))

            # Mostrar estadísticas cada 30 segundos
            if current_time - last_stats_time > 30:
                if detection_times:
                    avg_time = np.mean(detection_times)
                    print(f"📊 Stats - Frames: {frame_count}, Avg detection: {avg_time:.1f}ms, "
                          f"Last hands: {detection_metadata.get('hands_detected', 0)}")
                last_stats_time = current_time

        except Exception as e:
            # Log error but continue processing
            print(f"Error processing frame {frame_count}: {e}")
            continue

if __name__ == "__main__":
    print("🚀 Starting FAST Hand Detection Server")
    print("Optimized for speed and efficiency in complex backgrounds")
    app.run(host="0.0.0.0", port=5000, debug=True)
