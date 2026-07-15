"""Shared pytest configuration and fixtures for BikeBox tests.

All hardware dependencies (smbus2, RPi.GPIO, picamera2, dbus) are
mocked so tests run on any machine without Pi hardware.
"""

import sys
import os
import types
from unittest.mock import MagicMock, patch

# Ensure the pi source directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Mock hardware modules before any BikeBox imports ───

def _create_mock_smbus2():
    """Create a mock smbus2 module with SMBus class."""
    mod = types.ModuleType("smbus2")
    mock_bus = MagicMock()
    mock_bus.read_byte_data.return_value = 0x68  # WHO_AM_I
    mock_bus.read_i2c_block_data.return_value = [0, 0, 0, 0, 0x08, 0x00]
    mod.SMBus = MagicMock(return_value=mock_bus)
    return mod


def _create_mock_gpio():
    """Create a mock RPi.GPIO module."""
    mod = types.ModuleType("RPi")
    gpio = types.ModuleType("RPi.GPIO")
    gpio.BCM = 11
    gpio.OUT = 0
    gpio.IN = 1
    gpio.HIGH = 1
    gpio.LOW = 0
    gpio.PUD_UP = 22
    gpio.BOTH = 33
    gpio.setmode = MagicMock()
    gpio.setwarnings = MagicMock()
    gpio.setup = MagicMock()
    gpio.output = MagicMock()
    gpio.input = MagicMock(return_value=1)  # Button not pressed
    gpio.cleanup = MagicMock()
    gpio.add_event_detect = MagicMock()
    mod.GPIO = gpio
    return mod, gpio


def _create_mock_picamera2():
    """Create a mock picamera2 module."""
    mod = types.ModuleType("picamera2")
    mod.Picamera2 = MagicMock()

    encoders = types.ModuleType("picamera2.encoders")
    encoders.H264Encoder = MagicMock()

    outputs = types.ModuleType("picamera2.outputs")
    outputs.CircularOutput = MagicMock()

    return mod, encoders, outputs


# Install mocks before imports
_smbus2_mock = _create_mock_smbus2()
_rpi_mock, _gpio_mock = _create_mock_gpio()
_picam_mock, _encoders_mock, _outputs_mock = _create_mock_picamera2()

sys.modules["smbus2"] = _smbus2_mock
sys.modules["RPi"] = _rpi_mock
sys.modules["RPi.GPIO"] = _gpio_mock
sys.modules["picamera2"] = _picam_mock
sys.modules["picamera2.encoders"] = _encoders_mock
sys.modules["picamera2.outputs"] = _outputs_mock

# Mock dbus and gi (not available on macOS)
_dbus_mock = MagicMock()
_dbus_service_mock = MagicMock()
_dbus_mainloop_mock = MagicMock()
_dbus_mainloop_glib_mock = MagicMock()
_dbus_exceptions_mock = MagicMock()
_gi_mock = MagicMock()
_gi_repo_mock = MagicMock()

sys.modules["dbus"] = _dbus_mock
sys.modules["dbus.service"] = _dbus_service_mock
sys.modules["dbus.mainloop"] = _dbus_mainloop_mock
sys.modules["dbus.mainloop.glib"] = _dbus_mainloop_glib_mock
sys.modules["dbus.exceptions"] = _dbus_exceptions_mock
sys.modules["gi"] = _gi_mock
sys.modules["gi.repository"] = _gi_repo_mock
