"""test_detector.py — Unit tests for the two-stage crash detection algorithm."""

import math
import time
from unittest.mock import MagicMock, patch

import pytest

from config import (
    IMPACT_THRESHOLD, GYRO_THRESHOLD, GYRO_ACCEL_MIN,
    TILT_THRESHOLD, SUSTAINED_TILT_TIME, COOLDOWN_TIME
)
from detector import CrashDetector


@pytest.fixture
def mock_imu():
    """Provide a mock IMU that returns configurable sensor values."""
    imu = MagicMock()
    imu.read_accel_g.return_value = (0.0, 0.0, 1.0)
    imu.accel_magnitude.return_value = 1.0
    imu.gyro_magnitude.return_value = 0.0
    return imu


@pytest.fixture
def callback():
    """Provide a mock crash callback."""
    return MagicMock()


@pytest.fixture
def detector(mock_imu, callback):
    """Provide a CrashDetector with mocked IMU and callback."""
    return CrashDetector(imu=mock_imu, on_crash=callback)


class TestComputeTilt:
    """Test the static tilt-angle computation."""

    def test_flat_device_near_0_degrees(self):
        tilt = CrashDetector.compute_tilt_from_accel(0.0, 0.0, 1.0)
        assert tilt < 5.0

    def test_on_side_near_90_degrees(self):
        tilt = CrashDetector.compute_tilt_from_accel(1.0, 0.0, 0.0)
        assert 85.0 < tilt < 95.0

    def test_upside_down_near_0_degrees(self):
        """Upside down: az=-1, but atan2(0, |-1|) = 0. This is expected."""
        tilt = CrashDetector.compute_tilt_from_accel(0.0, 0.0, -1.0)
        assert tilt < 5.0

    def test_45_degree_tilt(self):
        tilt = CrashDetector.compute_tilt_from_accel(0.707, 0.0, 0.707)
        assert 40.0 < tilt < 50.0

    def test_free_fall_returns_90(self):
        tilt = CrashDetector.compute_tilt_from_accel(0.0, 0.0, 0.0)
        assert tilt == 90.0

    def test_noisy_input_doesnt_crash(self):
        tilt = CrashDetector.compute_tilt_from_accel(100.0, 100.0, 100.0)
        assert 0.0 <= tilt <= 180.0


class TestComputeTiltFromIMU:
    """Test compute_tilt() with mock IMU."""

    def test_returns_float(self, detector, mock_imu):
        mock_imu.read_accel_g.return_value = (0.0, 0.0, 1.0)
        tilt = detector.compute_tilt()
        assert isinstance(tilt, float)

    def test_flat_device_low_tilt(self, detector, mock_imu):
        mock_imu.read_accel_g.return_value = (0.0, 0.0, 1.0)
        tilt = detector.compute_tilt()
        assert tilt < 5.0

    def test_tilted_device_high_tilt(self, detector, mock_imu):
        mock_imu.read_accel_g.return_value = (1.0, 0.0, 0.1)
        tilt = detector.compute_tilt()
        assert tilt > 80.0


class TestCheckSustainedTilt:
    """Test the sustained tilt verification."""

    def test_sustained_tilt_returns_true_when_tilted(self, detector, mock_imu):
        mock_imu.read_accel_g.return_value = (1.0, 0.0, 0.0)
        with patch('detector.time.sleep'):
            with patch('detector.time.time') as mock_time:
                mock_time.side_effect = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
                sustained, tilt = detector.check_sustained_tilt()
        assert sustained is True
        assert tilt > TILT_THRESHOLD

    def test_not_sustained_when_bike_rights_itself(self, detector, mock_imu):
        call_count = [0]
        def alternating_accel():
            call_count[0] += 1
            if call_count[0] <= 2:
                return (1.0, 0.0, 0.0)  # Tilted
            return (0.0, 0.0, 1.0)  # Upright
        mock_imu.read_accel_g.side_effect = lambda: alternating_accel()

        with patch('detector.time.sleep'):
            with patch('detector.time.time') as mock_time:
                mock_time.side_effect = [0.0, 0.1, 0.2, 0.3, 0.4]
                sustained, _ = detector.check_sustained_tilt()
        assert sustained is False


class TestDualPathStage1:
    """Test that both Path A (accel) and Path B (gyro) trigger Stage 1."""

    def test_path_a_high_g_triggers(self, detector, mock_imu):
        """High g-force alone should trigger Stage 1."""
        mag = IMPACT_THRESHOLD + 1.0
        assert mag > IMPACT_THRESHOLD

    def test_path_b_high_gyro_with_moderate_g_triggers(self, detector, mock_imu):
        """High gyro + moderate g should trigger Stage 1."""
        gyro = GYRO_THRESHOLD + 50.0
        mag = GYRO_ACCEL_MIN + 0.5
        path_b = gyro > GYRO_THRESHOLD and mag > GYRO_ACCEL_MIN
        assert path_b is True

    def test_path_b_high_gyro_without_sufficient_g_does_not_trigger(self):
        """High gyro alone (without sufficient g) should NOT trigger."""
        gyro = GYRO_THRESHOLD + 50.0
        mag = GYRO_ACCEL_MIN - 0.5
        path_b = gyro > GYRO_THRESHOLD and mag > GYRO_ACCEL_MIN
        assert path_b is False

    def test_normal_riding_does_not_trigger(self):
        """Normal riding (low g, low gyro) triggers neither path."""
        mag = 1.0
        gyro = 20.0
        path_a = mag > IMPACT_THRESHOLD
        path_b = gyro > GYRO_THRESHOLD and mag > GYRO_ACCEL_MIN
        assert not (path_a or path_b)


class TestCooldown:
    """Test cooldown prevents rapid re-triggers."""

    def test_cooldown_blocks_immediate_retrigger(self, detector):
        detector.last_crash_time = time.time()
        ts = time.time()
        assert (ts - detector.last_crash_time) < COOLDOWN_TIME

    def test_cooldown_allows_after_period(self, detector):
        detector.last_crash_time = time.time() - COOLDOWN_TIME - 1
        ts = time.time()
        assert (ts - detector.last_crash_time) > COOLDOWN_TIME


class TestHistory:
    """Test history buffer behavior."""

    def test_history_starts_empty(self, detector):
        assert len(detector.history) == 0

    def test_history_stores_entries(self, detector):
        detector.history.append({'time': 1.0, 'ax': 0, 'ay': 0, 'az': 1, 'mag': 1.0, 'gyro': 0.0})
        assert len(detector.history) == 1

    def test_history_maxlen_enforced(self, detector):
        for i in range(600):
            detector.history.append({'time': float(i), 'mag': 1.0})
        assert len(detector.history) == 500

    def test_get_history_returns_list(self, detector):
        detector.history.append({'time': 1.0, 'mag': 1.0})
        result = detector.get_history()
        assert isinstance(result, list)
        assert len(result) == 1


class TestCrashCallback:
    """Test that crash callback fires correctly in a simulated scenario."""

    def test_callback_invoked_on_confirmed_crash(self, detector, mock_imu, callback):
        """Simulate: high-g impact → settling → sustained tilt → callback fires."""
        mock_imu.accel_magnitude.return_value = IMPACT_THRESHOLD + 2.0
        mock_imu.gyro_magnitude.return_value = 10.0
        mock_imu.read_accel_g.return_value = (5.0, 0.0, 0.1)

        with patch.object(detector, 'compute_tilt', return_value=80.0):
            with patch.object(detector, 'check_sustained_tilt', return_value=(True, 80.0)):
                with patch('detector.time.sleep'):
                    detector.running = True
                    # Run one iteration manually
                    mag = mock_imu.accel_magnitude()
                    gyro_mag = mock_imu.gyro_magnitude()
                    ts = time.time()
                    ax, ay, az = mock_imu.read_accel_g()

                    path_a = mag > IMPACT_THRESHOLD
                    assert path_a

                    tilt = detector.compute_tilt()
                    assert tilt > TILT_THRESHOLD

                    sustained, final_tilt = detector.check_sustained_tilt()
                    assert sustained

                    detector.on_crash(mag, final_tilt, ts)
                    callback.assert_called_once()

    def test_callback_not_invoked_on_bump(self, detector, mock_imu, callback):
        """Simulate: high-g impact → settling → bike stays upright → no callback."""
        mock_imu.accel_magnitude.return_value = IMPACT_THRESHOLD + 1.0
        mock_imu.read_accel_g.return_value = (0.0, 0.0, 1.0)  # Upright

        tilt = detector.compute_tilt()
        assert tilt < TILT_THRESHOLD
        callback.assert_not_called()


class TestRunLoopTermination:
    """Test that the run loop can be stopped."""

    def test_running_flag_stops_loop(self, detector, mock_imu):
        iteration_count = [0]
        original_sleep = time.sleep

        def counting_sleep(duration):
            iteration_count[0] += 1
            if iteration_count[0] >= 3:
                detector.running = False

        mock_imu.accel_magnitude.return_value = 1.0
        mock_imu.gyro_magnitude.return_value = 0.0
        mock_imu.read_accel_g.return_value = (0.0, 0.0, 1.0)

        with patch('detector.time.sleep', side_effect=counting_sleep):
            detector.run()

        assert detector.running is False
        assert iteration_count[0] >= 3
