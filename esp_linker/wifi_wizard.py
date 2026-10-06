"""
ESP-Linker WiFi Configuration Wizard
(c) 2025 SK Raihan / SKR Electronics Lab

Interactive WiFi setup wizard that makes WiFi configuration easy and user-friendly.
"""

import serial
import time
import getpass
import re
from typing import List, Dict, Optional, Tuple
from .flasher import detect_esp8266
from .exceptions import DeviceNotFoundError, FlashError

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False


class WiFiNetwork:
    """Represents a WiFi network"""
    
    def __init__(self, ssid: str, rssi: int, encrypted: bool):
        self.ssid = ssid
        self.rssi = rssi
        self.encrypted = encrypted
        self.signal_strength = self._calculate_signal_strength()
    
    def _calculate_signal_strength(self) -> int:
        """Calculate signal strength bars (1-5)"""
        if self.rssi >= -50:
            return 5
        elif self.rssi >= -60:
            return 4
        elif self.rssi >= -70:
            return 3
        elif self.rssi >= -80:
            return 2
        else:
            return 1
    
    def __str__(self):
        security = "[L]" if self.encrypted else "[U]"
        signal = "[^]" * self.signal_strength + "[o]" * (5 - self.signal_strength)
        return f"{self.ssid} {security} {signal} ({self.rssi} dBm)"


class WiFiWizard:
    """Interactive WiFi configuration wizard"""
    
    def __init__(self, port: Optional[str] = None, baud_rate: int = 115200):
        self.port = port
        self.baud_rate = baud_rate
        self.serial_connection = None
    
    def _connect_serial(self) -> bool:
        """Connect to ESP8266 via serial"""
        try:
            if not self.port:
                # Auto-detect ESP8266
                ports = detect_esp8266()
                esp_ports = [p for p in ports if p['likely_esp']]
                
                if not esp_ports:
                    if ports:
                        print("[!] No ESP8266 detected, but found these ports:")
                        for i, port in enumerate(ports, 1):
                            print(f"   {i}. {port['port']} - {port['description']}")
                        
                        choice = input("\nSelect port number (or press Enter to skip): ").strip()
                        if choice.isdigit() and 1 <= int(choice) <= len(ports):
                            self.port = ports[int(choice) - 1]['port']
                        else:
                            return False
                    else:
                        raise DeviceNotFoundError("No serial ports found")
                else:
                    self.port = esp_ports[0]['port']
                    print(f"[^] Auto-detected ESP8266 on port: {self.port}")
            
            # Connect to serial port
            self.serial_connection = serial.Serial(self.port, self.baud_rate, timeout=2)
            time.sleep(1.5)  # Wait for ESP8266 to finish bootloader output
            self.serial_connection.reset_input_buffer()

            # Test connection (send newline first to clear any incomplete command buffer)
            self._send_command("")
            time.sleep(0.1)
            self._send_command("HELP")
            response = self._read_response(timeout=3)

            if "ESP-Linker Serial Commands" in response:
                print("[+] Serial connection established")
                return True
            else:
                print("[!] Connected but ESP-Linker firmware not detected")
                print("[i] You may need to flash ESP-Linker firmware first")
                return False
                
        except Exception as e:
            print(f"[!] Serial connection failed: {e}")
            return False
    
    def _send_command(self, command: str):
        """Send command to ESP8266"""
        if self.serial_connection:
            self.serial_connection.write(f"{command}\n".encode())
            self.serial_connection.flush()
    
    def _read_response(self, timeout: int = 5) -> str:
        """Read response from ESP8266"""
        if not self.serial_connection:
            return ""
        
        response = ""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.serial_connection.in_waiting > 0:
                data = self.serial_connection.read(self.serial_connection.in_waiting)
                response += data.decode('utf-8', errors='ignore')
            time.sleep(0.1)
        
        return response
    
    def scan_networks(self) -> List[WiFiNetwork]:
        """Scan for available WiFi networks"""
        print("[?] Scanning for WiFi networks...")
        
        if TQDM_AVAILABLE:
            # Show scanning progress
            with tqdm(total=100, desc="[^] Scanning", bar_format='{desc}: {bar} {percentage:3.0f}%') as pbar:
                self._send_command("WIFI_SCAN")
                
                for i in range(100):
                    pbar.update(1)
                    time.sleep(0.05)  # 5 second total scan time
        else:
            self._send_command("WIFI_SCAN")
            time.sleep(5)
        
        response = self._read_response(timeout=10)
        networks = self._parse_scan_results(response)
        
        print(f"[+] Found {len(networks)} networks")
        return networks
    
    def _parse_scan_results(self, response: str) -> List[WiFiNetwork]:
        """Parse WiFi scan results from ESP8266 response"""
        networks = []
        lines = response.split('\n')
        
        for line in lines:
            # Parse format: "1: NetworkName (-45 dBm) [Secured]"
            match = re.match(r'\d+:\s*(.+?)\s*\((-?\d+)\s*dBm\)\s*\[(.*?)\]', line.strip())
            if match:
                ssid = match.group(1).strip()
                rssi = int(match.group(2))
                security = match.group(3).strip()
                encrypted = security.lower() != 'open'
                
                networks.append(WiFiNetwork(ssid, rssi, encrypted))
        
        # Sort by signal strength (strongest first)
        networks.sort(key=lambda n: n.rssi, reverse=True)
        return networks
    
    def display_networks(self, networks: List[WiFiNetwork]) -> int:
        """Display available networks and get user selection"""
        print("\n[^] Available WiFi Networks:")
        print("=" * 50)
        
        for i, network in enumerate(networks, 1):
            print(f"{i:2d}. {network}")
        
        print(f"{len(networks) + 1:2d}. [~] Rescan networks")
        print(f"{len(networks) + 2:2d}. [K]  Enter SSID manually")
        print(f"{len(networks) + 3:2d}. [!] Cancel")
        
        while True:
            try:
                choice = input(f"\nSelect network (1-{len(networks) + 3}): ").strip()
                
                if not choice:
                    continue
                
                choice_num = int(choice)
                
                if 1 <= choice_num <= len(networks):
                    return choice_num - 1  # Return network index
                elif choice_num == len(networks) + 1:
                    return -1  # Rescan
                elif choice_num == len(networks) + 2:
                    return -2  # Manual entry
                elif choice_num == len(networks) + 3:
                    return -3  # Cancel
                else:
                    print("[!] Invalid choice. Please try again.")
                    
            except ValueError:
                print("[!] Please enter a valid number.")
    
    def get_manual_network(self) -> Tuple[str, str]:
        """Get network details manually from user"""
        print("\n[K] Manual Network Entry")
        print("=" * 30)
        
        ssid = input("[^] Enter WiFi SSID: ").strip()
        if not ssid:
            raise ValueError("SSID cannot be empty")
        
        password = getpass.getpass("[K] Enter WiFi password (or press Enter for open network): ")
        
        return ssid, password
    
    def configure_wifi(self, ssid: str, password: str) -> bool:
        """Configure WiFi on ESP8266"""
        print(f"\n[*] Configuring WiFi: {ssid}")
        
        # Send WiFi configuration command
        config_command = f"WIFI_CONFIG:{ssid},{password}"
        self._send_command(config_command)
        
        print("[.] Connecting to WiFi...")
        
        if TQDM_AVAILABLE:
            # Show connection progress
            with tqdm(total=100, desc="[*] Connecting", bar_format='{desc}: {bar} {percentage:3.0f}%') as pbar:
                for i in range(100):
                    pbar.update(1)
                    time.sleep(0.15)  # 15 second timeout
        else:
            time.sleep(15)
        
        # Read connection result
        response = self._read_response(timeout=5)
        
        if "SUCCESS: WiFi connected!" in response:
            # Extract IP address
            ip_match = re.search(r'IP Address: ([\d.]+)', response)
            ip_address = ip_match.group(1) if ip_match else "Unknown"
            
            print(f"[+] WiFi connected successfully!")
            print(f"[^] IP Address: {ip_address}")
            
            # Get signal strength
            signal_match = re.search(r'Signal Strength: (-?\d+) dBm', response)
            if signal_match:
                signal = int(signal_match.group(1))
                print(f"[^] Signal Strength: {signal} dBm")
            
            return True
        else:
            print("[!] WiFi connection failed!")
            print("[i] Please check SSID and password")
            return False
    
    def run_wizard(self) -> bool:
        """Run the complete WiFi configuration wizard"""
        print("[*] ESP-Linker WiFi Configuration Wizard")
        print("=" * 50)
        print("This wizard will help you configure WiFi on your ESP8266")
        print("Make sure your ESP8266 is connected via USB and running ESP-Linker firmware")
        print()
        
        # Step 1: Connect to ESP8266
        if not self._connect_serial():
            print("[!] Cannot proceed without serial connection")
            return False
        
        try:
            while True:
                # Step 2: Scan for networks
                networks = self.scan_networks()
                
                if not networks:
                    print("[!] No WiFi networks found")
                    retry = input("[~] Try scanning again? (y/N): ").strip().lower()
                    if retry != 'y':
                        return False
                    continue
                
                # Step 3: Display networks and get selection
                choice = self.display_networks(networks)
                
                if choice == -1:  # Rescan
                    continue
                elif choice == -2:  # Manual entry
                    try:
                        ssid, password = self.get_manual_network()
                    except ValueError as e:
                        print(f"[!] {e}")
                        continue
                elif choice == -3:  # Cancel
                    print("[!] WiFi configuration cancelled")
                    return False
                else:  # Network selected
                    selected_network = networks[choice]
                    ssid = selected_network.ssid
                    
                    if selected_network.encrypted:
                        password = getpass.getpass(f"[K] Enter password for '{ssid}': ")
                    else:
                        password = ""
                        print(f"[U] Connecting to open network '{ssid}'")
                
                # Step 4: Configure WiFi
                if self.configure_wifi(ssid, password):
                    print("\n[*] WiFi configuration completed successfully!")
                    print("[=] Next steps:")
                    print("   1. Your ESP8266 is now connected to WiFi")
                    print("   2. You can now use the Python library:")
                    print("      from esp_linker import connect_auto")
                    print("      board = connect_auto()")
                    return True
                else:
                    retry = input("\n[~] Try again with different credentials? (y/N): ").strip().lower()
                    if retry != 'y':
                        return False
        
        finally:
            if self.serial_connection:
                self.serial_connection.close()
                print("[*] Serial connection closed")
        
        return False


def run_wifi_wizard(port: Optional[str] = None) -> bool:
    """
    Run the WiFi configuration wizard.
    
    Args:
        port: Serial port (auto-detected if None)
        
    Returns:
        True if WiFi was configured successfully
    """
    wizard = WiFiWizard(port)
    return wizard.run_wizard()
