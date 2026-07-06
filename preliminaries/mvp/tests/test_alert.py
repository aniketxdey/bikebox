"""
test_alert.py — Tests for the on_crash terminal alert callback.

These tests verify that on_crash() prints the expected crash alert
to stdout. No GPIO or LED hardware is required.

Run:
    python3 -m pytest tests/test_alert.py -v
"""

import time

import pytest

from alert import on_crash


# ------------------------------------------------------------------
# on_crash output verification
# ------------------------------------------------------------------

class TestOnCrash:
    """Verify on_crash prints the correct alert information."""

    def test_on_crash_prints_crash_detected(self, capsys: pytest.CaptureFixture[str]) -> None:
        """on_crash should print a CRASH DETECTED banner."""
        on_crash(peak_g=5.0, tilt_angle=80.0, timestamp=time.time())
        captured = capsys.readouterr()
        assert "CRASH DETECTED" in captured.out

    def test_on_crash_prints_peak_g(self, capsys: pytest.CaptureFixture[str]) -> None:
        """on_crash should include the peak g-force value."""
        on_crash(peak_g=6.25, tilt_angle=72.0, timestamp=time.time())
        captured = capsys.readouterr()
        assert "6.25" in captured.out

    def test_on_crash_prints_tilt_angle(self, capsys: pytest.CaptureFixture[str]) -> None:
        """on_crash should include the tilt angle."""
        on_crash(peak_g=5.0, tilt_angle=83.5, timestamp=time.time())
        captured = capsys.readouterr()
        assert "83.5" in captured.out

    def test_on_crash_prints_timestamp(self, capsys: pytest.CaptureFixture[str]) -> None:
        """on_crash should include a human-readable time."""
        ts = time.time()
        expected_time = time.strftime("%H:%M:%S", time.localtime(ts))
        on_crash(peak_g=5.0, tilt_angle=80.0, timestamp=ts)
        captured = capsys.readouterr()
        assert expected_time in captured.out

    def test_on_crash_returns_immediately(self) -> None:
        """on_crash should return without blocking (no LED thread to wait on)."""
        start = time.time()
        on_crash(peak_g=5.0, tilt_angle=80.0, timestamp=time.time())
        elapsed = time.time() - start
        assert elapsed < 0.1, f"on_crash took {elapsed:.3f}s — should be near-instant"
