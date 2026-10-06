"""
ESP-Linker Utility Functions
(c) 2025 SK Raihan / SKR Electronics Lab -- All Rights Reserved.

Utility functions for device discovery, validation, and network operations
"""

import socket
import requests
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Union

# Import exceptions directly to avoid circular imports
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

def get_local_ip() -> str:
    """
    Get the local IP address of this machine.
    
    Returns:
        Local IP address as string
    """
    try:
        # Connect to a remote address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except (socket.error, OSError):
        # Handle network connectivity issues
        return "192.168.1.100"  # fallback

def get_network_range(ip: str = None) -> str:
    """
    Get network range for scanning.
    
    Args:
        ip: IP address to base range on (uses local IP if None)
        
    Returns:
        Network base (e.g., "192.168.1")
    """
    if ip is None:
        ip = get_local_ip()
    
    ip_parts = ip.split('.')
    return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}"

def check_esp_device(ip: str, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
    """
    Check if an IP address hosts an ESP-Linker device.

    Args:
        ip: IP address to check
        timeout: Request timeout in seconds

    Returns:
        Device info dictionary if ESP-Linker device found, None otherwise
    """
    try:
        response = requests.get(f"http://{ip}/status", timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            # Check if it's an ESP-Linker device (support both old and new names)
            firmware_name = data.get('firmware_name', '')
            if ('ESP-Linker' in firmware_name or 'esp-linker' in firmware_name.lower() or
                'ESP-Link' in firmware_name or 'esp-link' in firmware_name.lower()):
                return {
                    'ip': ip,
                    'url': f"http://{ip}",
                    'firmware_name': data.get('firmware_name', 'Unknown'),
                    'firmware_version': data.get('firmware_version', 'Unknown'),
                    'wifi_ssid': data.get('wifi_ssid', ''),
                    'uptime': data.get('uptime', 0),
                    'free_heap': data.get('free_heap', 0),
                    'chip_id': data.get('chip_id', 0)
                }
    except (requests.RequestException, ValueError, KeyError):
        # Handle HTTP errors, JSON parsing errors, and missing keys
        pass
    return None

def scan_network(network_range: str = None, max_workers: int = 50, timeout: float = 2.0) -> List[Dict[str, Any]]:
    """
    Scan local network for ESP-Linker devices.

    Args:
        network_range: Network range to scan (e.g., "192.168.1")
        max_workers: Maximum number of concurrent threads
        timeout: Request timeout per device

    Returns:
        List of found ESP-Linker devices

    Example:
        devices = scan_network()
        for device in devices:
            print(f"Found ESP-Linker at {device['ip']}")
    """
    if network_range is None:
        network_range = get_network_range()
    
    print(f"[?] Scanning network: {network_range}.1-254")
    print("[.] This may take 30-60 seconds...")
    
    # Create list of IPs to scan
    ips_to_scan = [f"{network_range}.{i}" for i in range(1, 255)]
    
    found_devices = []
    
    # Use ThreadPoolExecutor for faster scanning
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(lambda ip: check_esp_device(ip, timeout), ips_to_scan)
        
        for result in results:
            if result:
                found_devices.append(result)
                print(f"[+] Found ESP-Linker at: {result['ip']}")
    
    return found_devices

def discover_devices(timeout: float = 30.0) -> List[Dict[str, Any]]:
    """
    Discover ESP-Linker devices on the local network.

    Args:
        timeout: Maximum time to spend scanning

    Returns:
        List of discovered ESP-Linker devices

    Example:
        devices = discover_devices()
        if devices:
            board = ESPBoard(ip=devices[0]['ip'])
    """
    print("[?] Discovering ESP-Linker devices...")
    
    # Try mDNS discovery first (if available)
    devices = []
    try:
        devices.extend(discover_mdns(timeout=min(timeout, 10.0)))
    except ImportError:
        # zeroconf should be installed as core dependency, but handle gracefully
        pass
    except Exception as e:
        print(f"[!]  mDNS discovery failed: {e}")
    
    # Fall back to network scanning
    if not devices:
        remaining_time = max(timeout - 10.0, 10.0)
        devices.extend(scan_network(timeout=2.0))
    
    if devices:
        print(f"[*] Found {len(devices)} ESP-Linker device(s)!")
        for device in devices:
            print(f"[*] {device['firmware_name']} at {device['ip']}")
    else:
        print("[!] No ESP-Linker devices found")
    
    return devices

def discover_mdns(timeout: float = 10.0) -> List[Dict[str, Any]]:
    """
    Discover ESP-Linker devices using mDNS.

    Args:
        timeout: Discovery timeout in seconds

    Returns:
        List of discovered devices

    Raises:
        ImportError: If zeroconf is not installed
    """
    try:
        from zeroconf import ServiceBrowser, Zeroconf, ServiceListener
        import socket
    except ImportError:
        raise ImportError("zeroconf package required for mDNS discovery. Install with: pip install zeroconf")

    devices = []

    class ESPLinkListener(ServiceListener):
        def __init__(self):
            self.devices = []
            self.found_services = set()

        def remove_service(self, zeroconf, type, name):
            pass

        def add_service(self, zeroconf, type, name):
            try:
                info = zeroconf.get_service_info(type, name)
                if info and name not in self.found_services:
                    self.found_services.add(name)

                    # Check if it's an ESP-Linker device (support both old and new names)
                    if ('esp-linker' in name.lower() or 'esp_linker' in name.lower() or
                        'esp-link' in name.lower() or 'esp_link' in name.lower()):
                        if info.addresses:
                            ip = socket.inet_ntoa(info.addresses[0])
                            device_info = check_esp_device(ip, timeout=2.0)
                            if device_info:
                                self.devices.append(device_info)
                                print(f"[+] Found ESP-Linker via mDNS: {ip}")
            except Exception as e:
                print(f"[!]  mDNS service check failed: {e}")

        def update_service(self, zeroconf, type, name):
            pass

    print("[?] Scanning for mDNS services...")
    zeroconf = Zeroconf()
    listener = ESPLinkListener()

    # Browse multiple service types
    service_types = [
        "_http._tcp.local.",
        "_esp-linker._tcp.local.",
        "_esp-link._tcp.local.",  # Support old name too
        "_arduino._tcp.local.",
        "_iot._tcp.local."
    ]

    browsers = []
    for service_type in service_types:
        try:
            browser = ServiceBrowser(zeroconf, service_type, listener)
            browsers.append(browser)
        except Exception as e:
            print(f"[!]  Failed to browse {service_type}: {e}")

    # Wait for discovery
    print(f"[.] Waiting {timeout}s for mDNS responses...")
    time.sleep(timeout)

    # Cleanup
    for browser in browsers:
        try:
            browser.cancel()
        except Exception as e:
            # Ignore errors when canceling browsers
            pass

    try:
        zeroconf.close()
    except Exception as e:
        # Ignore errors when closing zeroconf
        pass

    return listener.devices

def validate_pin(pin: Union[int, str], capabilities: Dict[str, Any] = None):
    """
    Validate pin number.
    
    Args:
        pin: Pin number or 'A0'
        capabilities: Pin capabilities from board
        
    Raises:
        InvalidPinError: If pin is invalid
    """
    if pin == 'A0':
        return  # Analog pin is always valid
    
    if not isinstance(pin, int):
        try:
            pin = int(pin)
        except (ValueError, TypeError):
            raise InvalidPinError(f"Invalid pin: {pin}")
    
    if capabilities:
        valid_pins = [p['pin'] for p in capabilities.get('pins', [])]
        if pin not in valid_pins:
            raise InvalidPinError(f"Pin {pin} not available. Valid pins: {valid_pins}")

def validate_mode(mode: str):
    """
    Validate pin mode.
    
    Args:
        mode: Pin mode string
        
    Raises:
        InvalidModeError: If mode is invalid
    """
    valid_modes = ['INPUT', 'OUTPUT', 'INPUT_PULLUP', 'PWM', 'SERVO']
    if mode not in valid_modes:
        raise InvalidModeError(f"Invalid mode: {mode}. Valid modes: {valid_modes}")

def validate_pwm_value(value: int):
    """
    Validate PWM value.
    
    Args:
        value: PWM value
        
    Raises:
        InvalidValueError: If value is invalid
    """
    if not isinstance(value, int) or value < 0 or value > 1023:
        raise InvalidValueError(f"PWM value must be 0-1023, got {value}")

def validate_servo_angle(angle: int):
    """
    Validate servo angle.
    
    Args:
        angle: Servo angle in degrees
        
    Raises:
        InvalidValueError: If angle is invalid
    """
    if not isinstance(angle, int) or angle < 0 or angle > 180:
        raise InvalidValueError(f"Servo angle must be 0-180 degrees, got {angle}")

def format_uptime(uptime_ms: int) -> str:
    """
    Format uptime from milliseconds to human-readable string.
    
    Args:
        uptime_ms: Uptime in milliseconds
        
    Returns:
        Formatted uptime string
    """
    seconds = uptime_ms // 1000
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    
    if days > 0:
        return f"{days}d {hours % 24}h {minutes % 60}m {seconds % 60}s"
    elif hours > 0:
        return f"{hours}h {minutes % 60}m {seconds % 60}s"
    elif minutes > 0:
        return f"{minutes}m {seconds % 60}s"
    else:
        return f"{seconds}s"

def format_memory(bytes_value: int) -> str:
    """
    Format memory size in human-readable format.

    Args:
        bytes_value: Memory size in bytes

    Returns:
        Formatted memory string
    """
    if bytes_value >= 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.1f} MB"
    elif bytes_value >= 1024:
        return f"{bytes_value / 1024:.1f} KB"
    else:
        return f"{bytes_value} bytes"

def ping_device(ip: str, timeout: float = 2.0) -> bool:
    """
    Ping a device to check if it's reachable.

    Args:
        ip: IP address to ping
        timeout: Ping timeout in seconds

    Returns:
        True if device responds, False otherwise
    """
    try:
        import subprocess
        import platform

        # Determine ping command based on OS
        if platform.system().lower() == "windows":
            cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
        else:
            cmd = ["ping", "-c", "1", "-W", str(int(timeout)), ip]

        result = subprocess.run(cmd, capture_output=True, timeout=timeout + 1)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
        # Handle ping command errors gracefully
        return False

def get_device_info(ip: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive device information.

    Args:
        ip: IP address of device
        timeout: Request timeout

    Returns:
        Device information dictionary or None
    """
    device_info = check_esp_device(ip, timeout)
    if not device_info:
        return None

    try:
        # Get additional information
        response = requests.get(f"http://{ip}/capabilities", timeout=timeout)
        if response.status_code == 200:
            caps = response.json()
            device_info['capabilities'] = caps
            device_info['pin_count'] = len(caps.get('pins', []))
            device_info['pwm_pins'] = [p['pin'] for p in caps.get('pins', []) if p.get('pwm')]
            device_info['servo_pins'] = [p['pin'] for p in caps.get('pins', []) if p.get('servo')]
            device_info['analog_pin'] = caps.get('analog_pin', {}).get('pin', 'A0')
    except (requests.RequestException, ValueError, KeyError) as e:
        # Handle HTTP errors, JSON parsing errors, and missing keys
        pass

    return device_info

def configure_device_wifi(ip: str, ssid: str, password: str, timeout: float = 10.0) -> bool:
    """
    Configure WiFi on ESP-Linker device.

    Args:
        ip: Device IP address
        ssid: WiFi network name
        password: WiFi password
        timeout: Request timeout

    Returns:
        True if configuration successful, False otherwise
    """
    try:
        data = {'ssid': ssid, 'password': password}
        response = requests.post(
            f"http://{ip}/configure_wifi",
            json=data,
            timeout=timeout
        )
        return response.status_code == 200
    except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
        # Handle HTTP request errors
        return False

def restart_device(ip: str, timeout: float = 5.0) -> bool:
    """
    Restart ESP-Linker device.

    Args:
        ip: Device IP address
        timeout: Request timeout

    Returns:
        True if restart command sent, False otherwise
    """
    try:
        response = requests.post(f"http://{ip}/restart", timeout=timeout)
        return response.status_code == 200
    except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
        # Handle HTTP request errors
        return False

def wait_for_device(ip: str, max_wait: float = 30.0, check_interval: float = 1.0) -> bool:
    """
    Wait for device to come online.

    Args:
        ip: Device IP address
        max_wait: Maximum wait time in seconds
        check_interval: Check interval in seconds

    Returns:
        True if device comes online, False if timeout
    """
    start_time = time.time()

    while time.time() - start_time < max_wait:
        if check_esp_device(ip, timeout=2.0):
            return True
        time.sleep(check_interval)

    return False

def backup_device_config(ip: str, filename: str = None, timeout: float = 10.0) -> bool:
    """
    Backup device configuration.

    Args:
        ip: Device IP address
        filename: Backup filename (auto-generated if None)
        timeout: Request timeout

    Returns:
        True if backup successful, False otherwise
    """
    try:
        # Get device status and capabilities
        status_response = requests.get(f"http://{ip}/status", timeout=timeout)
        caps_response = requests.get(f"http://{ip}/capabilities", timeout=timeout)

        if status_response.status_code != 200 or caps_response.status_code != 200:
            return False

        backup_data = {
            'timestamp': time.time(),
            'device_ip': ip,
            'status': status_response.json(),
            'capabilities': caps_response.json()
        }

        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            chip_id = backup_data['status'].get('chip_id', 'unknown')
            filename = f"esp_link_backup_{chip_id}_{timestamp}.json"

        with open(filename, 'w') as f:
            import json
            json.dump(backup_data, f, indent=2)

        print(f"[+] Configuration backed up to: {filename}")
        return True

    except Exception as e:
        print(f"[!] Backup failed: {e}")
        return False

def validate_pin_configuration(pin: Union[int, str], mode: str, capabilities: Dict[str, Any] = None) -> bool:
    """
    Validate pin configuration against device capabilities.

    Args:
        pin: Pin number or 'A0'
        mode: Pin mode
        capabilities: Device capabilities (fetched if None)

    Returns:
        True if configuration is valid, False otherwise
    """
    try:
        validate_pin(pin, capabilities)
        validate_mode(mode)

        if capabilities and pin != 'A0':
            pin_info = next((p for p in capabilities.get('pins', []) if p['pin'] == pin), None)
            if pin_info:
                if mode == 'PWM' and not pin_info.get('pwm', False):
                    return False
                if mode == 'SERVO' and not pin_info.get('servo', False):
                    return False

        return True
    except (requests.RequestException, ValueError, KeyError) as e:
        # Handle HTTP errors, JSON parsing errors, and missing keys
        return False
