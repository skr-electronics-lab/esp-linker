/*

© 2025 SK Raihan / SKR Electronics Lab — All Rights Reserved.

Author: SK Raihan

Website: https://www.skrelectronicslab.com

Email: skrelectronicslab@gmail.com

YouTube: https://www.youtube.com/@skr_electronics_lab

Instagram: https://www.instagram.com/skr_electronics_lab

Twitter: https://www.twitter.com/skrelectronics

Buy Me a Coffee: https://buymeacoffee.com/skrelectronics */

// ESP-Link Complete Firmware
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266mDNS.h>
#include <ArduinoJson.h>
#include <Servo.h>
#include <EEPROM.h>
#include <ESP8266HTTPUpdateServer.h>

// Configuration
#define AP_SSID "ESP_Link"
#define AP_PASSWORD "12345678"
#define HTTP_PORT 80
#define LED_PIN 2
#define MAX_DIGITAL_PINS 17

// Pin modes
enum PinMode {
    PIN_INPUT = 0,
    PIN_OUTPUT = 1,
    PIN_INPUT_PULLUP = 2,
    PIN_PWM = 3,
    PIN_SERVO = 4
};

// Pin capabilities for ESP8266 NodeMCU
struct PinCapability {
    uint8_t pin;
    bool digital_io;
    bool pwm;
    bool analog_read;
    bool servo;
    bool interrupt;
};

PinCapability pinCapabilities[] = {
    {0, true, false, false, false, true},   // D3 - GPIO0 (Boot mode pin)
    {1, true, false, false, false, true},   // TX - GPIO1
    {2, true, true, false, true, true},     // D4 - GPIO2 (Built-in LED)
    {3, true, false, false, false, true},   // RX - GPIO3
    {4, true, true, false, true, true},     // D2 - GPIO4
    {5, true, true, false, true, true},     // D1 - GPIO5
    {12, true, true, false, true, true},    // D6 - GPIO12
    {13, true, true, false, true, true},    // D7 - GPIO13
    {14, true, true, false, true, true},    // D5 - GPIO14
    {15, true, true, false, true, true},    // D8 - GPIO15
    {16, true, false, false, false, false}, // D0 - GPIO16 (Wake pin)
};

const int numPins = sizeof(pinCapabilities) / sizeof(PinCapability);

// Global objects
ESP8266WebServer server(HTTP_PORT);
ESP8266HTTPUpdateServer httpUpdater;
Servo servos[MAX_DIGITAL_PINS];
bool servoAttached[MAX_DIGITAL_PINS] = {false};
uint8_t pinModes[MAX_DIGITAL_PINS];
unsigned long startTime;
String savedSSID = "";
String savedPassword = "";

// EEPROM Configuration
#define EEPROM_SIZE 512
#define WIFI_SSID_ADDR 0
#define WIFI_PASS_ADDR 64
#define CONFIG_FLAG_ADDR 128
#define CONFIG_MAGIC 0xAB

// Function declarations
void setupWiFi();
void setupServer();
void setupMDNS();
void loadWiFiCredentials();
void saveWiFiCredentials(String ssid, String password);
void handleConfigureWiFi();
void handleRestart();
void handleStatus();
void handleCapabilities();
void handleSetMode();
void handleWrite();
void handleRead();
void handlePWM();
void handleServo();
void handleBatch();
void handleNotFound();
String createResponse(int code, String message);
bool isValidPin(uint8_t pin);
bool pinSupportsMode(uint8_t pin, PinMode mode);
void logMessage(String message);
void handleSerialCommands();

void setup() {
    Serial.begin(115200);
    delay(1000);

    logMessage("ESP-Link Complete Firmware v1.0.0 Starting...");

    // Initialize EEPROM
    EEPROM.begin(EEPROM_SIZE);

    // Initialize pin modes array
    for (int i = 0; i < MAX_DIGITAL_PINS; i++) {
        pinModes[i] = PIN_INPUT;
    }

    // Record start time
    startTime = millis();

    // Load WiFi credentials
    loadWiFiCredentials();

    // Setup WiFi
    setupWiFi();

    // Setup HTTP server
    setupServer();

    // Setup mDNS
    setupMDNS();

    logMessage("ESP-Link ready! IP: " + WiFi.localIP().toString());
}

void loop() {
    server.handleClient();
    MDNS.update();
    handleSerialCommands();
    yield();
}

void setupWiFi() {
    WiFi.mode(WIFI_AP_STA);
    WiFi.setAutoReconnect(true);

    // Try to connect to saved WiFi if available
    if (savedSSID.length() > 0) {
        logMessage("Connecting to WiFi: " + savedSSID);
        WiFi.begin(savedSSID.c_str(), savedPassword.c_str());

        // Wait for connection
        int attempts = 0;
        while (WiFi.status() != WL_CONNECTED && attempts < 20) {
            delay(500);
            Serial.print(".");
            attempts++;
        }

        if (WiFi.status() == WL_CONNECTED) {
            Serial.println();
            logMessage("WiFi connected! IP: " + WiFi.localIP().toString());
        } else {
            Serial.println();
            logMessage("WiFi connection failed");
        }
    } else {
        logMessage("No WiFi credentials saved");
    }

    // Always start AP mode as backup
    logMessage("Starting Access Point...");
    WiFi.softAP(AP_SSID, AP_PASSWORD);
    logMessage("AP started: " + String(AP_SSID) + " IP: " + WiFi.softAPIP().toString());
}

void setupServer() {
    // Configure CORS headers
    server.enableCORS(true);
    
    // API endpoints
    server.on("/configure_wifi", HTTP_POST, handleConfigureWiFi);
    server.on("/restart", HTTP_POST, handleRestart);
    server.on("/status", HTTP_GET, handleStatus);
    server.on("/capabilities", HTTP_GET, handleCapabilities);
    server.on("/gpio/set_mode", HTTP_POST, handleSetMode);
    server.on("/gpio/write", HTTP_POST, handleWrite);
    server.on("/gpio/read", HTTP_GET, handleRead);
    server.on("/gpio/pwm", HTTP_POST, handlePWM);
    server.on("/servo/write", HTTP_POST, handleServo);
    server.on("/gpio/batch", HTTP_POST, handleBatch);
    
    // Simple test endpoints
    server.on("/", HTTP_GET, []() {
        String html = "<html><head><title>ESP-Link</title></head><body>";
        html += "<h1>🔗 ESP-Link Complete</h1>";
        html += "<p><strong>© 2025 SK Raihan / SKR Electronics Lab</strong></p>";
        html += "<hr>";
        html += "<h3>📡 WiFi Status</h3>";
        if (WiFi.status() == WL_CONNECTED) {
            html += "<p>✅ Connected to: <strong>" + WiFi.SSID() + "</strong></p>";
            html += "<p>📍 IP Address: <strong>" + WiFi.localIP().toString() + "</strong></p>";
        } else {
            html += "<p>❌ Not connected to WiFi</p>";
            html += "<p>🔧 Configure WiFi via API: POST /configure_wifi</p>";
        }
        html += "<p>📡 AP Mode: <strong>" + String(AP_SSID) + "</strong> (" + WiFi.softAPIP().toString() + ")</p>";
        html += "<hr>";
        html += "<h3>🧪 Quick Tests</h3>";
        html += "<p><a href='/led_on'>💡 LED ON</a> | <a href='/led_off'>💡 LED OFF</a></p>";
        html += "<p><a href='/status'>📊 Status</a> | <a href='/capabilities'>🔧 Capabilities</a></p>";
        html += "<hr>";
        html += "<h3>📚 API Documentation</h3>";
        html += "<p>WiFi: POST /configure_wifi, POST /restart</p>";
        html += "<p>GPIO: POST /gpio/set_mode, POST /gpio/write, GET /gpio/read</p>";
        html += "<p>PWM: POST /gpio/pwm | Servo: POST /servo/write</p>";
        html += "<p>Batch: POST /gpio/batch</p>";
        html += "</body></html>";
        server.send(200, "text/html", html);
    });
    
    server.on("/led_on", HTTP_GET, []() {
        digitalWrite(LED_PIN, LOW);
        server.send(200, "text/plain", "LED ON");
        logMessage("LED turned ON");
    });
    
    server.on("/led_off", HTTP_GET, []() {
        digitalWrite(LED_PIN, HIGH);
        server.send(200, "text/plain", "LED OFF");
        logMessage("LED turned OFF");
    });
    
    // OTA update endpoint
    httpUpdater.setup(&server, "/update", "admin", "esp-link-ota");
    
    // 404 handler
    server.onNotFound(handleNotFound);
    
    server.begin();
    logMessage("HTTP server started on port " + String(HTTP_PORT));
}

void setupMDNS() {
    if (MDNS.begin("esp-link")) {
        MDNS.addService("http", "tcp", HTTP_PORT);
        logMessage("mDNS responder started: esp-link.local");
    } else {
        logMessage("Error setting up mDNS responder!");
    }
}

void handleStatus() {
    DynamicJsonDocument doc(1024);
    doc["firmware_version"] = "1.0.0";
    doc["firmware_name"] = "ESP-Link-Complete";
    doc["uptime"] = millis() - startTime;
    doc["free_heap"] = ESP.getFreeHeap();
    doc["chip_id"] = ESP.getChipId();
    doc["flash_size"] = ESP.getFlashChipSize();
    doc["wifi_status"] = WiFi.status();
    doc["wifi_ssid"] = WiFi.SSID();
    doc["wifi_ip"] = WiFi.localIP().toString();
    doc["ap_ip"] = WiFi.softAPIP().toString();
    doc["ap_ssid"] = AP_SSID;
    doc["connected_clients"] = WiFi.softAPgetStationNum();

    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
}

void handleCapabilities() {
    DynamicJsonDocument doc(2048);
    JsonArray pins = doc.createNestedArray("pins");

    for (int i = 0; i < numPins; i++) {
        JsonObject pin = pins.createNestedObject();
        pin["pin"] = pinCapabilities[i].pin;
        pin["digital_io"] = pinCapabilities[i].digital_io;
        pin["pwm"] = pinCapabilities[i].pwm;
        pin["analog_read"] = pinCapabilities[i].analog_read;
        pin["servo"] = pinCapabilities[i].servo;
        pin["interrupt"] = pinCapabilities[i].interrupt;
    }

    JsonObject analogPin = doc.createNestedObject("analog_pin");
    analogPin["pin"] = "A0";
    analogPin["resolution"] = 10;
    analogPin["max_value"] = 1024;

    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
}

void handleSetMode() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    DynamicJsonDocument doc(512);
    DeserializationError error = deserializeJson(doc, server.arg("plain"));

    if (error) {
        server.send(400, "application/json", createResponse(400, "Invalid JSON"));
        return;
    }

    if (!doc.containsKey("pin") || !doc.containsKey("mode")) {
        server.send(400, "application/json", createResponse(400, "Missing pin or mode"));
        return;
    }

    uint8_t pin = doc["pin"];
    String modeStr = doc["mode"];
    PinMode mode;

    if (modeStr == "INPUT") mode = PIN_INPUT;
    else if (modeStr == "OUTPUT") mode = PIN_OUTPUT;
    else if (modeStr == "INPUT_PULLUP") mode = PIN_INPUT_PULLUP;
    else if (modeStr == "PWM") mode = PIN_PWM;
    else if (modeStr == "SERVO") mode = PIN_SERVO;
    else {
        server.send(400, "application/json", createResponse(400, "Invalid mode"));
        return;
    }

    if (!isValidPin(pin)) {
        server.send(400, "application/json", createResponse(400, "Invalid pin"));
        return;
    }

    if (!pinSupportsMode(pin, mode)) {
        server.send(400, "application/json", createResponse(400, "Pin does not support this mode"));
        return;
    }

    // Detach servo if previously attached
    if (servoAttached[pin]) {
        servos[pin].detach();
        servoAttached[pin] = false;
    }

    // Set pin mode
    switch (mode) {
        case PIN_INPUT:
            pinMode(pin, INPUT);
            break;
        case PIN_OUTPUT:
            pinMode(pin, OUTPUT);
            break;
        case PIN_INPUT_PULLUP:
            pinMode(pin, INPUT_PULLUP);
            break;
        case PIN_PWM:
            pinMode(pin, OUTPUT);
            break;
        case PIN_SERVO:
            servos[pin].attach(pin);
            servoAttached[pin] = true;
            break;
    }

    pinModes[pin] = mode;

    server.send(200, "application/json", createResponse(200, "Pin mode set successfully"));
    logMessage("Pin " + String(pin) + " mode set to " + modeStr);
}

void handleWrite() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    DynamicJsonDocument doc(512);
    DeserializationError error = deserializeJson(doc, server.arg("plain"));

    if (error) {
        server.send(400, "application/json", createResponse(400, "Invalid JSON"));
        return;
    }

    if (!doc.containsKey("pin") || !doc.containsKey("value")) {
        server.send(400, "application/json", createResponse(400, "Missing pin or value"));
        return;
    }

    uint8_t pin = doc["pin"];
    int value = doc["value"];

    if (!isValidPin(pin)) {
        server.send(400, "application/json", createResponse(400, "Invalid pin"));
        return;
    }

    if (pinModes[pin] != PIN_OUTPUT) {
        server.send(400, "application/json", createResponse(400, "Pin not set to OUTPUT mode"));
        return;
    }

    digitalWrite(pin, value ? HIGH : LOW);

    server.send(200, "application/json", createResponse(200, "Pin written successfully"));
    logMessage("Pin " + String(pin) + " written value " + String(value));
}

void handleRead() {
    if (!server.hasArg("pin")) {
        server.send(400, "application/json", createResponse(400, "Missing pin parameter"));
        return;
    }

    String pinStr = server.arg("pin");

    // Check if it's analog pin
    if (pinStr == "A0") {
        int value = analogRead(A0);
        DynamicJsonDocument doc(512);
        doc["pin"] = "A0";
        doc["value"] = value;
        doc["type"] = "analog";

        String response;
        serializeJson(doc, response);
        server.send(200, "application/json", response);
        return;
    }

    uint8_t pin = pinStr.toInt();
    if (pin == 0 && pinStr != "0") {
        server.send(400, "application/json", createResponse(400, "Invalid pin"));
        return;
    }

    if (!isValidPin(pin)) {
        server.send(400, "application/json", createResponse(400, "Invalid pin"));
        return;
    }

    int value = digitalRead(pin);

    DynamicJsonDocument doc(512);
    doc["pin"] = pin;
    doc["value"] = value;
    doc["type"] = "digital";

    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
}

void handlePWM() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    DynamicJsonDocument doc(512);
    DeserializationError error = deserializeJson(doc, server.arg("plain"));

    if (error) {
        server.send(400, "application/json", createResponse(400, "Invalid JSON"));
        return;
    }

    if (!doc.containsKey("pin") || !doc.containsKey("value")) {
        server.send(400, "application/json", createResponse(400, "Missing pin or value"));
        return;
    }

    uint8_t pin = doc["pin"];
    int value = doc["value"];

    if (!isValidPin(pin)) {
        server.send(400, "application/json", createResponse(400, "Invalid pin"));
        return;
    }

    if (!pinSupportsMode(pin, PIN_PWM)) {
        server.send(400, "application/json", createResponse(400, "Pin does not support PWM"));
        return;
    }

    if (value < 0 || value > 1023) {
        server.send(400, "application/json", createResponse(400, "PWM value must be 0-1023"));
        return;
    }

    // Set pin to PWM mode if not already
    if (pinModes[pin] != PIN_PWM) {
        pinMode(pin, OUTPUT);
        pinModes[pin] = PIN_PWM;
    }

    analogWrite(pin, value);

    server.send(200, "application/json", createResponse(200, "PWM set successfully"));
    logMessage("Pin " + String(pin) + " PWM set to " + String(value));
}

void handleServo() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    DynamicJsonDocument doc(512);
    DeserializationError error = deserializeJson(doc, server.arg("plain"));

    if (error) {
        server.send(400, "application/json", createResponse(400, "Invalid JSON"));
        return;
    }

    if (!doc.containsKey("pin") || !doc.containsKey("angle")) {
        server.send(400, "application/json", createResponse(400, "Missing pin or angle"));
        return;
    }

    uint8_t pin = doc["pin"];
    int angle = doc["angle"];

    if (!isValidPin(pin)) {
        server.send(400, "application/json", createResponse(400, "Invalid pin"));
        return;
    }

    if (!pinSupportsMode(pin, PIN_SERVO)) {
        server.send(400, "application/json", createResponse(400, "Pin does not support servo"));
        return;
    }

    if (angle < 0 || angle > 180) {
        server.send(400, "application/json", createResponse(400, "Servo angle must be 0-180"));
        return;
    }

    // Attach servo if not already attached
    if (!servoAttached[pin]) {
        servos[pin].attach(pin);
        servoAttached[pin] = true;
        pinModes[pin] = PIN_SERVO;
    }

    servos[pin].write(angle);

    server.send(200, "application/json", createResponse(200, "Servo angle set successfully"));
    logMessage("Pin " + String(pin) + " servo angle set to " + String(angle));
}

void handleBatch() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    DynamicJsonDocument doc(2048);
    DeserializationError error = deserializeJson(doc, server.arg("plain"));

    if (error) {
        server.send(400, "application/json", createResponse(400, "Invalid JSON"));
        return;
    }

    if (!doc.containsKey("operations")) {
        server.send(400, "application/json", createResponse(400, "Missing operations array"));
        return;
    }

    JsonArray operations = doc["operations"];
    DynamicJsonDocument responseDoc(2048);
    JsonArray results = responseDoc.createNestedArray("results");

    for (JsonVariant operation : operations) {
        JsonObject result = results.createNestedObject();

        if (!operation.containsKey("type") || !operation.containsKey("pin")) {
            result["success"] = false;
            result["error"] = "Missing type or pin";
            continue;
        }

        String type = operation["type"];
        uint8_t pin = operation["pin"];

        if (!isValidPin(pin)) {
            result["success"] = false;
            result["error"] = "Invalid pin";
            continue;
        }

        result["pin"] = pin;
        result["type"] = type;

        if (type == "write") {
            if (!operation.containsKey("value")) {
                result["success"] = false;
                result["error"] = "Missing value";
                continue;
            }

            if (pinModes[pin] != PIN_OUTPUT) {
                result["success"] = false;
                result["error"] = "Pin not in OUTPUT mode";
                continue;
            }

            int value = operation["value"];
            digitalWrite(pin, value ? HIGH : LOW);
            result["success"] = true;
            result["value"] = value;

        } else if (type == "read") {
            int value = digitalRead(pin);
            result["success"] = true;
            result["value"] = value;

        } else if (type == "pwm") {
            if (!operation.containsKey("value")) {
                result["success"] = false;
                result["error"] = "Missing value";
                continue;
            }

            if (!pinSupportsMode(pin, PIN_PWM)) {
                result["success"] = false;
                result["error"] = "Pin does not support PWM";
                continue;
            }

            int value = operation["value"];
            if (value < 0 || value > 1023) {
                result["success"] = false;
                result["error"] = "PWM value must be 0-1023";
                continue;
            }

            if (pinModes[pin] != PIN_PWM) {
                pinMode(pin, OUTPUT);
                pinModes[pin] = PIN_PWM;
            }

            analogWrite(pin, value);
            result["success"] = true;
            result["value"] = value;

        } else if (type == "servo") {
            if (!operation.containsKey("angle")) {
                result["success"] = false;
                result["error"] = "Missing angle";
                continue;
            }

            if (!pinSupportsMode(pin, PIN_SERVO)) {
                result["success"] = false;
                result["error"] = "Pin does not support servo";
                continue;
            }

            int angle = operation["angle"];
            if (angle < 0 || angle > 180) {
                result["success"] = false;
                result["error"] = "Servo angle must be 0-180";
                continue;
            }

            if (!servoAttached[pin]) {
                servos[pin].attach(pin);
                servoAttached[pin] = true;
                pinModes[pin] = PIN_SERVO;
            }

            servos[pin].write(angle);
            result["success"] = true;
            result["angle"] = angle;

        } else {
            result["success"] = false;
            result["error"] = "Unknown operation type";
        }
    }

    String response;
    serializeJson(responseDoc, response);
    server.send(200, "application/json", response);

    logMessage("Batch operation completed with " + String(operations.size()) + " operations");
}

void handleNotFound() {
    server.send(404, "application/json", createResponse(404, "Endpoint not found"));
}

String createResponse(int code, String message) {
    DynamicJsonDocument doc(512);
    doc["status"] = code;
    doc["message"] = message;
    doc["timestamp"] = millis();

    String response;
    serializeJson(doc, response);
    return response;
}

bool isValidPin(uint8_t pin) {
    for (int i = 0; i < numPins; i++) {
        if (pinCapabilities[i].pin == pin) {
            return true;
        }
    }
    return false;
}

bool pinSupportsMode(uint8_t pin, PinMode mode) {
    for (int i = 0; i < numPins; i++) {
        if (pinCapabilities[i].pin == pin) {
            switch (mode) {
                case PIN_INPUT:
                case PIN_OUTPUT:
                case PIN_INPUT_PULLUP:
                    return pinCapabilities[i].digital_io;
                case PIN_PWM:
                    return pinCapabilities[i].pwm;
                case PIN_SERVO:
                    return pinCapabilities[i].servo;
                default:
                    return false;
            }
        }
    }
    return false;
}

void logMessage(String message) {
    Serial.println("[" + String(millis()) + "] " + message);
}

void loadWiFiCredentials() {
    if (EEPROM.read(CONFIG_FLAG_ADDR) == CONFIG_MAGIC) {
        // Read SSID
        for (int i = 0; i < 32; i++) {
            char c = EEPROM.read(WIFI_SSID_ADDR + i);
            if (c == 0) break;
            savedSSID += c;
        }

        // Read Password
        for (int i = 0; i < 32; i++) {
            char c = EEPROM.read(WIFI_PASS_ADDR + i);
            if (c == 0) break;
            savedPassword += c;
        }

        logMessage("Loaded WiFi credentials from EEPROM");
    }
}

void saveWiFiCredentials(String ssid, String password) {
    // Clear the areas first
    for (int i = 0; i < 32; i++) {
        EEPROM.write(WIFI_SSID_ADDR + i, 0);
        EEPROM.write(WIFI_PASS_ADDR + i, 0);
    }

    // Write SSID
    for (size_t i = 0; i < ssid.length() && i < 31; i++) {
        EEPROM.write(WIFI_SSID_ADDR + i, ssid[i]);
    }

    // Write Password
    for (size_t i = 0; i < password.length() && i < 31; i++) {
        EEPROM.write(WIFI_PASS_ADDR + i, password[i]);
    }

    // Set magic flag
    EEPROM.write(CONFIG_FLAG_ADDR, CONFIG_MAGIC);
    EEPROM.commit();

    savedSSID = ssid;
    savedPassword = password;
    logMessage("WiFi credentials saved to EEPROM");
}

void handleConfigureWiFi() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    DynamicJsonDocument doc(1024);
    DeserializationError error = deserializeJson(doc, server.arg("plain"));

    if (error) {
        server.send(400, "application/json", createResponse(400, "Invalid JSON"));
        return;
    }

    if (!doc.containsKey("ssid") || !doc.containsKey("password")) {
        server.send(400, "application/json", createResponse(400, "Missing ssid or password"));
        return;
    }

    String ssid = doc["ssid"];
    String password = doc["password"];

    if (ssid.length() == 0 || ssid.length() > 31) {
        server.send(400, "application/json", createResponse(400, "Invalid SSID length"));
        return;
    }

    if (password.length() > 31) {
        server.send(400, "application/json", createResponse(400, "Invalid password length"));
        return;
    }

    saveWiFiCredentials(ssid, password);

    server.send(200, "application/json", createResponse(200, "WiFi credentials configured. Restart to apply."));
    logMessage("WiFi credentials updated via API");
}

void handleRestart() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    server.send(200, "application/json", createResponse(200, "Restarting..."));
    delay(1000);
    ESP.restart();
}

void handleSerialCommands() {
    static String serialBuffer = "";
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\r') continue;
        if (c == '\n') {
            serialBuffer.trim();
            if (serialBuffer.length() > 0) {
                if (serialBuffer.equalsIgnoreCase("HELP")) {
                    Serial.println("\n--- ESP-Linker Serial Commands ---");
                    Serial.println("HELP - Show this help menu");
                    Serial.println("STATUS - Show current device status");
                    Serial.println("WIFI_SCAN - Scan for available WiFi networks");
                    Serial.println("WIFI_CONFIG:<ssid>,<password> - Configure WiFi credentials");
                    Serial.println("RESTART - Restart the board");
                    Serial.println("RESET_CONFIG - Clear saved WiFi credentials");
                } else if (serialBuffer.equalsIgnoreCase("STATUS")) {
                    Serial.println("\n--- ESP-Linker Status ---");
                    Serial.println("Firmware: ESP-Linker v1.3.8");
                    Serial.println("Uptime: " + String(millis() / 1000) + "s");
                    Serial.println("Free Heap: " + String(ESP.getFreeHeap()) + " bytes");
                    if (WiFi.status() == WL_CONNECTED) {
                        Serial.println("WiFi: Connected to " + WiFi.SSID());
                        Serial.println("IP: " + WiFi.localIP().toString());
                        Serial.println("Signal: " + String(WiFi.RSSI()) + " dBm");
                    } else {
                        Serial.println("WiFi: Disconnected");
                    }
                    Serial.println("AP SSID: " + String(AP_SSID));
                    Serial.println("AP IP: " + WiFi.softAPIP().toString());
                } else if (serialBuffer.equalsIgnoreCase("WIFI_SCAN")) {
                    Serial.println("Scanning for WiFi networks...");
                    int n = WiFi.scanNetworks();
                    if (n == 0) {
                        Serial.println("No networks found");
                    } else {
                        for (int i = 0; i < n; ++i) {
                            String sec = (WiFi.encryptionType(i) == ENC_TYPE_NONE) ? "Open" : "Secured";
                            Serial.printf("%d: %s (%d dBm) [%s]\n", i + 1, WiFi.SSID(i).c_str(), WiFi.RSSI(i), sec.c_str());
                        }
                    }
                } else if (serialBuffer.startsWith("WIFI_CONFIG:")) {
                    String creds = serialBuffer.substring(12);
                    int commaIdx = creds.indexOf(',');
                    String ssid = "";
                    String password = "";
                    if (commaIdx != -1) {
                        ssid = creds.substring(0, commaIdx);
                        password = creds.substring(commaIdx + 1);
                    } else {
                        ssid = creds;
                    }
                    ssid.trim();
                    password.trim();
                    if (ssid.length() > 0) {
                        saveWiFiCredentials(ssid, password);
                        Serial.println("Connecting to WiFi: " + ssid + " ...");
                        WiFi.disconnect();
                        WiFi.begin(ssid.c_str(), password.c_str());
                        int attempts = 0;
                        while (WiFi.status() != WL_CONNECTED && attempts < 30) {
                            delay(500);
                            Serial.print(".");
                            attempts++;
                        }
                        if (WiFi.status() == WL_CONNECTED) {
                            Serial.println("\nSUCCESS: WiFi connected!");
                            Serial.println("IP Address: " + WiFi.localIP().toString());
                            Serial.println("Signal Strength: " + String(WiFi.RSSI()) + " dBm");
                        } else {
                            Serial.println("\nERROR: Failed to connect to WiFi! AP mode remains active.");
                        }
                    } else {
                        Serial.println("ERROR: SSID cannot be empty");
                    }
                } else if (serialBuffer.equalsIgnoreCase("RESTART")) {
                    Serial.println("Restarting ESP-Linker...");
                    delay(500);
                    ESP.restart();
                } else if (serialBuffer.equalsIgnoreCase("RESET_CONFIG")) {
                    for (int i = 0; i < EEPROM_SIZE; i++) EEPROM.write(i, 0);
                    EEPROM.commit();
                    Serial.println("WiFi credentials cleared. Restarting...");
                    delay(500);
                    ESP.restart();
                } else {
                    Serial.println("Unknown command: " + serialBuffer + ". Type HELP for commands.");
                }
            }
            serialBuffer = "";
        } else {
            serialBuffer += c;
        }
    }
}