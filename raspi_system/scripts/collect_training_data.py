#!/usr/bin/env python3
"""
VeggieFeed — Training Data Collection Script
=============================================

Uses the Raspberry Pi AI Camera (IMX500) to capture and organize
training images for the vegetable peel classification model.

Usage:
    python collect_training_data.py

Controls:
    - Number keys 0-9, a, b: Select class for next capture
    - SPACE or ENTER: Capture image for current class
    - Q: Quit and show dataset summary
"""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# Class mapping
CLASSES = {
    '0': 'carrot_peels',
    '1': 'potato_skins',
    '2': 'onion_skins',
    '3': 'tomato_skins',
    '4': 'cucumber_peels',
    '5': 'cabbage_leaves',
    '6': 'lettuce',
    '7': 'bell_pepper_scraps',
    '8': 'broccoli_stems',
    '9': 'cauliflower_leaves',
    'a': 'celery',
    'b': 'spinach',
}


def collect_with_picamera(output_dir: str, split: str = "train"):
    """Collect images using the Raspberry Pi camera."""
    try:
        from picamera2 import Picamera2
        import cv2
        import numpy as np
    except ImportError:
        print("[ERROR] picamera2 or opencv not installed.")
        print("  sudo apt install python3-picamera2 python3-opencv")
        sys.exit(1)

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (640, 480)}
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1)  # warm up

    current_class = 'carrot_peels'
    capture_count = {cls: 0 for cls in CLASSES.values()}

    # Count existing images
    for cls_name in CLASSES.values():
        cls_dir = os.path.join(output_dir, split, cls_name)
        if os.path.exists(cls_dir):
            capture_count[cls_name] = len([
                f for f in os.listdir(cls_dir)
                if f.lower().endswith(('.jpg', '.jpeg', '.png'))
            ])

    print("=" * 60)
    print("VeggieFeed — Training Data Collection")
    print("=" * 60)
    print(f"Output: {output_dir}/{split}/")
    print()
    print("Keys:")
    for key, cls in sorted(CLASSES.items()):
        print(f"  [{key}] {cls} ({capture_count[cls]} existing)")
    print()
    print("  [SPACE/ENTER] Capture    [Q] Quit")
    print("=" * 60)

    try:
        while True:
            frame = picam2.capture_array()
            display = frame.copy()

            # Draw current class label
            label = f"Class: {current_class} ({capture_count[current_class]} images)"
            cv2.putText(display, label, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display, "Press key [0-9,a,b] to switch class | SPACE to capture | Q to quit",
                       (10, display.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

            cv2.imshow("VeggieFeed Data Collection", display)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q') or key == 27:  # q or ESC
                break
            elif chr(key) in CLASSES:
                current_class = CLASSES[chr(key)]
                print(f"[INFO] Switched to class: {current_class}")
            elif key in (32, 13):  # SPACE or ENTER
                # Save image
                cls_dir = os.path.join(output_dir, split, current_class)
                os.makedirs(cls_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"{current_class}_{timestamp}.jpg"
                filepath = os.path.join(cls_dir, filename)
                cv2.imwrite(filepath, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                capture_count[current_class] += 1
                print(f"[CAPTURED] {filepath} (total: {capture_count[current_class]})")

    except KeyboardInterrupt:
        pass
    finally:
        picam2.stop()
        cv2.destroyAllWindows()

    print("\n" + "=" * 60)
    print("Dataset Summary:")
    print("=" * 60)
    total = 0
    for cls_name in CLASSES.values():
        count = capture_count[cls_name]
        total += count
        status = "OK" if count >= 50 else "NEED MORE" if count > 0 else "EMPTY"
        print(f"  {cls_name:25s}: {count:5d} images  [{status}]")
    print(f"  {'TOTAL':25s}: {total:5d} images")
    print()
    if total < 100:
        print("[WARN] Aim for at least 50-100 images per class for good results.")
    print("[TIP] Also run with --split val to collect validation images (~20% of train).")


def collect_from_webcam(output_dir: str, split: str = "train"):
    """Fallback: collect images using any USB webcam via OpenCV."""
    try:
        import cv2
    except ImportError:
        print("[ERROR] opencv not installed. Run: pip install opencv-python")
        sys.exit(1)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open camera. Check connection.")
        sys.exit(1)

    current_class = 'carrot_peels'
    capture_count = {cls: 0 for cls in CLASSES.values()}

    for cls_name in CLASSES.values():
        cls_dir = os.path.join(output_dir, split, cls_name)
        if os.path.exists(cls_dir):
            capture_count[cls_name] = len([
                f for f in os.listdir(cls_dir)
                if f.lower().endswith(('.jpg', '.jpeg', '.png'))
            ])

    print("=" * 60)
    print("VeggieFeed — Training Data Collection (Webcam Mode)")
    print("=" * 60)
    print(f"Output: {output_dir}/{split}/")
    for key, cls in sorted(CLASSES.items()):
        print(f"  [{key}] {cls} ({capture_count[cls]} existing)")
    print("  [SPACE/ENTER] Capture    [Q] Quit")
    print("=" * 60)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            display = frame.copy()
            label = f"Class: {current_class} ({capture_count[current_class]} images)"
            cv2.putText(display, label, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("VeggieFeed Data Collection", display)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q') or key == 27:
                break
            elif chr(key) in CLASSES if key < 128 else False:
                current_class = CLASSES[chr(key)]
                print(f"[INFO] Switched to class: {current_class}")
            elif key in (32, 13):
                cls_dir = os.path.join(output_dir, split, current_class)
                os.makedirs(cls_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"{current_class}_{timestamp}.jpg"
                filepath = os.path.join(cls_dir, filename)
                cv2.imwrite(filepath, frame)
                capture_count[current_class] += 1
                print(f"[CAPTURED] {filepath} (total: {capture_count[current_class]})")
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()

    total = sum(capture_count.values())
    print(f"\n[DONE] Collected {total} images total.")


def main():
    parser = argparse.ArgumentParser(description="Collect training data for VeggieFeed")
    parser.add_argument("--output", type=str,
                       default=os.path.join(os.path.dirname(__file__), "..", "data", "images"),
                       help="Output directory for images")
    parser.add_argument("--split", type=str, default="train", choices=["train", "val"],
                       help="Dataset split (train or val)")
    parser.add_argument("--webcam", action="store_true",
                       help="Use USB webcam instead of Pi camera")
    args = parser.parse_args()

    if args.webcam:
        collect_from_webcam(args.output, args.split)
    else:
        try:
            collect_with_picamera(args.output, args.split)
        except Exception as e:
            print(f"[WARN] Pi camera failed ({e}), falling back to webcam...")
            collect_from_webcam(args.output, args.split)


if __name__ == "__main__":
    main()
