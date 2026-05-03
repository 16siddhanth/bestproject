"""
MG996R servo control through PCA9685 over I2C (Raspberry Pi 5).

Install dependencies:
    sudo apt install -y python3-pip python3-smbus i2c-tools
    pip install adafruit-blinka adafruit-circuitpython-pca9685

Enable I2C (if not already enabled):
    sudo raspi-config
    Interface Options -> I2C -> Enable

Wiring:
    Pi pin 3  (SDA) -> PCA9685 SDA
    Pi pin 5  (SCL) -> PCA9685 SCL
    Pi pin 1  (3V3) -> PCA9685 VCC (logic)
    Pi GND          -> PCA9685 GND

    MG996R signal   -> PCA9685 channel output (default channel 0)
    MG996R VCC      -> External 5-6V supply (+)
    MG996R GND      -> External supply GND and PCA9685 GND

    Do not power MG996R from Pi 5V pin. Use an external servo supply.

MG996R typical pulse range:
    500 us (0 deg) to 2500 us (180 deg) at 50 Hz
"""

import time

try:
    import board  # type: ignore[import-not-found]
    import busio  # type: ignore[import-not-found]
    from adafruit_pca9685 import PCA9685  # type: ignore[import-not-found]
except ImportError as exc:
    raise SystemExit(
        "Missing dependency. Install with: "
        "pip install adafruit-blinka adafruit-circuitpython-pca9685"
    ) from exc


# --- Configuration ---
I2C_ADDRESS = 0x40
SERVO_CHANNEL = 0
PWM_FREQ = 50

# Tune these if your servo does not reach full travel.
MIN_PULSE_US = 500
MAX_PULSE_US = 2500


def angle_to_pulse_us(angle: float) -> float:
    """Convert angle (0-180) to pulse width in microseconds."""
    angle = max(0.0, min(180.0, angle))
    return MIN_PULSE_US + (MAX_PULSE_US - MIN_PULSE_US) * (angle / 180.0)


def pulse_us_to_duty_cycle(pulse_us: float, freq_hz: int) -> int:
    """Convert pulse width to PCA9685 16-bit duty cycle."""
    period_us = 1_000_000.0 / freq_hz
    duty = int((pulse_us / period_us) * 65535)
    return max(0, min(65535, duty))


def set_servo_angle(pca: PCA9685, channel: int, angle: float):
    """Set servo angle on a PCA9685 channel."""
    pulse_us = angle_to_pulse_us(angle)
    duty = pulse_us_to_duty_cycle(pulse_us, PWM_FREQ)
    pca.channels[channel].duty_cycle = duty


def main():
    pca = None

    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        pca = PCA9685(i2c, address=I2C_ADDRESS)
        pca.frequency = PWM_FREQ

        # Software Fix: Disable PCA9685 All-Call address (0x70) to prevent conflict with PCA9548A mux
        try:
            import smbus2
            with smbus2.SMBus(1) as bus:
                mode1 = bus.read_byte_data(I2C_ADDRESS, 0x00)
                bus.write_byte_data(I2C_ADDRESS, 0x00, mode1 & ~0x01)
        except Exception as e:
            print(f"Warning: Could not disable All-Call on PCA9685: {e}")

        set_servo_angle(pca, SERVO_CHANNEL, 0)
        time.sleep(0.5)

        print("MG996R via PCA9685 ready. Ctrl-C to quit.\n")
        print("Commands: 0-180 = move to angle")
        print("          s     = sweep 0->180->0")
        print("          q     = quit\n")

        while True:
            cmd = input("Angle> ").strip().lower()

            if cmd == "q":
                break

            if cmd == "s":
                for angle in range(0, 181, 2):
                    set_servo_angle(pca, SERVO_CHANNEL, angle)
                    time.sleep(0.02)
                time.sleep(0.3)
                for angle in range(180, -1, -2):
                    set_servo_angle(pca, SERVO_CHANNEL, angle)
                    time.sleep(0.02)
                print("Sweep done.")
                continue

            try:
                angle = float(cmd)
            except ValueError:
                print("Enter a number 0-180, 's' to sweep, or 'q' to quit.")
                continue

            if not 0 <= angle <= 180:
                print("Angle must be 0-180.")
                continue

            set_servo_angle(pca, SERVO_CHANNEL, angle)
            print(f"-> {angle:.1f} deg")

    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as exc:
        print(f"Error: {exc}")
        print("Check I2C wiring, I2C enablement, and PCA9685 address.")
    finally:
        if pca is not None:
            pca.channels[SERVO_CHANNEL].duty_cycle = 0
            pca.deinit()


if __name__ == "__main__":
    main()
