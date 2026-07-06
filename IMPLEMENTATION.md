# BikeBox Implementation Guide

**From bare parts to a fully running bicycle crash detection system.**

Dartmouth ENGS 21 — Team 1 | March 2026

---

## Table of Contents

1. [Prerequisites and Required Materials](#1-prerequisites-and-required-materials)
2. [Phase 1 — Flash and Boot the Raspberry Pi](#2-phase-1--flash-and-boot-the-raspberry-pi)
3. [Phase 2 — SSH In and Configure the OS](#3-phase-2--ssh-in-and-configure-the-os)
4. [Phase 3 — Wire All Hardware Components](#4-phase-3--wire-all-hardware-components)
5. [Phase 4 — Verify Every Hardware Connection](#5-phase-4--verify-every-hardware-connection)
6. [Phase 5 — Install Software Dependencies](#6-phase-5--install-software-dependencies)
7. [Phase 6 — Deploy the BikeBox Python Code](#7-phase-6--deploy-the-bikebox-python-code)
8. [Phase 7 — Run Unit Tests](#8-phase-7--run-unit-tests)
9. [Phase 8 — Run Hardware Self-Tests](#9-phase-8--run-hardware-self-tests)
10. [Phase 9 — Set Up the Systemd Service (Auto-Start)](#10-phase-9--set-up-the-systemd-service-auto-start)
11. [Phase 10 — Build and Deploy the iOS Companion App](#11-phase-10--build-and-deploy-the-ios-companion-app)
12. [Phase 11 — Pair the iOS App to the Pi](#12-phase-11--pair-the-ios-app-to-the-pi)
13. [Phase 12 — Run Full System Detection](#13-phase-12--run-full-system-detection)
14. [Phase 13 — Integration and Field Testing](#14-phase-13--integration-and-field-testing)
15. [Complete Troubleshooting Reference](#15-complete-troubleshooting-reference)
16. [Quick Reference Card](#16-quick-reference-card)

---

## 1. Prerequisites and Required Materials

### 1.1 Hardware You Need

| #  | Component              | Exact Model                              | Where to Get It |
| -- | ---------------------- | ---------------------------------------- | --------------- |
| 1  | Raspberry Pi Zero 2 WH | Pre-soldered headers variant             | Adafruit        |
| 2  | IMU Sensor             | HiLetgo GY-521 (MPU-6050)                | Amazon          |
| 3  | Camera                 | Arducam 5MP OV5647 160° Wide Angle      | Amazon          |
| 4  | Battery + UPS          | PiSugar 3 for Pi Zero (1200mAh)          | PiSugar         |
| 5  | External Power Bank    | Anker PowerCore 10000mAh USB-C           | Amazon          |
| 6  | MicroSD Card           | SanDisk High Endurance 64GB A2 U3        | Amazon          |
| 7  | Push Button            | Adafruit 1477 — 16mm Blue LED Momentary | Adafruit        |
| 8  | Resistor               | 1 × 10kΩ (for button LED)              | Lab stock       |
| 9  | CSI Cable              | 22-pin to 15-pin FFC adapter             | Amazon          |
| 10 | Jumper Wires           | 10 × Male-to-female Dupont cables       | Lab stock       |

### 1.2 Tools You Need

- A computer (Mac, Windows, or Linux) with an SD card reader or USB adapter
- Raspberry Pi Imager (free download from raspberrypi.com)
- A Wi-Fi network the Pi can join (2.4GHz — Pi Zero 2 W does not support 5GHz)
- A Mac with Xcode 15+ installed (for the iOS companion app)
- An iPhone running iOS 16+ (BLE requires a physical device, not the simulator)
- An Apple Developer account (free tier works for personal device deployment)
- A small Phillips screwdriver (for PiSugar 3 mounting screws)
- Optional: multimeter for verifying voltages

### 1.3 Software You Need on Your Computer

| Software              | Purpose                  | Install                                       |
| --------------------- | ------------------------ | --------------------------------------------- |
| Raspberry Pi Imager   | Flash OS to SD card      | https://www.raspberrypi.com/software/         |
| Terminal / SSH client | Remote access to Pi      | Built into macOS/Linux; PuTTY on Windows      |
| Xcode 15+             | Build and deploy iOS app | Mac App Store                                 |
| Git                   | Clone project repository | `brew install git` (macOS) or pre-installed |

---

## 2. Phase 1 — Flash and Boot the Raspberry Pi

### Step 2.1 — Download and Install Raspberry Pi Imager

1. Go to https://www.raspberrypi.com/software/
2. Download Raspberry Pi Imager for your operating system
3. Install and open it

### Step 2.2 — Flash the SD Card

1. Insert your 64GB microSD card into your computer's card reader
2. In Raspberry Pi Imager:

   - **Choose Device**: Raspberry Pi Zero 2 W
   - **Choose OS**: Raspberry Pi OS (other) → **Raspberry Pi OS Lite (64-bit)** — select the **Bookworm** release
   - **Choose Storage**: Select your microSD card
3. Click the **gear icon** or "Edit Settings" to open advanced options. Configure ALL of the following:

| Setting                | Value                            | Why                             |
| ---------------------- | -------------------------------- | ------------------------------- |
| Set hostname           | `bikebox`                      | Allows `ssh pi@bikebox.local` |
| Enable SSH             | Yes, use password authentication | Headless access                 |
| Set username           | `pi`                           | Standard Pi username            |
| Set password           | (your choice — remember it)     | SSH login                       |
| Configure wireless LAN | Your Wi-Fi SSID + password       | Network access                  |
| Wireless LAN country   | US (or your country)             | Regulatory compliance           |
| Set locale settings    | Your timezone, keyboard layout   | Correct timestamps              |

4. Click **Save**, then **Write**
5. Wait for the write and verification to complete (takes 3–8 minutes)
6. Eject the SD card

### Step 2.3 — First Boot

1. Insert the microSD card into the Raspberry Pi Zero 2 WH
2. If you have the PiSugar 3 already attached, press its power button to boot. Otherwise, connect a micro-USB power cable to the Pi's **power** port (the one labeled "PWR", not "USB")
3. Wait **60–90 seconds** for the first boot to complete. The Pi will:
   - Expand the filesystem
   - Generate SSH keys
   - Connect to your Wi-Fi network
   - The green activity LED on the Pi will flicker during boot and stabilize when ready

### Step 2.4 — Verify Network Connectivity

From your computer's terminal:

```bash
ping bikebox.local
```

Expected output:

```
PING bikebox.local (192.168.x.x): 56 data bytes
64 bytes from 192.168.x.x: icmp_seq=0 ttl=64 time=5.234 ms
```

If `bikebox.local` doesn't resolve:

- Wait another 30 seconds and try again
- Try `ping raspberrypi.local` (fallback hostname)
- Check your router's admin page for connected devices and find the Pi's IP address
- If nothing works, re-flash the SD card and double-check the Wi-Fi credentials

---

## 3. Phase 2 — SSH In and Configure the OS

### Step 3.1 — Connect via SSH

```bash
ssh pi@bikebox.local
```

When prompted "Are you sure you want to continue connecting?", type `yes` and press Enter. Enter the password you set in Step 2.2.

You should see:

```
pi@bikebox:~ $
```

**All remaining commands in this guide are run inside this SSH session unless otherwise stated.**

### Step 3.2 — Update the System

```bash
sudo apt update && sudo apt full-upgrade -y
```

This takes 3–10 minutes. Wait for it to complete.

### Step 3.3 — Enable Hardware Interfaces via raspi-config

```bash
sudo raspi-config
```

Use arrow keys and Enter to navigate:

1. Select **Interface Options** → **I2C** → **Yes** → **OK**
2. Select **Interface Options** → **Camera** → **Yes** (if this option appears) → **OK**
3. Select **Interface Options** → **SSH** → **Yes** → **OK** (should already be enabled)
4. Select **Finish** → When asked to reboot, select **Yes**

Wait 30 seconds, then reconnect:

```bash
ssh pi@bikebox.local
```

### Step 3.4 — Edit Boot Configuration

```bash
sudo nano /boot/firmware/config.txt
```

Scroll to the bottom of the file (hold the down arrow key, or press `Ctrl+End`). Add these exact lines at the very end:

```ini
# BikeBox hardware configuration
dtparam=i2c_arm=on
dtparam=i2c_arm_baudrate=400000

# Enable camera (libcamera stack — not legacy picamera)
camera_auto_detect=1
```

Save and exit:

1. Press `Ctrl+O` (write out)
2. Press `Enter` (confirm filename)
3. Press `Ctrl+X` (exit nano)

**CRITICAL**: Do NOT add `dtoverlay=disable-bt` anywhere in this file. That would disable Bluetooth entirely, breaking the BLE crash alert system.

**CRITICAL**: Do NOT add `start_x=1`. That is for the legacy `picamera` library; BikeBox uses `picamera2` which relies on the `libcamera` stack.

Verify your edits:

```bash
grep -E 'i2c_arm|camera_auto_detect' /boot/firmware/config.txt
```

Expected output:

```
dtparam=i2c_arm=on
dtparam=i2c_arm_baudrate=400000
camera_auto_detect=1
```

Also verify Bluetooth is NOT disabled:

```bash
grep 'disable-bt' /boot/firmware/config.txt
```

This should return **nothing** (no output). If it shows a line, edit the file again and delete that line.

### Step 3.5 — Enable BlueZ Experimental Mode

The BLE GATT server requires BlueZ's experimental features for the LE Advertising Manager API.

```bash
sudo nano /lib/systemd/system/bluetooth.service
```

Find the `ExecStart` line. Press `Ctrl+W`, type `ExecStart`, press Enter.

You will see:

```
ExecStart=/usr/libexec/bluetooth/bluetoothd
```

Add ` --experimental` to the end of that line so it reads:

```
ExecStart=/usr/libexec/bluetooth/bluetoothd --experimental
```

Save and exit: `Ctrl+O`, `Enter`, `Ctrl+X`.

Reload systemd and restart Bluetooth:

```bash
sudo systemctl daemon-reload
sudo systemctl restart bluetooth
```

### Step 3.6 — Reboot and Reconnect

```bash
sudo reboot
```

Wait 30 seconds, then:

```bash
ssh pi@bikebox.local
```

### Step 3.7 — Add User to Required Groups

```bash
sudo usermod -aG gpio,i2c,video,bluetooth pi
```

Verify:

```bash
groups pi
```

Expected output should include: `gpio i2c video bluetooth`

---

## 4. Phase 3 — Wire All Hardware Components

**POWER OFF THE PI BEFORE WIRING.** Run `sudo shutdown -h now`, wait 10 seconds for the Pi's activity LED to stop blinking, then disconnect power.

### 4.0 — GPIO Header Reference

When looking at the Pi Zero 2 WH with the USB ports facing you and the GPIO header on top, the pins are numbered:

```
         GPIO Header (looking down from above)
         ┌──────────────────┐
  Pin 1  │ ●              ● │  Pin 2
  Pin 3  │ ●              ● │  Pin 4
  Pin 5  │ ●              ● │  Pin 6
  Pin 7  │ ●              ● │  Pin 8
  Pin 9  │ ●              ● │  Pin 10
  Pin 11 │ ●              ● │  Pin 12
         │     ... etc      │
  Pin 39 │ ●              ● │  Pin 40
         └──────────────────┘
  (Odd pins on left, even pins on right)
```

Pin 1 is marked with a small square pad on the PCB. Odd-numbered pins run down the left column; even-numbered pins run down the right column.

### 4.1 — Mount the PiSugar 3 Battery

The PiSugar 3 connects via **pogo pins on the back of the Pi** — no GPIO wires needed.

1. Place the PiSugar 3 board behind the Raspberry Pi Zero 2 WH
2. Align the four mounting holes and the pogo pin contacts
3. Secure with the 4 included screws (Phillips head)
4. The pogo pins provide: 5V power, GND, I2C SDA (GPIO 2), and I2C SCL (GPIO 3)
5. Charge the PiSugar 3 fully via its USB-C port before proceeding

The PiSugar 3 occupies I2C addresses **0x57** (battery management) and **0x68** (RTC). This is why the MPU-6050 must be shifted to 0x69 in the next step.

### 4.2 — Wire the MPU-6050 IMU

The GY-521 breakout board has 8 pins in a row. You will use 5 of them.

**Wire each connection with a female-to-female Dupont jumper:**

| MPU-6050 Pin | → | Pi Physical Pin |    BCM GPIO    | Wire Color | Purpose                                                  |
| :-----------: | :-: | :-------------: | :------------: | :--------: | -------------------------------------------------------- |
| **VCC** | → | **Pin 2** |  — (5V rail)  |    Red    | Power supply (GY-521 has onboard 3.3V regulator)         |
| **GND** | → | **Pin 6** |    — (GND)    |   Black   | Ground                                                   |
| **SCL** | → | **Pin 5** |     GPIO 3     |   Yellow   | I2C clock                                                |
| **SDA** | → | **Pin 3** |     GPIO 2     |    Blue    | I2C data                                                 |
| **AD0** | → | **Pin 1** | — (3.3V rail) |    Red    | Address select: pulls HIGH → shifts I2C address to 0x69 |

**Leave disconnected:** XDA, XCL, INT (not used)

**CRITICAL — AD0 MUST be wired to 3.3V (Pin 1).** Without this wire:

- The MPU-6050 defaults to I2C address 0x68
- The PiSugar 3's RTC is also at 0x68
- Both devices will collide on the I2C bus and neither will work

**Wiring procedure:**

1. Locate Pin 1 on the Pi header (top-left corner, marked with a square solder pad on the PCB)
2. Connect a red jumper from MPU-6050 **VCC** to Pi **Pin 2** (immediately to the right of Pin 1)
3. Connect a black jumper from MPU-6050 **GND** to Pi **Pin 6** (third pin down on the right column)
4. Connect a yellow jumper from MPU-6050 **SCL** to Pi **Pin 5** (third pin down on the left column)
5. Connect a blue jumper from MPU-6050 **SDA** to Pi **Pin 3** (second pin down on the left column)
6. Connect a red jumper from MPU-6050 **AD0** to Pi **Pin 1** (top-left corner, 3.3V)

**Double-check before powering on:**

- [ ] VCC goes to Pin 2 (5V), NOT Pin 1 (3.3V). The GY-521 breakout board has its own voltage regulator; feeding 5V is correct.
- [ ] AD0 goes to Pin 1 (3.3V), NOT Pin 2 (5V). AD0 is a logic-level input; 3.3V is correct.
- [ ] SDA goes to Pin 3 (an odd pin on the left), NOT Pin 4 (5V on the right)
- [ ] SCL goes to Pin 5 (an odd pin on the left), NOT Pin 6 (GND on the right)

### 4.3 — Connect the Camera Module

1. Locate the CSI camera connector on the Pi Zero 2 WH. It is the small ribbon cable connector between the mini-HDMI port and the micro-USB ports.
2. If your camera has a standard 15-pin ribbon cable and the Pi Zero has a 22-pin connector, use a **22-to-15 pin FFC adapter cable**:
   - The 22-pin end plugs into the Pi
   - The 15-pin end plugs into the camera module
3. To insert the cable into the Pi's CSI connector:
   - Gently lift the black plastic clamp by pulling it upward (away from the PCB) with your fingernails. It only lifts about 1–2mm.
   - Slide the ribbon cable in with the **silver contact strips facing the PCB** (toward the Pi board, not away from it)
   - Press the black clamp back down firmly to lock the cable
4. Repeat the same insertion process on the camera module end
5. Route the cable so it will exit through a slot in the enclosure with the lens facing rearward

### 4.4 — Wire the Blue Multi-Function Button (Adafruit 1477)

The Adafruit 1477 button has **4 electrical contacts** at its base:

- **2 unmarked metal tabs** = switch contacts (NO and COM)
- **2 terminals marked + and −** = built-in LED contacts

**Switch wiring (required):**

|     Button Contact     | → | Pi Physical Pin | BCM GPIO | Wire Color |
| :---------------------: | :-: | :--------------: | :------: | :--------: |
| NO terminal (unmarked) | → | **Pin 37** | GPIO 26 |   White   |
| COM terminal (unmarked) | → | **Pin 39** |   GND   |   Black   |

**LED wiring (recommended — provides visual power-on feedback):**

|      Button Contact      | → |          Pi Physical Pin          | BCM GPIO | Wire Color |
| :----------------------: | :-: | :-------------------------------: | :------: | :--------: |
|  LED + (anode, marked)  | → | 10kΩ resistor →**Pin 33** | GPIO 13 |    Blue    |
| LED − (cathode, marked) | → |         **Pin 34**         |   GND   |   Black   |

**Wiring procedure:**

1. Identify the 4 contacts at the base of the button. The switch contacts (NO and COM) are the two unmarked metal tabs; the LED contacts are marked with **+** and **−**.
2. Connect a white female Dupont jumper from the **NO terminal** to Pi **Pin 37** (GPIO 26)
3. Connect a black female Dupont jumper from the **COM terminal** to Pi **Pin 39** (GND)
4. Solder or connect a 10kΩ resistor inline between a blue jumper wire and the **LED + terminal**, then connect the free end to Pi **Pin 33** (GPIO 13)
5. Connect a black female Dupont jumper from the **LED − terminal** to Pi **Pin 34** (GND)

If the button uses spade/lug terminals instead of pins, use 0.110" (2.8mm) female quick-connect terminals (Adafruit product 1152).

### 4.5 — Final Wiring Summary and Pin Conflict Check

**All 9 used pins:**

| Pi Pin | What's Connected                      | Type                    |
| :----: | ------------------------------------- | ----------------------- |
|   1   | MPU-6050 AD0 (address select → 3.3V) | 3.3V power              |
|   2   | MPU-6050 VCC (power supply → 5V)     | 5V power                |
|   3   | MPU-6050 SDA (I2C data)               | I2C SDA (GPIO 2)        |
|   5   | MPU-6050 SCL (I2C clock)              | I2C SCL (GPIO 3)        |
|   6   | MPU-6050 GND                          | Ground                  |
|   33   | Blue button LED + (through 10kΩ)     | GPIO 13 output          |
|   34   | Blue button LED −                    | Ground                  |
|   37   | Blue button switch NO terminal        | GPIO 26 input (pull-up) |
|   39   | Blue button switch COM terminal       | Ground                  |

**Conflict check — all clear:**

| Potential Conflict                                | Status                                                   |
| ------------------------------------------------- | -------------------------------------------------------- |
| MPU-6050 (0x68) vs PiSugar 3 RTC (0x68)           | RESOLVED: AD0 → 3.3V shifts MPU to 0x69                 |
| I2C SDA/SCL shared between MPU-6050 and PiSugar 3 | OK: Multiple devices share I2C bus normally              |
| GPIO 3 (SCL) vs wake-from-halt                    | NOT USED for button (GPIO 26 used instead)               |
| UART TX/RX (GPIO 14/15)                           | UNUSED: GPS retired to iPhone                            |
| PiSugar 3 pogo pins vs header wiring              | NO CONFLICT: pogo pins contact PCB pads, not header pins |
| Camera CSI vs GPIO header                         | NO CONFLICT: CSI is a separate connector                 |

**Power the Pi back on** by pressing the PiSugar 3's hardware button or connecting USB-C power.

---

## 5. Phase 4 — Verify Every Hardware Connection

SSH back into the Pi:

```bash
ssh pi@bikebox.local
```

### Step 5.1 — I2C Bus Scan

```bash
sudo i2cdetect -y 1
```

**Expected output:**

```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- 57 -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- 69 -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

- `0x57` = PiSugar 3 battery management IC
- `0x69` = MPU-6050 IMU (shifted from 0x68 via AD0)
- 

**If you see 0x68 instead of 0x69**: The MPU-6050 AD0 wire is not connected to 3.3V. Power off and fix the wiring before proceeding.

**If you see 0x57 but no 0x69**: The MPU-6050 is not powered or not wired. Check VCC (Pin 2), GND (Pin 6), SDA (Pin 3), SCL (Pin 5).

**If you see nothing**: I2C is not enabled. Run `sudo raspi-config` → Interface Options → I2C → Enable, then reboot.

### Step 5.2 — Camera Check

```bash
rpicam-hello --timeout 2000 -n
```

Expected: the command runs for 2 seconds and exits with no errors. The `-n` flag suppresses the preview window (we're headless over SSH).

If it fails with "no cameras available":

- Check the CSI cable connections at both ends (silver contacts must face the PCB)
- Verify `camera_auto_detect=1` in `/boot/firmware/config.txt`
- Reboot after any config changes

Take a test photo to confirm full functionality:

```bash
rpicam-jpeg -o /tmp/test.jpg --width 1920 --height 1080
ls -la /tmp/test.jpg
```

Expected: a file around 200–800KB.

### Step 5.3 — Bluetooth Check

```bash
hciconfig hci0
```

**Expected output includes:**

```
hci0:   Type: Primary  Bus: UART
        BD Address: XX:XX:XX:XX:XX:XX  ACL MTU: 1021:8  SCO MTU: 64:1
        UP RUNNING
```

The key is seeing **UP RUNNING**. If it says **DOWN**:

```bash
sudo hciconfig hci0 up
```

Verify BlueZ experimental mode is active:

```bash
sudo btmgmt info | grep "current settings"
```

The output should include `le` (Low Energy).

### Step 5.4 — GPIO Quick Test (Blue Button)

```bash
python3 -c "
import RPi.GPIO as GPIO
import time
GPIO.setmode(GPIO.BCM)
GPIO.setup(26, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(13, GPIO.OUT)
GPIO.output(13, GPIO.HIGH)
print('Blue button LED should be ON.')
print('Press the button once, then Ctrl+C to exit.')
try:
    while True:
        state = GPIO.input(26)
        if state == GPIO.LOW:
            print('Button PRESSED (GPIO 26 = LOW)')
        time.sleep(0.1)
except KeyboardInterrupt:
    GPIO.output(13, GPIO.LOW)
    GPIO.cleanup()
    print('Button test passed')
"
```

- The blue button's built-in LED should light up
- Pressing the button should print "Button PRESSED"
- `Ctrl+C` to exit

If the button LED doesn't light: check GPIO 13 (Pin 33) → 10kΩ → LED+ and LED− → GND (Pin 34).

If button presses aren't detected: check NO terminal → Pin 37 (GPIO 26) and COM terminal → Pin 39 (GND).

---

## 6. Phase 5 — Install Software Dependencies

### Step 6.1 — Install System-Level Packages

These are the Linux packages required for hardware access, Bluetooth, and the camera stack:

```bash
sudo apt update && sudo apt install -y \
    python3-smbus2 \
    python3-rpi.gpio \
    python3-picamera2 \
    python3-dbus \
    python3-gi \
    python3-gi-cairo \
    python3-pytest \
    bluez \
    rpicam-apps \
    i2c-tools \
    git
```

This takes 2–5 minutes.

**Why apt and not pip?** On Raspberry Pi OS Bookworm, Python is managed by the system package manager. The packages `python3-dbus` and `python3-gi` (PyGObject) **must** be installed via `apt` — installing them with `pip` causes conflicts with the system Python environment.

The BikeBox code wraps all D-Bus/GLib imports in `try/except` blocks so it gracefully handles environments where these packages aren't available (e.g., dev machines for testing).

### Step 6.2 — Create the Project Directory

```bash
mkdir -p ~/bikebox/data/clips ~/bikebox/data/logs ~/bikebox/tests
```

Verify:

```bash
ls -la ~/bikebox/
```

Expected:

```
total 0
drwxr-xr-x  4 pi pi  80 ... .
drwxr-xr-x  5 pi pi 100 ... ..
drwxr-xr-x  4 pi pi  80 ... data
drwxr-xr-x  2 pi pi  40 ... tests
```

### Step 6.3 — Install pip Dependencies (for testing)

```bash
pip install pytest pytest-mock --break-system-packages
```

The `--break-system-packages` flag is required on Bookworm because Raspberry Pi OS uses an externally managed Python environment. These testing packages are safe to install this way.

---

## 7. Phase 6 — Deploy the BikeBox Python Code

### Step 7.1 — Transfer Files to the Pi

There are several ways to get the code onto the Pi. Choose one:

**Option A — Git clone (if the repo is hosted):**

```bash
cd ~/bikebox
git clone <your-repository-url> .
```

**Option B — SCP from your development machine:**

Run these commands **from your local computer** (not from the Pi SSH session):

```bash
scp -r /path/to/bikebox/full_system/pi/* pi@bikebox.local:~/bikebox/
scp -r /path/to/bikebox/full_system/pi/tests/* pi@bikebox.local:~/bikebox/tests/
```

**Option C — rsync (preserves structure, good for repeated syncs):**

Run from your local computer:

```bash
rsync -avz --exclude='.pytest_cache' --exclude='__pycache__' \
    /path/to/bikebox/full_system/pi/ pi@bikebox.local:~/bikebox/
```

### Step 7.2 — Verify the Deployed File Tree

SSH back into the Pi and verify:

```bash
ls -la ~/bikebox/
```

Expected files:

```
config.py
imu.py
detector.py
camera.py
battery.py
ble_server.py
alert.py
main.py
requirements.txt
tests/
data/
```

Verify the test directory:

```bash
ls ~/bikebox/tests/
```

Expected:

```
conftest.py
test_config.py
test_imu.py
test_detector.py
test_alert.py
test_battery.py
test_camera.py
test_ble_payload.py
```

### Step 7.3 — Verify config.py Key Values

Quickly sanity-check that the configuration matches your hardware:

```bash
cd ~/bikebox
python3 -c "
import config
print(f'Button Pin:       GPIO {config.BUTTON_PIN} (Pin 37)')
print(f'Button LED Pin:   GPIO {config.BUTTON_LED_PIN} (Pin 33)')
print(f'MPU-6050 Addr:    0x{config.MPU6050_ADDR:02X}')
print(f'PiSugar Addr:     0x{config.PISUGAR_ADDR:02X}')
print(f'I2C Bus:          {config.I2C_BUS}')
print(f'Impact Threshold: {config.IMPACT_THRESHOLD}g')
print(f'Gyro Threshold:   {config.GYRO_THRESHOLD} dps')
print(f'Tilt Threshold:   {config.TILT_THRESHOLD} deg')
print(f'BLE Service UUID: {config.BLE_SERVICE_UUID}')
"
```

Expected output:

```
Button Pin:       GPIO 26 (Pin 37)
Button LED Pin:   GPIO 13 (Pin 33)
MPU-6050 Addr:    0x69
PiSugar Addr:     0x57
I2C Bus:          1
Impact Threshold: 3.0g
Gyro Threshold:   200.0 dps
Tilt Threshold:   45.0 deg
BLE Service UUID: CB000001-0B1C-4E5D-8A9F-1234567890AB
```

---

## 8. Phase 7 — Run Unit Tests

The test suite uses mocked hardware so it runs on the Pi without needing the actual sensors active. This verifies the software logic is correct.

### Step 8.1 — Run the Full Test Suite

```bash
cd ~/bikebox
python3 -m pytest tests/ -v
```

**Expected output:**

```
========================= test session starts =========================
...
tests/test_alert.py::test_... PASSED
tests/test_battery.py::test_... PASSED
tests/test_ble_payload.py::test_... PASSED
tests/test_camera.py::test_... PASSED
tests/test_config.py::test_... PASSED
tests/test_detector.py::test_... PASSED
tests/test_imu.py::test_... PASSED
...
========================= 119 passed in ~2.5s =========================
```

All 119 tests should pass. If any fail:

- **ImportError**: A dependency is missing. Re-run the `apt install` command from Step 6.1
- **ModuleNotFoundError for dbus/gi**: These are mocked in `conftest.py` — this should not occur. If it does, verify `conftest.py` is in the `tests/` directory
- **Assertion errors**: The code may have been modified. Compare against the reference implementation in the design document

### Step 8.2 — Run a Specific Test Module (Optional)

If you want to test one module at a time:

```bash
python3 -m pytest tests/test_imu.py -v          # IMU tests only
python3 -m pytest tests/test_detector.py -v      # Crash detection tests
python3 -m pytest tests/test_alert.py -v         # Alert pipeline tests
python3 -m pytest tests/test_config.py -v        # Config validation
python3 -m pytest tests/test_battery.py -v       # Battery monitor tests
python3 -m pytest tests/test_camera.py -v        # Camera tests
python3 -m pytest tests/test_ble_payload.py -v   # BLE payload tests
```

---

## 9. Phase 8 — Run Hardware Self-Tests

These tests interact with real hardware. Run them one at a time.

### Step 9.1 — Test IMU (Live Accelerometer Output)

```bash
cd ~/bikebox
python3 main.py --test-imu
```

**Expected behavior:**

- The terminal prints live accelerometer data at ~20Hz
- With the device sitting still on a table, the magnitude should read approximately **1.00g** (gravity)
- Pick up and shake the device — the magnitude should spike to 2–5g
- Press `Ctrl+C` to stop

**If it fails:**

- "Bus error" or "Remote I/O error": I2C wiring is wrong. Check SDA, SCL, VCC, GND
- "WHO_AM_I mismatch": The MPU-6050 clone may report a different chip ID. The code accepts 0x68, 0x70, and 0x71. If yours reports another value, add it to `VALID_CHIP_IDS` in `imu.py`

### Step 9.2 — Test Battery

```bash
python3 main.py --test-battery
```

**Expected output:**

```
Battery: XX%  Charging: Yes/No
```

If it shows 0% or fails, the PiSugar 3 pogo pins may not be making solid contact. Re-seat the PiSugar 3 and tighten the mounting screws.

### Step 9.3 — Test BLE Server

```bash
python3 main.py --test-ble
```

**Expected**: The terminal prints "BLE server running."

**Verify from your iPhone:**

1. Install a BLE scanner app (e.g., **LightBlue** from the App Store — it's free)
2. Open LightBlue and scan for devices
3. You should see **"BikeBox"** in the scan results
4. Tap to connect. Under the connected device, you should see the service UUID `CB000001-0B1C-4E5D-8A9F-1234567890AB` with three characteristics:
   - `CB000002-...` (Crash Alert — Notify)
   - `CB000003-...` (Device Status — Read, Notify)
   - `CB000004-...` (Grace Period — Read, Write, Notify)

Press `Ctrl+C` on the Pi to stop the BLE server.

**If "BikeBox" doesn't appear:**

- Check `hciconfig hci0` shows "UP RUNNING"
- Verify BlueZ experimental mode: `grep experimental /lib/systemd/system/bluetooth.service`
- Restart Bluetooth: `sudo systemctl restart bluetooth`
- Ensure iPhone Bluetooth is on and Location Services are enabled (iOS requires location to scan BLE)

---

## 10. Phase 9 — Set Up the Systemd Service (Auto-Start)

This configures BikeBox to start automatically on every boot.

### Step 10.1 — Create the Service File

```bash
sudo nano /etc/systemd/system/bikebox.service
```

Paste the following content (right-click or `Ctrl+Shift+V` to paste in most terminals):

```ini
[Unit]
Description=BikeBox Bicycle Crash Detection System
After=network.target bluetooth.target
Wants=bluetooth.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/bikebox
ExecStart=/usr/bin/python3 /home/pi/bikebox/main.py
Restart=on-failure
RestartSec=10
TimeoutStartSec=30
TimeoutStopSec=15

Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=/home/pi/bikebox

ProtectSystem=strict
ReadWritePaths=/home/pi/bikebox/data
ProtectHome=read-only
NoNewPrivileges=false

StandardOutput=journal
StandardError=journal
SyslogIdentifier=bikebox

[Install]
WantedBy=multi-user.target
```

Save and exit: `Ctrl+O`, `Enter`, `Ctrl+X`.

### Step 10.2 — Enable and Test

```bash
sudo systemctl daemon-reload
sudo systemctl enable bikebox.service
sudo systemctl start bikebox.service
```

Check the status:

```bash
sudo systemctl status bikebox.service
```

**Expected**: Active (running), with log output showing the 7-step initialization:

```
● bikebox.service - BikeBox Bicycle Crash Detection System
     Loaded: loaded (/etc/systemd/system/bikebox.service; enabled)
     Active: active (running) since ...
```

View live logs:

```bash
journalctl -u bikebox.service -f
```

You should see the boot sequence:

```
[1/7] Initializing GPIO...
[2/7] Initializing IMU...
[3/7] Starting camera...
[4/7] Starting battery monitor...
[5/7] Starting BLE server...
[6/7] Connecting subsystems...
[7/7] System armed.
```

Press `Ctrl+C` to stop watching logs (the service keeps running).

### Step 10.3 — Verify Auto-Start on Reboot

```bash
sudo reboot
```

Wait 30 seconds, then SSH in and verify:

```bash
ssh pi@bikebox.local
sudo systemctl status bikebox.service
```

It should be **active (running)**. If the button is wired and `BUTTON_ENABLED = True`, the blue button LED should be on.

### Step 10.4 — Useful Service Commands

```bash
sudo systemctl stop bikebox.service       # Stop the service
sudo systemctl restart bikebox.service    # Restart after code changes
sudo systemctl disable bikebox.service    # Disable auto-start
journalctl -u bikebox.service -n 100 --no-pager  # View last 100 log lines
journalctl -u bikebox.service -b          # View logs from current boot
```

### Step 10.5 — GPIO Permissions Troubleshooting

If you see GPIO permission errors in the logs, add a udev rule:

```bash
sudo nano /etc/udev/rules.d/99-gpio.rules
```

Add this single line:

```
SUBSYSTEM=="gpio", KERNEL=="gpiochip*", GROUP="gpio", MODE="0660"
```

Save and reload:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

---

## 11. Phase 10 — Build and Deploy the iOS Companion App

### Step 11.1 — Open the Xcode Project

On your Mac, navigate to the iOS app directory and open the project:

```bash
cd /path/to/bikebox/full_system/ios/BikeBox
open BikeBox.xcodeproj
```

Or open Xcode manually and select File → Open → navigate to `BikeBox.xcodeproj`.

### Step 11.2 — Configure Signing

1. In Xcode, select the **BikeBox** target in the project navigator (left sidebar)
2. Go to the **Signing & Capabilities** tab
3. Under **Team**, select your Apple Developer account (personal or organization)
4. Under **Bundle Identifier**, enter a unique identifier (e.g., `com.yourname.bikebox`)
5. Xcode will automatically create a provisioning profile

If you see signing errors:

- Ensure you are signed into an Apple ID in Xcode → Settings → Accounts
- A free Apple Developer account allows deploying to your own device for 7 days
- For longer-term deployment, use a paid Apple Developer Program membership ($99/year)

### Step 11.3 — Verify Info.plist Configuration

The `Info.plist` must contain these keys for BLE and location to work. Open `BikeBox/Info.plist` in Xcode and verify:

| Key jiiiiiiiiiiiiiiiiiii                         | Required Value                                                                                                                                        |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `UIBackgroundModes`                            | Array containing `bluetooth-central` and `location`                                                                                               |
| `NSBluetoothAlwaysUsageDescription`            | "BikeBox uses Bluetooth to stay connected to your crash detection device and alert you in an emergency."                                              |
| `NSLocationWhenInUseUsageDescription`          | "BikeBox uses your location to attach GPS coordinates to crash alerts so emergency contacts know where you are."                                      |
| `NSLocationAlwaysAndWhenInUseUsageDescription` | "BikeBox needs continuous location access to provide accurate GPS coordinates in crash alerts, even when the app is in the background during a ride." |

These should already be configured in the provided project. If any are missing, add them.

### Step 11.4 — Verify BLE UUIDs Match

Open `BikeBox/Utilities/BLEConstants.swift` and confirm the UUIDs match the Pi side:

| Constant               | UUID (must match Pi's `config.py`)     |
| ---------------------- | ---------------------------------------- |
| `bikeBoxServiceUUID` | `CB000001-0B1C-4E5D-8A9F-1234567890AB` |
| `crashAlertUUID`     | `CB000002-0B1C-4E5D-8A9F-1234567890AB` |
| `deviceStatusUUID`   | `CB000003-0B1C-4E5D-8A9F-1234567890AB` |
| `gracePeriodUUID`    | `CB000004-0B1C-4E5D-8A9F-1234567890AB` |

These must be character-for-character identical to the values in the Pi's `config.py`:

```
BLE_SERVICE_UUID      = 'CB000001-0B1C-4E5D-8A9F-1234567890AB'
BLE_CRASH_ALERT_UUID  = 'CB000002-0B1C-4E5D-8A9F-1234567890AB'
BLE_DEVICE_STATUS_UUID= 'CB000003-0B1C-4E5D-8A9F-1234567890AB'
BLE_GRACE_PERIOD_UUID = 'CB000004-0B1C-4E5D-8A9F-1234567890AB'
```

### Step 11.5 — Build and Deploy to iPhone

1. Connect your iPhone to your Mac via USB cable
2. In Xcode, select your iPhone from the device dropdown at the top (next to the play button). **Do not select a simulator** — BLE does not work in the iOS simulator.
3. Click the **Play** button (▶) or press `Cmd+R` to build and run
4. On your iPhone, you may be prompted to:
   - **Trust the developer**: Go to Settings → General → VPN & Device Management → tap your developer profile → Trust
   - **Allow Bluetooth**: Tap "Allow" when the permission dialog appears
   - **Allow Location**: Select "Allow While Using App" or "Always" (Always is recommended for crash detection during rides)
5. The app should launch on your iPhone

### Step 11.6 — Verify the App Launches

The app should open to the **Pairing** screen (or Dashboard if previously paired). You should see:

- A "Scan for Devices" button
- Bluetooth permission was granted (no error banner)
- Location permission was granted (check the GPS status indicator)

---

## 12. Phase 11 — Pair the iOS App to the Pi

### Step 12.1 — Ensure BikeBox Is Running

On the Pi (via SSH):

```bash
sudo systemctl status bikebox.service
```

Confirm it shows **active (running)**. If not:

```bash
sudo systemctl start bikebox.service
```

Alternatively, for manual control during testing, stop the service and run manually:

```bash
sudo systemctl stop bikebox.service
cd ~/bikebox
python3 main.py
```

### Step 12.2 — Scan and Connect from the iOS App

1. Open the BikeBox app on your iPhone
2. Tap **"Scan for Devices"** (or navigate to the Pairing screen)
3. The app will scan for BLE peripherals advertising the BikeBox service UUID
4. **"BikeBox"** should appear in the list within 5–10 seconds
5. Tap **"BikeBox"** to connect
6. The app will:
   - Establish a GATT connection
   - Discover the BikeBox service
   - Subscribe to all three characteristics (Crash Alert, Device Status, Grace Period)
7. The Dashboard screen should populate with:
   - **Connection**: Connected
   - **Battery**: The Pi's battery percentage (from PiSugar 3)
   - **GPS**: Fix status (from the iPhone's own CoreLocation)

### Step 12.3 — Verify BLE Data Flow

On the Pi's log output (either via `journalctl -u bikebox.service -f` or the manual terminal):

- You should see "BLE: Central connected" when the iPhone pairs
- Every 30 seconds, the Pi sends a heartbeat via the Device Status characteristic

On the iOS app:

- The battery percentage should update
- The connection indicator should show "Connected"

### Step 12.4 — Persistence Test

1. Lock your iPhone screen (press the side button)
2. Wait 60 seconds
3. Unlock — the app should still show "Connected" with updated battery readings
4. The `bluetooth-central` background mode keeps the BLE connection alive

---

## 13. Phase 12 — Run Full System Detection

### 13.1 — Manual Run (Recommended for First Test)

Stop the systemd service (if running) so you can see live output:

```bash
sudo systemctl stop bikebox.service
cd ~/bikebox
python3 main.py
```

You will see the full boot sequence:

```
============================================================
  BikeBox — Bicycle Crash Detection System
  Dartmouth ENGS 21 | Team 1
============================================================

[1/7] Initializing GPIO...
[2/7] Initializing IMU...
[3/7] Starting camera...
[4/7] Starting battery monitor...
[5/7] Starting BLE server...
[6/7] Connecting subsystems...
[7/7] System armed.

============================================================
  BikeBox ARMED — All systems operational
  Battery: 87%  |  GPS: via iPhone
  Camera: Recording  |  BLE: Advertising
============================================================
```

### 13.2 — Trigger a Test Crash

While `main.py` is running and the iOS app is connected:

1. **Pick up the Pi** (still connected to power/battery)
2. **Give it a sharp shake** (to trigger Stage 1 — impact > 3.0g) or **quickly tilt it sideways** (to trigger Stage 1 Path B — gyro > 200°/s)
3. **Hold it tilted at > 45° for 2+ seconds** (to pass Stage 2 — sustained tilt confirmation)

**Expected sequence:**

| Timing   | What Happens                        | Where to See It                              |
| -------- | ----------------------------------- | -------------------------------------------- |
| T+0s     | Impact detected (Stage 1 triggers)  | Pi console:`IMPACT: X.XXg`                 |
| T+1s     | Tilt confirmed (Stage 2 passes)     | Pi console:`CRASH CONFIRMED`               |
| T+1s     | BLE Crash Alert sent (0x01)         | iOS app: Alert screen appears                |
| T+1s     | Grace period countdown starts (30s) | Pi console + iOS app: countdown              |
| T+1–31s | **Cancel window**             | Hold blue button ≥3s OR tap "I'M OK" in app |
| T+31s    | If not cancelled: ALERT CONFIRMED   | Pi console + iOS: escalation                 |

### 13.3 — Cancel the Alert (Two Methods)

**Method A — Physical button (long hold ≥3 seconds):**

During the 30-second grace period, press and hold the blue button for at least 3 seconds. The Pi should print:

```
CANCELLED by button long hold
```

**Method B — iOS app ("I'M OK" button):**

During the grace period, the iOS app shows a countdown ring with an "I'M OK" button. Tap it. The Pi should print:

```
CANCELLED by iOS app
```

After cancellation, the system returns to normal monitoring.

### 13.4 — Run with CSV Logging

For analyzing ride data and tuning thresholds:

```bash
python3 main.py --log my_test_ride.csv
```

This runs the full detection loop AND writes every IMU sample to a CSV file at `/home/pi/bikebox/data/logs/my_test_ride.csv`. The CSV columns are:

```
timestamp, ax, ay, az, magnitude, gyro, event
```

The `event` column marks Stage 1 triggers: `impact` for Path A (g-force) or `gyro_trigger` for Path B (angular velocity).

After the ride, analyze the data:

```bash
python3 -c "
import csv
with open('/home/pi/bikebox/data/logs/my_test_ride.csv') as f:
    rows = list(csv.DictReader(f))
    max_g = max(float(r['magnitude']) for r in rows)
    max_gyro = max(float(r['gyro']) for r in rows if r['gyro'])
    events = [r for r in rows if r['event']]
    print(f'Total samples: {len(rows)}')
    print(f'Peak g-force: {max_g:.2f}g (threshold: 3.0g)')
    print(f'Peak gyro: {max_gyro:.0f} dps (threshold: 200 dps)')
    print(f'Stage 1 triggers: {len(events)}')
    for e in events:
        print(f'  {e[\"event\"]} at {e[\"timestamp\"]} — {float(e[\"magnitude\"]):.2f}g, {e[\"gyro\"]} dps')
"
```

### 13.5 — Run Modes Summary

| Command                            | What It Does                                      |
| ---------------------------------- | ------------------------------------------------- |
| `python3 main.py`                | Full system (IMU + camera + BLE + detection)      |
| `python3 main.py --no-camera`    | No camera (saves power, useful for bench testing) |
| `python3 main.py --no-ble`       | No BLE                                            |
| `python3 main.py --log ride.csv` | Full system + CSV logging                         |
| `python3 main.py --test-imu`     | Live IMU readout only                             |
| `python3 main.py --test-battery` | Battery status readout                            |
| `python3 main.py --test-ble`     | BLE server test only                              |

---

## 14. Phase 13 — Integration and Field Testing

### 14.1 — Test 1: Baseline Ride (No Alert Expected)

Mount the device under the bicycle seat. Ride normally for 5 minutes over flat pavement, speed bumps, and gentle braking. Run with logging:

```bash
python3 main.py --log baseline_ride.csv
```

**Pass criteria**: No crash alert fires during normal riding. Check the CSV log afterward for peak values — they should stay below the thresholds.

### 14.2 — Test 2: Bump Test (No Alert Expected)

Hit a pothole or curb at moderate speed. The IMU may spike to 2–3.5g and the gyro may spike briefly, but the bike remains upright, so Stage 2 (tilt) should not confirm.

**Pass criteria**: Stage 1 may trigger (this is OK), but Stage 2 rejects it because the bike stays upright.

### 14.3 — Test 3: Crash Simulation (Alert Expected)

With the device mounted, give the bike a sharp shake or impact, then tip it over and hold it down for 3+ seconds.

**Pass criteria**:

1. Pi console prints "IMPACT" then "CRASH CONFIRMED"
2. iOS app receives the crash alert notification
3. Grace period countdown begins (30 seconds)

### 14.4 — Test 4: Grace Period Cancel — Physical Button

Trigger a crash. During the countdown, hold the blue button for ≥3 seconds.

**Pass criteria**: Alert is cancelled, system returns to monitoring.

### 14.5 — Test 5: Grace Period Cancel — iOS App

Trigger a crash. During the countdown, tap "I'M OK" in the iOS app.

**Pass criteria**: Alert is cancelled on both Pi and iOS.

### 14.6 — Test 6: Full Escalation (No Cancel)

Trigger a crash. Do NOT cancel during the 30-second countdown.

**Pass criteria**: After 30 seconds, the Pi sends `ALERT_CRASH_CONFIRMED` (0x03) and the iOS app escalates to emergency SMS/call.

### 14.7 — Test 7: BLE Disconnection and Reconnection

1. Walk the iPhone 50+ feet away from the Pi (out of BLE range)
2. Wait for the iOS app to show "Disconnected"
3. Walk back within range
4. Connection should auto-re-establish within 10–30 seconds

### 14.8 — Test 8: App Background and Terminated

1. Connect the iOS app to BikeBox
2. Press the Home button to background the app
3. Trigger a crash simulation on the Pi
4. iOS should fire a local notification even though the app is backgrounded
5. Repeat with the app force-quit (swipe up in the app switcher) — CoreBluetooth state restoration should relaunch the app for the notification

### 14.9 — Threshold Tuning

If you experience issues, adjust values in `~/bikebox/config.py`:

| Problem                             | Adjustment                                       |
| ----------------------------------- | ------------------------------------------------ |
| Too many false positives            | Increase `IMPACT_THRESHOLD` (try 4.0g or 5.0g) |
| Too many false positives from turns | Increase `GYRO_THRESHOLD` (try 250 or 300 dps) |
| Missed crashes                      | Decrease `IMPACT_THRESHOLD` (try 2.5g)         |
| Missed slow tipovers                | Decrease `GYRO_THRESHOLD` (try 150 dps)        |
| Stage 2 too sensitive               | Increase `SUSTAINED_TILT_TIME` (try 3.0s)      |
| Stage 2 too strict                  | Decrease `TILT_THRESHOLD` (try 35 degrees)     |

After editing `config.py`, restart the service:

```bash
sudo systemctl restart bikebox.service
```

---

## 15. Complete Troubleshooting Reference

### 15.1 — I2C Issues

| Symptom                                  | Cause                             | Fix                                                                                        |
| ---------------------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------ |
| `i2cdetect` shows 0x68 instead of 0x69 | AD0 not wired to 3.3V             | Wire MPU-6050 AD0 to Pin 1 (3.3V)                                                          |
| `i2cdetect` shows nothing              | I2C not enabled                   | `sudo raspi-config` → I2C → Enable; check `dtparam=i2c_arm=on` in config.txt; reboot |
| `i2cdetect` shows 0x57 but no 0x69     | MPU-6050 not powered or not wired | Check VCC→Pin 2, GND→Pin 6, SDA→Pin 3, SCL→Pin 5                                       |
| "Remote I/O error" in Python             | Loose wire or wrong address       | Check wiring; verify address matches `config.py` (0x69)                                  |
| `i2cdetect` shows 0x68 AND 0x69        | Phantom device from floating wire | Ensure AD0 is firmly connected to 3.3V (not floating)                                      |

### 15.2 — Camera Issues

| Symptom                                        | Cause                                       | Fix                                                                         |
| ---------------------------------------------- | ------------------------------------------- | --------------------------------------------------------------------------- |
| "no cameras available"                         | CSI cable disconnected or wrong orientation | Re-seat cable; silver contacts face the PCB                                 |
| `rpicam-hello` works but `picamera2` fails | picamera2 not installed                     | `sudo apt install python3-picamera2`                                      |
| "Camera already in use"                        | Another process is using it                 | `sudo fuser /dev/video0` to find the PID, then `kill` it                |
| Camera test works but systemd fails            | Missing `video` group                     | `sudo usermod -aG video pi`                                               |
| `camera_auto_detect=0` in config.txt         | Camera disabled in boot config              | Change to `camera_auto_detect=1` in `/boot/firmware/config.txt`; reboot |

### 15.3 — BLE Issues

| Symptom                                  | Cause                               | Fix                                                                                                |
| ---------------------------------------- | ----------------------------------- | -------------------------------------------------------------------------------------------------- |
| "GattManager1 not found"                 | BlueZ experimental mode not enabled | Add `--experimental` to ExecStart in `/lib/systemd/system/bluetooth.service`; reload + restart |
| "BikeBox" not appearing in scans         | Bluetooth adapter down              | `sudo hciconfig hci0 up`                                                                         |
| iPhone connects then disconnects         | Multiple GATT servers running       | `pkill -f main.py`; `sudo systemctl restart bluetooth`; wait 5s; restart bikebox               |
| "BikeBox" never appears                  | iPhone Location Services off        | Enable Settings → Privacy → Location Services on iPhone (required for BLE scanning)              |
| D-Bus connection refused                 | Missing dbus packages               | `sudo apt install python3-dbus python3-gi`                                                       |
| BLE server logs "DBUS_AVAILABLE = False" | System packages not installed       | `sudo apt install python3-dbus python3-gi python3-gi-cairo`                                      |

### 15.4 — Power Issues

| Symptom                            | Cause                         | Fix                                                                         |
| ---------------------------------- | ----------------------------- | --------------------------------------------------------------------------- |
| PiSugar 3 reports 0%               | Poor pogo pin contact         | Re-seat PiSugar 3; tighten screws                                           |
| Battery readings are erratic       | Loose I2C connection          | Check PiSugar alignment;`i2cget -y 1 0x57 0x2A` should return a hex value |
| System shuts down after ~1.6 hours | PiSugar 3 alone is not enough | Connect Anker PowerCore to PiSugar's USB-C input                            |
| Pi won't power on                  | PiSugar battery fully drained | Charge via USB-C for 30 minutes, then retry                                 |

### 15.5 — Crash Detection Issues

| Symptom                               | Cause                            | Fix                                                                             |
| ------------------------------------- | -------------------------------- | ------------------------------------------------------------------------------- |
| False positives during normal riding  | Thresholds too low               | Increase `IMPACT_THRESHOLD` and/or `GYRO_THRESHOLD` in `config.py`        |
| Missed crashes                        | Thresholds too high              | Decrease `IMPACT_THRESHOLD` and/or `GYRO_THRESHOLD`                         |
| IMU reads ~0g on all axes             | Calibration issue or dead sensor | Run `--test-imu` with device stationary; expect ~1.0g magnitude               |
| Button cancel doesn't work            | Wiring or timing                 | Must hold ≥3s; check NO→Pin 37, COM→Pin 39; verify `BUTTON_ENABLED = True` |
| Button shutdown triggers accidentally | Dead zone too narrow             | Increase `SHORT_PRESS_MAX` in `config.py` (default 1.0s)                    |

### 15.6 — iOS App Issues

| Symptom                                | Cause                                  | Fix                                                                         |
| -------------------------------------- | -------------------------------------- | --------------------------------------------------------------------------- |
| App can't find BikeBox                 | BLE not scanning or Pi not advertising | Verify Pi BLE is running; verify iPhone Bluetooth + Location are on         |
| "Bluetooth permission denied"          | User denied BLE permission             | Settings → BikeBox → Bluetooth → Allow                                   |
| "No GPS Fix" on dashboard              | Location permission not granted        | Settings → BikeBox → Location → "Always"                                 |
| Crash alert received but no GPS in SMS | Location updates paused in background  | Verify `allowsBackgroundLocationUpdates = true` in LocationService.swift  |
| App killed in background, no relaunch  | State restoration not configured       | Verify `restoreIdentifier` in `BluetoothManager.swift`                  |
| Build fails with signing error         | No valid provisioning profile          | Select your team in Xcode → Signing & Capabilities; use a unique bundle ID |

### 15.7 — Systemd Service Issues

| Symptom                               | Cause              | Fix                                                                      |
| ------------------------------------- | ------------------ | ------------------------------------------------------------------------ |
| Service fails to start                | Python error       | `journalctl -u bikebox.service -n 50 --no-pager` to see the error      |
| Service starts then crashes in a loop | Restart limit hit  | Fix the underlying error;`sudo systemctl reset-failed bikebox.service` |
| Service can't access GPIO             | Permission denied  | `sudo usermod -aG gpio pi`; add udev rule (Step 10.5)                  |
| Service starts before Bluetooth       | Missing dependency | Verify `After=bluetooth.target` in the service file                    |
| "ExecStart not found"                 | Wrong Python path  | Verify `/usr/bin/python3` exists: `which python3`                    |

---

## 16. Quick Reference Card

### Pin Wiring (9 pins used)

```
Pi Pin 1  (3.3V)    →  MPU-6050 AD0 (address select)
Pi Pin 2  (5V)      →  MPU-6050 VCC (power)
Pi Pin 3  (SDA)     →  MPU-6050 SDA (I2C data)
Pi Pin 5  (SCL)     →  MPU-6050 SCL (I2C clock)
Pi Pin 6  (GND)     →  MPU-6050 GND
Pi Pin 33 (GPIO 13) →  10kΩ → Blue Button LED+ → Pin 34 (GND)
Pi Pin 37 (GPIO 26) →  Blue Button NO terminal
Pi Pin 39 (GND)     →  Blue Button COM terminal
PiSugar 3           →  Pogo pins on Pi backside (I2C + power)
Camera               →  CSI ribbon cable (22→15 pin adapter)
```

### I2C Addresses

```
0x57  PiSugar 3 (battery)
0x69  MPU-6050 (IMU — shifted from 0x68 via AD0→3.3V)
```

### BLE UUIDs

```
Service:      CB000001-0B1C-4E5D-8A9F-1234567890AB
Crash Alert:  CB000002-0B1C-4E5D-8A9F-1234567890AB  (Notify)
Device Status:CB000003-0B1C-4E5D-8A9F-1234567890AB  (Read, Notify)
Grace Period: CB000004-0B1C-4E5D-8A9F-1234567890AB  (Read, Write, Notify)
```

### Essential Commands

```bash
ssh pi@bikebox.local                              # Connect to Pi
sudo i2cdetect -y 1                                # Scan I2C bus
rpicam-hello --timeout 2000 -n                  # Test camera
hciconfig hci0                                     # Check Bluetooth
python3 main.py                                    # Run full system
python3 main.py --test-imu                         # Test IMU
python3 main.py --test-ble                         # Test BLE
python3 main.py --log ride.csv                     # Run with logging
python3 -m pytest tests/ -v                        # Run unit tests
sudo systemctl start bikebox.service              # Start service
sudo systemctl stop bikebox.service               # Stop service
sudo systemctl restart bikebox.service            # Restart service
sudo systemctl status bikebox.service             # Check status
journalctl -u bikebox.service -f                  # Live logs
journalctl -u bikebox.service -n 100 --no-pager   # Last 100 lines
```

### Button Behavior

```
Short press (< 1 second)    →  Safe shutdown (sudo shutdown -h now)
Dead zone (1–3 seconds)     →  Ignored
Long hold (≥ 3 seconds)     →  Cancel crash alert (during grace period only)
```

### Detection Thresholds (config.py defaults)

```
IMPACT_THRESHOLD     = 3.0g     (Stage 1 Path A)
GYRO_THRESHOLD       = 200.0°/s (Stage 1 Path B)
GYRO_ACCEL_MIN       = 2.5g     (Path B minimum g-force)
TILT_THRESHOLD       = 45.0°    (Stage 2 confirmation)
SUSTAINED_TILT_TIME  = 2.0s     (Stage 2 duration)
GRACE_PERIOD_SECONDS = 30       (Countdown before escalation)
```

---

*BikeBox Implementation Guide v1.0 — March 2026 — Dartmouth ENGS 21 Team 1*
