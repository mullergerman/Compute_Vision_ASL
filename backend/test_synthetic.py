import cv2
import mediapipe as mp

# MediaPipe setup
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=True,
    max_num_hands=2,
    min_detection_confidence=0.1,  # Very low threshold
    min_tracking_confidence=0.1,
)

test_images = [
    "test_hand_realistic.jpg",
    "test_resized_frame.jpg"
]

print("Testing with created images:")
print("-" * 40)

for img_path in test_images:
    print(f"\n🔍 Testing: {img_path}")
    
    frame = cv2.imread(img_path)
    if frame is None:
        print(f"   ❌ Could not load {img_path}")
        continue
    
    print(f"   Shape: {frame.shape}")
    print(f"   Mean: {frame.mean():.2f}")
    
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

print(f"\n📋 Using very low thresholds (0.1) for maximum sensitivity")
