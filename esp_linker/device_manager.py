"""
ESP-Linker Device Management System
(c) 2025 SK Raihan / SKR Electronics Lab

Advanced device management features for handling multiple ESP-Linker devices.
"""

import json
import time
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime
import os

from .utils import discover_devices
from .espboard import ESPBoard
from .exceptions import DeviceNotFoundError, ConnectionError

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False


class DeviceInfo:
    """Represents information about an ESP-Linker device"""
    
    def __init__(self, ip: str, name: str = None, **kwargs):
        self.ip = ip
        self.name = name or f"ESP-Linker-{ip.split('.')[-1]}"
        self.firmware_name = kwargs.get('firmware_name', 'Unknown')
        self.firmware_version = kwargs.get('firmware_version', 'Unknown')
        self.mac = kwargs.get('mac', 'Unknown')
        self.wifi_ssid = kwargs.get('wifi_ssid', '')
        self.last_seen = datetime.now()
        self.status = 'unknown'  # online, offline, unknown
        self.tags = kwargs.get('tags', [])
        self.notes = kwargs.get('notes', '')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'ip': self.ip,
            'name': self.name,
            'firmware_name': self.firmware_name,
            'firmware_version': self.firmware_version,
            'mac': self.mac,
            'wifi_ssid': self.wifi_ssid,
            'last_seen': self.last_seen.isoformat(),
            'status': self.status,
            'tags': self.tags,
            'notes': self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceInfo':
        """Create from dictionary"""
        device = cls(data['ip'], data.get('name'))
        device.firmware_name = data.get('firmware_name', 'Unknown')
        device.firmware_version = data.get('firmware_version', 'Unknown')
        device.mac = data.get('mac', 'Unknown')
        device.wifi_ssid = data.get('wifi_ssid', '')
        device.last_seen = datetime.fromisoformat(data.get('last_seen', datetime.now().isoformat()))
        device.status = data.get('status', 'unknown')
        device.tags = data.get('tags', [])
        device.notes = data.get('notes', '')
        return device


class DeviceManager:
    """Manages multiple ESP-Linker devices"""
    
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir) if config_dir else Path.home() / '.esp-linker'
        self.config_dir.mkdir(exist_ok=True)
        self.devices_file = self.config_dir / 'devices.json'
        self.devices: Dict[str, DeviceInfo] = {}
        self.load_devices()
    
    def load_devices(self):
        """Load devices from configuration file"""
        if self.devices_file.exists():
            try:
                with open(self.devices_file, 'r') as f:
                    data = json.load(f)
                    self.devices = {
                        ip: DeviceInfo.from_dict(device_data)
                        for ip, device_data in data.items()
                    }
            except Exception as e:
                print(f"[!] Warning: Could not load devices config: {e}")
                self.devices = {}
    
    def save_devices(self):
        """Save devices to configuration file"""
        try:
            data = {ip: device.to_dict() for ip, device in self.devices.items()}
            with open(self.devices_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[!] Warning: Could not save devices config: {e}")
    
    def discover_and_add_devices(self, timeout: float = 30.0) -> List[DeviceInfo]:
        """Discover new devices and add them to the manager"""
        print("[?] Discovering ESP-Linker devices...")

        try:
            discovered = discover_devices(timeout=timeout)
        except Exception as e:
            print(f"[!] Discovery failed: {e}")
            return []

        new_devices = []
        
        for device_data in discovered:
            ip = device_data['ip']
            
            if ip not in self.devices:
                # New device found
                device = DeviceInfo(
                    ip=ip,
                    firmware_name=device_data.get('firmware_name', 'Unknown'),
                    firmware_version=device_data.get('firmware_version', 'Unknown'),
                    mac=device_data.get('mac', 'Unknown')
                )
                device.status = 'online'
                self.devices[ip] = device
                new_devices.append(device)
                print(f"[#] New device found: {device.name} ({ip})")
            else:
                # Update existing device
                device = self.devices[ip]
                device.last_seen = datetime.now()
                device.status = 'online'
                device.firmware_name = device_data.get('firmware_name', device.firmware_name)
                device.firmware_version = device_data.get('firmware_version', device.firmware_version)
        
        self.save_devices()
        return new_devices
    
    def list_devices(self, status_filter: Optional[str] = None) -> List[DeviceInfo]:
        """List all managed devices"""
        devices = list(self.devices.values())
        
        if status_filter:
            devices = [d for d in devices if d.status == status_filter]
        
        return sorted(devices, key=lambda d: d.name)
    
    def get_device(self, identifier: str) -> Optional[DeviceInfo]:
        """Get device by IP or name"""
        # Try by IP first
        if identifier in self.devices:
            return self.devices[identifier]
        
        # Try by name
        for device in self.devices.values():
            if device.name.lower() == identifier.lower():
                return device
        
        return None
    
    def rename_device(self, identifier: str, new_name: str) -> bool:
        """Rename a device"""
        device = self.get_device(identifier)
        if device:
            device.name = new_name
            self.save_devices()
            return True
        return False
    
    def add_tag(self, identifier: str, tag: str) -> bool:
        """Add a tag to a device"""
        device = self.get_device(identifier)
        if device and tag not in device.tags:
            device.tags.append(tag)
            self.save_devices()
            return True
        return False
    
    def remove_tag(self, identifier: str, tag: str) -> bool:
        """Remove a tag from a device"""
        device = self.get_device(identifier)
        if device and tag in device.tags:
            device.tags.remove(tag)
            self.save_devices()
            return True
        return False
    
    def set_notes(self, identifier: str, notes: str) -> bool:
        """Set notes for a device"""
        device = self.get_device(identifier)
        if device:
            device.notes = notes
            self.save_devices()
            return True
        return False
    
    def remove_device(self, identifier: str) -> bool:
        """Remove a device from management"""
        device = self.get_device(identifier)
        if device:
            del self.devices[device.ip]
            self.save_devices()
            return True
        return False
    
    def check_device_status(self, device: DeviceInfo) -> str:
        """Check if a device is online"""
        try:
            board = ESPBoard(ip=device.ip, timeout=3)
            status = board.status()
            board.close()
            return 'online'
        except:
            return 'offline'
    
    def update_all_status(self, show_progress: bool = True) -> Dict[str, str]:
        """Update status for all devices"""
        devices = list(self.devices.values())
        status_results = {}
        
        if show_progress and TQDM_AVAILABLE:
            devices_iter = tqdm(devices, desc="[=] Checking device status")
        else:
            devices_iter = devices
            if show_progress:
                print("[=] Checking device status...")
        
        for device in devices_iter:
            status = self.check_device_status(device)
            device.status = status
            device.last_seen = datetime.now()
            status_results[device.ip] = status
            
            if not TQDM_AVAILABLE and show_progress:
                status_icon = "[+]" if status == 'online' else "[!]"
                print(f"   {status_icon} {device.name} ({device.ip}): {status}")
        
        self.save_devices()
        return status_results
    
    def monitor_devices(self, interval: int = 30, callback: Optional[Callable] = None):
        """Monitor devices continuously"""
        print(f"[*] Starting device monitoring (checking every {interval} seconds)")
        print("Press Ctrl+C to stop monitoring")
        
        try:
            while True:
                status_results = self.update_all_status(show_progress=False)
                
                # Report status changes
                online_count = sum(1 for status in status_results.values() if status == 'online')
                total_count = len(status_results)
                
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] [=] Status: {online_count}/{total_count} devices online")
                
                if callback:
                    callback(status_results)
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n[!] Device monitoring stopped")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get device statistics"""
        devices = list(self.devices.values())
        
        if not devices:
            return {
                'total_devices': 0,
                'online_devices': 0,
                'offline_devices': 0,
                'firmware_versions': {},
                'tags': {}
            }
        
        # Update status for accurate statistics
        self.update_all_status(show_progress=False)
        
        online_count = sum(1 for d in devices if d.status == 'online')
        offline_count = len(devices) - online_count
        
        # Firmware version distribution
        firmware_versions = {}
        for device in devices:
            version = f"{device.firmware_name} v{device.firmware_version}"
            firmware_versions[version] = firmware_versions.get(version, 0) + 1
        
        # Tag distribution
        tag_counts = {}
        for device in devices:
            for tag in device.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        return {
            'total_devices': len(devices),
            'online_devices': online_count,
            'offline_devices': offline_count,
            'firmware_versions': firmware_versions,
            'tags': tag_counts,
            'last_discovery': max(d.last_seen for d in devices) if devices else None
        }


# Global device manager instance
_device_manager = None

def get_device_manager() -> DeviceManager:
    """Get the global device manager instance"""
    global _device_manager
    if _device_manager is None:
        _device_manager = DeviceManager()
    return _device_manager
