
# 🌱 Smart Garden Automation System

An IoT-based automated garden watering system that uses soil moisture sensors, weather data, and cloud computing to intelligently water your plants.

<img width="806" height="443" alt="Screenshot 2025-09-29 at 2 29 10 PM" src="https://github.com/user-attachments/assets/ebfb7930-0881-4c67-ab2b-7957333de1d2" />

<img width="802" height="656" alt="Screenshot 2025-09-29 at 2 29 36 PM" src="https://github.com/user-attachments/assets/d7b2ecbf-2cab-46da-96eb-2d9c8f1f6765" />




## 🎯 Features

- **Automated Watering**: Intelligently waters plants based on soil moisture and weather forecasts
- **Real-time Monitoring**: Live dashboard showing soil moisture, pump status, and system health
- **Cloud-Based**: Powered by AWS IoT Core, Lambda, and DynamoDB
- **Smart Decisions**: Considers weather forecasts to avoid unnecessary watering
- **Remote Control**: Control pumps from anywhere via web dashboard
- **Notifications**: Email and SMS alerts for critical conditions
- **Multi-Zone Support**: Manage multiple garden zones independently
- **Data Analytics**: Historical data tracking and visualization


## 🔧 Hardware Requirements

### Core Components
- **ESP32 Development Board** (or ESP8266)
- **Capacitive Soil Moisture Sensor** (1-3 units)
- **5V Relay Module** (single or multi-channel)
- **5V DC Water Pump** (submersible)
- **5V 2A Power Supply**
- **Jumper Wires** (male-to-female, male-to-male)
- **Breadboard** (optional for prototyping)
- **Water tubing/hose**

### Optional Components
- Waterproof enclosure (IP65 rated)
- Solar panel + LiPo battery for portable operation
- DHT22 temperature/humidity sensor
- pH sensor for water quality monitoring

### Estimated Cost
- Basic Setup: $30-50
- Complete Setup with enclosure: $60-80

## 💻 Software Requirements

### Development Tools
- [Arduino IDE](https://www.arduino.cc/en/software) (v1.8.19 or later)
- [Python](https://www.python.org/) (v3.8 or later)
- [AWS CLI](https://aws.amazon.com/cli/) (v2.x)

### Cloud Services
- AWS Account (Free tier eligible)
  - IoT Core
  - Lambda
  - DynamoDB
  - SNS (for notifications)
  - S3 (for data storage)
  - CloudWatch (for monitoring)

### Arduino Libraries
```
PubSubClient (v2.8.0)
ArduinoJson (v6.21.0)
WiFi (built-in for ESP32)
```

## 🏗️ System Architecture

```
┌─────────────────┐
│  Soil Sensors   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      MQTT/TLS      ┌──────────────┐
│   ESP32 Board   │ ◄─────────────────► │ AWS IoT Core │
│   (Arduino)     │      (Port 8883)    └──────┬───────┘
└────────┬────────┘                            │
         │                                     │
         │                              ┌──────▼───────┐
         │                              │  IoT Rules   │
         │                              └──────┬───────┘
         │                                     │
         ▼                                     ▼
┌─────────────────┐                    ┌──────────────┐
│  Water Pumps    │                    │ AWS Lambda   │
│   (via Relay)   │                    │  (Python)    │
└─────────────────┘                    └──────┬───────┘
                                              │
                    ┌─────────────────────────┼─────────────┐
                    │                         │             │
                    ▼                         ▼             ▼
            ┌──────────────┐         ┌──────────────┐ ┌────────┐
            │  DynamoDB    │         │     SNS      │ │   S3   │
            │  (Storage)   │         │ (Alerts)     │ │(Backup)│
            └──────────────┘         └──────────────┘ └────────┘
                    │
                    │
                    ▼
            ┌──────────────┐
            │  Dashboard   │
            │  (Web UI)    │
            └──────────────┘
```


### 🔄 How Components Work Together

```
┌─────────────────────┐
│   Arduino (C++)     │ ──┐
│   ESP32 Hardware    │   │
│  - Read sensors     │   │ MQTT over WiFi
│  - Control pump     │   │ (sends JSON data)
└─────────────────────┘   │
                          ▼
                ┌──────────────────┐
                │  AWS IoT Core    │
                │   (Message Hub)  │
                └────────┬─────────┘
                         │
                         ▼
                ┌──────────────────┐
                │ Lambda (Python)  │ ──► Weather API (HTTP)
                │  - Process data  │
                │  - Make decisions│ ──► DynamoDB (Store)
                │  - Send commands │
                └────────┬─────────┘ ──► SNS (Notify)
                         │
                         │ Commands
                         ▼
                ┌──────────────────┐
                │   Arduino (C++)  │
                │   Pump turns ON  │
                └──────────────────┘

                         ┌──────────────────┐
                         │ Dashboard (JS)   │ ◄── User views
                         │  - Live updates  │     in browser
                         │  - Manual control│
                         └──────────────────┘
```
