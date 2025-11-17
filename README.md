# Power Grid Monitor

Power grid monitoring application with sensor simulation, data ingestion, anomaly detection, and predictive maintenance capabilities.

## Overview

This system provides a complete IoT monitoring solution for power grid infrastructure:

- **Sensor Simulator**: Simulates thousands of power grid sensors publishing telemetry data
- **MQTT Broker**: Message broker for sensor data transmission
- **Ingestion Service**: FastAPI service that consumes MQTT messages and stores them in TimescaleDB
- **Anomaly Detection**: Real-time anomaly detection using statistical methods
- **Predictive Maintenance**: Trend analysis and failure prediction

## Project Structure

```
├── sensor_simulator/
│   └── simulator.py          # Sensor data simulator
├── ingestion_service/
│   ├── main.py               # FastAPI ingestion service
│   └── mqtt_handler.py       # MQTT client handler
├── anomaly_detection/
│   ├── detector.py           # Statistical anomaly detection
│   └── engine.py             # IsolationForest-based detection engine
├── predictive_maintenance/
│   └── predictor.py          # Maintenance prediction engine
├── common/
│   ├── models.py             # Data models (SensorData, AnomalyAlert, etc.)
│   ├── database.py           # Database connection and operations
│   └── telemetry.py          # Telemetry data processing
├── mosquitto/
│   └── config/
│       └── mosquitto.conf    # MQTT broker configuration
├── docker-compose.yml        # Docker Compose configuration
├── requirements.txt          # Python dependencies
└── README.md
```

## Prerequisites

- Python 3.8+
- Docker and Docker Compose (for MQTT broker)
- PostgreSQL with TimescaleDB extension (optional, but recommended)
- Redis (for anomaly alerts, optional)

## Installation

1. **Clone the repository** (if applicable):

```bash
git clone <repository-url>
cd powergrid-monitor
```

2. **Create and activate virtual environment**:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:

```bash
pip install -r requirements.txt
```

4. **Set up database** (PostgreSQL with TimescaleDB):

```bash
# Using Docker (recommended)
docker run -d \
  --name powergrid-db \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=powergrid \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg15

# Or install TimescaleDB on existing PostgreSQL
# See: https://docs.timescale.com/install/latest/self-hosted/
```

5. **Set up Redis** (for anomaly alerts):

```bash
# Using Docker (recommended)
docker run -d \
  --name powergrid-redis \
  -p 6379:6379 \
  redis:latest
```

## Configuration

### Environment Variables

The ingestion service uses the following environment variables:

- `DB_DSN`: Database connection string (default: `postgresql://postgres:password@localhost:5432/powergrid`)
- `BROKER_HOST`: MQTT broker host (default: `localhost`)
- `BROKER_PORT`: MQTT broker port (default: `1883`)
- `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379/0`)
- `ENABLE_TRACING`: Enable OpenTelemetry console tracing (default: `0`, set to `1` to enable verbose trace output)

Example:

```bash
export DB_DSN="postgresql://user:pass@localhost:5432/powergrid"
export BROKER_HOST="localhost"
export BROKER_PORT="1883"
```

## Quick Start

For complete setup and running instructions, see **[RUNNING.md](RUNNING.md)**.

For testing instructions, see **[TESTING.md](TESTING.md)**.

**Quick start with automated script:**

```bash
# Activate virtual environment
source venv/bin/activate

# Start all services (Docker + Python services)
./start.sh

# Stop all services
./stop.sh
```

## Usage

### 1. Start MQTT Broker

```bash
docker compose up -d mqtt-broker
```

This starts an Eclipse Mosquitto MQTT broker on port 1883.

### 2. Start Ingestion Service

```bash
cd ingestion_service
python main.py
```

The service will:

- Connect to the MQTT broker
- Subscribe to `grid/sensors/#` topic
- Initialize database schema
- Start listening for sensor data

The service runs on `http://localhost:8001` with endpoints:

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

### 3. Run Sensor Simulator

In a separate terminal:

```bash
cd sensor_simulator
python simulator.py
```

Options:

```bash
# Dry-run mode (no MQTT, prints to console)
python simulator.py --dry-run

# Custom number of sensors
python simulator.py --sensors 500

# Custom MQTT broker
python simulator.py --host localhost --port 1883
```

The simulator will:

- Generate sensor data for 10 sensors by default
- Publish to MQTT topics: `grid/sensors/sensor_0`, `grid/sensors/sensor_1`, etc.
- Inject anomalies randomly (~1% of readings)

### 4. Start Anomaly Detection Engine

The anomaly detection engine uses IsolationForest to detect anomalies in sensor data and publishes alerts to Redis.

**Prerequisites:**

- Redis server running (can use Docker: `docker run -d -p 6379:6379 redis:latest`)

**Run the engine:**

```bash
cd anomaly_detection
python engine.py
```

**Options:**

```bash
# Run once instead of continuously
python engine.py --once

# Custom detection interval (default: 60 seconds)
python engine.py --interval 30

# Custom contamination rate (default: 0.1 = 10% expected outliers)
python engine.py --contamination 0.05

# Custom lookback period for training (default: 24 hours)
python engine.py --lookback-hours 48

# Custom batch size (default: 1000 records)
python engine.py --batch-size 500

# Custom database and Redis URLs
python engine.py --db-dsn "postgresql://user:pass@localhost:5432/powergrid" \
                 --redis-url "redis://localhost:6379/0"
```

The engine will:

- Fetch recent data from TimescaleDB
- Train IsolationForest model on historical data
- Detect anomalies in recent sensor readings
- Publish alerts to Redis list `alerts:anomalies` and channel `alerts:anomalies:channel`

**Consuming alerts from Redis:**

```python
import redis
import json

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Pop alerts from list
alert_json = r.rpop('alerts:anomalies')
if alert_json:
    alert = json.loads(alert_json)
    print(f"Anomaly: {alert['description']}")

# Or subscribe to channel for real-time alerts
pubsub = r.pubsub()
pubsub.subscribe('alerts:anomalies:channel')
for message in pubsub.listen():
    if message['type'] == 'message':
        alert = json.loads(message['data'])
        print(f"Real-time alert: {alert['description']}")
```

### 5. Using Anomaly Detection (Programmatic)

```python
from common.database import Database
from common.models import SensorData
from anomaly_detection.detector import AnomalyDetector
from datetime import datetime

# Initialize
db = Database()
await db.connect()
detector = AnomalyDetector(database=db)

# Detect anomalies in sensor data
sensor_data = SensorData(
    device_id="sensor_0",
    timestamp=datetime.utcnow(),
    voltage=250.0,  # Anomalous voltage
    current=4.0,
    temperature=35.0
)

alert = detector.detect_anomaly(sensor_data)
if alert:
    print(f"Anomaly detected: {alert.description}")
    print(f"Severity: {alert.severity}")
```

### 6. Using Predictive Maintenance

```python
from common.database import Database
from predictive_maintenance.predictor import MaintenancePredictor

# Initialize
db = Database()
await db.connect()
predictor = MaintenancePredictor(database=db)

# Predict maintenance for a device
prediction = await predictor.predict_maintenance("sensor_0", lookback_days=30)

print(f"Device: {prediction.device_id}")
print(f"Predicted failure date: {prediction.predicted_failure_date}")
print(f"Confidence: {prediction.confidence:.2%}")
print(f"Risk factors: {prediction.risk_factors}")
print(f"Recommended actions: {prediction.recommended_actions}")
```

## Data Flow

```
┌─────────────────┐
│ Sensor Simulator│
│  (10 sensors) │
└────────┬────────┘
         │ MQTT
         ▼
┌─────────────────┐
│  MQTT Broker    │
│  (Mosquitto)    │
└────────┬────────┘
         │ Subscribe
         ▼
┌─────────────────┐
│ Ingestion       │
│ Service         │
│ (FastAPI)       │
└────────┬────────┘
         │ Batch Insert
         ▼
┌─────────────────┐      ┌──────────────────┐
│  TimescaleDB    │◄─────┤ Anomaly Detection│
│  (PostgreSQL)   │      │ Engine           │
└─────────────────┘      │ (IsolationForest)│
                         └────────┬─────────┘
                                   │ Alerts
                                   ▼
                          ┌─────────────────┐
                          │     Redis       │
                          │ alerts:anomalies│
                          └─────────────────┘
```

## Monitoring

### Prometheus Metrics

The ingestion service exposes Prometheus metrics at `/metrics`:

- `mqtt_ingest_total`: Total MQTT messages ingested
- `mqtt_ingest_errors_total`: Total message processing errors
- `validation_errors_total`: Total validation errors

### Health Check

```bash
curl http://localhost:8001/health
```

Response:

```json
{
  "status": "ok",
  "queued_messages": 42,
  "mqtt_connected": true,
  "database_connected": true
}
```

## Development

### Running Tests

(Add test instructions when tests are added)

### Code Structure

- **Common modules** (`common/`): Shared functionality used across services
- **Services**: Independent services that can run separately
- **Models**: Data classes using Python dataclasses
- **Database**: Async PostgreSQL operations using asyncpg

## Troubleshooting

### MQTT Connection Issues

If the sensor simulator can't connect:

1. Check if MQTT broker is running: `docker ps | grep mosquitto`
2. Verify broker is accessible: `telnet localhost 1883`
3. Use `--dry-run` mode to test without MQTT

### Database Connection Issues

1. Verify PostgreSQL is running
2. Check connection string in `DB_DSN` environment variable
3. Ensure database exists: `createdb powergrid`
4. TimescaleDB extension is optional but recommended for time-series data

### High Memory Usage

The sensor simulator runs 10 concurrent async tasks by default. Adjust with:

```bash
python simulator.py --sensors 100
```

## License

TBD

## Contributing

TBD
