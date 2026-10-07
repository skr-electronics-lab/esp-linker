"""
ESP-Linker Modern Terminal UI Engine
(c) 2025 SK Raihan / SKR Electronics Lab

Curated, modern, animated terminal user interface powered by Rich and Questionary.
Strictly emoji-free, utilizing professional unicode glyphs, smooth real-time animations,
and clean rounded box geometry.
"""

import sys
import os
import time
from typing import Optional, Dict, Any, List, Callable

from .version import __version__, __firmware_version__

# Rich Terminal Toolkit
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
        FileSizeColumn,
        TotalFileSizeColumn,
        TransferSpeedColumn,
        DownloadColumn,
    )
    from rich.traceback import install as install_rich_traceback
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Questionary Interactive Menus
try:
    import questionary
    from questionary import Style as QStyle
    QUESTIONARY_AVAILABLE = True
except ImportError:
    QUESTIONARY_AVAILABLE = False


# Configure UTF-8 on Windows consoles to prevent legacy cp1252 encoding exceptions
if sys.platform.startswith('win'):
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    if hasattr(sys.stderr, 'reconfigure'):
        try:
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


class UIManager:
    """Central UI Manager handling styling, consoles, questionary menus, and progress displays"""

    # Curated modern engineering color palette
    COLOR_BRAND = "#00f5d4"      # Electric Teal
    COLOR_PRIMARY = "#38bdf8"    # Sky / Cyan
    COLOR_MUTED = "#94a3b8"      # Slate Grey
    COLOR_SUCCESS = "#10b981"    # Emerald Green
    COLOR_WARN = "#f59e0b"       # Amber Gold
    COLOR_ERROR = "#ef4444"      # Crimson Red
    COLOR_STEP = "#818cf8"       # Indigo
    COLOR_RESET = "#a855f7"      # Electric Purple
    COLOR_BORDER = "#0284c7"     # Deep Cyan Border

    def __init__(self):
        self.plain_mode = False
        self.debug_mode = False
        self.console = None
        self._init_console()

    def _init_console(self):
        if not RICH_AVAILABLE:
            self.console = None
            return

        is_tty = sys.stdout.isatty() if hasattr(sys.stdout, 'isatty') else False
        if self.plain_mode or not is_tty:
            self.console = Console(no_color=True, highlight=False, force_terminal=False)
        else:
            self.console = Console(highlight=False)

    def configure(self, plain: bool = False, debug: bool = False):
        """Configure UI mode flags"""
        self.plain_mode = plain
        self.debug_mode = debug
        self._init_console()

        if debug and RICH_AVAILABLE:
            install_rich_traceback(show_locals=True, width=100)

    # Status badges using clean geometric unicode glyphs (NO EMOJIS)
    def info(self, msg: str):
        if self.console and not self.plain_mode:
            self.console.print(f"[{self.COLOR_PRIMARY}]● [INFO][/{self.COLOR_PRIMARY}] {msg}")
        else:
            print(f"[INFO] {msg}")

    def success(self, msg: str):
        if self.console and not self.plain_mode:
            self.console.print(f"[bold {self.COLOR_SUCCESS}]✔ [OK][/bold {self.COLOR_SUCCESS}] {msg}")
        else:
            print(f"[OK] {msg}")

    def warn(self, msg: str):
        if self.console and not self.plain_mode:
            self.console.print(f"[bold {self.COLOR_WARN}]▲ [WARN][/bold {self.COLOR_WARN}] {msg}")
        else:
            print(f"[WARN] {msg}")

    def error(self, msg: str):
        if self.console and not self.plain_mode:
            self.console.print(f"[bold {self.COLOR_ERROR}]✖ [ERROR][/bold {self.COLOR_ERROR}] {msg}")
        else:
            print(f"[ERROR] {msg}")

    def step(self, msg: str):
        if self.console and not self.plain_mode:
            self.console.print(f"[bold {self.COLOR_STEP}]◆ [STEP][/bold {self.COLOR_STEP}] {msg}")
        else:
            print(f"[STEP] {msg}")

    def banner(self, title: str = "ESP-LINKER", subtitle: str = "Hardware Provisioning Tool"):
        """Render a clean, modern, ultra-readable banner panel"""
        from .version import __version__
        if self.console and not self.plain_mode:
            content = Text()
            content.append("  ESP-LINKER  ", style=f"bold {self.COLOR_BRAND}")
            content.append(f"v{__version__}\n", style="bold white")
            content.append(f"  {subtitle}  |  SKR Electronics Lab", style=self.COLOR_MUTED)
            panel = Panel(content, box=box.ROUNDED, border_style=self.COLOR_BORDER, expand=False)
            self.console.print(panel)
        else:
            from .version import __version__
            print("=" * 60)
            print(f" ESP-LINKER v{__version__} - {subtitle} ")
            print("=" * 60)

    def select_menu(self, prompt: str, choices: List[Dict[str, Any]], default: Optional[str] = None) -> Optional[str]:
        """
        Interactive arrow-key selection menu using questionary.
        Falls back to numbered console prompt in plain mode or when questionary is missing.
        """
        if not choices:
            return None

        is_tty = sys.stdin.isatty() if hasattr(sys.stdin, 'isatty') else False
        if QUESTIONARY_AVAILABLE and not self.plain_mode and is_tty:
            q_choices = [
                questionary.Choice(
                    title=c.get("title", str(c.get("value"))),
                    value=c.get("value")
                )
                for c in choices
            ]

            custom_style = QStyle([
                ('qmark', 'fg:#00f5d4 bold'),
                ('question', 'bold white'),
                ('answer', 'fg:#10b981 bold'),
                ('pointer', 'fg:#00f5d4 bold'),
                ('highlighted', 'fg:#00f5d4 bold'),
                ('selected', 'fg:#10b981'),
                ('separator', 'fg:#64748b'),
                ('instruction', 'fg:#94a3b8 italic'),
            ])

            result = questionary.select(
                prompt,
                choices=q_choices,
                default=default,
                style=custom_style,
                qmark="◆"
            ).ask()
            return result
        else:
            print(f"\n{prompt}")
            for i, c in enumerate(choices, 1):
                print(f"  {i}. {c.get('title', c.get('value'))}")
            while True:
                try:
                    raw = input(f"Enter choice [1-{len(choices)}]: ").strip()
                    idx = int(raw) - 1
                    if 0 <= idx < len(choices):
                        return choices[idx].get("value")
                except (ValueError, EOFError):
                    return choices[0].get("value")

    def show_firmware_panel(self, info: Dict[str, Any], port: str, baud: int):
        """Render pre-flash hardware and firmware details in a clean, compact table"""
        if self.console and not self.plain_mode:
            table = Table(
                title="Pre-Flash Configuration",
                box=box.ROUNDED,
                border_style=self.COLOR_BORDER,
                title_style=f"bold {self.COLOR_PRIMARY}",
                show_header=False
            )
            table.add_column("Property", style=f"bold {self.COLOR_PRIMARY}", width=18)
            target_board = info.get("target_board", "ESP8266 / ESP32 (Universal)")
            flash_addr = info.get("flash_address", "0x00000")

            table.add_row("Target Board", target_board)
            table.add_row("Serial Port", f"[bold white]{port}[/bold white]")
            table.add_row("Baud Rate", f"{baud:,} bps (auto-fallback 115,200)")
            table.add_row("Firmware Image", f"{info.get('name', 'ESP-Linker Firmware')} v{info.get('version', __firmware_version__)}")
            table.add_row("Binary Size", f"{info.get('size_kb', 0)} KB ({info.get('size', 0):,} bytes)")
            table.add_row("Flash Target", f"{flash_addr} (dio, 40MHz, auto-detect)")

            self.console.print(table)
        else:
            target_board = info.get("target_board", "ESP8266 / ESP32")
            print("-" * 50)
            print(f"Target: {target_board} | Port: {port} | Baud: {baud}")
            print(f"Firmware: {info.get('name', 'ESP-Linker')} v{info.get('version', __firmware_version__)} ({info.get('size_kb', 0)} KB)")
            print("-" * 50)

    def show_flash_success(self, port: str):
        """Render final success panel with numbered next steps"""
        if self.console and not self.plain_mode:
            body = Text()
            body.append("✔ Firmware successfully flashed and verified!\n\n", style=f"bold {self.COLOR_SUCCESS}")
            body.append("Numbered Next Steps:\n", style="bold white")
            body.append("  1. Configure WiFi:   ", style=self.COLOR_PRIMARY)
            body.append("esp-linker setup-wifi\n", style="bold white")
            body.append("  2. Verify Hardware:  ", style=self.COLOR_PRIMARY)
            body.append("esp-linker test <IP>\n", style="bold white")
            body.append("  3. Discover Devices: ", style=self.COLOR_PRIMARY)
            body.append("esp-linker discover\n", style="bold white")
            body.append("  4. Start Python:     ", style=self.COLOR_PRIMARY)
            body.append("from esp_linker import connect_auto\n", style="bold white")

            panel = Panel(body, title=f"[bold {self.COLOR_SUCCESS}]Flashing Complete[/bold {self.COLOR_SUCCESS}]", box=box.ROUNDED, border_style=self.COLOR_SUCCESS, expand=False)
            self.console.print(panel)
        else:
            print("\n[OK] Firmware successfully flashed and verified!")
            print("Next steps:")
            print("  1. esp-linker setup-wifi")
            print("  2. esp-linker test <IP>")
            print("  3. esp-linker discover")
            print("  4. from esp_linker import connect_auto")


class RichFlashProgressCallback:
    """UI callback implementation with live animated Rich progress bars"""

    def __init__(self, ui_manager: UIManager):
        self.ui = ui_manager
        self.erase_progress: Optional[Progress] = None
        self.flash_progress: Optional[Progress] = None
        self.reset_progress: Optional[Progress] = None
        self.erase_task = None
        self.flash_task = None
        self.reset_task = None
        self.total_bytes = 0
        self.last_pct = -1

    def on_start(self, port: str, baud: int, firmware_info: Dict[str, Any]):
        self.total_bytes = firmware_info.get('size', 0)

    def on_sync(self):
        self.ui.step("Connecting to ESP bootloader...")

    def on_erase_start(self):
        if RICH_AVAILABLE and self.ui.console and not self.ui.plain_mode:
            self.erase_progress = Progress(
                SpinnerColumn(spinner_name="dots", style=f"bold {self.ui.COLOR_WARN}"),
                TextColumn(f"[bold {self.ui.COLOR_WARN}]{{task.description}}"),
                TimeElapsedColumn(),
                console=self.ui.console,
                transient=True
            )
            self.erase_progress.start()
            self.erase_task = self.erase_progress.add_task("Erasing flash memory sectors...", total=None)
        else:
            self.ui.step("Erasing flash memory sectors...")

    def on_erase_complete(self):
        if self.erase_progress:
            self.erase_progress.stop()
            self.erase_progress = None
        self.ui.success("Flash memory erased successfully")

    def on_flash_start(self, total_bytes: int):
        self.total_bytes = total_bytes
        if RICH_AVAILABLE and self.ui.console and not self.ui.plain_mode:
            self.flash_progress = Progress(
                SpinnerColumn(spinner_name="dots", style=f"bold {self.ui.COLOR_BRAND}"),
                TextColumn(f"[bold {self.ui.COLOR_PRIMARY}]{{task.description}}"),
                BarColumn(bar_width=24, style="grey23", complete_style=f"bold {self.ui.COLOR_BRAND}", finished_style=f"bold {self.ui.COLOR_SUCCESS}"),
                TaskProgressColumn("[bold white]{task.percentage:>3.0f}%"),
                TextColumn("[dim]•[/dim]"),
                DownloadColumn(),
                TextColumn("[dim]•[/dim]"),
                TransferSpeedColumn(),
                TextColumn("[dim]•[/dim]"),
                TimeElapsedColumn(),
                console=self.ui.console,
                transient=False
            )
            self.flash_progress.start()
            self.flash_task = self.flash_progress.add_task("Flashing firmware...", total=total_bytes)
        else:
            self.ui.step(f"Flashing firmware image ({total_bytes / 1024:.1f} KB)...")

    def on_flash_progress(self, bytes_written: int, total_bytes: int):
        if self.flash_progress and self.flash_task is not None:
            self.flash_progress.update(self.flash_task, completed=bytes_written, total=total_bytes)
        else:
            pct = int((bytes_written / total_bytes) * 100) if total_bytes > 0 else 0
            if pct // 10 != self.last_pct // 10:
                self.last_pct = pct
                print(f"[INFO] Flashing: {pct}% ({bytes_written // 1024} KB / {total_bytes // 1024} KB)")

    def on_flash_complete(self):
        if self.flash_progress and self.flash_task is not None:
            self.flash_progress.update(
                self.flash_task,
                completed=self.total_bytes,
                description=f"[bold {self.ui.COLOR_SUCCESS}]Firmware written & verified"
            )
            self.flash_progress.stop()
            self.flash_progress = None
        self.ui.success("Firmware written and verified successfully")

    def on_reset_start(self):
        if RICH_AVAILABLE and self.ui.console and not self.ui.plain_mode:
            self.reset_progress = Progress(
                SpinnerColumn(spinner_name="dots", style=f"bold {self.ui.COLOR_RESET}"),
                TextColumn(f"[bold {self.ui.COLOR_RESET}]{{task.description}}"),
                TimeElapsedColumn(),
                console=self.ui.console,
                transient=True
            )
            self.reset_progress.start()
            self.reset_task = self.reset_progress.add_task("Rebooting ESP8266 and verifying boot...", total=None)
        else:
            self.ui.step("Rebooting ESP8266 into firmware mode...")

    def on_reset_complete(self):
        if self.reset_progress:
            self.reset_progress.stop()
            self.reset_progress = None
        self.ui.success("Device rebooted successfully")

    def finish(self):
        if self.erase_progress:
            self.erase_progress.stop()
            self.erase_progress = None
        if self.flash_progress:
            self.flash_progress.stop()
            self.flash_progress = None
        if self.reset_progress:
            self.reset_progress.stop()
            self.reset_progress = None


# Global UI Singleton
ui = UIManager()
