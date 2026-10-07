# Changelog

All notable changes to ESP-Linker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.1] - 2026-10-07

### Fixed
- **Flasher Initialization Argument**: Fixed parameter compatibility in `ESP8266Flasher.__init__` and `ESPFlasher` to seamlessly accept `chip`, `chip_type`, and extra keyword arguments without runtime `TypeError`.
- **CLI Flashing Invocation**: Fixed `esp-linker flash` CLI argument passing for target chip selection.

## [1.4.0] - 2026-10-07

### Added
- **ESP32 & Multi-Architecture Support**: Built dual-target firmware images for both ESP8266 (NodeMCU, D1 Mini) and ESP32 (DevKit, NodeMCU-32S). Automatic chip type detection via `detect_chip_type()` in `ESPFlasher` and `--chip {auto,esp8266,esp32}` CLI flag.
- **I2C Hardware Bus & Sensors**: Complete I2C bus primitives (`board.i2c_scan()`, `board.i2c_read()`, `board.i2c_write()`, `board.i2c_transfer()`) and high-level sensor telemetry drivers for MPU-6050 6-axis IMU and BMP280 / BME280 barometers.
- **Over-The-Air (OTA) Firmware Flashing**: Seamless WiFi firmware flashing via `board.ota_flash(path, progress_callback)` and CLI `esp-linker ota <IP>`.
- **Real-Time Interrupt Events (SSE)**: Asynchronous pin change notifications using Server-Sent Events (SSE) `/api/events` via `board.on_change(pin, callback, mode)` and CLI `esp-linker events <IP>`.
- **Modern Hardware Control Dashboard**: Redesigned dark-theme glassmorphism browser dashboard in `dashboard.py` featuring live GPIO matrix, 16x8 I2C hex bus scanner, drag-and-drop OTA upload zone, and zero emojis.
- **New CLI Utilities**: Added `esp-linker ota`, `esp-linker i2c`, and `esp-linker events` with Rich formatting and zero emojis.

## [1.3.9] - 2025-10-07

### Fixed
- **Subprocess Isolation**: Isolated `esptool` child processes from local directory module shadowing by launching subprocesses in a safe working directory and passing `-P` (`safe_path`). This prevents empty or local `esptool.py` files in user directories from hijacking the execution.
- **Flashing Verification Guard**: Added an explicit verification guard in `_execute_flash()`. Flashing will now strictly raise a `FlashError` if no data blocks were written to the target chip, preventing false success reports on empty subprocess runs.
- **Dynamic Firmware Version Resolution**: Wired pre-flash configuration panels and telemetry outputs directly to `__firmware_version__`.

## [1.3.8] - 2025-10-07

### Added
- **Modern Animated TUI Engine**: Built with Rich, Questionary arrow-key interactive menus, and compact box geometry. Features real-time progress bars, transfer speeds, ETA counters, geometric box styling, and zero emojis.
- **Live In-Place Diagnostic Dashboard**: Upgraded `esp-linker test <IP>` to an in-place updating dashboard with `rich.live.Live` verifying telemetry, pin tables, digital I/O, PWM sweeps, servo positioning, ADC readings, and batch pipelines.
- **Flashing Progress Architecture**: Decoupled UI and core flasher logic using progress callbacks (`on_sync`, `on_erase_start`, `on_flash_progress`, `on_reset_start`).
- **Interactive Port & Network Selection**: Uses Questionary for clean arrow-key menu selection across detected serial ports and scanned WiFi networks.
- **Pre-Flash & Post-Flash Panels**: Hardware telemetry review panel before flashing and clean numbered next steps guide after verification.
- **Global CLI Flags**: Added `--plain` (auto-enabled when piped or not a TTY) and `--debug` with rich tracebacks.
- **Cross-Platform UTF-8 Support**: Automatic Windows console stdout reconfiguration to prevent legacy `cp1252` encoding exceptions.
- **SKR Ko-fi Support Badge**: Direct community sponsorship button and links for SKR Electronics Lab.
- **Comprehensive API Tutorials**: Line-by-line documented code examples for every feature in `README.md`.

### Fixed
- **Real-Time Flashing Progress**: Added support for `esptool v5.x` byte counters (`bytes_sent/total_bytes`) and unparenthesized percentages, completely eliminating the 0% to 100% jump during flashing.
- **Active Serial WiFi Scanning**: Fixed premature silence timeouts during `WiFi.scanNetworks()` in `setup-wifi`, ensuring all available 2.4 GHz networks are reliably discovered.
- **WiFi Wizard Credential Confirmation**: Fixed response buffer reading to reliably capture assigned IP address and signal strength after connecting.
- **Subprocess Deadlock Prevention**: Replaced pipe buffering with unbuffered binary stream decoding on both `\r` and `\n`.
- **Firmware Path Resolution**: Fully removed deprecated `pkg_resources` API in favor of modern `pathlib.Path`.

## [1.3.7] - 2025-07-15

### Fixed
- **🧪 Test Suite**: Fixed test_esp_linker.py to use correct analog reading method `board.read('A0')` instead of non-existent `board.read_analog()`
- **📋 Code Quality**: Improved test reliability and consistency with ESPBoard API

## [1.3.6] - 2025-07-15

### Added
- **🔄 Factory Reset Command**: Complete device reset functionality via CLI and web
- **🎨 Professional Dark Mode UI**: Lightweight, consistent interface design
- **🛡️ Enhanced Error Handling**: Comprehensive exception handling and logging system
- **💾 Memory Optimization**: Reduced firmware size and improved performance
- **📝 Centralized Logging**: Professional logging system with configurable levels

### Changed
- **Firmware Size**: Reduced from 371KB to 367.5KB through optimization
- **UI Design**: Consistent dark mode theme across WiFi setup and dashboard
- **CLI Commands**: Updated command structure for better usability
- **Error Messages**: More descriptive and helpful error reporting

### Fixed
- **Memory Issues**: Replaced String concatenation with memory-efficient alternatives
- **Exception Handling**: Replaced bare except clauses with specific exception types
- **Version Consistency**: Synchronized firmware and library versions

## [1.3.5] - 2025-07-15

### Fixed
- **🔧 Syntax Error**: Fixed syntax error in flasher.py that was causing import issues
- **📦 Package Integrity**: Ensured all Python files have correct syntax and structure

## [1.3.4] - 2025-07-15

### Added
- **🌐 Beautiful WiFi Setup Interface**: Complete redesign of ESP8266 web interface for WiFi configuration
- **📡 WiFi Network Scanning**: Automatic scanning and display of available WiFi networks with signal strength
- **🎨 Modern UI Design**: Gradient backgrounds, responsive design, and professional styling
- **🔧 CLI Version Support**: Added --version and --help options to esp-linker command
- **📶 WiFi Management Commands**: New wifi status, enable-ap, disable-ap commands

### Changed
- **Web Interface**: Replaced LED control buttons with WiFi setup form
- **Firmware Name**: Clean "ESP-Linker" name without suffixes
- **User Experience**: Intuitive WiFi configuration with network selection
- **Package Build**: Clean build process with all Python build artifacts removed

### Fixed
- **CLI Commands**: All documented commands now work properly
- **Version Display**: Firmware info shows correct version (1.3.3) and name
- **Web Interface**: Removed API endpoints display, focused on WiFi setup
- **Build Process**: Cleaned all build files for fresh package generation

## [1.3.1] - 2025-07-14

### Added
- **🌐 Beautiful WiFi Setup Interface**: Complete redesign of ESP8266 web interface for WiFi configuration
- **📡 WiFi Network Scanning**: Automatic scanning and display of available WiFi networks
- **🎨 Modern UI Design**: Gradient backgrounds, responsive design, and professional styling
- **🔧 CLI Version Support**: Added --version and --help options to esp-linker command
- **📶 WiFi Management Commands**: New wifi status, enable-ap, disable-ap commands

### Changed
- **Web Interface**: Replaced LED control buttons with WiFi setup form
- **Firmware Name**: Clean "ESP-Linker" name without suffixes
- **User Experience**: Intuitive WiFi configuration with network selection

### Fixed
- **CLI Commands**: All documented commands now work properly
- **Version Display**: Firmware info shows correct version and name
- **Web Interface**: Removed API endpoints display, focused on WiFi setup

## [1.3.0] - 2025-07-14

### Added
- **🤖 Auto-Mode GPIO Control**: Pins automatically configured - no manual setup needed
- **🔄 Smart AP Management**: AP mode auto-disables when WiFi connects, re-enables when disconnected
- **⚡ Ultra-Lightweight Web UI**: Optimized ESP8266 web interface (under 1KB CSS)
- **📊 Enhanced Dashboard**: Modern, responsive web interface with FontAwesome icons
- **🛡️ Better Error Handling**: Improved error messages and recovery mechanisms
- **📱 Mobile-Friendly**: Web interfaces work perfectly on phones and tablets
- **🎯 User Experience**: More intuitive CLI commands and comprehensive documentation
- **🔒 Stability**: Enhanced connection reliability and error recovery
- **🌐 Global CLI Options**: Added --version and --help support
- **📶 WiFi Management**: New wifi status, enable-ap, disable-ap commands

### Changed
- **Firmware Name**: Removed "Complete" suffix - now just "ESP-Linker"
- **Web Interface**: Complete redesign with dark, minimal theme
- **Documentation**: Comprehensive rewrite with step-by-step tutorials and real-world examples
- **API**: Auto-mode setting enabled by default for write(), pwm(), servo() methods
- **Performance**: Faster GPIO operations and reduced memory usage

### Fixed
- **Pin Mode Errors**: No more "Pin not set to OUTPUT mode" errors with auto-mode
- **CLI Commands**: Added missing --version and --help options
- **Web UI Issues**: Removed emojis and heavy CSS for ESP8266 compatibility
- **Documentation**: Fixed all documented commands to match actual implementation

## [1.2.1] - 2025-01-13

### Added
- **Professional CLI Tools Suite**: Complete command-line interface with 8 commands
- **Visual Progress Bars**: Real-time progress indicators for firmware flashing
- **Interactive WiFi Configuration Wizard**: Step-by-step WiFi setup with network scanning
- **Advanced Device Management System**: Multi-device support with persistent configuration
- **Professional Web Dashboard**: Modern responsive web interface for device control
- **Auto-Discovery System**: mDNS-based device discovery with zero configuration
- **Enhanced Error Handling**: Auto-retry logic with exponential backoff
- **Connection Health Monitoring**: Continuous connectivity verification
- **Batch GPIO Operations**: Efficient multiple pin control
- **Comprehensive Documentation**: Professional documentation with examples

### Enhanced
- **PyFirmata-Inspired API**: Familiar interface for Arduino developers
- **Cross-Platform Support**: Windows, Linux, macOS compatibility
- **Professional Logging**: Structured logging with multiple levels
- **Security Features**: CORS support and secure communication
- **Performance Optimization**: Connection pooling and caching

### CLI Commands
- `esp-linker flash`: Flash ESP8266 firmware with progress bars
- `esp-linker setup-wifi`: Interactive WiFi configuration wizard
- `esp-linker devices`: Advanced device management commands
- `esp-linker discover`: Network device discovery
- `esp-linker detect`: ESP8266 board detection
- `esp-linker test`: Device functionality testing
- `esp-linker dashboard`: Launch web dashboard

### Technical Improvements
- **Built-in Firmware**: 365KB complete ESP8266 firmware included
- **Auto-Port Detection**: Intelligent ESP8266 board detection
- **Multiple Baud Rates**: Support for high-speed flashing
- **Chip Verification**: Automatic chip ID and flash size detection
- **Real-time Monitoring**: Live device status and GPIO state updates

### Developer Experience
- **Professional Package Structure**: Clean, organized codebase
- **Comprehensive Testing**: 100% functionality verification
- **Unicode Compatibility**: ASCII-safe symbols for Windows compatibility
- **Professional Documentation**: Complete API reference and examples
- **Educational Content**: Ready-to-use project examples

## [1.2.0] - 2025-01-12

### Added
- Initial professional release
- Core GPIO control functionality
- Basic CLI tools
- Web dashboard foundation
- Device discovery system

### Features
- Digital I/O control
- PWM output (8 channels)
- Servo control (0-180°)
- Analog input (10-bit ADC)
- WiFi connectivity
- RESTful API

## [1.1.0] - 2025-01-11

### Added
- Enhanced GPIO control
- Improved error handling
- Basic device management

## [1.0.0] - 2025-01-10

### Added
- Initial release
- Basic ESP8266 control
- Simple Python API
- Core functionality

---

## Development Roadmap

### Planned Features (v1.3.0)
- **ESP32 Support**: Extend support to ESP32 boards
- **Bluetooth Connectivity**: Bluetooth Low Energy support
- **Advanced Sensors**: Built-in support for common sensors
- **Cloud Integration**: Direct cloud service integration
- **Mobile App**: Companion mobile application
- **OTA Updates**: Over-the-air firmware updates

### Long-term Goals
- **Multi-Protocol Support**: LoRaWAN, Zigbee, Thread
- **Edge Computing**: Local AI/ML processing
- **Industrial Protocols**: Modbus, MQTT, OPC-UA
- **Professional Certification**: Industrial-grade certifications

---

**ESP-Linker** - Professional IoT development made simple.  
*Developed with ❤️ by [SK Raihan](https://www.skrelectronicslab.com) & [SKR Electronics Lab](https://www.skrelectronicslab.com)*
