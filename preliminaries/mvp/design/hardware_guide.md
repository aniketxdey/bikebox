# BikeBox Hardware Guide

**Team 1 | ENGS 21 | Dartmouth College**

---

## Table of Contents

1. [Bill of Materials](#1-bill-of-materials)
2. [Wiring Diagram](#2-wiring-diagram)
3. [Step-by-Step Assembly](#3-step-by-step-assembly)
4. [Pi Setup from Scratch](#4-pi-setup-from-scratch)
5. [Deploying the MVP Code](#5-deploying-the-mvp-code)
6. [Verification and Testing Sequence](#6-verification-and-testing-sequence)
7. [Demo Experiment Protocol](#7-demo-experiment-protocol)
8. [Auto-Start on Boot](#8-auto-start-on-boot)
9. [Physical Layout Sketch](#9-physical-layout-sketch)
10. [Troubleshooting Table](#10-troubleshooting-table)

---

## 1. Bill of Materials

| # | Component                         | Role                                                | Qty | Required Accessories                             |
| - | --------------------------------- | --------------------------------------------------- | --- | ------------------------------------------------ |
| 1 | Raspberry Pi Zero 2 W             | Main computer (quad-core ARM, WiFi, BT 4.2)         | 1   | Header pins (solder yourself, or use WH variant) |
| 2 | PiSugar 3 (1200mAh)               | Battery module -- pogo-pin connection underneath Pi | 1   | M2.5 screws (included)                           |
| 3 | HiLetgo GY-521 (MPU-6050)         | 6-axis IMU -- 3-axis accel + 3-axis gyro            | 1   | 5x DuPont jumper wires (F-F)                     |
| 4 | MakerFocus GT-U7 GPS              | NEO-6M compatible GPS -- UART 9600 baud             | 1   | 4x DuPont jumper wires (future)                  |
| 5 | Raspberry Pi Camera Module 3 Wide | 120 deg FOV camera (IMX708, CSI)                    | 1   | 15-to-22 pin FFC cable (included)                |
| 6 | SanDisk 64GB MicroSD              | OS and data storage                                 | 1   | MicroSD adapter for flashing                     |
| 7 | DuPont jumper wires (F-F)         | Header-to-sensor connections                        | ~10 | Mixed colors recommended                         |
| 8 | Copper heatsink                   | Thermal management for Pi SoC                       | 1   | Adhesive-backed (included with many Pi kits)     |

**For MVP, you need items 1-3, 6, and 7.** Items 4 and 5 are wired later. Crash alerts display in the SSH terminal -- no LED or resistor needed.

> **Battery life note:** The PiSugar 3 (1200mAh) provides roughly 1.6 hours at continuous peak load per Mason's power analysis. This is sufficient for the MVP demo (~5 minutes) and bench testing, but falls short of the >4-hour field target from the project proposal. For extended field deployments, use an Anker 10000mAh USB power bank connected via USB-C, which provides 13+ hours of runtime.

---

## 2. Wiring Diagram

### Pin Reference Table

| Physical Pin | BCM GPIO     | Function               | Component          | Wire Color (suggested) |
| ------------ | ------------ | ---------------------- | ------------------ | ---------------------- |
| Pin 1        | 3.3V         | Power / AD0 pull-up    | MPU-6050 AD0       | Orange                 |
| Pin 2        | 5V           | Sensor power           | MPU-6050 VCC       | Red                    |
| Pin 3        | GPIO 2       | I2C SDA                | MPU-6050 SDA       | Blue                   |
| Pin 5        | GPIO 3       | I2C SCL                | MPU-6050 SCL       | Yellow                 |
| Pin 6        | GND          | Sensor ground          | MPU-6050 GND       | Black                  |
| Pin 4        | 5V           | GPS power              | GT-U7 VCC (future) | Red                    |
| Pin 8        | GPIO 14 (TX) | UART TX                | GT-U7 RX (future)  | White                  |
| Pin 9        | GND          | GPS ground             | GT-U7 GND (future) | Black                  |
| Pin 10       | GPIO 15 (RX) | UART RX                | GT-U7 TX (future)  | Green                  |
| Pin 13       | GPIO 27      | Cancel button (future) | Button signal      | --                     |

### ASCII Wiring Diagram

```
Raspberry Pi Zero 2 W (top view, USB ports at bottom)
+----------------------------------------------+
|  o  o  o  o  o  o  o  o  o  o  o  o  o      |
|  1  3  5  7  9  11 13 15 17 19 21 23 25      | (odd pins)
|  2  4  6  8  10 12 14 16 18 20 22 24 26      | (even pins)
|  o  o  o  o  o  o  o  o  o  o  o  o  o      |
|                                              |
|  [CSI]            [SoC + heatsink]           |
|                                              |
|           [micro-USB]  [mini-HDMI]           |
+----------------------------------------------+

MPU-6050 (GY-521)
+-------------+
|  VCC -------+-- Pin 2  (5V)
|  GND -------+-- Pin 6  (GND)
|  SDA -------+-- Pin 3  (GPIO 2)
|  SCL -------+-- Pin 5  (GPIO 3)
|  AD0 -------+-- Pin 1  (3.3V)  <-- CRITICAL
|  INT        |   (not connected)
|  XDA        |   (not connected)
|  XCL        |   (not connected)
+-------------+

GT-U7 GPS (future)
+-------------+
|  VCC -------+-- Pin 4  (5V)
|  GND -------+-- Pin 9  (GND)
|  TX  -------+-- Pin 10 (GPIO 15 / RX)   <-- crossover!
|  RX  -------+-- Pin 8  (GPIO 14 / TX)   <-- crossover!
+-------------+
```

### Critical: AD0 to 3.3V Wire (required when PiSugar is connected)

The orange wire from MPU-6050 AD0 to Pin 1 (3.3V) shifts the sensor from 0x68 to **0x69**, avoiding a conflict with the PiSugar 3 battery (which also uses 0x68).

- **Without PiSugar attached:** AD0 wire is optional. `imu.py` auto-detects the sensor at 0x68.
- **With PiSugar attached:** AD0 wire is **required**. Without it, both devices share 0x68 and corrupt each other's I2C traffic.

Verify with `sudo i2cdetect -y 1`. With PiSugar + AD0 wired, you should see `57`, `68`, and `69`.

---

## 3. Step-by-Step Assembly

### 3.1 Connecting PiSugar 3 to Pi

1. Place the PiSugar 3 board face-down on your work surface.
2. Align the Raspberry Pi Zero 2 W on top with the four screw holes matching.
3. The pogo pins on the PiSugar should contact the underside of the Pi's GPIO pads (near pins 1-6).
4. Press down gently and secure with the included M2.5 screws (4 corners).
5. If the Pi doesn't power on, remove it and clean the pogo pin contacts and Pi pad area with isopropyl alcohol on a cotton swab. Let dry, then reassemble.

The PiSugar provides power and I2C communication through the pogo pins. The entire 40-pin header remains free for sensors.

> **Important -- PiSugar and I2C address conflict:** The PiSugar 3 uses I2C addresses 0x57 (RTC) and 0x68 (battery gauge). The MPU-6050 also defaults to 0x68. When both are connected, you **must** wire the MPU-6050 AD0 pin to Pi Pin 1 (3.3V) to shift it to 0x69. Without PiSugar, the default 0x68 is fine -- `imu.py` auto-detects the correct address.

> **Power source options:** You can power the Pi via PiSugar battery, micro-USB cable, or USB-C power bank. The IMU wiring is identical regardless of power source -- the GPIO header pins do not change. For initial setup and testing, USB power is convenient. Switch to PiSugar for untethered field use.

### 3.2 Wiring MPU-6050 (5 wires)

Use female-to-female DuPont jumper wires. Plug directly from the GY-521 header pins to the Pi's GPIO header.

| Step | From (GY-521) | To (Pi)        | Wire   | Note                                     |
| ---- | ------------- | -------------- | ------ | ---------------------------------------- |
| 1    | VCC           | Pin 2 (5V)     | Red    | GY-521 has onboard regulator; 5V is safe |
| 2    | GND           | Pin 6 (GND)    | Black  | Common ground                            |
| 3    | SDA           | Pin 3 (GPIO 2) | Blue   | I2C data line                            |
| 4    | SCL           | Pin 5 (GPIO 3) | Yellow | I2C clock line                           |
| 5    | AD0           | Pin 1 (3.3V)   | Orange | **Sets address to 0x69**           |

Leave INT, XDA, and XCL unconnected.

### 3.3 Connecting Camera (future)

1. Locate the CSI connector on the Pi Zero 2 W (small black clip near one edge).
2. Gently lift the black tab straight up (it's a friction-fit latch, not a hinge).
3. Insert the **22-pin end** of the 15-to-22 pin FFC cable, **contacts facing the PCB** (toward the Pi board).
4. Press the black tab back down to lock the cable.
5. Connect the 15-pin end to the Camera Module 3 in the same manner.

### 3.4 Connecting GPS (future)

Four wires with UART crossover:

| From (GT-U7) | To (Pi)               | Note                                 |
| ------------ | --------------------- | ------------------------------------ |
| VCC          | Pin 4 (5V)            | Onboard regulator handles 5V to 3.3V |
| GND          | Pin 9 (GND)           |                                      |
| TX           | Pin 10 (GPIO 15 / RX) | GPS transmit to Pi receive           |
| RX           | Pin 8 (GPIO 14 / TX)  | Pi transmit to GPS receive           |

---

## 4. Pi Setup from Scratch

### 4.1 Flash the SD Card

1. Download **Raspberry Pi Imager** from https://www.raspberrypi.com/software/
2. Insert the 64GB MicroSD card into your computer.
3. In Raspberry Pi Imager:
   - **Device**: Raspberry Pi Zero 2 W
   - **OS**: Raspberry Pi OS (other) -> **Raspberry Pi OS Lite (64-bit)**
   - Click the **gear icon** (Edit Settings) and configure:
     - **Hostname**: `bikebox`
     - **Enable SSH**: Yes, use password authentication
     - **Username**: `pi`, **Password**: choose something memorable
     - **WiFi SSID**: your network name (e.g. your home WiFi)
     - **WiFi Password**: your network password
     - **WiFi Country**: `US`
     - **Locale**: US, Eastern time
4. Click **Write** and wait for it to finish.
5. Eject the SD card and insert it into the Pi.

### 4.2 First Boot

1. Power the Pi (PiSugar battery, USB-C power bank, or micro-USB cable).
2. Wait **90-120 seconds** for first boot -- the Pi Zero 2 W is slow.
3. From your laptop (on the same WiFi network), verify the Pi is online:

```bash
ping bikebox.local
```

You should see replies like:

```
64 bytes from 192.168.x.x: icmp_seq=0 ttl=64 time=5.2 ms
```

Press Ctrl+C to stop. If it says "Unknown host" after 2 minutes, see the Troubleshooting section.

### 4.3 SSH In and Update

```bash
ssh pi@bikebox.local
```

Enter your password when prompted. Then update the system:

```bash
sudo apt update && sudo apt upgrade -y
```

This takes 5-10 minutes on the Pi Zero 2 W. Be patient.

### 4.4 Enable I2C with raspi-config

```bash
sudo raspi-config
```

Navigate to **Interface Options** and enable:

| Interface   | Setting                                           | Why                                           |
| ----------- | ------------------------------------------------- | --------------------------------------------- |
| I2C         | Enable                                            | MPU-6050 communication                        |
| Serial Port | Login shell:**No**, Hardware: **Yes** | GPS UART (future, no console interference)    |
| Camera      | Enable (if option appears)                        | Camera Module 3 (may auto-detect on newer OS) |

Reboot when prompted:

```bash
sudo reboot
```

### 4.5 Install Dependencies

SSH back in after reboot (wait ~90 seconds):

```bash
ssh pi@bikebox.local
```

Install the required packages:

```bash
sudo apt install -y python3-smbus2 i2c-tools
pip3 install pytest --break-system-packages
```

---

## 5. Deploying the MVP Code

These steps upload the BikeBox scripts from your laptop to the Pi and verify they are in place. Run all commands from your **laptop's** terminal (not SSH'd into the Pi).

### 5.1 Create the Project Directory

```bash
ssh pi@bikebox.local "mkdir -p ~/bikebox ~/bikebox/tests"
```

### 5.2 Upload All Scripts

From the `mvp/` folder on your laptop:

```bash
cd /path/to/bikebox/mvp

scp imu.py detector.py alert.py main.py pi@bikebox.local:~/bikebox/
scp pytest.ini pi@bikebox.local:~/bikebox/
scp tests/__init__.py tests/conftest.py pi@bikebox.local:~/bikebox/tests/
scp tests/test_imu.py tests/test_detector.py tests/test_alert.py pi@bikebox.local:~/bikebox/tests/
```

Or upload everything in one command:

```bash
scp -r imu.py detector.py alert.py main.py pytest.ini tests pi@bikebox.local:~/bikebox/
```

### 5.3 Verify Files Landed

```bash
ssh pi@bikebox.local "ls -la ~/bikebox/"
```

You should see:

```
alert.py
detector.py
imu.py
main.py
pytest.ini
tests/
```

And check the tests folder:

```bash
ssh pi@bikebox.local "ls ~/bikebox/tests/"
```

Expected:

```
__init__.py
conftest.py
test_alert.py
test_detector.py
test_imu.py
```

### 5.4 Quick Smoke Test

SSH into the Pi and verify Python can import the modules:

```bash
ssh pi@bikebox.local
cd ~/bikebox
python3 -c "import imu; import detector; import alert; print('All modules OK')"
```

If the IMU is not wired yet, you will see an I2C error -- that is expected. The import test just confirms the files are in place and Python can parse them.

---

## 6. Verification and Testing Sequence

Run these commands **on the Pi** (SSH in first: `ssh pi@bikebox.local`). Run them **in order** -- do not skip ahead if a step fails.

### Step 1: Verify I2C Device

```bash
sudo i2cdetect -y 1
```

**What you should see depends on your setup:**

| Setup                              | Expected addresses                                                    |
| ---------------------------------- | --------------------------------------------------------------------- |
| IMU only (no PiSugar, AD0 unwired) | `68`                                                                |
| IMU only (AD0 wired to 3.3V)       | `69`                                                                |
| IMU + PiSugar (AD0 wired to 3.3V)  | `57`, `68` (or `UU`), and `69`                                |
| IMU + PiSugar (AD0 NOT wired)      | `57`, `68` only -- **conflict!** IMU and PiSugar share 0x68 |

**If the bus is completely empty:** wires are loose or I2C is not enabled. See Troubleshooting.

### Step 2: Verify IMU Initialization

```bash
cd ~/bikebox
python3 -c "from imu import IMU; IMU()"
```

The driver auto-detects the IMU address. Expected output (depending on AD0 wiring):

```
MPU-6050 found at 0x69 (WHO_AM_I=0x68)
MPU-6050 initialized at 0x69
```

or, if AD0 is not wired to 3.3V and PiSugar is not connected:

```
MPU-6050 found at 0x68 (WHO_AM_I=0x68)
MPU-6050 initialized at 0x68
```

**If "not found at 0x69 or 0x68" error:** The sensor is not on the bus. Check wiring and run `i2cdetect` again.

**If WHO_AM_I returns 0x70 or 0x71:** The chip is a compatible variant (MPU-6500/9250). The auto-detect handles this -- data reads still work correctly.

### Step 3: Test IMU Live Data

```bash
python3 main.py --test-imu
```

**Expected:** Live readout updating at ~20Hz. At rest on a flat surface:

- AX, AY: near 0.000
- AZ: near 1.000
- Mag: near 1.000
- Tilt: 0-5 degrees

Tilt the sensor and watch values change in real time. Ctrl+C to stop.

### Step 4: Run Automated Tests

```bash
python3 -m pytest tests/ -v -m "not manual"
```

**Expected:** All non-manual tests pass. To also run the manual shake/tilt tests:

```bash
python3 -m pytest tests/ -v
```

### Step 5: Full System Test (Crash Simulation)

```bash
python3 main.py
```

1. Wait for "BikeBox armed."
2. **Smack the table** hard -- should see `IMPACT: X.XXg`
3. **Immediately tilt the sensor** on its side and hold for 3 seconds.
4. **Expected:** `CRASH CONFIRMED` followed by a `CRASH DETECTED` banner with peak g and tilt angle.
5. Ctrl+C to stop.

If the table smack doesn't reach 4.0g, temporarily lower `IMPACT_THRESHOLD` to 2.0 in `detector.py`:

```bash
nano ~/bikebox/detector.py
```

Change `IMPACT_THRESHOLD = 4.0` to `IMPACT_THRESHOLD = 2.0`, save (Ctrl+O, Enter, Ctrl+X), and rerun.

### Step 6: Full System Test with Logging

```bash
python3 main.py --log test_run.csv
```

Repeat the smack+tilt test. Ctrl+C to stop. Verify the CSV was created:

```bash
head -5 test_run.csv
```

You should see the header row and a few data rows with timestamp, ax, ay, az, magnitude, and event columns.

---

## 7. Demo Experiment Protocol

### Preparation

1. Mount the BikeBox device under the bicycle seat in the 3D-printed enclosure.
2. Ensure the PiSugar 3 is charged (green LED on PiSugar = charged).
3. Connect the Pi to WiFi if not already connected (it remembers configured networks automatically).
4. SSH in from your laptop: `ssh pi@bikebox.local`

### Recording

```bash
cd ~/bikebox
python3 main.py --log demo.csv
```

Wait for "BikeBox armed."

### Test Sequence

| Phase        | Duration | Action                                        | Expected Data                                  |
| ------------ | -------- | --------------------------------------------- | ---------------------------------------------- |
| 1. Baseline  | 30s      | Ride normally on flat ground                  | Mag near 1.0g, no events                       |
| 2. Bump test | 10s      | Ride over a speed bump or curb                | Mag spike 2-3g,`bump` event                  |
| 3. Crash sim | 10s      | Dismount, push bike to fall, leave it down 5s | Mag spike 4g+,`CRASH` event + terminal alert |
| 4. Recovery  | 10s      | Pick up bike, ride away                       | Return to ~1.0g baseline                       |

### Data Retrieval

From your laptop (not SSH):

```bash
scp pi@bikebox.local:~/bikebox/demo.csv .
```

### Plotting

Open `demo.csv` in Excel or Google Sheets:

- **X-axis:** timestamp (or convert to relative seconds)
- **Y-axis:** magnitude column
- Add a horizontal line at 4.0g (impact threshold)
- Color-code points by event column

The resulting plot clearly shows three distinct regions: flat baseline, moderate bump spike, and large crash spike with sustained deviation.

---

## 8. Auto-Start on Boot

For field testing without SSH access, configure the system to start automatically.

### Method: /etc/rc.local

```bash
sudo nano /etc/rc.local
```

Add this line **before** `exit 0`:

```bash
/usr/bin/python3 /home/pi/bikebox/main.py --log /home/pi/bikebox/auto.csv &
```

The `&` runs it in the background so boot continues. Data logs to `auto.csv`.

### Verify

```bash
sudo reboot
```

After boot (~90s), check the process:

```bash
ps aux | grep main.py
```

### Stopping

```bash
sudo pkill -f "python3 /home/pi/bikebox/main.py"
```

### Alternative: systemd Service (more robust)

Create `/etc/systemd/system/bikebox.service`:

```
[Unit]
Description=BikeBox Crash Detection
After=multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/bikebox
ExecStart=/usr/bin/python3 main.py --log /home/pi/bikebox/auto.csv
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl enable bikebox
sudo systemctl start bikebox
sudo systemctl status bikebox
```

---

## 9. Physical Layout Sketch

```
TOP VIEW (enclosure lid removed)
+------------------------------------------+
|                                          |
|   +---- Camera Module 3 ----+           |
|   |  [===  lens  ===]       |  <-- facing rear of bike
|   |  15-pin FFC cable down  |           |
|   +-------------------------+           |
|                                          |
|   +-- Raspberry Pi Zero 2 W --+         |
|   |  [GPIO Header]            |         |
|   |   ^ jumper wires to IMU   |         |
|   |                           |         |
|   |  [micro-USB]  [mini-HDMI] |         |
|   +---------------------------+         |
|          | pogo pins                     |
|   +-- PiSugar 3 Battery --------+       |
|   |  1200mAh LiPo               |       |
|   |  [USB-C charge port]        |       |
|   +------------------------------+      |
|   +-- MPU-6050 (GY-521) --+             |
|   |  mounted flat,         |            |
|   |  oriented Z-up         |  <-- critical: Z-axis must point UP
|   |  5 wires to GPIO       |            |
|   +------------------------+            |
|                                          |
|   +-- GT-U7 GPS ----------+             |
|   |  antenna facing UP     |  <-- needs sky view for satellite fix
|   |  4 wires to GPIO       |            |
|   +------------------------+            |
|                                          |
+------------------------------------------+

SIDE VIEW
+----------------------------+
|  Camera (rear-facing)      |  <-- top of enclosure
|  -------------------------  |
|  Pi Zero 2 W               |
|  ==========================  |  <-- pogo pin interface
|  PiSugar 3 Battery         |
|  -------------------------  |
|  MPU-6050 / GPS            |  <-- bottom of enclosure
+----------------------------+
         |
---------+---- seat post clamp
```

**Mounting orientation:** The MPU-6050 must be mounted with its Z-axis pointing UP (toward the sky) when the bike is upright. Calibration assumes this orientation. If mounted differently, the tilt calculation will be incorrect.

---

## 10. Troubleshooting Table

| #  | Symptom                                                    | Likely Cause                                     | Fix                                                                                                                                                                            |
| -- | ---------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1  | `ping bikebox.local` says "Unknown host"                 | Pi not connected to WiFi, or wrong SSID/password | Re-flash with correct WiFi credentials; verify SSID is exact (case-sensitive); ensure WiFi country is set to US                                                                |
| 2  | `ping` works but `ssh` says "Connection refused"       | SSH not enabled                                  | Re-flash with SSH enabled in Raspberry Pi Imager settings                                                                                                                      |
| 3  | `i2cdetect` shows nothing at all                         | I2C not enabled, or wires disconnected           | Run `sudo raspi-config` then Interface Options then I2C then Enable, then reboot. If already enabled, reseat all 4 wires (VCC, GND, SDA, SCL) and try different jumper wires |
| 4  | `i2cdetect` shows 0x68 but NOT 0x69                      | AD0 not wired to 3.3V                            | Fine without PiSugar -- auto-detect uses 0x68. With PiSugar connected, you MUST wire AD0 to Pin 1 (3.3V) to avoid conflict                                                     |
| 5  | `i2cdetect` shows 0x69 but WHO_AM_I returns 0x70 or 0x71 | Compatible variant (MPU-6500 or MPU-9250)        | Auto-detect handles these chip IDs -- no code changes needed                                                                                                                   |
| 5b | IMU + PiSugar both on bus but IMU data garbled             | Both at 0x68 -- I2C address conflict             | Wire AD0 to Pin 1 (3.3V) to shift IMU to 0x69; try a different jumper wire if AD0 doesn't take effect                                                                          |
| 5c | `i2cdetect` shows sensor intermittently                  | Loose DuPont connector on GPIO pin               | Reseat wires firmly; squeeze female connector with pliers to tighten the internal sleeve; try different wire                                                                   |
| 6  | `ModuleNotFoundError: No module named 'smbus2'`          | Library not installed                            | Run `sudo apt install python3-smbus2`                                                                                                                                        |
| 7  | `ModuleNotFoundError: No module named 'pytest'`          | Test framework not installed                     | Run `pip3 install pytest --break-system-packages`                                                                                                                            |
| 8  | IMU reads all zeros                                        | Sensor still in sleep mode                       | Verify `PWR_MGMT_1` write (0x6B = 0x00) in `_init_sensor()`                                                                                                                |
| 9  | IMU magnitude at rest is far from 1.0g                     | Wrong scale factor or range config               | Verify `ACCEL_CONFIG` = 0x18 (plus/minus 16g) and `ACCEL_SCALE` = 2048.0                                                                                                   |
| 10 | Calibration values seem wrong                              | Device was moving during calibration             | Re-run: place on flat, stable surface and keep completely still                                                                                                                |
| 11 | Too many false crash triggers                              | Threshold too low for your surface               | Increase `IMPACT_THRESHOLD` to 5.0 or 6.0 in `detector.py`                                                                                                                 |
| 12 | Never triggers on real crash simulation                    | Threshold too high or tilt check failing         | Lower `IMPACT_THRESHOLD` to 2.0-3.0; check sensor orientation (Z must be UP)                                                                                                 |
| 13 | `scp` fails with "No route to host"                      | Pi and laptop on different networks              | Ensure both are on the same WiFi network                                                                                                                                       |
| 14 | PiSugar not appearing on I2C (0x57 / 0x68)                 | Dirty pogo pin contacts                          | Remove Pi from PiSugar, clean both contact surfaces with isopropyl alcohol, let dry, reassemble                                                                                |
| 15 | Pi won't boot (no green activity LED)                      | SD card not flashed properly                     | Re-flash with Raspberry Pi Imager; try a different SD card                                                                                                                     |
| 16 | `Permission denied` on I2C operations                    | Not running as root / no i2c group membership    | Run with `sudo`, or add user to i2c group: `sudo usermod -aG i2c pi` then re-login                                                                                         |
| 17 | Python crash with `math domain error` in acos            | Noise pushed az/magnitude ratio outside [-1, 1]  | Already handled by clamping in `compute_tilt_from_accel()` -- if seen, check for sensor malfunction                                                                          |
| 18 | GPS shows no data (future)                                 | Console still active on serial port              | `sudo raspi-config` then Serial then Login shell: No, Hardware: Yes, then reboot                                                                                             |
| 19 | Camera error: "no cameras available" (future)              | FFC cable not seated or wrong cable type         | Use 15-to-22 pin FFC cable; contacts must face the PCB; re-seat both ends                                                                                                      |
