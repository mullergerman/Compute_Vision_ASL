import cv2
import numpy as np
import json
from flask import Flask
from flask_sock import Sock
import mediapipe as mp

app = Flask(__name__)
sock = Sock(app)

# MediaPipe setup
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False,
                       max_num_hands=2,
                       min_detection_confidence=0.5,
                       min_tracking_confidence=0.5)

DEFAULT_TOPOLOGY = [
    (
        c[0].value if hasattr(c[0], "value") else c[0],
        c[1].value if hasattr(c[1], "value") else c[1],
    )
    for c in mp_hands.HAND_CONNECTIONS
]


def _finger_extended(landmarks, tip, pip):
    """Return True if the finger is extended based on y-coordinates."""
    return landmarks[tip].y < landmarks[pip].y


def classify_gesture(hand_landmarks):
    lm = hand_landmarks.landmark
    index = _finger_extended(lm, 8, 6)
    middle = _finger_extended(lm, 12, 10)
    ring = _finger_extended(lm, 16, 14)
    pinky = _finger_extended(lm, 20, 18)

    wrist = lm[0]
    thumb_tip = lm[4]
    thumb_ip = lm[3]
    thumb = abs(thumb_tip.x - wrist.x) > abs(thumb_ip.x - wrist.x)

    if all([index, middle, ring, pinky, thumb]):
        return "paper"
    if index and middle and not ring and not pinky:
        return "scissors"
    if not any([index, middle, ring, pinky, thumb]):
        return "rock"
    if not any([index, middle, ring, pinky]):
        return "closed"
    return "unknown"


GESTURE_TO_LETTER = {
    "rock": "A",      # fist
    "paper": "B",     # open hand
    "scissors": "V",  # index and middle finger
    "closed": "E",    # closed with thumb over
}


def gesture_to_letter(gesture: str) -> str:
    """Map a simple gesture name to an ASL letter."""
    return GESTURE_TO_LETTER.get(gesture, "")

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

                    gesture = classify_gesture(hand_landmarks)
                    letter = gesture_to_letter(gesture)
                    detected_letters.append(letter)
                    print(f"Detected gesture: {gesture}, letter: {letter}")

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
