"""
ESP-Linker Firmware Flasher
(c) 2025 SK Raihan / SKR Electronics Lab

Firmware flashing functionality using esptool for ESP8266 boards.
Includes bundled firmware, robust automatic port detection, real-time progress,
and automatic baud-rate fallback.
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

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False


class ProgressTracker:
    """Enhanced progress tracking with visual progress bars"""

    def __init__(self, use_progress_bar: bool = True):
        self.use_progress_bar = use_progress_bar and TQDM_AVAILABLE
        self.current_progress = None

    def start_operation(self, description: str, total: int = 100):
        """Start a new operation with progress tracking"""
        if self.use_progress_bar:
            self.current_progress = tqdm(
                total=total,
                desc=description,
                unit="%",
                bar_format="{desc}: {percentage:3.0f}%|{bar}| [{elapsed}<{remaining}]"
            )
        else:
            print(f"[*] {description}...")

    def update_to(self, percentage: int, message: Optional[str] = None):
        """Update progress bar to specific percentage"""
        if self.current_progress:
            delta = percentage - self.current_progress.n
            if delta > 0:
                self.current_progress.update(delta)
            if message:
                self.current_progress.set_description(message)
        elif message:
            print(f"[*] {message}")

    def finish_operation(self, success_message: str):
        """Finish current operation"""
        if self.current_progress:
            if self.current_progress.n < self.current_progress.total:
                self.current_progress.update(self.current_progress.total - self.current_progress.n)
            self.current_progress.close()
            self.current_progress = None
        print(f"[+] {success_message}")

    def simple_message(self, message: str):
        """Display a simple message"""
        print(message)


class ESP8266Flasher:
    """ESP8266 firmware flasher using esptool"""

    # Flash parameters
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
        # 1. Try standard pathlib lookup relative to module file
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

        # Common ESP USB-to-Serial identifiers
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
            # Skip built-in motherboard legacy ports
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

            # If it's a USB device, it might be an ESP board
            is_usb = "USB" in hwid_upper or "VID:PID" in hwid_upper

            esp_ports.append({
                'port': port.device,
                'description': port.description or "Unknown Serial Device",
                'hwid': port.hwid or "",
                'manufacturer': getattr(port, 'manufacturer', 'Unknown') or 'Unknown',
                'likely_esp': likely_esp,
                'is_usb': is_usb
            })

        # Sort: likely ESP first, then general USB ports
        esp_ports.sort(key=lambda x: (x['likely_esp'], x['is_usb']), reverse=True)
        return esp_ports

    def auto_detect_port(self) -> str:
        """
        Automatically detect ESP8266 port.

        Returns:
            Port name (e.g., 'COM3', '/dev/ttyUSB0')

        Raises:
            DeviceNotFoundError: If no suitable port found
        """
        ports = self.detect_esp8266_ports()

        if not ports:
            raise DeviceNotFoundError("No USB serial ports found. Please connect your ESP8266 board via USB.")

        # If any port matches our ESP identifiers
        for p in ports:
            if p['likely_esp']:
                return p['port']

        # If only one USB port is connected, pick it
        usb_ports = [p for p in ports if p['is_usb']]
        if len(usb_ports) == 1:
            return usb_ports[0]['port']

        # Otherwise, report available ports
        avail = [f"{p['port']} ({p['description']})" for p in ports]
        raise DeviceNotFoundError(
            f"Could not automatically identify ESP8266. Available ports: {', '.join(avail)}. "
            f"Please specify the port manually using --port <PORT>."
        )

    def _execute_flash(self, port: str, baud_rate: int, erase_flash: bool,
                       progress: ProgressTracker, progress_callback: Optional[Callable] = None) -> bool:
        """Execute esptool flash with real-time output parsing to prevent pipe deadlock"""
        # Determine esptool commands based on installed esptool
        # write-flash with --erase-all handles both erasing and writing in a single clean pass!
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

        progress.start_operation(f"Connecting to ESP8266 at {baud_rate} baud & flashing", total=100)

        # Launch process and read output in real-time
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

                # Check for progress percentage (e.g. "Writing at 0x00010000... (32 %)")
                match = percent_pattern.search(clean_line)
                if match:
                    pct = int(match.group(1))
                    progress.update_to(pct, f"Writing firmware: {pct}%")
                elif "Erasing flash" in clean_line:
                    progress.update_to(10, "Erasing flash memory...")
                elif "Connecting" in clean_line:
                    progress.update_to(5, "Connecting to board...")
                elif "Hash of data verified" in clean_line:
                    progress.update_to(100, "Verification complete!")

            process.stdout.close()
            process.wait()
        except Exception:
            process.kill()
            raise

        full_log = "".join(all_output)

        if process.returncode != 0:
            # Check for connection timeout
            if "Timed out waiting for packet header" in full_log or "Failed to connect" in full_log:
                raise TimeoutError(f"Connection timed out at {baud_rate} baud.\n{full_log}")
            raise FlashError(f"Flashing failed (code {process.returncode}):\n{full_log}")

        progress.finish_operation("Firmware flashed and verified successfully!")
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

        Args:
            port: Serial port (auto-detected if None)
            baud_rate: Flash baud rate (default: 460800)
            erase_flash: Whether to erase flash before flashing
            verify: Whether to verify flash after writing
            progress_callback: Callback function for progress updates
            use_progress_bar: Whether to use visual progress bars

        Returns:
            True if successful
        """
        progress = ProgressTracker(use_progress_bar)

        # Auto-detect port if not provided
        if port is None:
            progress.simple_message("[?] Auto-detecting ESP8266...")
            port = self.auto_detect_port()
            progress.simple_message(f"[^] Found ESP8266 on port: {port}")

        if not os.path.exists(self.firmware_path):
            raise FlashError(f"Firmware binary not found: {self.firmware_path}")

        firmware_size = os.path.getsize(self.firmware_path)
        progress.simple_message(f"[+] Firmware binary: {firmware_size:,} bytes ({firmware_size/1024:.1f} KB)")

        # Try flashing at requested baud rate
        try:
            return self._execute_flash(port, baud_rate, erase_flash, progress, progress_callback)
        except TimeoutError as e:
            # If high baud failed, try fallback rate
            if baud_rate != self.FALLBACK_BAUD_RATE:
                progress.simple_message(f"[!] High-speed baud rate ({baud_rate}) timed out.")
                progress.simple_message(f"[~] Retrying at safe baud rate ({self.FALLBACK_BAUD_RATE})...")
                time.sleep(1.0)
                return self._execute_flash(port, self.FALLBACK_BAUD_RATE, erase_flash, progress, progress_callback)
            raise FlashError(str(e))
        except FlashError:
            raise
        except Exception as e:
            raise FlashError(f"Flashing failed: {e}")

    def get_chip_info(self, port: Optional[str] = None) -> Dict[str, Any]:
        """
        Get ESP8266 chip information.

        Args:
            port: Serial port (auto-detected if None)

        Returns:
            Dictionary with chip information
        """
        if port is None:
            port = self.auto_detect_port()

        # Try chip-id or chip_id
        cmd = [
            sys.executable, "-m", "esptool",
            "--chip", "esp8266",
            "--port", port,
            "--baud", str(self.FALLBACK_BAUD_RATE),
            "chip-id"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # Fallback to legacy syntax
            cmd[-1] = "chip_id"
            result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise FlashError(f"Failed to get chip info: {result.stderr or result.stdout}")

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
        """Get information about the bundled firmware"""
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
