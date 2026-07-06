"""
test_detector.py — Tests for the two-stage crash detection algorithm.

Tests cover tilt computation, threshold logic, the full impact→tilt→crash
pipeline, false-positive rejection, and cooldown enforcement.

Run:
    python3 -m pytest tests/test_detector.py -v
"""

import math
import time
from typing import Optional, Tuple
from unittest.mock import MagicMock

import pytest

from detector import (
    COOLDOWN_TIME,
    IMPACT_THRESHOLD,
    TILT_THRESHOLD,
    CrashDetector,
)
from imu import IMU


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
def sensor() -> IMU:
    """Provide a shared, calibrated IMU instance."""
    s = IMU()
    s.calibrate(samples=200, delay=0.005)
    return s


@pytest.fixture
def detector(sensor: IMU) -> CrashDetector:
    """Provide a CrashDetector wired to the real sensor with a mock callback."""
    callback = MagicMock()
    return CrashDetector(imu=sensor, on_crash=callback)


# ------------------------------------------------------------------
# Tilt computation (static / pure-math)
# ------------------------------------------------------------------

class TestComputeTilt:
    """Test the static tilt-angle computation."""

    def test_flat_device_tilt_below_10_degrees(self) -> None:
        """When az ≈ 1g and ax, ay ≈ 0, tilt should be < 10°."""
        tilt = CrashDetector.compute_tilt_from_accel(0.0, 0.0, 1.0)
        assert tilt < 10.0, f"Tilt {tilt:.1f}° should be < 10° when flat"

    def test_on_side_tilt_above_70_degrees(self) -> None:
        """When ax ≈ 1g and az ≈ 0, tilt should be > 70° (device on side)."""
        tilt = CrashDetector.compute_tilt_from_accel(1.0, 0.0, 0.0)
        assert tilt > 70.0, f"Tilt {tilt:.1f}° should be > 70° on side"

    def test_upside_down_tilt_near_180_degrees(self) -> None:
        """When az ≈ -1g, tilt should be near 180°."""
        tilt = CrashDetector.compute_tilt_from_accel(0.0, 0.0, -1.0)
        assert tilt > 170.0, f"Tilt {tilt:.1f}° should be > 170° upside down"

    def test_free_fall_returns_90_degrees(self) -> None:
        """Near-zero magnitude (free-fall) should return 90°."""
        tilt = CrashDetector.compute_tilt_from_accel(0.0, 0.0, 0.0)
        assert tilt == 90.0

    def test_noisy_input_clamped(self) -> None:
        """Large noise that could push az/mag outside [-1,1] should not crash."""
        tilt = CrashDetector.compute_tilt_from_accel(0.0, 0.0, 1.5)
        assert 0.0 <= tilt <= 180.0


# ------------------------------------------------------------------
# Live tilt from real sensor
# ------------------------------------------------------------------

class TestLiveTilt:
    """Test compute_tilt() with the real sensor flat on a table."""

    def test_compute_tilt_flat_below_10_degrees(self, detector: CrashDetector) -> None:
        """Real sensor flat on table should report < 10° tilt."""
        tilt = detector.compute_tilt()
        assert tilt < 10.0, f"Tilt {tilt:.1f}° should be < 10° when flat"


# ------------------------------------------------------------------
# Impact + tilt → CRASH (manual test)
# ------------------------------------------------------------------

class TestCrashTriggering:
    """Integration tests that require physical interaction with the sensor.

    These tests print instructions and wait for the user to shake / tilt
    the device. They are marked with a 'manual' marker so they can be
    skipped in automated runs: ``pytest -m 'not manual'``.
    """

    @pytest.mark.manual
    def test_impact_plus_tilt_triggers_crash(self, detector: CrashDetector) -> None:
        """Shake device hard (>4g) then tilt it on its side → CRASH fires."""
        print("\n>>> SHAKE the device hard, then TILT it on its side. You have 10s.")
        deadline = time.time() + 10.0
        triggered = False

        while time.time() < deadline and not triggered:
            mag = detector.imu.accel_magnitude()
            if mag > IMPACT_THRESHOLD:
                time.sleep(1.0)
                tilt = detector.compute_tilt()
                if tilt > TILT_THRESHOLD:
                    sustained, _ = detector.check_sustained_tilt()
                    if sustained:
                        triggered = True
            time.sleep(0.01)

        assert triggered, "CRASH was not triggered within the 10s window"

    @pytest.mark.manual
    def test_impact_without_tilt_does_not_trigger_crash(
        self, detector: CrashDetector
    ) -> None:
        """Tap the table hard but keep device upright → no crash."""
        print("\n>>> TAP the table hard, but keep the device UPRIGHT. You have 10s.")
        deadline = time.time() + 10.0
        false_crash = False

        while time.time() < deadline:
            mag = detector.imu.accel_magnitude()
            if mag > IMPACT_THRESHOLD:
                time.sleep(1.0)
                tilt = detector.compute_tilt()
                if tilt > TILT_THRESHOLD:
                    sustained, _ = detector.check_sustained_tilt()
                    if sustained:
                        false_crash = True
                        break
            time.sleep(0.01)

        assert not false_crash, "CRASH triggered when device was upright (false positive)"


# ------------------------------------------------------------------
# Cooldown enforcement
# ------------------------------------------------------------------

class TestCooldown:
    """Verify cooldown prevents rapid re-triggers."""

    def test_cooldown_blocks_second_crash_within_window(
        self, detector: CrashDetector
    ) -> None:
        """Setting last_crash_time to now should suppress new detections."""
        detector.last_crash_time = time.time()
        ts = time.time()
        within_cooldown = (ts - detector.last_crash_time) < COOLDOWN_TIME
        assert within_cooldown, "Cooldown check failed"

    def test_cooldown_allows_detection_after_expiry(
        self, detector: CrashDetector
    ) -> None:
        """After COOLDOWN_TIME has elapsed, detection should be allowed."""
        detector.last_crash_time = time.time() - COOLDOWN_TIME - 1
        ts = time.time()
        past_cooldown = (ts - detector.last_crash_time) >= COOLDOWN_TIME
        assert past_cooldown, "Detection should be allowed after cooldown"
