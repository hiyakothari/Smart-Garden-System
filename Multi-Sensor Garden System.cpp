// Multi-sensor configuration for different zones

#define NUM_SENSORS 3

// Pin definitions for multiple sensors
const int SOIL_PINS[NUM_SENSORS] = {34, 35, 36};  // Analog pins
const int PUMP_PINS[NUM_SENSORS] = {5, 18, 19};   // Relay pins

// Zone names
const char* ZONE_NAMES[NUM_SENSORS] = {
  "Vegetables",
  "Flowers", 
  "Herbs"
};

// Different moisture thresholds per zone
const int DRY_THRESHOLD[NUM_SENSORS] = {2000, 2200, 1800};
const int WET_THRESHOLD[NUM_SENSORS] = {1000, 1100, 900};

void setup() {
  Serial.begin(115200);
  
  // Initialize all sensor pins
  for (int i = 0; i < NUM_SENSORS; i++) {
    pinMode(SOIL_PINS[i], INPUT);
    pinMode(PUMP_PINS[i], OUTPUT);
    digitalWrite(PUMP_PINS[i], LOW);
  }
  
  connectWiFi();
  connectAWSIoT();
}

void publishMultiSensorData() {
  StaticJsonDocument<512> doc;
  doc["deviceId"] = "garden_sensor_01";
  doc["timestamp"] = millis();
  
  JsonArray zones = doc.createNestedArray("zones");
  
  // Read all sensors
  for (int i = 0; i < NUM_SENSORS; i++) {
    JsonObject zone = zones.createNestedObject();
    
    int rawValue = analogRead(SOIL_PINS[i]);
    int percent = map(rawValue, DRY_THRESHOLD[i], WET_THRESHOLD[i], 0, 100);
    percent = constrain(percent, 0, 100);
    
    zone["name"] = ZONE_NAMES[i];
    zone["soilMoisture"] = rawValue;
    zone["moisturePercent"] = percent;
    zone["pumpStatus"] = digitalRead(PUMP_PINS[i]) ? "ON" : "OFF";
  }
  
  char jsonBuffer[512];
  serializeJson(doc, jsonBuffer);
  
  client.publish("garden/telemetry/multi", jsonBuffer);
  Serial.println("Multi-sensor data: " + String(jsonBuffer));
}

void messageCallback(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<256> doc;
  deserializeJson(doc, payload, length);
  
  const char* action = doc["action"];
  const char* zone = doc["zone"];  // Which zone to control
  
  // Find zone index
  int zoneIndex = -1;
  for (int i = 0; i < NUM_SENSORS; i++) {
    if (strcmp(zone, ZONE_NAMES[i]) == 0) {
      zoneIndex = i;
      break;
    }
  }
  
  if (zoneIndex == -1) {
    Serial.println("Zone not found: " + String(zone));
    return;
  }
  
  // Control specific pump
  if (strcmp(action, "WATER_ON") == 0) {
    digitalWrite(PUMP_PINS[zoneIndex], HIGH);
    Serial.println(String(ZONE_NAMES[zoneIndex]) + " pump ON");
    
    if (doc.containsKey("duration")) {
      int duration = doc["duration"];
      delay(duration * 1000);
      digitalWrite(PUMP_PINS[zoneIndex], LOW);
    }
  } 
  else if (strcmp(action, "WATER_OFF") == 0) {
    digitalWrite(PUMP_PINS[zoneIndex], LOW);
    Serial.println(String(ZONE_NAMES[zoneIndex]) + " pump OFF");
  }
  else if (strcmp(action, "ALL_ON") == 0) {
    // Turn all pumps on
    for (int i = 0; i < NUM_SENSORS; i++) {
      digitalWrite(PUMP_PINS[i], HIGH);
    }
    Serial.println("All pumps ON");
  }
  else if (strcmp(action, "ALL_OFF") == 0) {
    // Turn all pumps off
    for (int i = 0; i < NUM_SENSORS; i++) {
      digitalWrite(PUMP_PINS[i], LOW);
    }
    Serial.println("All pumps OFF");
  }
  
  publishMultiSensorData();
}

void loop() {
  if (!client.connected()) {
    connectAWSIoT();
  }
  client.loop();
  
  if (millis() - lastPublish > publishInterval) {
    publishMultiSensorData();
    lastPublish = millis();
  }
}