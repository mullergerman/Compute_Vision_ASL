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

app = Flask(__name__)
sock = Sock(app)

# MediaPipe setup
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

DEFAULT_TOPOLOGY = [
    (
        c[0].value if hasattr(c[0], "value") else c[0],
        c[1].value if hasattr(c[1], "value") else c[1],
    )
    for c in mp_hands.HAND_CONNECTIONS
]

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
    """Parse YUV data with metadata header.
    
    Expected format:
    - 16 bytes header: width(4), height(4), rotation(4), yuv_size(4)
    - YUV data (NV21 format)
    
    Returns: (width, height, rotation, yuv_array) or None if invalid
    """
    try:
        if len(data) < 16:
            print(f"Data too short: {len(data)} bytes, expected at least 16 bytes header")
            return None
            
        # Parse metadata header (16 bytes)
        header = data[:16]
        width, height, rotation, yuv_size = struct.unpack('>IIII', header)  # Big-endian
        
        #print(f"YUV metadata: width={width}, height={height}, rotation={rotation}, yuv_size={yuv_size}")
        
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
    """Convert NV21 YUV data to RGB using OpenCV.
    
    Args:
        yuv_data: NV21 format YUV data as numpy array
        width: Image width
        height: Image height
        
    Returns: RGB image as numpy array
    """
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
            
            # Process MediaPipe Hands Detection
            start_mediapipe = time.perf_counter()
            results = hands.process(image_rgb)
            end_mediapipe = time.perf_counter()
            duration_mp_ms = (end_mediapipe - start_mediapipe) * 1000

            keypoints = []
            topology = []
            letter = ""
            duration_asl_ms = 0

            if results.multi_hand_landmarks:
                for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    base = idx * len(hand_landmarks.landmark)
                    # Append keypoints
                    for lm in hand_landmarks.landmark:
                        x_px = int(lm.x * width)
                        y_px = int(lm.y * height)
                        keypoints.append([x_px, y_px])

                    # Offset the predefined topology
                    for start, end in DEFAULT_TOPOLOGY:
                        topology.append([start + base, end + base])

                    # Medir tiempo de predicción ASL
                    start_asl = time.perf_counter()
                    letter = predict_letter(hand_landmarks)
                    end_asl = time.perf_counter()
                    duration_asl_ms = (end_asl - start_asl) * 1000

            # Send metrics - SIMPLE!
            send_metrics(
                measurement="asl_processing",
                tags={"endpoint": "ws", "service": "asl-backend"},
                fields={
                    "duration_asl_ms": duration_asl_ms,
                    "duration_mp_ms": duration_mp_ms
                }
            )

            response = {
                "keypoints": keypoints if keypoints else [],
                "topology": topology if topology else [],
                "image_width": width,
                "image_height": height,
                "letter": letter if letter else ""
            }
            ws.send(json.dumps(response))

        except Exception as e:
            app.logger.exception("Error processing image: %s", e)
            continue

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
