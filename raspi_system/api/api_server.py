#!/usr/bin/env python3
"""
VeggieFeed — Local Classification API Server
=============================================

Flask-based REST API running on the Raspberry Pi that exposes:
  - GET  /health              → System health check
  - GET  /status              → Full system status (inference + hardware)
  - POST /classify            → Get latest classification result
  - POST /classify-image      → Classify a provided image (base64)
  - GET  /classes             → List of supported classes
  - POST /hardware/conveyor   → Control conveyor belt
  - POST /hardware/divert     → Manually divert to bin
  - GET  /hardware/status     → Hardware status
  - GET  /stream              → MJPEG video stream

The API reads classification results from the shared inference state
and controls hardware via the HardwareController.

Requirements:
    pip install flask flask-cors

Usage:
    python api_server.py --port 5000
"""

import argparse
import base64
import json
import logging
import os
import sys
import time
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

logger = logging.getLogger("veggiefeed.api")

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from the Next.js frontend

# ──────────────────────────────────────────────────────────────
# References to shared state (set by main.py when starting the system)
# ──────────────────────────────────────────────────────────────

# These will be set by the system orchestrator
_inference_state = None    # From veggiefeed_inference.py
_hardware = None           # From hardware_controller.py

# Nutrition data for each vegetable class (per 100g, approximate USDA values)
NUTRITION_DATA = {
    "Carrot Peels": {"protein": 0.9, "fiber": 2.8, "moisture": 88.0, "energy": 41},
    "Potato Skins": {"protein": 2.6, "fiber": 2.2, "moisture": 79.0, "energy": 87},
    "Onion Skins": {"protein": 1.1, "fiber": 1.7, "moisture": 89.0, "energy": 40},
    "Tomato Skins": {"protein": 0.9, "fiber": 1.2, "moisture": 94.0, "energy": 18},
    "Cucumber Peels": {"protein": 0.7, "fiber": 1.0, "moisture": 95.0, "energy": 15},
    "Cabbage Leaves": {"protein": 1.3, "fiber": 2.5, "moisture": 92.0, "energy": 25},
    "Lettuce": {"protein": 1.4, "fiber": 1.3, "moisture": 95.0, "energy": 15},
    "Bell Pepper Scraps": {"protein": 1.0, "fiber": 2.1, "moisture": 92.0, "energy": 31},
    "Broccoli Stems": {"protein": 2.8, "fiber": 2.6, "moisture": 89.0, "energy": 34},
    "Cauliflower Leaves": {"protein": 1.9, "fiber": 2.0, "moisture": 92.0, "energy": 25},
    "Celery": {"protein": 0.7, "fiber": 1.6, "moisture": 95.0, "energy": 14},
    "Spinach": {"protein": 2.9, "fiber": 2.2, "moisture": 91.0, "energy": 23},
}

# Feed recommendations per class
FEED_RECOMMENDATIONS = {
    "Carrot Peels": [
        {"animalType": "Cattle", "suitability": "High",
         "processingRequired": ["Chopping", "Mixing with feed"],
         "nutritionalBenefit": "Rich in beta-carotene and fiber, excellent for dairy cattle."},
        {"animalType": "Poultry", "suitability": "Medium",
         "processingRequired": ["Drying", "Grinding"],
         "nutritionalBenefit": "Good source of vitamins A and K for egg production."},
    ],
    "Potato Skins": [
        {"animalType": "Pigs", "suitability": "High",
         "processingRequired": ["Cooking", "Mashing"],
         "nutritionalBenefit": "High energy content suitable for pig fattening."},
        {"animalType": "Cattle", "suitability": "Medium",
         "processingRequired": ["Chopping", "Ensiling"],
         "nutritionalBenefit": "Starch-rich supplement for ruminant diets."},
    ],
    "Onion Skins": [
        {"animalType": "Cattle", "suitability": "Low",
         "processingRequired": ["Drying", "Small quantities only"],
         "nutritionalBenefit": "Contains quercetin antioxidants, use sparingly due to strong flavor."},
    ],
    "Tomato Skins": [
        {"animalType": "Poultry", "suitability": "High",
         "processingRequired": ["Drying", "Grinding"],
         "nutritionalBenefit": "Lycopene-rich, improves egg yolk color and antioxidant status."},
        {"animalType": "Pigs", "suitability": "Medium",
         "processingRequired": ["Mixing with feed"],
         "nutritionalBenefit": "Good palatability and vitamin C content."},
    ],
    "Cucumber Peels": [
        {"animalType": "Cattle", "suitability": "High",
         "processingRequired": ["Chopping"],
         "nutritionalBenefit": "High moisture content helps with hydration, good fiber source."},
        {"animalType": "Goats", "suitability": "High",
         "processingRequired": ["Fresh feeding"],
         "nutritionalBenefit": "Palatable and hydrating, easily digestible."},
    ],
    "Cabbage Leaves": [
        {"animalType": "Cattle", "suitability": "High",
         "processingRequired": ["Chopping", "Wilting"],
         "nutritionalBenefit": "Excellent roughage with good vitamin K content."},
        {"animalType": "Poultry", "suitability": "Medium",
         "processingRequired": ["Shredding"],
         "nutritionalBenefit": "Provides variety and micronutrients in poultry diets."},
    ],
    "Lettuce": [
        {"animalType": "Rabbits", "suitability": "High",
         "processingRequired": ["Fresh feeding"],
         "nutritionalBenefit": "Hydrating and palatable, natural rabbit food."},
        {"animalType": "Poultry", "suitability": "Medium",
         "processingRequired": ["Chopping"],
         "nutritionalBenefit": "Low-calorie green supplement."},
    ],
    "Bell Pepper Scraps": [
        {"animalType": "Poultry", "suitability": "High",
         "processingRequired": ["Chopping", "Removing seeds"],
         "nutritionalBenefit": "Vitamin C-rich, supports immune function."},
        {"animalType": "Pigs", "suitability": "Medium",
         "processingRequired": ["Chopping", "Mixing"],
         "nutritionalBenefit": "Good palatability and vitamin content."},
    ],
    "Broccoli Stems": [
        {"animalType": "Cattle", "suitability": "High",
         "processingRequired": ["Chopping", "Ensiling"],
         "nutritionalBenefit": "High protein for a vegetable, supports milk production."},
        {"animalType": "Goats", "suitability": "High",
         "processingRequired": ["Chopping"],
         "nutritionalBenefit": "Nutrient-dense and palatable for goats."},
    ],
    "Cauliflower Leaves": [
        {"animalType": "Cattle", "suitability": "High",
         "processingRequired": ["Chopping", "Fresh or ensiled"],
         "nutritionalBenefit": "Good protein and fiber balance for ruminants."},
        {"animalType": "Goats", "suitability": "High",
         "processingRequired": ["Fresh feeding"],
         "nutritionalBenefit": "Readily consumed, good nutritional profile."},
    ],
    "Celery": [
        {"animalType": "Rabbits", "suitability": "High",
         "processingRequired": ["Chopping into small pieces"],
         "nutritionalBenefit": "Crunchy texture supports dental health."},
        {"animalType": "Cattle", "suitability": "Medium",
         "processingRequired": ["Chopping", "Mixing"],
         "nutritionalBenefit": "Low-calorie fiber supplement."},
    ],
    "Spinach": [
        {"animalType": "Poultry", "suitability": "High",
         "processingRequired": ["Fresh feeding", "Chopping"],
         "nutritionalBenefit": "Iron and calcium rich, supports egg shell quality."},
        {"animalType": "Pigs", "suitability": "Medium",
         "processingRequired": ["Mixing with feed"],
         "nutritionalBenefit": "High vitamin and mineral content."},
    ],
}


def set_inference_state(state):
    """Set the inference state reference (called by main.py)."""
    global _inference_state
    _inference_state = state


def set_hardware(hw):
    """Set the hardware controller reference (called by main.py)."""
    global _hardware
    _hardware = hw


# ──────────────────────────────────────────────────────────────
# API Routes
# ──────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """System health check."""
    return jsonify({
        "status": "healthy",
        "service": "VeggieFeed Pi Classification Server",
        "version": "1.0.0",
        "inference_running": _inference_state.is_running if _inference_state else False,
        "hardware_connected": _hardware is not None,
        "timestamp": time.time(),
    })


@app.route("/status", methods=["GET"])
def status():
    """Full system status."""
    result = {
        "inference": _inference_state.get_state() if _inference_state else None,
        "hardware": _hardware.get_status() if _hardware else None,
        "timestamp": time.time(),
    }
    return jsonify(result)


@app.route("/classes", methods=["GET"])
def classes():
    """List supported vegetable peel classes."""
    from inference.veggiefeed_inference import VEGGIE_CLASSES, VEGGIE_TO_BIN
    return jsonify({
        "classes": VEGGIE_CLASSES,
        "count": len(VEGGIE_CLASSES),
        "bin_assignment": VEGGIE_TO_BIN,
        "timestamp": time.time(),
    })


@app.route("/classify", methods=["POST"])
def classify():
    """
    Get the latest classification result from the inference engine.
    This returns whatever the camera is currently seeing.
    """
    if not _inference_state:
        return jsonify({"success": False, "error": "Inference engine not running"}), 503

    state = _inference_state.get_state()
    results = state.get("results", [])

    if not results:
        return jsonify({
            "success": False,
            "error": "No classification results available",
            "inference_running": state.get("is_running", False),
        }), 404

    top = results[0]
    label = top["label"]

    # Build full response matching the frontend's expected format
    response = {
        "success": True,
        "classification": {
            "top3": [
                {
                    "label": r["label"],
                    "confidence": r["confidence"],
                    "color": _pick_color(r["label"]),
                }
                for r in results[:3]
            ],
            "primaryLabel": label,
            "confidence": top["confidence"],
        },
        "bin_id": top.get("bin_id", 0),
        "nutrition": NUTRITION_DATA.get(label),
        "recommendations": FEED_RECOMMENDATIONS.get(label, []),
        "processingTime": int((time.time() - state.get("last_update", time.time())) * 1000),
        "timestamp": time.time(),
    }

    return jsonify(response)


@app.route("/classify-image", methods=["POST"])
def classify_image():
    """
    Classify a provided image (base64 encoded).
    For use when the frontend captures an image via browser camera.
    Falls back to software inference if no IMX500 results available.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No JSON body"}), 400

    image_base64 = data.get("imageBase64") or data.get("image_base64")
    if not image_base64:
        return jsonify({"success": False, "error": "No image provided"}), 400

    # If inference engine is running, return its latest results
    # (the camera feed takes priority over uploaded images)
    if _inference_state and _inference_state.is_running:
        state = _inference_state.get_state()
        results = state.get("results", [])
        if results:
            top = results[0]
            label = top["label"]
            return jsonify({
                "success": True,
                "classification": {
                    "top3": [
                        {
                            "label": r["label"],
                            "confidence": r["confidence"],
                            "color": _pick_color(r["label"]),
                        }
                        for r in results[:3]
                    ],
                    "primaryLabel": label,
                    "confidence": top["confidence"],
                },
                "bin_id": top.get("bin_id", 0),
                "nutrition": NUTRITION_DATA.get(label),
                "recommendations": FEED_RECOMMENDATIONS.get(label, []),
                "processingTime": 0,
                "timestamp": time.time(),
            })

    # Fallback: try software YOLO inference on the provided image
    try:
        return _software_classify(image_base64)
    except Exception as e:
        logger.error(f"Software classification failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _software_classify(image_base64: str):
    """Run classification using Ultralytics YOLO on a single image."""
    import cv2
    import numpy as np

    try:
        from ultralytics import YOLO
    except ImportError:
        return jsonify({"success": False, "error": "No inference backend available"}), 503

    # Decode base64 image
    if "," in image_base64:
        image_base64 = image_base64.split(",", 1)[1]

    img_bytes = base64.b64decode(image_base64)
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return jsonify({"success": False, "error": "Invalid image"}), 400

    # Load model (cached after first load)
    model_path = os.environ.get("VEGGIEFEED_MODEL",
                                os.path.join(os.path.dirname(__file__), "..",
                                             "training", "runs", "classify",
                                             "veggiefeed_cls", "weights", "best.pt"))
    if not os.path.exists(model_path):
        return jsonify({"success": False, "error": "Model not found. Train the model first."}), 503

    model = YOLO(model_path)
    results = model(img, verbose=False)

    from inference.veggiefeed_inference import VEGGIE_CLASSES, VEGGIE_TO_BIN

    # Parse results
    top3 = []
    if results and results[0].probs is not None:
        probs = results[0].probs
        top5_indices = probs.top5
        top5_conf = probs.top5conf.tolist()
        names = results[0].names

        for idx, conf in zip(top5_indices[:3], top5_conf[:3]):
            label = names.get(idx, "Unknown")
            # Map class folder name to display name
            display_label = _folder_to_display(label)
            top3.append({
                "label": display_label,
                "confidence": round(conf * 100, 2),
                "color": _pick_color(display_label),
            })

    if not top3:
        return jsonify({"success": False, "error": "Could not classify image"}), 422

    primary = top3[0]
    return jsonify({
        "success": True,
        "classification": {
            "top3": top3,
            "primaryLabel": primary["label"],
            "confidence": primary["confidence"],
        },
        "bin_id": VEGGIE_TO_BIN.get(primary["label"], 0),
        "nutrition": NUTRITION_DATA.get(primary["label"]),
        "recommendations": FEED_RECOMMENDATIONS.get(primary["label"], []),
        "processingTime": 0,
        "timestamp": time.time(),
    })


# ──────────────────────────────────────────────────────────────
# Hardware control endpoints
# ──────────────────────────────────────────────────────────────

@app.route("/hardware/status", methods=["GET"])
def hardware_status():
    if not _hardware:
        return jsonify({"error": "Hardware not connected"}), 503
    return jsonify(_hardware.get_status())


@app.route("/stream", methods=["GET"])
def video_stream():
    """
    MJPEG video stream of the annotated camera feed with bounding boxes.
    Consumed by the Next.js frontend via <img src="..."> tag.
    """
    def generate():
        while True:
            if not _inference_state:
                time.sleep(0.1)
                continue
            frame = _inference_state.get_frame_jpeg()
            if frame is None:
                time.sleep(0.05)
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
            time.sleep(0.033)  # ~30 fps cap

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/frame", methods=["GET"])
def latest_frame():
    """
    Return the latest annotated frame as a single JPEG image.
    Useful for polling-based approaches.
    """
    if not _inference_state:
        return jsonify({"error": "Inference not running"}), 503
    frame = _inference_state.get_frame_jpeg()
    if frame is None:
        return jsonify({"error": "No frame available"}), 404
    return Response(frame, mimetype="image/jpeg")


@app.route("/hardware/conveyor", methods=["POST"])
def hardware_conveyor():
    if not _hardware:
        return jsonify({"error": "Hardware not connected"}), 503

    data = request.get_json() or {}
    action = data.get("action", "start")
    speed = data.get("speed")

    if action == "start":
        _hardware.start_conveyor(speed)
    elif action == "stop":
        _hardware.stop_conveyor()
    elif action == "pause":
        _hardware.pause_conveyor()
    elif action == "resume":
        _hardware.resume_conveyor()
    elif action == "slow":
        _hardware.slow_conveyor()
    else:
        return jsonify({"error": f"Unknown action: {action}"}), 400

    return jsonify({"success": True, "conveyor": _hardware.conveyor_state.name})


@app.route("/hardware/divert", methods=["POST"])
def hardware_divert():
    if not _hardware:
        return jsonify({"error": "Hardware not connected"}), 503

    data = request.get_json() or {}
    bin_id = data.get("bin_id")
    if bin_id is None or bin_id not in range(4):
        return jsonify({"error": "bin_id must be 0-3"}), 400

    _hardware.divert_to_bin(bin_id)
    return jsonify({"success": True, "diverted_to": bin_id})


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _pick_color(label: str) -> str:
    """Pick a hex color for a class label."""
    l = label.lower()
    if "carrot" in l or "orange" in l:
        return "#f97316"
    if "lettuce" in l or "spinach" in l or "leafy" in l:
        return "#22c55e"
    if "tomato" in l or "pepper" in l:
        return "#ef4444"
    if "onion" in l:
        return "#a3a3a3"
    if "cucumber" in l or "broccoli" in l or "cabbage" in l or "cauliflower" in l:
        return "#16a34a"
    if "potato" in l:
        return "#d4a574"
    if "celery" in l:
        return "#84cc16"
    return "#f59e0b"


def _folder_to_display(folder_name: str) -> str:
    """Convert dataset folder name to display name."""
    mapping = {
        "carrot_peels": "Carrot Peels",
        "potato_skins": "Potato Skins",
        "onion_skins": "Onion Skins",
        "tomato_skins": "Tomato Skins",
        "cucumber_peels": "Cucumber Peels",
        "cabbage_leaves": "Cabbage Leaves",
        "lettuce": "Lettuce",
        "bell_pepper_scraps": "Bell Pepper Scraps",
        "broccoli_stems": "Broccoli Stems",
        "cauliflower_leaves": "Cauliflower Leaves",
        "celery": "Celery",
        "spinach": "Spinach",
    }
    return mapping.get(folder_name.lower(), folder_name)


# ──────────────────────────────────────────────────────────────
# Server startup
# ──────────────────────────────────────────────────────────────

def create_app(inference_state=None, hardware=None):
    """Factory function for creating the Flask app with dependencies."""
    if inference_state:
        set_inference_state(inference_state)
    if hardware:
        set_hardware(hardware)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VeggieFeed API Server")
    parser.add_argument("--port", type=int, default=5000, help="Port (default: 5000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    print(f"[INFO] VeggieFeed API server starting on {args.host}:{args.port}")
    print(f"[WARN] Running standalone — inference and hardware not connected")
    print(f"[INFO] Use main.py to start the full system")

    app.run(host=args.host, port=args.port, debug=args.debug)
