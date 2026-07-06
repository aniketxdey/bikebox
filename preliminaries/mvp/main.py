"""
main.py -- BikeBox entry point.

Modes:
    python3 main.py              Calibrate + run crash detector
    python3 main.py --test-imu   Live accelerometer readout (Ctrl+C to stop)
    python3 main.py --log FILE   Detect + log every IMU sample to CSV

CSV columns: timestamp, ax, ay, az, magnitude, event
Event values: (empty) = normal, impact = stage-1 trigger, bump = impact
without tilt, false_alarm = tilt that didn't sustain, CRASH = confirmed.
"""

import csv
import math
import signal
import sys
import time
from typing import Optional

from alert import on_crash
from detector import (
    COOLDOWN_TIME,
    CONFIRM_WINDOW,
    IMPACT_THRESHOLD,
    POLL_RATE,
    TILT_THRESHOLD,
    CrashDetector,
)
from imu import IMU


def _handle_exit(signum: int, frame: object) -> None:
    """Gracefully shut down on SIGINT / SIGTERM."""
    print("\nShutting down BikeBox...")
    sys.exit(0)


# ===================================================================
# Mode: --test-imu
# ===================================================================

def test_imu() -> None:
    """Print live accelerometer + tilt data until Ctrl+C."""
    sensor = IMU()
    sensor.calibrate()

    header = f"{'Time':>10} {'AX':>8} {'AY':>8} {'AZ':>8} {'Mag':>8} {'Tilt°':>8}"
    print(f"\n{header}")
    print("-" * len(header))

    try:
        while True:
            ax, ay, az = sensor.read_accel_g()
            mag = math.sqrt(ax * ax + ay * ay + az * az)
            tilt = CrashDetector.compute_tilt_from_accel(ax, ay, az)
            print(
                f"\r{time.strftime('%H:%M:%S'):>10} "
                f"{ax:>8.3f} {ay:>8.3f} {az:>8.3f} "
                f"{mag:>8.3f} {tilt:>8.1f}",
                end="",
                flush=True,
            )
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nDone.")
    finally:
        sensor.close()


# ===================================================================
# Mode: default / --log
# ===================================================================

def run_detector(log_file: Optional[str] = None) -> None:
    """Calibrate, arm the detector, and optionally log every sample to CSV."""
    sensor = IMU()
    sensor.calibrate()

    detector = CrashDetector(imu=sensor, on_crash=on_crash)

    csv_writer = None
    csv_fh = None
    if log_file:
        csv_fh = open(log_file, "w", newline="")
        csv_writer = csv.writer(csv_fh)
        csv_writer.writerow(["timestamp", "ax", "ay", "az", "magnitude", "event"])
        print(f"Logging to {log_file}")

    print("BikeBox armed.\n")

    try:
        detector.running = True

        while detector.running:
            ax, ay, az = sensor.read_accel_g()
            mag = math.sqrt(ax * ax + ay * ay + az * az)
            ts = time.time()
            event = ""

            detector.history.append(
                {"time": ts, "ax": ax, "ay": ay, "az": az, "mag": mag}
            )

            if mag > IMPACT_THRESHOLD and (ts - detector.last_crash_time) > COOLDOWN_TIME:
                peak_g = mag
                print(f"\n⚠  IMPACT: {peak_g:.2f}g")
                event = "impact"

                if csv_writer:
                    csv_writer.writerow([
                        f"{ts:.3f}", f"{ax:.4f}", f"{ay:.4f}",
                        f"{az:.4f}", f"{mag:.4f}", event,
                    ])

                time.sleep(CONFIRM_WINDOW)

                tilt = detector.compute_tilt()
                print(f"   Tilt: {tilt:.1f}°")

                if tilt > TILT_THRESHOLD:
                    sustained, final_tilt = detector.check_sustained_tilt()
                    if sustained:
                        detector.last_crash_time = time.time()
                        event = "CRASH"
                        print("🚨 CRASH CONFIRMED")
                        on_crash(peak_g, final_tilt, ts)
                    else:
                        event = "false_alarm"
                        print("   Righted — false alarm")
                else:
                    event = "bump"
                    print("   Upright — bump")

                if csv_writer:
                    ts_now = time.time()
                    ax2, ay2, az2 = sensor.read_accel_g()
                    mag2 = math.sqrt(ax2 * ax2 + ay2 * ay2 + az2 * az2)
                    csv_writer.writerow([
                        f"{ts_now:.3f}", f"{ax2:.4f}", f"{ay2:.4f}",
                        f"{az2:.4f}", f"{mag2:.4f}", event,
                    ])

            elif csv_writer:
                csv_writer.writerow([
                    f"{ts:.3f}", f"{ax:.4f}", f"{ay:.4f}",
                    f"{az:.4f}", f"{mag:.4f}", event,
                ])

            time.sleep(POLL_RATE)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if csv_fh:
            csv_fh.close()
            print(f"Data saved to {log_file}")
        sensor.close()


# ===================================================================
# CLI dispatch
# ===================================================================

def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate mode."""
    signal.signal(signal.SIGINT, _handle_exit)
    signal.signal(signal.SIGTERM, _handle_exit)

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--test-imu":
            test_imu()
        elif cmd == "--log" and len(sys.argv) > 2:
            run_detector(log_file=sys.argv[2])
        else:
            print(
                "Usage: python3 main.py [--test-imu | --log FILE]"
            )
            sys.exit(1)
    else:
        run_detector()


if __name__ == "__main__":
    main()
