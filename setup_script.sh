#!/bin/bash

# Smart Garden System - AWS Infrastructure Setup Script
# This script automates the AWS resource creation

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REGION=${AWS_REGION:-us-east-1}
THING_NAME="SmartGarden_Device01"
LAMBDA_FUNCTION_NAME="SmartGardenAutomation"
IOT_POLICY_NAME="SmartGardenPolicy"
DYNAMODB_TABLE1="GardenSensorData"
DYNAMODB_TABLE2="GardenActionLog"
SNS_TOPIC_NAME="GardenAlerts"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Smart Garden System - AWS Setup${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check AWS CLI installation
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI not found. Please install it first.${NC}"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured.${NC}"
    echo "Run: aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓ AWS Account: ${ACCOUNT_ID}${NC}"
echo -e "${GREEN}✓ Region: ${REGION}${NC}"
echo ""

# Function to create IoT Thing
create_iot_thing() {
    echo -e "${YELLOW}Creating IoT Thing...${NC}"
    
    # Create thing
    aws iot create-thing \
        --thing-name ${THING_NAME} \
        --region ${REGION} 2>/dev/null || echo "Thing already exists"
    
    # Create certificates
    mkdir -p certificates
    
    if [ ! -f "certificates/certificate.pem.crt" ]; then
        CERT_OUTPUT=$(aws iot create-keys-and-certificate \
            --set-as-active \
            --certificate-pem-outfile certificates/certificate.pem.crt \
            --public-key-outfile certificates/public.pem.key \
            --private-key-outfile certificates/private.pem.key \
            --region ${REGION})
        
        CERT_ARN=$(echo $CERT_OUTPUT | jq -r '.certificateArn')
        echo $CERT_ARN > certificates/cert_arn.txt
        
        # Download root CA
        curl -o certificates/AmazonRootCA1.pem https://www.amazontrust.com/repository/AmazonRootCA1.pem
        
        echo -e "${GREEN}✓ Certificates created in ./certificates/${NC}"
    else
        CERT_ARN=$(cat certificates/cert_arn.txt)
        echo -e "${GREEN}✓ Using existing certificates${NC}"
    fi
    
    # Create policy
    POLICY_DOCUMENT='{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": "iot:Connect",
          "Resource": "arn:aws:iot:'${REGION}':'${ACCOUNT_ID}':client/*"
        },
        {
          "Effect": "Allow",
          "Action": "iot:Publish",
          "Resource": "arn:aws:iot:'${REGION}':'${ACCOUNT_ID}':topic/garden/*"
        },
        {
          "Effect": "Allow",
          "Action": "iot:Subscribe",
          "Resource": "arn:aws:iot:'${REGION}':'${ACCOUNT_ID}':topicfilter/garden/*"
        },
        {
          "Effect": "Allow",
          "Action": "iot:Receive",
          "Resource": "arn:aws:iot:'${REGION}':'${ACCOUNT_ID}':topic/garden/*"
        }
      ]
    }'
    
    aws iot create-policy \
        --policy-name ${IOT_POLICY_NAME} \
        --policy-document "${POLICY_DOCUMENT}" \
        --region ${REGION} 2>/dev/null || echo "Policy already exists"
    
    # Attach policy to certificate
    aws iot attach-policy \
        --policy-name ${IOT_POLICY_NAME} \
        --target ${CERT_ARN} \
        --region ${REGION} 2>/dev/null || true
    
    # Attach certificate to thing
    aws iot attach-thing-principal \
        --thing-name ${THING_NAME} \
        --principal ${CERT_ARN} \
        --region ${REGION} 2>/dev/null || true
    
    # Get IoT endpoint
    IOT_ENDPOINT=$(aws iot describe-endpoint --endpoint-type iot:Data-ATS --region ${REGION} --query endpointAddress --output text)
    echo "IOT_ENDPOINT=${IOT_ENDPOINT}" > .env
    
    echo -e "${GREEN}✓ IoT Thing created: ${THING_NAME}${NC}"
    echo -e "${GREEN}✓ IoT Endpoint: ${IOT_ENDPOINT}${NC}"
}

# Function to create DynamoDB tables
create_dynamodb_tables() {
    echo -e "${YELLOW}Creating DynamoDB tables...${NC}"
    
    # Table 1: Sensor Data
    aws dynamodb create-table \
        --table-name ${DYNAMODB_TABLE1} \
        --attribute-definitions \
            AttributeName=deviceId,AttributeType=S \
            AttributeName=timestamp,AttributeType=S \
        --key-schema \
            AttributeName=deviceId,KeyType=HASH \
            AttributeName=timestamp,KeyType=RANGE \
        --billing-mode PAY_PER_REQUEST \
        --region ${REGION} 2>/dev/null || echo "Table ${DYNAMODB_TABLE1} already exists"
    
    # Table 2: Action Log
    aws dynamodb create-table \
        --table-name ${DYNAMODB_TABLE2} \
        --attribute-definitions \
            AttributeName=deviceId,AttributeType=S \
            AttributeName=timestamp,AttributeType=S \
        --key-schema \
            AttributeName=deviceId,KeyType=HASH \
            AttributeName=timestamp,KeyType=RANGE \
        --billing-mode PAY_PER_REQUEST \
        --region ${REGION} 2>/dev/null || echo "Table ${DYNAMODB_TABLE2} already exists"
    
    echo -e "${GREEN}✓ DynamoDB tables created${NC}"
}

# Function to create Lambda function
create_lambda_function() {
    echo -e "${YELLOW}Creating Lambda function...${NC}"
    
    # Create IAM role for Lambda
    LAMBDA_ROLE_NAME="SmartGardenLambdaRole"
    
    TRUST_POLICY='{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": {
            "Service": "lambda.amazonaws.com"
          },
          "Action": "sts:AssumeRole"
        }
      ]
    }'
    
    aws iam create-role \
        --role-name ${LAMBDA_ROLE_NAME} \
        --assume-role-policy-document "${TRUST_POLICY}" 2>/dev/null || echo "Role already exists"
    
    # Attach policies
    aws iam attach-role-policy \
        --role-name ${LAMBDA_ROLE_NAME} \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    aws iam attach-role-policy \
        --role-name ${LAMBDA_ROLE_NAME} \
        --policy-arn arn:aws:iam::aws:policy/AWSIoTDataAccess
    
    aws iam attach-role-policy \
        --role-name ${LAMBDA_ROLE_NAME} \
        --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
    
    aws iam attach-role-policy \
        --role-name ${LAMBDA_ROLE_NAME} \
        --policy-arn arn:aws:iam::aws:policy/AmazonSNSFullAccess
    
    sleep 10  # Wait for role propagation
    
    # Package Lambda function
    cd lambda
    zip -r ../function.zip . -x "*.pyc" "__pycache__/*"
    cd ..
    
    LAMBDA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"
    
    # Create or update Lambda function
    aws lambda create-function \
        --function-name ${LAMBDA_FUNCTION_NAME} \
        --runtime python3.11 \
        --role ${LAMBDA_ROLE_ARN} \
        --handler handler.lambda_handler \
        --zip-file fileb://function.zip \
        --timeout 30 \
        --memory-size 256 \
        --region ${REGION} 2>/dev/null || \
    aws lambda update-function-code \
        --function-name ${LAMBDA_FUNCTION_NAME} \
        --zip-file fileb://function.zip \
        --region ${REGION}
    
    rm function.zip
    
    echo -e "${GREEN}✓ Lambda function created${NC}"
}

# Function to create IoT Rule
create_iot_rule() {
    echo -e "${YELLOW}Creating IoT Rule...${NC}"
    
    LAMBDA_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${LAMBDA_FUNCTION_NAME}"
    
    # Create IoT Rule
    RULE_PAYLOAD='{
      "sql": "SELECT * FROM '"'"'garden/telemetry'"'"'",
      "description": "Process garden sensor data",
      "actions": [
        {
          "lambda": {
            "functionArn": "'${LAMBDA_ARN}'"
          }
        }
      ],
      "ruleDisabled": false
    }'
    
    aws iot create-topic-rule \
        --rule-name ProcessGardenData \
        --topic-rule-payload "${RULE_PAYLOAD}" \
        --region ${REGION} 2>/dev/null || echo "Rule already exists"
    
    # Add Lambda permission for IoT
    aws lambda add-permission \
        --function-name ${LAMBDA_FUNCTION_NAME} \
        --statement-id iot-invoke \
        --action lambda:InvokeFunction \
        --principal iot.amazonaws.com \
        --source-arn "arn:aws:iot:${REGION}:${ACCOUNT_ID}:rule/ProcessGardenData" \
        --region ${REGION} 2>/dev/null || true
    
    echo -e "${GREEN}✓ IoT Rule created${NC}"
}

# Function to create SNS topic
create_sns_topic() {
    echo -e "${YELLOW}Creating SNS topic...${NC}"
    
    SNS_ARN=$(aws sns create-topic \
        --name ${SNS_TOPIC_NAME} \
        --region ${REGION} \
        --query TopicArn \
        --output text)
    
    echo "SNS_TOPIC_ARN=${SNS_ARN}" >> .env
    
    echo -e "${GREEN}✓ SNS topic created: ${SNS_ARN}${NC}"
    echo -e "${YELLOW}  Subscribe to receive alerts:${NC}"
    echo "  aws sns subscribe --topic-arn ${SNS_ARN} --protocol email --notification-endpoint your-email@example.com"
}

# Function to create config file
create_config_file() {
    echo -e "${YELLOW}Creating configuration file...${NC}"
    
    cat > ../arduino/smart_garden/config.h << EOF
// WiFi Configuration
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// AWS IoT Configuration
#define AWS_IOT_ENDPOINT "${IOT_ENDPOINT}"
#define MQTT_PORT 8883

// MQTT Topics
#define TELEMETRY_TOPIC "garden/telemetry"
#define COMMAND_TOPIC "garden/commands"

// Pin Configuration
#define SOIL_SENSOR_PIN 34
#define PUMP_RELAY_PIN 5

// Sensor Thresholds (calibrate these values)
#define AIR_VALUE 3000       // Sensor reading in dry air
#define WATER_VALUE 1000     // Sensor reading in water
#define DRY_THRESHOLD 2000
#define WET_THRESHOLD 1000

// Timing Configuration
#define PUBLISH_INTERVAL 60000  // Publish every 60 seconds

// Device Information
#define DEVICE_ID "garden_sensor_01"
EOF
    
    echo -e "${GREEN}✓ Config file created: arduino/smart_garden/config.h${NC}"
    echo -e "${YELLOW}  Please update WiFi credentials in this file${NC}"
}

# Function to display certificate instructions
display_certificate_instructions() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Setup Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo ""
    echo "1. Update Arduino configuration:"
    echo "   - Open: arduino/smart_garden/config.h"
    echo "   - Add your WiFi SSID and password"
    echo ""
    echo "2. Add certificates to Arduino code:"
    echo "   - Open: arduino/smart_garden/smart_garden.ino"
    echo "   - Copy contents from:"
    echo "     * certificates/AmazonRootCA1.pem → root_ca"
    echo "     * certificates/certificate.pem.crt → certificate"
    echo "     * certificates/private.pem.key → private_key"
    echo ""
    echo "3. Upload Arduino code to ESP32"
    echo ""
    echo "4. Subscribe to SNS topic for alerts:"
    echo "   aws sns subscribe --topic-arn $(grep SNS_TOPIC_ARN .env | cut -d= -f2) \\"
    echo "     --protocol email --notification-endpoint your-email@example.com"
    echo ""
    echo "5. Configure Lambda environment variables:"
    echo "   aws lambda update-function-configuration \\"
    echo "     --function-name ${LAMBDA_FUNCTION_NAME} \\"
    echo "     --environment Variables={WEATHER_API_KEY=your_key,LOCATION=your_city}"
    echo ""
    echo -e "${GREEN}IoT Endpoint: ${IOT_ENDPOINT}${NC}"
    echo -e "${GREEN}Configuration saved to: .env${NC}"
    echo ""
}

# Main execution
main() {
    echo "This script will create AWS resources for the Smart Garden System."
    echo "Estimated time: 2-3 minutes"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 0
    fi
    
    create_iot_thing
    create_dynamodb_tables
    create_lambda_function
    create_iot_rule
    create_sns_topic
    create_config_file
    display_certificate_instructions
}

# Run main function
main