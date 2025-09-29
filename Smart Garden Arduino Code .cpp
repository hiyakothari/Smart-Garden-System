#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// AWS IoT endpoint
const char* mqtt_server = "YOUR_AWS_IOT_ENDPOINT.iot.us-east-1.amazonaws.com";
const int mqtt_port = 8883;

// Topics
const char* telemetry_topic = "garden/telemetry";
const char* command_topic = "garden/commands";

// Pin definitions
const int SOIL_SENSOR_PIN = 34;  // Analog pin for soil moisture
const int PUMP_RELAY_PIN = 5;    // Digital pin for relay

// Thresholds
const int DRY_THRESHOLD = 2000;   // Adjust based on your sensor (0-4095 for ESP32)
const int WET_THRESHOLD = 1000;

// Timing
unsigned long lastPublish = 0;
const long publishInterval = 60000;  // Publish every 60 seconds

WiFiClientSecure espClient;
PubSubClient client(espClient);

// Certificate strings (you'll add these from AWS)
const char* root_ca = R"EOF(
-----BEGIN CERTIFICATE-----
YOUR_ROOT_CA_CERTIFICATE_HERE
-----END CERTIFICATE-----
)EOF";

const char* certificate = R"EOF(
-----BEGIN CERTIFICATE-----
YOUR_DEVICE_CERTIFICATE_HERE
-----END CERTIFICATE-----
)EOF";

const char* private_key = R"EOF(
-----BEGIN RSA PRIVATE KEY-----
YOUR_PRIVATE_KEY_HERE
-----END RSA PRIVATE KEY-----
)EOF";

void setup() {
  Serial.begin(115200);
  
  // Initialize pins
  pinMode(PUMP_RELAY_PIN, OUTPUT);
  digitalWrite(PUMP_RELAY_PIN, LOW);  // Pump off initially
  pinMode(SOIL_SENSOR_PIN, INPUT);
  
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
}

void loop() {
  if (!client.connected()) {
    connectAWSIoT();
  }
  client.loop();
  
  // Read and publish sensor data periodically
  if (millis() - lastPublish > publishInterval) {
    publishSensorData();
    lastPublish = millis();
  }
}

void connectWiFi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\nWiFi connected");
  Serial.println("IP address: " + WiFi.localIP().toString());
}

void connectAWSIoT() {
  while (!client.connected()) {
    Serial.print("Connecting to AWS IoT...");
    
    String clientId = "ESP32_Garden_" + String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("connected!");
      client.subscribe(command_topic);
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 5 seconds");
      delay(5000);
    }
  }
}

void publishSensorData() {
  int soilMoisture = analogRead(SOIL_SENSOR_PIN);
  
  // Convert to percentage (adjust calibration as needed)
  int moisturePercent = map(soilMoisture, DRY_THRESHOLD, WET_THRESHOLD, 0, 100);
  moisturePercent = constrain(moisturePercent, 0, 100);
  
  // Create JSON payload
  StaticJsonDocument<200> doc;
  doc["deviceId"] = "garden_sensor_01";
  doc["soilMoisture"] = soilMoisture;
  doc["moisturePercent"] = moisturePercent;
  doc["pumpStatus"] = digitalRead(PUMP_RELAY_PIN) ? "ON" : "OFF";
  doc["timestamp"] = millis();
  
  char jsonBuffer[200];
  serializeJson(doc, jsonBuffer);
  
  // Publish to AWS IoT
  if (client.publish(telemetry_topic, jsonBuffer)) {
    Serial.println("Data published: " + String(jsonBuffer));
  } else {
    Serial.println("Publish failed");
  }
}

void messageCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message received on topic: ");
  Serial.println(topic);
  
  // Parse JSON command
  StaticJsonDocument<200> doc;
  deserializeJson(doc, payload, length);
  
  const char* action = doc["action"];
  
  if (strcmp(action, "WATER_ON") == 0) {
    digitalWrite(PUMP_RELAY_PIN, HIGH);
    Serial.println("Pump turned ON");
    
    // Auto turn off after duration (if specified)
    if (doc.containsKey("duration")) {
      int duration = doc["duration"];
      delay(duration * 1000);
      digitalWrite(PUMP_RELAY_PIN, LOW);
      Serial.println("Pump turned OFF after duration");
    }
  } 
  else if (strcmp(action, "WATER_OFF") == 0) {
    digitalWrite(PUMP_RELAY_PIN, LOW);
    Serial.println("Pump turned OFF");
  }
  
  // Publish status update
  publishSensorData();
}