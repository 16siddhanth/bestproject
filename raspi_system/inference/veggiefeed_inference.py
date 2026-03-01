#!/usr/bin/env python3
"""
VeggieFeed — IMX500 AI Camera Inference Engine
===============================================

Runs real-time vegetable peel classification or detection on the
Raspberry Pi AI Camera (IMX500) using a YOLO11n model.

Supports two modes:
  1. Classification mode (yolo11n-cls): Classifies the entire frame
  2. Detection mode (yolo11n with post-processing): Detects + classifies objects

The script exposes results via a shared state that the API server reads.

Usage:
    # Classification with custom fine-tuned model:
    python veggiefeed_inference.py --model /path/to/veggiefeed_cls.rpk --task classify

    # Detection with YOLO11n_pp (post-processed):
    python veggiefeed_inference.py --model /path/to/imx500_network_yolo11n_pp.rpk --task detect

    # Use the existing YOLO11n COCO model (for initial testing):
    python veggiefeed_inference.py --model ../models/coco_pretrained/imx500_network_yolo11n_pp.rpk --task detect
"""

import argparse
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# ──────────────────────────────────────────────────────────────
# Vegetable peel class definitions
# ──────────────────────────────────────────────────────────────

VEGGIE_CLASSES = [
    "Carrot Peels",
    "Potato Skins",
    "Onion Skins",
    "Tomato Skins",
    "Cucumber Peels",
    "Cabbage Leaves",
    "Lettuce",
    "Bell Pepper Scraps",
    "Broccoli Stems",
    "Cauliflower Leaves",
    "Celery",
    "Spinach",
]

# Mapping from COCO classes to our vegetable peel classes (pre-trained YOLO11n COCO).
# ONLY exact matches are mapped. Everything else is dropped.
# Used during initial testing before fine-tuning on real peel images.
COCO_TO_VEGGIE = {
    "broccoli": "Broccoli Stems",
    "carrot": "Carrot Peels",
}

# Bin assignment for segregation
VEGGIE_TO_BIN = {
    "Carrot Peels": 0,
    "Potato Skins": 1,
    "Onion Skins": 2,
    "Tomato Skins": 0,
    "Cucumber Peels": 1,
    "Cabbage Leaves": 3,
    "Lettuce": 3,
    "Bell Pepper Scraps": 0,
    "Broccoli Stems": 2,
    "Cauliflower Leaves": 3,
    "Celery": 2,
    "Spinach": 3,
}

# Color per class for display
CLASS_COLORS = {
    "Carrot Peels": (0, 165, 255),
    "Potato Skins": (139, 195, 230),
    "Onion Skins": (167, 167, 167),
    "Tomato Skins": (0, 0, 255),
    "Cucumber Peels": (0, 200, 0),
    "Cabbage Leaves": (0, 160, 0),
    "Lettuce": (0, 255, 128),
    "Bell Pepper Scraps": (0, 100, 255),
    "Broccoli Stems": (0, 128, 0),
    "Cauliflower Leaves": (200, 255, 200),
    "Celery": (100, 200, 100),
    "Spinach": (0, 100, 50),
}


@dataclass
class ClassificationResult:
    label: str
    confidence: float
    bin_id: int
    timestamp: float = 0.0

    def to_dict(self):
        return {
            "label": self.label,
            "confidence": round(self.confidence * 100, 2),
            "bin_id": self.bin_id,
            "timestamp": self.timestamp,
        }


@dataclass
class InferenceState:
    """Shared state between inference engine and API server."""
    results: List[ClassificationResult] = field(default_factory=list)
    last_frame_base64: Optional[str] = None
    last_frame_jpeg: Optional[bytes] = None   # Raw JPEG bytes for MJPEG stream
    detections: list = field(default_factory=list)  # Raw detection dicts with boxes
    fps: float = 0.0
    is_running: bool = False
    last_update: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def update(self, results: List[ClassificationResult], frame_b64: Optional[str] = None,
               frame_jpeg: Optional[bytes] = None, raw_detections: Optional[list] = None):
        with self.lock:
            self.results = results
            self.last_frame_base64 = frame_b64
            if frame_jpeg is not None:
                self.last_frame_jpeg = frame_jpeg
            if raw_detections is not None:
                self.detections = raw_detections
            self.last_update = time.time()

    def get_frame_jpeg(self) -> Optional[bytes]:
        """Get the latest annotated JPEG frame for MJPEG streaming."""
        with self.lock:
            return self.last_frame_jpeg

    def get_state(self) -> dict:
        with self.lock:
            return {
                "results": [r.to_dict() for r in self.results],
                "detections": self.detections,
                "fps": round(self.fps, 1),
                "is_running": self.is_running,
                "last_update": self.last_update,
                "has_frame": self.last_frame_jpeg is not None,
            }

    def get_top_result(self) -> Optional[ClassificationResult]:
        with self.lock:
            if self.results:
                return self.results[0]
            return None


# Global shared state — imported by the API server
inference_state = InferenceState()


# ──────────────────────────────────────────────────────────────
# Classification mode (for custom fine-tuned classification model)
# ──────────────────────────────────────────────────────────────

def run_classification_inference(model_path: str, labels: List[str],
                                  headless: bool = False, save_frames: bool = False):
    """Run classification inference using IMX500."""
    from picamera2 import CompletedRequest, MappedArray, Picamera2
    from picamera2.devices import IMX500
    from picamera2.devices.imx500 import NetworkIntrinsics
    from picamera2.devices.imx500.postprocess import softmax

    imx500 = IMX500(model_path)
    intrinsics = imx500.network_intrinsics or NetworkIntrinsics()
    intrinsics.task = "classification"
    intrinsics.labels = labels
    intrinsics.softmax = True
    intrinsics.update_with_defaults()

    picam2 = Picamera2(imx500.camera_num)
    config = picam2.create_preview_configuration(
        controls={"FrameRate": intrinsics.inference_rate},
        buffer_count=12,
    )

    last_detections = []
    frame_count = 0
    fps_start = time.time()

    def parse_and_draw(request: CompletedRequest):
        nonlocal last_detections, frame_count, fps_start

        np_outputs = imx500.get_outputs(request.get_metadata())
        if np_outputs is not None:
            np_output = np_outputs[0]
            if intrinsics.softmax:
                np_output = softmax(np_output)

            # Get top 3
            top_indices = np.argpartition(-np_output, 3)[:3]
            top_indices = top_indices[np.argsort(-np_output[top_indices])]

            results = []
            for idx in top_indices:
                label = labels[idx] if idx < len(labels) else "Unknown"
                conf = float(np_output[idx])
                bin_id = VEGGIE_TO_BIN.get(label, 0)
                results.append(ClassificationResult(
                    label=label,
                    confidence=conf,
                    bin_id=bin_id,
                    timestamp=time.time(),
                ))
            last_detections = results

        # Update FPS
        frame_count += 1
        elapsed = time.time() - fps_start
        if elapsed >= 1.0:
            inference_state.fps = frame_count / elapsed
            frame_count = 0
            fps_start = time.time()

        # Always draw annotations and encode JPEG for the MJPEG stream
        with MappedArray(request, "main") as m:
            frame = m.array.copy()
            # picamera2 default XRGB8888 delivers RGBA in numpy; convert to BGR for OpenCV
            if frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
            else:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            for i, det in enumerate(last_detections):
                color = CLASS_COLORS.get(det.label, (255, 255, 0))
                text = f"{det.label}: {det.confidence:.1%}"
                cv2.putText(frame, text, (10, 30 + i * 25),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            # Show FPS
            cv2.putText(frame, f"FPS: {inference_state.fps:.1f}",
                       (10, frame.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # Encode annotated frame as JPEG for MJPEG streaming
            _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_jpeg = buf.tobytes()

            # Also write annotations to the preview buffer
            if not headless:
                np.copyto(m.array, frame)

        inference_state.update(
            last_detections if last_detections else [],
            frame_jpeg=frame_jpeg,
        )

    imx500.show_network_fw_progress_bar()
    inference_state.is_running = True

    picam2.start(config, show_preview=not headless)
    picam2.pre_callback = parse_and_draw

    print(f"[INFO] Classification inference started (model: {model_path})")
    print(f"[INFO] Classes: {len(labels)}")
    print(f"[INFO] Headless: {headless}")

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping inference...")
    finally:
        inference_state.is_running = False
        picam2.stop()


# ──────────────────────────────────────────────────────────────
# Detection mode (for YOLO11n with post-processing)
# ──────────────────────────────────────────────────────────────

def run_detection_inference(model_path: str, labels: List[str],
                             threshold: float = 0.30, iou: float = 0.5,
                             headless: bool = False, save_frames: bool = False,
                             use_coco_mapping: bool = False):
    """Run YOLO11n detection inference using IMX500."""
    from picamera2 import CompletedRequest, MappedArray, Picamera2
    from picamera2.devices import IMX500
    from picamera2.devices.imx500 import NetworkIntrinsics

    imx500 = IMX500(model_path)
    intrinsics = imx500.network_intrinsics or NetworkIntrinsics()
    intrinsics.task = "object detection"
    intrinsics.labels = labels
    intrinsics.update_with_defaults()

    picam2 = Picamera2(imx500.camera_num)
    config = picam2.create_preview_configuration(
        controls={"FrameRate": intrinsics.inference_rate},
        buffer_count=12,
    )

    last_detections = []
    last_results = []
    frame_count = 0
    fps_start = time.time()

    def parse_detections(metadata: dict):
        nonlocal last_detections
        np_outputs = imx500.get_outputs(metadata, add_batch=True)
        if np_outputs is None:
            return last_detections

        input_w, input_h = imx500.get_input_size()

        # The _pp (post-processed) model outputs: boxes, scores, classes
        boxes = np_outputs[0][0]
        scores = np_outputs[1][0]
        classes = np_outputs[2][0]

        detections = []
        for box, score, cls_id in zip(boxes, scores, classes):
            if score < threshold:
                continue

            cls_idx = int(cls_id)
            if cls_idx >= len(labels):
                continue

            raw_label = labels[cls_idx]
            if raw_label == "-":
                continue  # Skip gap IDs in COCO label list

            # Map to veggie class if using COCO model
            if use_coco_mapping:
                mapped = COCO_TO_VEGGIE.get(raw_label.lower().strip(), None)
                label = mapped if mapped else raw_label
                is_veggie = mapped is not None
            else:
                label = raw_label
                is_veggie = True

            bin_id = VEGGIE_TO_BIN.get(label, 0) if is_veggie else -1

            # Try convert_inference_coords first; if coords are absurd, use raw scaling
            try:
                coord = imx500.convert_inference_coords(box, metadata, picam2)
                cx, cy, cw, ch = coord
                # Sanity check: if coords are way off, fall back to manual scaling
                if cx > 5000 or cy > 5000 or cw <= 0 or ch <= 0:
                    raise ValueError("coords out of range")
            except Exception:
                # Manual scaling: box is [y0, x0, y1, x1] normalized or [x0, y0, x1, y1] in input coords
                # Get output frame size
                stream_cfg = picam2.camera_configuration()["main"]
                out_w, out_h = stream_cfg["size"]

                b = box.copy() if hasattr(box, 'copy') else list(box)

                # Check if normalized (all values 0-1) or in pixel coords
                max_val = max(abs(float(v)) for v in b)
                if max_val <= 1.0:
                    # Normalized: [y0, x0, y1, x1]
                    y0, x0, y1, x1 = [float(v) for v in b]
                    px = int(x0 * out_w)
                    py = int(y0 * out_h)
                    pw = int((x1 - x0) * out_w)
                    ph = int((y1 - y0) * out_h)
                else:
                    # Pixel coords in input space: try [x0, y0, w, h] or [x0, y0, x1, y1]
                    vals = [float(v) for v in b]
                    # Scale from input to output
                    sx = out_w / input_w
                    sy = out_h / input_h
                    if vals[2] > input_w * 0.5 and vals[3] > input_h * 0.5:
                        # Likely [x0, y0, x1, y1]
                        px = int(vals[0] * sx)
                        py = int(vals[1] * sy)
                        pw = int((vals[2] - vals[0]) * sx)
                        ph = int((vals[3] - vals[1]) * sy)
                    else:
                        # Likely [x0, y0, w, h]
                        px = int(vals[0] * sx)
                        py = int(vals[1] * sy)
                        pw = int(vals[2] * sx)
                        ph = int(vals[3] * sy)
                coord = (px, py, pw, ph)

            detections.append({
                "label": label,
                "confidence": float(score),
                "bin_id": bin_id,
                "box": coord,  # (x, y, w, h)
                "timestamp": time.time(),
                "is_veggie": is_veggie,
            })

        last_detections = detections

        # Update inference state with veggie-only results (for sorting logic)
        veggie_dets = [d for d in detections if d.get("is_veggie", False)]
        raw_det_dicts = [
            {"label": d["label"], "confidence": d["confidence"], "bin_id": d["bin_id"],
             "box": list(d["box"]), "timestamp": d["timestamp"]}
            for d in veggie_dets
        ]
        if veggie_dets:
            class_scores: Dict[str, float] = {}
            for det in veggie_dets:
                lbl = det["label"]
                class_scores[lbl] = max(class_scores.get(lbl, 0), det["confidence"])

            results = []
            for lbl, conf in sorted(class_scores.items(), key=lambda x: -x[1])[:3]:
                results.append(ClassificationResult(
                    label=lbl,
                    confidence=conf,
                    bin_id=VEGGIE_TO_BIN.get(lbl, 0),
                    timestamp=time.time(),
                ))
            inference_state.update(results, raw_detections=raw_det_dicts)
        else:
            inference_state.update([], raw_detections=[])

        return detections

    def draw_detections(request: CompletedRequest):
        nonlocal frame_count, fps_start

        # Parse detections from THIS frame's metadata (ensures boxes match the frame)
        parse_detections(request.get_metadata())

        # Update FPS
        frame_count += 1
        elapsed = time.time() - fps_start
        if elapsed >= 1.0:
            inference_state.fps = frame_count / elapsed
            frame_count = 0
            fps_start = time.time()

        # Always draw annotations and encode JPEG for MJPEG stream
        with MappedArray(request, "main") as m:
            frame = m.array.copy()
            # picamera2 default XRGB8888 delivers RGBA in numpy; convert to BGR for OpenCV
            if frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
            else:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            dets = list(last_detections)  # snapshot to avoid mutation

            if dets:
                for det in dets:
                    # convert_inference_coords returns (x, y, width, height)
                    x, y, w, h = [int(v) for v in det["box"]]
                    label = det["label"]
                    conf = det["confidence"]
                    is_veggie = det.get("is_veggie", False)

                    if is_veggie:
                        color = CLASS_COLORS.get(label, (0, 255, 0))
                        box_thickness = 3
                        font_scale = 0.7
                        font_thickness = 2
                    else:
                        color = (128, 128, 128)
                        box_thickness = 1
                        font_scale = 0.5
                        font_thickness = 1

                    # Bounding box — (x,y) top-left to (x+w, y+h) bottom-right
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, box_thickness)

                    # Label background + text
                    text = f"{label}: {conf:.0%}"
                    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
                    cv2.rectangle(frame, (x, max(y - th - 10, 0)), (x + tw + 6, y), color, -1)
                    cv2.putText(frame, text, (x + 3, max(y - 5, th + 5)),
                               cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), font_thickness)
            else:
                # Show "no detection" overlay so user knows the stream is alive
                overlay_text = "VeggieFeed | No peel detected"
                cv2.putText(frame, overlay_text, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)

            # Show FPS + detection count
            status = f"FPS: {inference_state.fps:.1f}  |  Detections: {len(dets)}"
            cv2.putText(frame, status,
                       (10, frame.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Encode annotated frame as JPEG for MJPEG streaming
            _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_jpeg = buf.tobytes()
            # Only update the frame — don't overwrite results (parse_detections handles that)
            with inference_state.lock:
                inference_state.last_frame_jpeg = frame_jpeg

            # Write annotations to the preview buffer
            if not headless:
                np.copyto(m.array, frame)

    imx500.show_network_fw_progress_bar()
    inference_state.is_running = True

    picam2.start(config, show_preview=not headless)
    picam2.pre_callback = draw_detections

    print(f"[INFO] Detection inference started (model: {model_path})")
    print(f"[INFO] Labels: {len(labels)},  Threshold: {threshold}")
    print(f"[INFO] COCO mapping: {use_coco_mapping}")

    try:
        while True:
            time.sleep(0.1)  # parse_detections is now called inside draw_detections callback
    except KeyboardInterrupt:
        print("\n[INFO] Stopping inference...")
    finally:
        inference_state.is_running = False
        picam2.stop()


# ──────────────────────────────────────────────────────────────
# Fallback: Software-based YOLO inference (no IMX500 required)
# ──────────────────────────────────────────────────────────────

def run_software_inference(model_path: str, labels: List[str],
                            threshold: float = 0.4, headless: bool = False):
    """
    Run YOLO inference in software using Ultralytics.
    Fallback for when IMX500 camera is not available (e.g., development/testing).
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        print("[ERROR] ultralytics not installed for software inference.")
        print("  pip install ultralytics")
        sys.exit(1)

    try:
        from picamera2 import Picamera2
        picam2 = Picamera2()
        config = picam2.create_preview_configuration(
            main={"size": (640, 480)}
        )
        picam2.configure(config)
        picam2.start()
        use_picam = True
    except Exception:
        print("[WARN] Picamera2 not available, using USB camera")
        import cv2
        cap = cv2.VideoCapture(0)
        use_picam = False

    model = YOLO(model_path)
    inference_state.is_running = True
    frame_count = 0
    fps_start = time.time()

    print(f"[INFO] Software inference started (model: {model_path})")

    try:
        while True:
            if use_picam:
                frame = picam2.capture_array()
                # picamera2 delivers RGB; convert to BGR for OpenCV/YOLO
                if frame.shape[2] == 4:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                else:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            else:
                ret, frame = cap.read()
                if not ret:
                    continue

            # Run inference
            results = model(frame, verbose=False, conf=threshold)

            # Parse results
            detections = []
            for r in results:
                for box in r.boxes:
                    cls_idx = int(box.cls[0])
                    conf = float(box.conf[0])
                    label = labels[cls_idx] if cls_idx < len(labels) else "Unknown"
                    bin_id = VEGGIE_TO_BIN.get(label, 0)

                    detections.append(ClassificationResult(
                        label=label,
                        confidence=conf,
                        bin_id=bin_id,
                        timestamp=time.time(),
                    ))

            detections.sort(key=lambda x: -x.confidence)

            # FPS
            frame_count += 1
            elapsed = time.time() - fps_start
            if elapsed >= 1.0:
                inference_state.fps = frame_count / elapsed
                frame_count = 0
                fps_start = time.time()

            # Always annotate and encode for MJPEG stream
            annotated = results[0].plot() if results else frame.copy()
            cv2.putText(annotated, f"FPS: {inference_state.fps:.1f}",
                       (10, annotated.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            _, buf = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_jpeg = buf.tobytes()
            inference_state.update(detections[:3], frame_jpeg=frame_jpeg)

            if not headless:
                cv2.imshow("VeggieFeed", annotated)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    except KeyboardInterrupt:
        pass
    finally:
        inference_state.is_running = False
        if use_picam:
            picam2.stop()
        else:
            cap.release()
        cv2.destroyAllWindows()


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

def get_args():
    parser = argparse.ArgumentParser(description="VeggieFeed IMX500 Inference Engine")
    parser.add_argument("--model", type=str, required=True,
                       help="Path to .rpk model (IMX500) or .pt model (software)")
    parser.add_argument("--task", type=str, default="detect",
                       choices=["classify", "detect", "software"],
                       help="Inference mode")
    parser.add_argument("--labels", type=str, default=None,
                       help="Path to labels file (one label per line)")
    parser.add_argument("--threshold", type=float, default=0.4,
                       help="Detection confidence threshold (default: 0.4)")
    parser.add_argument("--iou", type=float, default=0.5,
                       help="IoU threshold for NMS (default: 0.5)")
    parser.add_argument("--headless", action="store_true",
                       help="Run without preview window")
    parser.add_argument("--save-frames", action="store_true",
                       help="Save frames as base64 for API access")
    parser.add_argument("--coco", action="store_true",
                       help="Use COCO→Veggie class mapping (for pre-trained model)")
    return parser.parse_args()


def load_labels(labels_path: Optional[str], task: str, use_coco: bool) -> List[str]:
    """Load label list."""
    if labels_path:
        with open(labels_path, 'r') as f:
            return [line.strip() for line in f.readlines() if line.strip()]

    if use_coco:
        # COCO labels
        coco_path = os.path.join(os.path.dirname(__file__), "..", "data", "coco_labels.txt")
        if os.path.exists(coco_path):
            with open(coco_path, 'r') as f:
                return [line.strip() for line in f.readlines() if line.strip()]

    # Default to our veggie classes
    return VEGGIE_CLASSES


if __name__ == "__main__":
    args = get_args()

    labels = load_labels(args.labels, args.task, args.coco)

    if args.task == "classify":
        run_classification_inference(
            model_path=args.model,
            labels=labels,
            headless=args.headless,
            save_frames=args.save_frames,
        )
    elif args.task == "detect":
        run_detection_inference(
            model_path=args.model,
            labels=labels,
            threshold=args.threshold,
            iou=args.iou,
            headless=args.headless,
            save_frames=args.save_frames,
            use_coco_mapping=args.coco,
        )
    elif args.task == "software":
        run_software_inference(
            model_path=args.model,
            labels=labels,
            threshold=args.threshold,
            headless=args.headless,
        )
