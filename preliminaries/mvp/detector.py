"""
detector.py -- Two-stage crash detection algorithm for BikeBox.

Detection strategy (reduces false positives from bumps / potholes):

  Stage 1 — IMPACT: acceleration magnitude exceeds IMPACT_THRESHOLD.
  Stage 2 — TILT:   after a CONFIRM_WINDOW settling period, the device's
            tilt from vertical exceeds TILT_THRESHOLD continuously for
            SUSTAINED_TILT_TIME seconds.

Both stages must pass to confirm a crash. A COOLDOWN_TIME lockout
prevents rapid re-triggers after a confirmed event.

Usage:
    from imu import IMU
    from detector import CrashDetector

    sensor = IMU()
    detector = CrashDetector(sensor, on_crash=my_callback)
    detector.run()
"""

import math
import time
from collections import deque
from typing import Callable, Deque, Dict, List, Optional, Tuple

from imu import IMU

# ---------------------------------------------------------------------------
# Tunable detection parameters
# ---------------------------------------------------------------------------
IMPACT_THRESHOLD    = 4.0    # g — stage 1 trigger (normal riding ≈ 1g, crash ≈ 4–10g+)
TILT_THRESHOLD      = 30.0   # degrees from vertical — stage 2 trigger
CONFIRM_WINDOW      = 0.5    # seconds — settle time after impact before tilt check
SUSTAINED_TILT_TIME = 1.0    # seconds — tilt must persist continuously
COOLDOWN_TIME       = 30.0   # seconds — lockout between crash events
POLL_RATE           = 0.01   # seconds — main-loop period (100 Hz)

# History buffer — ~5 seconds at 100 Hz
HISTORY_MAXLEN = 500


class CrashDetector:
    """Monitors IMU data and fires a callback on confirmed crashes.

    Attributes:
        imu: IMU driver instance.
        on_crash: Optional callback ``(peak_g, tilt_angle, timestamp) -> None``.
        running: Set to False to stop the detection loop.
        last_crash_time: Timestamp of the most recent confirmed crash.
        history: Ring buffer of recent IMU readings (dicts).
    """

    def __init__(
        self,
        imu: IMU,
        on_crash: Optional[Callable[[float, float, float], None]] = None,
    ) -> None:
        self.imu = imu
        self.on_crash = on_crash
        self.running: bool = False
        self.last_crash_time: float = 0.0
        self.history: Deque[Dict[str, float]] = deque(maxlen=HISTORY_MAXLEN)

    # ------------------------------------------------------------------
    # Tilt computation
    # ------------------------------------------------------------------

    @staticmethod
    def compute_tilt_from_accel(ax: float, ay: float, az: float) -> float:
        """Return tilt angle (degrees) from vertical given accel readings.

        Uses ``acos(az / magnitude)`` with input clamped to [-1, 1].
        Free-fall (magnitude ≈ 0) returns 90°.
        """
        mag = math.sqrt(ax * ax + ay * ay + az * az)
        if mag < 0.1:
            return 90.0
        cos_angle = max(-1.0, min(1.0, az / mag))
        return math.degrees(math.acos(cos_angle))

    def compute_tilt(self) -> float:
        """Read accelerometer and return current tilt from vertical."""
        ax, ay, az = self.imu.read_accel_g()
        return self.compute_tilt_from_accel(ax, ay, az)

    # ------------------------------------------------------------------
    # Stage 2: sustained tilt verification
    # ------------------------------------------------------------------

    def check_sustained_tilt(self) -> Tuple[bool, float]:
        """Poll tilt for SUSTAINED_TILT_TIME seconds.

        Returns:
            (sustained, last_tilt) — *sustained* is True only if tilt
            stayed above TILT_THRESHOLD for the entire window.
        """
        start = time.time()
        tilt = 0.0
        while (time.time() - start) < SUSTAINED_TILT_TIME:
            tilt = self.compute_tilt()
            if tilt < TILT_THRESHOLD:
                return False, tilt
            time.sleep(0.1)
        return True, tilt

    # ------------------------------------------------------------------
    # Main detection loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Run the detection loop until *self.running* is set False or Ctrl+C."""
        self.running = True
        print(
            f"Detector active: impact={IMPACT_THRESHOLD}g, "
            f"tilt={TILT_THRESHOLD}°, "
            f"cooldown={COOLDOWN_TIME}s"
        )
        print("Monitoring... (Ctrl+C to stop)\n")

        try:
            while self.running:
                ax, ay, az = self.imu.read_accel_g()
                mag = math.sqrt(ax * ax + ay * ay + az * az)
                ts = time.time()

                self.history.append(
                    {"time": ts, "ax": ax, "ay": ay, "az": az, "mag": mag}
                )

                if mag > IMPACT_THRESHOLD:
                    if (ts - self.last_crash_time) < COOLDOWN_TIME:
                        time.sleep(POLL_RATE)
                        continue

                    peak_g = mag
                    print(f"⚠  IMPACT: {peak_g:.2f}g at {time.strftime('%H:%M:%S')}")

                    time.sleep(CONFIRM_WINDOW)

                    tilt = self.compute_tilt()
                    print(f"   Tilt: {tilt:.1f}°")

                    if tilt > TILT_THRESHOLD:
                        sustained, final_tilt = self.check_sustained_tilt()
                        if sustained:
                            self.last_crash_time = time.time()
                            print(
                                f"🚨 CRASH CONFIRMED: "
                                f"{peak_g:.2f}g, tilt {final_tilt:.1f}°"
                            )
                            if self.on_crash:
                                self.on_crash(peak_g, final_tilt, ts)
                        else:
                            print("   Bike righted — false alarm.")
                    else:
                        print("   Upright — bump, not crash.")

                time.sleep(POLL_RATE)

        except KeyboardInterrupt:
            print("\nDetector stopped.")
        finally:
            self.running = False
