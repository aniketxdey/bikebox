"""
hotspot.py — On-demand WiFi hotspot for BikeBox clip transfer.

Switches wlan0 between client mode (home WiFi) and AP mode (BikeBox hotspot)
at runtime. The hotspot is only activated when the iOS app requests a clip
download, and automatically deactivates after a configurable timeout or when
the iOS app signals that the transfer is complete.

Requires hostapd and dnsmasq to be installed but DISABLED at boot.
The configuration files (/etc/hostapd/hostapd.conf, /etc/dnsmasq.d/bikebox.conf)
must already exist from the initial setup.
"""

import subprocess
import threading
import time
from typing import Callable, Optional

from config import HOTSPOT_IP, HOTSPOT_TIMEOUT, HOTSPOT_OFF, HOTSPOT_ACTIVATING, HOTSPOT_ACTIVE, HOTSPOT_DEACTIVATING


class HotspotManager:
    """Manages on-demand switching between WiFi client and AP mode."""

    def __init__(self, on_state_change: Optional[Callable[[int], None]] = None) -> None:
        self._state = HOTSPOT_OFF
        self._lock = threading.Lock()
        self._timeout_timer: Optional[threading.Timer] = None
        self._on_state_change = on_state_change

    @property
    def state(self) -> int:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._state == HOTSPOT_ACTIVE

    def activate(self) -> bool:
        """Switch wlan0 from client mode to AP mode. Returns True on success."""
        with self._lock:
            if self._state in (HOTSPOT_ACTIVATING, HOTSPOT_ACTIVE):
                print("Hotspot: already active or activating")
                return self._state == HOTSPOT_ACTIVE

            self._set_state(HOTSPOT_ACTIVATING)

        success = False
        try:
            print("Hotspot: [1/4] disconnecting from home WiFi...")
            self._disconnect_client()
            print("Hotspot: [2/4] assigning static IP...")
            self._assign_static_ip()
            print("Hotspot: [3/4] starting hostapd + dnsmasq...")
            self._start_ap_services()
            print("Hotspot: [4/4] verifying AP is running...")
            success = self._verify_ap()
            if not success:
                print("Hotspot: hostapd did not reach 'active' state")
        except Exception as e:
            print(f"Hotspot: activation exception — {e}")

        with self._lock:
            if success:
                self._set_state(HOTSPOT_ACTIVE)
                self._start_timeout()
                print(f"Hotspot: ACTIVE (SSID=BikeBox, IP={HOTSPOT_IP}, timeout={HOTSPOT_TIMEOUT}s)")
            else:
                print("Hotspot: activation failed, reverting to client mode")
                self._stop_ap_services()
                self._restore_client()
                self._set_state(HOTSPOT_OFF)

        return success

    def deactivate(self) -> None:
        """Switch wlan0 back to client mode (home WiFi)."""
        with self._lock:
            if self._state == HOTSPOT_OFF:
                return
            self._cancel_timeout()
            self._set_state(HOTSPOT_DEACTIVATING)

        try:
            self._stop_ap_services()
            self._flush_ip()
            self._restore_client()
        except Exception as e:
            print(f"Hotspot: deactivation error — {e}")

        with self._lock:
            self._set_state(HOTSPOT_OFF)
        print("Hotspot: OFF — returning to home WiFi")

    def reset_timeout(self) -> None:
        """Reset the auto-deactivation timer (call when a download is in progress)."""
        with self._lock:
            if self._state == HOTSPOT_ACTIVE:
                self._cancel_timeout()
                self._start_timeout()

    # ── Internal: state management ──

    def _set_state(self, new_state: int) -> None:
        self._state = new_state
        if self._on_state_change:
            try:
                self._on_state_change(new_state)
            except Exception as e:
                print(f"Hotspot: state callback error — {e}")

    def _start_timeout(self) -> None:
        self._cancel_timeout()
        self._timeout_timer = threading.Timer(HOTSPOT_TIMEOUT, self._on_timeout)
        self._timeout_timer.daemon = True
        self._timeout_timer.start()

    def _cancel_timeout(self) -> None:
        if self._timeout_timer:
            self._timeout_timer.cancel()
            self._timeout_timer = None

    def _on_timeout(self) -> None:
        print("Hotspot: timeout reached — auto-deactivating")
        self.deactivate()

    # ── Internal: network operations ──

    def _run(self, cmd: list, timeout: int = 15) -> bool:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                stderr = result.stderr.strip() if result.stderr else ''
                print(f"Hotspot: cmd failed (rc={result.returncode}): {' '.join(cmd)}")
                if stderr:
                    print(f"  stderr: {stderr}")
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"Hotspot: cmd exception {' '.join(cmd)} — {e}")
            return False

    def _disconnect_client(self) -> None:
        """Disconnect wlan0 from any current WiFi network."""
        if self._is_networkmanager():
            self._run(['sudo', 'nmcli', 'device', 'disconnect', 'wlan0'])
            self._run(['sudo', 'nmcli', 'device', 'set', 'wlan0', 'managed', 'no'])
        else:
            self._run(['sudo', 'wpa_cli', '-i', 'wlan0', 'disconnect'])
            self._run(['sudo', 'systemctl', 'stop', 'wpa_supplicant'])

    def _assign_static_ip(self) -> None:
        """Assign the hotspot static IP to wlan0."""
        self._run(['sudo', 'ip', 'addr', 'flush', 'dev', 'wlan0'])
        self._run(['sudo', 'ip', 'addr', 'add', f'{HOTSPOT_IP}/24', 'dev', 'wlan0'])
        self._run(['sudo', 'ip', 'link', 'set', 'wlan0', 'up'])

    def _start_ap_services(self) -> None:
        """Start hostapd and dnsmasq."""
        self._run(['sudo', 'systemctl', 'start', 'hostapd'])
        self._run(['sudo', 'systemctl', 'start', 'dnsmasq'])

    def _stop_ap_services(self) -> None:
        """Stop hostapd and dnsmasq."""
        self._run(['sudo', 'systemctl', 'stop', 'hostapd'])
        self._run(['sudo', 'systemctl', 'stop', 'dnsmasq'])

    def _flush_ip(self) -> None:
        """Remove static IP from wlan0."""
        self._run(['sudo', 'ip', 'addr', 'flush', 'dev', 'wlan0'])

    def _restore_client(self) -> None:
        """Re-enable wlan0 as a WiFi client."""
        if self._is_networkmanager():
            self._run(['sudo', 'nmcli', 'device', 'set', 'wlan0', 'managed', 'yes'])
            self._run(['sudo', 'nmcli', 'device', 'connect', 'wlan0'])
        else:
            self._run(['sudo', 'systemctl', 'start', 'wpa_supplicant'])
            self._run(['sudo', 'wpa_cli', '-i', 'wlan0', 'reconnect'])

    def _verify_ap(self) -> bool:
        """Check that hostapd started successfully."""
        time.sleep(3)
        result = subprocess.run(
            ['sudo', 'systemctl', 'is-active', 'hostapd'],
            capture_output=True, text=True, timeout=5
        )
        state = result.stdout.strip()
        if state != 'active':
            print(f"Hotspot: hostapd state is '{state}', expected 'active'")
            status = subprocess.run(
                ['sudo', 'systemctl', 'status', 'hostapd', '--no-pager', '-l'],
                capture_output=True, text=True, timeout=5
            )
            for line in (status.stdout or '').splitlines()[-10:]:
                print(f"  hostapd: {line}")
        return state == 'active'

    @staticmethod
    def _is_networkmanager() -> bool:
        """Check if NetworkManager is the active network manager."""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'NetworkManager'],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() == 'active'
        except Exception:
            return False
