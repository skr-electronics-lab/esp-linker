"""
ESP-Linker WiFi Configuration Wizard
(c) 2025 SK Raihan / SKR Electronics Lab

Interactive WiFi setup wizard for ESP8266 boards over USB serial.
Features:
- Modern Rich TUI with sleek tables and live scanning spinners (zero emojis)
- Arrow-key menu selection for networks via Questionary
- Secure password masking
- Real-time network scanning and colored RSSI signal quality bars
- Robust serial handshake with dynamic silence-detection response reader (zero fake progress)
"""

import sys
import serial
import time
import getpass
import re
from typing import List, Dict, Optional, Tuple

from .flasher import detect_esp8266, ESP8266Flasher
from .exceptions import DeviceNotFoundError
from .ui import ui

try:
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    import questionary
    from questionary import Style as QStyle
    QUESTIONARY_AVAILABLE = True
except ImportError:
    QUESTIONARY_AVAILABLE = False


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
            return f"[bold {ui.COLOR_SUCCESS}]{filled}[/bold {ui.COLOR_SUCCESS}][dim]{empty}[/dim]"
        elif bars == 3:
            return f"[bold {ui.COLOR_WARN}]{filled}[/bold {ui.COLOR_WARN}][dim]{empty}[/dim]"
        else:
            return f"[bold {ui.COLOR_ERROR}]{filled}[/bold {ui.COLOR_ERROR}][dim]{empty}[/dim]"


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
                ports = detect_esp8266()
                if not ports:
                    raise DeviceNotFoundError("No serial ports detected. Connect ESP8266 via USB.")

                if len(ports) == 1:
                    self.port = ports[0]['port']
                    ui.success(f"Detected board on serial port: [bold cyan]{self.port}[/bold cyan] ({ports[0]['description']})")
                else:
                    choices = [
                        {
                            "title": f"{p['port']}  -  {p['description']}" + (" [Likely ESP8266]" if p['likely_esp'] else ""),
                            "value": p['port']
                        }
                        for p in ports
                    ]
                    self.port = ui.select_menu("Select serial port for ESP8266:", choices, default=ports[0]['port'])
                    ui.success(f"Selected serial port: [bold cyan]{self.port}[/bold cyan]")

            ui.step(f"Opening serial connection to {self.port} at {self.baud_rate} baud...")
            self.serial_connection = serial.Serial(self.port, self.baud_rate, timeout=2)
            time.sleep(1.2)  # Wait for ESP bootloader output to settle
            self.serial_connection.reset_input_buffer()

            # Handshake with ESP-Linker firmware
            self._send_command("")
            time.sleep(0.1)
            self._send_command("HELP")
            response = self._read_response(timeout=3.0, stop_pattern="ESP-Linker Serial Commands")

            if "ESP-Linker Serial Commands" in response:
                ui.success("ESP-Linker firmware communication verified")
                return True
            else:
                ui.warn("Connected to port, but ESP-Linker firmware did not respond to HELP.")
                ui.info("If the board is freshly connected, please flash first with: [bold cyan]esp-linker flash[/bold cyan]")
                return False

        except Exception as e:
            ui.error(f"Serial connection failed: {e}")
            return False

    def _send_command(self, command: str):
        """Send command to ESP8266"""
        if self.serial_connection:
            self.serial_connection.write(f"{command}\n".encode())
            self.serial_connection.flush()

    def _read_response(self, timeout: float = 6.0, stop_pattern: Optional[str] = None, wait_after_stop: float = 0.5) -> str:
        """Read response from ESP8266 until stop pattern or timeout"""
        if not self.serial_connection:
            return ""

        response = ""
        start_time = time.time()
        stop_seen_time = None

        while time.time() - start_time < timeout:
            if self.serial_connection.in_waiting > 0:
                data = self.serial_connection.read(self.serial_connection.in_waiting)
                chunk = data.decode('utf-8', errors='ignore')
                response += chunk

            if stop_pattern and stop_pattern in response:
                if stop_seen_time is None:
                    stop_seen_time = time.time()
                if time.time() - stop_seen_time >= wait_after_stop:
                    break

            time.sleep(0.05)

        return response

    def scan_networks(self) -> List[WiFiNetwork]:
        """Scan for available WiFi networks using active serial polling (no fake progress)"""
        ui.step("Scanning for 2.4 GHz WiFi networks...")

        response = ""
        self._send_command("WIFI_SCAN")

        def _do_scan():
            nonlocal response
            start = time.time()
            scan_timeout = 15.0
            found_networks = False
            last_net_time = None

            while time.time() - start < scan_timeout:
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    data = self.serial_connection.read(self.serial_connection.in_waiting)
                    chunk = data.decode('utf-8', errors='ignore')
                    response += chunk

                    if "No networks found" in response:
                        break

                    if re.search(r'\d+:\s*.+\s*\(-?\d+\s*dBm\)', response):
                        found_networks = True
                        last_net_time = time.time()

                if found_networks and last_net_time and (time.time() - last_net_time > 1.0):
                    break

                time.sleep(0.05)

        if RICH_AVAILABLE and ui.console and not ui.plain_mode:
            with Progress(
                SpinnerColumn(spinner_name="dots", style=f"bold {ui.COLOR_PRIMARY}"),
                TextColumn(f"[bold {ui.COLOR_PRIMARY}]ESP8266 scanning wireless channels..."),
                TimeElapsedColumn(),
                console=ui.console,
                transient=True
            ) as progress:
                progress.add_task("Scanning...", total=None)
                _do_scan()
        else:
            _do_scan()

        networks = self._parse_scan_results(response)
        ui.success(f"Discovered {len(networks)} visible WiFi network(s)")
        return networks

    def _parse_scan_results(self, response: str) -> List[WiFiNetwork]:
        """Parse WiFi scan results from ESP8266 serial output"""
        networks = []
        lines = response.splitlines()

        for line in lines:
            match = re.match(r'\d+:\s*(.+?)\s*\((-?\d+)\s*dBm\)\s*\[(.*?)\]', line.strip())
            if match:
                ssid = match.group(1).strip()
                rssi = int(match.group(2))
                security = match.group(3).strip()
                encrypted = security.lower() != 'open'
                networks.append(WiFiNetwork(ssid, rssi, encrypted))

        networks.sort(key=lambda n: n.rssi, reverse=True)
        return networks

    def display_networks_table(self, networks: List[WiFiNetwork]):
        """Render table of discovered networks"""
        if RICH_AVAILABLE and ui.console and not ui.plain_mode:
            table = Table(
                title="Discovered WiFi Networks (2.4 GHz)",
                box=box.ROUNDED,
                header_style=f"bold {ui.COLOR_PRIMARY}",
                border_style=ui.COLOR_BORDER,
                title_style=f"bold {ui.COLOR_PRIMARY}"
            )
            table.add_column("#", style="dim", width=4)
            table.add_column("SSID", style="bold white", width=28)
            table.add_column("Signal", justify="right", width=12)
            table.add_column("Quality", justify="center", width=10)
            table.add_column("Security", justify="center", width=12)

            for i, net in enumerate(networks, 1):
                sec_str = f"[{ui.COLOR_WARN}]WPA/WPA2[/{ui.COLOR_WARN}]" if net.encrypted else f"[{ui.COLOR_SUCCESS}]Open[/{ui.COLOR_SUCCESS}]"
                table.add_row(
                    str(i),
                    net.ssid,
                    f"{net.rssi} dBm",
                    net.quality_bar(),
                    sec_str
                )

            ui.console.print(table)
        else:
            print("\nAvailable WiFi Networks:")
            print("-" * 50)
            for i, net in enumerate(networks, 1):
                sec = "Secured" if net.encrypted else "Open"
                print(f" {i:2d}. {net.ssid:<25} ({net.rssi} dBm) [{sec}]")
            print("-" * 50)

    def select_network_option(self, networks: List[WiFiNetwork]) -> Tuple[int, Optional[str]]:
        """
        Interactive network selection using arrow keys or numbered fallback.
        Returns (choice_code, manual_ssid).
        choice_code >= 0 is network index, -1 is rescan, -2 is manual, -3 is cancel.
        """
        is_tty = sys.stdin.isatty() if hasattr(sys.stdin, 'isatty') else False

        if QUESTIONARY_AVAILABLE and not ui.plain_mode and is_tty:
            choices = []
            for i, net in enumerate(networks):
                sec_label = "Secured" if net.encrypted else "Open"
                choices.append({
                    "title": f"{net.ssid:<24}  ({net.rssi} dBm)  [{sec_label}]",
                    "value": str(i)
                })
            choices.append({"title": "[Rescan Networks]", "value": "rescan"})
            choices.append({"title": "[Enter Hidden / Manual SSID]", "value": "manual"})
            choices.append({"title": "[Cancel Setup]", "value": "cancel"})

            selected = ui.select_menu("Select WiFi network to connect:", choices)
            if selected == "rescan":
                return -1, None
            elif selected == "manual":
                return -2, None
            elif selected == "cancel" or selected is None:
                return -3, None
            else:
                return int(selected), None
        else:
            self.display_networks_table(networks)
            print("Options: [R] Rescan | [M] Manual Entry | [Q] Cancel")
            while True:
                choice = input("\nEnter choice [number, R, M, Q]: ").strip()
                if not choice:
                    continue
                lower = choice.lower()
                if lower == 'r':
                    return -1, None
                elif lower == 'm':
                    return -2, None
                elif lower in ['q', 'cancel', 'exit']:
                    return -3, None
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(networks):
                        return idx, None

    def get_password_input(self, ssid: str) -> str:
        """Prompt for password with secure hidden input"""
        is_tty = sys.stdin.isatty() if hasattr(sys.stdin, 'isatty') else False
        if QUESTIONARY_AVAILABLE and not ui.plain_mode and is_tty:
            custom_style = QStyle([
                ('qmark', f'fg:{ui.COLOR_BRAND} bold'),
                ('question', 'bold white'),
                ('answer', f'fg:{ui.COLOR_SUCCESS} bold'),
            ])
            pwd = questionary.password(
                f"Enter password for '{ssid}':",
                style=custom_style,
                qmark="◆"
            ).ask()
            return pwd or ""
        else:
            return getpass.getpass(f"Enter password for '{ssid}': ")

    def configure_wifi(self, ssid: str, password: str) -> bool:
        """Send credentials to ESP8266 and await connection confirmation"""
        ui.info(f"Sending credentials for SSID: [bold white]{ssid}[/bold white]")

        # Send command
        config_command = f"WIFI_CONFIG:{ssid},{password}"
        self._send_command(config_command)

        response = ""
        def _do_connect():
            nonlocal response
            start = time.time()
            connect_timeout = 20.0
            success_time = None

            while time.time() - start < connect_timeout:
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    data = self.serial_connection.read(self.serial_connection.in_waiting)
                    chunk = data.decode('utf-8', errors='ignore')
                    response += chunk

                    if "SUCCESS: WiFi connected!" in response:
                        if success_time is None:
                            success_time = time.time()
                        if "Signal Strength:" in response or (time.time() - success_time > 1.0):
                            break

                    if "ERROR: Failed to connect" in response:
                        break

                time.sleep(0.05)

        if RICH_AVAILABLE and ui.console and not ui.plain_mode:
            with Progress(
                SpinnerColumn(spinner_name="dots", style=f"bold {ui.COLOR_BRAND}"),
                TextColumn(f"[bold {ui.COLOR_PRIMARY}]ESP8266 connecting to {ssid}..."),
                TimeElapsedColumn(),
                console=ui.console,
                transient=True
            ) as progress:
                progress.add_task("Connecting...", total=None)
                _do_connect()
        else:
            ui.step(f"Waiting for ESP8266 to join {ssid}...")
            _do_connect()

        if "SUCCESS: WiFi connected!" in response:
            ip_match = re.search(r'IP Address: ([\d.]+)', response)
            ip_address = ip_match.group(1) if ip_match else "Unknown"

            signal_match = re.search(r'Signal Strength: (-?\d+) dBm', response)
            signal_dbm = signal_match.group(1) if signal_match else "N/A"

            if RICH_AVAILABLE and ui.console and not ui.plain_mode:
                summary = Text()
                summary.append("✔ WiFi Connection Established!\n\n", style=f"bold {ui.COLOR_SUCCESS}")
                summary.append("  Connected SSID:  ", style=ui.COLOR_MUTED)
                summary.append(f"{ssid}\n", style="bold white")
                summary.append("  Assigned IP:     ", style=ui.COLOR_MUTED)
                summary.append(f"{ip_address}\n", style=f"bold {ui.COLOR_PRIMARY}")
                summary.append("  Signal Strength: ", style=ui.COLOR_MUTED)
                summary.append(f"{signal_dbm} dBm\n\n", style="white")
                summary.append("Next Steps:\n", style="bold white")
                summary.append("  1. Verify Hardware:  ", style=ui.COLOR_PRIMARY)
                summary.append(f"esp-linker test {ip_address}\n", style="bold white")
                summary.append("  2. Python Control:   ", style=ui.COLOR_PRIMARY)
                summary.append(f"from esp_linker import ESPBoard; board = ESPBoard(ip='{ip_address}')\n", style="bold white")

                panel = Panel(summary, title=f"[bold {ui.COLOR_SUCCESS}]WiFi Configured[/bold {ui.COLOR_SUCCESS}]", box=box.ROUNDED, border_style=ui.COLOR_SUCCESS, expand=False)
                ui.console.print(panel)
            else:
                print("\n[OK] WiFi connected successfully!")
                print(f"  SSID:        {ssid}")
                print(f"  Assigned IP: {ip_address}")
                print(f"  Signal:      {signal_dbm} dBm\n")

            return True
        else:
            ui.error("WiFi connection failed! Please verify SSID spelling and password.")
            return False

    def run_wizard(self) -> bool:
        """Run the complete interactive WiFi wizard"""
        ui.banner("ESP-LINKER", "WiFi Configuration Wizard")

        if not self._connect_serial():
            return False

        try:
            while True:
                networks = self.scan_networks()

                if not networks:
                    ui.warn("No visible 2.4 GHz WiFi networks found.")
                    retry = input("Try scanning again? (y/N): ").strip().lower()
                    if retry != 'y':
                        return False
                    continue

                code, _ = self.select_network_option(networks)

                if code == -1:  # Rescan
                    continue
                elif code == -2:  # Manual entry
                    ssid = input("\nEnter WiFi SSID: ").strip()
                    if not ssid:
                        ui.error("SSID cannot be empty.")
                        continue
                    password = self.get_password_input(ssid)
                elif code == -3:  # Cancel
                    ui.info("WiFi setup cancelled by user.")
                    return False
                else:  # Selected from list
                    selected_network = networks[code]
                    ssid = selected_network.ssid

                    if selected_network.encrypted:
                        password = self.get_password_input(ssid)
                    else:
                        password = ""
                        ui.info(f"Connecting to open network '{ssid}'")

                if self.configure_wifi(ssid, password):
                    return True
                else:
                    retry = input("\nTry again with different credentials? (y/N): ").strip().lower()
                    if retry != 'y':
                        return False

        finally:
            if self.serial_connection:
                self.serial_connection.close()
                ui.info("Serial connection closed.")

        return False


def run_wifi_wizard(port: Optional[str] = None) -> bool:
    """Run the WiFi configuration wizard"""
    wizard = WiFiWizard(port)
    return wizard.run_wizard()
