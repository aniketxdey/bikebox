# BikeBox Software Guide

**Team 1 | ENGS 21 | Dartmouth College**

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Module Breakdown](#2-module-breakdown)
3. [Algorithm Deep Dive](#3-algorithm-deep-dive)
4. [Data Flow](#4-data-flow)
5. [CSV Output Format](#5-csv-output-format)
6. [Configuration &amp; Tuning](#6-configuration--tuning)
7. [Future Integration Points](#7-future-integration-points)

---

## 1. System Overview

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        main.py                                │
│           CLI dispatch · CSV logging · signal handling         │
│                                                                │
│    ┌────────────┐    ┌──────────────┐    ┌───────────────┐    │
│    │   imu.py   │───▶│ detector.py  │───▶│   alert.py    │    │
│    │            │    │              │    │               │    │
│    │ I2C driver │    │  Two-stage   │    │  Terminal     │    │
│    │ calibrate  │    │  algorithm   │    │  on_crash()   │    │
│    │ read data  │    │  tilt calc   │    │  print alert  │    │
│    └─────┬──────┘    └──────────────┘    └───────────────┘    │
│          │                                                     │
│    ┌─────▼──────┐                                              │
│    │  MPU-6050  │    I2C bus 1, address 0x69                   │
│    │  (GY-521)  │    ±16g accel · ±2000°/s gyro               │
│    └────────────┘                                              │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow Summary

```
MPU-6050 ──I2C──▶ imu.py ──(ax,ay,az)──▶ detector.py ──on_crash()──▶ alert.py
                                              │                          │
                                              ▼                          ▼
                                        main.py CSV log          Terminal (SSH)
```

The four Python files form a clean pipeline:

1. **imu.py** talks to hardware over I2C and returns calibrated acceleration/gyro values.
2. **detector.py** consumes those values, runs the two-stage crash algorithm, and fires a callback.
3. **alert.py** owns the output — currently a terminal print (visible over SSH), later BLE + cancel button.
4. **main.py** wires everything together, handles the CLI, and adds CSV logging.

---

## 2. Module Breakdown

### imu.py — MPU-6050 I2C Driver

**Purpose**: Encapsulate all I2C communication with the MPU-6050 sensor.

**Public API**:

| Method                        | Returns          | Description                                          |
| ----------------------------- | ---------------- | ---------------------------------------------------- |
| `IMU(bus_num, address)`     | instance         | Init sensor, verify WHO_AM_I, configure ranges       |
| `calibrate(samples, delay)` | `dict`         | Average*samples* readings to compute X/Y/Z offsets |
| `read_accel_g()`            | `(ax, ay, az)` | Calibrated acceleration in g-force                   |
| `read_gyro_dps()`           | `(gx, gy, gz)` | Angular velocity in °/s                             |
| `accel_magnitude()`         | `float`        | `sqrt(ax² + ay² + az²)` in g                    |
| `close()`                   | `None`         | Release the I2C bus                                  |

**Key design decisions**:

- Burst-reads 6 bytes at once via `read_i2c_block_data` + `struct.unpack` instead of two single-byte reads per axis. This is faster and avoids sampling skew between axes.
- Calibration subtracts 1.0g from the Z average so the resting state reads exactly (0, 0, 1.0g) after offset removal.
- Address defaults to `0x69` — the AD0-HIGH address that avoids the PiSugar 3 conflict on 0x68.

### detector.py — Crash Detection Algorithm

**Purpose**: Monitor IMU data and decide whether a crash has occurred.

**Public API**:

| Method                                | Returns           | Description                                 |
| ------------------------------------- | ----------------- | ------------------------------------------- |
| `CrashDetector(imu, on_crash)`      | instance          | Wire sensor + callback                      |
| `compute_tilt()`                    | `float`         | Current tilt angle in degrees from vertical |
| `compute_tilt_from_accel(ax,ay,az)` | `float`         | Static tilt calc (no hardware read)         |
| `check_sustained_tilt()`            | `(bool, float)` | Poll tilt for `SUSTAINED_TILT_TIME`       |
| `run()`                             | `None`          | Main loop — blocks until stopped           |

**Key design decisions**:

- Two-stage algorithm (impact + sustained tilt) to eliminate false positives from bumps.
- `compute_tilt_from_accel` is a `@staticmethod` so it can be unit-tested with synthetic data.
- Ring buffer (`deque(maxlen=500)`) stores ~5 seconds of history for future analysis/logging.
- 30-second cooldown prevents alert fatigue after a confirmed crash.

### alert.py — Terminal Alert & Crash Callback

**Purpose**: Provide the single `on_crash()` entry point for crash responses.

**Public API**:

| Function                                    | Description                                                        |
| ------------------------------------------- | ------------------------------------------------------------------ |
| `on_crash(peak_g, tilt_angle, timestamp)` | Print a prominent crash alert banner to stdout (visible over SSH)  |

**Key design decisions**:

- `on_crash()` is the *single entry point* for all crash responses. Today it prints to the terminal; tomorrow it sends a BLE notification. Nothing outside this file needs to change.
- No GPIO or hardware dependencies — the alert is pure stdout, visible on the operator's laptop via SSH.
- GPIO 27 is reserved (not configured) for the future cancel button.

### main.py — CLI Entry Point

**Purpose**: Parse arguments, wire modules together, handle CSV logging.

**Modes**:

| Command                            | Action                                                  |
| ---------------------------------- | ------------------------------------------------------- |
| `python3 main.py`                | Calibrate → arm detector → terminal alert on crash    |
| `python3 main.py --test-imu`     | Live accel/tilt readout (Ctrl+C to stop)                |
| `python3 main.py --log file.csv` | Full detection + log every sample to CSV                |

**Key design decisions**:

- Signal handlers for SIGINT/SIGTERM ensure clean shutdown on unexpected termination.
- CSV rows are written for every single IMU sample (not just events), enabling continuous time-series plots.

---

## 3. Algorithm Deep Dive

### Why Two Stages?

A single acceleration threshold produces many false positives. Potholes, speed bumps, and curb hops routinely generate 2–4g spikes. Our structural analysis assumes an 8.5g deceleration for enclosure stress calculations, which confirms real crashes produce forces well above the 4.0g detection threshold while leaving margin for the ±16g sensor range. Even so, a threshold-only approach would false-trigger on rough roads.

The second stage — sustained tilt — exploits a simple physical fact: *when a bike crashes, it stays on the ground*. A bump spikes the accelerometer but the bike stays upright. A crash spikes it *and then the orientation changes permanently*.

### Stage 1: Impact Detection

```
magnitude = sqrt(ax² + ay² + az²)
if magnitude > 4.0g → IMPACT detected
```

- **Normal riding**: ~1.0g (just gravity)
- **Speed bump**: 2–3g spike, <50ms
- **Pothole**: 2–4g, <100ms
- **Crash**: 4–10g+, often sustained for 100–500ms

The 4.0g threshold sits well above routine riding forces while staying below the 8.5g deceleration assumed in our structural analysis. It catches most real crashes while rejecting most road features.

### Stage 2: Sustained Tilt Verification

After an impact is detected, the algorithm waits **1.0 second** (CONFIRM_WINDOW) for the initial chaos to settle, then measures tilt:

```
tilt = acos(az / magnitude)
```

Where `az` is the vertical-axis accelerometer reading. At rest upright, `az ≈ 1.0g` and tilt ≈ 0°. When the bike is on its side, `az ≈ 0` and tilt ≈ 90°.

The tilt must exceed **45°** continuously for **2.0 seconds**. This eliminates:

- Momentary oscillations from a hard landing
- Brief tilts from sharp turns
- Sensor noise after impact

### Combined Timeline

```
T = 0.0s    Impact detected (mag > 4.0g)
T = 0.0–1.0 Settling window (no checks, sensor stabilizing)
T = 1.0     First tilt reading — if < 45°, classified as "bump"
T = 1.0–3.0 Continuous tilt monitoring (every 100ms)
            - If tilt drops below 45° at any point → "false_alarm"
            - If tilt stays above 45° for full 2.0s → CRASH CONFIRMED
T = 3.0     on_crash() callback fires → terminal alert printed
T = 3.0–33.0 Cooldown period (no new detections)
```

### False Positive Analysis

| Scenario             | Mag (g)          | Tilt (°)        | Duration            | Result                             |
| -------------------- | ---------------- | ---------------- | ------------------- | ---------------------------------- |
| Normal riding        | 0.8–1.2         | 0–15            | —                  | No trigger                         |
| Speed bump           | 2–3             | 5–15            | <50ms               | Below threshold                    |
| Pothole              | 2–4             | 10–20           | <100ms              | Below threshold or no tilt         |
| Hard curb hop        | 3–5             | 15–30           | <200ms              | May trigger stage 1, fails stage 2 |
| Sharp turn           | 1.5–2.5         | 20–40           | 1–3s               | Below threshold                    |
| Drop off curb        | 2–4             | 10–25           | <500ms              | Fails stage 2                      |
| **Real crash** | **4–10+** | **60–90** | **Sustained** | **Both stages pass**         |

Target: <10% false positive rate in urban commuting conditions.

---

## 4. Data Flow

### From Impact to Alert — Step by Step

1. **IMU Read** (`imu.py`): `read_accel_g()` burst-reads 6 bytes from registers 0x3B–0x40 over I2C, unpacks three 16-bit signed integers, divides by 2048.0 (±16g scale), subtracts calibration offsets.
2. **Magnitude Calculation** (`imu.py` via `accel_magnitude()`): `sqrt(ax² + ay² + az²)` computed from the calibrated values. In standalone detector mode this happens inside `detector.py`'s `run()` loop; in logging mode, `main.py` calls the same `imu.accel_magnitude()` method so it can write the value to CSV. Detection decisions always flow through `detector.py`.
3. **Stage 1 Check** (`detector.py` logic, orchestrated by `main.py` in logging mode): If magnitude > 4.0g AND cooldown has expired, an impact is registered. The event label is set to `"impact"` and the CSV row is written immediately.
4. **Settling Wait**: `time.sleep(1.0)` — the sensor often produces noisy readings right after a collision. Waiting 1 second lets the physical system stabilize.
5. **Tilt Read** (`detector.py`): `compute_tilt()` calls `read_accel_g()` again and computes `acos(az / mag)`. The `acos` input is clamped to [-1, 1] to prevent `math domain error` from noise.
6. **Stage 2 Gate**: If tilt ≤ 45°, the event is a `"bump"` — no crash. If tilt > 45°, proceed to sustained check.
7. **Sustained Tilt Loop** (`detector.py`): `check_sustained_tilt()` polls tilt every 100ms for 2.0 seconds. If tilt drops below 45° at any sample, it returns `(False, tilt)` — event becomes `"false_alarm"`.
8. **Crash Confirmation**: If all 2.0 seconds of tilt readings stayed above 45°, the crash is confirmed. `last_crash_time` is updated (starting the 30s cooldown). Event label is `"CRASH"`.
9. **Callback** (`alert.py`): `on_crash(peak_g, final_tilt, timestamp)` prints a prominent `CRASH DETECTED` banner to stdout with the peak g-force, tilt angle, and timestamp. This is immediately visible in the SSH terminal on the operator's laptop.
10. **CSV Row**: The post-decision reading is logged with the final event label so the CSV contains both the trigger sample and the outcome sample.

---

## 5. CSV Output Format

Generated by `python3 main.py --log <file.csv>`.

### Columns

| Column        | Type   | Description                                                    |
| ------------- | ------ | -------------------------------------------------------------- |
| `timestamp` | float  | Unix epoch with millisecond precision (e.g.`1706234567.123`) |
| `ax`        | float  | X-axis acceleration in g (calibrated)                          |
| `ay`        | float  | Y-axis acceleration in g (calibrated)                          |
| `az`        | float  | Z-axis acceleration in g (calibrated)                          |
| `magnitude` | float  | `sqrt(ax² + ay² + az²)` in g                              |
| `event`     | string | Event classification (see below), empty for normal samples     |

### Event Values

| Value           | Meaning                                                               |
| --------------- | --------------------------------------------------------------------- |
| *(empty)*     | Normal sample — no detection event                                   |
| `impact`      | Stage 1 triggered: magnitude exceeded 4.0g                            |
| `bump`        | Impact detected but tilt was < 45° — likely a pothole or speed bump |
| `false_alarm` | Impact + initial tilt detected, but tilt did not sustain for 2s       |
| `CRASH`       | Confirmed crash — both stages passed                                 |

### Using CSV Data for Presentations

1. **Transfer**: `scp pi@bikebox.local:~/bikebox/demo.csv .`
2. **Open** in Excel, Google Sheets, or Python (pandas/matplotlib)
3. **Plot**: magnitude column (Y-axis) vs timestamp (X-axis)
   - Normal riding: flat line at ~1.0g
   - Bump event: spike to 2–4g, then back to 1.0g
   - Crash event: spike to 4g+, followed by a different baseline (tilted)
4. **Annotate**: Filter rows where `event` is non-empty to mark detection points on the plot
5. **Timeline**: Convert timestamps to relative seconds from the first row for a cleaner X-axis

Example matplotlib snippet:

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("demo.csv")
df["t"] = df["timestamp"] - df["timestamp"].iloc[0]  # relative time

plt.figure(figsize=(12, 4))
plt.plot(df["t"], df["magnitude"], linewidth=0.5)
plt.axhline(y=4.0, color="r", linestyle="--", label="Impact threshold")

crashes = df[df["event"] == "CRASH"]
plt.scatter(crashes["t"], crashes["magnitude"], color="red", zorder=5, label="CRASH")

plt.xlabel("Time (s)")
plt.ylabel("Acceleration (g)")
plt.title("BikeBox Demo — Acceleration Over Time")
plt.legend()
plt.tight_layout()
plt.savefig("demo_plot.png", dpi=150)
plt.show()
```

---

## 6. Configuration & Tuning

All parameters are defined as constants at the top of `detector.py`.

### Parameter Reference

| Parameter               | Default | Unit    | Effect of Increasing                    | Effect of Decreasing                  |
| ----------------------- | ------- | ------- | --------------------------------------- | ------------------------------------- |
| `IMPACT_THRESHOLD`    | 4.0     | g       | Fewer triggers, may miss light crashes  | More triggers, more false positives   |
| `TILT_THRESHOLD`      | 45.0    | degrees | Requires more severe tilt to confirm    | Triggers on smaller tilts             |
| `CONFIRM_WINDOW`      | 1.0     | seconds | More settling time, slower response     | Faster but noisier tilt readings      |
| `SUSTAINED_TILT_TIME` | 2.0     | seconds | Fewer false alarms, slower confirmation | Faster but less reliable confirmation |
| `COOLDOWN_TIME`       | 30.0    | seconds | Longer gap between alerts               | May re-trigger on same incident       |
| `POLL_RATE`           | 0.01    | seconds | Slower sampling, lower CPU              | Faster sampling, higher CPU           |

### Recommended Presets

**Urban commuting** (default — optimized for low false positives):

```python
IMPACT_THRESHOLD    = 4.0
TILT_THRESHOLD      = 45.0
SUSTAINED_TILT_TIME = 2.0
```

**Mountain biking** (rougher terrain, higher baseline forces):

```python
IMPACT_THRESHOLD    = 6.0    # trail bumps can hit 4–5g
TILT_THRESHOLD      = 60.0   # aggressive cornering tilts more
SUSTAINED_TILT_TIME = 3.0    # give more time to recover from drops
```

**Demo / testing** (easier to trigger for demonstrations):

```python
IMPACT_THRESHOLD    = 2.0    # a hard table slap will trigger
TILT_THRESHOLD      = 30.0   # gentle tilt sufficient
SUSTAINED_TILT_TIME = 1.0    # faster confirmation
```

### How to Change Parameters

Edit the constants at the top of `detector.py`, save, and restart. No recompilation or reconfiguration needed. Future versions will support a config file or CLI flags.

---

## 7. Future Integration Points

### BLE Notification (replaces terminal print)

**What changes**: Only `alert.py`.

- `on_crash()` will send a GATT notification instead of (or in addition to) printing to the terminal.
- A 30-second grace period will be added: start a countdown, poll the cancel button, and only send the BLE alert if the button is not pressed.
- The callback signature `on_crash(peak_g, tilt_angle, timestamp)` stays the same — `detector.py` and `main.py` are unaffected.

### Cancel Button (GPIO 27)

**What changes**: Only `alert.py`.

- `GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_UP)` added to a new `setup_gpio()` function in `alert.py`.
- Inside `on_crash()`: loop for 30 seconds checking `GPIO.input(27)`. If pressed (LOW), cancel the alert and reset.
- GPIO 27 is already reserved and unused.

### GPS Location

**What changes**: New file `gps.py` + minor addition to `main.py`.

- A background thread reads `/dev/serial0` at 9600 baud using `pyserial` + `pynmea2`.
- Stores last-known `{"lat": ..., "lon": ...}` in a shared dict.
- `on_crash()` reads the dict to include coordinates in the alert payload.
- The detector loop and IMU driver are completely unaffected.

### Camera Video Buffer

**What changes**: New file `camera.py` + trigger call from `alert.py`.

- `picamera2` with `CircularOutput` maintains a 15-second rolling buffer.
- On crash confirmation, the buffer is flushed to a file (e.g., `crash_20260223_143200.h264`).
- `on_crash()` calls `camera.save_clip()` alongside the BLE/terminal alert.
- No changes to `imu.py` or `detector.py`.

### Integration Map

```
                     ┌──────────────┐
                     │  detector.py │  ← NO changes needed
                     └──────┬───────┘
                            │ on_crash(peak_g, tilt, ts)
                            ▼
                     ┌──────────────┐
                     │   alert.py   │  ← BLE, cancel button, camera trigger
                     └──┬───┬───┬───┘
                        │   │   │
              ┌─────────┘   │   └─────────┐
              ▼             ▼             ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │   BLE    │ │  Cancel  │ │  Camera  │
        │ (BlueZ)  │ │  Button  │ │  Buffer  │
        │          │ │ (GPIO27) │ │(picamera)│
        └──────────┘ └──────────┘ └──────────┘

        ┌──────────┐
        │  gps.py  │  ← background thread, shared dict
        └──────────┘
            ▲ read by on_crash() for lat/lon
```

Every future feature plugs in at `alert.py` or as a new standalone module. The core pipeline (`imu.py` → `detector.py`) remains untouched.
