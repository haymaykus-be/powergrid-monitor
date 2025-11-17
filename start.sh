#!/bin/bash

# Power Grid Monitor - Full Application Startup Script

set -e

echo "=========================================="
echo "Power Grid Monitor - Starting Services"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}Warning: Virtual environment not activated.${NC}"
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Set PYTHONPATH to project root
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Check if Docker is running
echo -e "\n${GREEN}Checking Docker...${NC}"
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker daemon is not running!${NC}"
    echo ""
    echo "Please start Docker Desktop or Docker daemon:"
    echo "  - macOS: Open Docker Desktop application"
    echo "  - Linux: sudo systemctl start docker"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓ Docker is running${NC}"

# Step 1: Start Docker services (MQTT, PostgreSQL, Redis)
echo -e "\n${GREEN}[1/5] Starting Docker services...${NC}"
docker compose up -d

echo "Waiting for services to be ready..."
sleep 5

# Check if services are running
if ! docker ps | grep -q powergrid-mqtt-broker; then
    echo -e "${RED}Error: MQTT broker failed to start${NC}"
    exit 1
fi

if ! docker ps | grep -q powergrid-db; then
    echo -e "${RED}Error: PostgreSQL failed to start${NC}"
    exit 1
fi

if ! docker ps | grep -q powergrid-redis; then
    echo -e "${RED}Error: Redis failed to start${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker services started${NC}"

# Step 2: Wait for database to be ready
echo -e "\n${GREEN}[2/5] Waiting for database to be ready...${NC}"
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker exec powergrid-db pg_isready -U postgres > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Database is ready${NC}"
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}Error: Database did not become ready in time${NC}"
    exit 1
fi

# Step 3: Start Ingestion Service
echo -e "\n${GREEN}[3/5] Starting Ingestion Service...${NC}"
cd ingestion_service
python main.py &
INGESTION_PID=$!
cd - > /dev/null
echo -e "${GREEN}✓ Ingestion service started (PID: $INGESTION_PID)${NC}"

# Wait for ingestion service to start
sleep 3

# Step 4: Start Anomaly Detection Engine
echo -e "\n${GREEN}[4/5] Starting Anomaly Detection Engine...${NC}"
cd anomaly_detection
python engine.py &
ANOMALY_PID=$!
cd - > /dev/null
echo -e "${GREEN}✓ Anomaly detection engine started (PID: $ANOMALY_PID)${NC}"

# Step 5: Start Sensor Simulator
echo -e "\n${GREEN}[5/5] Starting Sensor Simulator...${NC}"
cd sensor_simulator
python simulator.py &
SIMULATOR_PID=$!
cd - > /dev/null
echo -e "${GREEN}✓ Sensor simulator started (PID: $SIMULATOR_PID)${NC}"

echo -e "\n${GREEN}=========================================="
echo "All services started successfully!"
echo "==========================================${NC}"
echo ""
echo "Services running:"
echo "  - MQTT Broker:      localhost:1883"
echo "  - PostgreSQL:       localhost:5432"
echo "  - Redis:            localhost:6379"
echo "  - Ingestion Service: http://localhost:8001"
echo "  - Health Check:      http://localhost:8001/health"
echo "  - Metrics:          http://localhost:8001/metrics"
echo ""
echo "Process IDs:"
echo "  - Ingestion Service: $INGESTION_PID"
echo "  - Anomaly Detection:  $ANOMALY_PID"
echo "  - Sensor Simulator:   $SIMULATOR_PID"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Save PIDs to file for cleanup
echo "$INGESTION_PID" > /tmp/powergrid_ingestion.pid
echo "$ANOMALY_PID" > /tmp/powergrid_anomaly.pid
echo "$SIMULATOR_PID" > /tmp/powergrid_simulator.pid

# Wait for interrupt
trap "echo -e '\n${YELLOW}Stopping services...${NC}'; kill $INGESTION_PID $ANOMALY_PID $SIMULATOR_PID 2>/dev/null; exit" INT TERM

# Keep script running
wait

