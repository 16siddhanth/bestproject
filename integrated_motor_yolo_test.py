#!/usr/bin/env python3
"""
Integration test runner for:
- BTS7960 motor continuous speed control
- YOLO camera detection (IMX500 or software)
- AI-based image classification endpoint

Behavior:
1) Motor runs continuously at fixed PWM speed (23% default)
2) On IR sensor detection, motor pauses after a 1.5s delay
3) Latest frame is sent to the enhanced classifier endpoint
4) Motor resumes only after a successful classification
"""

from __future__ import annotations

import argparse
import base64
import importlib
import json
import os
import re
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import error as url_error
from urllib import request as url_request


BASE_DIR = Path(__file__).resolve().parent


@dataclass
class ClassificationOutcome:
    label: str
    confidence_pct: float
    source: str
    raw: Optional[Dict[str, Any]] = None


class SimulatedMotorController:
    """Fallback dual-motor controller for dry runs without GPIO hardware."""

    def __init__(self) -> None:
        self._is_running = False
        print("[SIM] Dual motor controller enabled")

    def motor_forward(self, duty_cycle: float) -> None:
        if not self._is_running:
            print(f"[SIM] Both motors ON (duty={duty_cycle:.1f}%)")
            self._is_running = True

    def motor_stop(self) -> None:
        if self._is_running:
            print("[SIM] Both motors OFF")
            self._is_running = False

    def cleanup(self) -> None:
        self.motor_stop()
        print("[SIM] Motor cleanup complete")


class MotorPins:
    """BCM pin mapping for two BTS7960 motor drivers."""

    # BTS7960 #1
    M1_RPWM = 4
    M1_LPWM = 17
    M1_R_EN = 27
    M1_L_EN = 22

    # BTS7960 #2
    M2_RPWM = 18
    M2_LPWM = 23
    M2_R_EN = 24
    M2_L_EN = 25


PWM_FREQ_HZ = 1000
MOTOR_DUTY_CYCLE_DEFAULT = 24.0
IR_SENSOR_PHYSICAL_PIN = 35
IR_SENSOR_BCM_PIN = 19
IR_STOP_DELAY_DEFAULT = 1.5


class _RPiGPIODualMotorBackend:
    """Dual BTS7960 backend using RPi.GPIO."""

    def __init__(self) -> None:
        gpio_module = importlib.import_module("RPi.GPIO")
        self._GPIO = gpio_module

        GPIO = self._GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        self._pwm_pins = [
            MotorPins.M1_RPWM,
            MotorPins.M1_LPWM,
            MotorPins.M2_RPWM,
            MotorPins.M2_LPWM,
        ]
        self._enable_pins = [
            MotorPins.M1_R_EN,
            MotorPins.M1_L_EN,
            MotorPins.M2_R_EN,
            MotorPins.M2_L_EN,
        ]

        for pin in self._pwm_pins:
            GPIO.setup(pin, GPIO.OUT)
        for pin in self._enable_pins:
            GPIO.setup(pin, GPIO.OUT)

        self._m1_rpwm = GPIO.PWM(MotorPins.M1_RPWM, PWM_FREQ_HZ)
        self._m1_lpwm = GPIO.PWM(MotorPins.M1_LPWM, PWM_FREQ_HZ)
        self._m2_rpwm = GPIO.PWM(MotorPins.M2_RPWM, PWM_FREQ_HZ)
        self._m2_lpwm = GPIO.PWM(MotorPins.M2_LPWM, PWM_FREQ_HZ)
        self._pwm_channels = [
            self._m1_rpwm,
            self._m1_lpwm,
            self._m2_rpwm,
            self._m2_lpwm,
        ]
        for pwm in self._pwm_channels:
            pwm.start(0)

        for pin in self._enable_pins:
            GPIO.output(pin, GPIO.HIGH)

    def motor_forward(self, duty_cycle: float) -> None:
        duty = max(0.0, min(100.0, duty_cycle))
        self._m1_lpwm.ChangeDutyCycle(0)
        self._m2_lpwm.ChangeDutyCycle(0)
        self._m1_rpwm.ChangeDutyCycle(duty)
        self._m2_rpwm.ChangeDutyCycle(duty)

    def motor_stop(self) -> None:
        for pwm in self._pwm_channels:
            pwm.ChangeDutyCycle(0)

    def cleanup(self) -> None:
        GPIO = self._GPIO
        self.motor_stop()
        for pwm in self._pwm_channels:
            pwm.stop()
        for pin in self._enable_pins:
            GPIO.output(pin, GPIO.LOW)
        GPIO.cleanup()


class _LGPIODualMotorBackend:
    """Dual BTS7960 backend using lgpio (Pi 5 friendly)."""

    def __init__(self) -> None:
        self._lgpio = importlib.import_module("lgpio")
        self._chip = self._open_gpio_chip()

        self._pwm_pins = [
            MotorPins.M1_RPWM,
            MotorPins.M1_LPWM,
            MotorPins.M2_RPWM,
            MotorPins.M2_LPWM,
        ]
        self._enable_pins = [
            MotorPins.M1_R_EN,
            MotorPins.M1_L_EN,
            MotorPins.M2_R_EN,
            MotorPins.M2_L_EN,
        ]

        for pin in self._pwm_pins + self._enable_pins:
            self._lgpio.gpio_claim_output(self._chip, pin, 0)

        for pin in self._enable_pins:
            self._lgpio.gpio_write(self._chip, pin, 1)

    def _open_gpio_chip(self) -> int:
        # Pi 5 commonly exposes RP1 on gpiochip4, but keep fallback probes.
        candidates = [4, 0, 1, 2, 3, 5]
        last_error: Optional[Exception] = None
        for chip_index in candidates:
            try:
                return self._lgpio.gpiochip_open(chip_index)
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"Unable to open any gpiochip device: {last_error}")

    def _set_pwm(self, pin: int, duty_cycle: float) -> None:
        duty = max(0.0, min(100.0, duty_cycle))
        # lgpio expects duty cycle in percent (0-100).
        self._lgpio.tx_pwm(self._chip, pin, PWM_FREQ_HZ, duty)

    def motor_forward(self, duty_cycle: float) -> None:
        self._set_pwm(MotorPins.M1_LPWM, 0)
        self._set_pwm(MotorPins.M2_LPWM, 0)
        self._set_pwm(MotorPins.M1_RPWM, duty_cycle)
        self._set_pwm(MotorPins.M2_RPWM, duty_cycle)

    def motor_stop(self) -> None:
        for pin in self._pwm_pins:
            self._set_pwm(pin, 0)

    def cleanup(self) -> None:
        try:
            self.motor_stop()
            for pin in self._enable_pins:
                self._lgpio.gpio_write(self._chip, pin, 0)
        finally:
            self._lgpio.gpiochip_close(self._chip)


class DualBTS7960MotorController:
    """Dual BTS7960 controller with automatic GPIO backend selection."""

    def __init__(self) -> None:
        backend_errors = []

        try:
            self._backend = _RPiGPIODualMotorBackend()
            print("[MOTOR] Using RPi.GPIO backend")
            return
        except Exception as exc:
            backend_errors.append(f"RPi.GPIO backend failed: {exc}")

        try:
            self._backend = _LGPIODualMotorBackend()
            print("[MOTOR] Using lgpio backend")
            return
        except Exception as exc:
            backend_errors.append(f"lgpio backend failed: {exc}")

        details = "; ".join(backend_errors)
        raise RuntimeError(
            "Failed to initialize dual BTS7960 controller. "
            "Install GPIO packages for this Pi (python3-rpi.gpio or python3-lgpio). "
            f"Details: {details}"
        )

    def motor_forward(self, duty_cycle: float) -> None:
        self._backend.motor_forward(duty_cycle)

    def motor_stop(self) -> None:
        self._backend.motor_stop()

    def cleanup(self) -> None:
        self._backend.cleanup()


class _RPiGPIOIRSensorBackend:
    """IR sensor backend using RPi.GPIO with BCM numbering."""

    def __init__(self) -> None:
        gpio_module = importlib.import_module("RPi.GPIO")
        self._GPIO = gpio_module

        GPIO = self._GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(IR_SENSOR_BCM_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def read(self) -> int:
        return int(self._GPIO.input(IR_SENSOR_BCM_PIN))

    def cleanup(self) -> None:
        self._GPIO.cleanup(IR_SENSOR_BCM_PIN)


class _LGPIOIRSensorBackend:
    """IR sensor backend using lgpio with BCM numbering."""

    def __init__(self) -> None:
        self._lgpio = importlib.import_module("lgpio")
        self._chip = self._open_gpio_chip()
        self._lgpio.gpio_claim_input(self._chip, IR_SENSOR_BCM_PIN)

    def _open_gpio_chip(self) -> int:
        candidates = [4, 0, 1, 2, 3, 5]
        last_error: Optional[Exception] = None

        for chip_index in candidates:
            try:
                return self._lgpio.gpiochip_open(chip_index)
            except Exception as exc:
                last_error = exc

        raise RuntimeError(f"Unable to open any gpiochip device: {last_error}")

    def read(self) -> int:
        return int(self._lgpio.gpio_read(self._chip, IR_SENSOR_BCM_PIN))

    def cleanup(self) -> None:
        self._lgpio.gpiochip_close(self._chip)


class IRSensorTrigger:
    """IR sensor trigger with automatic GPIO backend selection."""

    def __init__(self, backend: str, active_high: bool) -> None:
        self._active_high = active_high
        self._backend_name, self._backend = self._build_backend(backend)
        polarity = "active-high" if active_high else "active-low"
        print(
            f"[IR] Using {self._backend_name} backend on pin "
            f"{IR_SENSOR_PHYSICAL_PIN} (BCM GPIO{IR_SENSOR_BCM_PIN}), {polarity}"
        )

    def _build_backend(self, preferred: str) -> tuple[str, Any]:
        errors: list[str] = []
        candidates = [preferred] if preferred != "auto" else ["rpi", "lgpio"]

        for name in candidates:
            if name == "rpi":
                try:
                    return "RPi.GPIO", _RPiGPIOIRSensorBackend()
                except Exception as exc:
                    errors.append(f"RPi.GPIO backend failed: {exc}")
            elif name == "lgpio":
                try:
                    return "lgpio", _LGPIOIRSensorBackend()
                except Exception as exc:
                    errors.append(f"lgpio backend failed: {exc}")

        details = "; ".join(errors)
        raise RuntimeError(
            "Failed to initialize IR sensor backend. "
            "Install python3-rpi.gpio or python3-lgpio. "
            f"Details: {details}"
        )

    def is_detected(self) -> bool:
        raw = self._backend.read()
        if self._active_high:
            return raw == 1
        return raw == 0

    def cleanup(self) -> None:
        try:
            self._backend.cleanup()
        except Exception:
            pass


class ServoController:
    """MG996R servo control via PCA9685 with graceful fallback."""

    def __init__(self, channel: int = 0, i2c_address: int = 0x40, pwm_freq: int = 50) -> None:
        self.channel = channel
        self.pwm_freq = pwm_freq
        self._pca = None
        self._ready = False

        try:
            board = importlib.import_module("board")
            busio = importlib.import_module("busio")
            pca9685_module = importlib.import_module("adafruit_pca9685")
        except ImportError as exc:
            print(
                "[WARN] Servo dependencies unavailable; servo moves disabled. "
                "Install: pip install adafruit-blinka adafruit-circuitpython-pca9685"
            )
            print(f"[WARN] Import detail: {exc}")
            return

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            pca_class = getattr(pca9685_module, "PCA9685")
            self._pca = pca_class(i2c, address=i2c_address)
            self._pca.frequency = pwm_freq
            self._ready = True
            print(f"[SERVO] PCA9685 ready on I2C address 0x{i2c_address:02x}, channel {channel}")
        except Exception as exc:
            print(f"[WARN] Failed to initialize PCA9685 servo controller: {exc}")

    def is_ready(self) -> bool:
        return self._ready and self._pca is not None

    @staticmethod
    def _angle_to_duty_cycle(angle: float, freq_hz: int) -> int:
        angle = max(0.0, min(180.0, angle))
        min_pulse_us = 500.0
        max_pulse_us = 2500.0
        pulse_us = min_pulse_us + (max_pulse_us - min_pulse_us) * (angle / 180.0)
        period_us = 1_000_000.0 / freq_hz
        duty = int((pulse_us / period_us) * 65535)
        return max(0, min(65535, duty))

    def set_angle(self, angle: float, reason: str = "") -> bool:
        if not self.is_ready() or self._pca is None:
            return False

        duty = self._angle_to_duty_cycle(angle, self.pwm_freq)
        self._pca.channels[self.channel].duty_cycle = duty
        suffix = f" ({reason})" if reason else ""
        print(f"[SERVO] Angle set to {angle:.1f} deg{suffix}")
        return True

    def cleanup(self) -> None:
        if self._pca is None:
            return
        try:
            self._pca.channels[self.channel].duty_cycle = 0
            self._pca.deinit()
        except Exception:
            pass


def get_servo_angle_for_label(label: str) -> Optional[float]:
    """Map classification labels to MG996R target angles."""
    normalized = re.sub(r"[^a-z]+", " ", label.lower()).strip()

    if "onion" in normalized:
        return 30.0
    if "carrot" in normalized:
        return 90.0
    if "potato" in normalized:
        return 120.0
    return None


class MotorCycler:
    """Keeps the motor running continuously while enabled."""

    def __init__(
        self,
        controller: Any,
        duty_cycle: float,
        stop_event: threading.Event,
    ) -> None:
        self.controller = controller
        self.duty_cycle = max(0.0, min(100.0, duty_cycle))
        self.stop_event = stop_event
        self.enabled_event = threading.Event()
        self.enabled_event.set()
        self._thread = threading.Thread(target=self._run, daemon=True, name="motor-cycler")

    def start(self) -> None:
        self._thread.start()

    def pause(self) -> None:
        self.enabled_event.clear()
        self.controller.motor_stop()
        print("[MOTOR] Paused")

    def resume(self) -> None:
        if not self.enabled_event.is_set():
            self.enabled_event.set()
            print("[MOTOR] Resumed")

    def join(self, timeout: float = 2.0) -> None:
        self._thread.join(timeout=timeout)

    def _run(self) -> None:
        is_running = False
        while not self.stop_event.is_set():
            if not self.enabled_event.is_set():
                if is_running:
                    self.controller.motor_stop()
                    is_running = False
                self.stop_event.wait(0.05)
                continue

            if not is_running:
                self.controller.motor_forward(self.duty_cycle)
                is_running = True

            self.stop_event.wait(0.05)

        if is_running:
            self.controller.motor_stop()


def parse_args() -> argparse.Namespace:
    default_model = BASE_DIR / "raspi_system" / "models" / "coco_pretrained" / "imx500_network_yolo11n_pp.rpk"

    parser = argparse.ArgumentParser(description="Motor + YOLO + enhanced classification integration test")
    parser.add_argument("--model", type=str, default=str(default_model), help="Path to .rpk or .pt model")
    parser.add_argument("--task", type=str, default="detect", choices=["detect", "software"], help="Inference mode")
    parser.add_argument("--labels", type=str, default=None, help="Optional custom labels file path")
    parser.add_argument("--threshold", type=float, default=0.30, help="Detection confidence threshold")
    parser.add_argument("--headless", action="store_true", help="Run camera inference without preview window")
    parser.add_argument("--coco-map", action="store_true", help="Map COCO labels to veggie labels before publishing results")
    parser.add_argument("--force-coco-labels", action="store_true", help="Force COCO labels file loading")

    parser.add_argument(
        "--motor-duty",
        "--speed",
        dest="motor_duty",
        type=float,
        default=MOTOR_DUTY_CYCLE_DEFAULT,
        help="Motor PWM duty cycle percent (0-100)",
    )
    parser.add_argument("--simulate-motor", action="store_true", help="Use simulated motor (no GPIO)")
    parser.add_argument(
        "--ir-stop-delay",
        type=float,
        default=IR_STOP_DELAY_DEFAULT,
        help="Seconds after IR detection before stopping motor",
    )
    parser.add_argument(
        "--ir-backend",
        choices=["auto", "rpi", "lgpio"],
        default="auto",
        help="IR sensor GPIO backend",
    )
    parser.add_argument(
        "--ir-active-high",
        action="store_true",
        help="Treat HIGH as IR detection (default is active-low)",
    )

    parser.add_argument("--env-file", type=str, default=str(BASE_DIR / ".env"), help="Path to .env file")

    # Preferred neutral CLI names.
    parser.add_argument(
        "--disable-ai-classifier",
        dest="disable_gemini",
        action="store_true",
        help="Disable AI image classification",
    )
    parser.add_argument(
        "--allow-secondary-fallback",
        dest="allow_non_gemini_fallback",
        action="store_true",
        help="Allow secondary fallback classification if AI classification fails",
    )
    parser.add_argument(
        "--ai-model",
        dest="gemini_model",
        type=str,
        metavar="AI_MODEL",
        default=os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview"),
        help="AI model name",
    )

    # Backward-compatible aliases hidden from --help.
    parser.add_argument("--disable-gemini", dest="disable_gemini", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--allow-non-gemini-fallback",
        dest="allow_non_gemini_fallback",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--gemini-model", dest="gemini_model", type=str, help=argparse.SUPPRESS)

    parser.add_argument(
        "--classifier-url",
        type=str,
        default=os.environ.get("CLASSIFIER_URL", "http://localhost:3000/api/classify-enhanced"),
        help="Enhanced classifier endpoint",
    )
    parser.add_argument("--classifier-timeout", type=float, default=10.0, help="Classifier request timeout in seconds")
    parser.add_argument("--classification-retry", type=float, default=1.0, help="Retry delay when classification fails")
    parser.add_argument("--frame-timeout", type=float, default=2.0, help="Seconds to wait for a frame before retrying")
    parser.add_argument("--disable-local-fallback", action="store_true", help="Disable local inference fallback if API fails")
    parser.add_argument("--no-pi-api", action="store_true", help="Do not start local Pi Flask API")
    parser.add_argument("--pi-api-port", type=int, default=5000, help="Port for local Pi Flask API")

    parser.add_argument("--poll-interval", type=float, default=0.1, help="Detection polling interval in seconds")
    parser.add_argument("--clear-delay", type=float, default=0.8, help="No-detection delay before arming next trigger")
    parser.add_argument(
        "--post-stop-capture-delay",
        type=float,
        default=0.0,
        help="Optional seconds to wait after motor stop before sending frame to AI classifier",
    )
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=180.0,
        help="Max seconds to wait for camera feed to become live before aborting",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Keep classifying on every detection (default is classify once then keep motor running)",
    )

    return parser.parse_args()


def resolve_env_file_from_argv(default_path: str) -> str:
    """Find --env-file from argv before full argparse processing."""
    for idx, arg in enumerate(sys.argv[1:], start=1):
        if arg == "--env-file" and idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
        if arg.startswith("--env-file="):
            return arg.split("=", 1)[1]
    return default_path


def build_motor_controller(simulate: bool) -> tuple[Any, float]:
    if simulate:
        return SimulatedMotorController(), MOTOR_DUTY_CYCLE_DEFAULT

    controller = DualBTS7960MotorController()
    return controller, MOTOR_DUTY_CYCLE_DEFAULT


def import_inference_symbols() -> Dict[str, Any]:
    raspi_dir = BASE_DIR / "raspi_system"
    if str(raspi_dir) not in sys.path:
        sys.path.insert(0, str(raspi_dir))

    inference_module = importlib.import_module("inference.veggiefeed_inference")
    api_server_module = importlib.import_module("api.api_server")

    return {
        "inference_state": inference_module.inference_state,
        "veggie_classes": inference_module.VEGGIE_CLASSES,
        "load_labels": inference_module.load_labels,
        "run_detection_inference": inference_module.run_detection_inference,
        "run_software_inference": inference_module.run_software_inference,
        "create_api_app": api_server_module.create_app,
    }


def maybe_reexec_for_pi_camera_runtime(task: str) -> None:
    """
    If a user-site NumPy shadows system packages, picamera2/simplejpeg can crash
    with a binary mismatch on Raspberry Pi. Detect that and re-exec with
    PYTHONNOUSERSITE=1 automatically.
    """
    if task != "detect":
        return

    if os.environ.get("PYTHONNOUSERSITE") == "1":
        return

    try:
        importlib.import_module("picamera2")
    except Exception as exc:
        text = f"{type(exc).__name__}: {exc}"
        mismatch = "numpy.dtype size changed" in text or "simplejpeg" in text
        if not mismatch:
            return

        print("[FIX] Detected picamera2/simplejpeg binary mismatch with user-site NumPy.")
        print("[FIX] Restarting automatically with PYTHONNOUSERSITE=1...")

        env = os.environ.copy()
        env["PYTHONNOUSERSITE"] = "1"
        argv = [sys.executable, *sys.argv]

        try:
            os.execvpe(sys.executable, argv, env)
        except Exception as restart_exc:
            print(f"[ERROR] Auto-restart failed: {restart_exc}")
            print("[HINT] Run manually: PYTHONNOUSERSITE=1 python3 integrated_motor_yolo_test.py")


def load_env_file(env_path: str) -> None:
    """Lightweight .env loader to avoid extra dependencies."""
    path = Path(env_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    text = text.strip()
    if not text:
        return None

    # Try direct JSON first.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Fallback: extract first JSON object block from markdown or prose.
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None

    return None


def call_gemini_classifier(
    frame_jpeg: bytes,
    gemini_model: str,
    allowed_labels: list[str],
) -> Optional[ClassificationOutcome]:
    """Classify the detected object image using the configured AI vision model."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[WARN] AI API key is not set; cannot classify")
        return None

    try:
        genai = importlib.import_module("google.genai")
        types = importlib.import_module("google.genai.types")
    except ImportError:
        print("[WARN] Required AI SDK is not installed; cannot classify")
        return None

    labels_text = ", ".join(allowed_labels)
    prompt = (
        "Classify this image as one vegetable waste type. "
        f"Allowed labels: {labels_text}. "
        "Return strict JSON only with keys: "
        '{"label":"<one allowed label>","confidence":<0-100 number>,"reason":"<short reason>"}. '
        "If uncertain, choose the closest allowed label."
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=gemini_model,
            contents=[
                types.Part.from_bytes(data=frame_jpeg, mime_type="image/jpeg"),
                prompt,
            ],
        )
    except Exception as exc:
        print(f"[WARN] AI classification request failed: {exc}")
        return None

    response_text = getattr(response, "text", "") or ""
    parsed = _extract_json_object(response_text)
    if not parsed:
        print("[WARN] AI model response did not contain valid JSON")
        return None

    label = str(parsed.get("label", "")).strip()
    confidence = parsed.get("confidence", 0.0)

    if label not in allowed_labels:
        print(f"[WARN] AI model returned unsupported label: {label}")
        return None

    try:
        confidence_val = float(confidence)
    except (TypeError, ValueError):
        confidence_val = 0.0

    confidence_val = max(0.0, min(100.0, confidence_val))

    return ClassificationOutcome(
        label=label,
        confidence_pct=confidence_val,
        source="ai-vision",
        raw=parsed,
    )


def validate_gemini_setup() -> tuple[bool, str]:
    """Validate AI-classifier prerequisites for strict mode before motor loop starts."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return False, "AI API key is missing in .env"

    try:
        importlib.import_module("google.genai")
        importlib.import_module("google.genai.types")
    except ImportError:
        return False, "Required AI SDK package is not installed"

    return True, ""


def should_use_coco_labels(model_path: str, force_coco_labels: bool) -> bool:
    if force_coco_labels:
        return True
    model_name = os.path.basename(model_path).lower()
    return "coco" in model_name or "yolo11n_pp" in model_name


def start_inference_thread(args: argparse.Namespace, symbols: Dict[str, Any], labels: list[str]) -> threading.Thread:
    inference_state = symbols["inference_state"]
    run_detection_inference = symbols["run_detection_inference"]
    run_software_inference = symbols["run_software_inference"]

    def _runner() -> None:
        try:
            if args.task == "detect":
                run_detection_inference(
                    model_path=args.model,
                    labels=labels,
                    threshold=args.threshold,
                    headless=args.headless,
                    use_coco_mapping=args.coco_map,
                )
            else:
                run_software_inference(
                    model_path=args.model,
                    labels=labels,
                    threshold=args.threshold,
                    headless=args.headless,
                )
        except Exception as exc:
            print(f"[ERROR] Inference crashed: {exc}")
            if "numpy.dtype size changed" in str(exc):
                print("[HINT] Run with system packages: PYTHONNOUSERSITE=1 ...")
            traceback.print_exc()
            inference_state.is_running = False

    thread = threading.Thread(target=_runner, daemon=True, name="inference-thread")
    thread.start()
    return thread


def wait_for_live_feed(inference_state: Any, timeout_seconds: float) -> bool:
    """Wait until inference is running and at least one frame is available."""
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        state = inference_state.get_state()
        if state.get("is_running") and state.get("has_frame"):
            return True
        time.sleep(0.1)
    return False


def has_detection(inference_state: Any) -> bool:
    state = inference_state.get_state()
    return bool(state.get("detections") or state.get("results"))


def wait_for_latest_frame(
    inference_state: Any,
    timeout_seconds: float,
    previous_frame: Optional[bytes] = None,
) -> Optional[bytes]:
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        frame = inference_state.get_frame_jpeg()
        if frame and (previous_frame is None or frame != previous_frame):
            return frame
        time.sleep(0.05)
    return None


def call_enhanced_classifier(frame_jpeg: bytes, classifier_url: str, timeout_seconds: float) -> Optional[ClassificationOutcome]:
    payload = {
        "imageBase64": base64.b64encode(frame_jpeg).decode("ascii"),
        "userId": "integration-test-runner",
    }
    body = json.dumps(payload).encode("utf-8")

    req = url_request.Request(
        classifier_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with url_request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
    except (url_error.URLError, url_error.HTTPError, TimeoutError) as exc:
        print(f"[WARN] Enhanced classifier request failed: {exc}")
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print("[WARN] Enhanced classifier returned non-JSON response")
        return None

    if not parsed.get("success"):
        print(f"[WARN] Enhanced classifier returned success=false: {parsed}")
        return None

    classification = parsed.get("classification") or {}
    top3 = classification.get("top3") or []
    if not top3:
        return None

    top = top3[0]
    label = str(top.get("label", "Unknown"))
    confidence = float(top.get("confidence", 0.0))
    if confidence <= 1.0:
        confidence *= 100.0

    return ClassificationOutcome(
        label=label,
        confidence_pct=confidence,
        source="enhanced-api",
        raw=parsed,
    )


def local_inference_fallback(inference_state: Any) -> Optional[ClassificationOutcome]:
    top = inference_state.get_top_result()
    if not top:
        return None
    return ClassificationOutcome(
        label=top.label,
        confidence_pct=float(top.confidence) * 100.0,
        source="local-yolo-fallback",
        raw={"bin_id": top.bin_id, "timestamp": top.timestamp},
    )


def classify_until_success(
    inference_state: Any,
    veggie_classes: list[str],
    use_gemini: bool,
    gemini_model: str,
    classifier_url: str,
    classifier_timeout: float,
    frame_timeout: float,
    retry_delay: float,
    stop_on_gemini_failure: bool,
    allow_http_fallback: bool,
    allow_local_fallback: bool,
    initial_previous_frame: Optional[bytes],
    stop_event: threading.Event,
) -> Optional[ClassificationOutcome]:
    attempt = 0
    previous_frame = initial_previous_frame
    while not stop_event.is_set():
        attempt += 1
        print(f"[CLASSIFY] Attempt {attempt}")

        frame = wait_for_latest_frame(inference_state, frame_timeout, previous_frame=previous_frame)
        result = None
        if frame is not None:
            previous_frame = frame

        if frame is not None and use_gemini:
            result = call_gemini_classifier(frame, gemini_model, veggie_classes)
            if result:
                return result
            if stop_on_gemini_failure:
                print("[ERROR] AI classification failed. Safety hold engaged.")
                return None

        if frame is not None and classifier_url and allow_http_fallback:
            result = call_enhanced_classifier(frame, classifier_url, classifier_timeout)
            if result:
                return result

        if allow_local_fallback:
            result = local_inference_fallback(inference_state)
            if result:
                return result

        print("[CLASSIFY] No valid classification yet; retrying...")
        stop_event.wait(retry_delay)

    return None


def start_local_pi_api(symbols: Dict[str, Any], inference_state: Any, port: int) -> threading.Thread:
    create_api_app = symbols["create_api_app"]
    app = create_api_app(inference_state=inference_state, hardware=None)

    def _run() -> None:
        try:
            app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
        except OSError as exc:
            print(f"[WARN] Local Pi API server failed to start on port {port}: {exc}")

    thread = threading.Thread(target=_run, daemon=True, name="pi-api-thread")
    thread.start()
    return thread


def main() -> None:
    env_file = resolve_env_file_from_argv(str(BASE_DIR / ".env"))
    load_env_file(env_file)
    args = parse_args()
    maybe_reexec_for_pi_camera_runtime(args.task)

    print("=" * 68)
    print("  Integrated Motor + YOLO + Enhanced Classifier Test")
    print("=" * 68)
    print(f"Model:           {args.model}")
    print(f"Task:            {args.task}")
    print(f"Motor speed:     {args.motor_duty:.1f}% (continuous)")
    print(f"IR stop delay:   {args.ir_stop_delay:.2f}s after IR detection")
    print(f"IR backend:      {args.ir_backend}")
    print(f"Capture delay:   {args.post_stop_capture_delay:.2f}s after motor stop")
    print(f"Env file:        {args.env_file}")
    print(f"AI classifier:   {'off' if args.disable_gemini else 'on'}")
    print(f"AI model:        {args.gemini_model}")
    print(f"Strict mode:     {'on' if (not args.disable_gemini and not args.allow_non_gemini_fallback) else 'off'}")
    print(f"Classifier URL:  {args.classifier_url}")
    print(f"COCO map:        {args.coco_map}")
    print(f"Local Pi API:    {'off' if args.no_pi_api else f'port {args.pi_api_port}'}")
    print("Servo map:       Onion->30 deg, Carrot->90 deg, Potato->120 deg")
    print(f"Run mode:        {'continuous classify' if args.continuous else 'single classify then run motor'}")
    print("=" * 68)

    stop_event = threading.Event()

    symbols = import_inference_symbols()
    inference_state = symbols["inference_state"]
    veggie_classes = list(symbols["veggie_classes"])
    load_labels = symbols["load_labels"]

    use_coco_labels = should_use_coco_labels(args.model, args.force_coco_labels)
    labels = load_labels(args.labels, args.task, use_coco_labels)
    if use_coco_labels:
        print(f"[INFO] Loaded COCO labels ({len(labels)} classes)")
    else:
        print(f"[INFO] Loaded Veggie labels ({len(labels)} classes)")

    use_gemini = not args.disable_gemini
    strict_gemini_mode = use_gemini and not args.allow_non_gemini_fallback
    if strict_gemini_mode:
        ok, message = validate_gemini_setup()
        if not ok:
            print(f"[ERROR] Strict AI mode is enabled but not ready: {message}")
            print("[HINT] Add API key in .env and install package: sudo python3 -m pip install --break-system-packages google-genai")
            return
        print("[INFO] Strict AI mode: motor resumes only after successful AI classification")

    _inference_thread = start_inference_thread(args, symbols, labels)

    if not args.no_pi_api:
        start_local_pi_api(symbols, inference_state, args.pi_api_port)
        print(f"[INFO] Local Pi API server requested on port {args.pi_api_port}")
        print(f"[INFO] Camera MJPEG stream: http://localhost:{args.pi_api_port}/stream")
        print(f"[INFO] Latest frame image:  http://localhost:{args.pi_api_port}/frame")
        print(f"[INFO] Inference status:    http://localhost:{args.pi_api_port}/status")

    print("[INFO] Waiting for camera feed to become live before starting motor...")
    if wait_for_live_feed(inference_state, args.startup_timeout):
        print("[INFO] Camera feed is live")
    else:
        print("[ERROR] Camera feed did not become live within startup timeout")
        print("[HINT] Increase --startup-timeout if firmware upload is slow")
        return

    ir_trigger: Optional[IRSensorTrigger] = None
    try:
        ir_trigger = IRSensorTrigger(args.ir_backend, args.ir_active_high)
    except RuntimeError as exc:
        print(f"[ERROR] IR sensor initialization failed: {exc}")
        return

    try:
        controller, default_duty = build_motor_controller(args.simulate_motor)
    except Exception:
        if ir_trigger is not None:
            ir_trigger.cleanup()
        raise
    duty_cycle = args.motor_duty if args.motor_duty is not None else default_duty
    cycler = MotorCycler(
        controller=controller,
        duty_cycle=duty_cycle,
        stop_event=stop_event,
    )
    cycler.start()
    print(f"[MOTOR] Continuous run started (duty={duty_cycle:.1f}%)")

    servo_controller = ServoController(channel=0)
    if servo_controller.is_ready():
        print("[INFO] Servo actions enabled on PCA9685 channel 0")
    else:
        print("[WARN] Servo actions are disabled because PCA9685 is unavailable")

    object_locked = False
    last_ir_detection_time = 0.0
    scheduled_stop_time: Optional[float] = None
    motor_lockout = False
    classification_completed = False

    if use_gemini:
        if args.allow_non_gemini_fallback:
            print("[WARN] Secondary fallback flag is ignored while strict AI mode is enabled")
        allow_http_fallback = False
        allow_local_fallback = False
    else:
        allow_http_fallback = args.allow_non_gemini_fallback
        allow_local_fallback = (not args.disable_local_fallback) and args.allow_non_gemini_fallback

    stop_on_gemini_failure = use_gemini

    try:
        while not stop_event.is_set():
            if motor_lockout:
                stop_event.wait(args.poll_interval)
                continue

            # In default mode, classify only once and keep the motor running afterward.
            if classification_completed and not args.continuous:
                stop_event.wait(args.poll_interval)
                continue

            if ir_trigger is None:
                print("[SAFE-STOP] IR trigger is unavailable. Motor will remain stopped.")
                cycler.pause()
                motor_lockout = True
                continue

            try:
                ir_detected = ir_trigger.is_detected()
            except Exception as exc:
                cycler.pause()
                motor_lockout = True
                print(f"[SAFE-STOP] IR sensor read failed: {exc}")
                print("[SAFE-STOP] Fix IR wiring/backend and restart script.")
                continue

            now = time.monotonic()

            if ir_detected:
                last_ir_detection_time = now
                if not object_locked:
                    object_locked = True
                    scheduled_stop_time = now + max(0.0, args.ir_stop_delay)
                    print(
                        "[EVENT] Object detected by IR sensor. "
                        f"Motor will pause in {args.ir_stop_delay:.1f}s..."
                    )

            if object_locked and scheduled_stop_time is not None and now >= scheduled_stop_time:
                scheduled_stop_time = None
                print("[EVENT] IR stop delay elapsed. Pausing motor for classification...")

                # Snapshot last frame BEFORE stopping so we can force a fresh post-stop frame.
                frame_before_stop = inference_state.get_frame_jpeg()
                cycler.pause()

                if args.post_stop_capture_delay > 0:
                    print(
                        "[CLASSIFY] Waiting "
                        f"{args.post_stop_capture_delay:.1f}s after motor stop for a clearer frame..."
                    )
                    if stop_event.wait(args.post_stop_capture_delay):
                        break

                outcome = classify_until_success(
                    inference_state=inference_state,
                    veggie_classes=veggie_classes,
                    use_gemini=use_gemini,
                    gemini_model=args.gemini_model,
                    classifier_url=args.classifier_url,
                    classifier_timeout=args.classifier_timeout,
                    frame_timeout=args.frame_timeout,
                    retry_delay=args.classification_retry,
                    stop_on_gemini_failure=stop_on_gemini_failure,
                    allow_http_fallback=allow_http_fallback,
                    allow_local_fallback=allow_local_fallback,
                    initial_previous_frame=frame_before_stop,
                    stop_event=stop_event,
                )

                if outcome:
                    print(
                        "[RESULT] Classified: "
                        f"{outcome.label} ({outcome.confidence_pct:.1f}%) via {outcome.source}"
                    )
                    if outcome.raw and isinstance(outcome.raw, dict) and outcome.raw.get("reason"):
                        print(f"[RESULT] Model reason: {outcome.raw['reason']}")

                    servo_angle = get_servo_angle_for_label(outcome.label)
                    if servo_angle is not None:
                        if not servo_controller.set_angle(servo_angle, reason=outcome.label):
                            print("[WARN] Servo move skipped because controller is unavailable")

                    cycler.resume()
                    if args.continuous:
                        pass
                    else:
                        classification_completed = True
                        object_locked = False
                        print("[DONE] First successful classification completed.")
                        print("[DONE] Motor will keep running; further classification is disabled.")
                else:
                    if stop_on_gemini_failure:
                        motor_lockout = True
                        print("[SAFE-STOP] Motor will remain stopped because AI classification failed.")
                        print("[SAFE-STOP] Fix AI setup and restart script manually to resume motor.")
                    else:
                        print("[WARN] Classification loop exited without a result")

            elif object_locked and scheduled_stop_time is None and not ir_detected and (now - last_ir_detection_time) >= args.clear_delay and not motor_lockout:
                object_locked = False
                print("[READY] IR detection cleared. Waiting for next object...")

            stop_event.wait(args.poll_interval)

    except KeyboardInterrupt:
        print("\n[INFO] Keyboard interrupt received. Shutting down...")
    finally:
        stop_event.set()
        cycler.join(timeout=2.0)
        controller.cleanup()
        servo_controller.cleanup()
        if ir_trigger is not None:
            ir_trigger.cleanup()
        print("[INFO] Cleanup complete")


if __name__ == "__main__":
    main()
