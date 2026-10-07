"""
ESP-Linker Python Library
(c) 2025 SK Raihan / SKR Electronics Lab -- All Rights Reserved.

Author: SK Raihan
Website: https://www.skrelectronicslab.com
Email: skrelectronicslab@gmail.com
YouTube: https://www.youtube.com/@skr_electronics_lab
Instagram: https://www.instagram.com/skr_electronics_lab
Twitter: https://www.twitter.com/skrelectronics
Buy Me a Coffee: https://buymeacoffee.com/skrelectronics

Wireless GPIO and peripheral control for ESP8266 boards over WiFi.
Inspired by the user-friendliness of PyFirmata.
"""

# Import version information from single source of truth
from .version import (
    __version__,
    AUTHOR as __author__,
    EMAIL as __email__,
    LICENSE as __license__,
    COPYRIGHT as __copyright__,
    get_version,
    get_version_info
)

# Import logger
from .logger import get_logger, set_log_level, setup_logging, debug, info, warning, error, critical

# Get module logger
logger = get_logger(__name__)

# Import main classes for easy access
from .espboard import ESPBoard
from .exceptions import (
    ESPLinkerError,
    ConnectionError,
    DeviceNotFoundError,
    InvalidPinError,
    InvalidModeError,
    InvalidValueError,
    TimeoutError,
    APIError,
    FlashError
)
from .utils import discover_devices, scan_network
from .flasher import (
    flash_esp8266,
    flash_esp,
    detect_esp8266,
    get_chip_info,
    ESP8266Flasher,
    ESPFlasher
)
from .device_manager import get_device_manager

# Define what gets imported with "from esp_linker import *"
__all__ = [
    # Main classes
    'ESPBoard',
    
    # Exceptions
    'ESPLinkerError',
    'ConnectionError',
    'DeviceNotFoundError',
    'InvalidPinError',
    'InvalidModeError',
    'InvalidValueError',
    'TimeoutError',
    'APIError',
    'FlashError',
    
    # Utility functions
    'discover_devices',
    'scan_network',
    'connect_auto',
    'connect_first',
    'list_devices',
    'connect_to_device',

    # Firmware flashing functions
    'flash_esp',
    'flash_esp8266',
    'detect_esp8266',
    'get_chip_info',
    'ESP8266Flasher',
    'ESPFlasher',

    # Device management
    'get_device_manager',
    
    # Constants
    '__version__',
    '__author__',
    '__email__',
]

# Pin mode constants for easy access
class PinMode:
    """Pin mode constants matching firmware definitions"""
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    INPUT_PULLUP = "INPUT_PULLUP"
    PWM = "PWM"
    SERVO = "SERVO"

# Add PinMode to exports
__all__.append('PinMode')

# Library information
def get_info():
    """Get library information"""
    return {
        'name': 'esp-linker',
        'version': __version__,
        'author': __author__,
        'email': __email__,
        'website': 'https://www.skrelectronicslab.com',
        'github': 'https://github.com/skr-electronics-lab/esp-linker',
        'description': 'Wireless GPIO and peripheral control for ESP8266 boards over WiFi with ESP-Linker'
    }

# Convenience functions for auto-discovery
def connect_auto():
    """
    Automatically discover and connect to the first available ESP-Linker device.

    Returns:
        ESPBoard: Connected board instance

    Raises:
        ConnectionError: If no devices found

    Example:
        board = connect_auto()
        board.write(2, 1)  # Control LED
        board.close()
    """
    return ESPBoard()  # Auto-discovery is enabled by default

def connect_first():
    """
    Alias for connect_auto() - connects to first discovered device.

    Returns:
        ESPBoard: Connected board instance
    """
    return connect_auto()

def list_devices():
    """
    List all available ESP-Linker devices on the network.

    Returns:
        List of device information dictionaries

    Example:
        devices = list_devices()
        for device in devices:
            print(f"Device: {device['firmware_name']} at {device['ip']}")
    """
    return discover_devices()

def connect_to_device(device_index: int = 0):
    """
    Connect to a specific device by index from discovered devices.

    Args:
        device_index: Index of device to connect to (0 = first device)

    Returns:
        ESPBoard: Connected board instance

    Example:
        devices = list_devices()
        board = connect_to_device(1)  # Connect to second device
    """
    devices = discover_devices()
    if not devices:
        raise ConnectionError("No ESP-Linker devices found")

    if device_index >= len(devices):
        raise IndexError(f"Device index {device_index} out of range. Found {len(devices)} devices.")

    device = devices[device_index]
    return ESPBoard(ip=device['ip'])

# Quick start example
def quick_start_example():
    """Print a quick start example"""
    example = """
# ESP-Linker Quick Start Example

from esp_linker import ESPBoard, PinMode, connect_auto

# Method 1: Auto-discover and connect
board = connect_auto()  # Automatically finds first device

# Method 2: Connect to specific IP
# board = ESPBoard(ip='192.168.1.100')

# Method 3: Discover devices and choose
# devices = list_devices()
# board = connect_to_device(0)  # Connect to first device

# Configure and control pins
board.set_mode(2, PinMode.OUTPUT)     # Set pin 2 to OUTPUT
board.write(2, 1)                     # Turn on LED
board.write(2, 0)                     # Turn off LED

# PWM control
board.set_mode(4, PinMode.PWM)        # Set pin 4 to PWM
board.pwm(4, 512)                     # 50% duty cycle

# Servo control
board.set_mode(5, PinMode.SERVO)      # Set pin 5 to SERVO
board.servo(5, 90)                    # Move to 90 degrees

# Read pins
value = board.read(2)                 # Read digital pin
analog_value = board.read('A0')       # Read analog pin

# Batch operations
board.batch([
    {'type': 'write', 'pin': 2, 'value': 1},
    {'type': 'pwm', 'pin': 4, 'value': 256},
    {'type': 'servo', 'pin': 5, 'angle': 45}
])

# Get board status
status = board.status()
print(f"Device: {status['firmware_name']} v{status['firmware_version']}")
print(f"WiFi: {status['wifi_ssid']} ({status['wifi_ip']})")
print(f"Uptime: {status['uptime']/1000:.1f} seconds")

# Close connection
board.close()
"""
    print(example)

# Add to exports
__all__.extend(['get_info', 'quick_start_example'])
