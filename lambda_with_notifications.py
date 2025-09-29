import json
import boto3
from datetime import datetime

# Initialize clients
iot_client = boto3.client('iot-data')
dynamodb = boto3.resource('dynamodb')
sns_client = boto3.client('sns')

# SNS Configuration
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:ACCOUNT_ID:GardenAlerts'
PHONE_NUMBER = '+1234567890'  # Your phone for SMS
EMAIL = 'your-email@example.com'

def send_notification(subject, message, priority='normal'):
    """
    Send notifications via SNS (SMS + Email)
    Priority: 'low', 'normal', 'high', 'critical'
    """
    try:
        # Publish to SNS topic (email subscribers)
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
        
        # Send SMS for high priority
        if priority in ['high', 'critical']:
            sns_client.publish(
                PhoneNumber=PHONE_NUMBER,
                Message=f"🌱 GARDEN ALERT: {message}"
            )
        
        print(f"Notification sent: {subject}")
        
    except Exception as e:
        print(f"Notification error: {str(e)}")

def lambda_handler(event, context):
    device_id = event.get('deviceId', 'unknown')
    moisture_percent = event.get('moisturePercent', 0)
    
    # Critical alerts
    if moisture_percent < 15:
        send_notification(
            subject='⚠️ CRITICAL: Plants Need Water!',
            message=f'Soil moisture critically low at {moisture_percent}%. Immediate watering triggered.',
            priority='critical'
        )
        send_pump_command('WATER_ON', 30)
        return response('critical_watering', moisture_percent)
    
    # Low moisture warning
    elif moisture_percent < 25:
        weather = get_weather_forecast()
        rain_chance = weather.get('rain_probability', 0)
        
        if rain_chance < 30:
            send_notification(
                subject='🌱 Garden Alert: Low Moisture',
                message=f'Soil at {moisture_percent}%. Rain chance: {rain_chance}%. Watering scheduled.',
                priority='high'
            )
            send_pump_command('WATER_ON', 20)
        else:
            send_notification(
                subject='🌧️ Rain Expected',
                message=f'Soil at {moisture_percent}% but {rain_chance}% rain chance. Watering postponed.',
                priority='normal'
            )
    
    # Daily summary (call this on schedule)
    if context.get('daily_summary', False):
        send_daily_summary(device_id)
    
    return response('ok', moisture_percent)

def send_daily_summary(device_id):
    """Send daily garden status report"""
    
    # Query last 24 hours of data
    table = dynamodb.Table('GardenSensorData')
    response = table.query(
        KeyConditionExpression='deviceId = :id',
        ExpressionAttributeValues={':id': device_id},
        Limit=288,  # ~5 min intervals for 24 hours
        ScanIndexForward=False
    )
    
    readings = response.get('Items', [])
    
    if not readings:
        return
    
    # Calculate stats
    avg_moisture = sum(r['moisturePercent'] for r in readings) / len(readings)
    min_moisture = min(r['moisturePercent'] for r in readings)
    max_moisture = max(r['moisturePercent'] for r in readings)
    
    # Count watering events
    action_table = dynamodb.Table('GardenActionLog')
    action_response = action_table.query(
        KeyConditionExpression='deviceId = :id',
        ExpressionAttributeValues={':id': device_id},
        Limit=100
    )
    watering_count = len([a for a in action_response.get('Items', []) 
                         if a.get('action') == 'WATER_ON'])
    
    # Compose message
    message = f"""
🌱 Daily Garden Report
━━━━━━━━━━━━━━━━━━━━━
Date: {datetime.now().strftime('%Y-%m-%d')}

📊 Moisture Statistics:
  • Average: {avg_moisture:.1f}%
  • Minimum: {min_moisture:.1f}%
  • Maximum: {max_moisture:.1f}%

💧 Watering Events: {watering_count} times today

🌡️ Current Status: {'Healthy' if avg_moisture > 40 else 'Needs Attention'}

View details: https://your-dashboard-url.com
    """.strip()
    
    send_notification(
        subject='🌱 Daily Garden Summary',
        message=message,
        priority='low'
    )

def send_pump_command(action, duration=10):
    """Send command to IoT device"""
    topic = 'garden/commands'
    payload = {
        'action': action,
        'duration': duration,
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        iot_client.publish(
            topic=topic,
            qos=1,
            payload=json.dumps(payload)
        )
        return True
    except Exception as e:
        print(f"Command error: {str(e)}")
        return False

def get_weather_forecast():
    """Simplified weather fetch"""
    # Your existing weather API code
    return {'rain_probability': 20, 'temperature': 25}

def response(status, moisture):
    return {
        'statusCode': 200,
        'body': json.dumps({
            'status': status,
            'moisture': moisture,
            'timestamp': datetime.now().isoformat()
        })
    }
