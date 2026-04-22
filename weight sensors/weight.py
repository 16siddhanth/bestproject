"""
Load cell + HX711 for Raspberry Pi 5
Uses lgpio (native Pi 5 GPIO library) instead of RPi.GPIO which
does NOT work on Pi 5 (different GPIO chip - RP1).

Install dependency:
    sudo apt install python3-lgpio

Wiring (BCM pin numbers):
    HX711 DOUT  -> GPIO 5   (pin 29)
    HX711 SCK   -> GPIO 6   (pin 31)
    HX711 VCC   -> 3.3V or 5V
    HX711 GND   -> GND

Calibration:
    1. Run the script with nothing on the scale (it tares automatically).
    2. Place a known weight (e.g. 100 g), note the Raw count shown.
    3. Set REFERENCE_UNIT = Raw_count / known_weight_in_grams
       e.g. if Raw shows ~42000 with 100 g → REFERENCE_UNIT = 420
"""

import lgpio
import time
import argparse

# --- Configuration ---
DOUT_PIN = 5          # BCM pin for HX711 data output (physical pin 29)
SCK_PIN  = 6          # BCM pin for HX711 clock (physical pin 31)
REFERENCE_UNIT = 712.930    # Calibrated counts per gram
NUM_SAMPLES = 7       # Median filter size per reading


def _read_raw(h: int) -> int | None:
    """
    Read one 24-bit raw value from the HX711.
    Returns a signed integer, or None on timeout.
    Gain is set to 128 (channel A) via the 25th clock pulse.

    CRITICAL: Read DOUT *after* pulling SCK LOW, not while HIGH.
    This keeps the HIGH pulse as short as possible to avoid
    triggering the HX711's 60 µs power-down mode.
    """
    # Wait for DOUT to go LOW (conversion ready), timeout after 2 s
    deadline = time.monotonic() + 2.0
    while lgpio.gpio_read(h, DOUT_PIN):
        if time.monotonic() > deadline:
            return None
        time.sleep(0.001)

    # Read 24 bits — pulse SCK high then low, read DOUT after falling edge
    count = 0
    for _ in range(24):
        lgpio.gpio_write(h, SCK_PIN, 1)
        lgpio.gpio_write(h, SCK_PIN, 0)
        count = (count << 1) | lgpio.gpio_read(h, DOUT_PIN)

    # 25th pulse → gain 128, channel A for next conversion
    lgpio.gpio_write(h, SCK_PIN, 1)
    lgpio.gpio_write(h, SCK_PIN, 0)

    # Convert from 24-bit two's complement to signed int
    if count & 0x800000:
        count -= 0x1000000

    return count


def read_median(h: int, n: int = NUM_SAMPLES) -> int | None:
    """Return the median of n raw readings to reduce noise."""
    samples = []
    for _ in range(n):
        v = _read_raw(h)
        if v is not None:
            samples.append(v)
    if not samples:
        return None
    samples.sort()
    return samples[len(samples) // 2]


def tare(h: int, n: int = 20) -> float:
    """Average n readings to establish the zero offset."""
    print("Taring — keep the scale empty ...")
    # Discard a few readings to let the HX711 settle
    for _ in range(5):
        _read_raw(h)
    values = [_read_raw(h) for _ in range(n)]
    values = [v for v in values if v is not None]
    if not values:
        raise RuntimeError("HX711 not responding — check wiring.")
    offset = sum(values) / len(values)
    print(f"Tare offset: {offset:.0f} counts")
    return offset


def calibrate(h: int, offset: float, known_weight_g: float, n: int = 25) -> float:
    """Estimate counts-per-gram from a known calibration weight."""
    if known_weight_g <= 0:
        raise ValueError("Known weight must be > 0 grams.")

    print(f"Place {known_weight_g:.1f} g on the scale, then wait...")
    time.sleep(2)
    raw = read_median(h, n=n)
    if raw is None:
        raise RuntimeError("Calibration failed: HX711 read timeout.")

    delta = raw - offset
    if abs(delta) < 100:
        raise RuntimeError(
            "Calibration signal too small. Use a heavier known weight or check wiring."
        )

    reference_unit = abs(delta) / known_weight_g
    print(
        f"Calibration raw={raw:.0f}, offset={offset:.0f}, delta={delta:.0f} -> "
        f"REFERENCE_UNIT={reference_unit:.3f} counts/g"
    )
    return reference_unit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read HX711 load cell on Raspberry Pi 5")
    parser.add_argument(
        "--calibrate",
        type=float,
        metavar="GRAMS",
        help="Known weight in grams to auto-calculate REFERENCE_UNIT",
    )
    parser.add_argument(
        "--reference-unit",
        type=float,
        default=REFERENCE_UNIT,
        help="Counts per gram (overrides REFERENCE_UNIT constant)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    h = lgpio.gpiochip_open(4)   # Pi 5 uses gpiochip4
    lgpio.gpio_claim_output(h, SCK_PIN, 0)
    lgpio.gpio_claim_input(h, DOUT_PIN)

    try:
        time.sleep(1)                    # Let HX711 settle after power-on
        offset = tare(h)

        reference_unit = args.reference_unit
        if args.calibrate is not None:
            reference_unit = calibrate(h, offset, args.calibrate)
            print(
                f"\nSet this in the script for future runs: REFERENCE_UNIT = {reference_unit:.3f}\n"
            )
        elif reference_unit == 1:
            print(
                "Warning: REFERENCE_UNIT is still 1. Run once with --calibrate <known_grams>."
            )

        print("Ready — place weight on scale. Ctrl-C to quit.\n")

        while True:
            raw = read_median(h)
            if raw is None:
                print("\rRead timeout — check wiring.          ", end="", flush=True)
            else:
                weight_g = (raw - offset) / reference_unit
                print(
                    f"\rRaw: {raw:>10d}   Weight: {weight_g:>8.1f} g   ",
                    end="", flush=True,
                )
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
