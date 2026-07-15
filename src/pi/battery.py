"""
battery.py — PiSugar 3 battery monitor for BikeBox.

Reads battery percentage from I2C register 0x2A at address 0x57.
Checks charging status from bit 7 of register 0x02.
"""

import threading
import time
from typing import Callable, Dict, Optional

import smbus2

from config import (
    PISUGAR_ADDR, I2C_BUS,
    PISUGAR_BATTERY_REGISTER, PISUGAR_CHARGING_REGISTER,
    BATTERY_LOW_THRESHOLD, BATTERY_CRITICAL_THRESHOLD,
    BATTERY_CHECK_INTERVAL
)


class BatteryMonitor:
    """Reads PiSugar 3 battery state over I2C."""

    def __init__(self) -> None:
        self._bus: Optional[smbus2.SMBus] = None
        self._state: Dict[str, object] = {
            'percentage': 100,
            'charging': False,
            'last_update': 0.0,
        }
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_low_battery: Optional[Callable] = None
        self._on_critical_battery: Optional[Callable] = None
        self._low_warning_sent = False
        self._critical_warning_sent = False

    def start(
        self,
        on_low_battery: Optional[Callable] = None,
        on_critical_battery: Optional[Callable] = None,
    ) -> None:
        """Start background battery monitoring."""
        self._on_low_battery = on_low_battery
        self._on_critical_battery = on_critical_battery

        try:
            self._bus = smbus2.SMBus(I2C_BUS)
            _ = self._bus.read_byte_data(PISUGAR_ADDR, PISUGAR_BATTERY_REGISTER)
            print(f"Battery monitor started (PiSugar 3 at 0x{PISUGAR_ADDR:02X})")
        except Exception as e:
            print(f"Battery monitor: PiSugar 3 not detected at "
                  f"0x{PISUGAR_ADDR:02X}: {e}")
            print("Battery monitoring disabled. Reporting 100% as fallback.")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name='battery-monitor'
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        if self._bus:
            try:
                self._bus.close()
            except Exception:
                pass

    def get_percentage(self) -> int:
        """Return current battery percentage (0-100)."""
        with self._lock:
            return self._state['percentage']

    def is_charging(self) -> bool:
        """Return True if external power is connected."""
        with self._lock:
            return self._state['charging']

    def get_state(self) -> Dict[str, object]:
        """Return full battery state dict."""
        with self._lock:
            return dict(self._state)

    def _read_battery(self) -> int:
        """Read battery percentage from PiSugar 3 register."""
        try:
            raw = self._bus.read_byte_data(
                PISUGAR_ADDR, PISUGAR_BATTERY_REGISTER
            )
            return max(0, min(100, raw))
        except Exception:
            return -1

    def _read_charging(self) -> bool:
        """Check if external power is connected (bit 7 of register 0x02)."""
        try:
            raw = self._bus.read_byte_data(
                PISUGAR_ADDR, PISUGAR_CHARGING_REGISTER
            )
            return bool(raw & 0x80)
        except Exception:
            return False

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            pct = self._read_battery()
            charging = self._read_charging()

            if pct >= 0:
                with self._lock:
                    self._state['percentage'] = pct
                    self._state['charging'] = charging
                    self._state['last_update'] = time.time()

                if pct <= BATTERY_LOW_THRESHOLD and not self._low_warning_sent:
                    self._low_warning_sent = True
                    if self._on_low_battery:
                        self._on_low_battery(pct)

                if (pct <= BATTERY_CRITICAL_THRESHOLD
                        and not self._critical_warning_sent):
                    self._critical_warning_sent = True
                    if self._on_critical_battery:
                        self._on_critical_battery(pct)

                if pct > BATTERY_LOW_THRESHOLD + 5:
                    self._low_warning_sent = False
                    self._critical_warning_sent = False

            time.sleep(BATTERY_CHECK_INTERVAL)
