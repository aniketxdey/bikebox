"""test_battery.py — Unit tests for the PiSugar 3 battery monitor."""

import time
from unittest.mock import MagicMock, patch

import pytest
import smbus2

from battery import BatteryMonitor
from config import (
    PISUGAR_ADDR, PISUGAR_BATTERY_REGISTER,
    PISUGAR_CHARGING_REGISTER, BATTERY_LOW_THRESHOLD,
    BATTERY_CRITICAL_THRESHOLD, BATTERY_CHECK_INTERVAL
)


@pytest.fixture
def mock_bus():
    """Provide a fresh mock SMBus."""
    bus = MagicMock()
    bus.read_byte_data.return_value = 75  # 75% battery
    return bus


@pytest.fixture
def monitor(mock_bus):
    """Provide a BatteryMonitor with mocked I2C."""
    with patch.object(smbus2, 'SMBus', return_value=mock_bus):
        mon = BatteryMonitor()
    return mon


class TestBatteryMonitorInit:
    """Test initialization."""

    def test_default_state(self, monitor):
        assert monitor.get_percentage() == 100
        assert monitor.is_charging() is False

    def test_get_state_returns_dict(self, monitor):
        state = monitor.get_state()
        assert 'percentage' in state
        assert 'charging' in state
        assert 'last_update' in state


class TestBatteryReading:
    """Test battery percentage reading."""

    def test_read_battery_returns_value(self, monitor, mock_bus):
        with patch.object(smbus2, 'SMBus', return_value=mock_bus):
            monitor._bus = mock_bus
            pct = monitor._read_battery()
        assert pct == 75

    def test_read_battery_clamps_to_100(self, monitor, mock_bus):
        mock_bus.read_byte_data.return_value = 120
        monitor._bus = mock_bus
        pct = monitor._read_battery()
        assert pct == 100

    def test_read_battery_clamps_to_0(self, monitor, mock_bus):
        mock_bus.read_byte_data.return_value = 0
        monitor._bus = mock_bus
        pct = monitor._read_battery()
        assert pct == 0

    def test_read_battery_returns_neg1_on_error(self, monitor, mock_bus):
        mock_bus.read_byte_data.side_effect = OSError("I2C error")
        monitor._bus = mock_bus
        pct = monitor._read_battery()
        assert pct == -1


class TestChargingStatus:
    """Test charging detection."""

    def test_charging_detected_when_bit7_set(self, monitor, mock_bus):
        mock_bus.read_byte_data.return_value = 0x80
        monitor._bus = mock_bus
        assert monitor._read_charging() is True

    def test_not_charging_when_bit7_clear(self, monitor, mock_bus):
        mock_bus.read_byte_data.return_value = 0x00
        monitor._bus = mock_bus
        assert monitor._read_charging() is False

    def test_charging_with_other_bits_set(self, monitor, mock_bus):
        mock_bus.read_byte_data.return_value = 0x85  # bit 7 + bits 0, 2
        monitor._bus = mock_bus
        assert monitor._read_charging() is True


class TestLowBatteryCallbacks:
    """Test that low/critical battery callbacks fire correctly."""

    def test_low_battery_callback_fires(self, monitor, mock_bus):
        mock_bus.read_byte_data.return_value = BATTERY_LOW_THRESHOLD - 1
        monitor._bus = mock_bus
        low_cb = MagicMock()
        monitor._on_low_battery = low_cb
        monitor._running = True

        monitor._state['percentage'] = 100
        pct = monitor._read_battery()
        with monitor._lock:
            monitor._state['percentage'] = pct
            monitor._state['last_update'] = time.time()

        if pct <= BATTERY_LOW_THRESHOLD and not monitor._low_warning_sent:
            monitor._low_warning_sent = True
            if monitor._on_low_battery:
                monitor._on_low_battery(pct)

        low_cb.assert_called_once()

    def test_critical_battery_callback_fires(self, monitor, mock_bus):
        mock_bus.read_byte_data.return_value = BATTERY_CRITICAL_THRESHOLD - 1
        monitor._bus = mock_bus
        crit_cb = MagicMock()
        monitor._on_critical_battery = crit_cb
        monitor._running = True

        pct = monitor._read_battery()
        with monitor._lock:
            monitor._state['percentage'] = pct

        if pct <= BATTERY_CRITICAL_THRESHOLD and not monitor._critical_warning_sent:
            monitor._critical_warning_sent = True
            if monitor._on_critical_battery:
                monitor._on_critical_battery(pct)

        crit_cb.assert_called_once()


class TestMonitorStop:
    """Test stop behavior."""

    def test_stop_sets_running_false(self, monitor):
        monitor._running = True
        monitor._thread = None
        monitor.stop()
        assert monitor._running is False
