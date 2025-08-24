import cv2
import numpy as np
import json
import os
import logging
import os
import logging
from flask import Flask
from flask_sock import Sock
import mediapipe as mp
import pickle
import warnings
import time

# Suppress specific warnings before importing other libraries
warnings.filterwarnings('ignore', category=UserWarning, module='sklearn')
warnings.filterwarnings('ignore', category=UserWarning, module='google.protobuf')

# Set environment variables to suppress TensorFlow/MediaPipe warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['GLOG_minloglevel'] = '2'

# Configure logging to reduce noise
logging.getLogger('tensorflow').setLevel(logging.ERROR)
logging.getLogger('absl').setLevel(logging.ERROR)

app = Flask(__name__)
sock = Sock(app)

# MediaPipe setup
mp_hands = mp.solutions.hands


def _center_crop_square(img: "np.ndarray") -> "np.ndarray":
    """Return a square crop centered in the image."""
    h, w = img.shape[:2]
    if h == w:
        return img
    side = min(h, w)
    y0 = (h - side) // 2
    x0 = (w - side) // 2
    return img[y0 : y0 + side, x0 : x0 + side]

DEFAULT_TOPOLOGY = [
    (
        c[0].value if hasattr(c[0], "value") else c[0],
        c[1].value if hasattr(c[1], "value") else c[1],
    )
    for c in mp_hands.HAND_CONNECTIONS
]

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

asl_model = load_model()
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
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return asl_model.predict(features)[0]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return asl_model.predict(features)[0]
    except Exception:
        return ""

@sock.route('/ws')
def process_video(ws):
    # Suppress MediaPipe warnings during initialization
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hands_processor = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
    
    with hands_processor as hands:
    # Suppress MediaPipe warnings during initialization
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hands_processor = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
    
    with hands_processor as hands:
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

                # Normalize aspect ratio to a square image to avoid MediaPipe warnings
                frame = _center_crop_square(frame)

                # Convert to RGB
                # Convert to RGB
                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Process with warnings suppressed
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
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
                
                # Mostrar tiempos en la consola (una línea)
                print(f"MediaPipe: {mediapipe_processing_time:.2f}ms | ASL: {asl_processing_time:.2f}ms | Total: {total_processing_time:.2f}ms")

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
                app.logger.exception("Error processing image: %s", e)
                continue

if __name__ == "__main__":
    # Suppress additional startup warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        app.run(host='0.0.0.0', port=5000)