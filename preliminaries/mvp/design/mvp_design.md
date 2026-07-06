# Bicycle Crash Detection System — MVP Implementation Plan

**Team 1 | ENGS 21 | Dartmouth College**
**Components**: Raspberry Pi Zero 2 WH, MPU-6050 (GY-521), GT-U7 GPS, Camera Module 3 Wide, PiSugar 3, LED

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Hardware: Pin Assignments &amp; Wiring](#2-hardware-pin-assignments--wiring)
3. [Critical Hardware Note: I2C Address Conflict](#3-critical-hardware-note-i2c-address-conflict)
4. [Development Environment Setup](#4-development-environment-setup)
5. [Phase 1 — Raspberry Pi OS &amp; SSH Access](#5-phase-1--raspberry-pi-os--ssh-access)
6. [Phase 2 — Enable Interfaces (I2C, UART, Camera)](#6-phase-2--enable-interfaces-i2c-uart-camera)
7. [Phase 3 — IMU Crash Detection (Core MVP)](#7-phase-3--imu-crash-detection-core-mvp)
8. [Phase 4 — LED Alert Signal](#8-phase-4--led-alert-signal)
9. [Phase 5 — Integration: Crash Detector + LED](#9-phase-5--integration-crash-detector--led)
10. [Checkpoint Tests](#10-checkpoint-tests)
11. [Designing for the Demo Experiment](#11-designing-for-the-demo-experiment)
12. [Future-Proofing: What NOT to Do](#12-future-proofing-what-not-to-do)
13. [Future Integration Notes (Post-MVP)](#13-future-integration-notes-post-mvp)
14. [Troubleshooting Guide](#14-troubleshooting-guide)
15. [References &amp; Documentation Links](#15-references--documentation-links)

---

## 1. System Architecture Overview

The MVP is a deliberately minimal system that proves crash detection works end-to-end. It reads IMU data, runs a detection algorithm, and flashes an LED when a crash is detected. Every design choice is made so that the LED can later be replaced with a BLE notification, and the GPS/camera modules can be layered on without rewiring.

```
┌─────────────────────────────────────────────────────┐
│                  Raspberry Pi Zero 2 WH              │
│                                                       │
│   I2C Bus 1 (GPIO 2/3)         UART (GPIO 14/15)    │
│       │                              │               │
│   ┌───┴───┐                    ┌─────┴─────┐        │
│   │MPU-6050│                   │  GT-U7 GPS │        │
│   │ (0x69) │                   │  (9600 bd) │        │
│   └────────┘                   └────────────┘        │
│                                                       │
│   GPIO 17 ──── LED + 330Ω Resistor ──── GND         │
│                                                       │
│   CSI Port ──── Camera Module 3 Wide (22→15 pin)    │
│                                                       │
│   Pogo Pins (back) ──── PiSugar 3 (0x57 I2C)        │
└─────────────────────────────────────────────────────┘
```

**MVP Scope** (what we build now):

- Pi boots headless, reads MPU-6050 over I2C
- Python crash detection algorithm monitors acceleration magnitude
- LED on GPIO 17 flashes when crash threshold exceeded
- All data logged to CSV for post-ride analysis

**Not MVP** (designed for, built later):

- BLE notification to iOS app (replaces LED)
- Cancel button with 30-second grace period
- Camera video recording loop
- GPS location in alert payload

---

## 2. Hardware: Pin Assignments & Wiring

### Complete Pin Map

Every pin assignment below is chosen to avoid conflicts between all current and future components.

| Component  | Signal      | Pi GPIO (BCM) | Physical Pin | Wire Color (suggested)  |
| ---------- | ----------- | ------------- | ------------ | ----------------------- |
| MPU-6050   | VCC         | —            | Pin 2 (5V)   | Red                     |
| MPU-6050   | GND         | —            | Pin 6 (GND)  | Black                   |
| MPU-6050   | SDA         | GPIO 2        | Pin 3        | Blue                    |
| MPU-6050   | SCL         | GPIO 3        | Pin 5        | Yellow                  |
| MPU-6050   | AD0         | —            | Pin 1 (3.3V) | Orange                  |
| GT-U7 GPS  | VCC         | —            | Pin 4 (5V)   | Red                     |
| GT-U7 GPS  | GND         | —            | Pin 9 (GND)  | Black                   |
| GT-U7 GPS  | TX          | GPIO 15 (RX)  | Pin 10       | Green                   |
| GT-U7 GPS  | RX          | GPIO 14 (TX)  | Pin 8        | White                   |
| LED        | Anode (+)   | GPIO 17       | Pin 11       | —                      |
| LED        | Cathode (-) | —            | Pin 14 (GND) | — (via 330Ω resistor) |
| Cancel Btn | Signal      | GPIO 27       | Pin 13       | — (future)             |
| Cancel Btn | GND         | —            | Pin 14 (GND) | — (future)             |

### Wiring the MPU-6050 (GY-521 Breakout Board)

The GY-521 board has an onboard voltage regulator, so it accepts 5V on VCC safely. The I2C lines (SDA/SCL) are 3.3V logic on both the Pi and the MPU-6050, so they connect directly with no level shifter needed. The Pi's I2C1 bus has built-in 1.8kΩ pull-up resistors to 3.3V, which is sufficient.

Connect these 5 wires:

```
GY-521 Board          Raspberry Pi Zero 2 WH
─────────────         ──────────────────────
VCC          ──────── Pin 2  (5V)
GND          ──────── Pin 6  (GND)
SDA          ──────── Pin 3  (GPIO 2 / SDA1)
SCL          ──────── Pin 5  (GPIO 3 / SCL1)
AD0          ──────── Pin 1  (3.3V)        ← CRITICAL: sets address to 0x69
```

Leave INT, XDA, and XCL unconnected. INT could be used for interrupt-driven reads later, but polling is simpler and sufficient for MVP.

### Wiring the LED

Use any standard 3mm or 5mm LED. The GPIO pins output 3.3V and can source up to ~16mA safely. A 330Ω resistor limits current to about 10mA, which is bright enough.

```
GPIO 17 (Pin 11) ────┤►├──── 330Ω ──── GND (Pin 14)
                     LED          Resistor
                  (long leg)    (either side)
```

### Wiring the GT-U7 GPS (future, not needed for MVP)

The GT-U7 is a NEO-6M compatible module that communicates over UART at 9600 baud. Its onboard regulator accepts 5V. IMPORTANT: the GPS TX pin connects to the Pi's RX pin and vice versa (crossover).

```
GT-U7 Module          Raspberry Pi Zero 2 WH
────────────          ──────────────────────
VCC          ──────── Pin 4  (5V)
GND          ──────── Pin 9  (GND)
TX           ──────── Pin 10 (GPIO 15 / RX)
RX           ──────── Pin 8  (GPIO 14 / TX)
```

### PiSugar 3 (Battery)

The PiSugar 3 connects via pogo pins on the back of the Pi Zero — it does NOT use the GPIO header. Align the four screw holes, press the Pi down onto the PiSugar board, and secure with the included M2.5 screws. The pogo pins contact the underside of the Pi's GPIO pads, providing both power and I2C communication. This means the entire 40-pin header remains free for your sensors and LED.

### Camera Module 3 Wide (future, not needed for MVP)

The Pi Zero 2 W has a 22-pin mini CSI connector. The Camera Module 3 has a standard 15-pin connector. You need a 15-pin to 22-pin FFC adapter cable (your camera listing mentions a "15cm 15-22 Pin FFC Cable" is included — use that). Gently lift the black tab on the Pi's CSI connector, insert the 22-pin end (contacts facing the board), and press the tab back down.

---

## 3. Critical Hardware Note: I2C Address Conflict

**This is the single most important hardware detail. Miss it and nothing works.**

The PiSugar 3 uses I2C addresses **0x57** (EEPROM/RTC) and **0x68** (power management). The MPU-6050 default address is also **0x68**. Two devices on the same address on the same bus will corrupt each other's data.

**Solution**: Connect the MPU-6050's AD0 pin to 3.3V (Pin 1 on the Pi). This changes its address from 0x68 to **0x69**. This is a one-wire fix that permanently avoids the conflict.

After wiring, verify with:

```bash
sudo i2cdetect -y 1
```

You should see:

- `0x57` — PiSugar 3 RTC/EEPROM
- `0x68` — PiSugar 3 power management (may show as `UU` if the driver claims it)
- `0x69` — MPU-6050 (your IMU)

If you see `0x68` but NOT `0x69`, the AD0 wire is not making contact. Recheck it.

---

## 4. Development Environment Setup

### What You Need on Your Laptop/Desktop

You will write code on the Pi itself over SSH (or optionally write on your laptop and transfer via `scp`). No special IDE is needed — a terminal and a text editor are sufficient.

**Recommended tools on your computer:**

- **Terminal**: macOS Terminal, Windows Terminal, or iTerm2
- **SSH Client**: Built into macOS/Linux (`ssh` command); on Windows use the built-in OpenSSH or PuTTY
- **Code Editor** (optional, for writing on your laptop): VS Code with the "Remote - SSH" extension is excellent — it lets you edit files on the Pi as if they were local
- **SD Card Writer**: Raspberry Pi Imager (download from raspberrypi.com/software)

### What Runs on the Pi

- **OS**: Raspberry Pi OS Lite (64-bit, Bookworm) — no desktop environment needed, saves resources
- **Language**: Python 3.11+ (pre-installed on Raspberry Pi OS)
- **Editor on Pi**: `nano` (pre-installed) or `vim`

### Python Libraries (installed on the Pi)

| Library       | Purpose                         | Install Command                                   |
| ------------- | ------------------------------- | ------------------------------------------------- |
| `smbus2`    | I2C communication with MPU-6050 | `sudo apt install python3-smbus2`               |
| `RPi.GPIO`  | Control LED on GPIO pins        | Pre-installed on Raspberry Pi OS                  |
| `pyserial`  | UART communication with GPS     | `pip3 install pyserial --break-system-packages` |
| `pynmea2`   | Parse GPS NMEA sentences        | `pip3 install pynmea2 --break-system-packages`  |
| `picamera2` | Camera Module 3 control         | `sudo apt install python3-picamera2`            |

For MVP, you only need `smbus2` and `RPi.GPIO`. Install the others when you reach those features.

---

## 5. Phase 1 — Raspberry Pi OS & SSH Access

### Step 1: Flash the SD Card

1. Download and install **Raspberry Pi Imager** from https://www.raspberrypi.com/software/
2. Insert the SanDisk 64GB MicroSD card into your computer
3. In Raspberry Pi Imager:
   - **Device**: Raspberry Pi Zero 2 W
   - **OS**: Raspberry Pi OS (other) → Raspberry Pi OS Lite (64-bit)
   - Click the **gear icon** (or "Edit Settings") before writing to pre-configure:
     - **Hostname**: `bikebox` (or whatever you prefer)
     - **Enable SSH**: Yes, use password authentication
     - **Username**: `pi`, **Password**: choose something memorable
     - **Configure Wi-Fi**: Enter your WiFi SSID and password (use your phone hotspot or home network; at Dartmouth, eduroam requires special config — use a mobile hotspot for initial setup)
     - **Locale**: US, Eastern time
4. Click **Write** and wait for it to finish

### Step 2: First Boot

1. Insert the SD card into the Pi Zero 2 WH
2. Attach the PiSugar 3 battery (or power via USB-C)
3. Wait about 60-90 seconds for first boot (the Pi Zero 2 W is slow to boot)
4. Find the Pi's IP address. Options:
   - Try `ping bikebox.local` from your computer (works if mDNS is enabled)
   - Check your router's admin page for connected devices
   - Use a network scanner app on your phone (Fing is good)

### Step 3: SSH In

```bash
ssh pi@bikebox.local
# Enter your password when prompted
```

### Step 4: Initial System Update

```bash
sudo apt update && sudo apt upgrade -y
```

This takes 5-10 minutes on the Pi Zero 2 W. Be patient.

### Step 5: Install Copper Heatsinks

While the Pi is updating, attach the copper heatsinks to the Pi's SoC (the square chip). Peel the adhesive backing and stick it on. This helps with thermal throttling during sustained workloads like video encoding.

### Checkpoint ✓

If you can SSH in and run `uname -a` and see `aarch64`, your Pi is ready. Run:

```bash
cat /proc/cpuinfo | head -5
```

You should see the BCM2710 quad-core processor.

---

## 6. Phase 2 — Enable Interfaces (I2C, UART, Camera)

### Enable I2C

```bash
sudo raspi-config
```

Navigate to: **Interface Options → I2C → Enable**

### Enable Serial Port (for future GPS)

Still in raspi-config: **Interface Options → Serial Port**

- "Would you like a login shell to be accessible over serial?" → **No**
- "Would you like the serial port hardware to be enabled?" → **Yes**

This disables the console on the UART (so it doesn't interfere with GPS data) while keeping the serial hardware active.

### Enable Camera

Still in raspi-config: **Interface Options → Camera → Enable**

(On newer Raspberry Pi OS versions, the camera may be auto-detected. If you don't see this option, it's already enabled via `camera_auto_detect=1` in `/boot/firmware/config.txt`.)

### Reboot

```bash
sudo reboot
```

### Install MVP Dependencies

After reboot, SSH back in and install:

```bash
sudo apt install -y python3-smbus2 i2c-tools
```

### Verify I2C Bus

With the MPU-6050 wired up (AD0 to 3.3V):

```bash
sudo i2cdetect -y 1
```

**Expected output** (with PiSugar 3 attached):

```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- 57 -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- UU 69 -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

**Without PiSugar** (just MPU-6050):

```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
...
60: -- -- -- -- -- -- -- -- -- 69 -- -- -- -- -- --
...
```

If you see `0x69`, the MPU-6050 is detected and ready. If you see `0x68` instead of `0x69`, the AD0 pin is not connected to 3.3V.

### Checkpoint ✓

Run the following quick test to read the MPU-6050's WHO_AM_I register:

```bash
python3 -c "import smbus2; bus = smbus2.SMBus(1); print(hex(bus.read_byte_data(0x69, 0x75)))"
```

This should print `0x68` (the WHO_AM_I value for the MPU-6050, which is always 0x68 regardless of the AD0 setting — yes, this is confusing, but it's correct per the datasheet).

---

## 7. Phase 3 — IMU Crash Detection (Core MVP)

### Understanding the MPU-6050

The MPU-6050 combines a 3-axis accelerometer and 3-axis gyroscope. For crash detection, we primarily use the accelerometer. It measures acceleration in g-forces along three axes (X, Y, Z). When the bike is stationary and upright, you should read approximately (0, 0, 1g) — the 1g comes from gravity pulling on the Z axis.

Key registers:

- `0x6B` — Power Management 1 (write 0x00 to wake the device from sleep)
- `0x1C` — Accelerometer Configuration (sets full-scale range: ±2g, ±4g, ±8g, ±16g)
- `0x3B-0x40` — Accelerometer data (X high/low, Y high/low, Z high/low)
- `0x43-0x48` — Gyroscope data (X, Y, Z)
- `0x19` — Sample Rate Divider

For crash detection, we use **±16g range** (register 0x1C = 0x18). Bicycle crashes can produce 8-10g of deceleration per your design analysis. The ±2g default range would clip and saturate, missing the actual peak. At ±16g, each LSB = 1g/2048, and we can capture impacts up to 16g.

### The Crash Detection Algorithm

The algorithm computes the **total acceleration magnitude** and compares it against a threshold:

```
magnitude = sqrt(ax² + ay² + az²)
```

During normal riding, this hovers around 1.0g (gravity). Bumps might push it to 2-3g. A crash typically produces a sharp spike to 4-8g+ followed by a sustained change in orientation (the bike has fallen over).

Our detection uses two conditions:

1. **Impact spike**: magnitude exceeds `IMPACT_THRESHOLD` (default: 4.0g)
2. **Sustained tilt**: after the spike, check if the bike remains tilted (confirms it's not just a pothole)

This two-stage approach dramatically reduces false positives.

### Create the Project Directory

```bash
mkdir -p ~/bikebox
cd ~/bikebox
```

### MPU-6050 Driver Module

Create the file `~/bikebox/imu.py`:

```python
"""
imu.py — MPU-6050 I2C driver for Raspberry Pi
Handles initialization, raw data reads, and calibration.

Reference: MPU-6050 Register Map (Rev 4.2)
  https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Register-Map1.pdf
"""

import smbus2
import time
import math

# MPU-6050 I2C address (AD0 pin connected to 3.3V → 0x69)
MPU_ADDR = 0x69

# Register addresses
PWR_MGMT_1   = 0x6B
SMPLRT_DIV    = 0x19
CONFIG        = 0x1A
GYRO_CONFIG   = 0x1B
ACCEL_CONFIG  = 0x1C
INT_ENABLE    = 0x38
ACCEL_XOUT_H  = 0x3B
GYRO_XOUT_H   = 0x43
WHO_AM_I      = 0x75

# Scale factors
# At ±16g range, sensitivity is 2048 LSB/g
ACCEL_SCALE_16G = 2048.0
# At ±2000°/s range, sensitivity is 16.4 LSB/(°/s)
GYRO_SCALE_2000 = 16.4


class IMU:
    def __init__(self, bus_num=1, address=MPU_ADDR):
        self.bus = smbus2.SMBus(bus_num)
        self.address = address
        self.accel_offset = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self._init_sensor()

    def _init_sensor(self):
        """Wake up the MPU-6050 and configure it for crash detection."""
        # Verify device identity
        who = self.bus.read_byte_data(self.address, WHO_AM_I)
        if who != 0x68:
            raise RuntimeError(
                f"MPU-6050 not found at 0x{self.address:02X}. "
                f"WHO_AM_I returned 0x{who:02X} (expected 0x68). "
                f"Check wiring and AD0 pin."
            )

        # Wake up from sleep mode (default state after power-on)
        self.bus.write_byte_data(self.address, PWR_MGMT_1, 0x00)
        time.sleep(0.1)  # Wait for sensor to stabilize

        # Set sample rate: Sample Rate = 1kHz / (1 + SMPLRT_DIV)
        # SMPLRT_DIV = 4 → 200 Hz sample rate
        self.bus.write_byte_data(self.address, SMPLRT_DIV, 4)

        # Set DLPF (Digital Low Pass Filter) to ~44Hz bandwidth
        # This filters out high-frequency vibration noise from the road
        # CONFIG register bits [2:0] = 3 → ~44Hz accel, ~42Hz gyro
        self.bus.write_byte_data(self.address, CONFIG, 3)

        # Set accelerometer to ±16g range (ACCEL_CONFIG bits [4:3] = 11)
        self.bus.write_byte_data(self.address, ACCEL_CONFIG, 0x18)

        # Set gyroscope to ±2000°/s range (GYRO_CONFIG bits [4:3] = 11)
        self.bus.write_byte_data(self.address, GYRO_CONFIG, 0x18)

        print(f"MPU-6050 initialized at 0x{self.address:02X}")

    def _read_raw_word(self, reg):
        """Read a signed 16-bit value from two consecutive registers."""
        high = self.bus.read_byte_data(self.address, reg)
        low = self.bus.read_byte_data(self.address, reg + 1)
        value = (high << 8) | low
        if value >= 0x8000:
            value -= 0x10000
        return value

    def read_accel_raw(self):
        """Read raw accelerometer values (X, Y, Z)."""
        ax = self._read_raw_word(ACCEL_XOUT_H)
        ay = self._read_raw_word(ACCEL_XOUT_H + 2)
        az = self._read_raw_word(ACCEL_XOUT_H + 4)
        return ax, ay, az

    def read_accel_g(self):
        """Read accelerometer values in g-force units, with calibration applied."""
        ax_raw, ay_raw, az_raw = self.read_accel_raw()
        ax = (ax_raw / ACCEL_SCALE_16G) - self.accel_offset['x']
        ay = (ay_raw / ACCEL_SCALE_16G) - self.accel_offset['y']
        az = (az_raw / ACCEL_SCALE_16G) - self.accel_offset['z']
        return ax, ay, az

    def read_gyro_dps(self):
        """Read gyroscope values in degrees per second."""
        gx = self._read_raw_word(GYRO_XOUT_H)
        gy = self._read_raw_word(GYRO_XOUT_H + 2)
        gz = self._read_raw_word(GYRO_XOUT_H + 4)
        return gx / GYRO_SCALE_2000, gy / GYRO_SCALE_2000, gz / GYRO_SCALE_2000

    def accel_magnitude(self):
        """Compute total acceleration magnitude in g."""
        ax, ay, az = self.read_accel_g()
        return math.sqrt(ax**2 + ay**2 + az**2)

    def calibrate(self, samples=200, delay=0.005):
        """
        Calibrate accelerometer offsets. Place the device flat and still
        on a level surface before calling this. Takes ~1 second.
        """
        print("Calibrating IMU — keep device STILL and FLAT...")
        sum_x, sum_y, sum_z = 0.0, 0.0, 0.0
        for _ in range(samples):
            ax, ay, az = self.read_accel_raw()
            sum_x += ax / ACCEL_SCALE_16G
            sum_y += ay / ACCEL_SCALE_16G
            sum_z += az / ACCEL_SCALE_16G
            time.sleep(delay)

        avg_x = sum_x / samples
        avg_y = sum_y / samples
        avg_z = sum_z / samples

        # At rest flat, expect (0, 0, 1.0g)
        self.accel_offset['x'] = avg_x
        self.accel_offset['y'] = avg_y
        self.accel_offset['z'] = avg_z - 1.0

        print(f"Calibration done. Offsets: X={avg_x:.4f}, Y={avg_y:.4f}, Z={avg_z:.4f}")
        return self.accel_offset
```

### Crash Detection Engine

Create the file `~/bikebox/detector.py`:

```python
"""
detector.py — Crash detection algorithm.

Detection strategy (two-stage to reduce false positives):
  1. Monitor acceleration magnitude continuously
  2. If magnitude > IMPACT_THRESHOLD → potential crash
  3. Wait CONFIRM_WINDOW, then check tilt angle
  4. If tilt > TILT_THRESHOLD for SUSTAINED_TILT_TIME → confirmed crash
  5. Fire alert callback (LED now, BLE later)
"""

import time
import math
from collections import deque

# --- Tunable Parameters ---
IMPACT_THRESHOLD = 4.0    # g-force to trigger stage 1 (normal: ~1g, crash: 4-10g+)
TILT_THRESHOLD = 45.0     # degrees from upright to confirm (bike on side ≈ 90°)
CONFIRM_WINDOW = 1.0      # seconds after impact before checking tilt
SUSTAINED_TILT_TIME = 2.0 # seconds bike must stay tilted to confirm
COOLDOWN_TIME = 30.0      # seconds between crash detections
POLL_RATE = 0.01           # seconds between IMU reads (100 Hz)


class CrashDetector:
    def __init__(self, imu, on_crash=None):
        self.imu = imu
        self.on_crash = on_crash
        self.running = False
        self.last_crash_time = 0
        self.history = deque(maxlen=500)  # ~5 seconds at 100Hz

    def compute_tilt(self):
        """Tilt angle from vertical using accelerometer."""
        ax, ay, az = self.imu.read_accel_g()
        magnitude = math.sqrt(ax**2 + ay**2 + az**2)
        if magnitude < 0.1:
            return 90.0  # Free-fall → treat as tilted
        cos_angle = max(-1.0, min(1.0, az / magnitude))
        return math.degrees(math.acos(cos_angle))

    def check_sustained_tilt(self):
        """Check if bike remains tilted for SUSTAINED_TILT_TIME."""
        start = time.time()
        tilt = 0
        while (time.time() - start) < SUSTAINED_TILT_TIME:
            tilt = self.compute_tilt()
            if tilt < TILT_THRESHOLD:
                return False, tilt
            time.sleep(0.1)
        return True, tilt

    def run(self):
        """Main detection loop. Runs until self.running = False or Ctrl+C."""
        self.running = True
        print(f"Detector active: impact={IMPACT_THRESHOLD}g, tilt={TILT_THRESHOLD}°")
        print("Monitoring... (Ctrl+C to stop)\n")

        try:
            while self.running:
                mag = self.imu.accel_magnitude()
                ts = time.time()
                ax, ay, az = self.imu.read_accel_g()
                self.history.append({'time': ts, 'ax': ax, 'ay': ay, 'az': az, 'mag': mag})

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
                            print(f"🚨 CRASH CONFIRMED: {peak_g:.2f}g, tilt {final_tilt:.1f}°")
                            if self.on_crash:
                                self.on_crash(peak_g, final_tilt, ts)
                        else:
                            print(f"   Bike righted — false alarm.")
                    else:
                        print(f"   Upright — bump, not crash.")

                time.sleep(POLL_RATE)

        except KeyboardInterrupt:
            print("\nDetector stopped.")
        finally:
            self.running = False
```

---

## 8. Phase 4 — LED Alert Signal

Create the file `~/bikebox/alert.py`:

```python
"""
alert.py — LED alert output for crash notification.

MVP: Flash LED on GPIO 17.
Future: Replace with BLE notification + 30s cancel window.
"""

import RPi.GPIO as GPIO
import time
import threading

LED_PIN = 17  # BCM numbering, physical pin 11

def setup_gpio():
    """Initialize GPIO pins. Call once at program start."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(LED_PIN, GPIO.OUT)
    GPIO.output(LED_PIN, GPIO.LOW)
    print(f"GPIO ready. LED on BCM {LED_PIN}.")

def flash_led(times=10, on_time=0.2, off_time=0.2):
    """Flash the LED a specified number of times."""
    for _ in range(times):
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(on_time)
        GPIO.output(LED_PIN, GPIO.LOW)
        time.sleep(off_time)

def on_crash(peak_g, tilt_angle, timestamp):
    """
    Crash alert callback. Called by CrashDetector on confirmed crash.
    MVP: flash LED. Future: BLE notify + grace period.
    """
    t = time.strftime('%H:%M:%S', time.localtime(timestamp))
    print(f"ALERT @ {t} | Peak: {peak_g:.2f}g | Tilt: {tilt_angle:.1f}°")
    threading.Thread(
        target=flash_led,
        kwargs={'times': 20, 'on_time': 0.1, 'off_time': 0.1},
        daemon=True,
    ).start()

def cleanup():
    GPIO.output(LED_PIN, GPIO.LOW)
    GPIO.cleanup()
```

---

## 9. Phase 5 — Integration: Crash Detector + LED

Create `~/bikebox/main.py`:

```python
"""
main.py — BikeBox entry point.

Usage:
    python3 main.py              # Normal operation
    python3 main.py --test-led   # Quick LED test
    python3 main.py --test-imu   # Print live IMU data
    python3 main.py --log FILE   # Log to CSV while detecting
"""

import sys
import time
import csv
import math
import signal

from imu import IMU
from detector import CrashDetector, IMPACT_THRESHOLD, TILT_THRESHOLD, COOLDOWN_TIME
from alert import setup_gpio, on_crash, flash_led, cleanup


def handle_exit(signum, frame):
    print("\nShutting down BikeBox...")
    cleanup()
    sys.exit(0)


def test_led():
    setup_gpio()
    print("LED test — 5 flashes...")
    flash_led(times=5, on_time=0.3, off_time=0.3)
    print("Done.")
    cleanup()


def test_imu():
    sensor = IMU()
    sensor.calibrate()
    print(f"\n{'Time':>10} {'AX':>8} {'AY':>8} {'AZ':>8} {'Mag':>8} {'Tilt°':>8}")
    print("-" * 58)
    try:
        while True:
            ax, ay, az = sensor.read_accel_g()
            mag = math.sqrt(ax**2 + ay**2 + az**2)
            cos_a = max(-1.0, min(1.0, az / mag)) if mag > 0.1 else 0
            tilt = math.degrees(math.acos(cos_a))
            print(f"\r{time.strftime('%H:%M:%S'):>10} "
                  f"{ax:>8.3f} {ay:>8.3f} {az:>8.3f} "
                  f"{mag:>8.3f} {tilt:>8.1f}", end='', flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nDone.")


def run_detector(log_file=None):
    setup_gpio()
    sensor = IMU()
    sensor.calibrate()

    detector = CrashDetector(imu=sensor, on_crash=on_crash)

    csv_writer, csv_fh = None, None
    if log_file:
        csv_fh = open(log_file, 'w', newline='')
        csv_writer = csv.writer(csv_fh)
        csv_writer.writerow(['timestamp', 'ax', 'ay', 'az', 'magnitude', 'event'])
        print(f"Logging to {log_file}")

    flash_led(times=3, on_time=0.1, off_time=0.1)  # Startup confirmation
    print("BikeBox armed.\n")

    try:
        detector.running = True
        while detector.running:
            mag = sensor.accel_magnitude()
            ax, ay, az = sensor.read_accel_g()
            ts = time.time()
            event = ""

            detector.history.append({'time': ts, 'ax': ax, 'ay': ay, 'az': az, 'mag': mag})

            if mag > IMPACT_THRESHOLD and (ts - detector.last_crash_time) > COOLDOWN_TIME:
                peak_g = mag
                print(f"\n⚠  IMPACT: {peak_g:.2f}g")
                event = "impact"
                time.sleep(1.0)

                tilt = detector.compute_tilt()
                print(f"   Tilt: {tilt:.1f}°")

                if tilt > TILT_THRESHOLD:
                    sustained, final_tilt = detector.check_sustained_tilt()
                    if sustained:
                        detector.last_crash_time = time.time()
                        event = "CRASH"
                        print(f"🚨 CRASH CONFIRMED")
                        on_crash(peak_g, final_tilt, ts)
                    else:
                        event = "false_alarm"
                        print(f"   Righted — false alarm")
                else:
                    event = "bump"
                    print(f"   Upright — bump")

            if csv_writer:
                csv_writer.writerow([f"{ts:.3f}", f"{ax:.4f}", f"{ay:.4f}",
                                     f"{az:.4f}", f"{mag:.4f}", event])
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if csv_fh:
            csv_fh.close()
            print(f"Data saved to {log_file}")
        cleanup()


def main():
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == '--test-led':
            test_led()
        elif cmd == '--test-imu':
            test_imu()
        elif cmd == '--log' and len(sys.argv) > 2:
            run_detector(log_file=sys.argv[2])
        else:
            print("Usage: python3 main.py [--test-led | --test-imu | --log FILE]")
    else:
        run_detector()


if __name__ == '__main__':
    main()
```

---

## 10. Checkpoint Tests

Run these in order. **Do not skip ahead if a test fails.**

| # | Command                                          | Pass Criteria                         | Common Failure                      |
| - | ------------------------------------------------ | ------------------------------------- | ----------------------------------- |
| 1 | `sudo i2cdetect -y 1`                          | `0x69` visible                      | AD0 not wired to 3.3V               |
| 2 | `python3 -c "from imu import IMU; IMU()"`      | "initialized at 0x69"                 | Wrong WHO_AM_I (counterfeit chip)   |
| 3 | `python3 main.py --test-imu`                   | Mag ≈ 1.00g at rest, changes on tilt | Sensor in sleep mode                |
| 4 | `python3 main.py --test-led`                   | LED flashes 5 times                   | LED polarity reversed               |
| 5 | `python3 main.py` → smack table + tilt sensor | "CRASH CONFIRMED" + LED flash         | Threshold too high — lower to 2.0g |
| 6 | Tap table without tilting                        | "bump, not crash"                     | Tilt check failing                  |

---

## 11. Designing for the Demo Experiment

### Experiment: Controlled Bicycle Tip-Over

**Setup**: Mount BikeBox under seat → `python3 main.py --log demo.csv`

**Protocol**:

1. **Baseline** (30s): Ride normally. CSV shows ~1.0g. No alerts.
2. **Bump test**: Ride over obstacle. Shows 2-3g spike. System says "bump" → demonstrates false positive rejection.
3. **Crash sim**: Push bike and let it fall. System triggers CRASH CONFIRMED + LED flash. This is the key demo moment.

**Post-experiment**: Transfer CSV via `scp pi@bikebox.local:~/bikebox/demo.csv .` and plot magnitude vs time. The graph clearly distinguishes riding, bumps, and crash.

### Threshold Tuning

- Too many false positives → raise `IMPACT_THRESHOLD` to 5.0 or 6.0
- Missing crashes → lower to 3.0
- Tilt too sensitive → raise `TILT_THRESHOLD` to 60°
- Always recalibrate on the actual bike in its mounting position before demos

---

## 12. Future-Proofing: What NOT to Do

1. **Do NOT disable Bluetooth** (`dtoverlay=disable-bt`). You need BLE for the iOS app. The mini UART works fine for GPS at 9600 baud.
2. **Do NOT hardcode LED pin everywhere.** It's in `alert.py` only. Swap to BLE by changing `on_crash()`.
3. **Do NOT use GPIO 27 for LED.** Reserved for cancel button.
4. **Do NOT write blocking GPS code in the main loop.** Use a background thread.
5. **Do NOT use legacy `picamera`.** Camera Module 3 requires `picamera2` (libcamera).
6. **Do NOT use `/dev/ttyAMA0` for GPS.** Use `/dev/serial0` — it's a symlink that always points to the correct UART regardless of BT config.

---

## 13. Future Integration Notes (Post-MVP)

### Cancel Button (GPIO 27)

Wire between GPIO 27 and GND. Enable internal pull-up:

```python
GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_UP)
# Pressed → GPIO.input(27) == 0
```

Modify `on_crash()`: start 30s timer, poll button, cancel if pressed.

### BLE Notification

Pi Zero 2 W has BT 4.2 with BLE. Use BlueZ + `dbus-python` to create a GATT peripheral. The iOS app subscribes to a characteristic; crash writes trigger notifications.

### GPS (UART Background Thread)

```python
import serial, pynmea2, threading

def gps_reader(state):
    ser = serial.Serial('/dev/serial0', 9600, timeout=1.0)
    while True:
        line = ser.readline().decode('ascii', errors='replace').strip()
        if 'RMC' in line:
            try:
                msg = pynmea2.parse(line)
                if msg.status == 'A':
                    state['lat'] = msg.latitude
                    state['lon'] = msg.longitude
            except pynmea2.ParseError:
                pass
```

### Camera (Circular Video Buffer)

```python
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import CircularOutput

picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (1920, 1080)}))
encoder = H264Encoder()
output = CircularOutput(buffersize=30 * 15)  # ~15s buffer
picam2.start_recording(encoder, output)
# On crash: output.outputfile = "crash.h264"; output.start(); sleep(5); output.stop()
```

---

## 14. Troubleshooting Guide

| Problem                       | Likely Cause                                  | Fix                                                            |
| ----------------------------- | --------------------------------------------- | -------------------------------------------------------------- |
| `i2cdetect` shows nothing   | I2C not enabled or wiring wrong               | `sudo raspi-config` → enable I2C; check SDA/SCL not swapped |
| 0x68 instead of 0x69          | AD0 not connected to 3.3V                     | Wire AD0 to Pin 1                                              |
| WHO_AM_I returns 0x70 or 0x71 | Counterfeit MPU-6050 (actually MPU-6500/9250) | Comment out WHO_AM_I check; data still works                   |
| `No module named 'smbus2'`  | Not installed                                 | `sudo apt install python3-smbus2`                            |
| LED doesn't light             | Polarity reversed or wrong pin                | Long leg to GPIO; check BCM 17 = Pin 11                        |
| GPS shows no data             | Console still on serial                       | `raspi-config` → Serial → No login shell, Yes hardware     |
| GPS all zeros                 | No satellite fix                              | Move outdoors, wait 1-2 min for cold start                     |
| Camera "no cameras available" | Cable not seated or wrong type                | Use 15→22 pin FFC; contacts face board                        |
| PiSugar not on I2C            | Dirty pogo pin contacts                       | Clean with isopropyl alcohol                                   |

---

## 15. References & Documentation Links

| Resource                     | URL                                                                                             |
| ---------------------------- | ----------------------------------------------------------------------------------------------- |
| Raspberry Pi Zero 2 W Pinout | https://pinout.xyz                                                                              |
| Raspberry Pi UART Config     | https://www.raspberrypi.com/documentation/computers/configuration.html                          |
| MPU-6050 Register Map        | https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Register-Map1.pdf                |
| MPU-6050 Python (PyPI)       | https://pypi.org/project/mpu6050-raspberrypi/                                                   |
| PiSugar 3 Wiki               | https://github.com/PiSugar/PiSugar/wiki/PiSugar-3-Series                                        |
| PiSugar 3 I2C Datasheet      | https://github.com/PiSugar/PiSugar/wiki/PiSugar-3-I2C-Datasheet                                 |
| GT-U7 GPS Guide              | https://docs.cirkitdesigner.com/component/88312a00-fbbc-40b2-94d4-7cc32f2b4e4b/gt-u7-gps-module |
| Picamera2 Manual             | https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf                                  |
| Camera Module 3              | https://www.raspberrypi.com/products/camera-module-3/                                           |
| Pi Zero Camera Cable         | https://www.raspberrypi.com/products/camera-cable/                                              |

---

## File Structure

```
~/bikebox/
├── main.py        # Entry point
├── imu.py         # MPU-6050 driver
├── detector.py    # Crash detection algorithm
└── alert.py       # LED + alert callbacks
```

**Run**: `cd ~/bikebox && python3 main.py`
**Log**: `python3 main.py --log ride_data.csv`
**Auto-start on boot**: Add to `/etc/rc.local` before `exit 0`:

```
/usr/bin/python3 /home/pi/bikebox/main.py --log /home/pi/bikebox/auto.csv &
```
