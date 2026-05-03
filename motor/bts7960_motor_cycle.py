#!/usr/bin/env python3
"""
BTS7960 DC Motor Cycle Controller (Raspberry Pi, BCM GPIO numbering)

Behavior:
- Runs continuously at the selected speed until stopped.

Wiring (BTS7960 <-> Raspberry Pi):
- BTS7960 #1 RPWM -> GPIO 4
- BTS7960 #1 LPWM -> GPIO 17
- BTS7960 #1 R_EN -> GPIO 27
- BTS7960 #1 L_EN -> GPIO 22
- BTS7960 #2 RPWM -> GPIO 18
- BTS7960 #2 LPWM -> GPIO 23
- BTS7960 #2 R_EN -> GPIO 24
- BTS7960 #2 L_EN -> GPIO 25
- GND (both drivers) -> Pi GND (common ground)

Power wiring:
- B+ / B-  -> Motor power supply (per motor voltage/current needs)
- M+ / M-  -> DC motor terminals
- VCC      -> 5V logic supply for BTS7960 board (module dependent)

Notes:
- Always share ground between Pi and motor driver.
- Do not power the motor directly from the Pi.
"""

import argparse
import importlib
import time


class Pins:
    """BCM GPIO mapping for two BTS7960 motor drivers."""

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
DEFAULT_MOTOR_DUTY_CYCLE = 70.0  # 0-100


class _RPiGPIODualMotorBackend:
    """Dual BTS7960 backend using RPi.GPIO."""

    def __init__(self) -> None:
        gpio_module = importlib.import_module("RPi.GPIO")
        self._GPIO = gpio_module

        GPIO = self._GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        self._pwm_pins = [
            Pins.M1_RPWM,
            Pins.M1_LPWM,
            Pins.M2_RPWM,
            Pins.M2_LPWM,
        ]
        self._enable_pins = [
            Pins.M1_R_EN,
            Pins.M1_L_EN,
            Pins.M2_R_EN,
            Pins.M2_L_EN,
        ]

        for pin in self._pwm_pins:
            GPIO.setup(pin, GPIO.OUT)
        for pin in self._enable_pins:
            GPIO.setup(pin, GPIO.OUT)

        self._m1_rpwm = GPIO.PWM(Pins.M1_RPWM, PWM_FREQ_HZ)
        self._m1_lpwm = GPIO.PWM(Pins.M1_LPWM, PWM_FREQ_HZ)
        self._m2_rpwm = GPIO.PWM(Pins.M2_RPWM, PWM_FREQ_HZ)
        self._m2_lpwm = GPIO.PWM(Pins.M2_LPWM, PWM_FREQ_HZ)
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

    def motor_forward(self, m1_duty: float = 50.0, m2_duty: float = 52.0) -> None:
        m1 = max(0.0, min(100.0, m1_duty))
        m2 = max(0.0, min(100.0, m2_duty))
        self._m1_lpwm.ChangeDutyCycle(0)
        self._m2_lpwm.ChangeDutyCycle(0)
        self._m1_rpwm.ChangeDutyCycle(m1)
        self._m2_rpwm.ChangeDutyCycle(m2)

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
            Pins.M1_RPWM,
            Pins.M1_LPWM,
            Pins.M2_RPWM,
            Pins.M2_LPWM,
        ]
        self._enable_pins = [
            Pins.M1_R_EN,
            Pins.M1_L_EN,
            Pins.M2_R_EN,
            Pins.M2_L_EN,
        ]

        for pin in self._pwm_pins + self._enable_pins:
            self._lgpio.gpio_claim_output(self._chip, pin, 0)

        for pin in self._enable_pins:
            self._lgpio.gpio_write(self._chip, pin, 1)

    def _open_gpio_chip(self) -> int:
        # Pi 5 commonly uses gpiochip4 (RP1), but fallback probes are kept.
        candidates = [4, 0, 1, 2, 3, 5]
        last_error = None
        for chip_index in candidates:
            try:
                return self._lgpio.gpiochip_open(chip_index)
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"Unable to open any gpiochip device: {last_error}")

    def _set_pwm(self, pin: int, duty_cycle: float) -> None:
        duty = max(0.0, min(100.0, duty_cycle))
        self._lgpio.tx_pwm(self._chip, pin, PWM_FREQ_HZ, duty)

    def motor_forward(self, m1_duty: float = 50.0, m2_duty: float = 52.0) -> None:
        self._set_pwm(Pins.M1_LPWM, 0)
        self._set_pwm(Pins.M2_LPWM, 0)
        self._set_pwm(Pins.M1_RPWM, m1_duty)
        self._set_pwm(Pins.M2_RPWM, m2_duty)

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


class BTS7960MotorController:
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
            "On Raspberry Pi 5, install lgpio: sudo apt install -y python3-lgpio. "
            "On older Pi models, install RPi.GPIO: sudo apt install -y python3-rpi.gpio. "
            f"Details: {details}"
        )

    def motor_forward(self, m1_duty: float = 50.0, m2_duty: float = 52.0) -> None:
        self._backend.motor_forward(m1_duty, m2_duty)

    def motor_stop(self) -> None:
        self._backend.motor_stop()

    def cleanup(self) -> None:
        self._backend.cleanup()


def main() -> None:
    args = parse_args()

    m1_duty = args.speed_belt
    m2_duty = args.speed_vibration

    try:
        controller = BTS7960MotorController()
    except RuntimeError as exc:
        raise SystemExit(f"[ERROR] {exc}") from exc
    print(
        "Starting BTS7960 continuous run:\n"
        f"  - Belt (M1) at {m1_duty:.1f}% speed.\n"
        f"  - Vibration (M2) at {m2_duty:.1f}% speed.\n"
        "Press Ctrl+C to stop."
    )

    try:
        controller.motor_forward(m1_duty, m2_duty)
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nStopping motor controller...")
    finally:
        controller.cleanup()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run two BTS7960-controlled motors in sync at a configurable speed"
        )
    )
    parser.add_argument(
        "--speed-belt",
        type=float,
        default=50.0,
        help="Belt motor (M1) duty cycle percent (0-100)",
    )
    parser.add_argument(
        "--speed-vibration",
        type=float,
        default=52.0,
        help="Vibration motor (M2) duty cycle percent (0-100)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
