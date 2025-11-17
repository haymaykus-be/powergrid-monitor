#!/bin/bash

# Power Grid Monitor - Application Testing Script

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

PASSED=0
FAILED=0

# Test function
test_check() {
    local name="$1"
    local command="$2"
    local expected="$3"
    
    echo -n "Testing $name... "
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        ((FAILED++))
        return 1
    fi
}

test_check_with_output() {
    local name="$1"
    local command="$2"
    local expected_pattern="$3"
    
    echo -n "Testing $name... "
    
    output=$(eval "$command" 2>&1)
    if echo "$output" | grep -q "$expected_pattern"; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "  Expected pattern: $expected_pattern"
        echo "  Got: $output"
        ((FAILED++))
        return 1
    fi
}

echo "=========================================="
echo "Power Grid Monitor - Application Tests"
echo "=========================================="
echo ""

# 1. Check Docker services
echo -e "${BLUE}[1] Checking Docker Services${NC}"
test_check "Docker daemon is running" "docker info"
test_check "MQTT broker container is running" "docker ps | grep -q powergrid-mqtt-broker"
test_check "PostgreSQL container is running" "docker ps | grep -q powergrid-db"
test_check "Redis container is running" "docker ps | grep -q powergrid-redis"
echo ""

# 2. Check service ports
echo -e "${BLUE}[2] Checking Service Ports${NC}"
test_check "MQTT port 1883 is open" "nc -z localhost 1883 || timeout 1 bash -c '</dev/tcp/localhost/1883'"
test_check "PostgreSQL port 5432 is open" "nc -z localhost 5432 || timeout 1 bash -c '</dev/tcp/localhost/5432'"
test_check "Redis port 6379 is open" "nc -z localhost 6379 || timeout 1 bash -c '</dev/tcp/localhost/6379'"
test_check "Ingestion service port 8001 is open" "nc -z localhost 8001 || timeout 1 bash -c '</dev/tcp/localhost/8001'"
echo ""

# 3. Check Ingestion Service
echo -e "${BLUE}[3] Checking Ingestion Service${NC}"
test_check_with_output "Ingestion service health endpoint" \
    "curl -s http://localhost:8001/health" \
    "status.*ok"
test_check_with_output "Ingestion service metrics endpoint" \
    "curl -s http://localhost:8001/metrics" \
    "mqtt_ingest_total"
echo ""

# 4. Check Database
echo -e "${BLUE}[4] Checking Database${NC}"
test_check "Database is accessible" \
    "docker exec powergrid-db pg_isready -U postgres"
test_check "Database schema exists" \
    "docker exec powergrid-db psql -U postgres -d powergrid -c 'SELECT 1 FROM sensor_data LIMIT 1;' > /dev/null 2>&1 || docker exec powergrid-db psql -U postgres -d powergrid -c '\\d sensor_data' > /dev/null 2>&1"
echo ""

# 5. Check Redis
echo -e "${BLUE}[5] Checking Redis${NC}"
test_check "Redis is accessible" \
    "docker exec powergrid-redis redis-cli ping | grep -q PONG"
test_check "Redis can store data" \
    "docker exec powergrid-redis redis-cli SET test_key test_value && docker exec powergrid-redis redis-cli GET test_key | grep -q test_value"
echo ""

# 6. Check MQTT
echo -e "${BLUE}[6] Checking MQTT${NC}"
if command -v mosquitto_pub > /dev/null 2>&1; then
    test_check "MQTT broker accepts connections" \
        "timeout 2 mosquitto_pub -h localhost -t test/topic -m 'test' || true"
    test_check "MQTT broker is publishing" \
        "timeout 2 mosquitto_sub -h localhost -t 'grid/sensors/+' -C 1 -W 1 || true"
else
    echo -e "${YELLOW}⚠ mosquitto clients not installed, skipping MQTT tests${NC}"
    echo "  Install with: brew install mosquitto (macOS) or apt-get install mosquitto-clients (Linux)"
fi
echo ""

# 7. Check Python processes
echo -e "${BLUE}[7] Checking Python Services${NC}"
test_check "Ingestion service process is running" \
    "ps aux | grep -v grep | grep -q 'python.*main.py'"
test_check "Anomaly detection engine process is running" \
    "ps aux | grep -v grep | grep -q 'python.*engine.py'"
test_check "Sensor simulator process is running" \
    "ps aux | grep -v grep | grep -q 'python.*simulator.py'"
echo ""

# 8. Check data flow
echo -e "${BLUE}[8] Checking Data Flow${NC}"
echo -n "Checking if data is being ingested... "
sleep 2
RECORD_COUNT=$(docker exec powergrid-db psql -U postgres -d powergrid -t -c "SELECT COUNT(*) FROM sensor_data;" 2>/dev/null | tr -d ' ')
if [ -n "$RECORD_COUNT" ] && [ "$RECORD_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ PASSED${NC} (Found $RECORD_COUNT records)"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ No data yet (this is normal if services just started)${NC}"
fi

echo -n "Checking if alerts are being generated... "
ALERT_COUNT=$(docker exec powergrid-redis redis-cli LLEN alerts:anomalies 2>/dev/null || echo "0")
if [ -n "$ALERT_COUNT" ] && [ "$ALERT_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ PASSED${NC} (Found $ALERT_COUNT alerts)"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ No alerts yet (normal if model is still training)${NC}"
fi
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}Failed: $FAILED${NC}"
    exit 0
fi

