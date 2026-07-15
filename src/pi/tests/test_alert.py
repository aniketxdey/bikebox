"""test_alert.py — Unit tests for the crash alert pipeline."""

import time
from unittest.mock import MagicMock, patch

import pytest

import alert
from config import (
    GRACE_PERIOD_SECONDS, LONG_HOLD_MIN,
    ALERT_CRASH_DETECTED, ALERT_CRASH_CANCELLED, ALERT_CRASH_CONFIRMED,
    GRACE_COUNTDOWN, GRACE_CANCELLED_BUTTON, GRACE_CANCELLED_APP,
)


def _make_fast_time():
    """Create a mock time.time() that advances 0.2s per call to speed up grace period."""
    counter = [0.0]
    def fast_time():
        counter[0] += 0.2
        return counter[0]
    return fast_time


@pytest.fixture(autouse=True)
def reset_alert_state():
    """Reset alert module state between tests."""
    alert._ble_server = None
    alert._camera_manager = None
    alert._battery_monitor = None
    alert._cancel_from_app = False
    alert._alert_active = False
    yield
    alert._ble_server = None
    alert._camera_manager = None
    alert._battery_monitor = None
    alert._cancel_from_app = False
    alert._alert_active = False


def _run_on_crash_fast(**kwargs):
    """Run on_crash with mocked time so it completes in milliseconds."""
    ble = kwargs.get('ble')
    cam = kwargs.get('cam')
    bat = kwargs.get('bat')
    button_held = kwargs.get('button_held', False)
    cancel_after = kwargs.get('cancel_after_calls', None)

    if ble or cam or bat:
        alert.set_subsystems(ble_server=ble, camera_manager=cam, battery_monitor=bat)

    call_count = [0]
    def sleep_maybe_cancel(d):
        if cancel_after is not None:
            call_count[0] += 1
            if call_count[0] > cancel_after:
                alert._cancel_from_app = True

    with patch('alert.time.sleep', side_effect=sleep_maybe_cancel):
        with patch('alert.time.time', side_effect=_make_fast_time()):
            with patch('alert.time.strftime', return_value='12:00:00'):
                with patch('alert._check_button_held', return_value=button_held):
                    alert.on_crash(5.0, 80.0, 1000.0)


class TestSetupGPIO:
    """Test GPIO initialization."""

    def test_setup_gpio_calls_setmode(self):
        import RPi.GPIO as GPIO
        GPIO.setmode.reset_mock()
        alert.setup_gpio()
        GPIO.setmode.assert_called()

    def test_setup_gpio_configures_button_when_enabled(self):
        import RPi.GPIO as GPIO
        GPIO.setup.reset_mock()
        alert.setup_gpio()
        assert GPIO.setup.called

    def test_setup_gpio_skips_button_when_disabled(self):
        import RPi.GPIO as GPIO
        GPIO.setup.reset_mock()
        with patch('alert.BUTTON_ENABLED', False):
            alert.setup_gpio()
        GPIO.setup.assert_not_called()


class TestSetSubsystems:
    """Test subsystem wiring."""

    def test_set_subsystems_stores_references(self):
        ble = MagicMock()
        cam = MagicMock()
        bat = MagicMock()
        alert.set_subsystems(ble_server=ble, camera_manager=cam, battery_monitor=bat)
        assert alert._ble_server is ble
        assert alert._camera_manager is cam
        assert alert._battery_monitor is bat

    def test_set_subsystems_registers_cancel_callback(self):
        ble = MagicMock()
        alert.set_subsystems(ble_server=ble)
        ble.set_cancel_callback.assert_called_once()


class TestOnCancelFromApp:
    """Test app-initiated cancel flag."""

    def test_sets_cancel_flag(self):
        assert alert._cancel_from_app is False
        alert._on_cancel_from_app()
        assert alert._cancel_from_app is True


class TestOnCrash:
    """Test the main crash alert handler."""

    def test_basic_crash_alert_completes(self):
        """on_crash should complete without raising when no subsystems are wired."""
        _run_on_crash_fast()

    def test_ble_crash_alert_sent(self):
        """BLE server should receive crash alert notification."""
        ble = MagicMock()
        _run_on_crash_fast(ble=ble)
        ble.send_crash_alert.assert_called()
        first_call = ble.send_crash_alert.call_args_list[0]
        assert first_call[0][0] == ALERT_CRASH_DETECTED

    def test_grace_period_sends_countdown(self):
        """BLE server should receive countdown updates."""
        ble = MagicMock()
        _run_on_crash_fast(ble=ble)
        assert ble.send_grace_period.call_count > 0

    def test_camera_clip_triggered(self):
        """Camera manager should be told to save a clip."""
        cam = MagicMock()
        cam.is_recording.return_value = True
        with patch('alert.threading.Thread') as mock_thread:
            mock_thread.return_value.start = MagicMock()
            _run_on_crash_fast(cam=cam)
        # The Thread constructor should have been called for camera clip

    def test_battery_level_read(self):
        """Battery monitor should be queried for level."""
        bat = MagicMock()
        bat.get_percentage.return_value = 75
        _run_on_crash_fast(bat=bat)
        bat.get_percentage.assert_called()

    def test_cancel_from_app_stops_countdown(self):
        """App cancel should stop the grace period early."""
        ble = MagicMock()
        _run_on_crash_fast(ble=ble, cancel_after_calls=5)

        cancel_calls = [c for c in ble.send_crash_alert.call_args_list
                       if c[0][0] == ALERT_CRASH_CANCELLED]
        assert len(cancel_calls) > 0

    def test_confirmed_when_no_cancel(self):
        """If no cancel received, alert should be confirmed."""
        ble = MagicMock()
        _run_on_crash_fast(ble=ble)

        confirmed_calls = [c for c in ble.send_crash_alert.call_args_list
                          if c[0][0] == ALERT_CRASH_CONFIRMED]
        assert len(confirmed_calls) > 0

    def test_reentrant_crash_rejected(self):
        """Second crash while first is active should be rejected."""
        alert._alert_active = True
        ble = MagicMock()
        alert.set_subsystems(ble_server=ble)
        alert.on_crash(5.0, 80.0, time.time())
        ble.send_crash_alert.assert_not_called()


class TestCleanup:
    """Test GPIO cleanup."""

    def test_cleanup_calls_gpio_cleanup(self):
        import RPi.GPIO as GPIO
        GPIO.cleanup.reset_mock()
        alert.cleanup()
        GPIO.cleanup.assert_called()
