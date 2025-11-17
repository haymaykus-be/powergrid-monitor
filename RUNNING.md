# Running the Power Grid Monitor Application

This guide provides step-by-step instructions to run the full Power Grid Monitor application.

## Quick Start (Automated)

The easiest way to run everything is using the provided startup script:

```bash
# Make sure you're in the project root
cd powergrid-monitor

# Activate virtual environment
source venv/bin/activate

# Start all services
./start.sh
```

This will:

1. Start Docker services (MQTT, PostgreSQL, Redis)
2. Start the Ingestion Service
3. Start the Anomaly Detection Engine
4. Start the Sensor Simulator

To stop all services:

```bash
./stop.sh
```

## Manual Setup (Step by Step)

### Prerequisites

1. **Python 3.8+** with virtual environment activated
2. **Docker and Docker Compose** installed
3. **All dependencies installed**: `pip install -r requirements.txt`

### Step 1: Start Infrastructure Services (Docker)

Start MQTT broker, PostgreSQL/TimescaleDB, and Redis:

```bash
docker compose up -d
```

Verify services are running:

```bash
docker ps
```

You should see:

- `powergrid-mqtt-broker` (port 1883)
- `powergrid-db` (port 5432)
- `powergrid-redis` (port 6379)

### Step 2: Start Ingestion Service

The ingestion service receives MQTT messages and stores them in the database.

**Terminal 1:**

```bash
cd ingestion_service
python main.py
```

The service will:

- Connect to MQTT broker
- Initialize database schema
- Start listening on `http://localhost:8001`

**Verify it's working:**

```bash
curl http://localhost:8001/health
```

Expected response:

```json
{
  "status": "ok",
  "queued_messages": 0,
  "mqtt_connected": true,
  "database_connected": true
}
```

### Step 3: Start Anomaly Detection Engine

The anomaly detection engine analyzes data from the database and publishes alerts to Redis.

**Terminal 2:**

```bash
cd anomaly_detection
python engine.py
```

The engine will:

- Fetch data from TimescaleDB
- Train IsolationForest model
- Detect anomalies every 60 seconds (default)
- Publish alerts to Redis

**Verify it's working:**

```bash
# Check Redis for alerts
redis-cli LLEN alerts:anomalies
```

### Step 4: Start Sensor Simulator

The sensor simulator generates sensor data and publishes it via MQTT.

**Terminal 3:**

```bash
cd sensor_simulator
python simulator.py
```

The simulator will:

- Generate data for 10 sensors (default)
- Publish to MQTT topics: `grid/sensors/sensor_0`, `grid/sensors/sensor_1`, etc.
- Inject anomalies randomly (~1% of readings)

**Options:**

```bash
# Run with fewer sensors (for testing)
python simulator.py --sensors 100

# Dry-run mode (no MQTT, prints to console)
python simulator.py --dry-run
```

## Verification

### Check All Services

1. **Ingestion Service Health:**

   ```bash
   curl http://localhost:8001/health
   ```

2. **Prometheus Metrics:**

   ```bash
   curl http://localhost:8001/metrics
   ```

3. **Database Connection:**

   ```bash
   docker exec -it powergrid-db psql -U postgres -d powergrid -c "SELECT COUNT(*) FROM sensor_data;"
   ```

4. **Redis Alerts:**

   ```bash
   redis-cli LLEN alerts:anomalies
   redis-cli LRANGE alerts:anomalies 0 4  # View last 5 alerts
   ```

5. **MQTT Messages:**

   ```bash
   # Install mosquitto clients if needed
   # macOS: brew install mosquitto
   # Ubuntu: sudo apt-get install mosquitto-clients

   mosquitto_sub -h localhost -t "grid/sensors/#" -v
   ```

## Monitoring the Application

### View Logs

**Docker services:**

```bash
docker compose logs -f
```

**Individual service logs:**

```bash
docker compose logs -f mqtt-broker
docker compose logs -f postgres
docker compose logs -f redis
```

### Check Database

```bash
# Connect to database
docker exec -it powergrid-db psql -U postgres -d powergrid

# View recent sensor data
SELECT device_id, timestamp, voltage, current, temperature
FROM sensor_data
ORDER BY timestamp DESC
LIMIT 10;

# Count records
SELECT COUNT(*) FROM sensor_data;

# View by device
SELECT device_id, COUNT(*) as count
FROM sensor_data
GROUP BY device_id
ORDER BY count DESC
LIMIT 10;
```

### Check Redis Alerts

```bash
# View alert count
redis-cli LLEN alerts:anomalies

# Pop and view an alert
redis-cli RPOP alerts:anomalies

# Subscribe to real-time alerts
redis-cli SUBSCRIBE alerts:anomalies:channel
```

### View Prometheus Metrics

```bash
# Get metrics
curl http://localhost:8001/metrics

# Key metrics:
# - mqtt_ingest_total: Total messages ingested
# - mqtt_ingest_errors_total: Total errors
# - validation_errors_total: Total validation errors
```

## Troubleshooting

### Services Won't Start

1. **Check Docker is running:**

   ```bash
   docker ps
   ```

2. **Check ports are available:**

   ```bash
   # Check if ports are in use
   lsof -i :1883  # MQTT
   lsof -i :5432  # PostgreSQL
   lsof -i :6379  # Redis
   lsof -i :8001  # Ingestion Service
   ```

3. **Check virtual environment:**
   ```bash
   which python  # Should point to venv
   pip list      # Should show all dependencies
   ```

### Database Connection Issues

1. **Verify database is ready:**

   ```bash
   docker exec powergrid-db pg_isready -U postgres
   ```

2. **Check connection string:**

   ```bash
   echo $DB_DSN
   # Should be: postgresql://postgres:password@localhost:5432/powergrid
   ```

3. **Test connection:**
   ```bash
   docker exec -it powergrid-db psql -U postgres -d powergrid -c "SELECT 1;"
   ```

### MQTT Connection Issues

1. **Verify MQTT broker is running:**

   ```bash
   docker ps | grep mosquitto
   ```

2. **Test MQTT connection:**
   ```bash
   mosquitto_pub -h localhost -t test/topic -m "test message"
   mosquitto_sub -h localhost -t test/topic
   ```

### Redis Connection Issues

1. **Verify Redis is running:**

   ```bash
   docker ps | grep redis
   redis-cli ping  # Should return PONG
   ```

2. **Check Redis URL:**
   ```bash
   echo $REDIS_URL
   # Should be: redis://localhost:6379/0
   ```

### No Data in Database

1. **Check ingestion service is running:**

   ```bash
   curl http://localhost:8001/health
   ```

2. **Check sensor simulator is publishing:**

   ```bash
   mosquitto_sub -h localhost -t "grid/sensors/#" -v
   ```

3. **Check database schema:**
   ```bash
   docker exec -it powergrid-db psql -U postgres -d powergrid -c "\d sensor_data"
   ```

### No Alerts in Redis

1. **Wait for initial training:** The anomaly detection engine needs to train on historical data first (default: 24 hours). If you just started, there may not be enough data yet.

2. **Check engine is running:**

   ```bash
   ps aux | grep engine.py
   ```

3. **Run detection once manually:**

   ```bash
   cd anomaly_detection
   python engine.py --once
   ```

4. **Check for errors in engine logs**

## Stopping the Application

### Using the Stop Script

```bash
./stop.sh
```

### Manually

1. **Stop Python processes:**

   - Press `Ctrl+C` in each terminal running a service
   - Or find and kill processes:
     ```bash
     pkill -f "python.*main.py"
     pkill -f "python.*engine.py"
     pkill -f "python.*simulator.py"
     ```

2. **Stop Docker services:**

   ```bash
   docker compose down
   ```

3. **Stop and remove volumes (clean slate):**
   ```bash
   docker compose down -v
   ```

## Environment Variables

You can customize the configuration using environment variables:

```bash
# Database
export DB_DSN="postgresql://postgres:password@localhost:5432/powergrid"

# MQTT
export BROKER_HOST="localhost"
export BROKER_PORT="1883"

# Redis
export REDIS_URL="redis://localhost:6379/0"
```

## Next Steps

Once everything is running:

1. **Monitor the dashboard:** Check `/health` and `/metrics` endpoints
2. **View alerts:** Monitor Redis for anomaly alerts
3. **Analyze data:** Query the database for sensor statistics
4. **Customize:** Adjust detection parameters, sensor count, etc.

## Production Considerations

For production deployment:

1. **Use environment-specific configuration**
2. **Set up proper logging** (file-based, centralized)
3. **Add monitoring/alerting** (Prometheus + Grafana)
4. **Secure services** (authentication, TLS)
5. **Use process managers** (systemd, supervisor, etc.)
6. **Set up backups** for database
7. **Use connection pooling** and resource limits
8. **Implement graceful shutdown** handlers
