"""
alert.py — Full crash alert pipeline for BikeBox.

When on_crash() is called by detector.py, this module:
1. Reads battery level from battery.py
2. Triggers camera clip save from camera.py
3. Sends a crash alert via BLE to the iOS app (GPS coordinates are 0,0 —
   the iOS app substitutes its own CoreLocation data)
4. Starts the grace period countdown (30 seconds)
5. During countdown: monitors blue button long hold (GPIO 26, >=3s) and BLE cancel writes
6. If cancelled: sends cancel notification, stops alert
7. If countdown expires: sends confirmed notification for emergency dispatch

The on_crash() function signature remains: on_crash(peak_g, tilt_angle, timestamp)
"""

import time
import threading
from typing import Optional

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

from config import (
    BUTTON_ENABLED, BUTTON_PIN, BUTTON_LED_PIN, LONG_HOLD_MIN,
    GRACE_PERIOD_SECONDS, GRACE_POLL_INTERVAL,
    ALERT_CRASH_DETECTED, ALERT_CRASH_CANCELLED, ALERT_CRASH_CONFIRMED,
    GRACE_IDLE, GRACE_COUNTDOWN, GRACE_CANCELLED_BUTTON, GRACE_CANCELLED_APP,
    DEVICE_MONITORING, DEVICE_GRACE_PERIOD, DEVICE_ALERT_SENT
)

_ble_server = None
_camera_manager = None
_battery_monitor = None
_cancel_from_app = False
_alert_active = False


def is_alert_active() -> bool:
    """Return True if a crash alert grace period is currently in progress."""
    return _alert_active


def setup_gpio() -> None:
    """Initialize GPIO pins for button LED and blue multi-function button."""
    if not GPIO_AVAILABLE:
        print("GPIO: RPi.GPIO not available. GPIO functions disabled.")
        return

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    if BUTTON_ENABLED:
        GPIO.setup(BUTTON_LED_PIN, GPIO.OUT)
        GPIO.output(BUTTON_LED_PIN, GPIO.HIGH)
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        print(f"GPIO ready. Button=BCM{BUTTON_PIN}, ButtonLED=BCM{BUTTON_LED_PIN}")
    else:
        print("GPIO ready. Button disabled (set BUTTON_ENABLED=True in config.py to enable)")


def set_subsystems(ble_server=None, camera_manager=None, battery_monitor=None) -> None:
    """Register subsystem references. Called by main.py after initialization."""
    global _ble_server, _camera_manager, _battery_monitor
    _ble_server = ble_server
    _camera_manager = camera_manager
    _battery_monitor = battery_monitor

    if _ble_server:
        _ble_server.set_cancel_callback(_on_cancel_from_app)


def _on_cancel_from_app() -> None:
    """Called when the iOS app writes a cancel command via BLE."""
    global _cancel_from_app
    _cancel_from_app = True
    ts = time.strftime('%H:%M:%S')
    print(f"ALERT [{ts}]: Cancel received from iOS app")


def _check_button_held() -> bool:
    """Check if the blue button is currently held down."""
    if not BUTTON_ENABLED or not GPIO_AVAILABLE:
        return False
    try:
        return GPIO.input(BUTTON_PIN) == GPIO.LOW
    except Exception:
        return False


def on_crash(peak_g: float, tilt_angle: float, timestamp: float) -> None:
    """
    Main crash alert handler. Called by CrashDetector.

    This is the central orchestration point for the entire alert pipeline.
    """
    global _cancel_from_app, _alert_active

    if _alert_active:
        print("ALERT: Already processing a crash alert. Ignoring.")
        return

    _alert_active = True
    _cancel_from_app = False

    time_str = time.strftime('%H:%M:%S', time.localtime(timestamp))
    print(f"\n{'=' * 60}")
    print(f"CRASH ALERT at {time_str}")
    print(f"   Peak: {peak_g:.2f}g | Tilt: {tilt_angle:.1f}")
    print(f"{'=' * 60}")

    lat, lon = 0.0, 0.0
    print(f"   GPS: provided by iPhone (Pi sends 0.0, 0.0)")

    battery_pct = 100
    if _battery_monitor:
        battery_pct = _battery_monitor.get_percentage()
        print(f"   Battery: {battery_pct}%")

    clip_thread = None
    if _camera_manager and _camera_manager.is_recording():
        clip_thread = threading.Thread(
            target=_camera_manager.save_clip,
            args=(timestamp,),
            daemon=True
        )
        clip_thread.start()
        print("   Camera: saving crash clip...")

    clip_available = 1 if (_camera_manager and _camera_manager.is_recording()) else 0

    if _ble_server:
        _ble_server.send_grace_period(GRACE_IDLE, 0)
        _ble_server.send_device_status(
            DEVICE_GRACE_PERIOD, battery_pct, False,
            0
        )
        _ble_server.send_crash_alert(
            ALERT_CRASH_DETECTED,
            lat, lon, peak_g, tilt_angle, timestamp, battery_pct,
            clip_available=clip_available
        )
        time.sleep(0.5)

    print(f"\n   Grace period: {GRACE_PERIOD_SECONDS}s countdown started")

    # Flash the button LED rapidly to indicate grace period
    if BUTTON_ENABLED and GPIO_AVAILABLE:
        print(f"   Hold blue button >={LONG_HOLD_MIN:.0f}s or use app to dismiss")
        print(f"   Button LED flashing — awaiting input\n")
    else:
        print(f"   Use iOS app to dismiss\n")

    cancelled = False
    cancel_source = GRACE_CANCELLED_BUTTON
    button_held_since: Optional[float] = None
    button_check_count = 0

    for seconds_left in range(GRACE_PERIOD_SECONDS, 0, -1):
        if _ble_server:
            _ble_server.send_grace_period(GRACE_COUNTDOWN, seconds_left)

        # Flash button LED during grace period (on/off each second)
        if BUTTON_ENABLED and GPIO_AVAILABLE:
            try:
                GPIO.output(BUTTON_LED_PIN, GPIO.HIGH if seconds_left % 2 == 0 else GPIO.LOW)
            except Exception:
                pass

        print(f"   {seconds_left}s remaining...", end='\r')

        check_start = time.time()
        while (time.time() - check_start) < 1.0:
            is_held = _check_button_held()
            button_check_count += 1

            if is_held:
                if button_held_since is None:
                    button_held_since = time.time()
                    ts = time.strftime('%H:%M:%S')
                    print(f"\n   BUTTON [{ts}]: press detected during grace period at {seconds_left}s")
                else:
                    hold_duration = time.time() - button_held_since
                    if hold_duration >= LONG_HOLD_MIN:
                        ts = time.strftime('%H:%M:%S')
                        print(f"\n   BUTTON [{ts}]: LONG HOLD ({hold_duration:.1f}s) — CANCELLING at {seconds_left}s")
                        cancelled = True
                        cancel_source = GRACE_CANCELLED_BUTTON
                        break
            else:
                if button_held_since is not None:
                    hold_duration = time.time() - button_held_since
                    ts = time.strftime('%H:%M:%S')
                    print(f"   BUTTON [{ts}]: released after {hold_duration:.1f}s (need >={LONG_HOLD_MIN:.0f}s to cancel)")
                button_held_since = None

            if _cancel_from_app:
                ts = time.strftime('%H:%M:%S')
                print(f"\n   CANCEL [{ts}]: received from iOS app at {seconds_left}s")
                cancelled = True
                cancel_source = GRACE_CANCELLED_APP
                break

            time.sleep(GRACE_POLL_INTERVAL)

        if cancelled:
            break

    # Restore button LED to solid on
    if BUTTON_ENABLED and GPIO_AVAILABLE:
        try:
            GPIO.output(BUTTON_LED_PIN, GPIO.HIGH)
        except Exception:
            pass

    if cancelled:
        print("   Alert cancelled. Returning to monitoring.\n")
        if _ble_server:
            _ble_server.send_crash_alert(
                ALERT_CRASH_CANCELLED,
                lat, lon, peak_g, tilt_angle, timestamp, battery_pct
            )
            _ble_server.send_grace_period(cancel_source, 0)
    else:
        print(f"\n   GRACE PERIOD EXPIRED — ALERT CONFIRMED")
        print(f"   Emergency contacts will be notified via iOS app.\n")
        if _ble_server:
            _ble_server.send_crash_alert(
                ALERT_CRASH_CONFIRMED,
                lat, lon, peak_g, tilt_angle, timestamp, battery_pct
            )
            _ble_server.send_grace_period(GRACE_IDLE, 0)

    ts = time.strftime('%H:%M:%S')
    print(f"   ALERT [{ts}]: Grace period ended. Button polled {button_check_count} times.")
    _alert_active = False


def cleanup() -> None:
    """Clean up GPIO on program exit."""
    if not GPIO_AVAILABLE:
        return
    try:
        if BUTTON_ENABLED:
            GPIO.output(BUTTON_LED_PIN, GPIO.LOW)
        GPIO.cleanup()
    except Exception:
        pass
