/*
(c) 2025 SK Raihan / SKR Electronics Lab -- All Rights Reserved.
Author: SK Raihan
Website: https://www.skrelectronicslab.com
Email: skrelectronicslab@gmail.com
YouTube: https://www.youtube.com/@skr_electronics_lab
Instagram: https://www.instagram.com/skr_electronics_lab
Twitter: https://www.twitter.com/skrelectronics
Support: https://ko-fi.com/skrelectronicslab

ESP-Linker Universal Firmware
Dual architecture support: ESP8266 and ESP32
Features: GPIO, PWM, Servo, I2C, OTA Update, Real-time Events (SSE), Serial CLI
*/

#include <Arduino.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <EEPROM.h>

#if defined(ESP32)
    #include <WiFi.h>
    #include <WebServer.h>
    #include <ESPmDNS.h>
    #include <Update.h>
    typedef WebServer WebServerType;
    #define ARCH_NAME "ESP32"
    #define DEFAULT_SDA 21
    #define DEFAULT_SCL 22
    #define MAX_DIGITAL_PINS 40
    #define LED_PIN 2
#elif defined(ESP8266)
    #include <ESP8266WiFi.h>
    #include <ESP8266WebServer.h>
    #include <ESP8266mDNS.h>
    #include <ESP8266HTTPUpdateServer.h>
    #include <Servo.h>
    typedef ESP8266WebServer WebServerType;
    #define ARCH_NAME "ESP8266"
    #define DEFAULT_SDA 4
    #define DEFAULT_SCL 5
    #define MAX_DIGITAL_PINS 17
    #define LED_PIN 2
#else
    #error "Unsupported architecture! Must be ESP8266 or ESP32."
#endif

// Configuration
#define FIRMWARE_VERSION "1.3.9"
#define FIRMWARE_NAME "ESP-Linker"
#define AP_SSID "ESP_Link"
#define AP_PASSWORD "12345678"
#define HTTP_PORT 80

// Pin modes
enum PinMode {
    PIN_INPUT = 0,
    PIN_OUTPUT = 1,
    PIN_INPUT_PULLUP = 2,
    PIN_PWM = 3,
    PIN_SERVO = 4
};

// Pin capabilities
struct PinCapability {
    uint8_t pin;
    bool digital_io;
    bool pwm;
    bool analog_read;
    bool servo;
    bool interrupt;
};

#if defined(ESP32)
PinCapability pinCapabilities[] = {
    {0, true, true, false, true, true},
    {2, true, true, true, true, true},
    {4, true, true, true, true, true},
    {5, true, true, false, true, true},
    {12, true, true, true, true, true},
    {13, true, true, true, true, true},
    {14, true, true, true, true, true},
    {15, true, true, true, true, true},
    {16, true, true, false, true, true},
    {17, true, true, false, true, true},
    {18, true, true, false, true, true},
    {19, true, true, false, true, true},
    {21, true, true, false, true, true}, // SDA
    {22, true, true, false, true, true}, // SCL
    {23, true, true, false, true, true},
    {25, true, true, true, true, true},  // DAC1
    {26, true, true, true, true, true},  // DAC2
    {27, true, true, true, true, true},
    {32, true, true, true, true, true},  // ADC1
    {33, true, true, true, true, true},  // ADC1
    {34, false, false, true, false, true}, // Input only ADC1
    {35, false, false, true, false, true}, // Input only ADC1
    {36, false, false, true, false, true}, // Input only (VP)
    {39, false, false, true, false, true}  // Input only (VN)
};
#else
PinCapability pinCapabilities[] = {
    {0, true, false, false, false, true},   // D3 - GPIO0
    {1, true, false, false, false, true},   // TX - GPIO1
    {2, true, true, false, true, true},     // D4 - GPIO2
    {3, true, false, false, false, true},   // RX - GPIO3
    {4, true, true, false, true, true},     // D2 - GPIO4 (SDA)
    {5, true, true, false, true, true},     // D1 - GPIO5 (SCL)
    {12, true, true, false, true, true},    // D6 - GPIO12
    {13, true, true, false, true, true},    // D7 - GPIO13
    {14, true, true, false, true, true},    // D5 - GPIO14
    {15, true, true, false, true, true},    // D8 - GPIO15
    {16, true, false, false, false, false}  // D0 - GPIO16
};
#endif

const int numPins = sizeof(pinCapabilities) / sizeof(PinCapability);

// Global objects
WebServerType server(HTTP_PORT);
#if defined(ESP8266)
ESP8266HTTPUpdateServer httpUpdater;
#endif

#if defined(ESP8266)
Servo servos[MAX_DIGITAL_PINS];
#endif
bool servoAttached[MAX_DIGITAL_PINS] = {false};
uint8_t pinModes[MAX_DIGITAL_PINS];
unsigned long startTime;
String savedSSID = "";
String savedPassword = "";

void writeServoAngle(uint8_t pin, int angle) {
#if defined(ESP8266)
    if (!servoAttached[pin]) {
        servos[pin].attach(pin);
        servoAttached[pin] = true;
    }
    servos[pin].write(angle);
#else
    if (!servoAttached[pin]) {
        ledcAttach(pin, 50, 14); // 50Hz, 14-bit resolution
        servoAttached[pin] = true;
    }
    uint32_t duty = 410 + (uint32_t)((angle * 1638) / 180);
    ledcWrite(pin, duty);
#endif
    pinModes[pin] = PIN_SERVO;
}

void detachServo(uint8_t pin) {
    if (servoAttached[pin]) {
#if defined(ESP8266)
        servos[pin].detach();
#else
        ledcDetach(pin);
#endif
        servoAttached[pin] = false;
    }
}

// Real-time Event Monitor Struct
struct PinWatcher {
    uint8_t pin;
    uint8_t mode; // 0: CHANGE, 1: RISING, 2: FALLING
    int lastState;
    bool active;
};
#define MAX_WATCHERS 8
PinWatcher watchers[MAX_WATCHERS];
unsigned long lastEventPing = 0;
WiFiClient sseClient;
bool sseClientConnected = false;

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
void handleI2CScan();
void handleI2CWrite();
void handleI2CRead();
void handleI2CTransfer();
void handleEvents();
void handleEventSubscribe();
void handleOTAUpload();
void handleOTAFinish();
void checkPinEvents();
void handleNotFound();
String createResponse(int code, String message);
bool isValidPin(uint8_t pin);
bool pinSupportsMode(uint8_t pin, PinMode mode);
void logMessage(String message);
void handleSerialCommands();

void setup() {
    Serial.begin(115200);
    delay(500);

    logMessage(String(FIRMWARE_NAME) + " v" + String(FIRMWARE_VERSION) + " (" + ARCH_NAME + ") Starting...");

    // Initialize EEPROM
    EEPROM.begin(EEPROM_SIZE);

    // Initialize pin modes array
    for (int i = 0; i < MAX_DIGITAL_PINS; i++) {
        pinModes[i] = PIN_INPUT;
    }

    // Initialize watchers
    for (int i = 0; i < MAX_WATCHERS; i++) {
        watchers[i].active = false;
    }

    // Initialize I2C bus
    Wire.begin(DEFAULT_SDA, DEFAULT_SCL);

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

    logMessage(String(FIRMWARE_NAME) + " ready. IP: " + WiFi.localIP().toString());
}

void loop() {
    server.handleClient();
    #if defined(ESP8266)
    MDNS.update();
    #endif
    handleSerialCommands();
    checkPinEvents();
    yield();
}

void setupWiFi() {
    WiFi.mode(WIFI_AP_STA);
    #if defined(ESP8266)
    WiFi.setAutoReconnect(true);
    #endif

    if (savedSSID.length() > 0) {
        logMessage("Connecting to WiFi: " + savedSSID);
        WiFi.begin(savedSSID.c_str(), savedPassword.c_str());

        int attempts = 0;
        while (WiFi.status() != WL_CONNECTED && attempts < 20) {
            delay(500);
            Serial.print(".");
            attempts++;
        }

        if (WiFi.status() == WL_CONNECTED) {
            Serial.println();
            logMessage("WiFi connected. IP: " + WiFi.localIP().toString());
        } else {
            Serial.println();
            logMessage("WiFi connection failed. Starting AP mode.");
        }
    } else {
        logMessage("No WiFi credentials saved in EEPROM.");
    }

    WiFi.softAP(AP_SSID, AP_PASSWORD);
    logMessage("AP active: " + String(AP_SSID) + " (" + WiFi.softAPIP().toString() + ")");
}

void setupMDNS() {
    if (MDNS.begin("esp-link")) {
        MDNS.addService("http", "tcp", HTTP_PORT);
        logMessage("mDNS started: esp-link.local");
    } else {
        logMessage("mDNS setup failed");
    }
}

void setupServer() {
    #if defined(ESP8266)
    server.enableCORS(true);
    #endif

    // Core System Endpoints
    server.on("/configure_wifi", HTTP_POST, handleConfigureWiFi);
    server.on("/restart", HTTP_POST, handleRestart);
    server.on("/status", HTTP_GET, handleStatus);
    server.on("/api/status", HTTP_GET, handleStatus);
    server.on("/capabilities", HTTP_GET, handleCapabilities);
    server.on("/api/capabilities", HTTP_GET, handleCapabilities);

    // GPIO Endpoints
    server.on("/gpio/set_mode", HTTP_POST, handleSetMode);
    server.on("/api/gpio/set_mode", HTTP_POST, handleSetMode);
    server.on("/gpio/write", HTTP_POST, handleWrite);
    server.on("/api/gpio/write", HTTP_POST, handleWrite);
    server.on("/gpio/read", HTTP_GET, handleRead);
    server.on("/api/gpio/read", HTTP_GET, handleRead);
    server.on("/gpio/pwm", HTTP_POST, handlePWM);
    server.on("/api/gpio/pwm", HTTP_POST, handlePWM);
    server.on("/servo/write", HTTP_POST, handleServo);
    server.on("/api/servo/write", HTTP_POST, handleServo);
    server.on("/gpio/batch", HTTP_POST, handleBatch);
    server.on("/api/batch", HTTP_POST, handleBatch);

    // I2C Bus Endpoints
    server.on("/api/i2c/scan", HTTP_GET, handleI2CScan);
    server.on("/api/i2c/write", HTTP_POST, handleI2CWrite);
    server.on("/api/i2c/read", HTTP_GET, handleI2CRead);
    server.on("/api/i2c/transfer", HTTP_POST, handleI2CTransfer);

    // Real-Time Events (Server-Sent Events)
    server.on("/api/events", HTTP_GET, handleEvents);
    server.on("/api/events/subscribe", HTTP_POST, handleEventSubscribe);

    // Over-The-Air (OTA) Binary Upload Endpoint
    server.on("/api/ota", HTTP_POST, handleOTAFinish, handleOTAUpload);

    #if defined(ESP8266)
    // Legacy HTTP Update Form
    httpUpdater.setup(&server, "/update", "admin", "esp-link-ota");
    #endif

    // Simple Built-in Root Page
    server.on("/", HTTP_GET, []() {
        String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>ESP-Linker</title>";
        html += "<style>body{background:#090d16;color:#e2e8f0;font-family:sans-serif;padding:30px;line-height:1.6;}";
        html += "a{color:#38bdf8;text-decoration:none;}a:hover{text-decoration:underline;}";
        html += ".card{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:20px;max-width:700px;margin:20px 0;}";
        html += ".badge{display:inline-block;padding:4px 8px;border-radius:4px;background:#0369a1;font-size:12px;font-weight:bold;}";
        html += "</style></head><body>";
        html += "<h2>ESP-Linker " + String(ARCH_NAME) + "</h2>";
        html += "<div class='card'>";
        html += "<p><span class='badge'>v" + String(FIRMWARE_VERSION) + "</span> Status: <strong>Online</strong></p>";
        html += "<p>Architecture: <strong>" + String(ARCH_NAME) + "</strong> | Free Heap: <strong>" + String(ESP.getFreeHeap()) + " bytes</strong></p>";
        html += "<p>IP Address: <strong>" + WiFi.localIP().toString() + "</strong> | AP SSID: <strong>" + String(AP_SSID) + "</strong></p>";
        html += "<hr style='border:0;border-top:1px solid #334155;'>";
        html += "<p>Features: <strong>GPIO, PWM, Servo, I2C Bus, OTA Update, SSE Event Stream</strong></p>";
        html += "<p><a href='/api/status'>GET /api/status</a> | <a href='/api/capabilities'>GET /api/capabilities</a> | <a href='/api/i2c/scan'>GET /api/i2c/scan</a></p>";
        html += "</div></body></html>";
        server.send(200, "text/html", html);
    });

    server.onNotFound(handleNotFound);
    server.begin();
    logMessage("HTTP server started on port " + String(HTTP_PORT));
}

void handleStatus() {
    DynamicJsonDocument doc(1024);
    doc["firmware_version"] = FIRMWARE_VERSION;
    doc["firmware_name"] = FIRMWARE_NAME;
    doc["architecture"] = ARCH_NAME;
    doc["uptime"] = millis() - startTime;
    doc["free_heap"] = ESP.getFreeHeap();
    #if defined(ESP32)
    doc["chip_id"] = (uint32_t)ESP.getEfuseMac();
    doc["flash_size"] = ESP.getFlashChipSize();
    #else
    doc["chip_id"] = ESP.getChipId();
    doc["flash_size"] = ESP.getFlashChipSize();
    #endif
    doc["wifi_status"] = WiFi.status();
    doc["wifi_ssid"] = WiFi.SSID();
    doc["wifi_ip"] = WiFi.localIP().toString();
    doc["ap_ip"] = WiFi.softAPIP().toString();
    doc["ap_ssid"] = AP_SSID;
    #if defined(ESP8266)
    doc["connected_clients"] = WiFi.softAPgetStationNum();
    #else
    doc["connected_clients"] = WiFi.softAPgetStationNum();
    #endif

    JsonArray feat = doc.createNestedArray("features");
    feat.add("gpio");
    feat.add("pwm");
    feat.add("servo");
    feat.add("i2c");
    feat.add("ota");
    feat.add("events");

    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
}

void handleCapabilities() {
    DynamicJsonDocument doc(3072);
    doc["architecture"] = ARCH_NAME;
    doc["firmware_version"] = FIRMWARE_VERSION;
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
    #if defined(ESP32)
    analogPin["pin"] = "36";
    analogPin["resolution"] = 12;
    analogPin["max_value"] = 4095;
    #else
    analogPin["pin"] = "A0";
    analogPin["resolution"] = 10;
    analogPin["max_value"] = 1024;
    #endif

    JsonObject i2c = doc.createNestedObject("i2c");
    i2c["sda"] = DEFAULT_SDA;
    i2c["scl"] = DEFAULT_SCL;
    i2c["supported"] = true;

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
    if (error || !doc.containsKey("pin") || !doc.containsKey("mode")) {
        server.send(400, "application/json", createResponse(400, "Missing pin or mode in JSON payload"));
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

    if (!isValidPin(pin) || !pinSupportsMode(pin, mode)) {
        server.send(400, "application/json", createResponse(400, "Pin does not support mode"));
        return;
    }

    detachServo(pin);

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
            writeServoAngle(pin, 90);
            break;
    }

    pinModes[pin] = mode;
    server.send(200, "application/json", createResponse(200, "Pin mode set successfully"));
}

void handleWrite() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    DynamicJsonDocument doc(512);
    DeserializationError error = deserializeJson(doc, server.arg("plain"));
    if (error || !doc.containsKey("pin") || !doc.containsKey("value")) {
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
        pinMode(pin, OUTPUT);
        pinModes[pin] = PIN_OUTPUT;
    }

    digitalWrite(pin, value ? HIGH : LOW);
    server.send(200, "application/json", createResponse(200, "Pin written successfully"));
}

void handleRead() {
    if (!server.hasArg("pin")) {
        server.send(400, "application/json", createResponse(400, "Missing pin parameter"));
        return;
    }

    String pinStr = server.arg("pin");

    // Analog reading
    if (pinStr.equalsIgnoreCase("A0") || pinStr == "36" || pinStr == "39") {
        #if defined(ESP8266)
        int value = analogRead(A0);
        #else
        int value = analogRead(pinStr.equalsIgnoreCase("A0") ? 36 : pinStr.toInt());
        #endif
        DynamicJsonDocument doc(512);
        doc["pin"] = pinStr;
        doc["value"] = value;
        doc["type"] = "analog";
        String response;
        serializeJson(doc, response);
        server.send(200, "application/json", response);
        return;
    }

    uint8_t pin = pinStr.toInt();
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
    if (error || !doc.containsKey("pin") || !doc.containsKey("value")) {
        server.send(400, "application/json", createResponse(400, "Missing pin or value"));
        return;
    }

    uint8_t pin = doc["pin"];
    int value = doc["value"];

    if (!isValidPin(pin) || !pinSupportsMode(pin, PIN_PWM)) {
        server.send(400, "application/json", createResponse(400, "Pin does not support PWM"));
        return;
    }

    if (value < 0 || value > 1023) {
        server.send(400, "application/json", createResponse(400, "PWM value must be 0-1023"));
        return;
    }

    #if defined(ESP8266)
    analogWrite(pin, value);
    #else
    ledcAttach(pin, 5000, 10);
    ledcWrite(pin, value);
    #endif

    pinModes[pin] = PIN_PWM;
    server.send(200, "application/json", createResponse(200, "PWM value set successfully"));
}

void handleServo() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    DynamicJsonDocument doc(512);
    DeserializationError error = deserializeJson(doc, server.arg("plain"));
    if (error || !doc.containsKey("pin") || !doc.containsKey("angle")) {
        server.send(400, "application/json", createResponse(400, "Missing pin or angle"));
        return;
    }

    uint8_t pin = doc["pin"];
    int angle = doc["angle"];

    if (!isValidPin(pin) || !pinSupportsMode(pin, PIN_SERVO)) {
        server.send(400, "application/json", createResponse(400, "Pin does not support servo"));
        return;
    }

    if (angle < 0 || angle > 180) {
        server.send(400, "application/json", createResponse(400, "Servo angle must be 0-180"));
        return;
    }

    writeServoAngle(pin, angle);
    server.send(200, "application/json", createResponse(200, "Servo angle set successfully"));
}

void handleBatch() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    DynamicJsonDocument doc(2048);
    DeserializationError error = deserializeJson(doc, server.arg("plain"));
    if (error || !doc.containsKey("operations")) {
        server.send(400, "application/json", createResponse(400, "Missing operations array"));
        return;
    }

    JsonArray operations = doc["operations"];
    DynamicJsonDocument responseDoc(2048);
    JsonArray results = responseDoc.createNestedArray("results");

    for (JsonVariant op : operations) {
        JsonObject res = results.createNestedObject();
        String type = op["type"];
        uint8_t pin = op["pin"];

        if (!isValidPin(pin)) {
            res["success"] = false;
            res["error"] = "Invalid pin";
            continue;
        }

        res["pin"] = pin;
        res["type"] = type;

        if (type == "write") {
            int val = op["value"];
            pinMode(pin, OUTPUT);
            digitalWrite(pin, val ? HIGH : LOW);
            res["success"] = true;
            res["value"] = val;
        } else if (type == "read") {
            res["value"] = digitalRead(pin);
            res["success"] = true;
        } else if (type == "pwm") {
            int val = op["value"];
            #if defined(ESP8266)
            analogWrite(pin, val);
            #else
            ledcAttach(pin, 5000, 10);
            ledcWrite(pin, val);
            #endif
            res["success"] = true;
            res["value"] = val;
        } else if (type == "servo") {
            int angle = op["angle"];
            writeServoAngle(pin, angle);
            res["success"] = true;
            res["angle"] = angle;
        } else {
            res["success"] = false;
            res["error"] = "Unknown operation";
        }
    }

    String response;
    serializeJson(responseDoc, response);
    server.send(200, "application/json", response);
}

// -------------------------------------------------------------
// I2C Hardware Bus Handlers
// -------------------------------------------------------------
void handleI2CScan() {
    DynamicJsonDocument doc(1536);
    doc["sda"] = DEFAULT_SDA;
    doc["scl"] = DEFAULT_SCL;
    JsonArray devices = doc.createNestedArray("devices");

    for (uint8_t address = 8; address < 120; address++) {
        Wire.beginTransmission(address);
        if (Wire.endTransmission() == 0) {
            JsonObject dev = devices.createNestedObject();
            dev["address"] = address;
            char hexStr[8];
            snprintf(hexStr, sizeof(hexStr), "0x%02X", address);
            dev["hex"] = String(hexStr);
        }
    }

    doc["count"] = devices.size();
    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
}

void handleI2CWrite() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    DynamicJsonDocument doc(1024);
    DeserializationError error = deserializeJson(doc, server.arg("plain"));
    if (error || !doc.containsKey("address") || !doc.containsKey("data")) {
        server.send(400, "application/json", createResponse(400, "Missing address or data"));
        return;
    }

    uint8_t address = doc["address"];
    JsonArray data = doc["data"];

    Wire.beginTransmission(address);
    for (size_t i = 0; i < data.size(); i++) {
        Wire.write((uint8_t)data[i].as<int>());
    }
    uint8_t err = Wire.endTransmission();

    if (err == 0) {
        server.send(200, "application/json", createResponse(200, "I2C write success"));
    } else {
        server.send(500, "application/json", createResponse(500, "I2C write failed, error code: " + String(err)));
    }
}

void handleI2CRead() {
    if (!server.hasArg("address") || !server.hasArg("length")) {
        server.send(400, "application/json", createResponse(400, "Missing address or length"));
        return;
    }

    uint8_t address = server.arg("address").toInt();
    size_t length = server.arg("length").toInt();
    if (length > 64) length = 64;

    if (server.hasArg("register")) {
        uint8_t reg = server.arg("register").toInt();
        Wire.beginTransmission(address);
        Wire.write(reg);
        Wire.endTransmission(false); // Repeated start
    }

    size_t received = Wire.requestFrom((int)address, (int)length);
    DynamicJsonDocument doc(1024);
    doc["address"] = address;
    doc["bytes_read"] = received;
    JsonArray bytes = doc.createNestedArray("data");

    while (Wire.available()) {
        bytes.add(Wire.read());
    }

    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
}

void handleI2CTransfer() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    DynamicJsonDocument doc(1024);
    DeserializationError error = deserializeJson(doc, server.arg("plain"));
    if (error || !doc.containsKey("address")) {
        server.send(400, "application/json", createResponse(400, "Missing address"));
        return;
    }

    uint8_t address = doc["address"];
    if (doc.containsKey("write")) {
        JsonArray wdata = doc["write"];
        Wire.beginTransmission(address);
        for (size_t i = 0; i < wdata.size(); i++) {
            Wire.write((uint8_t)wdata[i].as<int>());
        }
        Wire.endTransmission(doc.containsKey("read_length") ? false : true);
    }

    DynamicJsonDocument responseDoc(1024);
    responseDoc["address"] = address;

    if (doc.containsKey("read_length")) {
        size_t len = doc["read_length"];
        if (len > 64) len = 64;
        Wire.requestFrom((int)address, (int)len);
        JsonArray rdata = responseDoc.createNestedArray("read");
        while (Wire.available()) {
            rdata.add(Wire.read());
        }
    }

    responseDoc["status"] = 200;
    String response;
    serializeJson(responseDoc, response);
    server.send(200, "application/json", response);
}

// -------------------------------------------------------------
// Real-Time Events Handlers (Server-Sent Events)
// -------------------------------------------------------------
void handleEvents() {
    WiFiClient client = server.client();
    client.println("HTTP/1.1 200 OK");
    client.println("Content-Type: text/event-stream");
    client.println("Cache-Control: no-cache");
    client.println("Connection: keep-alive");
    client.println("Access-Control-Allow-Origin: *");
    client.println();
    #if defined(ESP8266)
    client.flush();
    #endif

    sseClient = client;
    sseClientConnected = true;
    lastEventPing = millis();

    sseClient.println("event: connected\ndata: {\"status\":\"connected\",\"arch\":\"" + String(ARCH_NAME) + "\"}\n\n");
    #if defined(ESP8266)
    sseClient.flush();
    #endif
}

void handleEventSubscribe() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    DynamicJsonDocument doc(512);
    DeserializationError error = deserializeJson(doc, server.arg("plain"));
    if (error || !doc.containsKey("pin")) {
        server.send(400, "application/json", createResponse(400, "Missing pin"));
        return;
    }

    uint8_t pin = doc["pin"];
    String modeStr = doc.containsKey("mode") ? doc["mode"].as<String>() : "CHANGE";
    uint8_t m = 0;
    if (modeStr.equalsIgnoreCase("RISING")) m = 1;
    else if (modeStr.equalsIgnoreCase("FALLING")) m = 2;

    if (!isValidPin(pin)) {
        server.send(400, "application/json", createResponse(400, "Invalid pin"));
        return;
    }

    pinMode(pin, INPUT_PULLUP);
    pinModes[pin] = PIN_INPUT_PULLUP;

    // Register into watcher list
    bool added = false;
    for (int i = 0; i < MAX_WATCHERS; i++) {
        if (!watchers[i].active || watchers[i].pin == pin) {
            watchers[i].pin = pin;
            watchers[i].mode = m;
            watchers[i].lastState = digitalRead(pin);
            watchers[i].active = true;
            added = true;
            break;
        }
    }

    if (added) {
        server.send(200, "application/json", createResponse(200, "Subscribed to pin " + String(pin)));
    } else {
        server.send(500, "application/json", createResponse(500, "Maximum watchers reached"));
    }
}

void checkPinEvents() {
    if (!sseClientConnected || !sseClient.connected()) {
        sseClientConnected = false;
        return;
    }

    // Heartbeat ping every 10 seconds
    if (millis() - lastEventPing > 10000) {
        lastEventPing = millis();
        sseClient.println("event: ping\ndata: {\"uptime\":" + String(millis()) + "}\n\n");
        #if defined(ESP8266)
        sseClient.flush();
        #endif
    }

    // Check watched pins
    for (int i = 0; i < MAX_WATCHERS; i++) {
        if (watchers[i].active) {
            int currentState = digitalRead(watchers[i].pin);
            if (currentState != watchers[i].lastState) {
                bool trigger = false;
                if (watchers[i].mode == 0) trigger = true; // CHANGE
                else if (watchers[i].mode == 1 && currentState == HIGH) trigger = true; // RISING
                else if (watchers[i].mode == 2 && currentState == LOW) trigger = true;  // FALLING

                watchers[i].lastState = currentState;

                if (trigger) {
                    sseClient.println("event: pin_change\ndata: {\"pin\":" + String(watchers[i].pin) + ",\"value\":" + String(currentState) + ",\"timestamp\":" + String(millis()) + "}\n\n");
                    #if defined(ESP8266)
                    sseClient.flush();
                    #endif
                }
            }
        }
    }
}

// -------------------------------------------------------------
// Over-The-Air (OTA) Binary Upload Handlers
// -------------------------------------------------------------
void handleOTAUpload() {
    HTTPUpload& upload = server.upload();
    if (upload.status == UPLOAD_FILE_START) {
        logMessage("OTA Update started: " + upload.filename);
        #if defined(ESP32)
        if (!Update.begin(UPDATE_SIZE_UNKNOWN)) {
            Update.printError(Serial);
        }
        #else
        uint32_t maxSketchSpace = (ESP.getFreeSketchSpace() - 0x1000) & 0xFFFFF000;
        if (!Update.begin(maxSketchSpace)) {
            Update.printError(Serial);
        }
        #endif
    } else if (upload.status == UPLOAD_FILE_WRITE) {
        if (Update.write(upload.buf, upload.currentSize) != upload.currentSize) {
            Update.printError(Serial);
        }
    } else if (upload.status == UPLOAD_FILE_END) {
        if (Update.end(true)) {
            logMessage("OTA Update success: " + String(upload.totalSize) + " bytes");
        } else {
            Update.printError(Serial);
        }
    }
}

void handleOTAFinish() {
    server.sendHeader("Connection", "close");
    if (Update.hasError()) {
        server.send(500, "application/json", createResponse(500, "OTA Update failed"));
    } else {
        server.send(200, "application/json", createResponse(200, "OTA Update successful. Rebooting..."));
        delay(500);
        ESP.restart();
    }
}

// -------------------------------------------------------------
// Utilities & WiFi Handlers
// -------------------------------------------------------------
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
        if (pinCapabilities[i].pin == pin) return true;
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
        for (int i = 0; i < 32; i++) {
            char c = EEPROM.read(WIFI_SSID_ADDR + i);
            if (c == 0) break;
            savedSSID += c;
        }
        for (int i = 0; i < 32; i++) {
            char c = EEPROM.read(WIFI_PASS_ADDR + i);
            if (c == 0) break;
            savedPassword += c;
        }
        logMessage("Loaded saved WiFi credentials");
    }
}

void saveWiFiCredentials(String ssid, String password) {
    for (int i = 0; i < 32; i++) {
        EEPROM.write(WIFI_SSID_ADDR + i, 0);
        EEPROM.write(WIFI_PASS_ADDR + i, 0);
    }
    for (size_t i = 0; i < ssid.length() && i < 31; i++) {
        EEPROM.write(WIFI_SSID_ADDR + i, ssid[i]);
    }
    for (size_t i = 0; i < password.length() && i < 31; i++) {
        EEPROM.write(WIFI_PASS_ADDR + i, password[i]);
    }
    EEPROM.write(CONFIG_FLAG_ADDR, CONFIG_MAGIC);
    EEPROM.commit();

    savedSSID = ssid;
    savedPassword = password;
    logMessage("Saved WiFi credentials");
}

void handleConfigureWiFi() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }

    DynamicJsonDocument doc(1024);
    DeserializationError error = deserializeJson(doc, server.arg("plain"));
    if (error || !doc.containsKey("ssid") || !doc.containsKey("password")) {
        server.send(400, "application/json", createResponse(400, "Missing ssid or password"));
        return;
    }

    String ssid = doc["ssid"];
    String password = doc["password"];

    if (ssid.length() == 0 || ssid.length() > 31 || password.length() > 31) {
        server.send(400, "application/json", createResponse(400, "Invalid credential length"));
        return;
    }

    saveWiFiCredentials(ssid, password);
    server.send(200, "application/json", createResponse(200, "WiFi configured. Restart to apply."));
}

void handleRestart() {
    if (server.method() != HTTP_POST) {
        server.send(405, "application/json", createResponse(405, "Method not allowed"));
        return;
    }
    server.send(200, "application/json", createResponse(200, "Restarting..."));
    delay(500);
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
                    Serial.println("Firmware: ESP-Linker v" + String(FIRMWARE_VERSION) + " (" + String(ARCH_NAME) + ")");
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
                            #if defined(ESP8266)
                            String sec = (WiFi.encryptionType(i) == ENC_TYPE_NONE) ? "Open" : "Secured";
                            #else
                            String sec = (WiFi.encryptionType(i) == WIFI_AUTH_OPEN) ? "Open" : "Secured";
                            #endif
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