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
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

import serial.tools.list_ports

from .logger import get_logger
from .exceptions import FlashError, DeviceNotFoundError, TimeoutError
from .version import __firmware_version__

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

    def __init__(self, chip: str = "auto", chip_type: Optional[str] = None, **kwargs):
        """Initialize the flasher"""
        target_chip = chip_type if chip_type is not None else chip
        self.chip = target_chip
        self.firmware_path = self._get_firmware_path(target_chip)
        self.esptool_path = self._get_esptool_path()

    def _get_firmware_path(self, chip: str = "auto") -> str:
        """Get the path to the bundled firmware using modern resource lookup"""
        current_dir = Path(__file__).resolve().parent
        chip_lower = (chip or "auto").lower()

        if "esp32" in chip_lower:
            firmware_path = current_dir / "firmware" / "esp-linker-esp32.bin"
            if firmware_path.exists():
                return str(firmware_path)

        firmware_path = current_dir / "firmware" / "esp-linker-esp8266.bin"
        if firmware_path.exists():
            return str(firmware_path)

        firmware_path = current_dir / "firmware" / "esp-linker-firmware.bin"
        if firmware_path.exists():
            return str(firmware_path)

        raise FlashError(f"ESP-Linker firmware binary for {chip} not found. Please reinstall the library.")

    def detect_chip_type(self, port: str) -> str:
        """Detect whether connected chip is ESP8266 or ESP32"""
        try:
            info = self.get_chip_info(port)
            chip_type = info.get('chip_type', '').lower()
            if 'esp32' in chip_type:
                return 'esp32'
            return 'esp8266'
        except Exception:
            return 'esp8266'

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

    def display_flash_summary(self, port: str, baud_rate: int, chip: str = "auto"):
        """Display configuration summary table before flashing"""
        chip_name = "ESP32" if "esp32" in (chip or "").lower() else "ESP8266"
        fw_path = self._get_firmware_path(chip)
        flash_addr = "0x10000" if chip_name == "ESP32" else self.FLASH_ADDRESS
        firmware_size = os.path.getsize(fw_path)
        firmware_size_kb = firmware_size / 1024

        if RICH_AVAILABLE and console:
            table = Table(box=box.ROUNDED, border_style="cyan", show_header=False)
            table.add_column("Parameter", style="bold cyan", width=18)
            table.add_column("Value", style="white")

            table.add_row("Target Architecture", f"{chip_name} (Auto-detected)")
            table.add_row("Serial Port", port)
            table.add_row("Baud Rate", f"{baud_rate} bps")
            table.add_row("Flash Mode", f"{self.DEFAULT_FLASH_MODE.upper()} / 40MHz")
            table.add_row("Firmware Binary", f"{firmware_size_kb:.1f} KB ({fw_path})")
            table.add_row("Flash Address", flash_addr)

            panel = Panel(table, title="[bold white]Flash Configuration[/bold white]", box=box.ROUNDED, border_style="cyan")
            console.print(panel)
        else:
            print("-" * 50)
            print(f"Target: {chip_name} | Port: {port} | Baud: {baud_rate}")
            print(f"Firmware: {firmware_size_kb:.1f} KB | Addr: {flash_addr}")
            print("-" * 50)

    def _execute_flash(self, port: str, baud_rate: int, erase_flash: bool,
                       chip: str = "auto",
                       callbacks: Optional[Any] = None,
                       progress_callback: Optional[Callable] = None) -> bool:
        """Execute esptool flash with unbuffered real-time output streaming"""
        py_cmd = [sys.executable]
        if sys.version_info >= (3, 11):
            py_cmd.append("-P")
        py_cmd.extend(["-u", "-m", "esptool"])

        chip_lower = (chip or "auto").lower()
        if "esp32" in chip_lower:
            target_chip = "esp32"
            flash_addr = "0x10000"
            fw_path = self._get_firmware_path("esp32")
        else:
            target_chip = "esp8266"
            flash_addr = self.FLASH_ADDRESS
            fw_path = self._get_firmware_path("esp8266")

        cmd = py_cmd + [
            "--chip", target_chip,
            "--port", port,
            "--baud", str(baud_rate),
            "--connect-attempts", "10",
            "write-flash",
            "--flash-size", "detect",
            "--flash-mode", self.DEFAULT_FLASH_MODE,
            "--flash-freq", self.DEFAULT_FLASH_FREQ
        ]

        if erase_flash:
            cmd.append("--erase-all")

        cmd.extend([flash_addr, fw_path])

        firmware_size = os.path.getsize(fw_path) if os.path.exists(fw_path) else 0

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        safe_cwd = tempfile.gettempdir()

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            env=env,
            cwd=safe_cwd
        )

        all_output = []
        r_bytes = re.compile(r'(\d+)\s*/\s*(\d+)\s+bytes')
        r_pct = re.compile(r'\(?(\d+(?:\.\d+)?)\s*%')
        ansi_strip = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
        erasing = False
        flashing_started = False

        def _stream_lines(raw_stream):
            buf = bytearray()
            while True:
                char = raw_stream.read(1)
                if not char:
                    if buf:
                        yield buf.decode('utf-8', errors='replace').strip()
                    break
                if char in (b'\r', b'\n'):
                    if buf:
                        line = buf.decode('utf-8', errors='replace').strip()
                        buf.clear()
                        if line:
                            yield line
                else:
                    buf.extend(char)

        try:
            for raw_line in _stream_lines(process.stdout):
                all_output.append(raw_line + "\n")
                clean_line = ansi_strip.sub('', raw_line).strip()

                if progress_callback:
                    progress_callback(clean_line)

                if "Connecting" in clean_line:
                    if callbacks and hasattr(callbacks, "on_sync"):
                        callbacks.on_sync()
                elif "Erasing flash" in clean_line:
                    erasing = True
                    if callbacks and hasattr(callbacks, "on_erase_start"):
                        callbacks.on_erase_start()
                elif "Flash memory erased successfully" in clean_line:
                    if erasing:
                        erasing = False
                        if callbacks and hasattr(callbacks, "on_erase_complete"):
                            callbacks.on_erase_complete()
                elif "Writing at 0x" in clean_line or r_pct.search(clean_line) or r_bytes.search(clean_line):
                    if erasing:
                        erasing = False
                        if callbacks and hasattr(callbacks, "on_erase_complete"):
                            callbacks.on_erase_complete()
                    if not flashing_started:
                        flashing_started = True
                        if callbacks and hasattr(callbacks, "on_flash_start"):
                            callbacks.on_flash_start(firmware_size)
                    bytes_match = r_bytes.search(clean_line)
                    pct_match = r_pct.search(clean_line)
                    if bytes_match:
                        bytes_written = int(bytes_match.group(1))
                        total_bytes = int(bytes_match.group(2))
                        if callbacks and hasattr(callbacks, "on_flash_progress"):
                            callbacks.on_flash_progress(bytes_written, total_bytes)
                    elif pct_match:
                        pct = float(pct_match.group(1))
                        bytes_written = int(firmware_size * (pct / 100.0))
                        if callbacks and hasattr(callbacks, "on_flash_progress"):
                            callbacks.on_flash_progress(bytes_written, firmware_size)
                elif "Hash of data verified" in clean_line:
                    if callbacks and hasattr(callbacks, "on_flash_complete"):
                        callbacks.on_flash_complete()
                elif "Leaving... Hard resetting" in clean_line or "Hard resetting" in clean_line:
                    if callbacks and hasattr(callbacks, "on_reset_start"):
                        callbacks.on_reset_start()

            process.stdout.close()
            process.wait()
        except Exception:
            process.kill()
            if callbacks and hasattr(callbacks, "finish"):
                callbacks.finish()
            raise

        full_log = "".join(all_output)

        if process.returncode != 0:
            if callbacks and hasattr(callbacks, "finish"):
                callbacks.finish()
            if "Timed out waiting for packet header" in full_log or "Failed to connect" in full_log:
                raise TimeoutError(f"Connection timed out at {baud_rate} baud.\n{full_log}")
            raise FlashError(f"Flashing failed with exit code {process.returncode}:\n{full_log}")

        if not flashing_started and "Hash of data verified" not in full_log and "Wrote " not in full_log:
            if callbacks and hasattr(callbacks, "finish"):
                callbacks.finish()
            raise FlashError(f"Flashing failed: esptool did not write any data to the target.\n{full_log}")

        if callbacks and hasattr(callbacks, "on_reset_complete"):
            callbacks.on_reset_complete()
        if callbacks and hasattr(callbacks, "finish"):
            callbacks.finish()

        return True

    def flash_firmware(self,
                       port: Optional[str] = None,
                       baud_rate: int = DEFAULT_BAUD_RATE,
                       chip: str = "auto",
                       erase_flash: bool = True,
                       verify: bool = True,
                       callbacks: Optional[Any] = None,
                       progress_callback: Optional[Callable] = None,
                       use_progress_bar: bool = True) -> bool:
        """
        Flash ESP-Linker firmware to ESP8266/ESP32 with automatic baud fallback and deadlock prevention.
        """
        from .ui import ui, RichFlashProgressCallback

        # Port detection
        if port is None:
            ports = self.detect_esp8266_ports()
            if not ports:
                raise DeviceNotFoundError("No USB serial ports detected. Connect your ESP board via USB.")
            if len(ports) == 1:
                port = ports[0]['port']
                ui.success(f"Detected board on serial port: [bold cyan]{port}[/bold cyan] ({ports[0]['description']})")
            else:
                choices = [
                    {
                        "title": f"{p['port']}  -  {p['description']}" + (" [Likely ESP board]" if p['likely_esp'] else ""),
                        "value": p['port']
                    }
                    for p in ports
                ]
                port = ui.select_menu("Select serial port for ESP board:", choices, default=ports[0]['port'])
                ui.success(f"Selected serial port: [bold cyan]{port}[/bold cyan]")
        else:
            ui.info(f"Using specified serial port: [bold cyan]{port}[/bold cyan]")

        target_chip = chip
        if not target_chip or target_chip == "auto":
            target_chip = self.detect_chip_type(port)

        fw_info = self.get_firmware_info(target_chip)
        ui.show_firmware_panel(fw_info, port, baud_rate)

        if callbacks is None and use_progress_bar:
            callbacks = RichFlashProgressCallback(ui)

        if callbacks and hasattr(callbacks, "on_start"):
            callbacks.on_start(port, baud_rate, fw_info)

        try:
            success = self._execute_flash(port, baud_rate, erase_flash, target_chip, callbacks, progress_callback)
        except TimeoutError as e:
            if baud_rate != self.FALLBACK_BAUD_RATE:
                ui.warn(f"High-speed baud rate ({baud_rate}) timed out.")
                ui.warn(f"Resetting board and retrying at safe baud rate ({self.FALLBACK_BAUD_RATE} bps)...")
                try:
                    import serial
                    s = serial.Serial(port, 115200)
                    s.setDTR(False)
                    s.setRTS(True)
                    time.sleep(0.15)
                    s.setDTR(True)
                    s.setRTS(False)
                    time.sleep(0.3)
                    s.close()
                except Exception:
                    pass
                time.sleep(1.0)
                if callbacks and hasattr(callbacks, "on_start"):
                    callbacks.on_start(port, self.FALLBACK_BAUD_RATE, fw_info)
                success = self._execute_flash(port, self.FALLBACK_BAUD_RATE, erase_flash, target_chip, callbacks, progress_callback)
            else:
                raise FlashError(str(e))
        except FlashError:
            raise
        except Exception as e:
            raise FlashError(f"Flash execution failed: {e}")

        # Post-flash clean summary
        if success:
            ui.show_flash_success(port)

        return success

    def get_chip_info(self, port: Optional[str] = None) -> Dict[str, Any]:
        """Get ESP8266 chip information"""
        if port is None:
            port = self.auto_detect_port()

        py_cmd = [sys.executable]
        if sys.version_info >= (3, 11):
            py_cmd.append("-P")
        py_cmd.extend(["-m", "esptool"])

        cmd = py_cmd + [
            "--port", port,
            "--baud", str(self.FALLBACK_BAUD_RATE),
            "chip_id"
        ]

        safe_cwd = tempfile.gettempdir()
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=safe_cwd)
        if result.returncode != 0:
            cmd[-1] = "chip-id"
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=safe_cwd)
        if result.returncode != 0:
            cmd[-1] = "flash_id"
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=safe_cwd)

        if result.returncode != 0:
            raise FlashError(f"Failed to query chip info: {result.stderr or result.stdout}")

        output = (result.stdout or "") + "\n" + (result.stderr or "")
        detected_type = 'ESP32' if 'ESP32' in output else 'ESP8266'
        chip_info = {
            'port': port,
            'chip_type': detected_type,
            'raw_output': output
        }

        for line in output.splitlines():
            if 'Chip is' in line:
                chip_info['chip_model'] = line.split('Chip is')[-1].strip()
                if 'ESP32' in line:
                    chip_info['chip_type'] = 'ESP32'
                elif 'ESP8266' in line:
                    chip_info['chip_type'] = 'ESP8266'
            elif 'Chip ID:' in line:
                chip_info['chip_id'] = line.split(':')[-1].strip()
            elif 'MAC:' in line:
                chip_info['mac_address'] = line.split('MAC:')[-1].strip()
            elif 'Features:' in line:
                chip_info['features'] = line.split(':')[-1].strip()

        return chip_info

    def get_firmware_info(self, chip: str = "auto") -> Dict[str, Any]:
        """Get bundled firmware metadata"""
        fw_path = self._get_firmware_path(chip)
        target_name = "ESP32" if "esp32" in (chip or "").lower() else "ESP8266"
        flash_addr = "0x10000" if target_name == "ESP32" else "0x00000"

        if not os.path.exists(fw_path):
            raise FlashError(f"Firmware binary for {target_name} not found: {fw_path}")

        stat = os.stat(fw_path)

        return {
            'path': fw_path,
            'size': stat.st_size,
            'size_kb': round(stat.st_size / 1024, 1),
            'modified': time.ctime(stat.st_mtime),
            'version': __firmware_version__,
            'name': f'ESP-Linker Firmware ({target_name})',
            'target_board': f'{target_name} (Auto-detected)',
            'flash_address': flash_addr,
            'description': f'Universal wireless GPIO firmware with I2C, OTA updates, and real-time SSE events for {target_name}'
        }


# Backwards compatibility and modern alias
ESPFlasher = ESP8266Flasher


def flash_esp(port: Optional[str] = None,
              baud_rate: int = ESP8266Flasher.DEFAULT_BAUD_RATE,
              chip: str = "auto",
              erase_flash: bool = True,
              progress_callback: Optional[Callable] = None) -> bool:
    """Convenience function to flash ESP-Linker firmware to ESP8266 or ESP32"""
    flasher = ESP8266Flasher(chip=chip)
    return flasher.flash_firmware(
        port=port,
        baud_rate=baud_rate,
        chip=chip,
        erase_flash=erase_flash,
        progress_callback=progress_callback
    )


def flash_esp8266(port: Optional[str] = None,
                  baud_rate: int = ESP8266Flasher.DEFAULT_BAUD_RATE,
                  erase_flash: bool = True,
                  progress_callback: Optional[Callable] = None) -> bool:
    """Convenience function to flash ESP-Linker firmware"""
    return flash_esp(port=port, baud_rate=baud_rate, chip="esp8266", erase_flash=erase_flash, progress_callback=progress_callback)


def detect_esp8266() -> List[Dict[str, Any]]:
    """Detect connected ESP8266/ESP32 boards"""
    flasher = ESP8266Flasher()
    return flasher.detect_esp8266_ports()


def get_chip_info(port: Optional[str] = None) -> Dict[str, Any]:
    """Get ESP chip information"""
    flasher = ESP8266Flasher()
    return flasher.get_chip_info(port)
