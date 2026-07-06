"""
imu.py — MPU-6050 I2C driver for BikeBox.

Reads 3-axis accelerometer and gyroscope data from the GY-521 breakout.
Configured for ±16g accel range and ±2000°/s gyro range.

CRITICAL: The MPU-6050 is at address 0x69 (AD0 pin wired to 3.3V)
          because PiSugar 3 occupies the default 0x68.
"""

import math
import time
from typing import Dict, Tuple

import smbus2

from config import (
    MPU6050_ADDR, I2C_BUS, ACCEL_RANGE, GYRO_RANGE,
    ACCEL_SENSITIVITY, GYRO_SENSITIVITY, CALIBRATION_SAMPLES
)

# MPU-6050 Register Map
PWR_MGMT_1 = 0x6B
PWR_MGMT_2 = 0x6C
SMPLRT_DIV = 0x19
CONFIG_REG = 0x1A
ACCEL_CONFIG = 0x1C
GYRO_CONFIG = 0x1B
ACCEL_XOUT_H = 0x3B
GYRO_XOUT_H = 0x43
WHO_AM_I = 0x75

VALID_CHIP_IDS = {0x68, 0x70, 0x71, 0x72, 0x73, 0x98}


class IMU:
    """Interface to the MPU-6050 accelerometer/gyroscope."""

    def __init__(self, address: int = MPU6050_ADDR, bus_num: int = I2C_BUS) -> None:
        self.address = address
        self.bus = smbus2.SMBus(bus_num)
        self.accel_scale = ACCEL_SENSITIVITY[ACCEL_RANGE]
        self.gyro_scale = GYRO_SENSITIVITY[GYRO_RANGE]
        self.accel_offset: Dict[str, float] = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self._initialize()

    def _initialize(self) -> None:
        """Wake up the sensor and configure ranges."""
        who = self.bus.read_byte_data(self.address, WHO_AM_I)
        if who not in VALID_CHIP_IDS:
            print(f"WARNING: Unexpected WHO_AM_I: 0x{who:02X} (expected 0x68)")
            print("Proceeding anyway — may be a compatible clone chip.")

        self.bus.write_byte_data(self.address, PWR_MGMT_1, 0x00)
        time.sleep(0.1)

        self.bus.write_byte_data(self.address, SMPLRT_DIV, 0x09)  # 100 Hz
        self.bus.write_byte_data(self.address, CONFIG_REG, 0x03)  # ~44 Hz DLPF
        self.bus.write_byte_data(self.address, ACCEL_CONFIG, ACCEL_RANGE << 3)
        self.bus.write_byte_data(self.address, GYRO_CONFIG, GYRO_RANGE << 3)

        print(f"IMU initialized at 0x{self.address:02X} "
              f"(accel: ±{2 ** (ACCEL_RANGE + 1)}g, "
              f"gyro: ±{250 * (2 ** GYRO_RANGE)}°/s)")

    def _read_word(self, reg: int) -> int:
        """Read a signed 16-bit value from two consecutive registers."""
        high = self.bus.read_byte_data(self.address, reg)
        low = self.bus.read_byte_data(self.address, reg + 1)
        value = (high << 8) | low
        if value >= 0x8000:
            value -= 0x10000
        return value

    def read_accel_raw(self) -> Tuple[int, int, int]:
        """Read raw accelerometer values (X, Y, Z)."""
        ax = self._read_word(ACCEL_XOUT_H)
        ay = self._read_word(ACCEL_XOUT_H + 2)
        az = self._read_word(ACCEL_XOUT_H + 4)
        return ax, ay, az

    def read_accel_g(self) -> Tuple[float, float, float]:
        """Read accelerometer in g, with calibration offset applied."""
        ax, ay, az = self.read_accel_raw()
        gx = (ax / self.accel_scale) - self.accel_offset['x']
        gy = (ay / self.accel_scale) - self.accel_offset['y']
        gz = (az / self.accel_scale) - self.accel_offset['z']
        return gx, gy, gz

    def read_gyro_raw(self) -> Tuple[int, int, int]:
        """Read raw gyroscope values (X, Y, Z)."""
        gx = self._read_word(GYRO_XOUT_H)
        gy = self._read_word(GYRO_XOUT_H + 2)
        gz = self._read_word(GYRO_XOUT_H + 4)
        return gx, gy, gz

    def read_gyro_dps(self) -> Tuple[float, float, float]:
        """Read gyroscope in degrees per second."""
        gx, gy, gz = self.read_gyro_raw()
        return gx / self.gyro_scale, gy / self.gyro_scale, gz / self.gyro_scale

    def accel_magnitude(self) -> float:
        """Compute total acceleration magnitude in g."""
        ax, ay, az = self.read_accel_g()
        return math.sqrt(ax ** 2 + ay ** 2 + az ** 2)

    def gyro_magnitude(self) -> float:
        """Compute total angular velocity magnitude in °/s."""
        gx, gy, gz = self.read_gyro_dps()
        return math.sqrt(gx ** 2 + gy ** 2 + gz ** 2)

    def calibrate(self, samples: int = CALIBRATION_SAMPLES) -> Dict[str, float]:
        """
        Calibrate accelerometer offsets. Device must be stationary and level.
        Gravity should read as (0, 0, 1.0g) after calibration.
        """
        print(f"Calibrating IMU ({samples} samples). Keep device still and level...")
        sum_x, sum_y, sum_z = 0.0, 0.0, 0.0

        for _ in range(samples):
            ax, ay, az = self.read_accel_raw()
            sum_x += ax / self.accel_scale
            sum_y += ay / self.accel_scale
            sum_z += az / self.accel_scale
            time.sleep(0.005)

        avg_x = sum_x / samples
        avg_y = sum_y / samples
        avg_z = sum_z / samples

        self.accel_offset['x'] = avg_x
        self.accel_offset['y'] = avg_y
        self.accel_offset['z'] = avg_z - 1.0

        print(f"Calibration done. Offsets: X={avg_x:.4f}, Y={avg_y:.4f}, Z={avg_z:.4f}")
        return dict(self.accel_offset)

    def close(self) -> None:
        """Release the I2C bus."""
        self.bus.close()
