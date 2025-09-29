/*
 * Smart Garden System - Main Arduino Code
 * 
 * This code runs on ESP32/ESP8266 to:
 * - Read soil moisture sensor
 * - Control water pump via relay
 * - Communicate with AWS IoT Core
 * - Receive automated watering commands
 * 
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ============================================
// Configuration - Update these values
// ============================================
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// AWS IoT endpoint (get from: aws iot describe-endpoint --endpoint-type iot:Data-ATS)
const char* mqtt_server = "YOUR_AWS_IOT_ENDPOINT.iot.us-east-1.amazonaws.com";
const int mqtt_port = 8883;

// MQTT Topics
const char* telemetry_topic = "garden/telemetry";
const char* command_topic = "garden/commands";

// Pin definitions
const int SOIL_SENSOR_PIN = 34;  // Analog pin for soil moisture sensor
const int PUMP_RELAY_PIN = 5;    // Digital pin for relay control

// Sensor calibration (update after calibrating your sensor)
const int AIR_VALUE = 3000;      // Sensor reading in dry air
const int WATER_VALUE = 1000;    // Sensor reading in water
const int DRY_THRESHOLD = 2000;  // Below this = dry soil
const int WET_THRESHOLD = 1000;  // Below this = wet soil

// Timing
unsigned long lastPublish = 0;
const long publishInterval = 60000;  // Publish every 60 seconds

// Device info
const char* DEVICE_ID = "garden_sensor_01";
const char* FIRMWARE_VERSION = "1.0.0";

WiFiClientSecure espClient;
PubSubClient client(espClient);

// ============================================
// AWS IoT Certificates
// Replace with your actual certificates from AWS IoT Core
// ============================================
const char* root_ca = R"EOF(
-----BEGIN CERTIFICATE-----
YOUR_ROOT_CA_CERTIFICATE_HERE
PASTE_CONTENTS_OF_AmazonRootCA1.pem
-----END CERTIFICATE-----
)EOF";

const char* certificate = R"EOF(
-----BEGIN CERTIFICATE-----
YOUR_DEVICE_CERTIFICATE_HERE
PASTE_CONTENTS_OF_certificate.pem.crt
-----END CERTIFICATE-----
)EOF";

const char* private_key = R"EOF(
-----BEGIN RSA PRIVATE KEY-----
YOUR_PRIVATE_KEY_HERE
PASTE_CONTENTS_OF_private.pem.key
-----END RSA PRIVATE KEY-----
)EOF";

// ============================================
// Setup Function
// ============================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n========================================");
  Serial.println("Smart Garden System Starting...");
  Serial.println("Version: " + String(FIRMWARE_VERSION));
  Serial.println("========================================\n");
  
  // Initialize pins
  pinMode(PUMP_RELAY_PIN, OUTPUT);
  digitalWrite(PUMP_RELAY_PIN, LOW);  // Pump off initially
  pinMode(SOIL_SENSOR_PIN, INPUT);
  
  Serial.println("✓ Pins initialized");
  Serial.println("  - Soil Sensor: GPIO" + String(SOIL_SENSOR_PIN));
  Serial.println("  - Pump Relay: GPIO" + String(PUMP_RELAY_PIN));
  
  // Connect to WiFi
  connectWiFi();
  
  // Configure AWS IoT certificates
  espClient.setCACert(root_ca);
  espClient.setCertificate(certificate);
  espClient.setPrivateKey(private_key);
  
  // Connect to AWS IoT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(messageCallback);
  
  connectAWSIoT();
  
  Serial.println("\n✓ System ready!");
  Serial.println("Device ID: " + String(DEVICE_ID));
  Serial.println("\nStarting sensor monitoring...\n");
}

// ============================================
// Main Loop
// ============================================
void loop() {
  // Ensure MQTT connection
  if (!client.connected()) {
    connectAWSIoT();
  }
  client.loop();
  
  // Publish sensor data periodically
  if (millis() - lastPublish > publishInterval) {
    publishSensorData();
    lastPublish = millis();
  }
  
  // Small delay to prevent watchdog issues
  delay(10);
}

// ============================================
// WiFi Connection
// ============================================
void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✓ WiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal strength (RSSI): ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("\n✗ WiFi connection failed!");
    Serial.println("Please check SSID and password");
  }
}

// ============================================
// AWS IoT Connection
// ============================================
void connectAWSIoT() {
  while (!client.connected()) {
    Serial.print("Connecting to AWS IoT Core...");
    
    // Generate unique client ID
    String clientId = "ESP32_Garden_" + String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println(" connected!");
      
      // Subscribe to command topic
      if (client.subscribe(command_topic)) {
        Serial.println("✓ Subscribed to: " + String(command_topic));
      }
      
      // Publish initial status
      publishSensorData();
      
    } else {
      Serial.print(" failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 5 seconds...");
      
      // Error codes:
      // -4 : MQTT_CONNECTION_TIMEOUT
      // -3 : MQTT_CONNECTION_LOST
      // -2 : MQTT_CONNECT_FAILED
      // -1 : MQTT_DISCONNECTED
      
      delay(5000);
    }
  }
}

// ============================================
// Read and Publish Sensor Data
// ============================================
void publishSensorData() {
  // Read soil moisture sensor
  int soilMoisture = analogRead(SOIL_SENSOR_PIN);
  
  // Convert to percentage (0-100%)
  int moisturePercent = map(soilMoisture, AIR_VALUE, WATER_VALUE, 0, 100);
  moisturePercent = constrain(moisturePercent, 0, 100);
  
  // Get pump status
  bool pumpOn = digitalRead(PUMP_RELAY_PIN);
  
  // Create JSON payload
  StaticJsonDocument<256> doc;
  doc["deviceId"] = DEVICE_ID;
  doc["soilMoisture"] = soilMoisture;
  doc["moisturePercent"] = moisturePercent;
  doc["pumpStatus"] = pumpOn ? "ON" : "OFF";
  doc["timestamp"] = millis();
  doc["rssi"] = WiFi.RSSI();
  doc["firmwareVersion"] = FIRMWARE_VERSION;
  
  char jsonBuffer[256];
  serializeJson(doc, jsonBuffer);
  
  // Publish to AWS IoT
  if (client.publish(telemetry_topic, jsonBuffer)) {
    Serial.println("📤 Data published:");
    Serial.println("   Moisture: " + String(moisturePercent) + "% (raw: " + String(soilMoisture) + ")");
    Serial.println("   Pump: " + String(pumpOn ? "ON" : "OFF"));
    Serial.println("   Topic: " + String(telemetry_topic));
  } else {
    Serial.println("✗ Publish failed!");
  }
}

// ============================================
// Handle Incoming MQTT Messages
// ============================================
void messageCallback(char* topic, byte* payload, unsigned int length) {
  Serial.println("\n📥 Message received on topic: " + String(topic));
  
  // Parse JSON command
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, payload, length);
  
  if (error) {
    Serial.println("✗ JSON parsing failed: " + String(error.c_str()));
    return;
  }
  
  const char* action = doc["action"];
  
  if (action == nullptr) {
    Serial.println("✗ No action specified in command");
    return;
  }
  
  Serial.println("Action: " + String(action));
  
  // Process commands
  if (strcmp(action, "WATER_ON") == 0) {
    digitalWrite(PUMP_RELAY_PIN, HIGH);
    Serial.println("💧 Pump turned ON");
    
    // Auto turn off after duration (if specified)
    if (doc.containsKey("duration")) {
      int duration = doc["duration"];
      Serial.println("   Duration: " + String(duration) + " seconds");
      delay(duration * 1000);
      digitalWrite(PUMP_RELAY_PIN, LOW);
      Serial.println("💧 Pump turned OFF after " + String(duration) + "s");
    }
  } 
  else if (strcmp(action, "WATER_OFF") == 0) {
    digitalWrite(PUMP_RELAY_PIN, LOW);
    Serial.println("🛑 Pump turned OFF");
  }
  else if (strcmp(action, "STATUS") == 0) {
    Serial.println("📊 Status requested - publishing data...");
  }
  else {
    Serial.println("⚠ Unknown action: " + String(action));
  }
  
  // Publish status update
  publishSensorData();
}
