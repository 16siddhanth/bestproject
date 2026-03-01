#!/usr/bin/env python3
"""
VeggieFeed — Fine-tune YOLOv11n for Vegetable Peel Classification
=================================================================

This script fine-tunes the Ultralytics YOLOv11n model on a custom dataset
of vegetable peels/waste for the VeggieFeed sorting system.

Requirements:
    pip install ultralytics torch torchvision

Usage:
    # Standard training (GPU recommended):
    python train_yolo11n.py

    # Resume from checkpoint:
    python train_yolo11n.py --resume

    # Custom epochs/batch:
    python train_yolo11n.py --epochs 150 --batch 32

After training, export for IMX500:
    python export_to_imx500.py --weights runs/detect/veggiefeed/weights/best.pt
"""

import argparse
import os
import sys
from pathlib import Path

def check_dataset(data_yaml: str) -> bool:
    """Verify dataset directories exist and have images."""
    import yaml
    with open(data_yaml, 'r') as f:
        config = yaml.safe_load(f)

    base = Path(data_yaml).parent / config['path']
    train_dir = base / config['train']
    val_dir = base / config['val']

    if not train_dir.exists():
        print(f"[ERROR] Training images directory not found: {train_dir}")
        return False
    if not val_dir.exists():
        print(f"[ERROR] Validation images directory not found: {val_dir}")
        return False

    train_images = list(train_dir.rglob("*.jpg")) + list(train_dir.rglob("*.png")) + list(train_dir.rglob("*.jpeg"))
    val_images = list(val_dir.rglob("*.jpg")) + list(val_dir.rglob("*.png")) + list(val_dir.rglob("*.jpeg"))

    print(f"[INFO] Training images found: {len(train_images)}")
    print(f"[INFO] Validation images found: {len(val_images)}")

    if len(train_images) == 0:
        print("[ERROR] No training images found! Please add images to data/images/train/<class_name>/")
        print("[INFO]  For detection: also add YOLO-format labels to data/labels/train/")
        print("[INFO]  For classification: just organize images in class folders")
        return False

    return True


def train(args):
    """Run YOLO11n fine-tuning."""
    try:
        from ultralytics import YOLO
    except ImportError:
        print("[ERROR] ultralytics not installed. Run: pip install ultralytics")
        sys.exit(1)

    data_yaml = os.path.join(os.path.dirname(__file__), "dataset.yaml")

    # For classification task, we can use YOLO classification mode
    # For detection task, we use standard detection mode
    if args.task == "classify":
        print("=" * 60)
        print("VeggieFeed — YOLO11n Classification Fine-tuning")
        print("=" * 60)
        print(f"[INFO] Task: Classification (12 vegetable peel classes)")
        print(f"[INFO] Epochs: {args.epochs}")
        print(f"[INFO] Batch size: {args.batch}")
        print(f"[INFO] Image size: {args.imgsz}")
        print()

        # For classification, dataset is organized as:
        # data/images/train/<class_name>/*.jpg
        # data/images/val/<class_name>/*.jpg
        data_root = os.path.join(os.path.dirname(__file__), "..", "data", "images")

        if not os.path.exists(os.path.join(data_root, "train")):
            print(f"[ERROR] Classification dataset not found at {data_root}")
            print("[INFO]  Organize images as: data/images/train/<class_name>/*.jpg")
            sys.exit(1)

        # Count images per class
        train_dir = os.path.join(data_root, "train")
        total = 0
        for cls_dir in sorted(os.listdir(train_dir)):
            cls_path = os.path.join(train_dir, cls_dir)
            if os.path.isdir(cls_path):
                count = len([f for f in os.listdir(cls_path)
                           if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
                total += count
                print(f"  {cls_dir}: {count} images")

        if total == 0:
            print("\n[ERROR] No images found in class folders!")
            print("[INFO]  Add images to: data/images/train/<class_name>/")
            print("[INFO]  Classes: carrot_peels, potato_skins, onion_skins, etc.")
            print("\n[HINT]  You can collect images by running:")
            print("         python ../scripts/collect_training_data.py")
            sys.exit(1)

        print(f"\n[INFO] Total training images: {total}")
        print(f"[INFO] Loading YOLO11n-cls base model...")

        # Load YOLO11n classification model
        model = YOLO("yolo11n-cls.pt")

        # Fine-tune on our vegetable peel dataset
        results = model.train(
            data=data_root,
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            project="runs/classify",
            name="veggiefeed_cls",
            patience=args.patience,
            lr0=args.lr,
            lrf=0.01,
            warmup_epochs=3,
            warmup_momentum=0.8,
            weight_decay=0.0005,
            hsv_h=0.015,
            hsv_s=0.7,
            hsv_v=0.4,
            degrees=15.0,
            translate=0.1,
            scale=0.5,
            flipud=0.5,
            fliplr=0.5,
            mosaic=0.0,  # disable mosaic for classification
            mixup=0.1,
            erasing=0.2,
            workers=args.workers,
            exist_ok=True,
            verbose=True,
            resume=args.resume,
        )

        best_weights = "runs/classify/veggiefeed_cls/weights/best.pt"
        print(f"\n{'=' * 60}")
        print(f"Training complete!")
        print(f"Best weights: {best_weights}")
        print(f"{'=' * 60}")

    else:
        # Detection mode
        print("=" * 60)
        print("VeggieFeed — YOLO11n Detection Fine-tuning")
        print("=" * 60)
        print(f"[INFO] Task: Detection (12 vegetable peel classes)")
        print(f"[INFO] Dataset: {data_yaml}")
        print(f"[INFO] Epochs: {args.epochs}")
        print(f"[INFO] Batch size: {args.batch}")
        print(f"[INFO] Image size: {args.imgsz}")
        print()

        if not check_dataset(data_yaml):
            print("\n[HINT] To collect and annotate training data, run:")
            print("       python ../scripts/collect_training_data.py")
            sys.exit(1)

        # Load pretrained YOLO11n
        model = YOLO("yolo11n.pt")

        # Fine-tune on vegetable peel dataset
        results = model.train(
            data=data_yaml,
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            project="runs/detect",
            name="veggiefeed_det",
            patience=args.patience,
            lr0=args.lr,
            lrf=0.01,
            warmup_epochs=3,
            warmup_momentum=0.8,
            weight_decay=0.0005,
            hsv_h=0.015,
            hsv_s=0.7,
            hsv_v=0.4,
            degrees=10.0,
            translate=0.1,
            scale=0.5,
            flipud=0.5,
            fliplr=0.5,
            mosaic=1.0,
            mixup=0.1,
            workers=args.workers,
            exist_ok=True,
            verbose=True,
            resume=args.resume,
        )

        best_weights = "runs/detect/veggiefeed_det/weights/best.pt"
        print(f"\n{'=' * 60}")
        print(f"Training complete!")
        print(f"Best weights: {best_weights}")
        print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="VeggieFeed YOLO11n Training")
    parser.add_argument("--task", type=str, default="classify",
                       choices=["classify", "detect"],
                       help="Task type: 'classify' for classification, 'detect' for detection")
    parser.add_argument("--epochs", type=int, default=100,
                       help="Number of training epochs (default: 100)")
    parser.add_argument("--batch", type=int, default=16,
                       help="Batch size (default: 16)")
    parser.add_argument("--imgsz", type=int, default=224,
                       help="Image size (default: 224 for cls, use 640 for det)")
    parser.add_argument("--lr", type=float, default=0.01,
                       help="Initial learning rate (default: 0.01)")
    parser.add_argument("--patience", type=int, default=20,
                       help="Early stopping patience (default: 20)")
    parser.add_argument("--workers", type=int, default=4,
                       help="Dataloader workers (default: 4)")
    parser.add_argument("--resume", action="store_true",
                       help="Resume from last checkpoint")
    args = parser.parse_args()

    # For detection, default to 640
    if args.task == "detect" and args.imgsz == 224:
        args.imgsz = 640

    train(args)


if __name__ == "__main__":
    main()
