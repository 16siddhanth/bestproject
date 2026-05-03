#!/usr/bin/env python3
"""
VeggieFeed — Unified System Controller
=======================================
Central orchestrator for the automated vegetable-waste-to-animal-feed system.

Hardware:
  - 2x BTS7960 for conveyor motors (GPIO 4,17,27,22 and 18,23,24,25)
  - 1x BTS7960 for vibration motor (GPIO 5,6,13,16)
  - 1x PCA9685 servo (channel 0) for bin diverter
  - 4x M5 MiniScales via TCA9548A I2C multiplexer
  - Raspberry Pi AI Camera (IMX500) with YOLO11n (object detection triggers belt stop)

Run:
    python system_controller.py [--simulate] [--port 5001]
"""

from __future__ import annotations

import argparse
import base64
import importlib
import json
import os
import re
import struct
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent for raspi_system imports
BASE_DIR = Path(__file__).resolve().parent.parent
RASPI_DIR = BASE_DIR / "raspi_system"
if str(RASPI_DIR) not in sys.path:
    sys.path.insert(0, str(RASPI_DIR))

from nutrient_data import (
    ANIMAL_TO_BIN, BIN_SERVO_ANGLES, BIN_TO_ANIMAL,
    PEEL_NUTRITION, NUTRIENT_KEYS,
    BinState, create_initial_bin_states, find_optimal_bin,
    get_estimated_weight, get_peel_nutrients_for_weight,
)

# ── Constants ─────────────────────────────────────────────────

PWM_FREQ_HZ = 1000
CONVEYOR_DUTY_CYCLE = 24.0
VIBRATION_DUTY_CYCLE = 50.0
VIBRATION_ON_SECONDS = 5.0
VIBRATION_CYCLE_SECONDS = 15.0
POST_STOP_CAPTURE_DELAY = 1.5  # seconds to wait after belt stops before capturing frame


# ── Motor Pin Configs ─────────────────────────────────────────

class ConveyorPins:
    M1_RPWM = 4; M1_LPWM = 17; M1_R_EN = 27; M1_L_EN = 22
    M2_RPWM = 18; M2_LPWM = 23; M2_R_EN = 24; M2_L_EN = 25

class VibrationPins:
    RPWM = 5; LPWM = 6; R_EN = 13; L_EN = 16


# ── Classification Event ─────────────────────────────────────

@dataclass
class ClassificationEvent:
    timestamp: float
    peels: List[Dict[str, Any]]  # [{label, confidence, count}]
    estimated_weight_g: float
    assigned_bin: int
    assigned_animal: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "peels": self.peels,
            "estimated_weight_g": round(self.estimated_weight_g, 1),
            "assigned_bin": self.assigned_bin,
            "assigned_animal": self.assigned_animal,
        }


# ── Simulated Motor Controller ───────────────────────────────

class SimulatedMotorController:
    def __init__(self, name="motor"):
        self._name = name; self._running = False
    def motor_forward(self, duty):
        if not self._running:
            self._running = True
    def motor_stop(self):
        if self._running:
            self._running = False
    def cleanup(self):
        self.motor_stop()


# ── BTS7960 Motor Controller (real GPIO) ─────────────────────

class BTS7960Controller:
    def __init__(self, rpwm, lpwm, r_en, l_en, name="motor"):
        self._name = name
        self._lgpio = importlib.import_module("lgpio")
        self._chip = self._open_chip()
        self._rpwm = rpwm; self._lpwm = lpwm
        self._r_en = r_en; self._l_en = l_en
        for pin in [rpwm, lpwm, r_en, l_en]:
            self._lgpio.gpio_claim_output(self._chip, pin, 0)
        for pin in [r_en, l_en]:
            self._lgpio.gpio_write(self._chip, pin, 1)

    def _open_chip(self):
        for i in [4, 0, 1, 2, 3, 5]:
            try: return self._lgpio.gpiochip_open(i)
            except Exception: pass
        raise RuntimeError("Cannot open gpiochip")

    def _pwm(self, pin, duty):
        self._lgpio.tx_pwm(self._chip, pin, PWM_FREQ_HZ, max(0, min(100, duty)))

    def motor_forward(self, duty):
        self._pwm(self._lpwm, 0)
        self._pwm(self._rpwm, duty)

    def motor_stop(self):
        self._pwm(self._rpwm, 0)
        self._pwm(self._lpwm, 0)

    def cleanup(self):
        self.motor_stop()
        for pin in [self._r_en, self._l_en]:
            self._lgpio.gpio_write(self._chip, pin, 0)
        self._lgpio.gpiochip_close(self._chip)


class DualConveyorController:
    """Controls two synced BTS7960 drivers for the conveyor belt.
    Each motor is initialized independently — if one fails, it falls
    back to a simulated controller so the system can still start."""
    def __init__(self, simulate=False):
        self.m1_real = False
        self.m2_real = False
        if simulate:
            self._m1 = SimulatedMotorController("conv1")
            self._m2 = SimulatedMotorController("conv2")
        else:
            try:
                self._m1 = BTS7960Controller(
                    ConveyorPins.M1_RPWM, ConveyorPins.M1_LPWM,
                    ConveyorPins.M1_R_EN, ConveyorPins.M1_L_EN, "conv1")
                self.m1_real = True
                print("[HW] Conveyor motor 1: OK")
            except Exception as e:
                print(f"[HW] Conveyor motor 1: SIMULATED ({e})")
                self._m1 = SimulatedMotorController("conv1")
            try:
                self._m2 = BTS7960Controller(
                    ConveyorPins.M2_RPWM, ConveyorPins.M2_LPWM,
                    ConveyorPins.M2_R_EN, ConveyorPins.M2_L_EN, "conv2")
                self.m2_real = True
                print("[HW] Conveyor motor 2: OK")
            except Exception as e:
                print(f"[HW] Conveyor motor 2: SIMULATED ({e})")
                self._m2 = SimulatedMotorController("conv2")

    @property
    def is_real(self) -> bool:
        return self.m1_real or self.m2_real

    def motor_forward(self, duty):
        self._m1.motor_forward(duty); self._m2.motor_forward(duty)
    def motor_stop(self):
        self._m1.motor_stop(); self._m2.motor_stop()
    def cleanup(self):
        self._m1.cleanup(); self._m2.cleanup()


# ── Servo Controller (PCA9685) ────────────────────────────────

class ServoController:
    def __init__(self, channel=0, simulate=False):
        self.channel = channel
        self._ready = False
        self._pca = None
        if simulate:
            return
        try:
            board = importlib.import_module("board")
            busio = importlib.import_module("busio")
            pca_mod = importlib.import_module("adafruit_pca9685")
            i2c = busio.I2C(board.SCL, board.SDA)
            self._pca = pca_mod.PCA9685(i2c, address=0x40)
            self._pca.frequency = 50
            self._ready = True
        except Exception:
            pass

    def set_angle(self, angle: float):
        if not self._ready or not self._pca:
            return
        angle = max(0, min(180, angle))
        pulse_us = 500 + (2500 - 500) * (angle / 180.0)
        duty = int((pulse_us / 20000.0) * 65535)
        self._pca.channels[self.channel].duty_cycle = max(0, min(65535, duty))

    def cleanup(self):
        if self._pca:
            try:
                self._pca.channels[self.channel].duty_cycle = 0
                self._pca.deinit()
            except Exception:
                pass


# ── M5 MiniScale via TCA9548A (HW-617) ───────────────────────

class MiniScaleArray:
    """Read 4 M5 MiniScales connected through a TCA9548A I2C multiplexer.

    I2C Wiring:
        Raspberry Pi 5          TCA9548A (HW-617)         M5 MiniScales
        ─────────────           ──────────────────         ─────────────
        Pin 3 (SDA) ──────────▶ SDA                       
        Pin 5 (SCL) ──────────▶ SCL                       
                                SD0 / SC0 ───────────────▶ Scale 0 (Bin 0 — Cattle)  SDA/SCL
                                SD1 / SC1 ───────────────▶ Scale 1 (Bin 1 — Goats)   SDA/SCL
                                SD2 / SC2 ───────────────▶ Scale 2 (Bin 2 — Poultry) SDA/SCL
                                SD3 / SC3 ───────────────▶ Scale 3 (Bin 3 — Pigs)    SDA/SCL

    Addresses:
        TCA9548A mux  : 0x70 (default, A0-A2 all low)
        M5 MiniScale  : 0x26 (same on each mux channel)
    """
    TCA_ADDR = 0x70
    SCALE_ADDR = 0x26
    REG_WEIGHT_FLOAT = 0x10
    REG_OFFSET = 0x50

    def __init__(self, simulate=False):
        self._simulate = simulate
        self._bus = None
        self._sim_weights = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0}
        if not simulate:
            try:
                smbus2 = importlib.import_module("smbus2")
                self._bus = smbus2.SMBus(1)
            except Exception:
                self._simulate = True

    def _select_channel(self, ch: int):
        if self._bus:
            self._bus.write_byte(self.TCA_ADDR, 1 << ch)
            time.sleep(0.01)

    def read_weight(self, bin_id: int) -> float:
        if self._simulate:
            return self._sim_weights.get(bin_id, 0.0)
        try:
            self._select_channel(bin_id)
            data = bytes(self._bus.read_i2c_block_data(self.SCALE_ADDR, self.REG_WEIGHT_FLOAT, 4))
            return struct.unpack_from("<f", data)[0]
        except Exception:
            return 0.0

    def tare(self, bin_id: int):
        if self._simulate:
            self._sim_weights[bin_id] = 0.0; return
        try:
            self._select_channel(bin_id)
            self._bus.write_i2c_block_data(self.SCALE_ADDR, self.REG_OFFSET, [1])
            time.sleep(0.2)
        except Exception:
            pass

    def tare_all(self):
        for i in range(4): self.tare(i)

    def close(self):
        if self._bus:
            try: self._bus.close()
            except Exception: pass


# ── AI Classifier (hidden, uses Gemini 3.0 Flash) ────────────

def _extract_json(text: str) -> Optional[dict]:
    text = text.strip()
    try:
        p = json.loads(text)
        if isinstance(p, dict): return p
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            p = json.loads(m.group(0))
            if isinstance(p, dict): return p
        except json.JSONDecodeError:
            pass
    return None


def classify_frame(frame_jpeg: bytes, model_name: str = "gemini-2.0-flash") -> Optional[List[Dict]]:
    """Classify peels in the frame. Returns list of {label, confidence, count}."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        genai = importlib.import_module("google.genai")
        types = importlib.import_module("google.genai.types")
    except ImportError:
        return None

    allowed = list(PEEL_NUTRITION.keys())
    labels_text = ", ".join(allowed)
    prompt = (
        "You are a vegetable peel classifier for an automated sorting system. "
        "Analyze this image and identify ALL vegetable peels/waste visible. "
        f"Allowed labels: {labels_text}. "
        "Return strict JSON only: "
        '{"peels": [{"label": "<allowed label>", "confidence": <0-100>, "count": <number>}]}. '
        "If multiple peels of different types are visible, list each separately. "
        "If multiple peels of the same type are visible, set count accordingly. "
        "If uncertain, choose the closest allowed label."
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(data=frame_jpeg, mime_type="image/jpeg"),
                prompt,
            ],
        )
    except Exception:
        return None

    text = getattr(response, "text", "") or ""
    parsed = _extract_json(text)
    if not parsed:
        return None

    peels = parsed.get("peels", [])
    if not isinstance(peels, list) or not peels:
        # Maybe old format with single label
        label = parsed.get("label")
        if label:
            peels = [{"label": label, "confidence": parsed.get("confidence", 50), "count": 1}]
        else:
            return None

    result = []
    for p in peels:
        label = str(p.get("label", "")).strip()
        if label not in allowed:
            continue
        try:
            conf = float(p.get("confidence", 50))
        except (TypeError, ValueError):
            conf = 50.0
        try:
            count = int(p.get("count", 1))
        except (TypeError, ValueError):
            count = 1
        result.append({"label": label, "confidence": max(0, min(100, conf)), "count": max(1, count)})

    return result if result else None


# ── Main System Controller ────────────────────────────────────

class SystemController:
    def __init__(self, simulate=False, port=5001):
        self.simulate = simulate
        self.port = port
        self.running = False
        self.status = "idle"  # idle, running, stopping
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # State
        self.bin_states = create_initial_bin_states()
        self.classification_log: List[ClassificationEvent] = []
        self.vibration_active = False
        self.latest_frame_jpeg: Optional[bytes] = None
        self.camera_connected = False
        self.fps = 0.0

        # Per-component hardware availability
        self.hw_status: Dict[str, str] = {
            "conveyor": "unknown",     # "active" | "simulated" | "unknown"
            "vibration": "unknown",
            "servo": "unknown",
            "scales": "unknown",
            "camera": "unknown",
        }

        # Hardware (initialized on start)
        self._conveyor: Optional[DualConveyorController] = None
        self._vibration: Any = None
        self._servo: Optional[ServoController] = None
        self._scales: Optional[MiniScaleArray] = None
        self._inference_state = None

        # AI model
        self._ai_model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    def start(self):
        if self.running:
            return
        self.running = True
        self.status = "running"
        self._stop_event.clear()

        # ── Init each hardware component independently ────────
        # Conveyor (dual BTS7960)
        self._conveyor = DualConveyorController(simulate=self.simulate)
        self.hw_status["conveyor"] = "active" if self._conveyor.is_real else "simulated"

        # Vibration motor (BTS7960)
        if self.simulate:
            self._vibration = SimulatedMotorController("vibration")
            self.hw_status["vibration"] = "simulated"
        else:
            try:
                self._vibration = BTS7960Controller(
                    VibrationPins.RPWM, VibrationPins.LPWM,
                    VibrationPins.R_EN, VibrationPins.L_EN, "vibration")
                self.hw_status["vibration"] = "active"
                print("[HW] Vibration motor: OK")
            except Exception as e:
                print(f"[HW] Vibration motor: SIMULATED ({e})")
                self._vibration = SimulatedMotorController("vibration")
                self.hw_status["vibration"] = "simulated"

        # Servo (PCA9685)
        self._servo = ServoController(channel=0, simulate=self.simulate)
        self.hw_status["servo"] = "active" if self._servo._ready else "simulated"
        print(f"[HW] Servo (PCA9685): {'OK' if self._servo._ready else 'SIMULATED'}")

        # Scales (TCA9548A + 4× M5 MiniScale)
        self._scales = MiniScaleArray(simulate=self.simulate)
        self.hw_status["scales"] = "active" if not self._scales._simulate else "simulated"
        print(f"[HW] Scales (TCA9548A): {'OK' if not self._scales._simulate else 'SIMULATED'}")
        self._scales.tare_all()

        # Print hardware summary
        active_count = sum(1 for v in self.hw_status.values() if v == "active")
        total = len(self.hw_status)
        print(f"[SYSTEM] Hardware: {active_count}/{total} components active")

        # Start inference (camera — always attempted)
        self._start_inference()

        # Start threads
        threading.Thread(target=self._conveyor_loop, daemon=True, name="conveyor").start()
        threading.Thread(target=self._vibration_loop, daemon=True, name="vibration").start()
        threading.Thread(target=self._detection_loop, daemon=True, name="detection").start()
        threading.Thread(target=self._scale_reader_loop, daemon=True, name="scales").start()

        print("[SYSTEM] Started")

    def stop(self):
        if not self.running:
            return
        self.status = "stopping"
        self._stop_event.set()
        time.sleep(1)

        if self._conveyor:
            self._conveyor.motor_stop(); self._conveyor.cleanup()
        if self._vibration:
            self._vibration.motor_stop(); self._vibration.cleanup()
        if self._servo:
            self._servo.cleanup()
        if self._scales:
            self._scales.close()

        self.running = False
        self.status = "idle"
        print("[SYSTEM] Stopped")

    def _start_inference(self):
        """Start YOLO11n camera inference in background."""
        try:
            from inference.veggiefeed_inference import (
                inference_state, load_labels, run_detection_inference,
            )
            self._inference_state = inference_state

            model_path = str(RASPI_DIR / "models" / "coco_pretrained" / "imx500_network_yolo11n_pp.rpk")
            labels = load_labels(None, "detect", True)

            def _run():
                try:
                    run_detection_inference(
                        model_path=model_path, labels=labels,
                        threshold=0.30, headless=True, use_coco_mapping=True,
                    )
                except Exception as e:
                    print(f"[WARN] Inference error: {e}")
                    inference_state.is_running = False

            threading.Thread(target=_run, daemon=True, name="inference").start()

            # Wait for camera
            start = time.monotonic()
            while time.monotonic() - start < 120:
                s = inference_state.get_state()
                if s.get("is_running") and s.get("has_frame"):
                    self.camera_connected = True
                    self.hw_status["camera"] = "active"
                    print("[HW] Camera (IMX500): OK")
                    return
                time.sleep(0.2)

            print("[WARN] Camera feed timeout")
            self.hw_status["camera"] = "simulated"
        except ImportError:
            print("[WARN] Inference module not available (not on Pi)")
            self.camera_connected = False
            self.hw_status["camera"] = "simulated"

    def _conveyor_loop(self):
        """Keep conveyor running while system is active."""
        self._conveyor.motor_forward(CONVEYOR_DUTY_CYCLE)
        while not self._stop_event.is_set():
            self._stop_event.wait(0.1)
        self._conveyor.motor_stop()

    def _vibration_loop(self):
        """Run vibration motor 5s every 15s."""
        while not self._stop_event.is_set():
            # Wait for cycle start
            self._stop_event.wait(VIBRATION_CYCLE_SECONDS - VIBRATION_ON_SECONDS)
            if self._stop_event.is_set():
                break
            # Turn on
            self.vibration_active = True
            self._vibration.motor_forward(VIBRATION_DUTY_CYCLE)
            self._stop_event.wait(VIBRATION_ON_SECONDS)
            # Turn off
            self._vibration.motor_stop()
            self.vibration_active = False

    def _detection_loop(self):
        """Watch for YOLO camera detections → stop belt → wait 1.5s → capture frame → classify → sort."""
        if not self._inference_state:
            return

        while not self._stop_event.is_set():
            state = self._inference_state.get_state()
            self.fps = state.get("fps", 0.0)

            frame = self._inference_state.get_frame_jpeg()
            if frame:
                with self._lock:
                    self.latest_frame_jpeg = frame

            # YOLO11n detects an object on camera → immediately stop belt
            detections = state.get("detections", [])
            if detections:
                self.status = "detecting"
                # Stop conveyor immediately on camera detection
                self._conveyor.motor_stop()
                print("[DETECT] Object detected by camera — belt stopped")

                # Wait 1.5 seconds after belt stop for stable frame capture
                self.status = "classifying"
                if self._stop_event.wait(POST_STOP_CAPTURE_DELAY):
                    break

                # Capture frame for AI classification
                capture_frame = self._inference_state.get_frame_jpeg()
                if capture_frame:
                    peels = classify_frame(capture_frame, self._ai_model)
                    if peels:
                        self._process_classification(peels)
                    else:
                        print("[CLASSIFY] No result from AI classifier")

                # Resume conveyor
                self._conveyor.motor_forward(CONVEYOR_DUTY_CYCLE)
                self.status = "running"

                # Wait for object to clear the belt before next detection
                self._stop_event.wait(2.0)
            else:
                self._stop_event.wait(0.15)

    def _process_classification(self, peels: List[Dict]):
        """Process classification result: match to bin, move servo, log event."""
        labels_for_matching = []
        total_estimated_weight = 0.0

        for p in peels:
            label = p["label"]
            count = p.get("count", 1)
            for _ in range(count):
                labels_for_matching.append(label)
            total_estimated_weight += get_estimated_weight(label, count)

        # Find optimal bin
        optimal_bin = find_optimal_bin(labels_for_matching, self.bin_states)
        animal = BIN_TO_ANIMAL.get(optimal_bin, "Cattle")

        # Move servo
        angle = BIN_SERVO_ANGLES.get(optimal_bin, 0.0)
        self._servo.set_angle(angle)
        self.status = "sorting"
        time.sleep(0.5)

        # Update bin state
        for p in peels:
            self.bin_states[optimal_bin].add_peel(
                p["label"], count=p.get("count", 1)
            )

        # Log event
        event = ClassificationEvent(
            timestamp=time.time(),
            peels=peels,
            estimated_weight_g=total_estimated_weight,
            assigned_bin=optimal_bin,
            assigned_animal=animal,
        )
        with self._lock:
            self.classification_log.append(event)
            if len(self.classification_log) > 100:
                self.classification_log = self.classification_log[-100:]

        peel_summary = ", ".join(f"{p['label']}x{p.get('count',1)}" for p in peels)
        print(f"[SORTED] {peel_summary} → {animal} (Bin {optimal_bin})")

    def _scale_reader_loop(self):
        """Periodically read all 4 MiniScales and update bin weights."""
        while not self._stop_event.is_set():
            for bin_id in range(4):
                weight = self._scales.read_weight(bin_id)
                self.bin_states[bin_id].update_actual_weight(weight)
            self._stop_event.wait(2.0)

    def get_status(self) -> dict:
        with self._lock:
            return {
                "status": self.status,
                "running": self.running,
                "camera_connected": self.camera_connected,
                "fps": round(self.fps, 1),
                "vibration_active": self.vibration_active,
                "hw_status": dict(self.hw_status),
                "bins": {
                    bid: state.to_dict()
                    for bid, state in self.bin_states.items()
                },
                "recent_events": [
                    e.to_dict() for e in self.classification_log[-20:]
                ],
            }

    def get_frame_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self.latest_frame_jpeg


# ── Flask API Server ──────────────────────────────────────────

def create_flask_app(controller: SystemController):
    from flask import Flask, Response, jsonify, request
    from flask_cors import CORS

    app = Flask(__name__)
    CORS(app)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "VeggieFeed System Controller"})

    @app.route("/system/start", methods=["POST"])
    def start_system():
        if controller.running:
            return jsonify({"success": False, "error": "Already running"})
        threading.Thread(target=controller.start, daemon=True).start()
        return jsonify({"success": True})

    @app.route("/system/stop", methods=["POST"])
    def stop_system():
        if not controller.running:
            return jsonify({"success": False, "error": "Not running"})
        threading.Thread(target=controller.stop, daemon=True).start()
        return jsonify({"success": True})

    @app.route("/system/status", methods=["GET"])
    def system_status():
        return jsonify(controller.get_status())

    @app.route("/system/stream", methods=["GET"])
    def stream():
        def gen():
            while True:
                frame = controller.get_frame_jpeg()
                if frame:
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                time.sleep(0.033)
        return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route("/system/frame", methods=["GET"])
    def frame():
        f = controller.get_frame_jpeg()
        if not f:
            return jsonify({"error": "No frame"}), 404
        return Response(f, mimetype="image/jpeg")

    return app


# ── Entry Point ───────────────────────────────────────────────

def load_env(path: str):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("\"'")
        if k and k not in os.environ:
            os.environ[k] = v


def main():
    parser = argparse.ArgumentParser(description="VeggieFeed System Controller")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--env-file", type=str, default=str(BASE_DIR / ".env"))
    args = parser.parse_args()

    load_env(args.env_file)

    controller = SystemController(simulate=args.simulate, port=args.port)
    app = create_flask_app(controller)

    print(f"[SYSTEM] API server starting on port {args.port}")
    print(f"[SYSTEM] Mode: {'SIMULATED' if args.simulate else 'LIVE GPIO'}")
    app.run(host="0.0.0.0", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
