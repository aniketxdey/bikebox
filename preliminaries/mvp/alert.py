"""
alert.py -- Crash alert callback for BikeBox.

MVP behaviour: print a prominent crash alert to the terminal (visible
over SSH on the operator's laptop). No GPIO or LED hardware required.

The on_crash() callback signature is the single integration point for
all crash responses. Future versions will add BLE notification, a
cancel-button grace period (GPIO 27), and GPS coordinates — all by
modifying this file alone.

Usage:
    from alert import on_crash
    on_crash(peak_g=5.2, tilt_angle=78.3, timestamp=time.time())
"""

import time

# GPIO 27 reserved for future cancel button — do NOT use


def on_crash(peak_g: float, tilt_angle: float, timestamp: float) -> None:
    """Crash-alert callback invoked by CrashDetector on a confirmed crash.

    MVP: prints a clearly visible alert to stdout (seen over SSH).
    Future: will add 30-second cancel window, BLE notification, GPS payload.

    Args:
        peak_g: Peak acceleration magnitude that triggered stage 1 (g).
        tilt_angle: Final sustained tilt angle from vertical (degrees).
        timestamp: Unix timestamp of the initial impact.
    """
    t_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
    print()
    print("=" * 60)
    print("   🚨  CRASH DETECTED  🚨")
    print(f"   Time:  {t_str}")
    print(f"   Peak:  {peak_g:.2f} g")
    print(f"   Tilt:  {tilt_angle:.1f}°")
    print("=" * 60)
    print()
