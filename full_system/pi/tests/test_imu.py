"""test_imu.py — Unit tests for the IMU driver (mocked I2C hardware)."""

import math
from unittest.mock import MagicMock, patch, call

import pytest
import smbus2

from imu import IMU, WHO_AM_I, ACCEL_XOUT_H, GYRO_XOUT_H, VALID_CHIP_IDS
from config import MPU6050_ADDR, I2C_BUS, ACCEL_SENSITIVITY, ACCEL_RANGE, GYRO_SENSITIVITY, GYRO_RANGE


@pytest.fixture
def mock_bus():
    """Provide a fresh mock SMBus."""
    bus = MagicMock()
    bus.read_byte_data.return_value = 0x68  # Valid WHO_AM_I
    return bus


@pytest.fixture
def sensor(mock_bus):
    """Provide an IMU instance with mocked I2C bus."""
    with patch.object(smbus2, 'SMBus', return_value=mock_bus):
        s = IMU()
    return s


class TestIMUInit:
    """Test sensor initialization."""

    def test_who_am_i_check_passes_for_valid_ids(self, mock_bus):
        for chip_id in VALID_CHIP_IDS:
            mock_bus.read_byte_data.return_value = chip_id
            with patch.object(smbus2, 'SMBus', return_value=mock_bus):
                sensor = IMU()
            assert sensor.address == MPU6050_ADDR

    def test_who_am_i_warning_for_unknown_id(self, mock_bus, capsys):
        mock_bus.read_byte_data.return_value = 0xFF
        with patch.object(smbus2, 'SMBus', return_value=mock_bus):
            sensor = IMU()
        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    def test_sets_correct_address(self, sensor):
        assert sensor.address == MPU6050_ADDR

    def test_sets_correct_scales(self, sensor):
        assert sensor.accel_scale == ACCEL_SENSITIVITY[ACCEL_RANGE]
        assert sensor.gyro_scale == GYRO_SENSITIVITY[GYRO_RANGE]


class TestAccelReading:
    """Test accelerometer data reads."""

    def test_read_accel_raw_returns_three_ints(self, sensor, mock_bus):
        mock_bus.read_byte_data.side_effect = lambda addr, reg: {
            ACCEL_XOUT_H: 0x00, ACCEL_XOUT_H + 1: 0x00,
            ACCEL_XOUT_H + 2: 0x00, ACCEL_XOUT_H + 3: 0x00,
            ACCEL_XOUT_H + 4: 0x08, ACCEL_XOUT_H + 5: 0x00,
        }.get(reg, 0x68)
        ax, ay, az = sensor.read_accel_raw()
        assert isinstance(ax, int)
        assert isinstance(ay, int)
        assert isinstance(az, int)

    def test_read_accel_g_applies_offset(self, sensor, mock_bus):
        sensor.accel_offset = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        mock_bus.read_byte_data.side_effect = lambda addr, reg: {
            ACCEL_XOUT_H: 0x00, ACCEL_XOUT_H + 1: 0x00,
            ACCEL_XOUT_H + 2: 0x00, ACCEL_XOUT_H + 3: 0x00,
            ACCEL_XOUT_H + 4: 0x08, ACCEL_XOUT_H + 5: 0x00,
        }.get(reg, 0x68)
        ax, ay, az = sensor.read_accel_g()
        assert isinstance(ax, float)
        assert isinstance(ay, float)
        assert isinstance(az, float)

    def test_accel_magnitude_nonnegative(self, sensor, mock_bus):
        mock_bus.read_byte_data.return_value = 0x00
        mag = sensor.accel_magnitude()
        assert mag >= 0.0

    def test_accel_magnitude_with_known_values(self, sensor):
        """When we mock read_accel_g to return known values, verify magnitude."""
        with patch.object(sensor, 'read_accel_g', return_value=(0.0, 0.0, 1.0)):
            mag = sensor.accel_magnitude()
        assert abs(mag - 1.0) < 0.001

    def test_accel_magnitude_with_3g(self, sensor):
        with patch.object(sensor, 'read_accel_g', return_value=(2.0, 2.0, 1.0)):
            mag = sensor.accel_magnitude()
        expected = math.sqrt(4 + 4 + 1)
        assert abs(mag - expected) < 0.001


class TestGyroReading:
    """Test gyroscope data reads."""

    def test_read_gyro_raw_returns_three_ints(self, sensor, mock_bus):
        mock_bus.read_byte_data.side_effect = lambda addr, reg: 0x00
        gx, gy, gz = sensor.read_gyro_raw()
        assert isinstance(gx, int)
        assert isinstance(gy, int)
        assert isinstance(gz, int)

    def test_gyro_magnitude_nonnegative(self, sensor):
        with patch.object(sensor, 'read_gyro_dps', return_value=(0.0, 0.0, 0.0)):
            mag = sensor.gyro_magnitude()
        assert mag >= 0.0

    def test_gyro_magnitude_with_known_values(self, sensor):
        with patch.object(sensor, 'read_gyro_dps', return_value=(100.0, 100.0, 100.0)):
            mag = sensor.gyro_magnitude()
        expected = math.sqrt(3 * 100 ** 2)
        assert abs(mag - expected) < 0.1


class TestCalibration:
    """Test calibration process."""

    def test_calibrate_sets_offsets(self, sensor, mock_bus):
        mock_bus.read_byte_data.return_value = 0x00
        offsets = sensor.calibrate(samples=10)
        assert 'x' in offsets
        assert 'y' in offsets
        assert 'z' in offsets

    def test_calibrate_z_offset_accounts_for_gravity(self, sensor, mock_bus):
        """After calibration with device flat, z offset should be avg_z - 1.0."""
        scale = sensor.accel_scale
        mock_val_z = int(1.0 * scale)
        high_z = (mock_val_z >> 8) & 0xFF
        low_z = mock_val_z & 0xFF

        def side_effect(addr, reg):
            if reg in (ACCEL_XOUT_H + 4,):
                return high_z
            if reg in (ACCEL_XOUT_H + 5,):
                return low_z
            return 0x00
        mock_bus.read_byte_data.side_effect = side_effect

        sensor.calibrate(samples=10)
        assert abs(sensor.accel_offset['z'] - 0.0) < 0.1


class TestClose:
    """Test resource cleanup."""

    def test_close_calls_bus_close(self, sensor, mock_bus):
        sensor.close()
        mock_bus.close.assert_called_once()
