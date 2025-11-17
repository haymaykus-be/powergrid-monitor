# Testing Guide

This guide covers all testing approaches for the Power Grid Monitor application.

## Quick Test

Run the automated test script to check if all services are running correctly:

```bash
./test_application.sh
```

This will test:

- Docker services (MQTT, PostgreSQL, Redis)
- Service ports
- Ingestion service endpoints
- Database connectivity
- Redis connectivity
- Python service processes
- Data flow

## Test Types

### 1. Component Tests

Test individual Python components:

```bash
python test_components.py
```

Tests:

- `SensorData` model serialization
- `TelemetryHandler` validation
- `AnomalyDetector` anomaly detection
- Database operations (if database is running)
- Feature preparation for IsolationForest

### 2. Integration Tests

Test end-to-end data flow:

```bash
./test_integration.sh
```

This test:

1. Sends a test MQTT message
2. Waits for ingestion
3. Checks if data appears in database
4. Checks if alerts appear in Redis
5. Verifies service health

### 3. Application Tests

Comprehensive application health check:

```bash
./test_application.sh
```

## Manual Testing

### Test 1: Verify Services Are Running

```bash
# Check Docker containers
docker ps

# Check Python processes
ps aux | grep python | grep -E "(main.py|engine.py|simulator.py)"
```

### Test 2: Test MQTT Publishing

```bash
# Publish a test message
mosquitto_pub -h localhost -t "grid/sensors/test_sensor" -m '{
  "device_id": "test_sensor",
  "timestamp": "2024-01-01T12:00:00",
  "voltage": 230.0,
  "current": 4.0,
  "temperature": 35.0
}'

# Subscribe to see messages
mosquitto_sub -h localhost -t "grid/sensors/#" -v
```

### Test 3: Check Ingestion Service

```bash
# Health check
curl http://localhost:8001/health

# Metrics
curl http://localhost:8001/metrics

# Expected health response:
# {
#   "status": "ok",
#   "queued_messages": 0,
#   "mqtt_connected": true,
#   "database_connected": true
# }
```

### Test 4: Verify Database

```bash
# Connect to database
docker exec -it powergrid-db psql -U postgres -d powergrid

# Check table exists
\d sensor_data

# Count records
SELECT COUNT(*) FROM sensor_data;

# View recent data
SELECT device_id, timestamp, voltage, current, temperature
FROM sensor_data
ORDER BY timestamp DESC
LIMIT 10;

# Check for specific device
SELECT * FROM sensor_data WHERE device_id = 'test_sensor';
```

### Test 5: Verify Redis Alerts

```bash
# Check alert count
docker exec powergrid-redis redis-cli LLEN alerts:anomalies

# View alerts
docker exec powergrid-redis redis-cli LRANGE alerts:anomalies 0 4

# Pop an alert (removes it from list)
docker exec powergrid-redis redis-cli RPOP alerts:anomalies

# Subscribe to real-time alerts
docker exec -it powergrid-redis redis-cli SUBSCRIBE alerts:anomalies:channel
```

### Test 6: Test Anomaly Detection

```bash
# Send anomalous data via MQTT
mosquitto_pub -h localhost -t "grid/sensors/anomaly_test" -m '{
  "device_id": "anomaly_test",
  "timestamp": "2024-01-01T12:00:00",
  "voltage": 260.0,
  "current": 8.0,
  "temperature": 75.0
}'

# Wait for detection cycle (default: 60 seconds)
sleep 65

# Check for alerts
docker exec powergrid-redis redis-cli LLEN alerts:anomalies
```

### Test 7: Test Sensor Simulator

```bash
# Run simulator in dry-run mode (no MQTT)
cd sensor_simulator
python simulator.py --dry-run --sensors 5

# Run with fewer sensors for testing
python simulator.py --sensors 10
```

### Test 8: Test Anomaly Detection Engine

```bash
# Run engine once (for testing)
cd anomaly_detection
python engine.py --once

# Run with custom parameters
python engine.py --once --contamination 0.05 --batch-size 100
```

## Performance Testing

### Load Test: High Volume Data

```bash
# Run simulator with many sensors
cd sensor_simulator
python simulator.py --sensors 10

# Monitor ingestion rate
watch -n 1 'curl -s http://localhost:8001/metrics | grep mqtt_ingest_total'
```

### Stress Test: Database

```bash
# Check database performance
docker exec powergrid-db psql -U postgres -d powergrid -c "
SELECT
    COUNT(*) as total_records,
    COUNT(DISTINCT device_id) as unique_devices,
    MIN(timestamp) as earliest,
    MAX(timestamp) as latest
FROM sensor_data;
"
```

## Test Data Scenarios

### Scenario 1: Normal Operation

```bash
# Send normal sensor readings
for i in {1..10}; do
    mosquitto_pub -h localhost -t "grid/sensors/normal_$i" -m "{
        \"device_id\": \"normal_$i\",
        \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%S)\",
        \"voltage\": 230.0,
        \"current\": 4.0,
        \"temperature\": 35.0
    }"
    sleep 0.5
done
```

### Scenario 2: Voltage Anomaly

```bash
mosquitto_pub -h localhost -t "grid/sensors/voltage_anomaly" -m '{
  "device_id": "voltage_anomaly",
  "timestamp": "2024-01-01T12:00:00",
  "voltage": 260.0,
  "current": 4.0,
  "temperature": 35.0
}'
```

### Scenario 3: Temperature Anomaly

```bash
mosquitto_pub -h localhost -t "grid/sensors/temp_anomaly" -m '{
  "device_id": "temp_anomaly",
  "timestamp": "2024-01-01T12:00:00",
  "voltage": 230.0,
  "current": 4.0,
  "temperature": 80.0
}'
```

### Scenario 4: Current Spike

```bash
mosquitto_pub -h localhost -t "grid/sensors/current_spike" -m '{
  "device_id": "current_spike",
  "timestamp": "2024-01-01T12:00:00",
  "voltage": 230.0,
  "current": 9.5,
  "temperature": 35.0
}'
```

## Monitoring During Tests

### Watch Metrics

```bash
# Continuous monitoring
watch -n 2 'curl -s http://localhost:8001/metrics | grep -E "(mqtt_ingest|validation_errors)"'
```

### Monitor Database Growth

```bash
watch -n 5 'docker exec powergrid-db psql -U postgres -d powergrid -t -c "SELECT COUNT(*) FROM sensor_data;"'
```

### Monitor Redis Alerts

```bash
watch -n 5 'docker exec powergrid-redis redis-cli LLEN alerts:anomalies'
```

## Troubleshooting Tests

### Test Fails: Services Not Running

```bash
# Check what's running
docker ps
ps aux | grep python

# Start services
./start.sh
```

### Test Fails: No Data in Database

1. Check ingestion service is running: `curl http://localhost:8001/health`
2. Check MQTT messages are being published
3. Check database connection in ingestion service logs
4. Verify schema exists: `docker exec powergrid-db psql -U postgres -d powergrid -c "\d sensor_data"`

### Test Fails: No Alerts in Redis

1. Wait for initial training period (anomaly engine needs historical data)
2. Check engine is running: `ps aux | grep engine.py`
3. Manually trigger detection: `cd anomaly_detection && python engine.py --once`
4. Check for errors in engine output

### Test Fails: MQTT Connection

```bash
# Test MQTT broker
mosquitto_pub -h localhost -t test -m "test"
mosquitto_sub -h localhost -t test

# Check broker logs
docker logs powergrid-mqtt-broker
```

## Continuous Testing

For development, you can set up continuous testing:

```bash
# Watch for changes and re-run tests
while true; do
    ./test_application.sh
    sleep 60
done
```

## Test Coverage Goals

- ✅ All services start correctly
- ✅ MQTT messages are received
- ✅ Data is stored in database
- ✅ Anomalies are detected
- ✅ Alerts are published to Redis
- ✅ Health endpoints respond
- ✅ Metrics are collected
- ✅ Error handling works

## Next Steps

After testing:

1. Review test results
2. Fix any failing tests
3. Monitor production metrics
4. Set up automated testing in CI/CD
5. Add more comprehensive unit tests
