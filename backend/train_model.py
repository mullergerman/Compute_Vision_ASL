"""Training script for the ASL alphabet model."""

import os
import sys
import pickle
from typing import List, Tuple

import cv2
import numpy as np
import mediapipe as mp
from sklearn.linear_model import LogisticRegression

LETTERS: List[str] = [chr(c) for c in range(ord("A"), ord("Z") + 1)]


def _extract_features(hand_landmarks) -> List[float]:
    """Return a flat list of x, y, z coordinates from hand landmarks."""
    feats: List[float] = []
    for lm in hand_landmarks.landmark:
        feats.extend([lm.x, lm.y, lm.z])
    return feats


def _load_dataset(data_dir: str) -> Tuple[np.ndarray, np.ndarray]:
    """Load images and extract landmark features from the Kaggle dataset."""

    features: List[List[float]] = []
    labels: List[str] = []

    mp_hands = mp.solutions.hands
    with mp_hands.Hands(
        static_image_mode=True,
        max_num_hands=1,
        min_detection_confidence=0.5,
    ) as hands:
        for letter in LETTERS:
            letter_dir = os.path.join(data_dir, letter)
            if not os.path.isdir(letter_dir):
                print(f"Warning: directory '{letter_dir}' not found; skipping")
                continue

            for fname in os.listdir(letter_dir):
                if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                path = os.path.join(letter_dir, fname)
                img = cv2.imread(path)
                if img is None:
                    continue
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                results = hands.process(img_rgb)
                if not results.multi_hand_landmarks:
                    continue
                feats = _extract_features(results.multi_hand_landmarks[0])
                features.append(feats)
                labels.append(letter)

    return np.array(features, dtype=np.float32), np.array(labels)


def main(dataset_dir: str, out_model: str) -> None:
    """Train a logistic regression model using MediaPipe hand landmarks."""

    X, y = _load_dataset(dataset_dir)
    if len(X) == 0:
        raise SystemExit("Dataset is empty or path is incorrect")

    clf = LogisticRegression(max_iter=1000)
    clf.fit(X, y)
    with open(out_model, 'wb') as f:
        pickle.dump(clf, f)
    print(f"Model saved to {out_model}")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python train_model.py /path/to/asl_alphabet_train asl_model.pkl')
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
