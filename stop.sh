#!/bin/bash

# Power Grid Monitor - Stop All Services

echo "Stopping Power Grid Monitor services..."

# Stop Python processes
if [ -f /tmp/powergrid_ingestion.pid ]; then
    PID=$(cat /tmp/powergrid_ingestion.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo "Stopped ingestion service (PID: $PID)"
    fi
    rm /tmp/powergrid_ingestion.pid
fi

if [ -f /tmp/powergrid_anomaly.pid ]; then
    PID=$(cat /tmp/powergrid_anomaly.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo "Stopped anomaly detection engine (PID: $PID)"
    fi
    rm /tmp/powergrid_anomaly.pid
fi

if [ -f /tmp/powergrid_simulator.pid ]; then
    PID=$(cat /tmp/powergrid_simulator.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo "Stopped sensor simulator (PID: $PID)"
    fi
    rm /tmp/powergrid_simulator.pid
fi

# Stop Docker services
echo "Stopping Docker services..."
docker compose down

echo "All services stopped."

