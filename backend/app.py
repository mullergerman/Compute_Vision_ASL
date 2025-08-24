import cv2
import numpy as np
import json
import os
import socket
import time

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

# Graphite configuration
GRAPHITE_HOST = os.getenv("GRAPHITE_HOST", "localhost")
GRAPHITE_PORT = int(os.getenv("GRAPHITE_PORT", "2003"))
print(f"Graphite server: {GRAPHITE_HOST}:{GRAPHITE_PORT}")

def send_metric(name: str, value: float) -> None:
    """Send a single metric to Graphite using the plaintext protocol."""
    timestamp = int(time.time())
    message = f"{name} {value} {timestamp}\n"
    try:
        with socket.create_connection((GRAPHITE_HOST, GRAPHITE_PORT), timeout=1) as sock_conn:
            sock_conn.sendall(message.encode("utf-8"))
    except OSError as exc:
        app.logger.warning("Failed to send metric %s: %s", name, exc)

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

@sock.route('/ws')
def process_video(ws):
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

            # Convert to RGB
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process with warnings suppressed
            mediapipe_start_time = time.time()
            results = hands.process(image_rgb)
            mediapipe_end_time = time.time()
            mediapipe_processing_time = (mediapipe_end_time - mediapipe_start_time) * 1000  # en milisegundos

            keypoints = []
            topology = []
            letter = []
            asl_processing_time = 0

            if results.multi_hand_landmarks:
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
                    asl_start_time = time.time()
                    letter = predict_letter(hand_landmarks)
                    asl_end_time = time.time()
                    asl_processing_time = (asl_end_time - asl_start_time) * 1000  # en milisegundos

            # Calcular tiempo total
            total_processing_time = mediapipe_processing_time + asl_processing_time

            # Enviar métricas a Graphite
            send_metric("mediapipe.delay_ms", mediapipe_processing_time)
            send_metric("asl.delay_ms", asl_processing_time)
            send_metric("total.delay_ms", total_processing_time)

            response = {
                "keypoints": keypoints if keypoints else [],
                "topology": topology if topology else [],
                "image_width": frame.shape[1],
                "image_height": frame.shape[0],
                "letter": letter if letter else ""
            }
            ws.send(json.dumps(response))

        except Exception as e:
            app.logger.exception("Error processing image: %s", e)
            continue

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
