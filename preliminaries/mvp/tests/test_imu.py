"""
test_imu.py — Hardware-level tests for the MPU-6050 IMU driver.

These tests run ON the Raspberry Pi with the MPU-6050 connected.
The sensor must be stationary and flat on a level surface during
the test run. The address is auto-detected (0x69 with AD0 HIGH,
or 0x68 without).

Run:
    python3 -m pytest tests/test_imu.py -v
"""

import math
import subprocess
import time

import pytest
import smbus2

from imu import (
    ACCEL_SCALE,
    GYRO_SCALE,
    MPU_ADDR_AD0_HIGH,
    MPU_ADDR_DEFAULT,
    WHO_AM_I,
    WHO_AM_I_EXPECTED,
    IMU,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
def sensor() -> IMU:
    """Provide a shared, calibrated IMU instance for the test module."""
    s = IMU()
    s.calibrate(samples=200, delay=0.005)
    return s


# ------------------------------------------------------------------
# I2C bus-level checks
# ------------------------------------------------------------------

class TestI2CBus:
    """Verify the MPU-6050 is visible on the I2C bus."""

    def test_i2cdetect_finds_device(self) -> None:
        """i2cdetect should report a device at 0x69 or 0x68."""
        result = subprocess.run(
            ["sudo", "i2cdetect", "-y", "1"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert "69" in result.stdout or "68" in result.stdout, (
            f"No MPU-6050 found on I2C bus 1.\n{result.stdout}"
        )

    def test_who_am_i_readable(self) -> None:
        """WHO_AM_I register should be readable at the detected address."""
        bus = smbus2.SMBus(1)
        try:
            for addr in (MPU_ADDR_AD0_HIGH, MPU_ADDR_DEFAULT):
                try:
                    chip_id = bus.read_byte_data(addr, WHO_AM_I)
                    assert isinstance(chip_id, int), "WHO_AM_I did not return an int"
                    return
                except OSError:
                    continue
            pytest.fail("Could not read WHO_AM_I at 0x69 or 0x68")
        finally:
            bus.close()


# ------------------------------------------------------------------
# Accelerometer at rest
# ------------------------------------------------------------------

class TestAccelAtRest:
    """Accelerometer sanity checks with the device flat and still."""

    NUM_SAMPLES = 100

    def test_magnitude_at_rest_is_near_1g(self, sensor: IMU) -> None:
        """With the sensor flat and still, magnitude should be 0.8–1.2g."""
        for i in range(self.NUM_SAMPLES):
            mag = sensor.accel_magnitude()
            assert 0.8 <= mag <= 1.2, (
                f"Sample {i}: magnitude {mag:.4f}g outside [0.8, 1.2]"
            )
            time.sleep(0.005)

    def test_individual_axes_in_range(self, sensor: IMU) -> None:
        """At rest flat: X ≈ 0, Y ≈ 0, Z ≈ 1.0g."""
        for i in range(self.NUM_SAMPLES):
            ax, ay, az = sensor.read_accel_g()
            assert -0.3 <= ax <= 0.3, f"Sample {i}: ax={ax:.4f} out of range"
            assert -0.3 <= ay <= 0.3, f"Sample {i}: ay={ay:.4f} out of range"
            assert 0.7 <= az <= 1.3, f"Sample {i}: az={az:.4f} out of range"
            time.sleep(0.005)


# ------------------------------------------------------------------
# Gyroscope at rest
# ------------------------------------------------------------------

class TestGyroAtRest:
    """Gyroscope readings with the device stationary."""

    NUM_SAMPLES = 100
    MAX_DPS = 5.0  # degrees-per-second tolerance

    def test_gyro_axes_within_5dps_when_stationary(self, sensor: IMU) -> None:
        """All gyro axes should read within ±5 °/s when still."""
        for i in range(self.NUM_SAMPLES):
            gx, gy, gz = sensor.read_gyro_dps()
            assert abs(gx) < self.MAX_DPS, f"Sample {i}: gx={gx:.2f}°/s"
            assert abs(gy) < self.MAX_DPS, f"Sample {i}: gy={gy:.2f}°/s"
            assert abs(gz) < self.MAX_DPS, f"Sample {i}: gz={gz:.2f}°/s"
            time.sleep(0.005)


# ------------------------------------------------------------------
# Calibration quality
# ------------------------------------------------------------------

class TestCalibration:
    """Verify that calibration brings resting magnitude close to 1.0g."""

    def test_calibration_reduces_magnitude_error_below_005g(self) -> None:
        """After calibration, average magnitude error should be < 0.05g."""
        sensor = IMU()
        sensor.calibrate(samples=200, delay=0.005)

        errors = []
        for _ in range(100):
            mag = sensor.accel_magnitude()
            errors.append(abs(mag - 1.0))
            time.sleep(0.005)

        avg_error = sum(errors) / len(errors)
        assert avg_error < 0.05, (
            f"Average magnitude error {avg_error:.4f}g exceeds 0.05g threshold"
        )
        sensor.close()
