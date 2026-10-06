# ESP-Linker: Universal Wireless GPIO Platform

[![PyPI version](https://img.shields.io/pypi/v/esp-linker?style=flat-square&color=0088cc)](https://pypi.org/project/esp-linker/)
[![Python versions](https://img.shields.io/pypi/pyversions/esp-linker?style=flat-square&color=22bb33)](https://pypi.org/project/esp-linker/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Support on Ko-fi](https://raw.githubusercontent.com/skr-electronics-lab/flyradar32/main/assets/kofi_button.svg)](https://ko-fi.com/skrelectronicslab)

ESP-Linker converts ESP8266 microcontrollers into high-performance, network-attached wireless GPIO servers. Program your hardware directly from Python over WiFi using an intuitive, PyFirmata-inspired interface without writing, compiling, or uploading Arduino C++ code for every project change.

---

## Key Capabilities

- **Zero C++ Firmware Workflow**: Precompiled, optimized C++ firmware binary is bundled inside the library. Flashes over USB in seconds using `esp-linker flash`.
- **PyFirmata-Inspired Python API**: Clean, intuitive hardware methods (`board.write(pin, val)`, `board.read(pin)`, `board.pwm(pin, val)`, `board.servo(pin, angle)`).
- **Auto-Configuring Pin Modes**: Pins automatically configure their internal registers based on the operation invoked (digital write, PWM, servo output).
- **Interactive WiFi Wizard**: Configure WiFi credentials directly over Serial without hardcoding SSIDs or passwords into source code.
- **Hardware Telemetry & Health**: Query heap memory, signal strength (RSSI), network IP, and uptime on demand.
- **Atomic Batch Commands**: Execute sequences of GPIO actions in a single network transaction to minimize network roundtrip latency.
- **Modern Animated Terminal UI**: Built with Rich featuring real-time progress bars, transfer speeds, ETA counters, and zero emojis.

---

## Supported Hardware

- **ESP8266 Modules**: NodeMCU v2 / v3, Wemos D1 Mini, ESP-12E / ESP-12F, Generic ESP8266 boards (4MB flash).
- **Operating Systems**: Windows 10/11, macOS, and Linux (x86_64, ARM64, Raspberry Pi OS).
- **Python Compatibility**: Python 3.7 through Python 3.12+.

---

## Installation

Install the latest stable release from PyPI:

```bash
pip install --upgrade esp-linker
```

To include the optional web dashboard:

```bash
pip install --upgrade "esp-linker[dashboard]"
```

---

## Quick Start: Three-Step Setup

### Step 1: Flash Firmware via USB

Connect your ESP8266 board to your PC using a micro-USB data cable, then run:

```bash
esp-linker flash
```

The flasher automatically detects the USB COM port (e.g., `COM4` on Windows or `/dev/ttyUSB0` on Linux), verifies bootloader communication, and flashes the bundled binary at 460,800 baud with real-time transfer progress.

### Step 2: Configure WiFi Credentials

Run the interactive WiFi setup wizard over the same USB connection:

```bash
esp-linker setup-wifi
```

1. Select your detected USB serial port.
2. The wizard requests the ESP8266 to scan for 2.4 GHz WiFi networks.
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
print(f"Connected to {board.firmware_name} at {board.device_ip}")
board.close()

# Method B: Python Context Manager (automatically cleans up HTTP session on exit)
with ESPBoard(ip="192.168.1.9", timeout=3.0) as board:
    status = board.status()
    print(f"Board Uptime: {status['uptime']} seconds | Free Heap: {status['free_heap']} bytes")

# Method C: Zero-Config Auto Discovery via mDNS
# Scans the local network for '_http._tcp.local.' and connects to the first responding board
auto_board = connect_auto(timeout=10.0)
print(f"Auto-connected to device at {auto_board.device_ip}")
auto_board.close()
```

#### Line-by-Line Explanation:
- `board = ESPBoard(ip="192.168.1.9")`: Instantiates the client, tests the `/status` endpoint, and caches the board's pin capabilities.
- `board.close()`: Explicitly closes the underlying `requests.Session` socket connection to free system resources.
- `with ESPBoard(ip="192.168.1.9", timeout=3.0) as board`: Uses Python's context manager protocol (`__enter__` and `__exit__`), guaranteeing that connections close even if an unhandled exception occurs.
- `connect_auto(timeout=10.0)`: Broadcasts mDNS service queries on your local subnet to locate any active ESP-Linker boards without requiring hardcoded IP addresses.

---

### 2. Digital Output: Blinking LEDs & Switching Relays

Control digital output states on any GPIO pin. By default, `auto_mode=True` automatically configures the pin to `OUTPUT` mode on the first write.

```python
import time
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    # On NodeMCU and D1 Mini, the onboard blue LED is on GPIO 2 (labeled D4).
    # Note: The ESP8266 onboard LED is active-LOW (0 = ON, 1 = OFF).
    led_pin = 2

    print("Blinking onboard LED 5 times...")
    for cycle in range(1, 6):
        # Turn LED ON (logic LOW for onboard LED)
        board.write(led_pin, 0)
        print(f"Cycle {cycle}: LED ON")
        time.sleep(0.5)

        # Turn LED OFF (logic HIGH for onboard LED)
        board.write(led_pin, 1)
        print(f"Cycle {cycle}: LED OFF")
        time.sleep(0.5)

    # Controlling an external standard active-HIGH relay or LED on GPIO 4 (labeled D2)
    relay_pin = 4
    board.set_mode(relay_pin, "OUTPUT")  # Explicit mode configuration
    board.write(relay_pin, 1)             # Turn relay ON (3.3V)
    time.sleep(1.0)
    board.write(relay_pin, 0)             # Turn relay OFF (0V)
```

#### Line-by-Line Explanation:
- `led_pin = 2`: Defines the target GPIO pin number. GPIO 2 maps to physical pin D4 on standard NodeMCU boards.
- `board.write(led_pin, 0)`: Sends a `POST /gpio/write` request with `{"pin": 2, "value": 0}`. Because `auto_mode` is enabled by default, the library sets the pin mode to `OUTPUT` if not already set.
- `board.set_mode(relay_pin, "OUTPUT")`: Explicitly invokes `POST /gpio/set_mode` to configure hardware registers as a push-pull digital output.
- `board.write(relay_pin, 1)`: Drives GPIO 4 HIGH to 3.3V rail.

---

### 3. Digital Input: Push Buttons & Contact Switches

Read digital sensor inputs and mechanical switches. Use `INPUT_PULLUP` to enable the ESP8266 internal 30kΩ–100kΩ pull-up resistor, eliminating the need for an external physical resistor.

```python
import time
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    # Connect a momentary push button between GPIO 14 (labeled D5) and GND
    button_pin = 14

    # Enable the internal pull-up resistor
    board.set_mode(button_pin, "INPUT_PULLUP")
    print("Monitoring button on GPIO 14 (Press Ctrl+C to stop)...")

    try:
        last_state = 1
        for _ in range(30):  # Monitor for 15 seconds
            # Read digital input level (1 = unpressed, 0 = pressed to GND)
            state = board.read(button_pin)

            if state != last_state:
                if state == 0:
                    print(">> Button PRESSED! (Contact connected to GND)")
                else:
                    print(">> Button RELEASED! (Pulled HIGH internally)")
                last_state = state

            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Monitoring stopped.")
```

#### Line-by-Line Explanation:
- `board.set_mode(button_pin, "INPUT_PULLUP")`: Sends `POST /gpio/set_mode` instructing the ESP8266 to activate its internal weak pull-up resistor on GPIO 14.
- `state = board.read(button_pin)`: Sends `GET /gpio/read?pin=14` and returns the instantaneous logic level (`0` or `1`).
- `if state == 0`: When the button is pressed, it shorts GPIO 14 to GND (logic 0). When released, the internal pull-up returns the pin to 3.3V (logic 1).

---

### 4. PWM Generator: LED Fading & Motor Speed Control

The ESP8266 provides 10-bit hardware PWM across GPIO pins (duty cycle values from `0` to `1023` at 1 kHz frequency).

```python
import time
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    # Connect an external LED (with a 220-330 ohm resistor) to GPIO 12 (labeled D6)
    pwm_pin = 12

    print("Beginning smooth LED breathing animation...")

    # Fade in: 0% to 100% duty cycle
    for duty in range(0, 1024, 32):
        board.pwm(pwm_pin, duty)
        percentage = (duty / 1023.0) * 100
        print(f"Brightness: {percentage:5.1f}% (Duty value: {duty})")
        time.sleep(0.04)

    # Fade out: 100% to 0% duty cycle
    for duty in range(1023, -1, -32):
        board.pwm(pwm_pin, duty)
        percentage = (duty / 1023.0) * 100
        print(f"Brightness: {percentage:5.1f}% (Duty value: {duty})")
        time.sleep(0.04)

    # Fully turn off PWM output
    board.pwm(pwm_pin, 0)
    print("PWM cycle complete.")
```

#### Line-by-Line Explanation:
- `board.pwm(pwm_pin, duty)`: Sends `POST /gpio/pwm` with `{"pin": 12, "value": duty}`. The ESP8266 firmware routes the pin through `analogWrite(pin, duty)`.
- `range(0, 1024, 32)`: Sweeps through the 10-bit resolution range (0 is completely OFF, 1023 is 100% continuous HIGH).
- `board.pwm(pwm_pin, 0)`: Ensures the pin output drops to steady 0V upon task completion.

---

### 5. Servo Motor Control: Precise Angle Positioning

Drive standard 50 Hz hobby servo motors (such as SG90, MG90S, or standard 180° servos) without requiring dedicated external servo driver shields.

```python
import time
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    # Connect servo signal wire to GPIO 13 (labeled D7)
    # Ensure servo VCC is connected to external 5V power and grounds are common
    servo_pin = 13

    # Define sweep positions in degrees
    positions = [0, 45, 90, 135, 180, 90]

    for angle in positions:
        print(f"Commanding servo on GPIO {servo_pin} to {angle} degrees...")
        board.servo(servo_pin, angle)
        # Allow sufficient time for the physical motor gear train to rotate
        time.sleep(0.8)

    print("Servo positioning test finished.")
```

#### Line-by-Line Explanation:
- `servo_pin = 13`: GPIO 13 (D7) is an ideal servo pin because it does not interfere with ESP8266 boot configurations.
- `board.servo(servo_pin, angle)`: Validates that `0 <= angle <= 180` and sends `POST /servo/write` with `{"pin": 13, "angle": angle}`.
- The ESP8266 firmware attaches an internal Arduino `Servo` instance to the pin, producing exact 544 µs to 2400 µs pulse-width signals at 50 Hz.
- `time.sleep(0.8)`: Provides a physical delay allowing the mechanical gears to reach the commanded angle before moving to the next position.

---

### 6. Analog Input: Reading the 10-Bit ADC (A0)

The ESP8266 features a single built-in Analog-to-Digital Converter (`A0`). On raw ESP8266 chips, the input range is 0.0V–1.0V; on NodeMCU and D1 Mini boards, an onboard resistor voltage divider extends the measurable range to 0.0V–3.3V.

```python
import time
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    print("Reading analog voltages from pin A0...")

    for sample in range(1, 6):
        # Read raw ADC integer (0 - 1024)
        raw_adc = board.read("A0")

        # Convert to calibrated voltage (0.0V to 3.3V on NodeMCU boards)
        voltage = (raw_adc / 1024.0) * 3.3

        print(f"Sample {sample}: Raw ADC = {raw_adc:4d} / 1024  |  Estimated Voltage = {voltage:4.2f} V")
        time.sleep(0.5)
```

#### Line-by-Line Explanation:
- `raw_adc = board.read("A0")`: Sends `GET /gpio/read?pin=A0`. The ESP8266 calls `analogRead(A0)` and returns the 10-bit integer reading.
- `voltage = (raw_adc / 1024.0) * 3.3`: Standard linear ADC conversion formula scaling the 1024 discrete steps across the 3.3V input range.

---

### 7. Atomic Batch Operations: Ultra-Low Latency Execution

When multiple pins need to update simultaneously (e.g., setting an RGB LED, steering a differential drive robot, or taking coordinated readings), sending individual HTTP requests introduces network round-trip delays. The `batch()` API executes multiple operations in a single atomic transaction.

```python
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    # Prepare a list of actions to execute in one network payload
    pipeline = [
        {"type": "write", "pin": 2, "value": 0},      # Turn onboard LED ON
        {"type": "pwm", "pin": 14, "value": 768},     # Set PWM channel to 75% duty
        {"type": "servo", "pin": 12, "angle": 45},    # Move servo to 45 degrees
        {"type": "read", "pin": 4},                   # Read digital switch state
        {"type": "read", "pin": "A0"}                 # Read analog sensor value
    ]

    print(f"Transmitting batch pipeline with {len(pipeline)} operations...")
    response = board.batch(pipeline)

    print(f"Batch execution status: {response.get('status')}")
    for idx, res in enumerate(response.get('results', []), 1):
        pin_id = res.get('pin')
        success = res.get('success')
        value = res.get('value', 'N/A')
        print(f"  Step {idx}: Pin {pin_id} | Success: {success} | Returned Value: {value}")
```

#### Line-by-Line Explanation:
- `pipeline = [...]`: Builds a list of operation dictionaries. Supported operation types include `write`, `read`, `pwm`, and `servo`.
- `response = board.batch(pipeline)`: Transmits `POST /gpio/batch` containing the entire operation array in a single JSON payload.
- The ESP8266 executes each operation sequentially in microcontroller RAM without any network latency between steps, then returns an array of results.

---

### 8. System Status, Hardware Capabilities & Health Monitoring

Monitor your ESP8266's memory health, WiFi connection strength, and hardware capabilities directly from Python.

```python
from esp_linker import ESPBoard

with ESPBoard(ip="192.168.1.9") as board:
    # 1. Hardware capabilities
    caps = board.capabilities()
    print("--- Accessible Hardware Pins ---")
    for pin_info in caps.get("pins", []):
        pin_num = pin_info["pin"]
        pwm_cap = "PWM" if pin_info.get("pwm") else "---"
        servo_cap = "SERVO" if pin_info.get("servo") else "---"
        print(f"  GPIO {pin_num:2d} -> Capabilities: {pwm_cap:<5} {servo_cap:<5}")

    # 2. System telemetry
    telemetry = board.status()
    print("\n--- System Telemetry ---")
    print(f"  Firmware:      {telemetry.get('firmware_name')} v{telemetry.get('firmware_version')}")
    print(f"  Free RAM Heap: {telemetry.get('free_heap'):,} bytes")
    print(f"  WiFi SSID:     {telemetry.get('wifi_ssid')}")
    print(f"  WiFi RSSI:     {telemetry.get('wifi_rssi')} dBm")
    print(f"  Uptime:        {telemetry.get('uptime')} seconds")

    # 3. Comprehensive device profile dictionary
    info = board.get_device_info()
    print(f"\nDevice Profile Summary: {info['firmware_name']} | Pin Count: {info['pin_count']}")
```

#### Line-by-Line Explanation:
- `board.capabilities()`: Queries `GET /capabilities` to return the complete JSON capability matrix programmed into the firmware, guaranteeing that your Python code never addresses unsupported pins.
- `board.status()`: Queries `GET /status` to inspect available heap memory (`free_heap`), preventing memory leaks during long-running tasks.
- `board.get_device_info()`: Consolidates IP, URL, firmware version, and pin statistics into a clean dictionary.

---

### 9. Multi-Device Fleet Management

When operating multiple ESP-Linker boards across your local network (e.g., multiple sensor stations or lab benches), use `DeviceManager` to register, tag, discover, and control your device fleet.

```python
from esp_linker import get_device_manager, ESPBoard

# Obtain the central DeviceManager singleton
manager = get_device_manager()

# Discover all active boards on the local subnet
print("Scanning network for ESP-Linker devices...")
devices = manager.discover_and_register(timeout=10.0)
print(f"Found {len(devices)} active board(s) on network.")

# Tag and assign meaningful aliases to boards
if devices:
    first_device = devices[0]
    manager.update_device(
        ip=first_device.ip,
        name="LivingRoom-Node",
        tags=["climate", "indoor"],
        notes="Bench 1 ESP8266 NodeMCU"
    )

# List all stored devices in registry
for dev in manager.get_all_devices():
    print(f"Device: {dev.name:<20} IP: {dev.ip:<15} Tags: {dev.tags}")

# Connect directly to a device by its assigned name
board = manager.connect("LivingRoom-Node")
print(f"Connected to {board.device_ip} using device alias!")
board.close()
```

#### Line-by-Line Explanation:
- `manager = get_device_manager()`: Retrieves the local SQLite/JSON device registry manager.
- `manager.discover_and_register()`: Runs automated discovery and adds all responding ESP-Linker boards to your local registry.
- `manager.update_device(...)`: Attaches persistent names and metadata tags to device entries.
- `manager.connect("LivingRoom-Node")`: Resolves the stored IP address by alias and returns an initialized `ESPBoard` instance.

---

### 10. Real-World Complete Project: Smart IoT Controller

This production-grade example combines analog sensor sampling, button input handling, PWM indicator driving, and automated health checks in a clean event loop.

```python
import time
from esp_linker import ESPBoard

# Connect to the board
with ESPBoard(ip="192.168.1.9", timeout=3.0) as board:
    # Pin definitions
    STATUS_LED = 2      # GPIO 2 (Onboard blue LED, active-LOW)
    ALERT_PWM  = 14     # GPIO 14 (D5, Indicator LED or Buzzer)
    INPUT_BTN  = 4      # GPIO 4 (D2, Emergency stop or trigger button)

    # Initialize pins
    board.set_mode(STATUS_LED, "OUTPUT")
    board.set_mode(ALERT_PWM, "PWM")
    board.set_mode(INPUT_BTN, "INPUT_PULLUP")

    print("--- Smart IoT Controller Active ---")
    print("Press Ctrl+C to terminate controller loop.")

    try:
        loop_counter = 0
        while True:
            # 1. Read analog light sensor or potentiometer on A0
            raw_sensor = board.read("A0")
            sensor_volts = (raw_sensor / 1024.0) * 3.3

            # 2. Read physical button state
            button_pressed = (board.read(INPUT_BTN) == 0)

            # 3. Dynamic PWM response based on sensor reading
            # Map raw sensor (0 - 1024) directly to PWM duty cycle (0 - 1023)
            pwm_duty = min(raw_sensor, 1023)
            board.pwm(ALERT_PWM, pwm_duty)

            # 4. Blink heartbeat LED
            board.write(STATUS_LED, loop_counter % 2)

            # Display real-time telemetry
            btn_status = "PRESSED" if button_pressed else "IDLE"
            print(f"[Loop {loop_counter:03d}] Sensor: {raw_sensor:4d} ({sensor_volts:4.2f}V) | PWM: {pwm_duty:4d} | Button: {btn_status}")

            loop_counter += 1
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nShutting down controller safely...")
        # Reset all actuators to safe state
        board.pwm(ALERT_PWM, 0)
        board.write(STATUS_LED, 1)  # Turn off onboard LED
        print("Actuators disarmed. Goodbye!")
```

---

## ESP8266 NodeMCU Pin Reference

| Board Label | ESP8266 GPIO | Primary Functions | Notes |
|:---:|:---:|:---|:---|
| **D0** | GPIO 16 | Digital I/O | Deep sleep wake pin (`WAKE`) |
| **D1** | GPIO 5 | Digital I/O, I2C SCL, PWM | Recommended general I/O |
| **D2** | GPIO 4 | Digital I/O, I2C SDA, PWM | Recommended general I/O |
| **D3** | GPIO 0 | Digital I/O, PWM | Pulled HIGH, boot configuration |
| **D4** | GPIO 2 | Digital I/O, PWM, Onboard LED | Active-LOW onboard blue LED |
| **D5** | GPIO 14 | Digital I/O, SPI SCK, PWM | Recommended general I/O |
| **D6** | GPIO 12 | Digital I/O, SPI MISO, Servo, PWM | Recommended general I/O |
| **D7** | GPIO 13 | Digital I/O, SPI MOSI, PWM | Recommended general I/O |
| **D8** | GPIO 15 | Digital I/O, SPI CS, PWM | Pulled LOW, boot configuration |
| **A0** | ADC0 | Analog Input | 10-bit ADC (0.0V–3.3V on NodeMCU) |

---

## Complete CLI Command Reference

| Command | Purpose |
|:---|:---|
| `esp-linker flash` | Auto-detect USB serial port and flash bundled firmware |
| `esp-linker setup-wifi` | Interactive serial wizard to scan and configure WiFi credentials |
| `esp-linker test <IP>` | In-place live diagnostic dashboard testing all hardware subsystems |
| `esp-linker discover` | Scan local network for active ESP-Linker devices |
| `esp-linker detect` | List connected USB serial ports and ESP chips |
| `esp-linker dashboard` | Launch the browser-based control dashboard |
| `esp-linker reset --ip <IP>` | Factory reset device settings and clear saved WiFi credentials |

### Command Options

```bash
# Flash options
esp-linker flash --port COM4        # Target a specific serial port
esp-linker flash --baud 115200      # Use safe 115,200 baud for long or noisy USB cables
esp-linker flash --no-erase         # Skip flash erase before flashing
esp-linker flash --chip-info        # Display ESP8266 chip ID and MAC address
esp-linker flash --firmware-info    # Display metadata of bundled firmware binary

# Diagnostic options
esp-linker test 192.168.1.9 --timeout 5.0    # Set custom network timeout
esp-linker test 192.168.1.9 --led-pin 2      # Specify custom LED pin for digital test
esp-linker test 192.168.1.9 --pwm-pin 14     # Specify custom PWM pin for sweep test
esp-linker test 192.168.1.9 --servo-pin 12   # Specify custom servo pin for sweep test

# Global flags
--plain    # Disable colors and animations (auto-enabled when piped or not in a TTY)
--debug    # Enable verbose debug logs and Rich exception tracebacks
```

---

## Support SKR Electronics Lab

If ESP-Linker helps your projects, DIY prototypes, or academic lab work, please consider supporting development:

[![Support on Ko-fi](https://raw.githubusercontent.com/skr-electronics-lab/flyradar32/main/assets/kofi_button.svg)](https://ko-fi.com/skrelectronicslab)

- **YouTube**: [@skr_electronics_lab](https://youtube.com/@skr_electronics_lab)
- **Instagram**: [@skr_electronics_lab](https://instagram.com/skr_electronics_lab)
- **Twitter / X**: [@skrelectronics](https://twitter.com/skrelectronics)
- **Author**: SK Raihan (Founder, SKR Electronics Lab)
- **Email**: `skrelectronicslab@gmail.com`

---

## License

MIT License. Copyright (c) 2025 SK Raihan / SKR Electronics Lab. All rights reserved.
