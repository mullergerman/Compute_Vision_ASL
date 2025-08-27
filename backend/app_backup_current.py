import cv2
import numpy as np
import json
import time
import os
import urllib.request
import urllib.parse
from dotenv import load_dotenv
from datetime import datetime

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
    min_detection_confidence=0.3,
    min_tracking_confidence=0.3,
)

DEFAULT_TOPOLOGY = [
    (
        c[0].value if hasattr(c[0], "value") else c[0],
        c[1].value if hasattr(c[1], "value") else c[1],
    )
    for c in mp_hands.HAND_CONNECTIONS
]

# Debug configuration
saved_image_count = 0
MAX_IMAGES_TO_SAVE = 10
DEBUG_DIR = "debug_images"

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

def fix_image_orientation(frame):
    """
    Fix image orientation if dimensions are inverted (height > width).
    This handles devices that send images in portrait mode.
    """
    height, width = frame.shape[:2]
    
    if height > width:
        # Image is in portrait mode, rotate 90 degrees counterclockwise
        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        print(f"DEBUG: Image rotated from {width}x{height} to {frame.shape[1]}x{frame.shape[0]}")
    else:
        print(f"DEBUG: Image orientation correct: {width}x{height}")
    
    return frame

@sock.route('/ws')
def process_video(ws):
    global saved_image_count
    while True:
        data = ws.receive()
        if not data:
            break

        try:
            if isinstance(data, str):
                data = data.encode('utf-8')

            np_arr = np.frombuffer(data, dtype=np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is None:
                continue

            print(f"DEBUG: Original frame - shape: {frame.shape}, type: {frame.dtype}, min: {frame.min()}, max: {frame.max()}, mean: {frame.mean():.2f}")
            
            # Fix image orientation if needed (ONLY if inverted)
            frame = fix_image_orientation(frame)
            
            # Debug: Save first few images for analysis (after rotation fix)
            if saved_image_count < MAX_IMAGES_TO_SAVE:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"{DEBUG_DIR}/fixed_frame_{saved_image_count:03d}_{timestamp}.jpg"
                cv2.imwrite(filename, frame)
                print(f"DEBUG: Saved corrected image {filename}")
                saved_image_count += 1

            # Convert to RGB
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process MediaPipe Hands Detection
            start_mediapipe = time.perf_counter()
            results = hands.process(image_rgb)
            print(f"DEBUG: MediaPipe results - multi_hand_landmarks: {results.multi_hand_landmarks is not None}")
            end_mediapipe = time.perf_counter()
            duration_mp_ms = (end_mediapipe - start_mediapipe) * 1000

            keypoints = []
            topology = []
            letter = ""
            duration_asl_ms = 0

            if results.multi_hand_landmarks:
                print(f"DEBUG: Found {len(results.multi_hand_landmarks)} hands")
                for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    base = idx * len(hand_landmarks.landmark)
                    # Append keypoints
                    for lm in hand_landmarks.landmark:
                        x_px = int(lm.x * frame.shape[1])
                        y_px = int(lm.y * frame.shape[0])
                        keypoints.append([x_px, y_px])

                    # Offset the predefined topology
                    for start, end in DEFAULT_TOPOLOGY:
                        topology.append([start + base, end + base])

                    # Medir tiempo de predicción ASL
                    start_asl = time.perf_counter()
                    letter = predict_letter(hand_landmarks)
                    end_asl = time.perf_counter()
                    duration_asl_ms = (end_asl - start_asl) * 1000

                print(f"DEBUG: Detected {len(keypoints)} keypoints and {len(topology)} connections")

            # Send metrics
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
                "image_width": frame.shape[1],
                "image_height": frame.shape[0],
                "letter": letter if letter else ""
            }
            
            print(f"DEBUG: Sending response - keypoints: {len(keypoints)}, topology: {len(topology)}, letter: {letter}")
            ws.send(json.dumps(response))

        except Exception as e:
            app.logger.exception("Error processing image: %s", e)
            continue

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
