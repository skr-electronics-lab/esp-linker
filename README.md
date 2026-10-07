# ESP-Linker: Universal Wireless GPIO Platform

[![PyPI version](https://img.shields.io/pypi/v/esp-linker?style=flat-square&color=0088cc)](https://pypi.org/project/esp-linker/)
[![Python versions](https://img.shields.io/pypi/pyversions/esp-linker?style=flat-square&color=22bb33)](https://pypi.org/project/esp-linker/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![GitHub release](https://img.shields.io/github/v/release/skr-electronics-lab/esp-linker?style=flat-square&color=orange)](https://github.com/skr-electronics-lab/esp-linker/releases)

ESP-Linker converts ESP8266 and ESP32 microcontrollers into high-performance, network-attached wireless GPIO servers. Program your hardware directly from Python over WiFi using an intuitive, PyFirmata-inspired interface without writing, compiling, or uploading Arduino C++ code for every project change.

<p align="left">
  <a href="https://ko-fi.com/skrelectronicslab" target="_blank">
    <img src="https://raw.githubusercontent.com/skr-electronics-lab/flyradar32/main/assets/kofi_button.svg" height="36" alt="Support on Ko-fi">
  </a>
</p>

---

## Key Capabilities

- **Multi-Architecture Support**: Native compiled firmware images for both ESP8266 (NodeMCU, D1 Mini) and ESP32 (DevKit, NodeMCU-32S, ESP32-WROOM) with auto-detection.
- **Zero C++ Firmware Workflow**: Precompiled, optimized C++ firmware binaries are bundled inside the Python package. Flashes via USB in seconds using `esp-linker flash`.
- **PyFirmata-Inspired Python API**: Clean, intuitive hardware methods (`board.write(pin, val)`, `board.read(pin)`, `board.pwm(pin, val)`, `board.servo(pin, angle)`).
- **I2C Hardware Bus & Sensors**: Complete I2C primitives (`i2c_scan()`, `i2c_read()`, `i2c_write()`, `i2c_transfer()`) plus direct telemetry drivers for MPU-6050 (6-axis IMU) and BMP280 / BME280 barometric pressure sensors.
- **Over-The-Air (OTA) Updates**: Wirelessly upload and flash firmware binaries over WiFi via Python API (`board.ota_flash()`) or CLI (`esp-linker ota <IP>`).
- **Real-Time Interrupt Events**: Stream asynchronous pin change interrupts using Server-Sent Events (SSE) via `board.on_change(pin, callback)` and `esp-linker events <IP>`.
- **Modern Hardware Dashboard**: Dark glassmorphism browser control dashboard with live pin toggle matrix, I2C hex grid scanner, OTA upload zone, and telemetry gauges.
- **Interactive WiFi Wizard**: Configure WiFi credentials directly over Serial without hardcoding SSIDs or passwords into source code.
- **Hardware Telemetry & Health**: Query heap memory, signal strength (RSSI), network IP, and uptime on demand.
- **Atomic Batch Commands**: Execute sequences of GPIO actions in a single network transaction to minimize network roundtrip latency.
- **Clean Terminal UI**: Built with Rich featuring real-time progress bars, transfer speeds, ETA counters, and zero emojis.

---

## Supported Hardware

- **ESP8266 Modules**: NodeMCU v2 / v3, Wemos D1 Mini, ESP-12E / ESP-12F, Generic ESP8266 boards (4MB flash).
- **ESP32 Modules**: ESP32 Dev Module, NodeMCU-32S, ESP32-WROOM-32, ESP32-WROVER (4MB flash).
- **Operating Systems**: Windows 10/11, macOS, and Linux (x86_64, ARM64, Raspberry Pi OS).
- **Python Compatibility**: Python 3.7 through Python 3.12+.

---

## Installation

```bash
pip install esp-linker
```

To include optional web dashboard dependencies:

```bash
pip install esp-linker[dashboard]
```

---

## Quick Start: Three-Step Setup

### Step 1: Flash Firmware via USB

Connect your ESP8266 or ESP32 board to your PC using a micro-USB / USB-C data cable, then run:

```bash
esp-linker flash
```

The flasher automatically detects the serial COM port (e.g., `COM4` on Windows or `/dev/ttyUSB0` on Linux), queries chip hardware registers to identify architecture (`ESP8266` or `ESP32`), and flashes the matching bundled binary at 460,800 baud with real-time transfer progress.

You can also specify the target chip explicitly:

```bash
esp-linker flash --chip esp32
# or
esp-linker flash --chip esp8266
```

### Step 2: Configure WiFi Credentials

Run the interactive WiFi setup wizard over the same USB connection:

```bash
esp-linker setup-wifi
```

1. Select your detected USB serial port.
2. The wizard requests the ESP board to scan for 2.4 GHz WiFi networks.
3. Select your network using arrow keys and securely input the password.
4. The board saves credentials into EEPROM and connects to your local network.
5. Take note of the assigned IP address displayed on screen (e.g., `192.168.1.9`).

### Step 3: Verify Hardware with Diagnostic Suite

Test your board live over WiFi:

```bash
esp-linker test 192.168.1.9
```

This launches a live in-place diagnostic dashboard verifying telemetry, pin capabilities, digital I/O, PWM output, servo pulses, ADC reading, and batch pipelines.

---

## Complete Python Feature Tutorials & Examples

### 1. Connecting to the Board & Context Management

Establish a robust HTTP session with your ESP-Linker board. You can connect using a direct IP address, a full URL, automatic mDNS discovery, or Python context managers (`with` statement).

```python
import time
from esp_linker import ESPBoard, connect_auto

# Method A: Direct IP connection (fastest, recommended)
board = ESPBoard(ip="192.168.1.9")
print(f"Connected to {board.firmware_name} ({board.architecture}) at {board.device_ip}")
board.close()

# Method B: Python Context Manager (automatically cleans up HTTP session on exit)
with ESPBoard(ip="192.168.1.9", timeout=3.0) as board:
    status = board.status()
    print(f"Firmware: {status['firmware_name']} v{status['firmware_version']}")
    print(f"Architecture: {status.get('arch', board.architecture)}")
    print(f"Free Heap: {status['free_heap']:,} bytes")
    print(f"WiFi RSSI: {status['wifi_rssi']} dBm")
    print(f"Uptime: {status['uptime']} seconds")
```

Line-by-line explanation:
- Line 5: `ESPBoard(ip="...")` initializes the persistent HTTP session targeting the board's REST API.
- Line 6: `board.architecture` returns `ESP8266` or `ESP32` based on remote device capabilities.
- Line 9: The `with` statement guarantees `board.close()` is executed even if exceptions occur.
- Line 11-15: `board.status()` retrieves real-time hardware telemetry from `/api/status`.

---

### 2. Digital GPIO Output & Input

Control digital logic levels (relays, LEDs, transistor gates) and read digital state (pushbuttons, PIR sensors, limit switches).

```python
import time
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    LED_PIN = 2     # Onboard blue LED (Active-LOW on ESP8266, Active-HIGH on ESP32)
    BUTTON_PIN = 0  # Flash button (GPIO 0)

    # Configure modes explicitly
    board.set_mode(LED_PIN, 'OUTPUT')
    board.set_mode(BUTTON_PIN, 'INPUT_PULLUP')

    # Blink LED 5 times
    for cycle in range(5):
        board.write(LED_PIN, 0)  # Logic LOW (turn LED ON)
        time.sleep(0.2)
        board.write(LED_PIN, 1)  # Logic HIGH (turn LED OFF)
        time.sleep(0.2)

    # Read current button state
    button_state = board.read(BUTTON_PIN)
    print(f"Button state on GPIO {BUTTON_PIN}: {'PRESSED (LOW)' if button_state == 0 else 'RELEASED (HIGH)'}")
```

Line-by-line explanation:
- Line 8: `set_mode(..., 'OUTPUT')` configures the pin register as a digital push-pull driver.
- Line 9: `set_mode(..., 'INPUT_PULLUP')` enables internal weak pull-up resistor (typically 30kΩ–50kΩ).
- Line 13-16: `board.write(pin, value)` sets GPIO output register to 0V (0) or 3.3V (1).
- Line 19: `board.read(pin)` polls digital input register from `/api/read`.

---

### 3. PWM (Pulse Width Modulation) Duty Cycle Control

Fade LEDs, generate audio tones, or regulate motor speed using onboard hardware PWM timers.

```python
import time
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    PWM_PIN = 14  # GPIO 14 (D5 on NodeMCU)

    # Set pin mode to PWM
    board.set_mode(PWM_PIN, 'PWM')

    # Smooth breathing fade: 10-bit resolution (0 to 1023)
    # Ramp brightness up
    for duty in range(0, 1024, 64):
        board.pwm(PWM_PIN, duty)
        time.sleep(0.04)

    # Ramp brightness down
    for duty in range(1023, -1, -64):
        board.pwm(PWM_PIN, duty)
        time.sleep(0.04)

    # Turn off PWM output
    board.pwm(PWM_PIN, 0)
```

Line-by-line explanation:
- Line 7: `set_mode(..., 'PWM')` initializes the hardware PWM timer (1 kHz frequency).
- Line 11-13: `board.pwm(pin, duty)` updates timer duty cycle with 10-bit range (0 = 0%, 1023 = 100%).
- Line 20: Sets duty cycle to 0 to safely disarm the actuator.

---

### 4. Servo Motor Angle Positioning

Position standard hobby RC servos (SG90, MG90S, MG996R) across 0° to 180° with precise pulse timings.

```python
import time
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    SERVO_PIN = 12  # GPIO 12 (D6 on NodeMCU)

    # Set pin mode to SERVO
    board.set_mode(SERVO_PIN, 'SERVO')

    # Sweep servo to key angles
    test_angles = [0, 45, 90, 135, 180, 90]
    for angle in test_angles:
        print(f"Steering servo to {angle} degrees...")
        board.servo(SERVO_PIN, angle)
        time.sleep(0.6)  # Allow mechanical horn to travel
```

Line-by-line explanation:
- Line 7: `set_mode(..., 'SERVO')` attaches the hardware timer generating 50 Hz PWM with 544µs–2400µs pulse width.
- Line 12: `board.servo(pin, angle)` maps 0°–180° directly to pulse durations with zero external dependencies.

---

### 5. Analog ADC Sampling & Voltage Conversion

Read real-time voltages from analog sensors (LDR photoresistors, thermistors, potentiometers).

```python
import time
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    print("Reading analog voltage on ADC channel A0...")

    for _ in range(5):
        raw_val = board.read('A0')
        # ESP8266 ADC0 is 10-bit (0-1023) mapped across 0.0V to 3.3V on NodeMCU
        voltage = (raw_val / 1024.0) * 3.3
        print(f"ADC Raw: {raw_val:4d} / 1024  -->  Measured: {voltage:.2f} Volts")
        time.sleep(0.5)
```

Line-by-line explanation:
- Line 7: `board.read('A0')` interrogates the onboard 10-bit analog-to-digital converter.
- Line 9: Calculates true voltage using NodeMCU onboard 220k/100k resistor divider ratio.

---

### 6. I2C Hardware Bus Control & Sensor Telemetry

Communicate directly with I2C peripherals over the hardware two-wire interface (SDA / SCL) and read calibrated sensor data.

```python
import time
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    # 1. Scan the I2C bus for active peripheral addresses
    devices = board.i2c_scan()
    print(f"Detected I2C devices: {[hex(a) for a in devices]}")

    # 2. Read MPU-6050 6-Axis Motion Tracking Sensor (if connected at 0x68)
    if 0x68 in devices:
        mpu_data = board.read_mpu6050(address=0x68)
        print("MPU-6050 IMU Telemetry:")
        print(f"  Acceleration (G):  X={mpu_data['accel_x']:+.3f}, Y={mpu_data['accel_y']:+.3f}, Z={mpu_data['accel_z']:+.3f}")
        print(f"  Gyroscope (deg/s): X={mpu_data['gyro_x']:+.2f}, Y={mpu_data['gyro_y']:+.2f}, Z={mpu_data['gyro_z']:+.2f}")
        print(f"  Temperature:       {mpu_data['temp_c']:.2f} deg C")

    # 3. Detect BMP280 / BME280 Environmental Sensor (if connected at 0x76 or 0x77)
    for addr in [0x76, 0x77]:
        if addr in devices:
            bmp = board.read_bmp280(address=addr)
            print(f"Detected {bmp['model']} at {bmp['address']} (Chip ID: {bmp['chip_id']})")

    # 4. Low-level I2C Write and Read
    # Example: write configuration byte 0x00 to register 0x6B
    board.i2c_write(0x68, [0x6B, 0x00])
    # Read 6 raw accelerometer bytes starting at register 0x3B
    raw_bytes = board.i2c_read(0x68, length=6, register=0x3B)
    print(f"Raw register bytes: {[hex(b) for b in raw_bytes]}")
```

Line-by-line explanation:
- Line 6: `board.i2c_scan()` probes addresses 0x08 to 0x77 and returns a list of integer addresses.
- Line 10: `board.read_mpu6050()` initializes power registers, reads burst telemetry, and converts raw two's complement into physical units (G's, deg/s, °C).
- Line 19: `board.read_bmp280()` reads the chip identification register (`0xD0`) to identify sensor silicon.
- Line 25-27: `board.i2c_write()` and `board.i2c_read()` provide low-level register access with repeated start capability.

---

### 7. Over-The-Air (OTA) Wireless Firmware Flashing

Upgrade the remote ESP board's firmware wirelessly over WiFi directly from Python with zero USB cable required.

```python
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    print(f"Initiating OTA firmware update on {board.architecture} board...")

    def progress_handler(bytes_sent, total_bytes):
        pct = (bytes_sent / total_bytes) * 100
        print(f"OTA Progress: {bytes_sent}/{total_bytes} bytes ({pct:.1f}%)", end="\r")

    # Flash new compiled firmware binary
    success = board.ota_flash(
        firmware_path="firmware.bin",
        progress_callback=progress_handler
    )

    if success:
        print("\nFirmware flashed successfully! Board is rebooting into new build.")
```

Line-by-line explanation:
- Line 6: `progress_callback` receives bytes uploaded and total bytes for building custom progress bars.
- Line 10: `board.ota_flash()` streams the binary in chunks to the board's `/api/ota` endpoint and validates the update before triggering reboot.

---

### 8. Real-Time Pin Change Interrupts (SSE Events)

Receive instant asynchronous notifications in Python when a hardware pin changes state without polling in a loop.

```python
import time
from esp_linker import ESPBoard

board = ESPBoard(ip="192.168.1.9")

def on_button_change(event):
    pin = event.get('pin')
    state = event.get('state')
    timestamp = event.get('millis')
    print(f"[INTERRUPT] GPIO {pin} changed state to {'HIGH' if state == 1 else 'LOW'} at {timestamp}ms")

# Subscribe to hardware interrupt on GPIO 0
board.on_change(pin=0, callback=on_button_change, mode="CHANGE")
print("Listening for hardware interrupts on GPIO 0. Press button on board...")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping event listener...")
    board.stop_events()
    board.close()
```

Line-by-line explanation:
- Line 5-9: Callback function invoked immediately when the ESP board registers an interrupt trigger.
- Line 12: `board.on_change()` registers the watcher on the ESP board and spawns a background thread consuming the `/api/events` SSE stream.
- Line 20: `board.stop_events()` safely terminates the streaming connection.

---

### 9. Atomic Batch Operations

Execute multiple read and write commands in a single HTTP request to eliminate network roundtrip overhead.

```python
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    pipeline = [
        {'type': 'write', 'pin': 2, 'value': 0},    # Turn on LED
        {'type': 'read', 'pin': 0},                 # Read button
        {'type': 'pwm', 'pin': 14, 'value': 512},   # Set 50% PWM
        {'type': 'read_analog', 'pin': 'A0'}        # Sample analog ADC
    ]

    response = board.batch(pipeline)
    for idx, result in enumerate(response['results']):
        print(f"Step {idx+1}: {result}")
```

Line-by-line explanation:
- Line 4-9: Constructs a JSON array containing the desired sequence of actions.
- Line 11: `board.batch()` dispatches the pipeline atomically to `/api/batch` on the ESP board.

---

## Pinout Reference

### ESP8266 NodeMCU Pinout

| Board Pin | ESP8266 GPIO | Functions | Notes |
|:---:|:---:|:---|:---|
| **D0** | GPIO 16 | Digital I/O | Deep sleep wake pin (`WAKE`) |
| **D1** | GPIO 5 | Digital I/O, I2C SCL, PWM | Recommended general I/O |
| **D2** | GPIO 4 | Digital I/O, I2C SDA, PWM | Recommended general I/O |
| **D3** | GPIO 0 | Digital I/O, PWM | Boot pin (pulled HIGH) |
| **D4** | GPIO 2 | Digital I/O, PWM, Onboard LED | Active-LOW onboard blue LED |
| **D5** | GPIO 14 | Digital I/O, SPI SCK, PWM | Recommended general I/O |
| **D6** | GPIO 12 | Digital I/O, SPI MISO, Servo, PWM | Recommended general I/O |
| **D7** | GPIO 13 | Digital I/O, SPI MOSI, PWM | Recommended general I/O |
| **D8** | GPIO 15 | Digital I/O, SPI CS, PWM | Boot pin (pulled LOW) |
| **A0** | ADC0 | Analog Input | 10-bit ADC (0.0V–3.3V on NodeMCU) |

### ESP32 DevKit Pinout

| Board Pin | ESP32 GPIO | Functions | Notes |
|:---:|:---:|:---|:---|
| **GPIO 2** | GPIO 2 | Digital I/O, Onboard LED, PWM | Active-HIGH onboard LED |
| **GPIO 4** | GPIO 4 | Digital I/O, PWM, ADC2 | General I/O |
| **GPIO 5** | GPIO 5 | Digital I/O, PWM, VSPI CS | General I/O |
| **GPIO 18** | GPIO 18 | Digital I/O, PWM, VSPI SCK | General I/O |
| **GPIO 19** | GPIO 19 | Digital I/O, PWM, VSPI MISO | General I/O |
| **GPIO 21** | GPIO 21 | Digital I/O, I2C SDA | Default hardware I2C SDA |
| **GPIO 22** | GPIO 22 | Digital I/O, I2C SCL | Default hardware I2C SCL |
| **GPIO 23** | GPIO 23 | Digital I/O, PWM, VSPI MOSI | General I/O |
| **GPIO 32 - 35** | GPIO 32-35 | Analog ADC1, Digital In | High-precision ADC |

---

## Command Line Interface (CLI)

| Command | Purpose |
|:---|:---|
| `esp-linker flash` | Auto-detect USB serial port and flash ESP8266 or ESP32 firmware |
| `esp-linker ota <IP>` | Flash compiled firmware Over-The-Air (OTA) via WiFi |
| `esp-linker i2c <IP>` | Scan I2C hardware bus and query sensors (MPU6050, BMP280) |
| `esp-linker events <IP>` | Stream real-time GPIO hardware interrupt events live to terminal |
| `esp-linker setup-wifi` | Interactive serial wizard to scan and configure WiFi credentials |
| `esp-linker test <IP>` | In-place live diagnostic dashboard testing all hardware subsystems |
| `esp-linker discover` | Scan local network for active ESP-Linker devices |
| `esp-linker detect` | List connected USB serial ports and ESP chips |
| `esp-linker dashboard` | Launch the modern browser-based hardware control dashboard |
| `esp-linker reset --ip <IP>` | Factory reset device settings and clear saved WiFi credentials |

### Command Options

```bash
# Flash options
esp-linker flash --chip auto        # Auto-detect between ESP8266 and ESP32
esp-linker flash --chip esp32       # Target ESP32 explicitly
esp-linker flash --chip esp8266     # Target ESP8266 explicitly
esp-linker flash --port COM4        # Target specific serial port
esp-linker flash --baud 115200      # Use 115,200 baud for noisy USB cables

# Over-The-Air update
esp-linker ota 192.168.1.9                          # Flash matching bundled firmware
esp-linker ota 192.168.1.9 --firmware custom.bin    # Flash custom binary

# I2C bus tools
esp-linker i2c 192.168.1.9 scan                     # Render 16x8 hex bus map
esp-linker i2c 192.168.1.9 sensors                  # Read MPU-6050 & BMP280 telemetry
esp-linker i2c 192.168.1.9 read --address 0x68 -l 6 # Read 6 bytes from address 0x68

# Live interrupt monitor
esp-linker events 192.168.1.9 --pin 0 --mode CHANGE # Stream events for GPIO 0

# Web Dashboard
esp-linker dashboard --port 8080                    # Launch control interface
```

---

## Support SKR Electronics Lab

If ESP-Linker helps your projects, DIY prototypes, or academic lab work, please consider supporting development:

<p align="left">
  <a href="https://ko-fi.com/skrelectronicslab" target="_blank">
    <img src="https://raw.githubusercontent.com/skr-electronics-lab/flyradar32/main/assets/kofi_button.svg" height="38" alt="Support on Ko-fi">
  </a>
</p>

- **YouTube**: [@skr_electronics_lab](https://youtube.com/@skr_electronics_lab)
- **Instagram**: [@skr_electronics_lab](https://instagram.com/skr_electronics_lab)
- **Twitter / X**: [@skrelectronics](https://twitter.com/skrelectronics)
- **Author**: SK Raihan (Founder, SKR Electronics Lab)
- **Email**: `skrelectronicslab@gmail.com`

---

## License

MIT License. Copyright (c) 2026 SK Raihan / SKR Electronics Lab. All rights reserved.
