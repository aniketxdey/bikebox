"""
imu.py -- MPU-6050 I2C driver for BikeBox on Raspberry Pi Zero 2 W.

Handles sensor initialization, raw and calibrated data reads for the
accelerometer (±16g) and gyroscope (±2000°/s). Auto-detects the
MPU-6050 at 0x69 (AD0 HIGH, needed when PiSugar 3 is on the bus) or
0x68 (default, when PiSugar is not attached).

Usage:
    from imu import IMU
    sensor = IMU()
    sensor.calibrate()
    ax, ay, az = sensor.read_accel_g()

Reference: MPU-6050 Register Map (Rev 4.2)
    https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Register-Map1.pdf
"""

import math
import struct
import time
from typing import Dict, Tuple

import smbus2

# ---------------------------------------------------------------------------
# I2C addresses -- 0x69 when AD0 is HIGH (avoids PiSugar conflict), 0x68 default
# ---------------------------------------------------------------------------
MPU_ADDR_AD0_HIGH = 0x69
MPU_ADDR_DEFAULT  = 0x68

# ---------------------------------------------------------------------------
# Register addresses
# ---------------------------------------------------------------------------
WHO_AM_I     = 0x75  # Chip ID register (always returns 0x68)
PWR_MGMT_1   = 0x6B  # Power management — write 0x00 to wake from sleep
SMPLRT_DIV   = 0x19  # Sample rate divider — 1kHz / (1 + value)
CONFIG       = 0x1A  # DLPF configuration
GYRO_CONFIG  = 0x1B  # Gyroscope full-scale range
ACCEL_CONFIG = 0x1C  # Accelerometer full-scale range
INT_ENABLE   = 0x38  # Interrupt enable (unused in MVP)
ACCEL_XOUT_H = 0x3B  # First of 6 accel data bytes (XH, XL, YH, YL, ZH, ZL)
GYRO_XOUT_H  = 0x43  # First of 6 gyro data bytes

# ---------------------------------------------------------------------------
# Scale factors for chosen full-scale ranges
# ---------------------------------------------------------------------------
ACCEL_SCALE = 2048.0  # LSB/g at ±16g
GYRO_SCALE  = 16.4    # LSB/(°/s) at ±2000°/s

# ---------------------------------------------------------------------------
# Configuration values
# ---------------------------------------------------------------------------
WHO_AM_I_EXPECTED = 0x68
SMPLRT_DIV_VALUE  = 0x04  # 200 Hz sample rate
DLPF_CFG_VALUE    = 0x03  # ~44 Hz bandwidth
ACCEL_FS_16G      = 0x18  # ±16g
GYRO_FS_2000      = 0x18  # ±2000°/s

# Calibration defaults
CALIBRATION_SAMPLES = 200
CALIBRATION_DELAY   = 0.005  # seconds between samples (~1s total)


class IMU:
    """Driver for the MPU-6050 IMU over I2C.

    Attributes:
        address: I2C address of the MPU-6050 (auto-detected or explicit).
        accel_offset: Calibration offsets for the accelerometer axes.
    """

    def __init__(self, bus_num: int = 1, address: int | None = None) -> None:
        self.bus = smbus2.SMBus(bus_num)
        if address is not None:
            self.address = address
        else:
            self.address = self._auto_detect()
        self.accel_offset: Dict[str, float] = {"x": 0.0, "y": 0.0, "z": 0.0}
        self._init_sensor()

    def _auto_detect(self) -> int:
        """Probe for the MPU-6050 at 0x69 first, then 0x68.

        Returns the first address that responds to WHO_AM_I.
        Raises RuntimeError if neither address has a sensor.
        """
        for addr in (MPU_ADDR_AD0_HIGH, MPU_ADDR_DEFAULT):
            try:
                chip_id = self.bus.read_byte_data(addr, WHO_AM_I)
                print(f"MPU-6050 found at 0x{addr:02X} (WHO_AM_I=0x{chip_id:02X})")
                return addr
            except OSError:
                continue
        raise RuntimeError(
            "MPU-6050 not found at 0x69 or 0x68. "
            "Check wiring: VCC->Pin2, GND->Pin6, SDA->Pin3, SCL->Pin5. "
            "Run 'sudo i2cdetect -y 1' to verify."
        )

    def _init_sensor(self) -> None:
        """Wake the MPU-6050 and configure for crash detection."""
        chip_id = self.bus.read_byte_data(self.address, WHO_AM_I)
        print(f"WHO_AM_I = 0x{chip_id:02X} (MPU-6050 expects 0x68; clones may differ)")

        self.bus.write_byte_data(self.address, PWR_MGMT_1, 0x00)
        time.sleep(0.1)

        self.bus.write_byte_data(self.address, SMPLRT_DIV, SMPLRT_DIV_VALUE)
        self.bus.write_byte_data(self.address, CONFIG, DLPF_CFG_VALUE)
        self.bus.write_byte_data(self.address, ACCEL_CONFIG, ACCEL_FS_16G)
        self.bus.write_byte_data(self.address, GYRO_CONFIG, GYRO_FS_2000)

        print(f"MPU-6050 initialized at 0x{self.address:02X}")

    # ------------------------------------------------------------------
    # Raw reads — burst-read 6 bytes and unpack as 3 big-endian int16s
    # ------------------------------------------------------------------

    def _read_six_bytes(self, start_reg: int) -> Tuple[int, int, int]:
        """Burst-read 6 bytes starting at *start_reg* and return 3 signed int16s."""
        data = self.bus.read_i2c_block_data(self.address, start_reg, 6)
        x, y, z = struct.unpack(">hhh", bytes(data))
        return x, y, z

    def read_accel_raw(self) -> Tuple[int, int, int]:
        """Read raw 16-bit accelerometer values (X, Y, Z)."""
        return self._read_six_bytes(ACCEL_XOUT_H)

    def read_gyro_raw(self) -> Tuple[int, int, int]:
        """Read raw 16-bit gyroscope values (X, Y, Z)."""
        return self._read_six_bytes(GYRO_XOUT_H)

    # ------------------------------------------------------------------
    # Scaled / calibrated reads
    # ------------------------------------------------------------------

    def read_accel_g(self) -> Tuple[float, float, float]:
        """Read accelerometer in g-force with calibration offsets applied."""
        ax_raw, ay_raw, az_raw = self.read_accel_raw()
        ax = (ax_raw / ACCEL_SCALE) - self.accel_offset["x"]
        ay = (ay_raw / ACCEL_SCALE) - self.accel_offset["y"]
        az = (az_raw / ACCEL_SCALE) - self.accel_offset["z"]
        return ax, ay, az

    def read_gyro_dps(self) -> Tuple[float, float, float]:
        """Read gyroscope in degrees-per-second."""
        gx_raw, gy_raw, gz_raw = self.read_gyro_raw()
        return gx_raw / GYRO_SCALE, gy_raw / GYRO_SCALE, gz_raw / GYRO_SCALE

    def accel_magnitude(self) -> float:
        """Total acceleration magnitude in g (calibrated)."""
        ax, ay, az = self.read_accel_g()
        return math.sqrt(ax * ax + ay * ay + az * az)

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def calibrate(
        self,
        samples: int = CALIBRATION_SAMPLES,
        delay: float = CALIBRATION_DELAY,
    ) -> Dict[str, float]:
        """Calibrate accelerometer offsets.

        Place the device flat and still on a level surface before calling.
        Averages *samples* readings and stores offsets so that the resting
        state reads (0, 0, 1.0g).

        Returns:
            Dictionary with x, y, z offsets.
        """
        print("Calibrating IMU — keep device STILL and FLAT...")
        sum_x, sum_y, sum_z = 0.0, 0.0, 0.0

        for _ in range(samples):
            ax_raw, ay_raw, az_raw = self.read_accel_raw()
            sum_x += ax_raw / ACCEL_SCALE
            sum_y += ay_raw / ACCEL_SCALE
            sum_z += az_raw / ACCEL_SCALE
            time.sleep(delay)

        avg_x = sum_x / samples
        avg_y = sum_y / samples
        avg_z = sum_z / samples

        self.accel_offset["x"] = avg_x
        self.accel_offset["y"] = avg_y
        self.accel_offset["z"] = avg_z - 1.0  # gravity on Z when flat

        print(
            f"Calibration complete. Offsets: "
            f"X={self.accel_offset['x']:.4f}  "
            f"Y={self.accel_offset['y']:.4f}  "
            f"Z={self.accel_offset['z']:.4f}"
        )
        return dict(self.accel_offset)

    def close(self) -> None:
        """Release the I2C bus."""
        self.bus.close()
