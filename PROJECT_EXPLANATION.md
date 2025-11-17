# Power Grid Monitor - Complete Project Explanation

## 🎯 Project Overview

**Power Grid Monitor** is an IoT monitoring system that simulates, collects, analyzes, and predicts issues in power grid infrastructure. It's designed as a complete end-to-end solution demonstrating:

- **Data Collection**: Simulating sensors and ingesting telemetry data
- **Data Storage**: Time-series database for historical data
- **Real-time Analysis**: Anomaly detection using machine learning
- **Predictive Analytics**: Maintenance prediction based on trends
- **Alerting**: Publishing alerts to a message queue

---

## 📊 System Architecture

```
┌─────────────────┐
│ Sensor Simulator│  ← Generates fake sensor data
│  (10 sensors)   │
└────────┬────────┘
         │ MQTT Protocol
         ▼
┌─────────────────┐
│  MQTT Broker    │  ← Message broker (Mosquitto)
│  (Mosquitto)    │
└────────┬────────┘
         │ Subscribe to "grid/sensors/#"
         ▼
┌─────────────────┐
│ Ingestion       │  ← FastAPI service
│ Service         │     - Receives MQTT messages
│ (FastAPI)       │     - Validates data
│                 │     - Batches & stores in DB
└────────┬────────┘
         │ Batch Insert
         ▼
┌─────────────────┐      ┌──────────────────┐
│  TimescaleDB    │◄─────┤ Anomaly Detection│
│  (PostgreSQL)   │      │ Engine           │
│                 │      │ (IsolationForest) │
│  Stores:        │      │                  │
│  - device_id    │      │ - Trains ML model│
│  - timestamp    │      │ - Detects anomalies
│  - voltage      │      │ - Publishes alerts
│  - current      │      └────────┬─────────┘
│  - temperature  │               │
└─────────────────┘               │ Alerts
                                  ▼
                         ┌─────────────────┐
                         │     Redis       │
                         │ alerts:anomalies│
                         └─────────────────┘
```

---

## 📁 Project Structure Explained

### 1. **`sensor_simulator/`** - Data Generation Layer

**Purpose**: Simulates power grid sensors to generate test data

**Files**:

- `simulator.py`: Main simulator script

**What it does**:

- Creates 10 virtual sensors (configurable)
- Each sensor generates readings every 1-3 seconds:
  - **Voltage**: ~230V ± 2V (normal), can spike to 250V+ or drop to 200V-
  - **Current**: ~4A ± 0.5A
  - **Temperature**: ~35°C ± 3°C
- Randomly injects anomalies (~1% chance) for testing
- Publishes data via MQTT to topics: `grid/sensors/sensor_0`, `grid/sensors/sensor_1`, etc.

**Key Features**:

- Async/await for concurrent sensor simulation
- Dry-run mode (no MQTT, just prints)
- Configurable sensor count
- Automatic reconnection handling

**Example Output**:

```json
{
  "device_id": "sensor_0",
  "timestamp": "2024-01-01T12:00:00",
  "voltage": 230.5,
  "current": 4.2,
  "temperature": 35.1
}
```

---

### 2. **`ingestion_service/`** - Data Ingestion Layer

**Purpose**: Receives MQTT messages and stores them in the database

**Files**:

- `main.py`: FastAPI application with HTTP endpoints
- `mqtt_handler.py`: MQTT client wrapper

#### `main.py` - FastAPI Service

**What it does**:

1. **Starts FastAPI server** on port 8001
2. **Connects to MQTT broker** and subscribes to `grid/sensors/#`
3. **Initializes database** schema (creates tables, indexes)
4. **Processes messages**:
   - Validates sensor data (voltage, current, temperature ranges)
   - Queues messages for batch processing
   - Inserts batches into database every 2 seconds or when batch reaches 100 records
5. **Exposes endpoints**:
   - `GET /health`: Service health check
   - `GET /metrics`: Prometheus metrics

**Key Features**:

- Async message processing
- Batch database inserts (efficient)
- Data validation before storage
- Prometheus metrics collection
- OpenTelemetry tracing (optional)

**Metrics Exposed**:

- `mqtt_ingest_total`: Total messages processed
- `mqtt_ingest_errors_total`: Processing errors
- `validation_errors_total`: Invalid data rejected

#### `mqtt_handler.py` - MQTT Client

**What it does**:

- Wraps paho-mqtt client
- Handles connection/disconnection
- Converts MQTT messages to `SensorData` objects
- Thread-safe async callback handling
- Automatic reconnection

---

### 3. **`common/`** - Shared Components

**Purpose**: Reusable code shared across all services

#### `models.py` - Data Models

**Classes**:

- `SensorData`: Represents a sensor reading
  - Fields: `device_id`, `timestamp`, `voltage`, `current`, `temperature`
  - Methods: `to_dict()`, `from_dict()` for serialization
- `AnomalyAlert`: Represents a detected anomaly
  - Fields: `device_id`, `timestamp`, `metric`, `value`, `severity`, `description`
- `MaintenancePrediction`: Represents maintenance forecast
  - Fields: `device_id`, `predicted_failure_date`, `confidence`, `risk_factors`, `recommended_actions`

#### `database.py` - Database Operations

**Class**: `Database`

**What it does**:

- Manages PostgreSQL/TimescaleDB connection pool
- Creates schema (tables, indexes, hypertables)
- Handles both regular PostgreSQL and TimescaleDB
- Provides methods:
  - `insert_sensor_data()`: Insert single record
  - `insert_batch()`: Batch insert (efficient)
  - `get_recent_data()`: Query recent records
  - `get_device_stats()`: Calculate statistics (avg, min, max)

**Schema**:

```sql
CREATE TABLE sensor_data (
    id SERIAL,
    device_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    voltage DOUBLE PRECISION NOT NULL,
    current DOUBLE PRECISION NOT NULL,
    temperature DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (id, timestamp)  -- Composite key for TimescaleDB
);
```

#### `telemetry.py` - Data Processing

**Class**: `TelemetryHandler`

**What it does**:

- Validates sensor data against safe ranges:
  - Voltage: 200-250V
  - Current: 0-10A
  - Temperature: 0-80°C
- Calculates statistics (mean, min, max)
- Filters data by time range, device ID, etc.

---

### 4. **`anomaly_detection/`** - Anomaly Detection Layer

**Purpose**: Detects unusual patterns in sensor data

#### `detector.py` - Statistical Anomaly Detection

**Class**: `AnomalyDetector`

**What it does**:

- Uses **statistical methods** (3-sigma rule)
- Checks each metric (voltage, current, temperature) against:
  - Absolute safety limits
  - Historical mean ± standard deviation
- Returns `AnomalyAlert` with severity (low/medium/high)

**Algorithm**:

1. Calculate mean and std dev from historical data
2. Check if current value deviates > 3σ from mean
3. Assign severity based on deviation magnitude

#### `engine.py` - ML-Based Anomaly Detection

**Class**: `AnomalyDetectionEngine`

**What it does**:

- Uses **IsolationForest** (scikit-learn) for ML-based detection
- Trains on historical data (last 24 hours by default)
- Analyzes recent data in batches
- Publishes alerts to Redis

**Features**:

- Feature engineering:
  - Raw values (voltage, current, temperature)
  - Derived features (power approximation, deviations from nominal)
- Configurable contamination rate (expected % of outliers)
- Continuous operation (runs every 60 seconds)
- Redis publishing:
  - List: `alerts:anomalies` (queue-based)
  - Channel: `alerts:anomalies:channel` (pub/sub)

**Workflow**:

1. Fetch training data from database
2. Train IsolationForest model
3. Fetch recent data for analysis
4. Detect anomalies
5. Publish alerts to Redis

---

### 5. **`predictive_maintenance/`** - Predictive Analytics Layer

**Purpose**: Predicts when equipment will need maintenance

#### `predictor.py` - Maintenance Predictor

**Class**: `MaintenancePredictor`

**What it does**:

- Analyzes historical trends:
  - Temperature trend (increasing = problem)
  - Voltage stability (high variance = problem)
  - Current patterns (spikes = load issues)
- Calculates predicted failure date
- Provides confidence score (0.0 to 1.0)
- Lists risk factors and recommended actions

**Analysis Methods**:

1. **Temperature Trend**: Linear regression to detect increasing temperature
2. **Voltage Variance**: High variance indicates instability
3. **Current Spikes**: Detects load anomalies
4. **Recent Anomalies**: Flags recent high temperatures

**Output Example**:

```python
MaintenancePrediction(
    device_id="sensor_0",
    predicted_failure_date=datetime(2024, 2, 15),
    confidence=0.75,
    risk_factors=["Temperature increasing at 0.8°C/day"],
    recommended_actions=["Check cooling systems"]
)
```

---

### 6. **Infrastructure Components**

#### `docker-compose.yml` - Container Orchestration

**Services**:

1. **mqtt-broker** (Mosquitto):

   - Port 1883: MQTT protocol
   - Port 9001: WebSocket
   - Anonymous access enabled

2. **postgres** (TimescaleDB):

   - PostgreSQL 15 with TimescaleDB extension
   - Port 5432
   - Database: `powergrid`
   - Persistent volume for data

3. **redis**:
   - Port 6379
   - Stores anomaly alerts
   - Persistent volume for data

#### `mosquitto/config/mosquitto.conf` - MQTT Configuration

- Listens on port 1883
- Allows anonymous connections
- Basic MQTT broker setup

---

### 7. **Utility Scripts**

#### `start.sh` - Automated Startup

**What it does**:

1. Checks Docker is running
2. Starts Docker services (MQTT, PostgreSQL, Redis)
3. Waits for database to be ready
4. Starts Ingestion Service (background)
5. Starts Anomaly Detection Engine (background)
6. Starts Sensor Simulator (background)
7. Tracks process IDs for cleanup

#### `stop.sh` - Cleanup Script

- Stops all Python processes
- Stops Docker services
- Cleans up PID files

#### `test_application.sh` - Health Checks

- Verifies all services are running
- Checks ports are accessible
- Tests endpoints
- Validates data flow

#### `test_components.py` - Unit Tests

- Tests individual components
- Validates models, handlers, detectors
- Can run without full infrastructure

#### `test_integration.sh` - End-to-End Tests

- Sends test MQTT message
- Verifies data appears in database
- Checks alerts appear in Redis
- Tests complete data flow

---

## 🔄 Complete Data Flow

### Step-by-Step Process:

1. **Sensor Simulator** generates data:

   ```
   sensor_0 → voltage: 230V, current: 4A, temp: 35°C
   ```

2. **MQTT Broker** receives and routes:

   ```
   Topic: grid/sensors/sensor_0
   Message: JSON payload
   ```

3. **Ingestion Service** processes:

   - Receives MQTT message
   - Validates data (voltage in range? current OK? temp safe?)
   - Queues for batch processing
   - Every 2 seconds or 100 messages: batch insert to database

4. **Database** stores:

   ```
   INSERT INTO sensor_data VALUES (...)
   ```

5. **Anomaly Detection Engine** (every 60 seconds):

   - Fetches recent data from database
   - Trains IsolationForest model
   - Detects anomalies
   - Publishes alerts to Redis

6. **Redis** stores alerts:
   ```
   LPUSH alerts:anomalies {alert_json}
   PUBLISH alerts:anomalies:channel {alert_json}
   ```

---

## 🛠️ Technology Stack

### Backend:

- **Python 3.12**: Main language
- **FastAPI**: Web framework for ingestion service
- **asyncpg**: Async PostgreSQL driver
- **paho-mqtt**: MQTT client library
- **scikit-learn**: Machine learning (IsolationForest)
- **numpy**: Numerical computations

### Infrastructure:

- **Docker Compose**: Container orchestration
- **Eclipse Mosquitto**: MQTT broker
- **TimescaleDB**: Time-series PostgreSQL extension
- **Redis**: In-memory data store for alerts

### Observability:

- **Prometheus**: Metrics collection
- **OpenTelemetry**: Distributed tracing (optional)

---

## 📈 Key Features

### 1. **Scalability**

- Async/await throughout (non-blocking I/O)
- Batch processing (efficient database writes)
- Connection pooling (database connections)
- Configurable sensor count

### 2. **Reliability**

- Error handling and validation
- Automatic reconnection (MQTT)
- Health check endpoints
- Graceful shutdown

### 3. **Observability**

- Prometheus metrics
- OpenTelemetry tracing (optional)
- Health endpoints
- Structured logging

### 4. **Flexibility**

- Works with or without TimescaleDB
- Optional Redis (anomaly detection still works)
- Configurable via environment variables
- Dry-run modes for testing

---

## 🎯 Use Cases

This system demonstrates:

1. **IoT Data Pipeline**: Complete flow from sensors to storage
2. **Real-time Processing**: MQTT → FastAPI → Database
3. **Time-Series Storage**: TimescaleDB for efficient time-based queries
4. **Machine Learning**: IsolationForest for anomaly detection
5. **Predictive Analytics**: Trend analysis for maintenance
6. **Microservices Architecture**: Separate services for different concerns
7. **Message Queuing**: Redis for alert distribution

---

## 🔍 How Each Component Works Together

1. **Simulator** → Generates realistic sensor data
2. **MQTT Broker** → Routes messages (pub/sub pattern)
3. **Ingestion Service** → Validates and stores data
4. **Database** → Provides historical data for analysis
5. **Anomaly Engine** → Analyzes patterns and detects issues
6. **Redis** → Distributes alerts to subscribers
7. **Predictive Maintenance** → Analyzes trends for forecasting

---

## 📝 Configuration

All services are configurable via environment variables:

```bash
# Database
DB_DSN=postgresql://user:pass@host:5432/dbname

# MQTT
BROKER_HOST=localhost
BROKER_PORT=1883

# Redis
REDIS_URL=redis://localhost:6379/0

# Tracing (optional)
ENABLE_TRACING=0  # Set to 1 for verbose trace output
```

---

## 🚀 Quick Start Summary

1. **Start infrastructure**: `docker compose up -d`
2. **Start ingestion**: `cd ingestion_service && python main.py`
3. **Start anomaly detection**: `cd anomaly_detection && python engine.py`
4. **Start simulator**: `cd sensor_simulator && python simulator.py`

Or use the automated script: `./start.sh`

---

This project demonstrates a production-ready IoT monitoring system with data collection, storage, analysis, and alerting capabilities!
