import json
import boto3
import requests
from datetime import datetime

# Initialize AWS clients
iot_client = boto3.client('iot-data')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('GardenSensorData')

# Weather API (using OpenWeatherMap - get free API key)
WEATHER_API_KEY = 'YOUR_OPENWEATHER_API_KEY'
LOCATION = 'YOUR_CITY'

def lambda_handler(event, context):
    """
    Triggered when sensor data arrives via IoT Core
    Analyzes soil moisture and weather to make watering decisions
    """
    
    print(f"Event received: {json.dumps(event)}")
    
    # Parse sensor data
    device_id = event.get('deviceId', 'unknown')
    soil_moisture = event.get('soilMoisture', 0)
    moisture_percent = event.get('moisturePercent', 0)
    
    # Save to DynamoDB
    save_to_database(event)
    
    # Get weather forecast
    weather_data = get_weather_forecast()
    
    # Make watering decision
    decision = make_watering_decision(
        moisture_percent, 
        weather_data
    )
    
    # Send command to device if needed
    if decision['should_water']:
        send_pump_command('WATER_ON', decision['duration'])
        log_action(device_id, 'WATER_ON', decision['reason'])
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'decision': decision,
            'moisture': moisture_percent,
            'weather': weather_data
        })
    }

def make_watering_decision(moisture_percent, weather_data):
    """
    Smart logic to decide if watering is needed
    """
    
    # Moisture thresholds
    DRY_THRESHOLD = 30
    VERY_DRY_THRESHOLD = 20
    
    # Default: no watering
    decision = {
        'should_water': False,
        'duration': 0,
        'reason': 'Soil moisture adequate'
    }
    
    # Check if soil is dry
    if moisture_percent < VERY_DRY_THRESHOLD:
        # Very dry - water regardless of weather
        decision = {
            'should_water': True,
            'duration': 30,  # seconds
            'reason': 'Soil very dry - immediate watering needed'
        }
    
    elif moisture_percent < DRY_THRESHOLD:
        # Moderately dry - check weather
        rain_forecast = weather_data.get('rain_probability', 0)
        
        if rain_forecast < 50:
            # Low chance of rain - water the plants
            decision = {
                'should_water': True,
                'duration': 20,
                'reason': f'Soil dry and rain probability low ({rain_forecast}%)'
            }
        else:
            decision['reason'] = f'Soil dry but rain expected ({rain_forecast}%)'
    
    # Night time watering preference (more efficient, less evaporation)
    current_hour = datetime.now().hour
    if decision['should_water'] and (current_hour < 6 or current_hour > 20):
        decision['duration'] += 5  # Water slightly longer at night
        decision['reason'] += ' - Night watering (optimal time)'
    
    return decision

def get_weather_forecast():
    """
    Fetch weather data from OpenWeatherMap API
    """
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={LOCATION}&appid={WEATHER_API_KEY}"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        # Extract relevant info
        weather = {
            'temperature': data['main']['temp'] - 273.15,  # Convert to Celsius
            'humidity': data['main']['humidity'],
            'rain_probability': data.get('rain', {}).get('1h', 0) * 100,
            'description': data['weather'][0]['description']
        }
        
        return weather
        
    except Exception as e:
        print(f"Weather API error: {str(e)}")
        return {
            'temperature': 25,
            'humidity': 50,
            'rain_probability': 0,
            'description': 'unavailable'
        }

def send_pump_command(action, duration=10):
    """
    Send command to IoT device to control pump
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
        print(f"Command sent: {payload}")
        return response
        
    except Exception as e:
        print(f"Error sending command: {str(e)}")
        return None

def save_to_database(data):
    """
    Save sensor readings to DynamoDB for history
    """
    try:
        item = {
            'deviceId': data.get('deviceId', 'unknown'),
            'timestamp': datetime.now().isoformat(),
            'soilMoisture': data.get('soilMoisture', 0),
            'moisturePercent': data.get('moisturePercent', 0),
            'pumpStatus': data.get('pumpStatus', 'OFF')
        }
        
        table.put_item(Item=item)
        print(f"Data saved to DynamoDB: {item}")
        
    except Exception as e:
        print(f"Database error: {str(e)}")

def log_action(device_id, action, reason):
    """
    Log watering actions for audit trail
    """
    try:
        log_table = dynamodb.Table('GardenActionLog')
        
        item = {
            'deviceId': device_id,
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'reason': reason
        }
        
        log_table.put_item(Item=item)
        print(f"Action logged: {item}")
        
    except Exception as e:
        print(f"Logging error: {str(e)}")
