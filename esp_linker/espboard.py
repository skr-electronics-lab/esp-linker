"""
ESP-Linker Board Control Class
(c) 2025 SK Raihan / SKR Electronics Lab -- All Rights Reserved.

Main class for controlling ESP8266 boards via WiFi
"""

import requests
import json
import time
from typing import Dict, List, Any, Optional, Union

# Import exceptions explicitly to avoid circular imports
from .exceptions import (
    ESPLinkerError,
    ConnectionError,
    DeviceNotFoundError,
    InvalidPinError,
    InvalidModeError,
    InvalidValueError,
    TimeoutError,
    APIError
)
from .utils import validate_pin, validate_mode, validate_pwm_value, validate_servo_angle, discover_devices

class ESPBoard:
    """
    Main class for controlling ESP8266 boards via WiFi.
    
    Provides PyFirmata-like interface for wireless GPIO control.
    """
    
    def __init__(self, ip: str = None, url: str = None, timeout: float = 5.0, retries: int = 3, auto_discover: bool = True, auto_retry: bool = False, max_retries: int = 5, health_check: bool = False):
        """
        Initialize ESP8266 board connection.

        Args:
            ip: IP address of ESP8266 (e.g., '192.168.1.100'). If None, auto-discovery is used.
            url: Full URL to ESP8266 (e.g., 'http://esp-linker.local')
            timeout: Request timeout in seconds
            retries: Number of retry attempts for failed requests
            auto_discover: Enable automatic device discovery if ip/url not provided
            auto_retry: Enable automatic retry with exponential backoff
            max_retries: Maximum number of auto-retry attempts
            health_check: Enable periodic connection health checks

        Example:
            # Auto-discover first available device
            board = ESPBoard()

            # Connect to specific IP with auto-retry
            board = ESPBoard(ip='192.168.1.100', auto_retry=True)

            # Connect via mDNS with health monitoring
            board = ESPBoard(url='http://esp-linker.local', health_check=True)
        """
        if url:
            self.base_url = url.rstrip('/')
            self.ip = url.replace('http://', '').replace('https://', '').split(':')[0]
        elif ip:
            self.base_url = f"http://{ip}"
            self.ip = ip
        elif auto_discover:
            # Auto-discover ESP-Linker devices
            print("[?] No IP specified, starting auto-discovery...")
            devices = discover_devices(timeout=30.0)
            if not devices:
                raise ConnectionError("No ESP-Linker devices found on network. Please specify IP manually or ensure device is connected.")

            # Use first found device
            device = devices[0]
            self.ip = device['ip']
            self.base_url = f"http://{self.ip}"
            print(f"[*] Auto-selected device: {device['firmware_name']} at {self.ip}")
        else:
            raise ValueError("Either 'ip', 'url' must be provided, or enable auto_discover=True")
            
        self.timeout = timeout
        self.retries = retries
        self.auto_retry = auto_retry
        self.max_retries = max_retries
        self.health_check = health_check
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'ESP-Linker-Python/1.2.0'
        })

        # Board state
        self._connected = False
        self._capabilities = None
        self._pin_modes = {}

        # Enhanced error handling state
        self.retry_count = 0
        self.last_error = None
        self.connection_healthy = True
        self.health_check_thread = None
        
        # Test connection
        self._test_connection()

        # Start health check if enabled
        if self.health_check:
            self.enable_health_check()
    
    def _test_connection(self):
        """Test connection to ESP8266"""
        try:
            response = self._request('GET', '/status')
            if response.get('firmware_name'):
                self._connected = True
                print(f"[+] Connected to {response['firmware_name']} v{response.get('firmware_version', 'Unknown')}")
            else:
                raise ConnectionError("Invalid response from device")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to ESP8266 at {self.base_url}: {e}")
    
    def _request_with_retry(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """Make HTTP request with enhanced error handling and auto-retry"""
        import time
        import random

        last_exception = None

        for attempt in range(self.max_retries if self.auto_retry else 1):
            try:
                return self._request(method, endpoint, data, params)
            except Exception as e:
                last_exception = e
                self.last_error = str(e)

                if not self.auto_retry or attempt == self.max_retries - 1:
                    # Last attempt or auto-retry disabled
                    self.connection_healthy = False
                    raise e

                # Exponential backoff with jitter
                delay = (2 ** attempt) + random.uniform(0, 1)
                print(f"[!] Request failed (attempt {attempt + 1}/{self.max_retries}), retrying in {delay:.1f}s...")
                time.sleep(delay)

        # Should never reach here, but just in case
        self.connection_healthy = False
        raise last_exception

    def _request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """
        Make HTTP request to ESP8266 with retry logic.
        
        Args:
            method: HTTP method ('GET', 'POST', etc.)
            endpoint: API endpoint (e.g., '/status')
            data: JSON data for POST requests
            params: URL parameters for GET requests
            
        Returns:
            Response data as dictionary
            
        Raises:
            APIError: If request fails after retries
        """
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.retries + 1):
            try:
                if method == 'GET':
                    response = self.session.get(url, params=params, timeout=self.timeout)
                elif method == 'POST':
                    response = self.session.post(url, json=data, timeout=self.timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Check HTTP status
                if response.status_code == 200:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        # Handle non-JSON responses (like simple text)
                        return {'message': response.text, 'status': 200}
                elif response.status_code == 400:
                    try:
                        error_data = response.json()
                        raise APIError(f"Bad request: {error_data.get('message', 'Unknown error')}")
                    except json.JSONDecodeError:
                        raise APIError(f"Bad request: {response.text}")
                elif response.status_code == 404:
                    raise APIError(f"Endpoint not found: {endpoint}")
                elif response.status_code == 405:
                    raise APIError(f"Method not allowed: {method} {endpoint}")
                else:
                    raise APIError(f"HTTP {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout:
                if attempt < self.retries:
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                raise TimeoutError(f"Request timeout after {self.retries + 1} attempts")
            except requests.exceptions.ConnectionError:
                if attempt < self.retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise ConnectionError(f"Connection failed after {self.retries + 1} attempts")
            except Exception as e:
                if attempt < self.retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise APIError(f"Request failed: {e}")
        
        raise APIError("Maximum retries exceeded")
    
    def status(self) -> Dict[str, Any]:
        """
        Get board status information.
        
        Returns:
            Dictionary with board status including:
            - firmware_name, firmware_version
            - uptime, free_heap, chip_id
            - wifi_status, wifi_ssid, wifi_ip
            - ap_ip, connected_clients
            
        Example:
            status = board.status()
            print(f"Uptime: {status['uptime']}ms")
            print(f"Free memory: {status['free_heap']} bytes")
        """
        return self._request('GET', '/status')
    
    def capabilities(self) -> Dict[str, Any]:
        """
        Get pin capabilities information.
        
        Returns:
            Dictionary with pin capabilities including:
            - pins: List of pin objects with capabilities
            - analog_pin: Analog pin information
            
        Example:
            caps = board.capabilities()
            for pin in caps['pins']:
                print(f"Pin {pin['pin']}: PWM={pin['pwm']}, Servo={pin['servo']}")
        """
        if self._capabilities is None:
            self._capabilities = self._request('GET', '/capabilities')
        return self._capabilities
    
    def set_mode(self, pin: Union[int, str], mode: str):
        """
        Set pin mode.
        
        Args:
            pin: Pin number (int) or 'A0' for analog
            mode: Pin mode ('INPUT', 'OUTPUT', 'INPUT_PULLUP', 'PWM', 'SERVO')
            
        Example:
            board.set_mode(2, 'OUTPUT')     # Digital output
            board.set_mode(4, 'PWM')        # PWM output
            board.set_mode(5, 'SERVO')      # Servo control
        """
        validate_pin(pin, self.capabilities())
        validate_mode(mode)
        
        data = {'pin': pin, 'mode': mode}
        response = self._request('POST', '/gpio/set_mode', data)
        
        # Update local state
        self._pin_modes[pin] = mode

        return response

    def write(self, pin: Union[int, str], value: Union[int, bool], auto_mode: bool = True):
        """
        Write digital value to pin.

        Args:
            pin: Pin number
            value: Digital value (0/1, False/True)
            auto_mode: Automatically set pin to OUTPUT mode if needed (default: True)

        Example:
            board.write(2, 1)    # Auto-sets OUTPUT mode and turns on
            board.write(2, 0)    # Turn off

            # Manual mode setting (PyFirmata style)
            board.set_mode(2, 'OUTPUT')
            board.write(2, 1, auto_mode=False)
        """
        validate_pin(pin, self.capabilities())

        # Convert boolean to int
        if isinstance(value, bool):
            value = 1 if value else 0

        if value not in [0, 1]:
            raise InvalidValueError(f"Digital value must be 0 or 1, got {value}")

        # Auto-set pin mode if enabled and not already set
        if auto_mode and self._pin_modes.get(pin) != 'OUTPUT':
            try:
                self.set_mode(pin, 'OUTPUT')
            except Exception as e:
                raise APIError(f"Failed to set pin {pin} to OUTPUT mode: {e}")

        data = {'pin': pin, 'value': value}
        try:
            return self._request('POST', '/gpio/write', data)
        except APIError as e:
            if "Pin not set to OUTPUT mode" in str(e):
                raise APIError(
                    f"Pin {pin} is not in OUTPUT mode. "
                    f"Use board.set_mode({pin}, 'OUTPUT') first, or enable auto_mode=True"
                ) from e
            raise

    def read(self, pin: Union[int, str]) -> int:
        """
        Read value from pin.

        Args:
            pin: Pin number (int) or 'A0' for analog

        Returns:
            Pin value (0-1 for digital, 0-1024 for analog)

        Example:
            value = board.read(2)      # Read digital pin
            analog = board.read('A0')  # Read analog pin
        """
        validate_pin(pin, self.capabilities())

        params = {'pin': pin}
        response = self._request('GET', '/gpio/read', params=params)
        return response.get('value', 0)

    def pwm(self, pin: Union[int, str], value: int, auto_mode: bool = True):
        """
        Set PWM value on pin.

        Args:
            pin: Pin number
            value: PWM value (0-1023)
            auto_mode: Automatically set pin to PWM mode if needed (default: True)

        Example:
            board.pwm(4, 512)    # Auto-sets PWM mode, 50% duty cycle
            board.pwm(4, 256)    # 25% duty cycle

            # Manual mode setting (PyFirmata style)
            board.set_mode(4, 'PWM')
            board.pwm(4, 512, auto_mode=False)
        """
        validate_pin(pin, self.capabilities())
        validate_pwm_value(value)

        # Auto-set pin mode if enabled and not already set
        if auto_mode and self._pin_modes.get(pin) != 'PWM':
            try:
                self.set_mode(pin, 'PWM')
            except Exception as e:
                raise APIError(f"Failed to set pin {pin} to PWM mode: {e}")

        data = {'pin': pin, 'value': value}
        try:
            return self._request('POST', '/gpio/pwm', data)
        except APIError as e:
            if "Pin not set to PWM mode" in str(e):
                raise APIError(
                    f"Pin {pin} is not in PWM mode. "
                    f"Use board.set_mode({pin}, 'PWM') first, or enable auto_mode=True"
                ) from e
            raise

    def servo(self, pin: Union[int, str], angle: int, auto_mode: bool = True):
        """
        Set servo angle.

        Args:
            pin: Pin number
            angle: Servo angle (0-180 degrees)
            auto_mode: Automatically set pin to SERVO mode if needed (default: True)

        Example:
            board.servo(5, 90)   # Auto-sets SERVO mode, center position
            board.servo(5, 0)    # Minimum angle
            board.servo(5, 180)  # Maximum angle

            # Manual mode setting (PyFirmata style)
            board.set_mode(5, 'SERVO')
            board.servo(5, 90, auto_mode=False)
        """
        validate_pin(pin, self.capabilities())
        validate_servo_angle(angle)

        # Auto-set pin mode if enabled and not already set
        if auto_mode and self._pin_modes.get(pin) != 'SERVO':
            try:
                self.set_mode(pin, 'SERVO')
            except Exception as e:
                raise APIError(f"Failed to set pin {pin} to SERVO mode: {e}")

        data = {'pin': pin, 'angle': angle}
        try:
            return self._request('POST', '/servo/write', data)
        except APIError as e:
            if "Pin not set to SERVO mode" in str(e):
                raise APIError(
                    f"Pin {pin} is not in SERVO mode. "
                    f"Use board.set_mode({pin}, 'SERVO') first, or enable auto_mode=True"
                ) from e
            raise

    def batch(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute multiple operations in a single call.

        Args:
            operations: List of operation dictionaries

        Returns:
            Dictionary with results for each operation

        Example:
            results = board.batch([
                {'type': 'write', 'pin': 2, 'value': 1},
                {'type': 'pwm', 'pin': 4, 'value': 512},
                {'type': 'servo', 'pin': 5, 'angle': 90},
                {'type': 'read', 'pin': 2}
            ])
        """
        if not operations:
            raise ValueError("Operations list cannot be empty")

        data = {'operations': operations}
        return self._request('POST', '/gpio/batch', data)

    def configure_wifi(self, ssid: str, password: str):
        """
        Configure WiFi credentials.

        Args:
            ssid: WiFi network name
            password: WiFi password

        Note:
            Board must be restarted for changes to take effect.

        Example:
            board.configure_wifi('MyWiFi', 'MyPassword')
            board.restart()
        """
        if not ssid or len(ssid) > 31:
            raise ValueError("SSID must be 1-31 characters")
        if len(password) > 31:
            raise ValueError("Password must be 31 characters or less")

        data = {'ssid': ssid, 'password': password}
        return self._request('POST', '/configure_wifi', data)

    def restart(self):
        """
        Restart the ESP8266 board.

        Note:
            Connection will be lost during restart.
            Wait 10-15 seconds before reconnecting.

        Example:
            board.restart()
            time.sleep(15)  # Wait for restart
            # Reconnect or create new board instance
        """
        try:
            response = self._request('POST', '/restart')
            self._connected = False
            return response
        except (ConnectionError, TimeoutError):
            # Expected behavior during restart
            self._connected = False
            return {'message': 'Restart initiated'}

    def is_connected(self) -> bool:
        """
        Check if board is connected.

        Returns:
            True if connected, False otherwise
        """
        try:
            self.status()
            self._connected = True
            return True
        except:
            self._connected = False
            return False

    @property
    def device_ip(self) -> str:
        """Get the device IP address"""
        return getattr(self, 'ip', self.base_url.replace('http://', '').replace('https://', '').split(':')[0])

    @property
    def device_url(self) -> str:
        """Get the device URL"""
        return self.base_url

    @property
    def is_connected(self) -> bool:
        """Check if device is connected"""
        return self._connected

    def reconnect(self):
        """
        Reconnect to the device.

        Example:
            board.reconnect()
        """
        self._test_connection()

    def get_device_info(self) -> Dict[str, Any]:
        """
        Get comprehensive device information.

        Returns:
            Dictionary with device information including capabilities

        Example:
            info = board.get_device_info()
            print(f"Device: {info['firmware_name']} v{info['firmware_version']}")
            print(f"Available pins: {[p['pin'] for p in info['capabilities']['pins']]}")
        """
        try:
            # Get status and capabilities
            status = self.status()
            capabilities = self.capabilities()

            return {
                'ip': self.device_ip,
                'url': self.device_url,
                'firmware_name': status.get('firmware_name', 'Unknown'),
                'firmware_version': status.get('firmware_version', 'Unknown'),
                'wifi_ssid': status.get('wifi_ssid', ''),
                'wifi_ip': status.get('wifi_ip', ''),
                'uptime': status.get('uptime', 0),
                'free_heap': status.get('free_heap', 0),
                'chip_id': status.get('chip_id', 0),
                'capabilities': capabilities,
                'pin_count': len(capabilities.get('pins', [])),
                'pwm_pins': [p['pin'] for p in capabilities.get('pins', []) if p.get('pwm')],
                'servo_pins': [p['pin'] for p in capabilities.get('pins', []) if p.get('servo')],
                'analog_pin': capabilities.get('analog_pin', {}).get('pin', 'A0')
            }
        except Exception as e:
            raise APIError(f"Failed to get device info: {e}")

    def enable_health_check(self, interval: int = 30):
        """Enable periodic connection health checks"""
        import threading
        import time

        def health_check_worker():
            while self.health_check and self._connected:
                try:
                    self.status()
                    self.connection_healthy = True
                except Exception as e:
                    self.connection_healthy = False
                    self.last_error = str(e)
                    print(f"[!] Health check failed: {e}")

                time.sleep(interval)

        if self.health_check_thread is None or not self.health_check_thread.is_alive():
            self.health_check_thread = threading.Thread(target=health_check_worker, daemon=True)
            self.health_check_thread.start()
            print(f"[+] Health monitoring enabled (checking every {interval} seconds)")

    def disable_health_check(self):
        """Disable health checks"""
        self.health_check = False
        if self.health_check_thread:
            self.health_check_thread = None
        print("[+] Health monitoring disabled")

    def get_connection_status(self) -> Dict[str, Any]:
        """Get detailed connection status"""
        return {
            'connected': self._connected,
            'healthy': self.connection_healthy,
            'last_error': self.last_error,
            'retry_count': self.retry_count,
            'auto_retry_enabled': self.auto_retry,
            'health_check_enabled': self.health_check,
            'base_url': self.base_url
        }

    def close(self):
        """
        Close connection to board.

        Example:
            board.close()
        """
        # Disable health check first
        if self.health_check:
            self.disable_health_check()

        if hasattr(self, 'session'):
            self.session.close()
        self._connected = False
        print("[*] Connection closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def __repr__(self):
        """String representation"""
        status = "connected" if self._connected else "disconnected"
        return f"ESPBoard({self.base_url}, {status})"
