"""
ESP-Linker WiFi Configuration Wizard
(c) 2025 SK Raihan / SKR Electronics Lab

Interactive WiFi setup wizard for ESP8266 boards over USB serial.
Features:
- Modern Rich TUI with sleek tables and progress bars (zero emojis)
- Real-time network scanning and RSSI signal quality bars
- Robust serial handshake with input buffer flush
"""

import serial
import time
import getpass
import re
from typing import List, Dict, Optional, Tuple

from .flasher import detect_esp8266, ESP8266Flasher, print_badge, ui_print, RICH_AVAILABLE, console
from .exceptions import DeviceNotFoundError

try:
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich import box
except ImportError:
    pass


class WiFiNetwork:
    """Represents a discovered WiFi network"""

    def __init__(self, ssid: str, rssi: int, encrypted: bool):
        self.ssid = ssid
        self.rssi = rssi
        self.encrypted = encrypted
        self.signal_bars = self._calculate_signal_bars()

    def _calculate_signal_bars(self) -> int:
        """Calculate signal bars 1 to 5 based on dBm"""
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

    def quality_bar(self) -> str:
        """Render high-tech text bar for signal quality"""
        bars = self.signal_bars
        filled = "█" * bars
        empty = "░" * (5 - bars)
        if bars >= 4:
            return f"[bold green]{filled}[/bold green][dim]{empty}[/dim]"
        elif bars == 3:
            return f"[bold yellow]{filled}[/bold yellow][dim]{empty}[/dim]"
        else:
            return f"[bold red]{filled}[/bold red][dim]{empty}[/dim]"


class WiFiWizard:
    """Interactive WiFi configuration wizard"""

    def __init__(self, port: Optional[str] = None, baud_rate: int = 115200):
        self.port = port
        self.baud_rate = baud_rate
        self.serial_connection = None

    def _connect_serial(self) -> bool:
        """Connect to ESP8266 via USB serial"""
        try:
            if not self.port:
                print_badge("DETECT", "Searching for connected ESP8266 board...")
                try:
                    self.port = ESP8266Flasher().auto_detect_port()
                    print_badge("OK", f"Found board on serial port: [bold cyan]{self.port}[/bold cyan]")
                except Exception:
                    ports = detect_esp8266()
                    if not ports:
                        raise DeviceNotFoundError("No serial ports found")

                    print_badge("WARN", "Multiple ports found. Please select:")
                    for i, p in enumerate(ports, 1):
                        ui_print(f"  {i}. {p['port']} - {p['description']}")

                    choice = input("\nSelect port number: ").strip()
                    if choice.isdigit() and 1 <= int(choice) <= len(ports):
                        self.port = ports[int(choice) - 1]['port']
                    else:
                        return False

            print_badge("INFO", f"Opening serial connection to {self.port} at {self.baud_rate} baud...")
            self.serial_connection = serial.Serial(self.port, self.baud_rate, timeout=2)
            time.sleep(1.5)  # Wait for ESP bootloader output to settle
            self.serial_connection.reset_input_buffer()

            # Handshake with ESP-Linker firmware
            self._send_command("")
            time.sleep(0.1)
            self._send_command("HELP")
            response = self._read_response(timeout=3)

            if "ESP-Linker Serial Commands" in response:
                print_badge("SUCCESS", "ESP-Linker firmware serial interface confirmed!")
                return True
            else:
                print_badge("WARN", "Connected to port, but ESP-Linker firmware did not respond to HELP.")
                print_badge("INFO", "If the board is freshly flashed, run: esp-linker flash")
                return False

        except Exception as e:
            print_badge("ERROR", f"Serial connection failed: {e}")
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
        print_badge("INFO", "Scanning for 2.4 GHz WiFi networks...")

        if RICH_AVAILABLE and console:
            with Progress(
                SpinnerColumn(spinner_name="dots", style="bold cyan"),
                TextColumn("[bold cyan]{task.description}"),
                BarColumn(bar_width=30, style="grey23", complete_style="bold cyan"),
                TimeElapsedColumn(),
                console=console,
                transient=True
            ) as progress:
                task = progress.add_task("Querying ESP8266 WiFi scan...", total=100)
                self._send_command("WIFI_SCAN")

                for _ in range(50):
                    progress.update(task, advance=2)
                    time.sleep(0.08)
        else:
            self._send_command("WIFI_SCAN")
            time.sleep(4.0)

        response = self._read_response(timeout=8)
        networks = self._parse_scan_results(response)

        print_badge("OK", f"Found {len(networks)} visible network(s)")
        return networks

    def _parse_scan_results(self, response: str) -> List[WiFiNetwork]:
        """Parse WiFi scan results from ESP8266 serial output"""
        networks = []
        lines = response.splitlines()

        for line in lines:
            # Matches: "1: NetworkName (-45 dBm) [Secured]"
            match = re.match(r'\d+:\s*(.+?)\s*\((-?\d+)\s*dBm\)\s*\[(.*?)\]', line.strip())
            if match:
                ssid = match.group(1).strip()
                rssi = int(match.group(2))
                security = match.group(3).strip()
                encrypted = security.lower() != 'open'
                networks.append(WiFiNetwork(ssid, rssi, encrypted))

        networks.sort(key=lambda n: n.rssi, reverse=True)
        return networks

    def display_networks(self, networks: List[WiFiNetwork]) -> int:
        """Display discovered networks in a clean table"""
        if RICH_AVAILABLE and console:
            table = Table(
                title="Visible WiFi Networks (2.4 GHz)",
                box=box.ROUNDED,
                header_style="bold cyan",
                border_style="cyan"
            )
            table.add_column("#", style="dim", width=4)
            table.add_column("SSID", style="bold white", width=26)
            table.add_column("Signal (dBm)", justify="right", width=12)
            table.add_column("Quality", justify="center", width=10)
            table.add_column("Security", justify="center", width=12)

            for i, net in enumerate(networks, 1):
                sec_str = "[yellow]WPA/WPA2[/yellow]" if net.encrypted else "[green]Open[/green]"
                table.add_row(
                    str(i),
                    net.ssid,
                    f"{net.rssi} dBm",
                    net.quality_bar(),
                    sec_str
                )

            console.print(table)
            ui_print("[dim]Options: [bold white][R][/bold white] Rescan | [bold white][M][/bold white] Manual SSID | [bold white][Q][/bold white] Cancel[/dim]")
        else:
            print("\nAvailable WiFi Networks:")
            print("-" * 50)
            for i, net in enumerate(networks, 1):
                sec = "Secured" if net.encrypted else "Open"
                print(f" {i:2d}. {net.ssid:<25} ({net.rssi} dBm) [{sec}]")
            print("-" * 50)
            print(" [R] Rescan | [M] Manual Entry | [Q] Cancel\n")

        while True:
            choice = input("\nSelect network option: ").strip()
            if not choice:
                continue

            lower = choice.lower()
            if lower == 'r':
                return -1
            elif lower == 'm':
                return -2
            elif lower in ['q', 'cancel', 'exit']:
                return -3

            if choice.isdigit():
                val = int(choice)
                if 1 <= val <= len(networks):
                    return val - 1

            print_badge("WARN", "Invalid selection. Enter network number, R, M, or Q.")

    def get_manual_network(self) -> Tuple[str, str]:
        """Prompt user for manual SSID and password"""
        ui_print("\n[bold cyan]Manual WiFi Configuration[/bold cyan]")
        ssid = input("Enter WiFi SSID: ").strip()
        if not ssid:
            raise ValueError("SSID cannot be empty")

        password = getpass.getpass("Enter WiFi password (or press Enter if open): ")
        return ssid, password

    def configure_wifi(self, ssid: str, password: str) -> bool:
        """Send credentials to ESP8266 and await connection confirmation"""
        print_badge("INFO", f"Sending credentials for SSID: [bold white]{ssid}[/bold white]")

        # Send command to ESP
        config_command = f"WIFI_CONFIG:{ssid},{password}"
        self._send_command(config_command)

        print_badge("WAIT", "ESP8266 connecting to WiFi network...")

        if RICH_AVAILABLE and console:
            with Progress(
                SpinnerColumn(spinner_name="dots", style="bold cyan"),
                TextColumn("[bold cyan]{task.description}"),
                BarColumn(bar_width=30, style="grey23", complete_style="bold green"),
                TimeElapsedColumn(),
                console=console,
                transient=True
            ) as progress:
                task = progress.add_task(f"Connecting to {ssid}...", total=100)
                for _ in range(70):
                    progress.update(task, advance=1.4)
                    time.sleep(0.15)
        else:
            time.sleep(12.0)

        response = self._read_response(timeout=6)

        if "SUCCESS: WiFi connected!" in response:
            ip_match = re.search(r'IP Address: ([\d.]+)', response)
            ip_address = ip_match.group(1) if ip_match else "Unknown"

            signal_match = re.search(r'Signal Strength: (-?\d+) dBm', response)
            signal_dbm = signal_match.group(1) if signal_match else "N/A"

            if RICH_AVAILABLE and console:
                summary = Text()
                summary.append("[SUCCESS] WiFi Connection Established!\n\n", style="bold green")
                summary.append("  SSID:            ", style="dim white")
                summary.append(f"{ssid}\n", style="bold white")
                summary.append("  Assigned IP:     ", style="dim white")
                summary.append(f"{ip_address}\n", style="bold cyan")
                summary.append("  Signal Strength: ", style="dim white")
                summary.append(f"{signal_dbm} dBm\n", style="white")

                panel = Panel(summary, box=box.ROUNDED, border_style="green", expand=False)
                console.print(panel)
            else:
                print("\n[SUCCESS] WiFi connected successfully!")
                print(f"  SSID:        {ssid}")
                print(f"  Assigned IP: {ip_address}")
                print(f"  Signal:      {signal_dbm} dBm\n")

            return True
        else:
            print_badge("ERROR", "WiFi connection failed! Check SSID spelling and password.")
            return False

    def run_wizard(self) -> bool:
        """Run the complete interactive WiFi wizard"""
        if RICH_AVAILABLE and console:
            banner = Text()
            banner.append("ESP-LINKER WIFI WIZARD\n", style="bold cyan")
            banner.append("Configure ESP8266 WiFi Credentials via USB Serial", style="dim white")
            panel = Panel(banner, box=box.ROUNDED, border_style="cyan", expand=False)
            console.print(panel)
        else:
            print("=" * 60)
            print(" ESP-LINKER WIFI WIZARD ")
            print("=" * 60)

        if not self._connect_serial():
            return False

        try:
            while True:
                networks = self.scan_networks()

                if not networks:
                    print_badge("WARN", "No WiFi networks found in range.")
                    retry = input("Try scanning again? (y/N): ").strip().lower()
                    if retry != 'y':
                        return False
                    continue

                choice = self.display_networks(networks)

                if choice == -1:  # Rescan
                    continue
                elif choice == -2:  # Manual entry
                    try:
                        ssid, password = self.get_manual_network()
                    except ValueError as e:
                        print_badge("ERROR", str(e))
                        continue
                elif choice == -3:  # Cancel
                    print_badge("INFO", "WiFi configuration cancelled by user.")
                    return False
                else:  # Network selected
                    selected_network = networks[choice]
                    ssid = selected_network.ssid

                    if selected_network.encrypted:
                        password = getpass.getpass(f"Enter password for '{ssid}': ")
                    else:
                        password = ""
                        print_badge("INFO", f"Connecting to open network '{ssid}'")

                if self.configure_wifi(ssid, password):
                    ui_print("\n[bold green]Ready for Python Control![/bold green]")
                    ui_print("Run in Python:\n  [bold cyan]from esp_linker import connect_auto[/bold cyan]\n  [bold cyan]board = connect_auto()[/bold cyan]\n")
                    return True
                else:
                    retry = input("\nTry again with different credentials? (y/N): ").strip().lower()
                    if retry != 'y':
                        return False

        finally:
            if self.serial_connection:
                self.serial_connection.close()
                print_badge("INFO", "Serial connection closed.")

        return False


def run_wifi_wizard(port: Optional[str] = None) -> bool:
    """Run the WiFi configuration wizard"""
    wizard = WiFiWizard(port)
    return wizard.run_wizard()
