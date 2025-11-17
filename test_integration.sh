#!/bin/bash

# Integration Test - End-to-End Data Flow

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "Integration Test - End-to-End Data Flow"
echo "=========================================="
echo ""

# Check prerequisites
echo -e "${BLUE}[1] Checking prerequisites...${NC}"
if ! docker ps | grep -q powergrid-db; then
    echo -e "${RED}Error: Database container not running${NC}"
    exit 1
fi
if ! docker ps | grep -q powergrid-redis; then
    echo -e "${RED}Error: Redis container not running${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Prerequisites met${NC}"
echo ""

# Step 1: Send test MQTT message
echo -e "${BLUE}[2] Sending test MQTT message...${NC}"
TEST_DEVICE_ID="test_device_$(date +%s)"
TEST_PAYLOAD="{\"device_id\":\"$TEST_DEVICE_ID\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S)\",\"voltage\":250.0,\"current\":5.0,\"temperature\":45.0}"

if command -v mosquitto_pub > /dev/null 2>&1; then
    mosquitto_pub -h localhost -t "grid/sensors/$TEST_DEVICE_ID" -m "$TEST_PAYLOAD"
    echo -e "${GREEN}✓ Test message sent${NC}"
else
    echo -e "${YELLOW}⚠ mosquitto_pub not available, skipping MQTT test${NC}"
fi
echo ""

# Step 2: Wait for ingestion
echo -e "${BLUE}[3] Waiting for data ingestion (10 seconds)...${NC}"
sleep 10

# Step 3: Check database
echo -e "${BLUE}[4] Checking database for ingested data...${NC}"
RECORD_COUNT=$(docker exec powergrid-db psql -U postgres -d powergrid -t -c "SELECT COUNT(*) FROM sensor_data WHERE device_id = '$TEST_DEVICE_ID';" 2>/dev/null | tr -d ' ')

if [ -n "$RECORD_COUNT" ] && [ "$RECORD_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Data found in database ($RECORD_COUNT records)${NC}"
    
    # Show the record
    echo "Sample record:"
    docker exec powergrid-db psql -U postgres -d powergrid -c "SELECT device_id, voltage, current, temperature FROM sensor_data WHERE device_id = '$TEST_DEVICE_ID' LIMIT 1;"
else
    echo -e "${RED}✗ No data found in database${NC}"
    echo "  This might mean:"
    echo "    - Ingestion service is not running"
    echo "    - MQTT message was not received"
    echo "    - Database connection issue"
fi
echo ""

# Step 4: Check Redis alerts (after anomaly detection runs)
echo -e "${BLUE}[5] Checking Redis for alerts...${NC}"
ALERT_COUNT=$(docker exec powergrid-redis redis-cli LLEN alerts:anomalies 2>/dev/null || echo "0")

if [ "$ALERT_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Alerts found in Redis ($ALERT_COUNT alerts)${NC}"
    
    # Show a sample alert
    echo "Sample alert:"
    SAMPLE_ALERT=$(docker exec powergrid-redis redis-cli RPOP alerts:anomalies 2>/dev/null || echo "")
    if [ -n "$SAMPLE_ALERT" ]; then
        echo "$SAMPLE_ALERT" | python3 -m json.tool 2>/dev/null || echo "$SAMPLE_ALERT"
    fi
else
    echo -e "${YELLOW}⚠ No alerts yet (this is normal if anomaly detection engine is still training)${NC}"
fi
echo ""

# Step 5: Check service health
echo -e "${BLUE}[6] Checking service health...${NC}"
HEALTH_RESPONSE=$(curl -s http://localhost:8001/health 2>/dev/null || echo "")
if echo "$HEALTH_RESPONSE" | grep -q "status.*ok"; then
    echo -e "${GREEN}✓ Ingestion service is healthy${NC}"
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
else
    echo -e "${RED}✗ Ingestion service health check failed${NC}"
fi
echo ""

# Summary
echo "=========================================="
echo "Integration Test Summary"
echo "=========================================="
echo "Test device ID: $TEST_DEVICE_ID"
echo "Records in database: $RECORD_COUNT"
echo "Alerts in Redis: $ALERT_COUNT"
echo ""

if [ "$RECORD_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Integration test PASSED${NC}"
    echo "  Data successfully flowed: MQTT → Ingestion → Database"
    exit 0
else
    echo -e "${RED}✗ Integration test FAILED${NC}"
    echo "  Data flow is not working correctly"
    exit 1
fi

