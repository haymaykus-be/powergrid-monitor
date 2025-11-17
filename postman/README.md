# Postman Collection for Power Grid Monitor

This folder contains a Postman collection with all API endpoints for the Power Grid Monitor application.

## Importing the Collection

1. **Open Postman**
2. Click **Import** button (top left)
3. Select **File** tab
4. Choose `Power_Grid_Monitor.postman_collection.json`
5. Click **Import**

## Collection Structure

The collection is organized into folders:

### 1. Health & Monitoring

- **Health Check** - `GET /health`
  - Check service status, database, and MQTT connections
- **Prometheus Metrics (All)** - `GET /metrics`
  - Get all Prometheus metrics including Python built-ins (GC stats, info, etc.)
- **Prometheus Metrics (Custom Only)** - `GET /metrics/custom`
  - Get only custom application metrics (mqtt_ingest, validation_errors, batch_insert, etc.)
  - Excludes Python built-in metrics for cleaner output

### 2. Devices

- **List All Devices** - `GET /api/devices`
  - Get all unique device IDs with last seen timestamps
- **Get Device Data** - `GET /api/devices/{device_id}`
  - Get recent sensor readings for a specific device
  - Query params: `limit`, `hours`
- **Get Device Statistics** - `GET /api/devices/{device_id}/stats`
  - Get statistics (avg, min, max) for a device
  - Query params: `hours`

### 3. Data Query

- **Query Sensor Data** - `GET /api/data`
  - Flexible querying with filters
  - Query params: `device_id`, `limit`, `hours`, `start_time`, `end_time`
- **Query Data with Time Range** - `GET /api/data`
  - Example with ISO time range
- **Query All Devices Data** - `GET /api/data`
  - Get data from all devices

### 4. Alerts

- **Get Recent Alerts** - `GET /api/alerts`
  - Get anomaly alerts from Redis
  - Query params: `limit`
- **Get Alert Count** - `GET /api/alerts/count`
  - Get total number of alerts

## Environment Variables

The collection uses a base URL variable:

- `base_url`: `http://localhost:8001` (default)

You can create a Postman environment to override this:

1. Create new environment
2. Add variable: `base_url` = `http://your-host:8001`
3. Select the environment in Postman

## Example Requests

### Health Check

```
GET http://localhost:8001/health
```

### List Devices

```
GET http://localhost:8001/api/devices?limit=100
```

### Get Device Data

```
GET http://localhost:8001/api/devices/sensor_0?limit=50&hours=24
```

### Get Device Statistics

```
GET http://localhost:8001/api/devices/sensor_0/stats?hours=48
```

### Query Data

```
GET http://localhost:8001/api/data?device_id=sensor_0&limit=100&hours=12
```

### Get Alerts

```
GET http://localhost:8001/api/alerts?limit=20
```

## Testing Tips

1. **Start the services first**: Make sure the ingestion service is running
2. **Generate data**: Run the sensor simulator to populate data
3. **Check health**: Start with the health check endpoint
4. **Explore data**: Use device endpoints to see what data is available
5. **Monitor alerts**: Check alerts endpoint after anomaly detection runs

## API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc
