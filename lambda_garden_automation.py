"""
Smart Garden System - AWS Lambda Function

This function processes sensor data from IoT devices and makes
intelligent watering decisions based on soil moisture and weather forecasts.

"""

import json
import boto3
import os
from datetime import datetime
from decimal import Decimal

# Initialize AWS clients
iot_client = boto3.client('iot-data')
dynamodb = boto3.resource('dynamodb')
sns_client = boto3.client('sns')

# Configuration from environment variables
SENSOR_DATA_TABLE = os.environ.get('SENSOR_DATA_TABLE', 'GardenSensorData')
ACTION_LOG_TABLE = os.environ.get('ACTION_LOG_TABLE', 'GardenActionLog')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY', '')
LOCATION = os.environ.get('LOCATION', 'San Francisco')

# Moisture thresholds
CRITICAL_MOISTURE = 15
LOW_MOISTURE = 25
OPTIMAL_MOISTURE = 45


def lambda_handler(event, context):
    """
    Main handler function triggered by AWS IoT Rule
    
    Args:
        event: Sensor data from IoT device
        context: Lambda context object
        
    Returns:
        dict: Response with status and decision
    """
    print(f"📥 Event received: {json.dumps(event)}")
    
    try:
        # Extract sensor data
        device_id = event.get('deviceId', 'unknown')
        moisture_percent = event.get('moisturePercent', 0)
        soil_moisture_raw = event.get('soilMoisture', 0)
        pump_status = event.get('pumpStatus', 'OFF')
        
        print(f"Device: {device_id}, Moisture: {moisture_percent}%, Pump: {pump_status}")
        
        # Save sensor data to DynamoDB
        save_sensor_data(event)
        
        # Get weather forecast
        weather_data = get_weather_forecast()
        
        # Make watering decision
        decision = make_watering_decision(moisture_percent, weather_data)
        
        # Execute decision
        if decision['should_water']:
            send_pump_command('WATER_ON', decision['duration'])
            log_action(device_id, 'WATER_ON', decision['reason'])
            
            # Send notification for critical conditions
            if moisture_percent < CRITICAL_MOISTURE:
                send_notification(
                    subject='🚨 CRITICAL: Garden Needs Water!',
                    message=f"Soil moisture critically low at {moisture_percent}%. "
                            f"Automatic watering triggered for {decision['duration']}s.",
                    priority='high'
                )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'device_id': device_id,
                'moisture': moisture_percent,
                'decision': decision,
                'weather': weather_data,
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def make_watering_decision(moisture_percent, weather_data):
    """
    Intelligent watering decision based on moisture and weather
    
    Args:
        moisture_percent: Current soil moisture percentage
        weather_data: Weather forecast data
        
    Returns:
        dict: Decision with should_water, duration, and reason
    """
    decision = {
        'should_water': False,
        'duration': 0,
        'reason': 'Soil moisture adequate'
    }
    
    rain_probability = weather_data.get('rain_probability', 0)
    temperature = weather_data.get('temperature', 25)
    
    # Critical moisture - water immediately regardless of weather
    if moisture_percent < CRITICAL_MOISTURE:
        decision = {
            'should_water': True,
            'duration': 30,
            'reason': f'CRITICAL: Soil very dry ({moisture_percent}%) - immediate watering'
        }
    
    # Low moisture - check weather before watering
    elif moisture_percent < LOW_MOISTURE:
        if rain_probability < 50:
            # Low chance of rain - water the plants
            duration = 20 if temperature > 30 else 15
            decision = {
                'should_water': True,
                'duration': duration,
                'reason': f'Soil dry ({moisture_percent}%), low rain chance ({rain_probability}%)'
            }
        else:
            decision['reason'] = f'Soil dry ({moisture_percent}%) but rain expected ({rain_probability}%)'
    
    # Optimal moisture - no watering needed
    elif moisture_percent >= OPTIMAL_MOISTURE:
        decision['reason'] = f'Soil moisture optimal ({moisture_percent}%)'
    
    # Adjust duration based on time of day (night watering is more efficient)
    current_hour = datetime.now().hour
    if decision['should_water'] and (current_hour < 6 or current_hour > 20):
        decision['duration'] += 5
        decision['reason'] += ' - Night watering (optimal time)'
    
    print(f"💡 Decision: {decision}")
    return decision


def get_weather_forecast():
    """
    Fetch weather data from OpenWeatherMap API
    
    Returns:
        dict: Weather data with temperature, humidity, rain probability
    """
    if not WEATHER_API_KEY:
        print("⚠️  No weather API key configured")
        return {
            'temperature': 25,
            'humidity': 50,
            'rain_probability': 0,
            'description': 'unavailable'
        }
    
    try:
        import requests
        
        url = f"http://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': LOCATION,
            'appid': WEATHER_API_KEY,
            'units': 'metric'
        }
        
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        weather = {
            'temperature': round(data['main']['temp'], 1),
            'humidity': data['main']['humidity'],
            'rain_probability': data.get('rain', {}).get('1h', 0) * 100 if 'rain' in data else 0,
            'description': data['weather'][0]['description']
        }
        
        print(f"🌤️  Weather: {weather['temperature']}°C, {weather['description']}, "
              f"Rain: {weather['rain_probability']}%")
        
        return weather
        
    except Exception as e:
        print(f"⚠️  Weather API error: {str(e)}")
        return {
            'temperature': 25,
            'humidity': 50,
            'rain_probability': 0,
            'description': 'error fetching data'
        }


def send_pump_command(action, duration=10):
    """
    Send command to IoT device to control pump
    
    Args:
        action: 'WATER_ON' or 'WATER_OFF'
        duration: Duration in seconds (for WATER_ON)
        
    Returns:
        bool: True if successful
    """
    topic = 'garden/commands'
    
    payload = {
        'action': action,
        'duration': duration,
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        response = iot_client.publish(
            topic=topic,
            qos=1,
            payload=json.dumps(payload)
        )
        print(f"✅ Command sent: {action} for {duration}s")
        return True
        
    except Exception as e:
        print(f"❌ Error sending command: {str(e)}")
        return False


def save_sensor_data(data):
    """
    Save sensor readings to DynamoDB
    
    Args:
        data: Sensor data dict
    """
    try:
        table = dynamodb.Table(SENSOR_DATA_TABLE)
        
        # Convert float to Decimal for DynamoDB
        item = {
            'deviceId': data.get('deviceId', 'unknown'),
            'timestamp': datetime.now().isoformat(),
            'soilMoisture': Decimal(str(data.get('soilMoisture', 0))),
            'moisturePercent': Decimal(str(data.get('moisturePercent', 0))),
            'pumpStatus': data.get('pumpStatus', 'OFF'),
            'rssi': Decimal(str(data.get('rssi', 0))) if 'rssi' in data else None
        }
        
        table.put_item(Item=item)
        print(f"💾 Data saved to DynamoDB")
        
    except Exception as e:
        print(f"⚠️  Database error: {str(e)}")


def log_action(device_id, action, reason):
    """
    Log watering actions for audit trail
    
    Args:
        device_id: Device identifier
        action: Action taken (e.g., 'WATER_ON')
        reason: Reason for the action
    """
    try:
        table = dynamodb.Table(ACTION_LOG_TABLE)
        
        item = {
            'deviceId': device_id,
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'reason': reason
        }
        
        table.put_item(Item=item)
        print(f"📝 Action logged: {action}")
        
    except Exception as e:
        print(f"⚠️  Logging error: {str(e)}")


def send_notification(subject, message, priority='normal'):
    """
    Send notifications via SNS (Email/SMS)
    
    Args:
        subject: Email subject
        message: Notification message
        priority: 'low', 'normal', 'high'
    """
    if not SNS_TOPIC_ARN:
        print("⚠️  No SNS topic configured")
        return
    
    try:
        # Send email via SNS topic
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
        
        print(f"📧 Notification sent: {subject}")
        
    except Exception as e:
        print(f"⚠️  Notification error: {str(e)}")
