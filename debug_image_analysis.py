#!/usr/bin/env python3
import cv2
import numpy as np
import os
from pathlib import Path

def analyze_image(image_path):
    """Analyze a corrupted image and show detailed statistics"""
    print(f"\n=== Analyzing {image_path} ===")
    
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        print("Failed to load image")
        return
    
    print(f"Image shape: {img.shape}")
    print(f"Image dtype: {img.dtype}")
    
    # Split channels (BGR)
    b, g, r = cv2.split(img)
    
    print(f"\nChannel Statistics:")
    print(f"Blue  - Min: {b.min():3d}, Max: {b.max():3d}, Mean: {b.mean():6.2f}, Std: {b.std():6.2f}")
    print(f"Green - Min: {g.min():3d}, Max: {g.max():3d}, Mean: {g.mean():6.2f}, Std: {g.std():6.2f}")
    print(f"Red   - Min: {r.min():3d}, Max: {r.max():3d}, Mean: {r.mean():6.2f}, Std: {r.std():6.2f}")
    
    # Check if image is heavily green-biased (corruption indicator)
    green_dominance = g.mean() / (b.mean() + r.mean() + 1)  # +1 to avoid division by zero
    print(f"Green dominance ratio: {green_dominance:.2f}")
    
    if green_dominance > 1.5:
        print("⚠️  IMAGE APPEARS TO BE CORRUPTED - Heavy green bias detected!")
    else:
        print("✅ Image appears normal")
    
    # Check for pattern corruption (like the green lines you described)
    height, width = img.shape[:2]
    
    # Sample horizontal lines to check for repeating patterns
    sample_lines = [height//4, height//2, 3*height//4]
    print(f"\nHorizontal line pattern analysis:")
    
    for line_y in sample_lines:
        line_pixels = img[line_y, :]
        # Check if there's a repeating pattern by comparing adjacent pixels
        diff = np.diff(line_pixels, axis=0)
        pattern_variance = np.var(diff)
        print(f"Line {line_y}: pattern variance = {pattern_variance:.2f}")
        
        if pattern_variance < 10:  # Very low variance suggests corruption
            print(f"  ⚠️  Potential corruption pattern detected at line {line_y}")
    
    return img, green_dominance

def main():
    debug_dir = Path("debug_images")
    
    if not debug_dir.exists():
        print("debug_images directory not found!")
        return
    
    image_files = list(debug_dir.glob("*.jpg"))[:5]  # Analyze first 5 images
    
    print("YUV Conversion Debug Analysis")
    print("=" * 50)
    
    corrupted_count = 0
    
    for img_file in image_files:
        img, green_dominance = analyze_image(str(img_file))
        if green_dominance > 1.5:
            corrupted_count += 1
    
    print(f"\n=== SUMMARY ===")
    print(f"Total images analyzed: {len(image_files)}")
    print(f"Corrupted images: {corrupted_count}")
    print(f"Corruption rate: {corrupted_count/len(image_files)*100:.1f}%")
    
    if corrupted_count > 0:
        print("\n🔍 DIAGNOSIS:")
        print("The high green dominance and corruption patterns suggest")
        print("an issue with YUV to RGB conversion in the Android app.")
        print("Likely causes:")
        print("- Incorrect U/V plane ordering in YUV420_888 to NV21 conversion") 
        print("- Wrong stride calculations")
        print("- Pixel format mismatch")

if __name__ == "__main__":
    main()
