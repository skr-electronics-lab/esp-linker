"""
ESP-Linker Exception Classes
(c) 2025 SK Raihan / SKR Electronics Lab -- All Rights Reserved.

Custom exception classes for ESP-Linker library
"""

class ESPLinkerError(Exception):
    """Base exception class for ESP-Linker library"""
    pass

class ConnectionError(ESPLinkerError):
    """Raised when connection to ESP8266 fails"""
    pass

class DeviceNotFoundError(ESPLinkerError):
    """Raised when ESP8266 device is not found on network"""
    pass

class InvalidPinError(ESPLinkerError):
    """Raised when invalid pin number is specified"""
    pass

class InvalidModeError(ESPLinkerError):
    """Raised when invalid pin mode is specified"""
    pass

class InvalidValueError(ESPLinkerError):
    """Raised when invalid value is provided"""
    pass

class TimeoutError(ESPLinkerError):
    """Raised when request times out"""
    pass

class APIError(ESPLinkerError):
    """Raised when API request fails"""
    pass

class ConfigurationError(ESPLinkerError):
    """Raised when configuration is invalid"""
    pass

class FirmwareError(ESPLinkerError):
    """Raised when firmware version is incompatible"""
    pass

class FlashError(ESPLinkerError):
    """Raised when firmware flashing fails"""
    pass
