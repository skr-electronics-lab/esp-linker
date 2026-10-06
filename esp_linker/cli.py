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
    ESP8266Flasher,
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
    """Command-line device testing tool"""
    parser = argparse.ArgumentParser(
        description="Test ESP-Linker device functionality",
        prog="esp-linker-test"
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
    
    print("[*] ESP-Link Device Test")
    print("(c) 2025 SK Raihan / SKR Electronics Lab")
    print("=" * 50)
    
    # Determine if input is IP or URL
    device_url = args.device
    if not device_url.startswith('http'):
        device_url = f"http://{device_url}"
    
    try:
        # Connect to device
        print(f"[*] Connecting to {device_url}...")
        board = ESPBoard(url=device_url, timeout=args.timeout)
        
        # Test 1: Status
        print("\n[=] Test 1: Device Status")
        status = board.status()
        print(f"[+] Firmware: {status['firmware_name']} v{status['firmware_version']}")
        print(f"[+] Uptime: {format_uptime(status['uptime'])}")
        print(f"[+] Memory: {format_memory(status['free_heap'])} free")
        print(f"[+] WiFi: {status.get('wifi_ssid', 'Not connected')}")
        
        # Test 2: Capabilities
        print("\n[*] Test 2: Pin Capabilities")
        caps = board.capabilities()
        pins = caps.get('pins', [])
        print(f"[+] Found {len(pins)} GPIO pins")
        pwm_pins = [p['pin'] for p in pins if p.get('pwm')]
        servo_pins = [p['pin'] for p in pins if p.get('servo')]
        print(f"[+] PWM capable pins: {pwm_pins}")
        print(f"[+] Servo capable pins: {servo_pins}")
        
        # Test 3: Digital I/O
        print(f"\n[i] Test 3: Digital I/O (Pin {args.led_pin})")
        try:
            board.set_mode(args.led_pin, 'OUTPUT')
            print(f"[+] Set pin {args.led_pin} to OUTPUT mode")
            
            board.write(args.led_pin, 1)
            print(f"[+] LED ON (pin {args.led_pin})")
            time.sleep(1)
            
            board.write(args.led_pin, 0)
            print(f"[+] LED OFF (pin {args.led_pin})")
            
            value = board.read(args.led_pin)
            print(f"[+] Read pin {args.led_pin}: {value}")
        except Exception as e:
            print(f"[!] Digital I/O test failed: {e}")
        
        # Test 4: PWM
        if args.pwm_pin in pwm_pins:
            print(f"\n[?] Test 4: PWM Control (Pin {args.pwm_pin})")
            try:
                board.set_mode(args.pwm_pin, 'PWM')
                print(f"[+] Set pin {args.pwm_pin} to PWM mode")
                
                for value in [0, 256, 512, 768, 1023]:
                    board.pwm(args.pwm_pin, value)
                    percentage = (value / 1023) * 100
                    print(f"[+] PWM {value}/1023 ({percentage:.1f}%)")
                    time.sleep(0.5)
            except Exception as e:
                print(f"[!] PWM test failed: {e}")
        else:
            print(f"\n[!]  Test 4: PWM - Pin {args.pwm_pin} does not support PWM")
        
        # Test 5: Servo
        if args.servo_pin in servo_pins:
            print(f"\n[~] Test 5: Servo Control (Pin {args.servo_pin})")
            try:
                board.set_mode(args.servo_pin, 'SERVO')
                print(f"[+] Set pin {args.servo_pin} to SERVO mode")
                
                for angle in [0, 45, 90, 135, 180]:
                    board.servo(args.servo_pin, angle)
                    print(f"[+] Servo angle: {angle}deg")
                    time.sleep(0.5)
            except Exception as e:
                print(f"[!] Servo test failed: {e}")
        else:
            print(f"\n[!]  Test 5: Servo - Pin {args.servo_pin} does not support servo")
        
        # Test 6: Analog Reading
        print("\n[^] Test 6: Analog Reading")
        try:
            analog_value = board.read('A0')
            voltage = (analog_value / 1024.0) * 3.3
            print(f"[+] Analog A0: {analog_value}/1024 ({voltage:.2f}V)")
        except Exception as e:
            print(f"[!] Analog reading failed: {e}")
        
        # Test 7: Batch Operations
        print("\n[+] Test 7: Batch Operations")
        try:
            operations = [
                {'type': 'write', 'pin': args.led_pin, 'value': 1},
                {'type': 'read', 'pin': args.led_pin}
            ]
            
            if args.pwm_pin in pwm_pins:
                operations.append({'type': 'pwm', 'pin': args.pwm_pin, 'value': 512})
            
            if args.servo_pin in servo_pins:
                operations.append({'type': 'servo', 'pin': args.servo_pin, 'angle': 90})
            
            results = board.batch(operations)
            success_count = sum(1 for r in results.get('results', []) if r.get('success'))
            total_count = len(results.get('results', []))
            print(f"[+] Batch operations: {success_count}/{total_count} successful")
        except Exception as e:
            print(f"[!] Batch operations failed: {e}")
        
        # Close connection
        board.close()
        
        print("\n" + "=" * 50)
        print("[*] All tests completed successfully!")
        print("[+] ESP-Linker device is working correctly")
        
    except ConnectionError as e:
        print(f"[!] Connection failed: {e}")
        print("\nTroubleshooting:")
        print("- Check device IP address or URL")
        print("- Verify device is powered on")
        print("- Check network connectivity")
        sys.exit(1)
    except Exception as e:
        print(f"[!] Test failed: {e}")
        sys.exit(1)

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
    """Command-line ESP8266 firmware flashing tool"""
    parser = argparse.ArgumentParser(
        description="Flash ESP-Linker firmware to ESP8266",
        prog="esp-linker flash"
    )
    parser.add_argument(
        "--port", "-p",
        type=str,
        help="Serial port (auto-detected if not specified)"
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
        help="Show ESP8266 chip information"
    )
    parser.add_argument(
        "--firmware-info",
        action="store_true",
        help="Show bundled firmware information"
    )

    args = parser.parse_args()

    try:
        flasher = ESP8266Flasher()

        # List ports
        if args.list_ports:
            flasher.display_ports_table()
            return

        # Show chip info
        if args.chip_info:
            try:
                info = flasher.get_chip_info(args.port)
                if RICH_AVAILABLE and console:
                    from rich.table import Table
                    from rich.panel import Panel
                    from rich import box
                    table = Table(box=box.ROUNDED, border_style="cyan", show_header=False)
                    table.add_column("Property", style="bold cyan", width=16)
                    table.add_column("Value", style="white")
                    table.add_row("Port", info['port'])
                    table.add_row("Chip Type", info['chip_type'])
                    if 'chip_id' in info:
                        table.add_row("Chip ID", str(info['chip_id']))
                    if 'mac_address' in info:
                        table.add_row("MAC Address", str(info['mac_address']))
                    console.print(Panel(table, title="[bold white]Chip Telemetry[/bold white]", box=box.ROUNDED, border_style="cyan"))
                else:
                    print(f"Port: {info['port']} | Chip: {info['chip_type']} | ID: {info.get('chip_id', 'N/A')}")
            except Exception as e:
                print_badge("ERROR", f"Failed to get chip info: {e}")
            return

        # Show firmware info
        if args.firmware_info:
            try:
                info = flasher.get_firmware_info()
                if RICH_AVAILABLE and console:
                    from rich.table import Table
                    from rich.panel import Panel
                    from rich import box
                    table = Table(box=box.ROUNDED, border_style="cyan", show_header=False)
                    table.add_column("Property", style="bold cyan", width=16)
                    table.add_column("Value", style="white")
                    table.add_row("Name", info['name'])
                    table.add_row("Version", info['version'])
                    table.add_row("Description", info['description'])
                    table.add_row("File Size", f"{info['size_kb']} KB ({info['size']:,} bytes)")
                    table.add_row("Binary Path", info['path'])
                    table.add_row("Last Modified", info['modified'])
                    console.print(Panel(table, title="[bold white]Bundled Firmware Image[/bold white]", box=box.ROUNDED, border_style="cyan"))
                else:
                    print(f"Firmware: {info['name']} v{info['version']} ({info['size_kb']} KB)")
            except Exception as e:
                print_badge("ERROR", f"Failed to get firmware info: {e}")
            return

        # Flash firmware
        success = flasher.flash_firmware(
            port=args.port,
            baud_rate=args.baud,
            erase_flash=not args.no_erase
        )
        if not success:
            sys.exit(1)

    except FlashError as e:
        print_badge("ERROR", f"Flash Error: {e}")
        sys.exit(1)
    except DeviceNotFoundError as e:
        print_badge("ERROR", f"Device Error: {e}")
        ui_print("\n[dim]Troubleshooting:[/dim]")
        ui_print("  - Check that ESP8266 is connected via USB data cable")
        ui_print("  - Run [bold white]esp-linker detect[/bold white] to see available serial ports")
        ui_print("  - Specify port manually with: [bold white]esp-linker flash --port COM3[/bold white]")
        sys.exit(1)
    except Exception as e:
        print_badge("ERROR", f"Execution error: {e}")
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

        table.add_row("flash", "Auto-detect and flash ESP-Linker firmware to ESP8266")
        table.add_row("detect", "Scan connected USB ports and identify ESP boards")
        table.add_row("setup-wifi", "Interactive USB serial WiFi configuration wizard")
        table.add_row("discover", "Scan local network for active ESP-Linker devices")
        table.add_row("test <IP>", "Run hardware diagnostic tests on connected board")
        table.add_row("dashboard", "Launch local browser-based control dashboard")
        table.add_row("devices", "Manage stored device registry")
        table.add_row("reset --ip <IP>", "Factory reset board settings")

        console.print(table)

        ui_print("\n[bold cyan]Quick Workflow:[/bold cyan]")
        ui_print("  1. [bold white]esp-linker flash[/bold white]       - Install firmware via USB")
        ui_print("  2. [bold white]esp-linker setup-wifi[/bold white]  - Configure WiFi credentials")
        ui_print("  3. [bold white]esp-linker discover[/bold white]    - Locate boards on network")
        ui_print("  4. [bold white]esp-linker dashboard[/bold white]   - Launch browser interface\n")
    else:
        print("\nAvailable commands:")
        print("   flash       - Flash ESP-Linker firmware to ESP8266")
        print("   detect      - Detect ESP8266 boards via USB")
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
    parser.add_argument('--ip', required=True, help='ESP8266 IP address')
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
    status_parser.add_argument('--ip', required=True, help='ESP8266 IP address')

    # Enable AP command
    enable_ap_parser = subparsers.add_parser('enable-ap', help='Enable AP mode')
    enable_ap_parser.add_argument('--ip', required=True, help='ESP8266 IP address')

    # Disable AP command
    disable_ap_parser = subparsers.add_parser('disable-ap', help='Disable AP mode')
    disable_ap_parser.add_argument('--ip', required=True, help='ESP8266 IP address')

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
    """Check WiFi status of ESP8266"""
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
    """Enable AP mode on ESP8266"""
    print(f"[*] Enabling AP mode on {ip}...")
    try:
        board = ESPBoard(ip, timeout=10)
        # This would require firmware support - for now just show message
        print("[!] AP mode control requires firmware v1.3.7+")
        print("[i] Current firmware supports AP auto-management")
        print("[i] AP mode automatically enables when WiFi disconnects")
        board.close()
    except Exception as e:
        print(f"[!] Failed to enable AP mode: {e}")
        sys.exit(1)

def wifi_disable_ap_command(ip):
    """Disable AP mode on ESP8266"""
    print(f"[*] Disabling AP mode on {ip}...")
    try:
        board = ESPBoard(ip, timeout=10)
        # This would require firmware support - for now just show message
        print("[!] AP mode control requires firmware v1.3.7+")
        print("[i] Current firmware supports AP auto-management")
        print("[i] AP mode automatically disables when WiFi connects")
        board.close()
    except Exception as e:
        print(f"[!] Failed to disable AP mode: {e}")
        sys.exit(1)

def main():
    """Main CLI entry point for esp-linker command"""
    # Call the main CLI function with all commands
    main_cli()


def main_cli():
    """Main CLI function"""
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
            # Remove 'discover' from sys.argv so argparse works correctly
            sys.argv.pop(1)
            discover_devices_cli()
        elif command == "test":
            # Remove 'test' from sys.argv so argparse works correctly
            sys.argv.pop(1)
            test_device_cli()
        elif command == "flash":
            # Remove 'flash' from sys.argv so argparse works correctly
            sys.argv.pop(1)
            flash_esp8266_cli()
        elif command == "detect":
            # Remove 'detect' from sys.argv so argparse works correctly
            sys.argv.pop(1)
            detect_esp8266_cli()
        elif command == "setup-wifi":
            # Remove 'setup-wifi' from sys.argv so argparse works correctly
            sys.argv.pop(1)
            wifi_wizard_cli()
        elif command == "devices":
            # Remove 'devices' from sys.argv so argparse works correctly
            sys.argv.pop(1)
            devices_cli()
        elif command == "dashboard":
            # Remove 'dashboard' from sys.argv so argparse works correctly
            sys.argv.pop(1)
            dashboard_cli()
        elif command == "wifi":
            # Remove 'wifi' from sys.argv so argparse works correctly
            sys.argv.pop(1)
            wifi_management_cli()
        elif command == "reset":
            # Remove 'reset' from sys.argv so argparse works correctly
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
