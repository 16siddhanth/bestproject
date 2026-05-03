"""
M5Stack MiniScales Unit — Raspberry Pi 5 over I2C (smbus2).

The MiniScales has an onboard STM32 that handles the HX711;
we only need to read/write I2C registers.

Wiring (PCA9548A HW-617 Multiplexer):
    Raspberry Pi 5              PCA9548A (HW-617)         M5 MiniScales
    ─────────────               ──────────────────         ─────────────
    Pin 3 (SDA) ──────────────▶ SDA
    Pin 5 (SCL) ──────────────▶ SCL
    Pin 1/17 (3.3V) ──────────▶ VCC
    Pin 6 (GND) ──────────────▶ GND
                                SD0 / SC0 ───────────────▶ Scale 1 SDA/SCL
                                SD1 / SC1 ───────────────▶ Scale 2 SDA/SCL
                                SD2 / SC2 ───────────────▶ Scale 3 SDA/SCL
                                SD3 / SC3 ───────────────▶ Scale 4 SDA/SCL

    PCA9548A address : 0x70 (A0-A2 all low)
    MiniScale address: 0x26 (same on every channel)

Enable I2C on Pi 5 if not already:
    sudo raspi-config  →  Interface Options  →  I2C  →  Enable

Install dependency:
    sudo apt install python3-smbus2      # preferred on Pi OS Bookworm
    # or: pip install smbus2             (inside a venv)

Verify the mux is detected:
    i2cdetect -y 1        # should show 0x70
"""

import struct
import time
import smbus2

# ── I2C address & bus ──────────────────────────────────────────────
I2C_BUS = 1
DEVICE_ADDR = 0x26
MUX_ADDR = 0x70

# ── Official register map (from M5Stack UNIT_SCALES.h) ────────────
# https://github.com/m5stack/M5Unit-Miniscale/blob/main/src/UNIT_SCALES.h
REG_RAW_ADC       = 0x00   # 4 bytes  int32   LE
REG_WEIGHT_FLOAT  = 0x10   # 4 bytes  float   LE  (calibrated)
REG_BUTTON        = 0x20   # 1 byte   uint8   (read-only: 1 = pressed)
REG_RGB_LED       = 0x30   # 3 bytes  R G B
REG_GAP           = 0x40   # 4 bytes  float   LE  (scale factor)
REG_OFFSET        = 0x50   # 1 byte   write 1 to tare (same as pressing button)
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
            try:
                self.bus.write_byte(MUX_ADDR, 1 << mux_channel)
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
        """True if the onboard button is physically pressed."""
        return bool(self._read(REG_BUTTON, 1)[0])

    # ── tare / calibration ─────────────────────────────────────────
    def tare(self):
        """Zero the scale — identical to pressing the physical button.
        Writes 0x01 to register 0x50 (UNIT_SCALES_SET_OFFSET_REG).
        """
        self._write(REG_OFFSET, b"\x01")
        time.sleep(0.2)

    def get_gap(self) -> float:
        """Current gap (scale factor) value."""
        return struct.unpack_from("<f", self._read(REG_GAP, 4))[0]

    def set_gap(self, gap: float):
        """Set the gap (scale factor).
        gap = (raw_with_weight - raw_empty) / known_weight_grams
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


# ── Scale / channel names ─────────────────────────────────────────
SCALE_NAMES = {
    0: "Scale 1 (SD0)",
    1: "Scale 2 (SD1)",
    2: "Scale 3 (SD2)",
    3: "Scale 4 (SD3)",
}


# ══════════════════════════════════════════════════════════════════
#  Option 1 — Test a Single Scale
# ══════════════════════════════════════════════════════════════════

def _test_single():
    """Pick one scale, tare it, and stream live weight."""
    while True:
        try:
            choice = input("Which scale? (1, 2, 3, or 4): ").strip()
            if choice in ['1', '2', '3', '4']:
                mux_channel = int(choice) - 1
                break
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")
        except KeyboardInterrupt:
            print("\nExiting.")
            return

    print(f"\nInitializing {SCALE_NAMES[mux_channel]}...")
    scale = MiniScales(mux_channel=mux_channel)
    try:
        try:
            fw = scale.get_firmware_version()
        except OSError:
            print(f"\n[ERROR] {SCALE_NAMES[mux_channel]} not found.")
            print("Check wiring: scale → PCA9548A port → Pi I2C pins.")
            return

        print(f"Connected (FW v{fw})")
        scale.set_led(0, 16, 0)  # Green LED

        # Enable filters
        scale.set_lp_filter(True)
        scale.set_avg_filter(20)
        scale.set_ema_filter(10)
        time.sleep(0.3)

        # Auto-tare on startup
        print("Taring — keep the scale empty...")
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


# ══════════════════════════════════════════════════════════════════
#  Option 2 — Test All Scales Simultaneously
# ══════════════════════════════════════════════════════════════════

def _test_all():
    """Rapidly cycle all 4 channels and print live weights side-by-side."""
    print("\n╔══════════════════════════════════════╗")
    print("║     Testing All MiniScales Live      ║")
    print("╚══════════════════════════════════════╝")
    print("Press Ctrl-C to quit.\n")

    bus = smbus2.SMBus(1)

    # Pre-check which ones are connected
    connected = {}
    for ch in range(4):
        try:
            bus.write_byte(MUX_ADDR, 1 << ch)
            time.sleep(0.05)
            bus.read_i2c_block_data(DEVICE_ADDR, REG_FW_VERSION, 1)
            connected[ch] = True

            # Enable filters on each connected scale
            bus.write_i2c_block_data(DEVICE_ADDR, REG_LP_FILTER, [1])
            bus.write_i2c_block_data(DEVICE_ADDR, REG_AVG_FILTER, [20])
            bus.write_i2c_block_data(DEVICE_ADDR, REG_EMA_FILTER, [10])
            time.sleep(0.1)
            
            # Tare each connected scale
            bus.write_i2c_block_data(DEVICE_ADDR, REG_OFFSET, [1])
            time.sleep(0.1)
        except OSError:
            connected[ch] = False

    time.sleep(1) # Let all scales finish taring

    conn_list = [f"S{ch+1}" for ch, ok in connected.items() if ok]
    miss_list = [f"S{ch+1}" for ch, ok in connected.items() if not ok]
    print(f"  Connected: {', '.join(conn_list) if conn_list else 'none'}")
    if miss_list:
        print(f"  Missing:   {', '.join(miss_list)}")

    if not any(connected.values()):
        print("\n[ERROR] No scales detected on any multiplexer channel!")
        bus.close()
        return

    print()
    try:
        while True:
            parts = []
            for ch in range(4):
                if not connected[ch]:
                    parts.append(f"S{ch+1}:  ---  ")
                    continue
                try:
                    bus.write_byte(MUX_ADDR, 1 << ch)
                    time.sleep(0.02)
                    data = bytes(bus.read_i2c_block_data(DEVICE_ADDR, REG_WEIGHT_FLOAT, 4))
                    weight = struct.unpack_from("<f", data)[0]
                    parts.append(f"S{ch+1}: {weight:>6.1f}g")
                except OSError:
                    parts.append(f"S{ch+1}:  ERR  ")

            print("\r" + "  |  ".join(parts) + "   ", end="", flush=True)
            time.sleep(0.2)

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        bus.close()


# ══════════════════════════════════════════════════════════════════
#  Option 3 — Calibrate Scale Factor (GAP) to 20g
# ══════════════════════════════════════════════════════════════════

def _calibrate():
    """Calibrates the scale's internal multiplier using a 20g weight.
    This permanently fixes wild 18,000g readings caused by corrupt memory.
    """
    print("\n╔══════════════════════════════════════╗")
    print("║     Calibrate Scale Factor (20g)     ║")
    print("╚══════════════════════════════════════╝")
    print("This will fix scales that are showing wild, impossible numbers.\n")

    while True:
        try:
            choice = input("Which scale is broken? (1, 2, 3, or 4): ").strip()
            if choice in ['1', '2', '3', '4']:
                mux_channel = int(choice) - 1
                break
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")
        except KeyboardInterrupt:
            print("\nCancelled.")
            return

    scale = MiniScales(mux_channel=mux_channel)
    try:
        try:
            scale.get_firmware_version()
        except OSError:
            print(f"\n[ERROR] Scale {choice} not detected on the multiplexer.")
            return
            
        # Ensure filters are on for a stable read
        scale.set_lp_filter(True)
        scale.set_avg_filter(20)
        scale.set_ema_filter(10)
        time.sleep(0.5)

        print(f"\n--- Step 1: Empty the scale ---")
        input("Remove all items from the scale and press Enter...")
        print("Taring scale to 0g...")
        scale.tare()
        time.sleep(2)  # Wait for stable zero
        raw_empty = scale.get_raw_adc()

        print(f"\n--- Step 2: Place 20g Weight ---")
        input("Place EXACTLY 20g on the scale and press Enter...")
        print("Reading new weight...")
        time.sleep(2)  # Wait for stable reading
        raw_loaded = scale.get_raw_adc()

        if raw_loaded == raw_empty:
            print("\n[ERROR] The RAW values did not change! (Wiring or Load Cell is broken)")
            return

        # Calculate new GAP
        new_gap = (raw_loaded - raw_empty) / 20.0
        print(f"\nCalculated new Scale Factor: {new_gap:.4f}")
        
        # Save to memory
        scale.set_gap(new_gap)
        time.sleep(0.5)
        
        test_weight = scale.get_weight()
        print(f"Verification reading: {test_weight:.1f} g")
        print("\nCalibration successful! The scale should now read correctly.")
        
    except KeyboardInterrupt:
        print("\nCancelled.")
    finally:
        scale.close()


# ══════════════════════════════════════════════════════════════════
#  Main Menu
# ══════════════════════════════════════════════════════════════════

def main():
    # Software Fix: Disable PCA9685 All-Call address (0x70) to prevent conflict with PCA9548A mux
    try:
        import smbus2
        with smbus2.SMBus(1) as bus:
            mode1 = bus.read_byte_data(0x40, 0x00)
            bus.write_byte_data(0x40, 0x00, (mode1 & ~0x01) | 0x20)
    except Exception:
        pass

    print("M5Stack MiniScales — PCA9548A Multiplexer")
    print("==========================================\n")
    print("  1) Test a single scale")
    print("  2) Test all scales simultaneously")
    print("  3) Calibrate Scale Factor (requires 20g weight)")
    print()

    while True:
        try:
            choice = input("Select mode (1, 2, or 3): ").strip()
            if choice == '1':
                _test_single()
                return
            elif choice == '2':
                _test_all()
                return
            elif choice == '3':
                _calibrate()
                return
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
        except KeyboardInterrupt:
            print("\nExiting.")
            return


if __name__ == "__main__":
    main()
