import cv2
import numpy as np
import json
from flask import Flask
from flask_sock import Sock
import mediapipe as mp
import pickle

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

# Load ASL classification model
try:
    with open("asl_model.pkl", "rb") as f:
        asl_model = pickle.load(f)
except FileNotFoundError:
    asl_model = None
    print("Warning: ASL model 'asl_model.pkl' not found. Classification disabled.")



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
    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as hands:
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

                # Convertir a RGB
                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(image_rgb)

                keypoints = []
                topology = []
                detected_letters = []

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

                        letter = predict_letter(hand_landmarks)
                        detected_letters.append(letter)
                        #if letter:
                        #    print(f"Detected letter: {letter}")

                response = {
                    "keypoints": keypoints if keypoints else [],
                    "topology": topology if topology else [],
                    "image_width": frame.shape[1],  # ancho de la imagen
                    "image_height": frame.shape[0],  # alto de la imagen
                    "letter": detected_letters[0] if detected_letters else ""
                }
                ws.send(json.dumps(response))

            except Exception as e:
                app.logger.exception("Error al procesar imagen: %s", e)
                continue

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
