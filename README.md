# ⚡ ESP-Linker: Wireless GPIO & IoT Platform for Python

Control ESP8266 microcontrollers wirelessly over WiFi using an intuitive, PyFirmata-inspired Python API!

[![PyPI version](https://img.shields.io/pypi/v/esp-linker?style=flat-square&logo=pypi&logoColor=white&color=blue)](https://pypi.org/project/esp-linker/)
[![Python versions](https://img.shields.io/pypi/pyversions/esp-linker?style=flat-square&logo=python&logoColor=white&color=green)](https://pypi.org/project/esp-linker/)
[![Downloads](https://img.shields.io/pypi/dm/esp-linker?style=flat-square&logo=download&logoColor=white&color=orange)](https://pypistats.org/packages/esp-linker)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![YouTube](https://img.shields.io/badge/YouTube-SKR_Electronics_Lab-red?style=flat-square&logo=youtube)](https://www.youtube.com/@skr_electronics_lab)
[![Instagram](https://img.shields.io/badge/Instagram-@skr__electronics__lab-purple?style=flat-square&logo=instagram)](https://www.instagram.com/skr_electronics_lab)

---

## 🌟 Overview

**ESP-Linker** bridges the gap between Python and embedded electronics. Instead of writing custom C++ firmware, compiling sketches, and uploading via USB cables for every hardware change, ESP-Linker turns your board into a remote wireless GPIO server.

Flash the bundled firmware **once**, and control all digital pins, PWM channels, servos, and analog inputs directly from your Python scripts on Windows, macOS, or Linux!

### ✨ Key Features

- **🚀 One-Command Flashing**: Precompiled binary included — flash with `esp-linker flash` in seconds (no Arduino IDE required).
- **📡 WiFi Auto-Discovery**: Finds boards automatically on your local network using mDNS.
- **🔌 PyFirmata-Inspired Python API**: Simple, readable commands like `board.write(pin, 1)` and `board.read(pin)`.
- **🎛️ Multi-Peripheral Control**: Digital I/O, PWM dimming, Servo positioning, and ADC reading.
- **🔄 Auto-Mode Setup**: Pins configure themselves automatically on write operations.
- **🖥️ Built-in Web Dashboard**: Launch a local web UI to monitor and toggle GPIO pins in real time.
- **⚡ Interactive WiFi Wizard**: Interactive CLI wizard to scan and connect your board to local WiFi over USB serial.

---

## 🚀 Quick Start in 60 Seconds

### 1. Install the Library

```bash
pip install esp-linker
```

### 2. Connect Your Board & Flash Firmware

Connect your ESP8266 (NodeMCU, D1 Mini, etc.) via USB:

```bash
esp-linker flash
```

*The flasher automatically detects your USB port, checks connection speed, and flashes the verified firmware.*

### 3. Configure WiFi

Run the interactive WiFi configuration wizard:

```bash
esp-linker setup-wifi
```

*Follow the prompt to select your WiFi network and enter your password. Once connected, your ESP8266 joins your home/office network.*

### 4. Write Your Python Code!

```python
from esp_linker import connect_auto
import time

# Auto-discovers and connects to your ESP-Linker board on the network
board = connect_auto()

# Blink built-in LED (GPIO 2 on NodeMCU / ESP8266)
for _ in range(5):
    board.write(2, 1)  # LED ON
    time.sleep(0.5)
    board.write(2, 0)  # LED OFF
    time.sleep(0.5)
```

---

## 💻 Python Examples

### 1. Connecting to Board

```python
from esp_linker import ESPBoard, connect_auto

# Option A: Automatic discovery via mDNS
board = connect_auto()

# Option B: Direct IP connection
board = ESPBoard(ip="192.168.1.100")
```

### 2. Digital Input (Reading a Button or Sensor)

```python
from esp_linker import ESPBoard

board = ESPBoard(ip="192.168.1.100")

# Set GPIO 4 to INPUT with internal pull-up resistor
board.set_mode(4, "INPUT_PULLUP")

# Read pin state (0 or 1)
state = board.read(4)
print(f"Button state: {state}")
```

### 3. PWM (LED Dimming / Motor Speed)

```python
from esp_linker import ESPBoard
import time

board = ESPBoard(ip="192.168.1.100")

# Smooth LED fade (0 to 1023 duty cycle)
for duty in range(0, 1024, 50):
    board.pwm(4, duty)
    time.sleep(0.05)
```

### 4. Servo Motor Control

```python
from esp_linker import ESPBoard
import time

board = ESPBoard(ip="192.168.1.100")

# Sweep servo on GPIO 5 from 0 to 180 degrees
for angle in [0, 45, 90, 135, 180, 90]:
    board.servo(5, angle)
    time.sleep(0.5)
```

### 5. Analog Reading (ADC A0)

```python
from esp_linker import ESPBoard

board = ESPBoard(ip="192.168.1.100")

# Read 10-bit analog voltage (0 - 1024)
raw = board.read("A0")
voltage = (raw / 1024.0) * 3.3
print(f"Analog Value: {raw} ({voltage:.2f}V)")
```

### 6. High-Speed Batch Operations

Send multiple GPIO updates in a single network round-trip:

```python
from esp_linker import ESPBoard

board = ESPBoard(ip="192.168.1.100")

operations = [
    {"type": "write", "pin": 2, "value": 1},
    {"type": "pwm", "pin": 4, "value": 512},
    {"type": "servo", "pin": 5, "angle": 90},
    {"type": "read", "pin": 12}
]

result = board.batch(operations)
print("Batch results:", result)
```

---

## 🛠️ Command-Line Interface (CLI)

ESP-Linker includes a complete suite of command-line tools:

| Command | Description |
|---|---|
| `esp-linker flash` | Auto-detect and flash firmware to ESP8266 |
| `esp-linker flash --port COM3` | Flash firmware to a specific serial port |
| `esp-linker setup-wifi` | Interactive USB serial WiFi configuration wizard |
| `esp-linker discover` | Scan local network for active ESP-Linker devices |
| `esp-linker test <IP>` | Run comprehensive hardware test suite on board |
| `esp-linker dashboard` | Launch local web control dashboard |
| `esp-linker reset --ip <IP>` | Factory reset board back to initial state |

---

## 📌 NodeMCU Pin Mapping Reference

When using NodeMCU boards, use the following GPIO numbers in your Python code:

| NodeMCU Pin Label | ESP8266 GPIO Number | Capabilities | Notes |
|:---:|:---:|:---|:---|
| **D0** | GPIO 16 | Digital I/O | Wake pin (no PWM/Interrupt) |
| **D1** | GPIO 5 | Digital, PWM, Servo | General Purpose |
| **D2** | GPIO 4 | Digital, PWM, Servo | General Purpose |
| **D3** | GPIO 0 | Digital, Servo | Bootloader pin (pull high) |
| **D4** | GPIO 2 | Digital, PWM, Servo | Built-in Blue LED (active LOW) |
| **D5** | GPIO 14 | Digital, PWM, Servo, SPI CLK | General Purpose |
| **D6** | GPIO 12 | Digital, PWM, Servo, SPI MISO| General Purpose |
| **D7** | GPIO 13 | Digital, PWM, Servo, SPI MOSI| General Purpose |
| **D8** | GPIO 15 | Digital, PWM, Servo, SPI CS  | Boot pin (pulled to GND) |
| **A0** | ADC0 | Analog Input (0 - 1.0V / 3.3V) | Read with `board.read('A0')` |

---

## 🌐 Web Dashboard

Want a visual control panel? Launch the built-in browser dashboard:

```bash
esp-linker dashboard
```

Open `http://localhost:8080` in your browser to inspect discovered boards, toggle pins with switches, and monitor telemetry.

---

## ❓ Troubleshooting

- **Flasher times out waiting for packet**:
  - Hold down the **BOOT** (or **FLASH**) button on your ESP8266 board right when plugging in the USB cable or when flashing starts.
  - Make sure your USB cable supports data transfer (some cheap cables are power-only).
- **Device not found by `connect_auto()`**:
  - Ensure your computer and your ESP8266 are on the same WiFi network (or 2.4 GHz band).
  - Verify that your router doesn't block mDNS/multicast traffic.
  - If mDNS is disabled on your network, connect directly using the board's IP address: `board = ESPBoard("192.168.x.x")`.

---

## 👨‍💻 Author & Community

Developed with ❤️ by **SK Raihan** ([SKR Electronics Lab](https://www.youtube.com/@skr_electronics_lab)).

- **YouTube**: [@skr_electronics_lab](https://www.youtube.com/@skr_electronics_lab)
- **Instagram**: [@skr_electronics_lab](https://www.instagram.com/skr_electronics_lab)
- **Twitter / X**: [@skrelectronics](https://twitter.com/skrelectronics)
- **GitHub**: [skr-electronics-lab](https://github.com/skr-electronics-lab)
- **Support & Coffee**: [buymeacoffee.com/skrelectronics](https://buymeacoffee.com/skrelectronics)

## 📄 License

This project is licensed under the **MIT License**.
