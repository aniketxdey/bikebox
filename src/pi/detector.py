"""
detector.py — Two-stage crash detection algorithm.

Stage 1 (dual-path trigger — EITHER path fires Stage 1):
  Path A: Acceleration magnitude > IMPACT_THRESHOLD (3.0g).
          Catches hard impacts: crashes, collisions, high-speed falls.
  Path B: Angular velocity magnitude > GYRO_THRESHOLD (200°/s) AND
          acceleration magnitude > GYRO_ACCEL_MIN (2.5g).
          Catches slow-speed tipovers where g-force is low but the
          bike rotates rapidly.

Stage 2 (tilt confirmation — required for BOTH paths):
  Tilt angle > TILT_THRESHOLD (45°) sustained for SUSTAINED_TILT_TIME (2.0s).
  This rejects false positives from potholes, bumps, and hard braking —
  all of which spike g-force or vibration but leave the bike upright.
"""

import math
import time
from collections import deque
from typing import Callable, Deque, Dict, List, Optional, Tuple

from config import (
    IMPACT_THRESHOLD, GYRO_THRESHOLD, GYRO_ACCEL_MIN,
    TILT_THRESHOLD, CONFIRM_WINDOW,
    SUSTAINED_TILT_TIME, COOLDOWN_TIME, POLL_RATE
)


class CrashDetector:
    """Monitors IMU data and fires a callback on confirmed crashes."""

    def __init__(
        self,
        imu: object,
        on_crash: Optional[Callable[[float, float, float], None]] = None,
    ) -> None:
        self.imu = imu
        self.on_crash = on_crash
        self.running: bool = False
        self.last_crash_time: float = 0.0
        self.history: Deque[Dict[str, float]] = deque(maxlen=500)

    @staticmethod
    def compute_tilt_from_accel(ax: float, ay: float, az: float) -> float:
        """Return tilt angle (degrees) from vertical given accel readings.

        Uses atan2(horizontal, |az|). Free-fall (magnitude ≈ 0) returns 90°.
        """
        horizontal = math.sqrt(ax ** 2 + ay ** 2)
        if horizontal < 1e-6 and abs(az) < 1e-6:
            return 90.0
        return math.degrees(math.atan2(horizontal, abs(az)))

    def compute_tilt(self) -> float:
        """Read accelerometer and return current tilt from vertical."""
        ax, ay, az = self.imu.read_accel_g()
        return self.compute_tilt_from_accel(ax, ay, az)

    def check_sustained_tilt(self) -> Tuple[bool, float]:
        """Verify the bike remains tilted above threshold for the required duration."""
        start = time.time()
        tilt = 0.0
        while (time.time() - start) < SUSTAINED_TILT_TIME:
            tilt = self.compute_tilt()
            if tilt < TILT_THRESHOLD:
                return False, tilt
            time.sleep(0.1)
        return True, tilt

    def run(self) -> None:
        """Main detection loop. Runs until self.running = False or Ctrl+C."""
        self.running = True
        print(f"Detector active: impact={IMPACT_THRESHOLD}g, "
              f"gyro={GYRO_THRESHOLD}°/s (min {GYRO_ACCEL_MIN}g), "
              f"tilt={TILT_THRESHOLD}°, cooldown={COOLDOWN_TIME}s")
        print("Monitoring... (Ctrl+C to stop)\n")

        try:
            while self.running:
                mag = self.imu.accel_magnitude()
                gyro_mag = self.imu.gyro_magnitude()
                ts = time.time()
                ax, ay, az = self.imu.read_accel_g()
                self.history.append({
                    'time': ts, 'ax': ax, 'ay': ay, 'az': az,
                    'mag': mag, 'gyro': gyro_mag
                })

                path_a = mag > IMPACT_THRESHOLD
                path_b = gyro_mag > GYRO_THRESHOLD and mag > GYRO_ACCEL_MIN
                triggered = path_a or path_b

                if triggered:
                    if (ts - self.last_crash_time) < COOLDOWN_TIME:
                        time.sleep(POLL_RATE)
                        continue

                    peak_g = mag
                    trigger_reason = (
                        f"accel {peak_g:.2f}g" if path_a
                        else f"gyro {gyro_mag:.0f}°/s + accel {peak_g:.2f}g"
                    )
                    print(f"⚠  STAGE 1: {trigger_reason} at "
                          f"{time.strftime('%H:%M:%S')}")

                    time.sleep(CONFIRM_WINDOW)

                    tilt = self.compute_tilt()
                    print(f"   Tilt: {tilt:.1f}°")

                    if tilt > TILT_THRESHOLD:
                        sustained, final_tilt = self.check_sustained_tilt()
                        if sustained:
                            print(f"CRASH CONFIRMED: {trigger_reason}, "
                                  f"tilt {final_tilt:.1f}°")
                            if self.on_crash:
                                self.on_crash(peak_g, final_tilt, ts)
                            self.last_crash_time = time.time()
                        else:
                            print(f"   Bike righted — false alarm.")
                    else:
                        print(f"   Tilt {tilt:.1f}° < {TILT_THRESHOLD}° "
                              f"threshold. Bump, not crash.")

                time.sleep(POLL_RATE)

        except KeyboardInterrupt:
            print("\nDetector stopped by user.")
        finally:
            self.running = False

    def get_history(self) -> List[Dict[str, float]]:
        """Return the recorded history buffer as a list of dicts."""
        return list(self.history)
