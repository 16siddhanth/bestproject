"""
M5Stack MiniScales Unit — Raspberry Pi 5 over I2C (smbus2).

The MiniScales has an onboard STM32 that handles the HX711;
we only need to read/write I2C registers.

Wiring (Grove HY2.0-4P → Pi 5 GPIO header):
    Yellow (SDA)  → GPIO 2  (pin 3)
    White  (SCL)  → GPIO 3  (pin 5)
    Red    (VCC)  → 5 V     (pin 2 or 4)
    Black  (GND)  → GND     (pin 6)

Enable I2C on Pi 5 if not already:
    sudo raspi-config  →  Interface Options  →  I2C  →  Enable
    # or: sudo dtparam i2c_arm=on

Install dependency:
    sudo apt install python3-smbus2      # preferred on Pi OS Bookworm
    # or: pip install smbus2             (inside a venv)

Verify the device is detected:
    i2cdetect -y 1        # should show 0x26
"""

import struct
import time
import smbus2

# ── I2C address & bus ──────────────────────────────────────────────
I2C_BUS = 1
DEVICE_ADDR = 0x26

# ── Register map (from M5Stack UNIT_SCALES driver) ────────────────
REG_RAW_ADC       = 0x00   # 4 bytes  int32   LE
REG_WEIGHT_FLOAT  = 0x10   # 4 bytes  float   LE  (calibrated)
REG_BUTTON        = 0x20   # 1 byte   uint8
REG_RGB_LED       = 0x30   # 3 bytes  R G B
REG_GAP           = 0x40   # 4 bytes  float   LE  (scale factor)
REG_OFFSET        = 0x50   # 1 byte   write 1 to tare
REG_WEIGHT_INT    = 0x60   # 4 bytes  int32   LE  (calibrated, int)
REG_WEIGHT_STR    = 0x70   # 16 bytes string
REG_LP_FILTER     = 0x80   # 1 byte   0/1
REG_AVG_FILTER    = 0x81   # 1 byte
REG_EMA_FILTER    = 0x82   # 1 byte
REG_FW_VERSION    = 0xFE   # 1 byte
REG_I2C_ADDR      = 0xFF   # 1 byte


class MiniScales:
    """Driver for M5Stack MiniScales Unit over I2C."""

    def __init__(self, bus: int = I2C_BUS, addr: int = DEVICE_ADDR, mux_channel: int = None):
        self.addr = addr
        self.bus = smbus2.SMBus(bus)
        
        # If a mux channel is specified, configure the PCA9548A to select it
        if mux_channel is not None:
            # PCA9548A default address is 0x70
            try:
                self.bus.write_byte(0x70, 1 << mux_channel)
                time.sleep(0.05)  # Wait for multiplexer and scale to settle
            except Exception as e:
                print(f"Warning: Failed to set multiplexer channel: {e}")

    def close(self):
        self.bus.close()

    # ── low-level helpers ──────────────────────────────────────────
    def _read(self, reg: int, length: int) -> bytes:
        return bytes(self.bus.read_i2c_block_data(self.addr, reg, length))

    def _write(self, reg: int, data: bytes):
        self.bus.write_i2c_block_data(self.addr, reg, list(data))

    # ── reading ────────────────────────────────────────────────────
    def get_raw_adc(self) -> int:
        """Raw 24-bit HX711 ADC count (signed int32)."""
        return struct.unpack_from("<i", self._read(REG_RAW_ADC, 4))[0]

    def get_weight(self) -> float:
        """Calibrated weight as float (grams)."""
        return struct.unpack_from("<f", self._read(REG_WEIGHT_FLOAT, 4))[0]

    def get_weight_int(self) -> int:
        """Calibrated weight as int32 (grams)."""
        return struct.unpack_from("<i", self._read(REG_WEIGHT_INT, 4))[0]

    def get_weight_string(self) -> str:
        """Calibrated weight as a null-terminated string."""
        raw = self._read(REG_WEIGHT_STR, 16)
        return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")

    def get_button(self) -> bool:
        """True if the onboard button is pressed."""
        return bool(self._read(REG_BUTTON, 1)[0])

    # ── tare / calibration ─────────────────────────────────────────
    def tare(self):
        """Zero the scale (set current load as offset)."""
        self._write(REG_OFFSET, b"\x01")
        time.sleep(0.2)

    def get_gap(self) -> float:
        """Current gap (scale factor) value."""
        return struct.unpack_from("<f", self._read(REG_GAP, 4))[0]

    def set_gap(self, gap: float):
        """Set the gap (scale factor).
        gap = known_weight_grams / (raw_with_weight − raw_empty)
        """
        self._write(REG_GAP, struct.pack("<f", gap))
        time.sleep(0.1)

    # ── LED ────────────────────────────────────────────────────────
    def set_led(self, r: int, g: int, b: int):
        self._write(REG_RGB_LED, bytes([r & 0xFF, g & 0xFF, b & 0xFF]))

    def get_led(self) -> tuple[int, int, int]:
        d = self._read(REG_RGB_LED, 3)
        return (d[0], d[1], d[2])

    # ── filters ────────────────────────────────────────────────────
    def set_lp_filter(self, enable: bool):
        self._write(REG_LP_FILTER, bytes([int(enable)]))

    def set_avg_filter(self, samples: int):
        self._write(REG_AVG_FILTER, bytes([samples & 0xFF]))

    def set_ema_filter(self, alpha: int):
        self._write(REG_EMA_FILTER, bytes([alpha & 0xFF]))

    # ── info ───────────────────────────────────────────────────────
    def get_firmware_version(self) -> int:
        return self._read(REG_FW_VERSION, 1)[0]


# ── Main ──────────────────────────────────────────────────────────

SCALE_NAMES = {0: "Scale 1 (SD0)", 1: "Scale 2 (SD1)", 2: "Scale 3 (SD2)", 3: "Scale 4 (SD3)"}


def _test_scale():
    """Test a single scale: pick one, tare it, and stream live weight."""
    while True:
        try:
            choice = input("Which scale do you want to test? (1, 2, 3, or 4): ").strip()
            if choice in ['1', '2', '3', '4']:
                mux_channel = int(choice) - 1
                break
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")
        except KeyboardInterrupt:
            print("\nExiting.")
            return

    print(f"\nInitializing Scale {choice} (Mux Channel SD{mux_channel})...")
    scale = MiniScales(mux_channel=mux_channel)
    try:
        try:
            fw = scale.get_firmware_version()
        except OSError:
            print(f"\n[ERROR] Scale {choice} not found on multiplexer channel SD{mux_channel}.")
            print("Please check your wiring: ensure the scale is plugged into the correct port")
            print("on the PCA9548A multiplexer and that the Pi's I2C pins are connected.")
            return

        print(f"Scale {choice} connected  (FW v{fw})")

        # Green LED to confirm connection
        scale.set_led(0, 16, 0)

        # Enable onboard filters for stable readings
        scale.set_lp_filter(True)
        scale.set_avg_filter(20)
        scale.set_ema_filter(10)
        time.sleep(0.3)

        # Tare on startup — let readings settle first
        print("Taring — keep the scale empty ...")
        time.sleep(1)
        scale.tare()
        time.sleep(1)
        print("Ready — place weight on scale.  Ctrl-C to quit.\n")

        while True:
            weight = scale.get_weight()
            raw = scale.get_raw_adc()
            btn = scale.get_button()

            print(
                f"\rWeight: {weight:>8.1f} g   "
                f"Raw: {raw:>10d}   "
                f"Btn: {'PRESSED' if btn else '-'}   ",
                end="", flush=True,
            )
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        try:
            scale.set_led(0, 0, 0)
        except OSError:
            pass
        scale.close()


def _calibrate_all():
    """Scan all 4 mux channels, tare every connected scale to 0 g."""
    print("\n╔══════════════════════════════════════╗")
    print("║     Calibrating All MiniScales       ║")
    print("╚══════════════════════════════════════╝")
    print("Make sure ALL scales are EMPTY before proceeding.\n")

    try:
        input("Press Enter when ready (or Ctrl-C to cancel)... ")
    except KeyboardInterrupt:
        print("\nCancelled.")
        return

    bus = smbus2.SMBus(1)
    found = 0

    for ch in range(4):
        name = SCALE_NAMES[ch]
        # Select multiplexer channel
        try:
            bus.write_byte(0x70, 1 << ch)
            time.sleep(0.05)
        except OSError:
            print(f"  [✗] {name} — multiplexer channel failed")
            continue

        # Check if a scale is present
        try:
            bus.read_i2c_block_data(DEVICE_ADDR, REG_FW_VERSION, 1)
        except OSError:
            print(f"  [–] {name} — not connected")
            continue

        # Tare: write 1 to offset register
        try:
            bus.write_i2c_block_data(DEVICE_ADDR, REG_OFFSET, [1])
            time.sleep(0.3)
            # Verify it reads ~0
            data = bytes(bus.read_i2c_block_data(DEVICE_ADDR, REG_WEIGHT_FLOAT, 4))
            weight = struct.unpack_from("<f", data)[0]
            print(f"  [✓] {name} — tared  (reads {weight:+.1f} g)")
            found += 1
        except OSError as e:
            print(f"  [✗] {name} — tare failed ({e})")

    bus.close()
    print(f"\nCalibration complete: {found}/4 scales zeroed.\n")


def main():
    print("M5Stack MiniScales — PCA9548A Multiplexer")
    print("==========================================\n")
    print("  1) Test a single scale")
    print("  2) Calibrate all scales (tare to 0 g)")
    print()

    while True:
        try:
            choice = input("Select mode (1 or 2): ").strip()
            if choice == '1':
                _test_scale()
                return
            elif choice == '2':
                _calibrate_all()
                return
            else:
                print("Invalid choice. Please enter 1 or 2.")
        except KeyboardInterrupt:
            print("\nExiting.")
            return


if __name__ == "__main__":
    main()

