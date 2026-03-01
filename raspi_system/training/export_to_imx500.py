#!/usr/bin/env python3
"""
VeggieFeed — Export trained YOLO11n model to IMX500 RPK format
==============================================================

Converts a fine-tuned YOLO11n .pt model → ONNX → IMX500 RPK

Requirements:
    pip install ultralytics
    # For RPK conversion, Sony's imx500-converter is needed:
    pip install imx500-converter[pt]
    # OR use the Raspberry Pi IMX500 packaging tools

Usage:
    python export_to_imx500.py --weights runs/classify/veggiefeed_cls/weights/best.pt
    python export_to_imx500.py --weights runs/detect/veggiefeed_det/weights/best.pt --task detect
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path


def export_onnx(weights_path: str, imgsz: int, task: str) -> str:
    """Export YOLO model to ONNX format."""
    try:
        from ultralytics import YOLO
    except ImportError:
        print("[ERROR] ultralytics not installed. Run: pip install ultralytics")
        sys.exit(1)

    print(f"[INFO] Loading model from {weights_path}")
    model = YOLO(weights_path)

    print(f"[INFO] Exporting to ONNX (imgsz={imgsz})...")
    onnx_path = model.export(
        format="onnx",
        imgsz=imgsz,
        simplify=True,
        opset=12,
    )

    print(f"[INFO] ONNX model saved: {onnx_path}")
    return str(onnx_path)


def convert_to_rpk(onnx_path: str, output_dir: str, task: str):
    """
    Convert ONNX model to IMX500 RPK format.

    This requires Sony's imx500-converter tool, which is available on
    Raspberry Pi OS or can be installed separately.
    """
    output_rpk = os.path.join(
        output_dir, "imx500_network_veggiefeed_yolo11n.rpk"
    )

    print(f"[INFO] Converting ONNX to IMX500 RPK format...")
    print(f"[INFO] Output: {output_rpk}")

    # Method 1: Try imx500-converter (Sony's official tool)
    try:
        cmd = [
            "imx500-converter",
            "--onnx-file", onnx_path,
            "--output", output_rpk,
        ]

        if task == "detect":
            # Add post-processing for detection models
            cmd.extend(["--pp", "yolo11"])

        print(f"[INFO] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        print(f"[SUCCESS] RPK model created: {output_rpk}")
        return output_rpk

    except FileNotFoundError:
        print("[WARN] imx500-converter not found in PATH")
        print("[INFO] Trying alternative conversion method...")

    # Method 2: Try packetize tool (Raspberry Pi method)
    try:
        cmd = [
            "imx500-package",
            "-i", onnx_path,
            "-o", output_rpk,
        ]
        print(f"[INFO] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        print(f"[SUCCESS] RPK model created: {output_rpk}")
        return output_rpk

    except FileNotFoundError:
        pass

    print()
    print("=" * 60)
    print("MANUAL CONVERSION REQUIRED")
    print("=" * 60)
    print()
    print("The ONNX model has been exported successfully:")
    print(f"  {onnx_path}")
    print()
    print("To convert to IMX500 RPK format, you need one of:")
    print()
    print("Option A — Sony imx500-converter (recommended):")
    print("  pip install imx500-converter[pt]")
    print(f"  imx500-converter --onnx-file {onnx_path} --output {output_rpk}")
    print()
    print("Option B — Raspberry Pi tools:")
    print("  sudo apt install imx500-tools")
    print(f"  imx500-package -i {onnx_path} -o {output_rpk}")
    print()
    print("Option C — Use Ultralytics IMX500 export (if supported):")
    print("  from ultralytics import YOLO")
    print(f"  model = YOLO('{onnx_path.replace('.onnx', '.pt')}')")
    print("  model.export(format='imx')")
    print()
    return None


def main():
    parser = argparse.ArgumentParser(description="Export YOLO11n to IMX500 RPK")
    parser.add_argument("--weights", type=str, required=True,
                       help="Path to trained .pt weights file")
    parser.add_argument("--task", type=str, default="classify",
                       choices=["classify", "detect"],
                       help="Task type (default: classify)")
    parser.add_argument("--imgsz", type=int, default=None,
                       help="Image size (default: 224 for cls, 640 for det)")
    parser.add_argument("--output-dir", type=str, default="exported_models",
                       help="Output directory for RPK model")
    args = parser.parse_args()

    if args.imgsz is None:
        args.imgsz = 224 if args.task == "classify" else 640

    if not os.path.exists(args.weights):
        print(f"[ERROR] Weights file not found: {args.weights}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    # Step 1: Export to ONNX
    onnx_path = export_onnx(args.weights, args.imgsz, args.task)

    # Step 2: Convert to RPK
    rpk_path = convert_to_rpk(onnx_path, args.output_dir, args.task)

    if rpk_path:
        print(f"\n[DONE] Model ready for IMX500 deployment: {rpk_path}")
        print(f"[NEXT] Copy to the Raspberry Pi and update inference config")


if __name__ == "__main__":
    main()
