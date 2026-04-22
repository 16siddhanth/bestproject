#!/usr/bin/env python3
"""Continuously monitor an IR sensor on Raspberry Pi.

Wiring used by this script:
- IR sensor DOUT -> physical pin 35 (BCM GPIO19)
- VCC -> 3.3V or 5V (per sensor module spec)
- GND -> GND

By default, most IR obstacle sensors are active-low,
so this script prints "Object detected" when the pin reads LOW.
"""

from __future__ import annotations

import argparse
import importlib
import time


PHYSICAL_PIN = 35
BCM_PIN = 19


class IRSensorBackend:
    """Common interface for GPIO backends."""

    def read(self) -> int:
        raise NotImplementedError

    def cleanup(self) -> None:
        raise NotImplementedError


class RPiGPIOBackend(IRSensorBackend):
    """RPi.GPIO backend using BOARD numbering (physical pin 35)."""

    def __init__(self) -> None:
        gpio_module = importlib.import_module("RPi.GPIO")
        self._GPIO = gpio_module

        GPIO = self._GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(PHYSICAL_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def read(self) -> int:
        return int(self._GPIO.input(PHYSICAL_PIN))

    def cleanup(self) -> None:
        self._GPIO.cleanup()


class LGPIOBackend(IRSensorBackend):
    """lgpio backend using BCM numbering (GPIO19)."""

    def __init__(self) -> None:
        self._lgpio = importlib.import_module("lgpio")
        self._chip = self._open_gpio_chip()
        self._lgpio.gpio_claim_input(self._chip, BCM_PIN)

    def _open_gpio_chip(self) -> int:
        candidates = [4, 0, 1, 2, 3, 5]
        last_error: Exception | None = None

        for chip_index in candidates:
            try:
                return self._lgpio.gpiochip_open(chip_index)
            except Exception as exc:  # pragma: no cover
                last_error = exc

        raise RuntimeError(f"Unable to open any gpiochip device: {last_error}")

    def read(self) -> int:
        return int(self._lgpio.gpio_read(self._chip, BCM_PIN))

    def cleanup(self) -> None:
        self._lgpio.gpiochip_close(self._chip)


def select_backend(preferred: str) -> tuple[str, IRSensorBackend]:
    """Initialize GPIO backend with optional preference."""
    errors: list[str] = []

    candidates = [preferred] if preferred != "auto" else ["rpi", "lgpio"]

    for name in candidates:
        if name == "rpi":
            try:
                return "RPi.GPIO", RPiGPIOBackend()
            except Exception as exc:
                errors.append(f"RPi.GPIO backend failed: {exc}")
        elif name == "lgpio":
            try:
                return "lgpio", LGPIOBackend()
            except Exception as exc:
                errors.append(f"lgpio backend failed: {exc}")

    details = "; ".join(errors) if errors else "No backend candidates were tried."
    raise RuntimeError(
        "Failed to initialize GPIO backend. "
        "Install python3-rpi.gpio or python3-lgpio on Raspberry Pi. "
        f"Details: {details}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Continuously monitor IR sensor DOUT on physical pin 35"
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "rpi", "lgpio"],
        default="auto",
        help="GPIO backend to use (default: auto)",
    )
    parser.add_argument(
        "--active-high",
        action="store_true",
        help="Treat HIGH as object detected (default is active-low)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.05,
        help="Sensor polling interval in seconds (default: 0.05)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    active_low = not args.active_high

    backend_name, backend = select_backend(args.backend)
    print(f"IR monitor started with {backend_name}")
    print(f"Reading DOUT from physical pin {PHYSICAL_PIN} (BCM GPIO{BCM_PIN})")
    print("Press Ctrl+C to stop")

    last_detected = False

    try:
        while True:
            raw_value = backend.read()
            detected = raw_value == 0 if active_low else raw_value == 1

            if detected and not last_detected:
                print("Object detected")

            last_detected = detected
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\nStopped IR monitor")
    finally:
        backend.cleanup()


if __name__ == "__main__":
    main()
