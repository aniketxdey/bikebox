"""
config.py — Centralized configuration for the BikeBox system.

All hardware pin assignments, I2C addresses, detection thresholds,
and BLE UUIDs are defined here. Change values here, not in individual modules.
"""

# ─── Hardware: GPIO Pin Assignments (BCM numbering) ───
BUTTON_ENABLED = True
BUTTON_PIN = 26         # Blue multi-function button input with pull-up (physical pin 37)
BUTTON_LED_PIN = 13     # Blue button built-in LED output (physical pin 33)

# ─── Button Press Timing ───
SHORT_PRESS_MAX = 1.0       # Maximum seconds for a short press (→ shutdown)
LONG_HOLD_MIN = 3.0         # Minimum seconds for a long hold (→ cancel)
BUTTON_DEBOUNCE_MS = 200    # Debounce time in milliseconds

# ─── Hardware: I2C Addresses ───
MPU6050_ADDR = 0x69    # IMU (shifted from 0x68 via AD0 → 3.3V)
PISUGAR_ADDR = 0x57    # PiSugar 3 battery management IC
I2C_BUS = 1            # I2C bus number (always 1 on Pi Zero 2)

# ─── Crash Detection Thresholds ───
#
# Stage 1 triggers on EITHER of two paths:
#   Path A: accel magnitude > IMPACT_THRESHOLD (catches hard crashes)
#   Path B: gyro magnitude > GYRO_THRESHOLD AND accel > GYRO_ACCEL_MIN
#           (catches slow-speed tipovers with high rotation but low g-force)
#
IMPACT_THRESHOLD = 1.4     # g-force magnitude to trigger Stage 1 Path A (DEMO — normal: 1.5)
GYRO_THRESHOLD = 80.0      # °/s angular velocity magnitude to trigger Stage 1 Path B (DEMO — normal: 100)
GYRO_ACCEL_MIN = 1.15      # Minimum g-force required alongside gyro trigger (DEMO — normal: 1.2)
TILT_THRESHOLD = 25.0      # Degrees from vertical to confirm crash (DEMO — normal: 30)
CONFIRM_WINDOW = 0.4       # Seconds to wait after impact before checking tilt (DEMO — normal: 0.5)
SUSTAINED_TILT_TIME = 0.7  # Seconds device must remain tilted to confirm crash (DEMO — normal: 1.0)
COOLDOWN_TIME = 10.0       # Seconds between crash detections (DEMO — normal: 10)
POLL_RATE = 0.01           # IMU read interval (100 Hz)

# ─── IMU Configuration ───
ACCEL_RANGE = 3        # 0=±2g, 1=±4g, 2=±8g, 3=±16g
GYRO_RANGE = 3         # 0=±250, 1=±500, 2=±1000, 3=±2000°/s
ACCEL_SENSITIVITY = {0: 16384.0, 1: 8192.0, 2: 4096.0, 3: 2048.0}
GYRO_SENSITIVITY = {0: 131.0, 1: 65.5, 2: 32.8, 3: 16.4}
CALIBRATION_SAMPLES = 200

# ─── Grace Period ───
GRACE_PERIOD_SECONDS = 30  # Countdown duration before alert escalation
GRACE_POLL_INTERVAL = 0.1  # How often to check button / BLE cancel during grace period

# ─── Camera ───
VIDEO_RESOLUTION = (1920, 1080)
VIDEO_FRAMERATE = 30
CIRCULAR_BUFFER_SECONDS = 20
CLIP_POST_CRASH_SECONDS = 5
CLIP_SAVE_DIR = '/home/pi/bikebox/data/clips'
CLIP_FORMAT = 'mp4'

# ─── WiFi Hotspot / Clip Server ───
WIFI_SSID = 'BikeBox'
WIFI_PASSPHRASE = 'bikebox123'
HOTSPOT_IP = '192.168.4.1'
HOTSPOT_TIMEOUT = 300          # Auto-deactivate hotspot after 5 minutes of no download
CLIP_SERVER_HOST = '0.0.0.0'  # Bind to all interfaces (accessible over hotspot or home WiFi)
CLIP_SERVER_PORT = 8080

# ─── BLE Hotspot Control ───
BLE_HOTSPOT_CONTROL_UUID = 'CB000005-0B1C-4E5D-8A9F-1234567890AB'
HOTSPOT_OFF = 0x00
HOTSPOT_ACTIVATING = 0x01
HOTSPOT_ACTIVE = 0x02
HOTSPOT_DEACTIVATING = 0x03

# ─── Battery ───
PISUGAR_BATTERY_REGISTER = 0x2A
PISUGAR_CHARGING_REGISTER = 0x02
BATTERY_LOW_THRESHOLD = 20
BATTERY_CRITICAL_THRESHOLD = 10
BATTERY_SHUTDOWN_THRESHOLD = 5
BATTERY_CHECK_INTERVAL = 60

# ─── BLE GATT UUIDs ───
BLE_SERVICE_UUID = 'CB000001-0B1C-4E5D-8A9F-1234567890AB'
BLE_CRASH_ALERT_UUID = 'CB000002-0B1C-4E5D-8A9F-1234567890AB'
BLE_DEVICE_STATUS_UUID = 'CB000003-0B1C-4E5D-8A9F-1234567890AB'
BLE_GRACE_PERIOD_UUID = 'CB000004-0B1C-4E5D-8A9F-1234567890AB'

# ─── BLE Advertisement ───
BLE_LOCAL_NAME = 'BikeBox'
BLE_HEARTBEAT_INTERVAL = 30

# ─── BLE Alert Types ───
ALERT_CRASH_DETECTED = 0x01
ALERT_CRASH_CANCELLED = 0x02
ALERT_CRASH_CONFIRMED = 0x03

# ─── BLE Grace Period States ───
GRACE_IDLE = 0x00
GRACE_COUNTDOWN = 0x01
GRACE_CANCELLED_BUTTON = 0x02
GRACE_CANCELLED_APP = 0x03

# ─── BLE Device States ───
DEVICE_BOOTING = 0x00
DEVICE_MONITORING = 0x01
DEVICE_GRACE_PERIOD = 0x02
DEVICE_ALERT_SENT = 0x03
DEVICE_LOW_BATTERY = 0x04

# ─── Logging ───
LOG_DIR = '/home/pi/bikebox/data/logs'
LOG_CSV_COLUMNS = ['timestamp', 'ax', 'ay', 'az', 'magnitude', 'gyro', 'event']
