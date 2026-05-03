#!/usr/bin/env python3
"""
VeggieFeed — Hardware Controller
=================================

Controls all hardware components of the vegetable peel sorting system:
  - Conveyor belt motor (DC motor via L298N or relay)
  - Servo motors for bin diverters (4 bins)
  - IR sensors for object detection on conveyor
  - HX711 weight sensors for bin weight monitoring

Hardware Pin Mapping (Raspberry Pi 5 GPIO — BCM numbering):
─────────────────────────────────────────────────────────────
  Component               GPIO Pin    Description
  ─────────────────────────────────────────────────────────
  CONVEYOR_ENABLE         17          Motor driver enable
  CONVEYOR_IN1            27          Motor direction 1
  CONVEYOR_IN2            22          Motor direction 2
  SERVO_BIN_0             12          Servo for bin 0 (PWM)
  SERVO_BIN_1             13          Servo for bin 1 (PWM)
  SERVO_BIN_2             18          Servo for bin 2 (PWM)
  SERVO_BIN_3             19          Servo for bin 3 (PWM)
  IR_ENTRY                5           IR sensor — conveyor entry
  IR_CLASSIFY_ZONE        6           IR sensor — classification zone
  IR_EXIT                 16          IR sensor — conveyor exit
  WEIGHT_SCK              20          HX711 clock (weight sensor)
  WEIGHT_DT               21          HX711 data  (weight sensor)
  STATUS_LED              25          Status indicator LED
  BUZZER                  24          Alert buzzer
  ─────────────────────────────────────────────────────────

Usage:
    # As module (imported by main system):
    from hardware_controller import HardwareController
    hw = HardwareController()
    hw.start_conveyor()
    hw.divert_to_bin(2)

    # Standalone test:
    python hardware_controller.py --test
"""

import argparse
import logging
import time
import threading
from enum import IntEnum
from typing import Callable, Optional, Dict

logger = logging.getLogger("veggiefeed.hardware")


# ──────────────────────────────────────────────────────────────
# Pin Configuration
# ──────────────────────────────────────────────────────────────

class Pins:
    """GPIO pin assignments (BCM numbering)."""
    # Conveyor belt motor driver (L298N)
    CONVEYOR_ENABLE = 17
    CONVEYOR_IN1 = 27
    CONVEYOR_IN2 = 22

    # Servo motors for bin diverters
    SERVO_BIN_0 = 12   # Root vegetables: Carrot Peels, Tomato Skins, Bell Pepper
    SERVO_BIN_1 = 13   # Tubers/Gourds: Potato Skins, Cucumber Peels
    SERVO_BIN_2 = 18   # Aromatics: Onion Skins, Broccoli Stems, Celery
    SERVO_BIN_3 = 19   # Leafy Greens: Cabbage, Lettuce, Cauliflower, Spinach

    # IR sensors
    IR_ENTRY = 5            # Object entering conveyor
    IR_CLASSIFY_ZONE = 6    # Object in classification zone (under camera)
    IR_EXIT = 16            # Object reaching diverter

    # Weight sensor (HX711)
    WEIGHT_SCK = 20
    WEIGHT_DT = 21

    # Indicators
    STATUS_LED = 25
    BUZZER = 24


class ConveyorState(IntEnum):
    STOPPED = 0
    FORWARD = 1
    REVERSE = 2
    PAUSED = 3     # Temporarily paused for classification


class ServoPosition(IntEnum):
    NEUTRAL = 0    # Default position (pass-through)
    DIVERT = 1     # Divert to bin


# ──────────────────────────────────────────────────────────────
# Hardware Controller
# ──────────────────────────────────────────────────────────────

class HardwareController:
    """
    Controls all physical hardware for the VeggieFeed sorting system.

    Supports two modes:
    - Real GPIO mode (on Raspberry Pi with RPi.GPIO or gpiozero)
    - Simulation mode (for development/testing without hardware)
    """

    # Servo angle settings (degrees)
    SERVO_NEUTRAL_ANGLE = 90   # Pass-through position
    SERVO_DIVERT_ANGLE = 30    # Divert to bin position
    SERVO_RESET_DELAY = 1.0    # Seconds to hold divert before resetting

    # Conveyor speed (PWM duty cycle %)
    CONVEYOR_SPEED_NORMAL = 42
    CONVEYOR_SPEED_SLOW = 30

    # Debounce time for IR sensors (seconds)
    IR_DEBOUNCE = 0.1

    def __init__(self, simulate: bool = False):
        self.simulate = simulate
        self.conveyor_state = ConveyorState.STOPPED
        self.conveyor_speed = self.CONVEYOR_SPEED_NORMAL
        self._servo_positions = {0: ServoPosition.NEUTRAL, 1: ServoPosition.NEUTRAL,
                                  2: ServoPosition.NEUTRAL, 3: ServoPosition.NEUTRAL}
        self._ir_callbacks: Dict[str, Optional[Callable]] = {
            "entry": None, "classify": None, "exit": None
        }
        self._running = False
        self._ir_thread: Optional[threading.Thread] = None
        self._weight_value = 0.0
        self._gpio_initialized = False

        # Bin tracking
        self.bin_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        self.bin_weights = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0}

        if not simulate:
            self._init_gpio()
        else:
            logger.info("[SIM] Hardware controller in SIMULATION mode")

    def _init_gpio(self):
        """Initialize GPIO pins."""
        try:
            import RPi.GPIO as GPIO
            self._GPIO = GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Conveyor motor
            GPIO.setup(Pins.CONVEYOR_ENABLE, GPIO.OUT)
            GPIO.setup(Pins.CONVEYOR_IN1, GPIO.OUT)
            GPIO.setup(Pins.CONVEYOR_IN2, GPIO.OUT)
            self._conveyor_pwm = GPIO.PWM(Pins.CONVEYOR_ENABLE, 1000)  # 1kHz
            self._conveyor_pwm.start(0)

            # Servos
            servo_pins = [Pins.SERVO_BIN_0, Pins.SERVO_BIN_1,
                         Pins.SERVO_BIN_2, Pins.SERVO_BIN_3]
            self._servo_pwms = {}
            for i, pin in enumerate(servo_pins):
                GPIO.setup(pin, GPIO.OUT)
                pwm = GPIO.PWM(pin, 50)  # 50Hz for servos
                pwm.start(0)
                self._servo_pwms[i] = pwm

            # IR sensors
            GPIO.setup(Pins.IR_ENTRY, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(Pins.IR_CLASSIFY_ZONE, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(Pins.IR_EXIT, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            # Indicators
            GPIO.setup(Pins.STATUS_LED, GPIO.OUT)
            GPIO.setup(Pins.BUZZER, GPIO.OUT)

            # Weight sensor pins
            GPIO.setup(Pins.WEIGHT_SCK, GPIO.OUT)
            GPIO.setup(Pins.WEIGHT_DT, GPIO.IN)

            self._gpio_initialized = True
            logger.info("GPIO initialized successfully")

        except ImportError:
            logger.warning("RPi.GPIO not available — falling back to simulation mode")
            self.simulate = True
        except Exception as e:
            logger.error(f"GPIO initialization failed: {e}")
            self.simulate = True

    def _angle_to_duty(self, angle: float) -> float:
        """Convert servo angle (0-180) to PWM duty cycle (2-12%)."""
        return 2 + (angle / 180) * 10

    # ──────────────────────────────────────────
    # Conveyor Belt Control
    # ──────────────────────────────────────────

    def start_conveyor(self, speed: Optional[int] = None):
        """Start the conveyor belt in forward direction."""
        if speed is not None:
            self.conveyor_speed = max(0, min(100, speed))

        if self.simulate:
            logger.info(f"[SIM] Conveyor START (speed={self.conveyor_speed}%)")
            self.conveyor_state = ConveyorState.FORWARD
            return

        self._GPIO.output(Pins.CONVEYOR_IN1, self._GPIO.HIGH)
        self._GPIO.output(Pins.CONVEYOR_IN2, self._GPIO.LOW)
        self._conveyor_pwm.ChangeDutyCycle(self.conveyor_speed)
        self.conveyor_state = ConveyorState.FORWARD
        logger.info(f"Conveyor started (speed={self.conveyor_speed}%)")

    def stop_conveyor(self):
        """Stop the conveyor belt."""
        if self.simulate:
            logger.info("[SIM] Conveyor STOP")
            self.conveyor_state = ConveyorState.STOPPED
            return

        self._GPIO.output(Pins.CONVEYOR_IN1, self._GPIO.LOW)
        self._GPIO.output(Pins.CONVEYOR_IN2, self._GPIO.LOW)
        self._conveyor_pwm.ChangeDutyCycle(0)
        self.conveyor_state = ConveyorState.STOPPED
        logger.info("Conveyor stopped")

    def pause_conveyor(self):
        """Temporarily pause conveyor (e.g., during classification)."""
        if self.conveyor_state == ConveyorState.FORWARD:
            if self.simulate:
                logger.info("[SIM] Conveyor PAUSED")
            else:
                self._conveyor_pwm.ChangeDutyCycle(0)
            self.conveyor_state = ConveyorState.PAUSED
            logger.info("Conveyor paused")

    def resume_conveyor(self):
        """Resume conveyor from pause."""
        if self.conveyor_state == ConveyorState.PAUSED:
            if self.simulate:
                logger.info(f"[SIM] Conveyor RESUMED (speed={self.conveyor_speed}%)")
            else:
                self._conveyor_pwm.ChangeDutyCycle(self.conveyor_speed)
            self.conveyor_state = ConveyorState.FORWARD
            logger.info("Conveyor resumed")

    def slow_conveyor(self):
        """Slow the conveyor for the classification zone."""
        if self.simulate:
            logger.info(f"[SIM] Conveyor SLOW ({self.CONVEYOR_SPEED_SLOW}%)")
        else:
            self._conveyor_pwm.ChangeDutyCycle(self.CONVEYOR_SPEED_SLOW)
        logger.info("Conveyor slowed for classification")

    # ──────────────────────────────────────────
    # Servo / Bin Diverter Control
    # ──────────────────────────────────────────

    def divert_to_bin(self, bin_id: int):
        """
        Activate the servo diverter for the specified bin.
        The servo moves to divert position, holds briefly, then returns to neutral.
        """
        if bin_id not in range(4):
            logger.error(f"Invalid bin_id: {bin_id} (must be 0-3)")
            return

        if self.simulate:
            logger.info(f"[SIM] Diverting to BIN {bin_id}")
            self.bin_counts[bin_id] += 1
            return

        # Move servo to divert position
        pwm = self._servo_pwms[bin_id]
        duty = self._angle_to_duty(self.SERVO_DIVERT_ANGLE)
        pwm.ChangeDutyCycle(duty)
        self._servo_positions[bin_id] = ServoPosition.DIVERT
        logger.info(f"Diverting to bin {bin_id}")

        # Reset servo after delay (non-blocking)
        def reset_servo():
            time.sleep(self.SERVO_RESET_DELAY)
            duty = self._angle_to_duty(self.SERVO_NEUTRAL_ANGLE)
            pwm.ChangeDutyCycle(duty)
            time.sleep(0.3)
            pwm.ChangeDutyCycle(0)  # Stop PWM signal to prevent jitter
            self._servo_positions[bin_id] = ServoPosition.NEUTRAL
            logger.debug(f"Servo {bin_id} returned to neutral")

        threading.Thread(target=reset_servo, daemon=True).start()
        self.bin_counts[bin_id] += 1

    def set_servo_angle(self, bin_id: int, angle: float):
        """Manually set a servo to a specific angle (0-180)."""
        if bin_id not in range(4):
            return
        if self.simulate:
            logger.info(f"[SIM] Servo {bin_id} → {angle}°")
            return

        duty = self._angle_to_duty(angle)
        self._servo_pwms[bin_id].ChangeDutyCycle(duty)
        time.sleep(0.3)
        self._servo_pwms[bin_id].ChangeDutyCycle(0)

    def reset_all_servos(self):
        """Return all servos to neutral position."""
        for bin_id in range(4):
            if self.simulate:
                self._servo_positions[bin_id] = ServoPosition.NEUTRAL
            else:
                duty = self._angle_to_duty(self.SERVO_NEUTRAL_ANGLE)
                self._servo_pwms[bin_id].ChangeDutyCycle(duty)
                time.sleep(0.1)
                self._servo_pwms[bin_id].ChangeDutyCycle(0)
        logger.info("All servos reset to neutral")

    # ──────────────────────────────────────────
    # IR Sensor Monitoring
    # ──────────────────────────────────────────

    def read_ir_entry(self) -> bool:
        """Read the entry IR sensor. Returns True if object detected."""
        if self.simulate:
            return False
        return self._GPIO.input(Pins.IR_ENTRY) == self._GPIO.LOW

    def read_ir_classify_zone(self) -> bool:
        """Read the classification zone IR sensor."""
        if self.simulate:
            return False
        return self._GPIO.input(Pins.IR_CLASSIFY_ZONE) == self._GPIO.LOW

    def read_ir_exit(self) -> bool:
        """Read the exit IR sensor."""
        if self.simulate:
            return False
        return self._GPIO.input(Pins.IR_EXIT) == self._GPIO.LOW

    def on_ir_entry(self, callback: Callable):
        """Register callback for when object enters conveyor."""
        self._ir_callbacks["entry"] = callback

    def on_ir_classify(self, callback: Callable):
        """Register callback for when object reaches classification zone."""
        self._ir_callbacks["classify"] = callback

    def on_ir_exit(self, callback: Callable):
        """Register callback for when object reaches diverter zone."""
        self._ir_callbacks["exit"] = callback

    def start_ir_monitoring(self):
        """Start background thread to monitor IR sensors and fire callbacks."""
        if self._running:
            return

        self._running = True

        if self.simulate:
            logger.info("[SIM] IR monitoring started (no actual sensors)")
            return

        def monitor():
            last_states = {"entry": False, "classify": False, "exit": False}
            sensor_map = {
                "entry": Pins.IR_ENTRY,
                "classify": Pins.IR_CLASSIFY_ZONE,
                "exit": Pins.IR_EXIT,
            }

            while self._running:
                for name, pin in sensor_map.items():
                    triggered = self._GPIO.input(pin) == self._GPIO.LOW
                    if triggered and not last_states[name]:
                        # Rising edge — object just detected
                        cb = self._ir_callbacks.get(name)
                        if cb:
                            try:
                                cb()
                            except Exception as e:
                                logger.error(f"IR callback error ({name}): {e}")
                    last_states[name] = triggered
                time.sleep(self.IR_DEBOUNCE)

        self._ir_thread = threading.Thread(target=monitor, daemon=True)
        self._ir_thread.start()
        logger.info("IR sensor monitoring started")

    def stop_ir_monitoring(self):
        """Stop IR sensor monitoring."""
        self._running = False
        if self._ir_thread:
            self._ir_thread.join(timeout=2.0)
        logger.info("IR monitoring stopped")

    # ──────────────────────────────────────────
    # Weight Sensor (HX711)
    # ──────────────────────────────────────────

    def read_weight(self) -> float:
        """Read weight from HX711 sensor (in grams)."""
        if self.simulate:
            return self._weight_value

        try:
            # Simple HX711 bit-bang read
            value = self._hx711_read_raw()
            # Calibration: adjust these based on your load cell
            CALIBRATION_FACTOR = 420.0  # Adjust during calibration
            OFFSET = 8300000            # Tare offset
            weight_g = (value - OFFSET) / CALIBRATION_FACTOR
            return max(0, weight_g)
        except Exception as e:
            logger.error(f"Weight sensor error: {e}")
            return 0.0

    def _hx711_read_raw(self) -> int:
        """Read raw 24-bit value from HX711."""
        GPIO = self._GPIO
        # Wait for DOUT to go LOW (data ready)
        timeout = time.time() + 1.0
        while GPIO.input(Pins.WEIGHT_DT) == GPIO.HIGH:
            if time.time() > timeout:
                raise TimeoutError("HX711 not ready")

        # Read 24 bits
        value = 0
        for _ in range(24):
            GPIO.output(Pins.WEIGHT_SCK, GPIO.HIGH)
            value = (value << 1) | GPIO.input(Pins.WEIGHT_DT)
            GPIO.output(Pins.WEIGHT_SCK, GPIO.LOW)

        # One extra pulse for gain=128, channel A
        GPIO.output(Pins.WEIGHT_SCK, GPIO.HIGH)
        GPIO.output(Pins.WEIGHT_SCK, GPIO.LOW)

        # Convert from 24-bit two's complement
        if value & 0x800000:
            value -= 0x1000000

        return value

    def tare_weight(self):
        """Tare (zero) the weight sensor."""
        if self.simulate:
            self._weight_value = 0.0
            logger.info("[SIM] Weight sensor tared")
            return

        readings = []
        for _ in range(10):
            readings.append(self._hx711_read_raw())
            time.sleep(0.05)
        # Store average as new offset
        logger.info(f"Weight sensor tared (avg raw: {sum(readings)/len(readings):.0f})")

    # ──────────────────────────────────────────
    # Indicators
    # ──────────────────────────────────────────

    def set_led(self, on: bool):
        """Control status LED."""
        if self.simulate:
            return
        self._GPIO.output(Pins.STATUS_LED, self._GPIO.HIGH if on else self._GPIO.LOW)

    def beep(self, duration: float = 0.1, count: int = 1):
        """Sound the buzzer."""
        if self.simulate:
            logger.info(f"[SIM] BEEP x{count}")
            return

        for i in range(count):
            self._GPIO.output(Pins.BUZZER, self._GPIO.HIGH)
            time.sleep(duration)
            self._GPIO.output(Pins.BUZZER, self._GPIO.LOW)
            if i < count - 1:
                time.sleep(duration)

    def blink_led(self, times: int = 3, interval: float = 0.2):
        """Blink the status LED."""
        def _blink():
            for _ in range(times):
                self.set_led(True)
                time.sleep(interval)
                self.set_led(False)
                time.sleep(interval)
        threading.Thread(target=_blink, daemon=True).start()

    # ──────────────────────────────────────────
    # Status / Cleanup
    # ──────────────────────────────────────────

    def get_status(self) -> dict:
        """Get current hardware status."""
        return {
            "conveyor": self.conveyor_state.name,
            "conveyor_speed": self.conveyor_speed,
            "servos": {f"bin_{k}": v.name for k, v in self._servo_positions.items()},
            "ir_sensors": {
                "entry": self.read_ir_entry(),
                "classify_zone": self.read_ir_classify_zone(),
                "exit": self.read_ir_exit(),
            },
            "weight_g": round(self.read_weight(), 1),
            "bin_counts": dict(self.bin_counts),
            "simulate": self.simulate,
        }

    def cleanup(self):
        """Clean up GPIO resources."""
        self.stop_conveyor()
        self.stop_ir_monitoring()
        self.reset_all_servos()

        if not self.simulate and self._gpio_initialized:
            try:
                self._conveyor_pwm.stop()
                for pwm in self._servo_pwms.values():
                    pwm.stop()
                self._GPIO.cleanup()
                logger.info("GPIO cleaned up")
            except Exception as e:
                logger.error(f"GPIO cleanup error: {e}")

    def __del__(self):
        self.cleanup()


# ──────────────────────────────────────────────────────────────
# Standalone test
# ──────────────────────────────────────────────────────────────

def run_test(simulate: bool = True):
    """Run hardware self-test."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("=" * 60)
    print("VeggieFeed Hardware Controller — Self-Test")
    print("=" * 60)
    print(f"Mode: {'SIMULATION' if simulate else 'LIVE GPIO'}")
    print()

    hw = HardwareController(simulate=simulate)

    try:
        # Test conveyor
        print("[TEST] Conveyor belt...")
        hw.start_conveyor(60)
        time.sleep(1)
        hw.slow_conveyor()
        time.sleep(0.5)
        hw.pause_conveyor()
        time.sleep(0.5)
        hw.resume_conveyor()
        time.sleep(0.5)
        hw.stop_conveyor()
        print("  ✓ Conveyor OK")

        # Test servos
        print("[TEST] Servo diverters...")
        for bin_id in range(4):
            hw.divert_to_bin(bin_id)
            time.sleep(0.5)
        hw.reset_all_servos()
        print("  ✓ Servos OK")

        # Test IR sensors
        print("[TEST] IR sensors...")
        status = hw.get_status()
        print(f"  Entry: {status['ir_sensors']['entry']}")
        print(f"  Classify: {status['ir_sensors']['classify_zone']}")
        print(f"  Exit: {status['ir_sensors']['exit']}")
        print("  ✓ IR sensors OK")

        # Test weight sensor
        print("[TEST] Weight sensor...")
        weight = hw.read_weight()
        print(f"  Current weight: {weight:.1f}g")
        print("  ✓ Weight sensor OK")

        # Test indicators
        print("[TEST] Indicators...")
        hw.beep(0.1, 2)
        hw.blink_led(3, 0.1)
        time.sleep(1)
        print("  ✓ Indicators OK")

        # Print full status
        print()
        print("Full hardware status:")
        import json
        print(json.dumps(hw.get_status(), indent=2))

        print()
        print("=" * 60)
        print("All hardware tests PASSED")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        hw.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VeggieFeed Hardware Controller")
    parser.add_argument("--test", action="store_true", help="Run hardware self-test")
    parser.add_argument("--live", action="store_true",
                       help="Use live GPIO (default: simulation)")
    args = parser.parse_args()

    if args.test:
        run_test(simulate=not args.live)
    else:
        print("Usage: python hardware_controller.py --test [--live]")
        print("  Or import as module: from hardware_controller import HardwareController")
