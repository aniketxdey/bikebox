"""test_config.py — Verify config.py constants are consistent and valid."""

from config import (
    BUTTON_PIN, BUTTON_LED_PIN,
    SHORT_PRESS_MAX, LONG_HOLD_MIN, BUTTON_DEBOUNCE_MS,
    MPU6050_ADDR, PISUGAR_ADDR, I2C_BUS,
    IMPACT_THRESHOLD, GYRO_THRESHOLD, GYRO_ACCEL_MIN,
    TILT_THRESHOLD, CONFIRM_WINDOW, SUSTAINED_TILT_TIME, COOLDOWN_TIME, POLL_RATE,
    ACCEL_RANGE, GYRO_RANGE, ACCEL_SENSITIVITY, GYRO_SENSITIVITY,
    GRACE_PERIOD_SECONDS, GRACE_POLL_INTERVAL,
    VIDEO_RESOLUTION, VIDEO_FRAMERATE, CIRCULAR_BUFFER_SECONDS,
    BLE_SERVICE_UUID, BLE_CRASH_ALERT_UUID,
    BLE_DEVICE_STATUS_UUID, BLE_GRACE_PERIOD_UUID,
    ALERT_CRASH_DETECTED, ALERT_CRASH_CANCELLED, ALERT_CRASH_CONFIRMED,
    GRACE_IDLE, GRACE_COUNTDOWN, GRACE_CANCELLED_BUTTON, GRACE_CANCELLED_APP,
    DEVICE_BOOTING, DEVICE_MONITORING,
    LOG_CSV_COLUMNS,
)


class TestGPIOPins:
    """Verify GPIO pin assignments don't conflict."""

    def test_all_gpio_pins_unique(self):
        pins = [BUTTON_PIN, BUTTON_LED_PIN]
        assert len(pins) == len(set(pins)), "GPIO pin conflict detected"

    def test_button_pin_is_26(self):
        assert BUTTON_PIN == 26

    def test_button_led_pin_is_13(self):
        assert BUTTON_LED_PIN == 13


class TestI2CAddresses:
    """Verify I2C addresses don't conflict."""

    def test_imu_and_pisugar_different_addresses(self):
        assert MPU6050_ADDR != PISUGAR_ADDR

    def test_imu_address_is_0x69(self):
        assert MPU6050_ADDR == 0x69

    def test_pisugar_address_is_0x57(self):
        assert PISUGAR_ADDR == 0x57

    def test_i2c_bus_is_1(self):
        assert I2C_BUS == 1


class TestDetectionThresholds:
    """Verify thresholds are in valid ranges."""

    def test_impact_threshold_positive(self):
        assert IMPACT_THRESHOLD > 0

    def test_impact_threshold_reasonable(self):
        assert 1.0 <= IMPACT_THRESHOLD <= 10.0

    def test_gyro_threshold_positive(self):
        assert GYRO_THRESHOLD > 0

    def test_gyro_accel_min_less_than_impact(self):
        assert GYRO_ACCEL_MIN <= IMPACT_THRESHOLD

    def test_tilt_threshold_between_0_and_90(self):
        assert 0 < TILT_THRESHOLD < 90

    def test_sustained_tilt_time_positive(self):
        assert SUSTAINED_TILT_TIME > 0

    def test_cooldown_time_positive(self):
        assert COOLDOWN_TIME > 0

    def test_poll_rate_gives_at_least_50hz(self):
        assert POLL_RATE <= 0.02


class TestButtonTiming:
    """Verify button timing makes physical sense."""

    def test_short_press_max_less_than_long_hold_min(self):
        assert SHORT_PRESS_MAX < LONG_HOLD_MIN

    def test_debounce_positive(self):
        assert BUTTON_DEBOUNCE_MS > 0


class TestSensitivityMaps:
    """Verify sensitivity lookup tables are complete."""

    def test_accel_sensitivity_has_all_ranges(self):
        for i in range(4):
            assert i in ACCEL_SENSITIVITY

    def test_gyro_sensitivity_has_all_ranges(self):
        for i in range(4):
            assert i in GYRO_SENSITIVITY

    def test_accel_range_valid(self):
        assert ACCEL_RANGE in ACCEL_SENSITIVITY

    def test_gyro_range_valid(self):
        assert GYRO_RANGE in GYRO_SENSITIVITY


class TestBLEUUIDs:
    """Verify BLE UUIDs are properly formatted and unique."""

    def test_all_uuids_unique(self):
        uuids = [BLE_SERVICE_UUID, BLE_CRASH_ALERT_UUID,
                 BLE_DEVICE_STATUS_UUID, BLE_GRACE_PERIOD_UUID]
        assert len(uuids) == len(set(uuids))

    def test_uuids_correct_length(self):
        for uuid in [BLE_SERVICE_UUID, BLE_CRASH_ALERT_UUID,
                     BLE_DEVICE_STATUS_UUID, BLE_GRACE_PERIOD_UUID]:
            assert len(uuid) == 36  # UUID with hyphens


class TestAlertTypes:
    """Verify BLE protocol constants are distinct."""

    def test_alert_types_distinct(self):
        types = [ALERT_CRASH_DETECTED, ALERT_CRASH_CANCELLED, ALERT_CRASH_CONFIRMED]
        assert len(types) == len(set(types))

    def test_grace_states_distinct(self):
        states = [GRACE_IDLE, GRACE_COUNTDOWN, GRACE_CANCELLED_BUTTON, GRACE_CANCELLED_APP]
        assert len(states) == len(set(states))

    def test_device_states_include_monitoring(self):
        assert DEVICE_MONITORING == 0x01


class TestLogging:
    """Verify CSV column definitions."""

    def test_csv_columns_include_required_fields(self):
        required = ['timestamp', 'ax', 'ay', 'az', 'magnitude', 'gyro', 'event']
        for col in required:
            assert col in LOG_CSV_COLUMNS


class TestCameraConfig:
    """Verify camera configuration is reasonable."""

    def test_video_resolution_tuple(self):
        assert len(VIDEO_RESOLUTION) == 2
        assert VIDEO_RESOLUTION[0] > 0
        assert VIDEO_RESOLUTION[1] > 0

    def test_framerate_positive(self):
        assert VIDEO_FRAMERATE > 0

    def test_circular_buffer_positive(self):
        assert CIRCULAR_BUFFER_SECONDS > 0


class TestGracePeriod:
    """Verify grace period config."""

    def test_grace_period_positive(self):
        assert GRACE_PERIOD_SECONDS > 0

    def test_grace_poll_interval_sub_second(self):
        assert GRACE_POLL_INTERVAL < 1.0
