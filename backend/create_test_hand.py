import cv2
import numpy as np

# Create a more realistic hand-like image for testing
img = np.ones((480, 640, 3), dtype=np.uint8) * 50  # Dark background

# Create a hand-like shape
# Palm
cv2.ellipse(img, (320, 300), (80, 100), 0, 0, 360, (255, 220, 180), -1)

# Thumb
cv2.ellipse(img, (270, 250), (25, 60), 45, 0, 360, (255, 220, 180), -1)

# Fingers
finger_centers = [(300, 200), (320, 190), (340, 195), (360, 200)]
for center in finger_centers:
    cv2.ellipse(img, center, (15, 50), 0, 0, 360, (255, 220, 180), -1)

# Add some lighting variation
cv2.circle(img, (320, 280), 30, (240, 200, 160), -1, cv2.LINE_AA)

# Save the test image
cv2.imwrite('test_hand_realistic.jpg', img)
print("✅ Created test_hand_realistic.jpg")

# Also resize one of the existing images to see if size matters
try:
    existing = cv2.imread('debug_images/fixed_frame_000_20250825_015423_971597.jpg')
    if existing is not None:
        resized = cv2.resize(existing, (640, 480))
        cv2.imwrite('test_resized_frame.jpg', resized)
        print("✅ Created test_resized_frame.jpg")
    else:
        print("❌ Could not load existing frame")
except:
    print("❌ Error processing existing frame")
