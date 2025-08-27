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
from hand_detection_optimizer import HandDetectionOptimizer

app = Flask(__name__)
sock = Sock(app)

# Inicializar el optimizador de detección de manos
hand_optimizer = HandDetectionOptimizer()

# MediaPipe setup (mantener para compatibilidad)
mp_hands = mp.solutions.hands

DEFAULT_TOPOLOGY = [
    (
        c[0].value if hasattr(c[0], "value") else c[0],
        c[1].value if hasattr(c[1], "value") else c[1],
    )
    for c in mp_hands.HAND_CONNECTIONS
]

# Filtro temporal para suavizado de landmarks
class TemporalLandmarkFilter:
    def __init__(self, window_size=3, confidence_threshold=0.7):
        self.window_size = window_size
        self.confidence_threshold = confidence_threshold
        self.landmark_history = []
        self.confidence_history = []
        
    def add_detection(self, landmarks, confidence):
        """Agregar nueva detección al historial"""
        self.landmark_history.append(landmarks)
        self.confidence_history.append(confidence)
        
        # Mantener solo el tamaño de ventana especificado
        if len(self.landmark_history) > self.window_size:
            self.landmark_history.pop(0)
            self.confidence_history.pop(0)
    
    def get_filtered_landmarks(self):
        """Obtener landmarks filtrados temporalmente"""
        if not self.landmark_history:
            return None
            
        # Si tenemos pocas detecciones, usar la más reciente
        if len(self.landmark_history) < 2:
            return self.landmark_history[-1]
        
        # Calcular promedio ponderado por confianza
        total_weight = sum(self.confidence_history)
        if total_weight == 0:
            return self.landmark_history[-1]
        
        # Promedio ponderado de landmarks
        averaged_landmarks = []
        num_landmarks = len(self.landmark_history[-1])
        
        for i in range(num_landmarks):
            x_sum = y_sum = z_sum = 0
            
            for j, landmarks in enumerate(self.landmark_history):
                weight = self.confidence_history[j] / total_weight
                x_sum += landmarks[i][0] * weight
                y_sum += landmarks[i][1] * weight
                z_sum += landmarks[i][2] * weight
            
            averaged_landmarks.append([x_sum, y_sum, z_sum])
        
        return averaged_landmarks
    
    def should_use_detection(self):
        """Determinar si usar la detección actual basado en confianza histórica"""
        if not self.confidence_history:
            return True
            
        recent_confidence = np.mean(self.confidence_history[-2:]) if len(self.confidence_history) >= 2 else self.confidence_history[-1]
        return recent_confidence >= self.confidence_threshold

# Filtro temporal global
temporal_filter = TemporalLandmarkFilter()

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
        
        # Add tags and fields
        if tags:
            data.update(tags)
        if fields:
            data.update(fields)
        
        # Send to Telegraf HTTP endpoint
        req = urllib.request.Request(
            'http://localhost:8088/ingest',
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        urllib.request.urlopen(req, timeout=1)
        #print(f"✅ Metrics sent: {measurement}")
        
    except Exception as e:
        print(f"❌ Metrics failed: {e}")

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
            print(f"Data too short: {len(data)} bytes, expected at least 16 bytes header")
            return None
            
        # Parse metadata header (16 bytes)
        header = data[:16]
        width, height, rotation, yuv_size = struct.unpack('>IIII', header)  # Big-endian
        
        # Validate metadata
        expected_yuv_size = width * height * 3 // 2
        if yuv_size != expected_yuv_size:
            print(f"Invalid YUV size: expected {expected_yuv_size}, got {yuv_size}")
            return None
            
        if len(data) != 16 + yuv_size:
            print(f"Data size mismatch: expected {16 + yuv_size}, got {len(data)}")
            return None
            
        # Extract YUV data
        yuv_data = data[16:]
        yuv_array = np.frombuffer(yuv_data, dtype=np.uint8)
        
        return width, height, rotation, yuv_array
        
    except Exception as e:
        print(f"Error parsing YUV data: {e}")
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
        print(f"Error converting YUV to RGB: {e}")
        return None

@sock.route('/ws')
def process_video(ws):
    frame_count = 0
    last_processed_time = 0
    processing_interval = 0.1  # Process maximum 10 FPS
    
    while True:
        data = ws.receive()
        if not data:
            break

        frame_count += 1
        current_time = time.time()
        
        # Drop frames if we're processing too fast
        if (current_time - last_processed_time) < processing_interval:
            print(f"Dropping frame {frame_count} - too fast")
            # Send a quick ACK without processing
            try:
                response = {
                    "keypoints": [],
                    "topology": [],
                    "image_width": 1440,
                    "image_height": 1440,
                    "letter": ""
                }
                ws.send(json.dumps(response))
            except:
                pass
            continue
            
        last_processed_time = current_time
        #print(f"Processing frame {frame_count}")

        try:
            if isinstance(data, str):
                data = data.encode('utf-8')

            # Try to parse as YUV data first
            yuv_result = parse_yuv_data(data)
            
            if yuv_result is not None:
                # Process YUV data
                width, height, rotation, yuv_array = yuv_result
                #print(f"Processing YUV frame: {width}x{height}, rotation={rotation}")
                
                # Convert YUV to RGB
                start_conversion = time.perf_counter()
                image_rgb = yuv_to_rgb(yuv_array, width, height)
                end_conversion = time.perf_counter()
                conversion_time_ms = (end_conversion - start_conversion) * 1000
                #print(f"YUV to RGB conversion took {conversion_time_ms:.2f} ms")
                
                if image_rgb is None:
                    continue
                    
            else:
                # Fallback: try to decode as JPEG
                print("Falling back to JPEG decoding")
                np_arr = np.frombuffer(data, dtype=np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                if frame is None:
                    continue
                    
                # Convert BGR to RGB for JPEG fallback
                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                width, height = frame.shape[1], frame.shape[0]
            
            # 🚀 DETECCIÓN OPTIMIZADA DE MANOS
            start_mediapipe = time.perf_counter()
            results, detection_metadata = hand_optimizer.detect_hands_adaptive(image_rgb)
            end_mediapipe = time.perf_counter()
            duration_mp_ms = (end_mediapipe - start_mediapipe) * 1000

            keypoints = []
            topology = []
            letter = ""
            duration_asl_ms = 0
            detection_confidence = 0

            if results.multi_hand_landmarks:
                for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    # Validar landmarks antes de procesarlos
                    if hand_optimizer.validate_landmarks(hand_landmarks, width, height):
                        base = idx * len(hand_landmarks.landmark)
                        
                        # Extraer coordenadas para filtro temporal
                        current_landmarks = []
                        for lm in hand_landmarks.landmark:
                            current_landmarks.append([lm.x, lm.y, lm.z])
                        
                        # Calcular confianza basada en metadata de detección
                        detection_confidence = 1.0 - (detection_metadata["complexity_score"] / 100.0)
                        detection_confidence = max(0.1, min(1.0, detection_confidence))
                        
                        # Agregar al filtro temporal
                        temporal_filter.add_detection(current_landmarks, detection_confidence)
                        
                        # Usar filtro temporal si es apropiado
                        if temporal_filter.should_use_detection():
                            filtered_landmarks = temporal_filter.get_filtered_landmarks()
                            if filtered_landmarks:
                                current_landmarks = filtered_landmarks
                        
                        # Append keypoints usando landmarks filtrados
                        for lm_coords in current_landmarks:
                            x_px = int(lm_coords[0] * width)
                            y_px = int(lm_coords[1] * height)
                            keypoints.append([x_px, y_px])

                        # Offset the predefined topology
                        for start, end in DEFAULT_TOPOLOGY:
                            topology.append([start + base, end + base])

                        # Medir tiempo de predicción ASL
                        start_asl = time.perf_counter()
                        letter = predict_letter(hand_landmarks)
                        end_asl = time.perf_counter()
                        duration_asl_ms = (end_asl - start_asl) * 1000

            # Send enhanced metrics
            send_metrics(
                measurement="asl_processing_optimized",
                tags={
                    "endpoint": "ws", 
                    "service": "asl-backend",
                    "strategy": detection_metadata.get("strategy", "unknown"),
                    "frame": frame_count
                },
                fields={
                    "duration_asl_ms": duration_asl_ms,
                    "duration_mp_ms": duration_mp_ms,
                    "complexity_score": detection_metadata.get("complexity_score", 0),
                    "detection_confidence": detection_confidence,
                    "hands_detected": detection_metadata.get("hands_detected", 0)
                }
            )

            response = {
                "keypoints": keypoints if keypoints else [],
                "topology": topology if topology else [],
                "image_width": width,
                "image_height": height,
                "letter": letter if letter else "",
                "debug_info": {
                    "strategy": detection_metadata.get("strategy", "unknown"),
                    "complexity": detection_metadata.get("complexity_score", 0),
                    "confidence": detection_confidence
                }
            }
            ws.send(json.dumps(response))

        except Exception as e:
            app.logger.exception("Error processing image: %s", e)
            continue

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
