/*

© 2025 SK Raihan / SKR Electronics Lab — All Rights Reserved.

Author: SK Raihan

Website: https://www.skrelectronicslab.com

Email: skrelectronicslab@gmail.com

YouTube: https://www.youtube.com/@skr_electronics_lab

Instagram: https://www.instagram.com/skr_electronics_lab

Twitter: https://www.twitter.com/skrelectronics

Buy Me a Coffee: https://buymeacoffee.com/skrelectronics */

#ifndef CONFIG_H
#define CONFIG_H

// Firmware version
#define FIRMWARE_VERSION "1.0.0"
#define FIRMWARE_NAME "ESP-Link"

// WiFi Configuration
#define DEFAULT_AP_SSID "ESP_Link"
#define DEFAULT_AP_PASSWORD "12345678"
#define WIFI_CONNECT_TIMEOUT 30000  // 30 seconds
#define WIFI_RETRY_DELAY 5000       // 5 seconds

// HTTP Server Configuration
#define HTTP_PORT 80
#define MAX_CLIENTS 4

// mDNS Configuration
#define MDNS_NAME "esp-link"

// Authentication (optional)
#define USE_AUTH false
#define AUTH_TOKEN "your-secret-token"

// Pin Configuration
#define MAX_DIGITAL_PINS 17
#define ANALOG_PIN A0

// PWM Configuration
#define PWM_FREQUENCY 1000
#define PWM_RESOLUTION 10  // 10-bit (0-1023)

// Servo Configuration
#define SERVO_MIN_PULSE 544
#define SERVO_MAX_PULSE 2400

// EEPROM Configuration
#define EEPROM_SIZE 512
#define WIFI_SSID_ADDR 0
#define WIFI_PASS_ADDR 64
#define CONFIG_FLAG_ADDR 128
#define CONFIG_MAGIC 0xAB

// Serial Configuration
#define SERIAL_BAUD 115200

// OTA Configuration
#define OTA_PASSWORD "esp-link-ota"

// Timing Configuration
#define STATUS_UPDATE_INTERVAL 1000  // 1 second
#define WATCHDOG_TIMEOUT 8000        // 8 seconds

// Pin Capabilities
struct PinCapability {
    uint8_t pin;
    bool digital_io;
    bool pwm;
    bool analog_read;
    bool servo;
    bool interrupt;
};

// Pin modes
enum PinMode {
    PIN_INPUT = 0,
    PIN_OUTPUT = 1,
    PIN_INPUT_PULLUP = 2,
    PIN_PWM = 3,
    PIN_SERVO = 4
};

// Response codes
enum ResponseCode {
    SUCCESS = 200,
    BAD_REQUEST = 400,
    UNAUTHORIZED = 401,
    NOT_FOUND = 404,
    INTERNAL_ERROR = 500
};

#endif // CONFIG_H
