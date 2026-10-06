# Changelog

All notable changes to ESP-Linker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
