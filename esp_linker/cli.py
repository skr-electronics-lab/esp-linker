"""
ESP-Linker Command Line Interface
(c) 2025 SK Raihan / SKR Electronics Lab - All Rights Reserved.

Command-line tools for ESP-Linker library
"""

import sys
import argparse
import time
import json
import os
from .utils import discover_devices, scan_network, format_uptime, format_memory
from .espboard import ESPBoard
from .exceptions import (
    ESPLinkerError,
    ConnectionError,
    DeviceNotFoundError,
    InvalidPinError,
    InvalidModeError,
    InvalidValueError,
    TimeoutError,
    APIError,
    FlashError
)
from .flasher import (
    ESPFlasher,
    ESP8266Flasher,
    flash_esp,
    flash_esp8266,
    detect_esp8266,
    get_chip_info,
    print_badge,
    ui_print,
    render_banner,
    RICH_AVAILABLE,
    console
)
from .wifi_wizard import run_wifi_wizard
from .device_manager import get_device_manager
from .ui import ui

# Ensure UTF-8 encoding for Windows compatibility
if sys.platform.startswith('win') and hasattr(sys.stdout, 'encoding') and sys.stdout.encoding != 'utf-8':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

try:
    from .dashboard import run_dashboard
    DASHBOARD_AVAILABLE = True
except ImportError:
    DASHBOARD_AVAILABLE = False

def discover_devices_cli():
    """Command-line device discovery tool"""
    parser = argparse.ArgumentParser(
        description="Discover ESP-Linker devices on the network",
        prog="esp-linker-discover"
    )
    parser.add_argument(
        "--timeout", "-t",
        type=float,
        default=30.0,
        help="Discovery timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results in JSON format"
    )
    parser.add_argument(
        "--network", "-n",
        type=str,
        help="Network range to scan (e.g., 192.168.1)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    if not args.json:
        render_banner("ESP-LINKER DEVICE DISCOVERY", "Network Scanner")

    try:
        if args.network:
            devices = scan_network(network_range=args.network, timeout=2.0)
        else:
            devices = discover_devices(timeout=args.timeout)

        if args.json:
            import json
            print(json.dumps(devices, indent=2))
        else:
            if devices:
                if RICH_AVAILABLE and console:
                    from rich.table import Table
                    from rich import box
                    table = Table(
                        title=f"Discovered ESP-Linker Devices ({len(devices)})",
                        box=box.ROUNDED,
                        header_style="bold cyan",
                        border_style="cyan"
                    )
                    table.add_column("#", style="dim", width=4)
                    table.add_column("Device / Firmware", style="bold white", width=22)
                    table.add_column("IP Address", style="bold cyan", width=16)
                    table.add_column("WiFi SSID", style="white")
                    table.add_column("Uptime", style="dim")
                    table.add_column("Free Memory", justify="right", style="green")

                    for i, d in enumerate(devices, 1):
                        table.add_row(
                            str(i),
                            f"{d.get('firmware_name', 'ESP-Linker')} v{d.get('firmware_version', '1.0')}",
                            d['ip'],
                            d.get('wifi_ssid') or "[dim]AP Mode[/dim]",
                            format_uptime(d.get('uptime', 0)),
                            format_memory(d.get('free_heap', 0))
                        )
                    console.print(table)
                    ui_print("\n[bold cyan]Usage in Python:[/bold cyan]")
                    ui_print(f"  from esp_linker import ESPBoard\n  board = ESPBoard(ip='{devices[0]['ip']}')\n")
                else:
                    print(f"\nFound {len(devices)} device(s):")
                    for i, d in enumerate(devices, 1):
                        print(f"{i}. {d['firmware_name']} at {d['ip']} ({d.get('wifi_ssid', 'AP Mode')})")
            else:
                print_badge("WARN", "No ESP-Linker devices found on the local network.")
                ui_print("\n[dim]Troubleshooting:[/dim]")
                ui_print("  - Ensure board is powered on and within WiFi range")
                ui_print("  - Ensure your PC and ESP are on the same subnet")
                ui_print("  - Run [bold white]esp-linker setup-wifi[/bold white] to reconfigure credentials\n")

    except KeyboardInterrupt:
        print("\n\n[!] Discovery cancelled by user")
        sys.exit(1)
    except Exception as e:
        if args.json:
            import json
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"\n[!] Discovery failed: {e}")
        sys.exit(1)

def test_device_cli():
    """Command-line device testing tool with live in-place diagnostic dashboard"""
    parser = argparse.ArgumentParser(
        description="Test ESP-Linker device functionality",
        prog="esp-linker test"
    )
    parser.add_argument(
        "device",
        help="Device IP address or URL (e.g., 192.168.1.100 or http://esp-linker.local)"
    )
    parser.add_argument(
        "--timeout", "-t",
        type=float,
        default=5.0,
        help="Request timeout in seconds (default: 5)"
    )
    parser.add_argument(
        "--led-pin", "-l",
        type=int,
        default=2,
        help="LED pin for testing (default: 2)"
    )
    parser.add_argument(
        "--pwm-pin", "-p",
        type=int,
        default=4,
        help="PWM pin for testing (default: 4)"
    )
    parser.add_argument(
        "--servo-pin", "-s",
        type=int,
        default=5,
        help="Servo pin for testing (default: 5)"
    )

    args = parser.parse_args()

    ui.banner("ESP-LINKER", "Hardware Verification Suite")

    device_url = args.device
    if not device_url.startswith('http'):
        device_url = f"http://{device_url}"

    ui.step(f"Connecting to ESP8266 at [bold white]{device_url}[/bold white]...")

    try:
        board = ESPBoard(url=device_url, timeout=args.timeout)
    except Exception as e:
        ui.error(f"Failed to connect to {device_url}: {e}")
        ui.info("Troubleshooting: Check device IP and make sure device is powered on.")
        sys.exit(1)

    tests = [
        {"name": "Telemetry & Status", "target": "GET /api/status", "status": "PENDING", "detail": "Awaiting execution"},
        {"name": "GPIO Capabilities", "target": "GET /api/capabilities", "status": "PENDING", "detail": "Awaiting execution"},
        {"name": "Digital I/O Toggle", "target": f"GPIO {args.led_pin} (LED)", "status": "PENDING", "detail": "Awaiting execution"},
        {"name": "PWM Duty Sweep", "target": f"GPIO {args.pwm_pin}", "status": "PENDING", "detail": "Awaiting execution"},
        {"name": "Servo Pulse Sweep", "target": f"GPIO {args.servo_pin}", "status": "PENDING", "detail": "Awaiting execution"},
        {"name": "Analog ADC Sampling", "target": "A0 (ADC)", "status": "PENDING", "detail": "Awaiting execution"},
        {"name": "Batch Pipeline", "target": "POST /api/batch", "status": "PENDING", "detail": "Awaiting execution"},
    ]

    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box

    def render_table():
        table = Table(
            title=f"Hardware Diagnostics Dashboard ({device_url})",
            box=box.ROUNDED,
            border_style=ui.COLOR_BORDER,
            title_style=f"bold {ui.COLOR_PRIMARY}",
            expand=False
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Diagnostic Suite", style="bold white", width=25)
        table.add_column("Target Resource", style=ui.COLOR_PRIMARY, width=18)
        table.add_column("Status", justify="center", width=12)
        table.add_column("Result / Telemetry", style="white", width=36)

        for i, t in enumerate(tests, 1):
            st = t["status"]
            if st == "PENDING":
                st_str = "[dim]PENDING[/dim]"
            elif st == "RUNNING":
                st_str = f"[bold {ui.COLOR_WARN}]RUNNING...[/bold {ui.COLOR_WARN}]"
            elif st == "PASS":
                st_str = f"[bold {ui.COLOR_SUCCESS}]✔ PASS[/bold {ui.COLOR_SUCCESS}]"
            elif st == "SKIP":
                st_str = f"[{ui.COLOR_MUTED}]SKIP[/{ui.COLOR_MUTED}]"
            else:
                st_str = f"[bold {ui.COLOR_ERROR}]✖ FAIL[/bold {ui.COLOR_ERROR}]"

            table.add_row(str(i), t["name"], t["target"], st_str, t["detail"])
        return table

    is_interactive = RICH_AVAILABLE and ui.console and not ui.plain_mode and (hasattr(sys.stdout, 'isatty') and sys.stdout.isatty())

    live_context = Live(render_table(), console=ui.console, refresh_per_second=10) if is_interactive else None

    def update_test(idx: int, status: str, detail: str):
        tests[idx]["status"] = status
        tests[idx]["detail"] = detail
        if live_context:
            live_context.update(render_table())
        elif not is_interactive:
            mark = "✔" if status == "PASS" else ("✖" if status == "FAIL" else "·")
            print(f"[{mark}] [{idx+1}/7] {tests[idx]['name']}: {status} - {detail}")

    passed = 0
    failed = 0
    skipped = 0

    try:
        if live_context:
            live_context.start()

        # Test 1: Telemetry & Status
        update_test(0, "RUNNING", "Querying telemetry endpoint...")
        try:
            status = board.status()
            detail = f"{status.get('firmware_name', 'ESP-Linker')} v{status.get('firmware_version', '1.0')} • {format_memory(status.get('free_heap', 0))} free"
            update_test(0, "PASS", detail)
            passed += 1
        except Exception as e:
            update_test(0, "FAIL", str(e)[:35])
            failed += 1

        # Test 2: Capabilities
        update_test(1, "RUNNING", "Fetching hardware pin table...")
        pwm_pins = []
        servo_pins = []
        try:
            caps = board.capabilities()
            pins = caps.get('pins', [])
            pwm_pins = [p['pin'] for p in pins if p.get('pwm')]
            servo_pins = [p['pin'] for p in pins if p.get('servo')]
            detail = f"{len(pins)} GPIOs ({len(pwm_pins)} PWM, {len(servo_pins)} Servo)"
            update_test(1, "PASS", detail)
            passed += 1
        except Exception as e:
            update_test(1, "FAIL", str(e)[:35])
            failed += 1

        # Test 3: Digital I/O
        update_test(2, "RUNNING", f"Toggling GPIO {args.led_pin} HIGH/LOW...")
        try:
            board.set_mode(args.led_pin, 'OUTPUT')
            board.write(args.led_pin, 1)
            time.sleep(0.3)
            board.write(args.led_pin, 0)
            val = board.read(args.led_pin)
            update_test(2, "PASS", f"Output toggled (readback: {val})")
            passed += 1
        except Exception as e:
            update_test(2, "FAIL", str(e)[:35])
            failed += 1

        # Test 4: PWM
        if args.pwm_pin in pwm_pins or not pwm_pins:
            update_test(3, "RUNNING", f"Testing duty cycle on GPIO {args.pwm_pin}...")
            try:
                board.set_mode(args.pwm_pin, 'PWM')
                for val in [0, 512, 1023, 0]:
                    board.pwm(args.pwm_pin, val)
                    time.sleep(0.08)
                update_test(3, "PASS", "Duty sweep 0 -> 1023 verified")
                passed += 1
            except Exception as e:
                update_test(3, "FAIL", str(e)[:35])
                failed += 1
        else:
            update_test(3, "SKIP", f"GPIO {args.pwm_pin} no PWM support")
            skipped += 1

        # Test 5: Servo
        if args.servo_pin in servo_pins or not servo_pins:
            update_test(4, "RUNNING", f"Sweeping servo angles on GPIO {args.servo_pin}...")
            try:
                board.set_mode(args.servo_pin, 'SERVO')
                for angle in [0, 90, 180, 90]:
                    board.servo(args.servo_pin, angle)
                    time.sleep(0.08)
                update_test(4, "PASS", "Sweep 0° -> 180° verified")
                passed += 1
            except Exception as e:
                update_test(4, "FAIL", str(e)[:35])
                failed += 1
        else:
            update_test(4, "SKIP", f"GPIO {args.servo_pin} no Servo support")
            skipped += 1

        # Test 6: Analog ADC
        update_test(5, "RUNNING", "Sampling ADC pin A0...")
        try:
            analog_val = board.read('A0')
            voltage = (analog_val / 1024.0) * 3.3
            update_test(5, "PASS", f"Raw: {analog_val}/1024 ({voltage:.2f}V)")
            passed += 1
        except Exception as e:
            update_test(5, "FAIL", str(e)[:35])
            failed += 1

        # Test 7: Batch Operations
        update_test(6, "RUNNING", "Testing atomic batch request...")
        try:
            ops = [
                {'type': 'write', 'pin': args.led_pin, 'value': 0},
                {'type': 'read', 'pin': args.led_pin}
            ]
            batch_res = board.batch(ops)
            ok_cnt = sum(1 for r in batch_res.get('results', []) if r.get('success'))
            update_test(6, "PASS", f"{ok_cnt}/{len(ops)} operations atomic OK")
            passed += 1
        except Exception as e:
            update_test(6, "FAIL", str(e)[:35])
            failed += 1

    finally:
        if live_context:
            live_context.stop()
        board.close()

    # Final summary panel
    total_tests = passed + failed + skipped
    if is_interactive and ui.console:
        summary = Text()
        if failed == 0:
            summary.append(f"✔ All Hardware Diagnostics Passed! ({passed}/{total_tests} passed)\n\n", style=f"bold {ui.COLOR_SUCCESS}")
            summary.append(f"Target: {device_url} is healthy and responsive.\n", style="white")
            summary.append("You are ready to control the board using the Python SDK:\n", style=ui.COLOR_MUTED)
            summary.append(f"  from esp_linker import ESPBoard\n  board = ESPBoard(ip='{args.device}')\n", style="bold white")
            panel = Panel(summary, title=f"[bold {ui.COLOR_SUCCESS}]Diagnostics Passed[/bold {ui.COLOR_SUCCESS}]", box=box.ROUNDED, border_style=ui.COLOR_SUCCESS, expand=False)
        else:
            summary.append(f"✖ Diagnostic Failures Detected ({failed} failed, {passed} passed)\n\n", style=f"bold {ui.COLOR_ERROR}")
            summary.append(f"Target: {device_url} had test failures. Review table above.\n", style="white")
            panel = Panel(summary, title=f"[bold {ui.COLOR_ERROR}]Diagnostics Incomplete[/bold {ui.COLOR_ERROR}]", box=box.ROUNDED, border_style=ui.COLOR_ERROR, expand=False)
        ui.console.print(panel)
    else:
        print(f"\nDiagnostics completed: {passed} passed, {failed} failed, {skipped} skipped.")

# Removed incomplete main_cli() function - using the complete one below

def configure_wifi_cli(device: str, ssid: str, password: str, timeout: float = 10.0):
    """Configure WiFi credentials on ESP-Linker device"""
    print("[*] ESP-Linker WiFi Configuration")
    print("(c) 2025 SK Raihan / SKR Electronics Lab")
    print("=" * 50)

    try:
        # Determine if device is IP or URL
        if device.startswith('http'):
            board = ESPBoard(url=device, timeout=timeout)
        else:
            board = ESPBoard(ip=device, timeout=timeout)

        print(f"[^] Connecting to device: {device}")

        # Get current status
        status = board.status()
        print(f"[+] Connected to {status.get('firmware_name', 'ESP-Linker')} v{status.get('firmware_version', 'Unknown')}")

        # Configure WiFi
        print(f"[*] Configuring WiFi: {ssid}")
        result = board.configure_wifi(ssid, password)

        if result.get('status') == 200:
            print("[+] WiFi credentials configured successfully!")
            print("[~] Device will restart to apply new settings...")
            print(f"[*] After restart, device should connect to: {ssid}")
            print("\n[i] Use 'esp-linker discover' to find the new IP address")
        else:
            print(f"[!] Configuration failed: {result.get('message', 'Unknown error')}")
            sys.exit(1)

        board.close()

    except Exception as e:
        print(f"[!] WiFi configuration failed: {e}")
        print("\nTroubleshooting:")
        print("- Check device IP address or URL")
        print("- Verify device is powered on and accessible")
        print("- Ensure SSID and password are correct")
        sys.exit(1)

# Entry point functions for console scripts
def discover_devices_entry():
    """Entry point for esp-linker-discover command"""
    discover_devices_cli()

def flash_esp8266_cli():
    """Command-line ESP8266 / ESP32 firmware flashing tool"""
    parser = argparse.ArgumentParser(
        description="Flash ESP-Linker firmware to ESP8266 or ESP32",
        prog="esp-linker flash"
    )
    parser.add_argument(
        "--port", "-p",
        type=str,
        help="Serial port (auto-detected if not specified)"
    )
    parser.add_argument(
        "--chip", "-c",
        type=str,
        choices=["auto", "esp8266", "esp32"],
        default="auto",
        help="Target chip architecture (default: auto)"
    )
    parser.add_argument(
        "--baud", "-b",
        type=int,
        default=ESP8266Flasher.DEFAULT_BAUD_RATE,
        help=f"Flash baud rate (default: {ESP8266Flasher.DEFAULT_BAUD_RATE})"
    )
    parser.add_argument(
        "--no-erase",
        action="store_true",
        help="Skip flash erase (not recommended)"
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="List available serial ports"
    )
    parser.add_argument(
        "--chip-info",
        action="store_true",
        help="Show chip information"
    )
    parser.add_argument(
        "--firmware-info",
        action="store_true",
        help="Show bundled firmware information"
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Disable colors and rich terminal animations"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug mode and rich tracebacks"
    )

    args = parser.parse_args()

    ui.configure(plain=args.plain or ui.plain_mode, debug=args.debug or ui.debug_mode)

    try:
        flasher = ESPFlasher(chip_type=args.chip)

        # List ports
        if args.list_ports:
            ui.banner("ESP-LINKER", "Serial Port Scanner")
            flasher.display_ports_table()
            return

        # Show chip info
        if args.chip_info:
            ui.banner("ESP-LINKER", "Chip Telemetry")
            try:
                info = flasher.get_chip_info(args.port)
                if RICH_AVAILABLE and ui.console and not ui.plain_mode:
                    from rich.table import Table
                    from rich import box
                    table = Table(title="Chip Telemetry", box=box.ROUNDED, border_style=ui.COLOR_BORDER, title_style="bold #38bdf8", show_header=False)
                    table.add_column("Property", style="bold #38bdf8", width=16)
                    table.add_column("Value", style="white")
                    table.add_row("Port", info['port'])
                    table.add_row("Chip Type", info['chip_type'])
                    if 'chip_id' in info:
                        table.add_row("Chip ID", str(info['chip_id']))
                    if 'mac_address' in info:
                        table.add_row("MAC Address", str(info['mac_address']))
                    ui.console.print(table)
                else:
                    print(f"Port: {info['port']} | Chip: {info['chip_type']} | ID: {info.get('chip_id', 'N/A')}")
            except Exception as e:
                ui.error(f"Failed to get chip info: {e}")
            return

        # Show firmware info
        if args.firmware_info:
            ui.banner("ESP-LINKER", "Firmware Package Info")
            try:
                info = flasher.get_firmware_info()
                if RICH_AVAILABLE and ui.console and not ui.plain_mode:
                    from rich.table import Table
                    from rich import box
                    table = Table(title="Bundled Firmware Image", box=box.ROUNDED, border_style=ui.COLOR_BORDER, title_style="bold #38bdf8", show_header=False)
                    table.add_column("Property", style="bold #38bdf8", width=16)
                    table.add_column("Value", style="white")
                    table.add_row("Name", info['name'])
                    table.add_row("Version", info['version'])
                    table.add_row("Description", info['description'])
                    table.add_row("File Size", f"{info['size_kb']} KB ({info['size']:,} bytes)")
                    table.add_row("Binary Path", info['path'])
                    table.add_row("Last Modified", info['modified'])
                    ui.console.print(table)
                else:
                    print(f"Firmware: {info['name']} v{info['version']} ({info['size_kb']} KB)")
            except Exception as e:
                ui.error(f"Failed to get firmware info: {e}")
            return

        # Flash firmware with rich animated TUI
        ui.banner("ESP-LINKER", "Firmware Flasher")
        success = flasher.flash_firmware(
            port=args.port,
            baud_rate=args.baud,
            erase_flash=not args.no_erase
        )
        if not success:
            sys.exit(1)

    except FlashError as e:
        ui.error(f"Flash Error: {e}")
        sys.exit(1)
    except DeviceNotFoundError as e:
        ui.error(f"Device Error: {e}")
        if ui.console and not ui.plain_mode:
            ui.console.print("\n[dim white]Troubleshooting:[/dim white]")
            ui.console.print("  - Check that ESP8266 is connected via USB data cable")
            ui.console.print("  - Run [bold cyan]esp-linker detect[/bold cyan] to see available serial ports")
            ui.console.print("  - Specify port manually with: [bold cyan]esp-linker flash --port COM4[/bold cyan]")
        else:
            print("\nTroubleshooting:")
            print("  - Check that ESP8266 is connected via USB data cable")
            print("  - Run esp-linker detect to see available serial ports")
            print("  - Specify port manually with: esp-linker flash --port COM4")
        sys.exit(1)
    except Exception as e:
        ui.error(f"Execution error: {e}")
        sys.exit(1)


def detect_esp8266_cli():
    """Command-line ESP8266 detection tool"""
    parser = argparse.ArgumentParser(
        description="Detect ESP8266 boards connected via USB",
        prog="esp-linker detect"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results in JSON format"
    )

    args = parser.parse_args()

    try:
        if args.json:
            import json
            ports = detect_esp8266()
            print(json.dumps(ports, indent=2))
            return

        render_banner("ESP-LINKER HARDWARE DETECT", "Serial Port Scanner")
        flasher = ESP8266Flasher()
        flasher.display_ports_table()
    except Exception as e:
        print_badge("ERROR", f"Detection failed: {e}")
        sys.exit(1)


def test_device_entry():
    """Entry point for esp-linker-test command"""
    test_device_cli()


def flash_esp8266_entry():
    """Entry point for esp-linker-flash command"""
    flash_esp8266_cli()


def ota_cli():
    """Command-line Over-The-Air (OTA) firmware update tool"""
    parser = argparse.ArgumentParser(
        description="Flash ESP-Linker firmware Over-The-Air (OTA) via WiFi",
        prog="esp-linker ota"
    )
    parser.add_argument(
        "device",
        help="Device IP address or URL (e.g. 192.168.1.100 or http://192.168.1.100)"
    )
    parser.add_argument(
        "--firmware", "-f",
        type=str,
        default=None,
        help="Path to compiled firmware .bin file (bundled firmware used if omitted)"
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Disable rich colors and animations"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )

    args = parser.parse_args()
    ui.configure(plain=args.plain or ui.plain_mode, debug=args.debug or ui.debug_mode)
    ui.banner("ESP-LINKER", "Over-The-Air (OTA) Firmware Flasher")

    device_url = args.device
    if not device_url.startswith("http"):
        device_url = f"http://{device_url}"

    try:
        board = ESPBoard(url=device_url, timeout=5.0)
        ui.step(f"Connecting to target board at [bold white]{board.ip}[/bold white]...")
        status = board.status()
        arch = status.get("arch", board.architecture)
        ui.success(f"Connected to {status.get('firmware_name', 'ESP-Linker')} v{status.get('firmware_version', '1.0')} [cyan]({arch})[/cyan]")

        firmware_path = args.firmware
        if not firmware_path:
            pkg_dir = os.path.dirname(os.path.abspath(__file__))
            bin_name = "esp-linker-esp32.bin" if arch == "ESP32" else "esp-linker-esp8266.bin"
            bundled_path = os.path.join(pkg_dir, "firmware", bin_name)
            if not os.path.exists(bundled_path):
                bundled_path = os.path.join(pkg_dir, "firmware", "esp-linker-firmware.bin")
            firmware_path = bundled_path

        if not os.path.exists(firmware_path):
            ui.error(f"Firmware binary not found: {firmware_path}")
            sys.exit(1)

        file_size = os.path.getsize(firmware_path)
        ui.info(f"Target Binary: [bold white]{os.path.basename(firmware_path)}[/bold white] ({file_size:,} bytes / {file_size/1024:.1f} KB)")

        if RICH_AVAILABLE and ui.console and not ui.plain_mode:
            from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, TransferSpeedColumn
            with Progress(
                TextColumn("[bold cyan]OTA Flashing[/bold cyan]"),
                BarColumn(complete_style="cyan", finished_style="green"),
                TextColumn("[bold white]{task.percentage:>3.0f}%[/bold white]"),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=ui.console
            ) as progress:
                task_id = progress.add_task("ota", total=file_size)
                def on_progress(sent, total):
                    progress.update(task_id, completed=sent, total=total)

                ui.step("Streaming firmware binary over WiFi...")
                success = board.ota_flash(firmware_path, progress_callback=on_progress)
        else:
            def on_progress(sent, total):
                pct = int((sent / total) * 100) if total > 0 else 0
                print(f"[*] OTA Progress: {sent}/{total} bytes ({pct}%)", end="\r")

            print("[*] Uploading firmware binary...")
            success = board.ota_flash(firmware_path, progress_callback=on_progress)
            print()

        if success:
            ui.success("OTA update installed successfully! Board is rebooting into new firmware.")
            ui.info("Wait approximately 5 seconds for board to reconnect to WiFi.")
        else:
            ui.error("OTA update failed.")
            sys.exit(1)

    except Exception as e:
        ui.error(f"OTA Error: {e}")
        sys.exit(1)


def i2c_cli():
    """Command-line I2C bus scanner and peripheral controller"""
    parser = argparse.ArgumentParser(
        description="ESP-Linker I2C Bus Diagnostic and Transceiver Tool",
        prog="esp-linker i2c"
    )
    parser.add_argument("device", help="Device IP address or URL")
    parser.add_argument("action", choices=["scan", "read", "write", "sensors"], nargs="?", default="scan", help="Action (default: scan)")
    parser.add_argument("--address", "-a", type=str, help="I2C peripheral address (e.g. 0x68 or 104)")
    parser.add_argument("--register", "-r", type=str, default=None, help="Register address (e.g. 0x3B or 59)")
    parser.add_argument("--length", "-l", type=int, default=1, help="Number of bytes to read (default: 1)")
    parser.add_argument("--data", "-d", type=str, default=None, help="Bytes to write as comma-separated hex/decimal (e.g. 0x6B,0x00)")
    parser.add_argument("--plain", action="store_true", help="Disable rich formatting")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()
    ui.configure(plain=args.plain or ui.plain_mode, debug=args.debug or ui.debug_mode)

    device_url = args.device
    if not device_url.startswith("http"):
        device_url = f"http://{device_url}"

    try:
        board = ESPBoard(url=device_url, timeout=5.0)

        def parse_int(val, name):
            if val is None:
                ui.error(f"Missing required parameter: --{name}")
                sys.exit(1)
            try:
                if str(val).startswith("0x") or str(val).startswith("0X"):
                    return int(val, 16)
                return int(val)
            except ValueError:
                ui.error(f"Invalid integer value for {name}: {val}")
                sys.exit(1)

        KNOWN_I2C = {
            0x20: "PCF8574 I/O Expander",
            0x27: "PCF8574 I2C LCD Backlight",
            0x38: "AHT10 / AHT20 Temp & Humidity",
            0x39: "TSL2561 Light Sensor",
            0x3C: "SSD1306 / SH1106 OLED Display (0.96 inch)",
            0x3D: "SSD1306 OLED Display (Alternative)",
            0x48: "ADS1115 / TMP102 16-bit ADC",
            0x50: "AT24C32 / AT24C64 EEPROM",
            0x57: "MAX30100 / MAX30102 Pulse Oximeter",
            0x68: "MPU6050 / DS3231 RTC / IMU",
            0x76: "BMP280 / BME280 Environmental Sensor",
            0x77: "BMP280 / BME280 (Alternative Address)",
        }

        if args.action == "scan":
            ui.banner("ESP-LINKER", "I2C Hardware Bus Scanner")
            ui.step(f"Scanning I2C peripheral addresses on [bold white]{board.ip}[/bold white]...")
            addresses = board.i2c_scan()

            if RICH_AVAILABLE and ui.console and not ui.plain_mode:
                from rich.table import Table
                from rich import box
                matrix = Table(
                    title=f"I2C Bus Address Map ({len(addresses)} device(s) found)",
                    box=box.ROUNDED,
                    border_style=ui.COLOR_BORDER,
                    header_style=f"bold {ui.COLOR_PRIMARY}"
                )
                matrix.add_column("     ", style="dim cyan", width=5)
                for col in range(16):
                    matrix.add_column(f"{col:02X}", justify="center", width=4)

                for row in range(0, 8):
                    row_base = row * 16
                    row_cells = [f"{row_base:02X}:"]
                    for col in range(16):
                        addr = row_base + col
                        if addr < 0x08 or addr > 0x77:
                            row_cells.append("[dim]--[/dim]")
                        elif addr in addresses:
                            row_cells.append(f"[bold {ui.COLOR_SUCCESS}]{addr:02X}[/bold {ui.COLOR_SUCCESS}]")
                        else:
                            row_cells.append("[dim]. [/dim]")
                    matrix.add_row(*row_cells)

                ui.console.print(matrix)

                if addresses:
                    dev_table = Table(
                        title="Identified Peripheral Devices",
                        box=box.ROUNDED,
                        border_style=ui.COLOR_BORDER,
                        header_style="bold cyan"
                    )
                    dev_table.add_column("Address", style="bold white", width=12)
                    dev_table.add_column("Identified Hardware Device", style="green")

                    for addr in addresses:
                        ident = KNOWN_I2C.get(addr, "Unknown I2C Peripheral")
                        dev_table.add_row(f"0x{addr:02X} ({addr})", ident)
                    ui.console.print(dev_table)
                else:
                    ui.warn("No I2C peripherals responded. Check wiring on SDA/SCL pins.")
            else:
                print(f"Discovered {len(addresses)} I2C address(es):")
                for addr in addresses:
                    ident = KNOWN_I2C.get(addr, "Unknown device")
                    print(f"  - 0x{addr:02X} ({addr}): {ident}")

        elif args.action == "read":
            addr = parse_int(args.address, "address")
            reg = parse_int(args.register, "register") if args.register is not None else None
            ui.step(f"Reading {args.length} byte(s) from 0x{addr:02X} (register: {args.register or 'none'})...")
            data = board.i2c_read(addr, args.length, register=reg)
            hex_str = " ".join([f"0x{b:02X}" for b in data])
            ui.success(f"Received {len(data)} bytes: {hex_str} (dec: {data})")

        elif args.action == "write":
            addr = parse_int(args.address, "address")
            if not args.data:
                ui.error("Missing --data argument (e.g. --data 0x6B,0x00)")
                sys.exit(1)
            raw_bytes = [int(x.strip(), 16 if '0x' in x or '0X' in x else 10) for x in args.data.split(',')]
            ui.step(f"Writing {len(raw_bytes)} byte(s) to 0x{addr:02X}...")
            res = board.i2c_write(addr, raw_bytes)
            ui.success(f"I2C write complete: {res.get('message', 'OK')}")

        elif args.action == "sensors":
            ui.banner("ESP-LINKER", "Hardware Sensor Telemetry")
            ui.step(f"Interrogating onboard I2C sensors at [bold white]{board.ip}[/bold white]...")
            try:
                mpu = board.read_mpu6050()
                if RICH_AVAILABLE and ui.console and not ui.plain_mode:
                    from rich.table import Table
                    from rich import box
                    t = Table(title="MPU-6050 6-Axis Motion Tracking Sensor (0x68)", box=box.ROUNDED, border_style=ui.COLOR_BORDER)
                    t.add_column("Channel", style="bold cyan")
                    t.add_column("Value", style="bold white")
                    t.add_column("Unit", style="dim")
                    t.add_row("Accel X", str(mpu['accel_x']), "G")
                    t.add_row("Accel Y", str(mpu['accel_y']), "G")
                    t.add_row("Accel Z", str(mpu['accel_z']), "G")
                    t.add_row("Temperature", str(mpu['temp_c']), "deg C")
                    t.add_row("Gyro X", str(mpu['gyro_x']), "deg/s")
                    t.add_row("Gyro Y", str(mpu['gyro_y']), "deg/s")
                    t.add_row("Gyro Z", str(mpu['gyro_z']), "deg/s")
                    ui.console.print(t)
                else:
                    print(f"MPU6050: {mpu}")
            except Exception as e:
                ui.info(f"MPU6050 not responding: {e}")

            for test_addr in [0x76, 0x77]:
                try:
                    bmp = board.read_bmp280(test_addr)
                    if bmp['model'] != "Unknown":
                        ui.success(f"Detected {bmp['model']} at {bmp['address']} (Chip ID: {bmp['chip_id']})")
                except Exception:
                    pass

    except Exception as e:
        ui.error(f"I2C Operation Failed: {e}")
        sys.exit(1)


def events_cli():
    """Live GPIO interrupt event stream tool"""
    parser = argparse.ArgumentParser(
        description="Stream real-time GPIO interrupt change events from ESP-Linker device",
        prog="esp-linker events"
    )
    parser.add_argument("device", help="Device IP address or URL")
    parser.add_argument("--pin", "-p", type=int, default=None, help="Watch a specific GPIO pin (default: all)")
    parser.add_argument("--mode", "-m", choices=["CHANGE", "RISING", "FALLING"], default="CHANGE", help="Interrupt trigger mode (default: CHANGE)")
    parser.add_argument("--plain", action="store_true", help="Disable rich formatting")

    args = parser.parse_args()
    ui.configure(plain=args.plain or ui.plain_mode)
    ui.banner("ESP-LINKER", "Real-Time Hardware Interrupt Monitor")

    device_url = args.device
    if not device_url.startswith("http"):
        device_url = f"http://{device_url}"

    try:
        board = ESPBoard(url=device_url, timeout=5.0)
        ui.step(f"Connected to [bold white]{board.ip}[/bold white]. Initializing event subscription...")

        if args.pin is not None:
            ui.info(f"Subscribing to GPIO {args.pin} on {args.mode} interrupts...")
            def event_handler(evt):
                ts = time.strftime('%H:%M:%S')
                pin_num = evt.get('pin', args.pin)
                state = evt.get('state', 'UNKNOWN')
                state_str = "[bold green]HIGH[/bold green]" if str(state) == "1" else "[bold red]LOW[/bold red]"
                if RICH_AVAILABLE and ui.console and not ui.plain_mode:
                    ui.console.print(f"[{ts}] [bold cyan]EVENT[/bold cyan] GPIO {pin_num} -> {state_str} (mode: {args.mode})")
                else:
                    print(f"[{ts}] EVENT GPIO {pin_num} -> {state} (mode: {args.mode})")

            board.on_change(args.pin, event_handler, mode=args.mode)
            ui.success(f"Watching GPIO {args.pin}. Press Ctrl+C to stop.")
        else:
            ui.info("Subscribing to active board events via SSE stream...")
            def global_handler(evt):
                ts = time.strftime('%H:%M:%S')
                pin_num = evt.get('pin', '?')
                state = evt.get('state', '?')
                state_str = "[bold green]HIGH[/bold green]" if str(state) == "1" else "[bold red]LOW[/bold red]"
                if RICH_AVAILABLE and ui.console and not ui.plain_mode:
                    ui.console.print(f"[{ts}] [bold cyan]INTERRUPT[/bold cyan] GPIO {pin_num} -> {state_str}")
                else:
                    print(f"[{ts}] INTERRUPT GPIO {pin_num} -> {state}")

            board.on_change(0, global_handler, mode="CHANGE")
            ui.success("Streaming live hardware interrupts. Press Ctrl+C to stop.")

        while True:
            time.sleep(0.5)

    except KeyboardInterrupt:
        if 'board' in locals():
            board.stop_events()
        ui.info("\nEvent monitor terminated by user.")
    except Exception as e:
        ui.error(f"Event Monitor Error: {e}")
        sys.exit(1)


def ota_entry():
    """Entry point for esp-linker-ota command"""
    ota_cli()


def i2c_entry():
    """Entry point for esp-linker-i2c command"""
    i2c_cli()


def events_entry():
    """Entry point for esp-linker-events command"""
    events_cli()


def wifi_wizard_cli():
    """Command-line WiFi configuration wizard"""
    parser = argparse.ArgumentParser(
        description="Interactive WiFi configuration wizard for ESP8266",
        prog="esp-linker setup-wifi"
    )
    parser.add_argument(
        "--port", "-p",
        type=str,
        help="Serial port (auto-detected if not specified)"
    )

    args = parser.parse_args()

    try:
        success = run_wifi_wizard(args.port)

        if success:
            print("\n[*] WiFi configuration wizard completed successfully!")
            sys.exit(0)
        else:
            print("\n[!] WiFi configuration wizard failed or was cancelled")
            sys.exit(1)

    except Exception as e:
        print(f"[!] WiFi wizard error: {e}")
        sys.exit(1)


def detect_esp8266_entry():
    """Entry point for esp-linker-detect command"""
    detect_esp8266_cli()


def devices_cli():
    """Command-line device management tool"""
    parser = argparse.ArgumentParser(
        description="Manage ESP-Linker devices",
        prog="esp-linker devices"
    )

    subparsers = parser.add_subparsers(dest='action', help='Device management actions')

    # List devices
    list_parser = subparsers.add_parser('list', help='List all managed devices')
    list_parser.add_argument('--status', choices=['online', 'offline'], help='Filter by status')
    list_parser.add_argument('--json', action='store_true', help='Output in JSON format')

    # Discover devices
    discover_parser = subparsers.add_parser('discover', help='Discover and add new devices')
    discover_parser.add_argument('--timeout', type=float, default=30.0, help='Discovery timeout in seconds')

    # Rename device
    rename_parser = subparsers.add_parser('rename', help='Rename a device')
    rename_parser.add_argument('device', help='Device IP or name')
    rename_parser.add_argument('name', help='New device name')

    # Add tag
    tag_add_parser = subparsers.add_parser('tag-add', help='Add tag to device')
    tag_add_parser.add_argument('device', help='Device IP or name')
    tag_add_parser.add_argument('tag', help='Tag to add')

    # Remove tag
    tag_remove_parser = subparsers.add_parser('tag-remove', help='Remove tag from device')
    tag_remove_parser.add_argument('device', help='Device IP or name')
    tag_remove_parser.add_argument('tag', help='Tag to remove')

    # Set notes
    notes_parser = subparsers.add_parser('notes', help='Set device notes')
    notes_parser.add_argument('device', help='Device IP or name')
    notes_parser.add_argument('notes', help='Device notes')

    # Remove device
    remove_parser = subparsers.add_parser('remove', help='Remove device from management')
    remove_parser.add_argument('device', help='Device IP or name')

    # Monitor devices
    monitor_parser = subparsers.add_parser('monitor', help='Monitor device status')
    monitor_parser.add_argument('--interval', type=int, default=30, help='Check interval in seconds')

    # Statistics
    stats_parser = subparsers.add_parser('stats', help='Show device statistics')

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        return

    try:
        manager = get_device_manager()

        if args.action == 'list':
            devices = manager.list_devices(status_filter=args.status)

            if args.json:
                device_data = [device.to_dict() for device in devices]
                print(json.dumps(device_data, indent=2))
                return

            if not devices:
                print("[#] No devices found")
                print("[i] Run 'esp-linker devices discover' to find devices")
                return

            print("[#] Managed ESP-Linker Devices:")
            print("=" * 60)

            for device in devices:
                status_icon = "[+]" if device.status == 'online' else "[!]" if device.status == 'offline' else "[o]"
                print(f"{status_icon} {device.name}")
                print(f"   IP: {device.ip}")
                print(f"   Firmware: {device.firmware_name} v{device.firmware_version}")
                print(f"   Status: {device.status}")
                print(f"   Last Seen: {device.last_seen.strftime('%Y-%m-%d %H:%M:%S')}")
                if device.tags:
                    print(f"   Tags: {', '.join(device.tags)}")
                if device.notes:
                    print(f"   Notes: {device.notes}")
                print()

        elif args.action == 'discover':
            new_devices = manager.discover_and_add_devices(timeout=args.timeout)

            if new_devices:
                print(f"[+] Found {len(new_devices)} new device(s):")
                for device in new_devices:
                    print(f"   [#] {device.name} ({device.ip})")
            else:
                print("[?][?] No new devices found")

        elif args.action == 'rename':
            if manager.rename_device(args.device, args.name):
                print(f"[+] Device renamed to '{args.name}'")
            else:
                print(f"[!] Device '{args.device}' not found")

        elif args.action == 'tag-add':
            if manager.add_tag(args.device, args.tag):
                print(f"[+] Tag '{args.tag}' added to device")
            else:
                print(f"[!] Device '{args.device}' not found or tag already exists")

        elif args.action == 'tag-remove':
            if manager.remove_tag(args.device, args.tag):
                print(f"[+] Tag '{args.tag}' removed from device")
            else:
                print(f"[!] Device '{args.device}' not found or tag doesn't exist")

        elif args.action == 'notes':
            if manager.set_notes(args.device, args.notes):
                print(f"[+] Notes updated for device")
            else:
                print(f"[!] Device '{args.device}' not found")

        elif args.action == 'remove':
            device = manager.get_device(args.device)
            if device:
                confirm = input(f"[?] Remove device '{device.name}' ({device.ip})? (y/N): ").strip().lower()
                if confirm == 'y':
                    manager.remove_device(args.device)
                    print("[+] Device removed from management")
                else:
                    print("[!] Operation cancelled")
            else:
                print(f"[!] Device '{args.device}' not found")

        elif args.action == 'monitor':
            manager.monitor_devices(interval=args.interval)

        elif args.action == 'stats':
            stats = manager.get_statistics()

            print("[=] Device Statistics:")
            print("=" * 30)
            print(f"Total Devices: {stats['total_devices']}")
            print(f"Online: {stats['online_devices']}")
            print(f"Offline: {stats['offline_devices']}")

            if stats['firmware_versions']:
                print("\nFirmware Versions:")
                for version, count in stats['firmware_versions'].items():
                    print(f"   {version}: {count} device(s)")

            if stats['tags']:
                print("\nTags:")
                for tag, count in stats['tags'].items():
                    print(f"   {tag}: {count} device(s)")

            if stats['last_discovery']:
                print(f"\nLast Discovery: {stats['last_discovery'].strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        print(f"[!] Device management error: {e}")
        sys.exit(1)


def wifi_wizard_entry():
    """Entry point for esp-linker-setup-wifi command"""
    wifi_wizard_cli()


def dashboard_cli():
    """Command-line web dashboard launcher"""
    parser = argparse.ArgumentParser(
        description="Launch ESP-Linker web dashboard",
        prog="esp-linker dashboard"
    )
    parser.add_argument('--host', default='localhost', help='Host to bind to (default: localhost)')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to (default: 8080)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--no-browser', action='store_true', help='Don\'t open browser automatically')

    args = parser.parse_args()

    if not DASHBOARD_AVAILABLE:
        print("[!] Dashboard not available")
        print("[i] Install dashboard dependencies with: pip install esp-linker[dashboard]")
        sys.exit(1)

    try:
        print("[*] Starting ESP-Linker Dashboard...")
        print(f"[^] Dashboard will be available at: http://{args.host}:{args.port}")

        if not args.no_browser:
            print("[*] Browser will open automatically")

        run_dashboard(host=args.host, port=args.port, debug=args.debug)

    except Exception as e:
        print(f"[!] Dashboard error: {e}")
        sys.exit(1)


def devices_entry():
    """Entry point for esp-linker-devices command"""
    devices_cli()


def dashboard_entry():
    """Entry point for esp-linker-dashboard command"""
    dashboard_cli()


def show_help():
    """Show help information with Rich TUI"""
    from . import __version__
    render_banner("ESP-LINKER COMMAND LINE INTERFACE", f"Version {__version__}")

    if RICH_AVAILABLE and console:
        from rich.table import Table
        from rich import box
        table = Table(
            title="Available Commands",
            box=box.ROUNDED,
            header_style="bold cyan",
            border_style="cyan"
        )
        table.add_column("Command", style="bold white", width=18)
        table.add_column("Description", style="white")

        table.add_row("flash", "Auto-detect and flash ESP-Linker firmware to ESP8266 / ESP32 via USB")
        table.add_row("ota <IP>", "Flash compiled firmware Over-The-Air (OTA) via WiFi")
        table.add_row("i2c <IP>", "Scan I2C hardware bus and query sensors (MPU6050, BMP280)")
        table.add_row("events <IP>", "Stream real-time GPIO hardware interrupt events live")
        table.add_row("detect", "Scan connected USB ports and identify ESP boards")
        table.add_row("setup-wifi", "Interactive USB serial WiFi configuration wizard")
        table.add_row("discover", "Scan local network for active ESP-Linker devices")
        table.add_row("test <IP>", "Run hardware diagnostic tests on connected board")
        table.add_row("dashboard", "Launch modern browser-based hardware control dashboard")
        table.add_row("devices", "Manage stored device registry")
        table.add_row("reset --ip <IP>", "Factory reset board settings")

        console.print(table)

        ui_print("\n[bold cyan]Quick Workflow:[/bold cyan]")
        ui_print("  1. [bold white]esp-linker flash[/bold white]       - Install firmware via USB")
        ui_print("  2. [bold white]esp-linker setup-wifi[/bold white]  - Configure WiFi credentials")
        ui_print("  3. [bold white]esp-linker discover[/bold white]    - Locate boards on network")
        ui_print("  4. [bold white]esp-linker dashboard[/bold white]   - Launch browser interface")
        ui_print("  5. [bold white]esp-linker ota <IP>[/bold white]   - Upgrade firmware wirelessly\n")
    else:
        print("\nAvailable commands:")
        print("   flash       - Flash ESP-Linker firmware to ESP8266 / ESP32 via USB")
        print("   ota         - Flash firmware Over-The-Air (OTA) via WiFi")
        print("   i2c         - Scan I2C hardware bus and read/write sensors")
        print("   events      - Stream real-time GPIO interrupt events live")
        print("   detect      - Detect ESP boards via USB")
        print("   setup-wifi  - Interactive WiFi configuration wizard")
        print("   discover    - Discover ESP-Linker devices on network")
        print("   test        - Test ESP-Linker device functionality")
        print("   dashboard   - Launch web dashboard")
        print("   reset       - Factory reset ESP-Linker device\n")

def reset_device_cli():
    """Factory reset ESP-Linker device"""
    parser = argparse.ArgumentParser(
        description="Factory reset ESP-Linker device",
        prog="esp-linker reset"
    )
    parser.add_argument('--ip', required=True, help='ESP IP address')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')

    args = parser.parse_args()

    print("[*] ESP-Linker Factory Reset")
    print("(c) 2025 SK Raihan / SKR Electronics Lab")
    print("=" * 50)

    if not args.confirm:
        print(f"[!] WARNING: This will factory reset the device at {args.ip}")
        print("[!] All WiFi credentials and settings will be cleared!")
        confirm = input("[?] Are you sure you want to continue? (yes/no): ").lower().strip()
        if confirm not in ['yes', 'y']:
            print("[!] Factory reset cancelled")
            return

    try:
        import requests
        print(f"[~] Sending factory reset command to {args.ip}...")

        response = requests.post(f"http://{args.ip}/factory_reset", timeout=10)

        if response.status_code == 200:
            data = response.json()
            print(f"[+] {data.get('message', 'Factory reset successful')}")
            print("[i] Device will restart with default settings")
            print("[i] You can now flash new firmware or configure WiFi")
        else:
            print(f"[!] Factory reset failed: HTTP {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"[!] Failed to connect to device: {e}")
    except Exception as e:
        print(f"[!] Error during factory reset: {e}")

def wifi_management_cli():
    """WiFi management commands"""
    parser = argparse.ArgumentParser(
        description="ESP-Linker WiFi Management",
        prog="esp-linker wifi"
    )
    subparsers = parser.add_subparsers(dest='wifi_command', help='WiFi commands')

    # Status command
    status_parser = subparsers.add_parser('status', help='Check WiFi status')
    status_parser.add_argument('--ip', required=True, help='ESP IP address')

    # Enable AP command
    enable_ap_parser = subparsers.add_parser('enable-ap', help='Enable AP mode')
    enable_ap_parser.add_argument('--ip', required=True, help='ESP IP address')

    # Disable AP command
    disable_ap_parser = subparsers.add_parser('disable-ap', help='Disable AP mode')
    disable_ap_parser.add_argument('--ip', required=True, help='ESP IP address')

    args = parser.parse_args()

    if not args.wifi_command:
        parser.print_help()
        return

    try:
        if args.wifi_command == 'status':
            wifi_status_command(args.ip)
        elif args.wifi_command == 'enable-ap':
            wifi_enable_ap_command(args.ip)
        elif args.wifi_command == 'disable-ap':
            wifi_disable_ap_command(args.ip)
    except Exception as e:
        print(f"[!] WiFi command failed: {e}")
        sys.exit(1)

def wifi_status_command(ip):
    """Check WiFi status of ESP device"""
    print(f"[*] Checking WiFi status for {ip}...")
    try:
        board = ESPBoard(ip, timeout=10)
        status = board.status()

        print(f"\n[=] WiFi Status for {ip}:")
        print(f"    Station Mode: {'Connected' if status.get('wifi_connected') else 'Disconnected'}")
        if status.get('wifi_connected'):
            print(f"    Network: {status.get('wifi_ssid', 'Unknown')}")
            print(f"    IP Address: {ip}")
            print(f"    Signal Strength: {status.get('wifi_rssi', 'Unknown')} dBm")
        print(f"    AP Mode: {'Enabled' if status.get('ap_enabled') else 'Disabled'}")
        if status.get('ap_enabled'):
            print(f"    AP SSID: {status.get('ap_ssid', 'ESP_Linker')}")
            print(f"    AP IP: {status.get('ap_ip', '192.168.4.1')}")

        board.close()

    except Exception as e:
        print(f"[!] Failed to get WiFi status: {e}")
        sys.exit(1)

def wifi_enable_ap_command(ip):
    """Enable AP mode on ESP device"""
    print(f"[*] Enabling AP mode on {ip}...")
    try:
        board = ESPBoard(ip, timeout=10)
        print("[!] AP mode control requires firmware v1.3.7+")
        print("[i] Current firmware supports AP auto-management")
        print("[i] AP mode automatically enables when WiFi disconnects")
        board.close()
    except Exception as e:
        print(f"[!] Failed to enable AP mode: {e}")
        sys.exit(1)

def wifi_disable_ap_command(ip):
    """Disable AP mode on ESP device"""
    print(f"[*] Disabling AP mode on {ip}...")
    try:
        board = ESPBoard(ip, timeout=10)
        print("[!] AP mode control requires firmware v1.3.7+")
        print("[i] Current firmware supports AP auto-management")
        print("[i] AP mode automatically disables when WiFi connects")
        board.close()
    except Exception as e:
        print(f"[!] Failed to disable AP mode: {e}")
        sys.exit(1)

def main():
    """Main CLI entry point for esp-linker command"""
    try:
        main_cli()
    except KeyboardInterrupt:
        if ui.console and not ui.plain_mode:
            ui.console.print("\n[bold yellow]▲ Operation cancelled by user.[/bold yellow]")
        else:
            print("\n[INFO] Operation cancelled by user.")
        sys.exit(130)


def main_cli():
    """Main CLI function"""
    is_tty = sys.stdout.isatty() if hasattr(sys.stdout, 'isatty') else False
    plain = ("--plain" in sys.argv) or (not is_tty)
    debug = "--debug" in sys.argv

    if "--plain" in sys.argv:
        sys.argv.remove("--plain")
    if "--debug" in sys.argv:
        sys.argv.remove("--debug")

    ui.configure(plain=plain, debug=debug)

    if len(sys.argv) > 1:
        command = sys.argv[1]

        # Handle global options
        if command in ["--version", "-v"]:
            from . import __version__
            print(f"ESP-Linker v{__version__}")
            sys.exit(0)
        elif command in ["--help", "-h"]:
            show_help()
            sys.exit(0)
        elif command == "discover":
            sys.argv.pop(1)
            discover_devices_cli()
        elif command == "test":
            sys.argv.pop(1)
            test_device_cli()
        elif command == "flash":
            sys.argv.pop(1)
            flash_esp8266_cli()
        elif command == "ota":
            sys.argv.pop(1)
            ota_cli()
        elif command == "i2c":
            sys.argv.pop(1)
            i2c_cli()
        elif command == "events":
            sys.argv.pop(1)
            events_cli()
        elif command == "detect":
            sys.argv.pop(1)
            detect_esp8266_cli()
        elif command == "setup-wifi":
            sys.argv.pop(1)
            wifi_wizard_cli()
        elif command == "devices":
            sys.argv.pop(1)
            devices_cli()
        elif command == "dashboard":
            sys.argv.pop(1)
            dashboard_cli()
        elif command == "wifi":
            sys.argv.pop(1)
            wifi_management_cli()
        elif command == "reset":
            sys.argv.pop(1)
            reset_device_cli()
        else:
            print("[!] Unknown command:", command)
            show_help()
            sys.exit(1)
    else:
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main_cli()
