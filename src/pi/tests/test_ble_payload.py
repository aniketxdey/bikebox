"""test_ble_payload.py — Test BLE payload encoding/decoding round-trips.

Tests the binary payload format defined in the BLE protocol spec to ensure
the Pi-side encoding matches what the iOS app expects to decode.
"""

import struct
import time

import pytest

from config import (
    ALERT_CRASH_DETECTED, ALERT_CRASH_CANCELLED, ALERT_CRASH_CONFIRMED,
    GRACE_IDLE, GRACE_COUNTDOWN, GRACE_CANCELLED_BUTTON, GRACE_CANCELLED_APP,
    DEVICE_BOOTING, DEVICE_MONITORING, DEVICE_GRACE_PERIOD,
    DEVICE_ALERT_SENT, DEVICE_LOW_BATTERY,
)


class TestCrashAlertPayload:
    """Test the 17-byte crash alert payload format."""

    def _encode_crash_alert(self, alert_type, lat, lon, peak_g, tilt, timestamp, battery):
        """Encode a crash alert payload (same as ble_server.py)."""
        peak_g_int = int(peak_g * 100)
        tilt_int = int(min(tilt, 180))
        ts_int = int(timestamp)
        bat = int(max(0, min(100, battery)))
        return struct.pack('<BffHBIB', alert_type, lat, lon, peak_g_int, tilt_int, ts_int, bat)

    def _decode_crash_alert(self, data):
        """Decode a crash alert payload (same as iOS PayloadDecoder)."""
        alert_type = data[0]
        lat = struct.unpack_from('<f', data, 1)[0]
        lon = struct.unpack_from('<f', data, 5)[0]
        peak_g_x100 = struct.unpack_from('<H', data, 9)[0]
        tilt = data[11]
        timestamp = struct.unpack_from('<I', data, 12)[0]
        battery = data[16]
        return {
            'alert_type': alert_type,
            'latitude': lat,
            'longitude': lon,
            'peak_g': peak_g_x100 / 100.0,
            'tilt': tilt,
            'timestamp': timestamp,
            'battery': battery,
        }

    def test_payload_is_17_bytes(self):
        payload = self._encode_crash_alert(
            ALERT_CRASH_DETECTED, 43.7044, -72.2887, 5.23, 78, 1000000, 85
        )
        assert len(payload) == 17

    def test_roundtrip_crash_detected(self):
        ts = int(time.time())
        payload = self._encode_crash_alert(
            ALERT_CRASH_DETECTED, 43.7044, -72.2887, 5.23, 78, ts, 85
        )
        decoded = self._decode_crash_alert(payload)
        assert decoded['alert_type'] == ALERT_CRASH_DETECTED
        assert abs(decoded['latitude'] - 43.7044) < 0.001
        assert abs(decoded['longitude'] - (-72.2887)) < 0.001
        assert abs(decoded['peak_g'] - 5.23) < 0.01
        assert decoded['tilt'] == 78
        assert decoded['timestamp'] == ts
        assert decoded['battery'] == 85

    def test_roundtrip_crash_cancelled(self):
        payload = self._encode_crash_alert(
            ALERT_CRASH_CANCELLED, 0.0, 0.0, 3.0, 45, 1000000, 50
        )
        decoded = self._decode_crash_alert(payload)
        assert decoded['alert_type'] == ALERT_CRASH_CANCELLED

    def test_roundtrip_crash_confirmed(self):
        payload = self._encode_crash_alert(
            ALERT_CRASH_CONFIRMED, 43.7, -72.3, 8.5, 90, 2000000, 30
        )
        decoded = self._decode_crash_alert(payload)
        assert decoded['alert_type'] == ALERT_CRASH_CONFIRMED
        assert decoded['tilt'] == 90
        assert decoded['battery'] == 30

    def test_zero_gps_coordinates(self):
        payload = self._encode_crash_alert(
            ALERT_CRASH_DETECTED, 0.0, 0.0, 5.0, 80, 1000000, 100
        )
        decoded = self._decode_crash_alert(payload)
        assert decoded['latitude'] == 0.0
        assert decoded['longitude'] == 0.0

    def test_battery_clamped_to_100(self):
        payload = self._encode_crash_alert(
            ALERT_CRASH_DETECTED, 0.0, 0.0, 5.0, 80, 1000000, 150
        )
        decoded = self._decode_crash_alert(payload)
        assert decoded['battery'] == 100

    def test_tilt_clamped_to_180(self):
        payload = self._encode_crash_alert(
            ALERT_CRASH_DETECTED, 0.0, 0.0, 5.0, 200, 1000000, 50
        )
        decoded = self._decode_crash_alert(payload)
        assert decoded['tilt'] == 180


class TestDeviceStatusPayload:
    """Test the 5-byte device status payload format."""

    def _encode_device_status(self, state, battery, gps_fix, uptime_min):
        return struct.pack('<BBBH',
            state,
            int(max(0, min(100, battery))),
            1 if gps_fix else 0,
            int(min(uptime_min, 65535))
        )

    def _decode_device_status(self, data):
        state = data[0]
        battery = data[1]
        gps_fix = data[2] == 0x01
        uptime = struct.unpack_from('<H', data, 3)[0]
        return {
            'state': state,
            'battery': battery,
            'gps_fix': gps_fix,
            'uptime_minutes': uptime,
        }

    def test_payload_is_5_bytes(self):
        payload = self._encode_device_status(DEVICE_MONITORING, 80, False, 45)
        assert len(payload) == 5

    def test_roundtrip_monitoring_state(self):
        payload = self._encode_device_status(DEVICE_MONITORING, 80, False, 45)
        decoded = self._decode_device_status(payload)
        assert decoded['state'] == DEVICE_MONITORING
        assert decoded['battery'] == 80
        assert decoded['gps_fix'] is False
        assert decoded['uptime_minutes'] == 45

    def test_roundtrip_booting_state(self):
        payload = self._encode_device_status(DEVICE_BOOTING, 100, False, 0)
        decoded = self._decode_device_status(payload)
        assert decoded['state'] == DEVICE_BOOTING
        assert decoded['uptime_minutes'] == 0

    def test_roundtrip_low_battery_state(self):
        payload = self._encode_device_status(DEVICE_LOW_BATTERY, 8, True, 120)
        decoded = self._decode_device_status(payload)
        assert decoded['state'] == DEVICE_LOW_BATTERY
        assert decoded['battery'] == 8
        assert decoded['gps_fix'] is True
        assert decoded['uptime_minutes'] == 120

    def test_uptime_max_65535(self):
        payload = self._encode_device_status(DEVICE_MONITORING, 50, False, 70000)
        decoded = self._decode_device_status(payload)
        assert decoded['uptime_minutes'] == 65535


class TestGracePeriodPayload:
    """Test the 2-byte grace period payload format."""

    def test_countdown_payload(self):
        payload = bytes([GRACE_COUNTDOWN, 25])
        assert payload[0] == GRACE_COUNTDOWN
        assert payload[1] == 25

    def test_idle_payload(self):
        payload = bytes([GRACE_IDLE, 0])
        assert payload[0] == GRACE_IDLE
        assert payload[1] == 0

    def test_cancelled_button_payload(self):
        payload = bytes([GRACE_CANCELLED_BUTTON, 0])
        assert payload[0] == GRACE_CANCELLED_BUTTON

    def test_cancelled_app_payload(self):
        payload = bytes([GRACE_CANCELLED_APP, 0])
        assert payload[0] == GRACE_CANCELLED_APP
