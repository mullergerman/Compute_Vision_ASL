import cv2
import numpy as np
import mediapipe as mp
import os

# MediaPipe setup
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=True,
    max_num_hands=2,
    min_detection_confidence=0.3,
    min_tracking_confidence=0.3,
)

# Test with a saved image from the problematic device
test_images = [
    "debug_images/fixed_frame_000_20250825_015423_971597.jpg",
    "debug_images/fixed_frame_001_20250825_015424_255175.jpg",
    "debug_images/fixed_frame_002_20250825_015424_498040.jpg"
]

print("Testing MediaPipe with saved images:")
print("-" * 50)

for image_path in test_images:
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        continue
    
    # Load image
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"❌ Could not load image: {image_path}")
        continue
    
    print(f"\n🔍 Testing: {image_path}")
    print(f"   Shape: {frame.shape}")
    print(f"   Mean: {frame.mean():.2f}")
    print(f"   Min/Max: {frame.min()}/{frame.max()}")
    
    # Convert to RGB
    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Process with MediaPipe
    results = hands.process(image_rgb)
    
    if results.multi_hand_landmarks:
        print(f"   ✅ DETECTED {len(results.multi_hand_landmarks)} hands!")
        for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
            print(f"      Hand {i+1}: {len(hand_landmarks.landmark)} landmarks")
    else:
        print(f"   ❌ No hands detected")

# Test with a simple test pattern
print(f"\n🧪 Testing with synthetic image:")
print("-" * 50)

# Create a simple test image
test_frame = np.ones((480, 640, 3), dtype=np.uint8) * 128  # Gray background
# Add a simple hand-like pattern (just for testing MediaPipe setup)
cv2.rectangle(test_frame, (300, 200), (350, 300), (255, 220, 180), -1)  # Hand-colored rectangle
cv2.circle(test_frame, (325, 180), 25, (255, 220, 180), -1)  # "Palm"

print(f"   Synthetic image shape: {test_frame.shape}")
image_rgb = cv2.cvtColor(test_frame, cv2.COLOR_BGR2RGB)
results = hands.process(image_rgb)

if results.multi_hand_landmarks:
    print(f"   ✅ DETECTED {len(results.multi_hand_landmarks)} hands in synthetic image")
else:
    print(f"   ❌ No hands detected in synthetic image")

print(f"\n📋 MediaPipe configuration:")
print(f"   static_image_mode: True")
print(f"   max_num_hands: 2") 
print(f"   min_detection_confidence: 0.3")
print(f"   min_tracking_confidence: 0.3")
