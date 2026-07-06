"""
main.py — BikeBox system entry point.

Initializes all subsystems and runs the crash detection loop.

Usage:
    python3 main.py                 # Normal operation (calibrate + detect)
    python3 main.py --test-imu      # Live IMU readout
    python3 main.py --test-battery  # Show battery status
    python3 main.py --test-ble      # Start BLE server only
    python3 main.py --log FILE.csv  # Detect + log IMU data to CSV
    python3 main.py --no-camera     # Run without camera
    python3 main.py --no-ble        # Run without BLE
"""

import sys
import os
import signal
import time
import csv
import argparse
import threading
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

from config import (
    DEVICE_BOOTING, DEVICE_MONITORING, DEVICE_LOW_BATTERY,
    BLE_HEARTBEAT_INTERVAL, LOG_CSV_COLUMNS, LOG_DIR,
    BUTTON_ENABLED, BUTTON_PIN, BUTTON_LED_PIN, SHORT_PRESS_MAX, LONG_HOLD_MIN,
    BUTTON_DEBOUNCE_MS, IMPACT_THRESHOLD, GYRO_THRESHOLD,
    GYRO_ACCEL_MIN, TILT_THRESHOLD, POLL_RATE
)
from imu import IMU
from detector import CrashDetector
import alert


# Global button state -- read by the status banner and alert.py
_button_status = "Not initialized"
_button_press_count = 0
_button_press_lock = threading.Lock()


def get_button_status():
    return _button_status


def get_button_press_count():
    with _button_press_lock:
        return _button_press_count


def _log_button_event(event_type, duration=None):
    """Log a button event with timestamp to stdout (captured by journalctl)."""
    global _button_press_count
    ts = time.strftime('%H:%M:%S')
    dur_str = f" ({duration:.2f}s)" if duration is not None else ""
    in_grace = alert.is_alert_active()
    context = "GRACE PERIOD" if in_grace else "ACCIDENTAL (no active alert)"

    with _button_press_lock:
        _button_press_count += 1
        count = _button_press_count

    print(f"BUTTON [{ts}] #{count}: {event_type}{dur_str} — {context}")


def parse_args():
    parser = argparse.ArgumentParser(description='BikeBox Crash Detection System')
    parser.add_argument('--test-imu', action='store_true', help='Live IMU readout')
    parser.add_argument('--test-battery', action='store_true', help='Battery status')
    parser.add_argument('--test-ble', action='store_true', help='BLE server test')
    parser.add_argument('--log', type=str, metavar='FILE', help='Log IMU data to CSV')
    parser.add_argument('--no-camera', action='store_true', help='Disable camera')
    parser.add_argument('--no-ble', action='store_true', help='Disable BLE')
    return parser.parse_args()


def test_imu():
    """Print live accelerometer + gyro data."""
    sensor = IMU()
    sensor.calibrate()
    print("\nLive IMU (Ctrl+C to stop):\n")
    try:
        while True:
            ax, ay, az = sensor.read_accel_g()
            mag = sensor.accel_magnitude()
            gyro = sensor.gyro_magnitude()
            print(f"  X={ax:+.3f}g  Y={ay:+.3f}g  Z={az:+.3f}g  "
                  f"Mag={mag:.3f}g  Gyro={gyro:.1f}dps", end='\r')
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n")
    finally:
        sensor.close()


def test_battery():
    """Show battery status."""
    from battery import BatteryMonitor
    mon = BatteryMonitor()
    mon.start()
    time.sleep(2)
    state = mon.get_state()
    print(f"Battery: {state['percentage']}%  "
          f"Charging: {'Yes' if state['charging'] else 'No'}")
    mon.stop()


def test_ble():
    """Start BLE server and wait."""
    from ble_server import BLEServer
    server = BLEServer()
    server.start()
    print("BLE server running. Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        print("\n")


def _start_button_listener():
    """
    Start button monitoring. Uses a polling thread that reads GPIO.input()
    directly — this works reliably on Bookworm without requiring the sysfs
    overlay that GPIO.add_event_detect() needs.

    Also attempts to register edge detection as an optimization.
    If edge detection fails, the polling thread handles everything.
    """
    global _button_status

    if not BUTTON_ENABLED:
        _button_status = "Disabled (BUTTON_ENABLED=False)"
        print(f"Button listener: {_button_status}")
        return

    if not GPIO_AVAILABLE:
        _button_status = "Unavailable (RPi.GPIO not installed)"
        print(f"Button listener: {_button_status}")
        return

    # Verify the pin is actually readable
    try:
        initial_state = GPIO.input(BUTTON_PIN)
        pin_label = "HIGH (released)" if initial_state == GPIO.HIGH else "LOW (pressed)"
        print(f"Button listener: pin BCM{BUTTON_PIN} reads {pin_label}")
    except Exception as e:
        _button_status = f"Error reading pin ({e})"
        print(f"Button listener: {_button_status}")
        return

    # Try edge detection first (faster, uses less CPU)
    edge_ok = False
    try:
        GPIO.add_event_detect(
            BUTTON_PIN, GPIO.BOTH,
            callback=lambda ch: None,
            bouncetime=BUTTON_DEBOUNCE_MS
        )
        GPIO.remove_event_detect(BUTTON_PIN)
        edge_ok = True
    except RuntimeError:
        edge_ok = False

    if edge_ok:
        _button_status = f"Active (edge detection, BCM{BUTTON_PIN})"
        _start_edge_listener()
    else:
        _button_status = f"Active (polling, BCM{BUTTON_PIN})"
        _start_polling_listener()

    print(f"Button listener: {_button_status}")


def _start_edge_listener():
    """Use GPIO edge detection for button events."""
    press_time = [None]

    def _on_edge(channel):
        if GPIO.input(BUTTON_PIN) == GPIO.LOW:
            press_time[0] = time.time()
            _log_button_event("press_start")
        else:
            if press_time[0] is None:
                return
            duration = time.time() - press_time[0]
            press_time[0] = None
            _handle_release(duration)

    GPIO.add_event_detect(
        BUTTON_PIN, GPIO.BOTH,
        callback=_on_edge, bouncetime=BUTTON_DEBOUNCE_MS
    )


def _start_polling_listener():
    """Fallback: poll the button pin in a background thread."""
    def _poll_loop():
        last_state = GPIO.HIGH
        press_time = None
        debounce_end = 0

        while True:
            try:
                current = GPIO.input(BUTTON_PIN)
            except Exception:
                time.sleep(1)
                continue

            now = time.time()
            if now < debounce_end:
                time.sleep(0.02)
                continue

            if current == GPIO.LOW and last_state == GPIO.HIGH:
                press_time = now
                debounce_end = now + (BUTTON_DEBOUNCE_MS / 1000.0)
                _log_button_event("press_start")

            elif current == GPIO.HIGH and last_state == GPIO.LOW:
                if press_time is not None:
                    duration = now - press_time
                    debounce_end = now + (BUTTON_DEBOUNCE_MS / 1000.0)
                    press_time = None
                    _handle_release(duration)

            last_state = current
            time.sleep(0.02)

    t = threading.Thread(target=_poll_loop, daemon=True, name='button-poll')
    t.start()


def _handle_release(duration):
    """Process a button release after a measured press duration."""
    if duration <= SHORT_PRESS_MAX:
        _log_button_event("short_press (shutdown)", duration)
        if not alert.is_alert_active():
            print(f"Short press ({duration:.1f}s) — initiating safe shutdown...")
            try:
                GPIO.output(BUTTON_LED_PIN, GPIO.LOW)
            except Exception:
                pass
            subprocess.call(['sudo', 'shutdown', '-h', 'now'])
        else:
            _log_button_event("short_press IGNORED (alert active)", duration)
    elif duration >= LONG_HOLD_MIN:
        _log_button_event("long_hold", duration)
    else:
        _log_button_event("medium_press (no action)", duration)


def main():
    args = parse_args()

    if args.test_imu:
        test_imu()
        return
    if args.test_battery:
        test_battery()
        return
    if args.test_ble:
        test_ble()
        return

    print("\n" + "=" * 60)
    print("  BikeBox — Bicycle Crash Detection System")
    print("  Dartmouth ENGS 21 | Team 1")
    print("=" * 60 + "\n")

    boot_time = time.time()
    ble_server = None
    camera_manager = None
    battery_monitor = None
    clip_server = None
    hotspot_manager = None
    csv_writer = None
    csv_file = None

    try:
        # 1. GPIO Setup
        print("[1/8] Initializing GPIO...")
        alert.setup_gpio()
        _start_button_listener()

        # 2. IMU
        print("[2/8] Initializing IMU...")
        sensor = IMU()
        sensor.calibrate()

        # 3. Camera
        if not args.no_camera:
            print("[3/8] Starting camera...")
            from camera import CameraManager
            camera_manager = CameraManager()
            camera_manager.start()
        else:
            print("[3/8] Camera disabled (--no-camera)")

        # 4. Battery Monitor
        print("[4/8] Starting battery monitor...")
        from battery import BatteryMonitor
        battery_monitor = BatteryMonitor()

        def on_low_battery(pct):
            print(f"LOW BATTERY: {pct}%")
            if ble_server:
                ble_server.send_device_status(
                    DEVICE_LOW_BATTERY, pct,
                    False,
                    int((time.time() - boot_time) / 60)
                )

        battery_monitor.start(
            on_low_battery=on_low_battery,
            on_critical_battery=on_low_battery
        )

        # 5. BLE Server
        if not args.no_ble:
            print("[5/8] Starting BLE server...")
            from ble_server import BLEServer
            ble_server = BLEServer()
            ble_server.start()
            time.sleep(1)
        else:
            print("[5/8] BLE disabled (--no-ble, LED-only mode)")

        # 6. Wire subsystems into alert.py
        print("[6/8] Connecting subsystems...")
        alert.set_subsystems(
            ble_server=ble_server,
            camera_manager=camera_manager,
            battery_monitor=battery_monitor
        )

        # 7. Clip Server + On-Demand Hotspot
        if not args.no_camera:
            print("[7/8] Starting clip server + hotspot manager...")
            from clip_server import ClipServer
            from hotspot import HotspotManager

            def _on_hotspot_state_change(state):
                if ble_server:
                    ble_server.send_hotspot_state(state)

            hotspot_manager = HotspotManager(on_state_change=_on_hotspot_state_change)

            def _on_hotspot_ble_command(command):
                if command == 0x01:
                    threading.Thread(
                        target=hotspot_manager.activate, daemon=True,
                        name='hotspot-activate'
                    ).start()
                elif command == 0x00:
                    threading.Thread(
                        target=hotspot_manager.deactivate, daemon=True,
                        name='hotspot-deactivate'
                    ).start()

            if ble_server:
                ble_server.set_hotspot_callback(_on_hotspot_ble_command)

            clip_server = ClipServer()
            ClipServer.on_download_activity = hotspot_manager.reset_timeout
            clip_server.start()
        else:
            print("[7/8] Clip server disabled (camera off)")

        # CSV Logging
        if args.log:
            log_path = args.log
            if not os.path.isabs(log_path):
                os.makedirs(LOG_DIR, exist_ok=True)
                log_path = os.path.join(LOG_DIR, log_path)
            csv_file = open(log_path, 'w', newline='')
            csv_writer = csv.DictWriter(csv_file, fieldnames=LOG_CSV_COLUMNS)
            csv_writer.writeheader()
            print(f"Logging IMU data to: {log_path}")

        # BLE Heartbeat Thread
        def heartbeat_loop():
            while True:
                if ble_server:
                    batt = battery_monitor.get_percentage() if battery_monitor else 100
                    uptime = int((time.time() - boot_time) / 60)
                    ble_server.send_device_status(
                        DEVICE_MONITORING, batt, False, uptime
                    )
                time.sleep(BLE_HEARTBEAT_INTERVAL)

        if ble_server:
            hb_thread = threading.Thread(
                target=heartbeat_loop, daemon=True, name='ble-heartbeat'
            )
            hb_thread.start()

        # 8. System Ready
        print("[8/8] System armed.")
        print("\n" + "=" * 60)
        print("  BikeBox ARMED — All systems operational")
        batt = battery_monitor.get_percentage() if battery_monitor else '?'
        cam_status = "Recording" if (camera_manager and camera_manager.is_recording()) else "Off"
        ble_status = "Advertising" if ble_server else "Disabled"
        clip_status = "Running" if clip_server else "Off"
        hotspot_status = "On-demand" if hotspot_manager else "Off"
        btn_status = get_button_status()
        print(f"  Battery: {batt}%  |  GPS: via iPhone")
        print(f"  Camera: {cam_status}  |  BLE: {ble_status}")
        print(f"  Clip Server: {clip_status}  |  Hotspot: {hotspot_status}")
        print(f"  Button: {btn_status}")
        print("=" * 60 + "\n")

        detector = CrashDetector(sensor, on_crash=alert.on_crash)

        if csv_writer:
            detector.running = True
            print(f"Detector active: impact={IMPACT_THRESHOLD}g, "
                  f"gyro={GYRO_THRESHOLD}dps (min {GYRO_ACCEL_MIN}g), "
                  f"tilt={TILT_THRESHOLD}deg")
            print("Monitoring with CSV logging... (Ctrl+C to stop)\n")

            try:
                while detector.running:
                    mag = sensor.accel_magnitude()
                    gyro_mag = sensor.gyro_magnitude()
                    ts = time.time()
                    ax, ay, az = sensor.read_accel_g()

                    event = ''
                    path_a = mag > IMPACT_THRESHOLD
                    path_b = gyro_mag > GYRO_THRESHOLD and mag > GYRO_ACCEL_MIN
                    if path_a or path_b:
                        event = 'impact' if path_a else 'gyro_trigger'

                    csv_writer.writerow({
                        'timestamp': f'{ts:.3f}',
                        'ax': f'{ax:.4f}',
                        'ay': f'{ay:.4f}',
                        'az': f'{az:.4f}',
                        'magnitude': f'{mag:.4f}',
                        'gyro': f'{gyro_mag:.1f}',
                        'event': event,
                    })

                    detector.history.append({
                        'time': ts, 'ax': ax, 'ay': ay,
                        'az': az, 'mag': mag, 'gyro': gyro_mag
                    })

                    time.sleep(POLL_RATE)

            except KeyboardInterrupt:
                print("\nDetector stopped.")
            finally:
                detector.running = False
        else:
            detector.run()

    except KeyboardInterrupt:
        print("\n\nShutdown requested...")

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nShutting down subsystems...")
        if hotspot_manager and hotspot_manager.is_active:
            hotspot_manager.deactivate()
        if clip_server:
            clip_server.stop()
        if camera_manager:
            camera_manager.stop()
        if battery_monitor:
            battery_monitor.stop()
        if ble_server:
            ble_server.stop()
        if csv_file:
            csv_file.close()
            print(f"CSV log saved.")
        alert.cleanup()
        print("BikeBox shutdown complete.\n")


if __name__ == '__main__':
    main()
