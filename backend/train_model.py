"""Training script for the ASL alphabet model."""

import os
import sys
import pickle
from typing import List, Tuple

import cv2
import numpy as np
from sklearn.linear_model import LogisticRegression

LETTERS: List[str] = [chr(c) for c in range(ord("A"), ord("Z") + 1)]


def _load_images(data_dir: str) -> Tuple[np.ndarray, np.ndarray]:
    """Load images from the Kaggle ASL Alphabet dataset.

    The expected directory structure is ``data_dir/A``, ``data_dir/B`` ...
    containing JPEG or PNG images for each letter. Only the 26 letters are
    used; other directories are ignored.
    """

    features: List[np.ndarray] = []
    labels: List[str] = []

    for letter in LETTERS:
        letter_dir = os.path.join(data_dir, letter)
        if not os.path.isdir(letter_dir):
            print(f"Warning: directory '{letter_dir}' not found; skipping")
            continue

        for fname in os.listdir(letter_dir):
            if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            path = os.path.join(letter_dir, fname)
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            img = cv2.resize(img, (64, 64))
            features.append(img.flatten() / 255.0)
            labels.append(letter)

    return np.array(features), np.array(labels)


def main(dataset_dir: str, out_model: str) -> None:
    """Train a simple logistic regression model using the Kaggle dataset."""

    X, y = _load_images(dataset_dir)
    if len(X) == 0:
        raise SystemExit("Dataset is empty or path is incorrect")

    clf = LogisticRegression(max_iter=1000)
    clf.fit(X, y)
    with open(out_model, 'wb') as f:
        pickle.dump(clf, f)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python train_model.py /path/to/asl_alphabet_train asl_model.pkl')
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
