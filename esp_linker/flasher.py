"""
ESP-Linker Firmware Flasher
(c) 2025 SK Raihan / SKR Electronics Lab

High-performance firmware flashing engine for ESP8266 boards.
Features:
- Sleek, modern terminal UI (Rich engine, zero emojis, clean engineering aesthetic)
- Real-time output streaming (deadlock-free subprocess architecture)
- Single-pass atomic write with flash erase
- Intelligent port detection (filters system ports, prioritizes ESP USB chips)
- Automatic high-speed baud detection with graceful fallback (460800 -> 115200)
"""

import os
import sys
import time
import subprocess
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

import serial.tools.list_ports

from .logger import get_logger
from .exceptions import FlashError, DeviceNotFoundError

logger = get_logger(__name__)

# Terminal UI Engine
try:
    from rich.console import Console
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
        TimeElapsedColumn,
    )
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None


def ui_print(message: str, style: str = ""):
    """Print message with Rich styling or fallback to plain text (NO emojis)"""
    if RICH_AVAILABLE and console:
        console.print(message, style=style if style else None)
    else:
        # Strip simple rich markup if fallback
        clean_text = re.sub(r'\[/?[a-zA-Z0-9_\s#]+\]', '', message)
        print(clean_text)


def print_badge(level: str, message: str):
    """Print a standardized, styled badge without emojis"""
    badges = {
        "INFO": "[bold cyan][INFO][/bold cyan]",
        "OK": "[bold green][OK][/bold green]",
        "SUCCESS": "[bold green][SUCCESS][/bold green]",
        "WAIT": "[bold yellow][WAIT][/bold yellow]",
        "WARN": "[bold yellow][WARN][/bold yellow]",
        "ERROR": "[bold red][ERROR][/bold red]",
        "FLASH": "[bold blue][FLASH][/bold blue]",
        "DETECT": "[bold magenta][DETECT][/bold magenta]",
        "RETRY": "[bold yellow][RETRY][/bold yellow]",
    }
    badge = badges.get(level.upper(), f"[{level.upper()}]")
    ui_print(f"{badge} {message}")


def render_banner(title: str = "ESP-LINKER FIRMWARE FLASHER", subtitle: str = "SKR Electronics Lab"):
    """Render a clean, high-tech header banner without emojis"""
    if RICH_AVAILABLE and console:
        content = Text()
        content.append(f"{title}\n", style="bold cyan")
        content.append(f"{subtitle} | Universal Wireless GPIO Platform", style="dim white")
        panel = Panel(content, box=box.ROUNDED, border_style="cyan", expand=False)
        console.print(panel)
    else:
        print("=" * 60)
        print(f" {title} ")
        print(f" {subtitle} ")
        print("=" * 60)


class ProgressTracker:
    """Modern progress tracking with smooth Rich bars or clean plain text"""

    def __init__(self, use_progress_bar: bool = True):
        self.use_progress_bar = use_progress_bar and RICH_AVAILABLE
        self.progress = None
        self.task_id = None

    def start_operation(self, description: str, total: int = 100):
        """Start a new operation with progress tracking"""
        if self.use_progress_bar and console:
            self.progress = Progress(
                SpinnerColumn(spinner_name="dots", style="bold cyan"),
                TextColumn("[bold cyan]{task.description}"),
                BarColumn(bar_width=36, style="grey23", complete_style="bold cyan", finished_style="bold green"),
                TaskProgressColumn("[bold white]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
                transient=False
            )
            self.progress.start()
            self.task_id = self.progress.add_task(description, total=total)
        else:
            print_badge("INFO", f"{description}...")

    def update_to(self, percentage: int, message: Optional[str] = None):
        """Update progress bar to specific percentage"""
        if self.progress and self.task_id is not None:
            self.progress.update(
                self.task_id,
                completed=min(percentage, 100),
                description=message or "Flashing firmware"
            )
        elif message:
            print_badge("INFO", message)

    def finish_operation(self, success_message: str):
        """Finish current operation"""
        if self.progress and self.task_id is not None:
            self.progress.update(self.task_id, completed=100)
            self.progress.stop()
            self.progress = None
        print_badge("SUCCESS", success_message)


class ESP8266Flasher:
    """ESP8266 firmware flasher using esptool"""

    DEFAULT_BAUD_RATE = 460800
    FALLBACK_BAUD_RATE = 115200
    DEFAULT_FLASH_SIZE = "4MB"
    DEFAULT_FLASH_MODE = "dio"
    DEFAULT_FLASH_FREQ = "40m"
    FLASH_ADDRESS = "0x00000"

    def __init__(self):
        """Initialize the flasher"""
        self.firmware_path = self._get_firmware_path()
        self.esptool_path = self._get_esptool_path()

    def _get_firmware_path(self) -> str:
        """Get the path to the bundled firmware using modern resource lookup"""
        # 1. Path relative to module file
        current_dir = Path(__file__).resolve().parent
        firmware_path = current_dir / "firmware" / "esp-linker-firmware.bin"
        if firmware_path.exists():
            return str(firmware_path)

        # 2. Try importlib.resources (Python 3.9+)
        try:
            import importlib.resources as pkg_res
            if hasattr(pkg_res, 'files'):
                traversable = pkg_res.files('esp_linker').joinpath('firmware', 'esp-linker-firmware.bin')
                if traversable.is_file():
                    return str(traversable)
        except Exception:
            pass

        raise FlashError("ESP-Linker firmware binary not found. Please reinstall the library.")

    def _get_esptool_path(self) -> str:
        """Get esptool entry point or module"""
        try:
            import esptool
            return sys.executable
        except ImportError:
            raise FlashError("esptool not found. Please install it with: pip install esptool")

    def detect_esp8266_ports(self) -> List[Dict[str, Any]]:
        """
        Detect ESP8266 boards connected via USB.

        Returns:
            List of dictionaries with port information
        """
        esp_ports = []
        ports = list(serial.tools.list_ports.comports())

        esp_identifiers = [
            'CH340',
            'CP210',
            'FT232',
            'USB-SERIAL',
            'USB2.0-SERIAL',
            'SILICON LABS',
            'SILICON LABORATORIES',
            'WCH.CN',
            'FTDI',
            'ESP'
        ]

        for port in ports:
            hwid_upper = (port.hwid or "").upper()
            if "PNP0501" in hwid_upper:
                continue

            desc_upper = (port.description or "").upper()
            mfg_upper = (getattr(port, 'manufacturer', '') or "").upper()

            likely_esp = False
            for ident in esp_identifiers:
                if ident in desc_upper or ident in hwid_upper or ident in mfg_upper:
                    likely_esp = True
                    break

            is_usb = "USB" in hwid_upper or "VID:PID" in hwid_upper

            esp_ports.append({
                'port': port.device,
                'description': port.description or "Unknown Serial Device",
                'hwid': port.hwid or "",
                'manufacturer': getattr(port, 'manufacturer', 'Unknown') or 'Unknown',
                'likely_esp': likely_esp,
                'is_usb': is_usb
            })

        esp_ports.sort(key=lambda x: (x['likely_esp'], x['is_usb']), reverse=True)
        return esp_ports

    def auto_detect_port(self) -> str:
        """
        Automatically detect ESP8266 port.

        Returns:
            Port name (e.g., 'COM3', '/dev/ttyUSB0')
        """
        ports = self.detect_esp8266_ports()

        if not ports:
            raise DeviceNotFoundError("No USB serial ports detected. Connect your ESP8266 board via USB.")

        for p in ports:
            if p['likely_esp']:
                return p['port']

        usb_ports = [p for p in ports if p['is_usb']]
        if len(usb_ports) == 1:
            return usb_ports[0]['port']

        avail = [f"{p['port']} ({p['description']})" for p in ports]
        raise DeviceNotFoundError(
            f"Could not automatically identify ESP8266. Available ports: {', '.join(avail)}. "
            f"Specify port manually with --port <PORT>."
        )

    def display_ports_table(self):
        """Display discovered ports in a clean Rich table without emojis"""
        ports = self.detect_esp8266_ports()
        if not ports:
            print_badge("WARN", "No serial ports found")
            return

        if RICH_AVAILABLE and console:
            table = Table(
                title="Available Serial Ports",
                box=box.ROUNDED,
                header_style="bold cyan",
                border_style="cyan"
            )
            table.add_column("#", style="dim", width=4)
            table.add_column("Port", style="bold white", width=12)
            table.add_column("Description", style="white")
            table.add_column("Manufacturer", style="dim")
            table.add_column("Likely ESP8266", justify="center")

            for i, p in enumerate(ports, 1):
                indicator = "[bold green]YES[/bold green]" if p['likely_esp'] else "[dim]NO[/dim]"
                table.add_row(str(i), p['port'], p['description'], p['manufacturer'], indicator)

            console.print(table)
        else:
            print("\nAvailable Serial Ports:")
            print("-" * 50)
            for i, p in enumerate(ports, 1):
                flag = "[ESP8266 MATCH]" if p['likely_esp'] else ""
                print(f"{i}. {p['port']} - {p['description']} {flag}")
            print()

    def display_flash_summary(self, port: str, baud_rate: int):
        """Display configuration summary table before flashing"""
        firmware_size = os.path.getsize(self.firmware_path)
        firmware_size_kb = firmware_size / 1024

        if RICH_AVAILABLE and console:
            table = Table(box=box.ROUNDED, border_style="cyan", show_header=False)
            table.add_column("Parameter", style="bold cyan", width=18)
            table.add_column("Value", style="white")

            table.add_row("Target Architecture", "ESP8266 (NodeMCU / Generic)")
            table.add_row("Serial Port", port)
            table.add_row("Baud Rate", f"{baud_rate} bps")
            table.add_row("Flash Mode", f"{self.DEFAULT_FLASH_MODE.upper()} / 40MHz")
            table.add_row("Firmware Binary", f"{firmware_size_kb:.1f} KB ({self.firmware_path})")
            table.add_row("Flash Address", self.FLASH_ADDRESS)

            panel = Panel(table, title="[bold white]Flash Configuration[/bold white]", box=box.ROUNDED, border_style="cyan")
            console.print(panel)
        else:
            print("-" * 50)
            print(f"Target: ESP8266 | Port: {port} | Baud: {baud_rate}")
            print(f"Firmware: {firmware_size_kb:.1f} KB | Addr: {self.FLASH_ADDRESS}")
            print("-" * 50)

    def _execute_flash(self, port: str, baud_rate: int, erase_flash: bool,
                       progress: ProgressTracker, progress_callback: Optional[Callable] = None) -> bool:
        """Execute esptool flash with real-time output parsing to prevent deadlock"""
        cmd = [
            sys.executable, "-m", "esptool",
            "--chip", "esp8266",
            "--port", port,
            "--baud", str(baud_rate),
            "--before", "default-reset",
            "--after", "hard-reset",
            "write-flash",
            "--flash-size", "detect",
            "--flash-mode", self.DEFAULT_FLASH_MODE,
            "--flash-freq", self.DEFAULT_FLASH_FREQ
        ]

        if erase_flash:
            cmd.append("--erase-all")

        cmd.extend([self.FLASH_ADDRESS, self.firmware_path])

        progress.start_operation(f"Connecting ({baud_rate} baud) & Writing Flash", total=100)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        all_output = []
        percent_pattern = re.compile(r'\((\d+)\s*%\)')

        try:
            for line in iter(process.stdout.readline, ''):
                all_output.append(line)
                clean_line = line.strip()

                if progress_callback:
                    progress_callback(clean_line)

                match = percent_pattern.search(clean_line)
                if match:
                    pct = int(match.group(1))
                    progress.update_to(pct, f"Writing blocks: {pct}%")
                elif "Erasing flash" in clean_line:
                    progress.update_to(10, "Erasing flash sectors...")
                elif "Connecting" in clean_line:
                    progress.update_to(5, "Syncing with bootloader...")
                elif "Hash of data verified" in clean_line:
                    progress.update_to(100, "Verifying flash image...")

            process.stdout.close()
            process.wait()
        except Exception:
            process.kill()
            raise

        full_log = "".join(all_output)

        if process.returncode != 0:
            if "Timed out waiting for packet header" in full_log or "Failed to connect" in full_log:
                raise TimeoutError(f"Connection timed out at {baud_rate} baud.\n{full_log}")
            raise FlashError(f"Flashing failed with exit code {process.returncode}:\n{full_log}")

        progress.finish_operation("Firmware successfully written and verified!")
        return True

    def flash_firmware(self,
                       port: Optional[str] = None,
                       baud_rate: int = DEFAULT_BAUD_RATE,
                       erase_flash: bool = True,
                       verify: bool = True,
                       progress_callback: Optional[Callable] = None,
                       use_progress_bar: bool = True) -> bool:
        """
        Flash ESP-Linker firmware to ESP8266 with automatic baud fallback and deadlock prevention.
        """
        render_banner()

        # Port detection
        if port is None:
            print_badge("DETECT", "Auto-detecting connected ESP8266 board...")
            port = self.auto_detect_port()
            print_badge("OK", f"Detected board on serial port: [bold cyan]{port}[/bold cyan]")
        else:
            print_badge("INFO", f"Using specified serial port: [bold cyan]{port}[/bold cyan]")

        if not os.path.exists(self.firmware_path):
            raise FlashError(f"Firmware binary missing: {self.firmware_path}")

        self.display_flash_summary(port, baud_rate)

        progress = ProgressTracker(use_progress_bar)

        try:
            success = self._execute_flash(port, baud_rate, erase_flash, progress, progress_callback)
        except TimeoutError as e:
            if baud_rate != self.FALLBACK_BAUD_RATE:
                print_badge("WARN", f"High-speed baud rate ({baud_rate}) timed out.")
                print_badge("RETRY", f"Retrying at safe baud rate ({self.FALLBACK_BAUD_RATE} bps)...")
                time.sleep(1.0)
                success = self._execute_flash(port, self.FALLBACK_BAUD_RATE, erase_flash, progress, progress_callback)
            else:
                raise FlashError(str(e))
        except FlashError:
            raise
        except Exception as e:
            raise FlashError(f"Flash execution failed: {e}")

        # Post-flash clean summary
        if success:
            if RICH_AVAILABLE and console:
                panel_text = Text()
                panel_text.append("[SUCCESS] ESP-Linker firmware installed successfully!\n\n", style="bold green")
                panel_text.append("Next Steps:\n", style="bold white")
                panel_text.append(" 1. Run WiFi Wizard:   ", style="cyan")
                panel_text.append("esp-linker setup-wifi\n", style="bold white")
                panel_text.append(" 2. Discover Devices: ", style="cyan")
                panel_text.append("esp-linker discover\n", style="bold white")
                panel_text.append(" 3. Start Python:     ", style="cyan")
                panel_text.append("from esp_linker import connect_auto\n", style="bold white")
                panel = Panel(panel_text, box=box.ROUNDED, border_style="green", expand=False)
                console.print(panel)
            else:
                print("\n[SUCCESS] Firmware installed successfully!")
                print("Next Steps:")
                print("  1. esp-linker setup-wifi")
                print("  2. esp-linker discover")

        return success

    def get_chip_info(self, port: Optional[str] = None) -> Dict[str, Any]:
        """Get ESP8266 chip information"""
        if port is None:
            port = self.auto_detect_port()

        cmd = [
            sys.executable, "-m", "esptool",
            "--chip", "esp8266",
            "--port", port,
            "--baud", str(self.FALLBACK_BAUD_RATE),
            "chip-id"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            cmd[-1] = "chip_id"
            result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise FlashError(f"Failed to query chip info: {result.stderr or result.stdout}")

        output = result.stdout
        chip_info = {
            'port': port,
            'chip_type': 'ESP8266',
            'raw_output': output
        }

        for line in output.splitlines():
            if 'Chip ID:' in line or 'Chip is' in line:
                chip_info['chip_id'] = line.split(':')[-1].strip()
            elif 'MAC:' in line:
                chip_info['mac_address'] = line.split(':')[-1].strip()
            elif 'Features:' in line:
                chip_info['features'] = line.split(':')[-1].strip()

        return chip_info

    def get_firmware_info(self) -> Dict[str, Any]:
        """Get bundled firmware metadata"""
        if not os.path.exists(self.firmware_path):
            raise FlashError("Firmware binary not found")

        stat = os.stat(self.firmware_path)

        return {
            'path': self.firmware_path,
            'size': stat.st_size,
            'size_kb': round(stat.st_size / 1024, 1),
            'modified': time.ctime(stat.st_mtime),
            'version': '1.3.8',
            'name': 'ESP-Linker Firmware',
            'description': 'Universal ESP-Linker firmware with WiFi configuration, Serial CLI, and PyFirmata-style GPIO control'
        }


def flash_esp8266(port: Optional[str] = None,
                  baud_rate: int = ESP8266Flasher.DEFAULT_BAUD_RATE,
                  erase_flash: bool = True,
                  progress_callback: Optional[Callable] = None) -> bool:
    """Convenience function to flash ESP-Linker firmware"""
    flasher = ESP8266Flasher()
    return flasher.flash_firmware(
        port=port,
        baud_rate=baud_rate,
        erase_flash=erase_flash,
        progress_callback=progress_callback
    )


def detect_esp8266() -> List[Dict[str, Any]]:
    """Detect connected ESP8266 boards"""
    flasher = ESP8266Flasher()
    return flasher.detect_esp8266_ports()


def get_chip_info(port: Optional[str] = None) -> Dict[str, Any]:
    """Get ESP8266 chip information"""
    flasher = ESP8266Flasher()
    return flasher.get_chip_info(port)
