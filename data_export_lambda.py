import json
import boto3
import csv
from datetime import datetime, timedelta
from io import StringIO

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

BUCKET_NAME = 'garden-data-analytics'
TABLE_NAME = 'GardenSensorData'

def lambda_handler(event, context):
    """
    Export yesterday's garden data to S3 as CSV
    Triggered daily by EventBridge
    """
    
    # Get yesterday's date
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime('%Y-%m-%d')
    
    # Query DynamoDB
    table = dynamodb.Table(TABLE_NAME)
    
    items = []
    last_key = None
    
    while True:
        if last_key:
            response = table.scan(
                ExclusiveStartKey=last_key
            )
        else:
            response = table.scan()
        
        items.extend(response.get('Items', []))
        
        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
    
    # Filter for yesterday's data
    filtered_items = [
        item for item in items 
        if item.get('timestamp', '').startswith(date_str)
    ]
    
    if not filtered_items:
        print(f"No data for {date_str}")
        return {'statusCode': 200, 'body': 'No data'}
    
    # Convert to CSV
    csv_buffer = StringIO()
    
    fieldnames = ['timestamp', 'deviceId', 'soilMoisture', 
                  'moisturePercent', 'pumpStatus']
    
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
    writer.writeheader()
    
    for item in filtered_items:
        writer.writerow({
            'timestamp': item.get('timestamp'),
            'deviceId': item.get('deviceId'),
            'soilMoisture': item.get('soilMoisture'),
            'moisturePercent': item.get('moisturePercent'),
            'pumpStatus': item.get('pumpStatus')
        })
    
    # Upload to S3
    s3_key = f"garden-data/{yesterday.year}/{yesterday.month:02d}/{date_str}.csv"
    
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=csv_buffer.getvalue(),
        ContentType='text/csv'
    )
    
    print(f"Exported {len(filtered_items)} records to s3://{BUCKET_NAME}/{s3_key}")
    
    # Optional: Generate summary stats
    generate_summary(filtered_items, date_str)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'records_exported': len(filtered_items),
            's3_location': f's3://{BUCKET_NAME}/{s3_key}'
        })
    }

def generate_summary(items, date):
    """Generate daily summary statistics"""
    
    if not items:
        return
    
    moisture_values = [item['moisturePercent'] for item in items]
    
    summary = {
        'date': date,
        'total_readings': len(items),
        'avg_moisture': sum(moisture_values) / len(moisture_values),
        'min_moisture': min(moisture_values),
        'max_moisture': max(moisture_values),
        'watering_events': sum(1 for item in items if item.get('pumpStatus') == 'ON')
    }
    
    # Save summary JSON
    s3_key = f"garden-summaries/{date}-summary.json"
    
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=json.dumps(summary, indent=2),
        ContentType='application/json'
    )
    
    print(f"Summary saved: {summary}")
